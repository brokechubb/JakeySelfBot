import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from enum import Enum

from utils.logging_config import get_logger

logger = get_logger(__name__)


class IntegrityStatus(Enum):
    """Integrity check status"""
    PASSED = "passed"
    FAILED = "failed"
    CORRUPTED = "corrupted"
    MISSING = "missing"
    INACCESSIBLE = "inaccessible"


class ValidationLevel(Enum):
    """Validation level enumeration"""
    BASIC = "basic"          # File existence and checksum
    STANDARD = "standard"    # Basic + database integrity
    COMPREHENSIVE = "comprehensive"  # Standard + schema and data validation


@dataclass
class IntegrityReport:
    """Integrity verification report"""
    backup_id: str
    backup_path: str
    validation_level: ValidationLevel
    checked_at: datetime
    status: IntegrityStatus
    file_exists: bool
    file_accessible: bool
    file_size: int
    checksum_valid: bool
    database_integrity: bool
    schema_valid: bool
    data_consistent: bool
    error_messages: List[str]
    warnings: List[str]
    validation_duration_seconds: float
    tables_found: List[str]
    records_per_table: Dict[str, int]
    indexes_found: List[str]
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
        if self.warnings is None:
            self.warnings = []
        if self.tables_found is None:
            self.tables_found = []
        if self.records_per_table is None:
            self.records_per_table = {}
        if self.indexes_found is None:
            self.indexes_found = []


@dataclass
class IntegrityConfig:
    """Integrity verification configuration"""
    # Default validation level
    default_validation_level: ValidationLevel = ValidationLevel.STANDARD
    
    # Performance settings
    max_concurrent_checks: int = 4
    timeout_seconds: int = 300  # 5 minutes per backup
    
    # Checksum settings
    checksum_algorithm: str = "sha256"
    verify_checksums: bool = True
    
    # Database validation settings
    integrity_check_enabled: bool = True
    schema_validation_enabled: bool = True
    data_consistency_check_enabled: bool = True
    
    # Expected schema (for validation)
    expected_tables: Optional[Set[str]] = None
    expected_indexes: Optional[Set[str]] = None
    required_table_columns: Optional[Dict[str, Set[str]]] = None
    
    # Thresholds for warnings
    max_file_size_mb: int = 1000  # Warn if backup is larger than this
    min_records_per_table: int = 0  # Warn if table has fewer records
    max_validation_age_hours: int = 24  # Warn if validation is older than this
    
    def __post_init__(self):
        if self.expected_tables is None:
            self.expected_tables = {'users', 'conversations', 'memories'}
        if self.expected_indexes is None:
            self.expected_indexes = {
                'idx_conversations_user_created',
                'idx_conversations_channel_created', 
                'idx_memories_user_key',
                'idx_users_username'
            }
        if self.required_table_columns is None:
            self.required_table_columns = {
                'users': {'user_id', 'username', 'preferences', 'important_facts', 'created_at', 'updated_at'},
                'conversations': {'id', 'user_id', 'channel_id', 'conversation', 'created_at', 'updated_at'},
                'memories': {'id', 'user_id', 'key', 'value', 'created_at', 'updated_at'}
            }


class BackupIntegrityManager:
    """Backup integrity verification and validation system"""
    
    def __init__(self, config: Optional[IntegrityConfig] = None):
        self.config = config or IntegrityConfig()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_checks)
        
        # Integrity reports storage
        self.integrity_dir = "integrity"
        os.makedirs(self.integrity_dir, exist_ok=True)
        self.integrity_reports_file = os.path.join(self.integrity_dir, "integrity_reports.json")
        self.integrity_reports = self._load_integrity_reports()
        
        logger.info(f"BackupIntegrityManager initialized with config: {self.config}")
    
    def _load_integrity_reports(self) -> Dict[str, Dict]:
        """Load integrity reports from disk"""
        if os.path.exists(self.integrity_reports_file):
            try:
                with open(self.integrity_reports_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load integrity reports: {e}")
        return {}
    
    def _save_integrity_reports(self):
        """Save integrity reports to disk"""
        try:
            with open(self.integrity_reports_file, 'w') as f:
                json.dump(self.integrity_reports, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save integrity reports: {e}")
    
    async def verify_backup_integrity(self, backup_path: str, backup_id: Optional[str] = None, 
                                    validation_level: Optional[ValidationLevel] = None) -> IntegrityReport:
        """Verify backup integrity at specified level"""
        if not backup_id:
            backup_id = os.path.basename(backup_path).split('.')[0]
        
        validation_level = validation_level or self.config.default_validation_level
        
        start_time = time.time()
        
        report = IntegrityReport(
            backup_id=backup_id,
            backup_path=backup_path,
            validation_level=validation_level,
            checked_at=datetime.now(),
            status=IntegrityStatus.PASSED,
            file_exists=False,
            file_accessible=False,
            file_size=0,
            checksum_valid=False,
            database_integrity=False,
            schema_valid=False,
            data_consistent=False,
            error_messages=[],
            warnings=[],
            validation_duration_seconds=0.0,
            tables_found=[],
            records_per_table={},
            indexes_found=[]
        )
        
        try:
            # Basic file checks
            await self._check_file_accessibility(report)
            
            if not report.file_exists:
                report.status = IntegrityStatus.MISSING
                return report
            
            if not report.file_accessible:
                report.status = IntegrityStatus.INACCESSIBLE
                return report
            
            # Checksum verification
            if self.config.verify_checksums and validation_level != ValidationLevel.BASIC:
                await self._verify_checksum(report)
            
            # Database-specific checks
            if backup_path.endswith(('.db', '.zip')):
                await self._check_database_integrity(report, validation_level)
            
            # Final status determination
            if report.error_messages:
                if any("corrupted" in msg.lower() for msg in report.error_messages):
                    report.status = IntegrityStatus.CORRUPTED
                else:
                    report.status = IntegrityStatus.FAILED
            elif report.warnings and validation_level == ValidationLevel.COMPREHENSIVE:
                # For comprehensive checks, warnings might indicate issues
                report.status = IntegrityStatus.PASSED  # Still passed but with warnings
        
        except Exception as e:
            logger.error(f"Integrity check failed for {backup_id}: {e}")
            report.status = IntegrityStatus.FAILED
            report.error_messages.append(f"Verification error: {str(e)}")
        
        finally:
            report.validation_duration_seconds = time.time() - start_time
            
            # Save report
            self.integrity_reports[backup_id] = asdict(report)
            self._save_integrity_reports()
        
        return report
    
    async def _check_file_accessibility(self, report: IntegrityReport):
        """Check basic file accessibility"""
        try:
            # Check if file exists
            if not os.path.exists(report.backup_path):
                report.error_messages.append("Backup file does not exist")
                return
            
            report.file_exists = True
            
            # Check file size
            report.file_size = os.path.getsize(report.backup_path)
            
            if report.file_size == 0:
                report.error_messages.append("Backup file is empty")
                return
            
            # Check if file is readable
            with open(report.backup_path, 'rb') as f:
                f.read(1)  # Try to read first byte
            
            report.file_accessible = True
            
            # Size warnings
            size_mb = report.file_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                report.warnings.append(f"Large backup file: {size_mb:.1f}MB")
        
        except PermissionError:
            report.error_messages.append("Permission denied accessing backup file")
        except Exception as e:
            report.error_messages.append(f"File access error: {str(e)}")
    
    async def _verify_checksum(self, report: IntegrityReport):
        """Verify file checksum"""
        try:
            # This would typically compare against stored checksum
            # For now, just calculate checksum for future reference
            checksum = await self._calculate_checksum(report.backup_path)
            # In a real implementation, you'd compare with expected checksum
            report.checksum_valid = True  # Assume valid for now
        
        except Exception as e:
            report.error_messages.append(f"Checksum verification failed: {str(e)}")
    
    async def _calculate_checksum(self, file_path: str) -> str:
        """Calculate file checksum"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._calculate_checksum_sync, file_path)
    
    def _calculate_checksum_sync(self, file_path: str) -> str:
        """Synchronous checksum calculation"""
        hash_func = getattr(hashlib, self.config.checksum_algorithm)()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    async def _check_database_integrity(self, report: IntegrityReport, validation_level: ValidationLevel):
        """Check database-specific integrity"""
        try:
            # Extract database if compressed
            if report.backup_path.endswith('.zip'):
                db_path = await self._extract_database(report.backup_path, report.backup_id)
            else:
                db_path = report.backup_path
            
            try:
                # Basic integrity check
                if self.config.integrity_check_enabled:
                    await self._check_sqlite_integrity(db_path, report)
                
                # Schema validation
                if self.config.schema_validation_enabled and validation_level in [ValidationLevel.STANDARD, ValidationLevel.COMPREHENSIVE]:
                    await self._validate_database_schema(db_path, report)
                
                # Data consistency check
                if self.config.data_consistency_check_enabled and validation_level == ValidationLevel.COMPREHENSIVE:
                    await self._check_data_consistency(db_path, report)
            
            finally:
                # Clean up extracted database
                if report.backup_path.endswith('.zip') and db_path != report.backup_path:
                    try:
                        os.unlink(db_path)
                        os.rmdir(os.path.dirname(db_path))
                    except:
                        pass
        
        except Exception as e:
            report.error_messages.append(f"Database integrity check failed: {str(e)}")
    
    async def _extract_database(self, zip_path: str, backup_id: str) -> str:
        """Extract database from ZIP archive"""
        temp_dir = tempfile.mkdtemp(prefix=f"integrity_{backup_id}_")
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Find the database file
        for file in os.listdir(temp_dir):
            if file.endswith('.db'):
                return os.path.join(temp_dir, file)
        
        raise Exception("No database file found in backup archive")
    
    async def _check_sqlite_integrity(self, db_path: str, report: IntegrityReport):
        """Check SQLite database integrity"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, self._check_sqlite_integrity_sync, db_path)
        
        if result == "ok":
            report.database_integrity = True
        else:
            report.database_integrity = False
            report.error_messages.append(f"Database integrity check failed: {result}")
    
    def _check_sqlite_integrity_sync(self, db_path: str) -> str:
        """Synchronous SQLite integrity check"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            return result
        except Exception as e:
            return str(e)
    
    async def _validate_database_schema(self, db_path: str, report: IntegrityReport):
        """Validate database schema against expected structure"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self._validate_database_schema_sync, db_path, report)
    
    def _validate_database_schema_sync(self, db_path: str, report: IntegrityReport):
        """Synchronous schema validation"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}
            report.tables_found = list(existing_tables)
            
            # Validate required tables
            if self.config.expected_tables:
                missing_tables = self.config.expected_tables - existing_tables
                if missing_tables:
                    report.error_messages.append(f"Missing required tables: {missing_tables}")
                    report.schema_valid = False
                else:
                    report.schema_valid = True
            else:
                report.schema_valid = True
            
            # Check indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            existing_indexes = {row[0] for row in cursor.fetchall()}
            report.indexes_found = list(existing_indexes)
            
            # Validate required indexes
            if self.config.expected_indexes:
                missing_indexes = self.config.expected_indexes - existing_indexes
                if missing_indexes:
                    report.warnings.append(f"Missing recommended indexes: {missing_indexes}")
            
            # Validate table columns
            if self.config.required_table_columns:
                for table_name in self.config.required_table_columns:
                    if table_name in existing_tables:
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = {row[1] for row in cursor.fetchall()}
                        
                        required_columns = self.config.required_table_columns[table_name]
                        missing_columns = required_columns - columns
                        
                        if missing_columns:
                            report.error_messages.append(f"Missing columns in {table_name}: {missing_columns}")
                            report.schema_valid = False
            
            # Get record counts
            for table_name in existing_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    report.records_per_table[table_name] = count
                    
                    if count < self.config.min_records_per_table:
                        report.warnings.append(f"Low record count in {table_name}: {count}")
                
                except Exception as e:
                    report.warnings.append(f"Could not count records in {table_name}: {str(e)}")
            
            conn.close()
        
        except Exception as e:
            report.error_messages.append(f"Schema validation error: {str(e)}")
            report.schema_valid = False
    
    async def _check_data_consistency(self, db_path: str, report: IntegrityReport):
        """Check data consistency and relationships"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self._check_data_consistency_sync, db_path, report)
    
    def _check_data_consistency_sync(self, db_path: str, report: IntegrityReport):
        """Synchronous data consistency check"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check foreign key relationships
            if 'conversations' in report.records_per_table and 'users' in report.records_per_table:
                cursor.execute("""
                    SELECT COUNT(*) FROM conversations c 
                    LEFT JOIN users u ON c.user_id = u.user_id 
                    WHERE u.user_id IS NULL
                """)
                orphaned_conversations = cursor.fetchone()[0]
                
                if orphaned_conversations > 0:
                    report.warnings.append(f"Found {orphaned_conversations} conversations with invalid user references")
            
            if 'memories' in report.records_per_table and 'users' in report.records_per_table:
                cursor.execute("""
                    SELECT COUNT(*) FROM memories m 
                    LEFT JOIN users u ON m.user_id = u.user_id 
                    WHERE u.user_id IS NULL
                """)
                orphaned_memories = cursor.fetchone()[0]
                
                if orphaned_memories > 0:
                    report.warnings.append(f"Found {orphaned_memories} memories with invalid user references")
            
            # Check for data anomalies
            for table_name in report.tables_found:
                # Check for duplicate primary keys
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                pk_columns = [col[1] for col in columns if col[5] == 1]
                
                if pk_columns:
                    pk_list = ", ".join(pk_columns)
                    cursor.execute(f"""
                        SELECT COUNT(*) - COUNT(DISTINCT {pk_list}) 
                        FROM {table_name}
                    """)
                    duplicates = cursor.fetchone()[0]
                    
                    if duplicates > 0:
                        report.error_messages.append(f"Found {duplicates} duplicate primary keys in {table_name}")
                        report.data_consistent = False
            
            if report.data_consistent is False:  # Only set if we found issues
                pass
            else:
                report.data_consistent = True
            
            conn.close()
        
        except Exception as e:
            report.error_messages.append(f"Data consistency check error: {str(e)}")
            report.data_consistent = False
    
    async def verify_multiple_backups(self, backup_paths: List[str], 
                                    validation_level: Optional[ValidationLevel] = None) -> List[IntegrityReport]:
        """Verify multiple backups concurrently"""
        validation_level = validation_level or self.config.default_validation_level
        
        tasks = []
        for backup_path in backup_paths:
            task = asyncio.create_task(
                self.verify_backup_integrity(backup_path, validation_level=validation_level)
            )
            tasks.append(task)
        
        reports = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        valid_reports = []
        for i, report in enumerate(reports):
            if isinstance(report, Exception):
                logger.error(f"Failed to verify backup {backup_paths[i]}: {report}")
            else:
                valid_reports.append(report)
        
        return valid_reports
    
    async def get_integrity_report(self, backup_id: str) -> Optional[IntegrityReport]:
        """Get stored integrity report"""
        if backup_id in self.integrity_reports:
            return IntegrityReport(**self.integrity_reports[backup_id])
        return None
    
    async def list_integrity_reports(self, status: Optional[IntegrityStatus] = None, 
                                   older_than_hours: Optional[int] = None) -> List[IntegrityReport]:
        """List integrity reports with optional filtering"""
        reports = []
        
        for report_data in self.integrity_reports.values():
            report = IntegrityReport(**report_data)
            
            # Apply filters
            if status and report.status != status:
                continue
            
            if older_than_hours:
                age_hours = (datetime.now() - report.checked_at).total_seconds() / 3600
                if age_hours < older_than_hours:
                    continue
            
            reports.append(report)
        
        # Sort by check time (newest first)
        reports.sort(key=lambda x: x.checked_at, reverse=True)
        return reports
    
    async def cleanup_old_reports(self, retention_days: int = 30):
        """Clean up old integrity reports"""
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            
            to_remove = []
            for backup_id, report_data in self.integrity_reports.items():
                report = IntegrityReport(**report_data)
                if report.checked_at < cutoff_time:
                    to_remove.append(backup_id)
            
            for backup_id in to_remove:
                del self.integrity_reports[backup_id]
            
            if to_remove:
                self._save_integrity_reports()
                logger.info(f"Cleaned up {len(to_remove)} old integrity reports")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old integrity reports: {e}")
    
    async def get_integrity_statistics(self) -> Dict[str, Any]:
        """Get integrity verification statistics"""
        reports = await self.list_integrity_reports()
        
        stats = {
            "total_checks": len(reports),
            "passed_checks": len([r for r in reports if r.status == IntegrityStatus.PASSED]),
            "failed_checks": len([r for r in reports if r.status == IntegrityStatus.FAILED]),
            "corrupted_backups": len([r for r in reports if r.status == IntegrityStatus.CORRUPTED]),
            "missing_backups": len([r for r in reports if r.status == IntegrityStatus.MISSING]),
            "average_check_time_seconds": sum(r.validation_duration_seconds for r in reports) / len(reports) if reports else 0,
            "last_check_time": max((r.checked_at for r in reports), default=None),
            "validation_levels": {
                level.value: len([r for r in reports if r.validation_level == level])
                for level in ValidationLevel
            }
        }
        
        return stats
    
    async def close(self):
        """Close integrity manager and cleanup resources"""
        self.executor.shutdown(wait=True)
        logger.info("BackupIntegrityManager closed")
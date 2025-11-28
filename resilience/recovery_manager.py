import asyncio
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from enum import Enum

from config import DATABASE_PATH
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RecoveryType(Enum):
    """Recovery type enumeration"""
    FULL_RESTORE = "full_restore"
    POINT_IN_TIME = "point_in_time"
    TABLE_RESTORE = "table_restore"
    SELECTIVE_RESTORE = "selective_restore"


class RecoveryStatus(Enum):
    """Recovery status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"


@dataclass
class RecoveryMetadata:
    """Recovery operation metadata"""
    recovery_id: str
    recovery_type: RecoveryType
    backup_id: str
    target_timestamp: Optional[datetime]
    target_tables: List[str]
    created_at: datetime
    completed_at: Optional[datetime]
    status: RecoveryStatus
    original_db_path: str
    backup_db_path: str
    records_restored: int
    tables_restored: int
    validation_passed: bool
    error_message: Optional[str] = None
    rollback_available: bool = True


@dataclass
class RecoveryConfig:
    """Recovery configuration"""
    # Safety settings
    create_backup_before_restore: bool = True
    validate_after_restore: bool = True
    enable_rollback: bool = True
    
    # Performance settings
    max_concurrent_recoveries: int = 1
    recovery_timeout_seconds: int = 7200  # 2 hours
    batch_size: int = 1000
    
    # Validation settings
    integrity_check_enabled: bool = True
    record_count_validation: bool = True
    schema_validation: bool = True
    
    # Rollback settings
    rollback_retention_hours: int = 24
    max_rollback_files: int = 10


class RecoveryManager:
    """Database recovery operations manager"""
    
    def __init__(self, config: Optional[RecoveryConfig] = None, db_path: Optional[str] = None):
        self.config = config or RecoveryConfig()
        self.db_path = db_path or DATABASE_PATH
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_recoveries)
        
        # Recovery registry
        self.recovery_dir = "recovery"
        os.makedirs(self.recovery_dir, exist_ok=True)
        self.recovery_registry_file = os.path.join(self.recovery_dir, "recovery_registry.json")
        self.recovery_registry = self._load_recovery_registry()
        
        # Rollback directory
        self.rollback_dir = os.path.join(self.recovery_dir, "rollback")
        os.makedirs(self.rollback_dir, exist_ok=True)
        
        # Active recoveries tracking
        self.active_recoveries: Dict[str, asyncio.Task] = {}
        
        logger.info(f"RecoveryManager initialized with config: {self.config}")
    
    def _load_recovery_registry(self) -> Dict[str, Dict]:
        """Load recovery registry from disk"""
        if os.path.exists(self.recovery_registry_file):
            try:
                with open(self.recovery_registry_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load recovery registry: {e}")
        return {}
    
    def _save_recovery_registry(self):
        """Save recovery registry to disk"""
        try:
            with open(self.recovery_registry_file, 'w') as f:
                json.dump(self.recovery_registry, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save recovery registry: {e}")
    
    def _generate_recovery_id(self) -> str:
        """Generate unique recovery ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(f"{timestamp}{os.getpid()}".encode()).hexdigest()[:8]
        return f"recovery_{timestamp}_{random_suffix}"
    
    async def create_full_restore(self, backup_id: str) -> RecoveryMetadata:
        """Create a full database restore from backup"""
        recovery_id = self._generate_recovery_id()
        
        recovery_metadata = RecoveryMetadata(
            recovery_id=recovery_id,
            recovery_type=RecoveryType.FULL_RESTORE,
            backup_id=backup_id,
            target_timestamp=None,
            target_tables=[],
            created_at=datetime.now(),
            completed_at=None,
            status=RecoveryStatus.PENDING,
            original_db_path=self.db_path,
            backup_db_path="",
            records_restored=0,
            tables_restored=0,
            validation_passed=False
        )
        
        # Add to registry
        self.recovery_registry[recovery_id] = asdict(recovery_metadata)
        self._save_recovery_registry()
        
        # Start recovery task
        task = asyncio.create_task(self._perform_full_restore(recovery_id))
        self.active_recoveries[recovery_id] = task
        
        logger.info(f"Started full restore: {recovery_id} from backup: {backup_id}")
        return recovery_metadata
    
    async def _perform_full_restore(self, recovery_id: str):
        """Perform the actual full restore operation"""
        recovery_metadata = RecoveryMetadata(**self.recovery_registry[recovery_id])
        
        try:
            # Update status
            recovery_metadata.status = RecoveryStatus.IN_PROGRESS
            self.recovery_registry[recovery_id] = asdict(recovery_metadata)
            self._save_recovery_registry()
            
            # Find backup file
            backup_file = await self._find_backup_file(recovery_metadata.backup_id)
            if not backup_file:
                raise Exception(f"Backup file not found: {recovery_metadata.backup_id}")
            
            recovery_metadata.backup_db_path = backup_file
            
            # Create rollback backup if enabled
            if self.config.create_backup_before_restore:
                rollback_file = await self._create_rollback_backup(recovery_id)
                logger.info(f"Created rollback backup: {rollback_file}")
            
            # Extract backup if compressed
            if backup_file.endswith('.zip'):
                extracted_db = await self._extract_backup(backup_file, recovery_id)
            else:
                extracted_db = backup_file
            
            # Perform restore
            await self._restore_database(extracted_db, recovery_id)
            
            # Get restore statistics
            tables_restored, records_restored = await self._get_restore_statistics(extracted_db)
            recovery_metadata.tables_restored = tables_restored
            recovery_metadata.records_restored = records_restored
            
            # Validate restore if enabled
            if self.config.validate_after_restore:
                validation_passed = await self._validate_restore(recovery_id)
                recovery_metadata.validation_passed = validation_passed
                
                if not validation_passed:
                    recovery_metadata.status = RecoveryStatus.VALIDATION_FAILED
                    recovery_metadata.error_message = "Post-restore validation failed"
                    
                    # Attempt rollback if enabled
                    if self.config.enable_rollback:
                        logger.warning("Validation failed, attempting rollback")
                        await self._rollback_restore(recovery_id)
            else:
                recovery_metadata.validation_passed = True
            
            # Update status
            if recovery_metadata.status != RecoveryStatus.VALIDATION_FAILED:
                recovery_metadata.status = RecoveryStatus.COMPLETED
            
            recovery_metadata.completed_at = datetime.now()
            self.recovery_registry[recovery_id] = asdict(recovery_metadata)
            self._save_recovery_registry()
            
            logger.info(f"Full restore completed: {recovery_id}")
            
        except Exception as e:
            logger.error(f"Full restore failed {recovery_id}: {e}")
            recovery_metadata.status = RecoveryStatus.FAILED
            recovery_metadata.error_message = str(e)
            recovery_metadata.completed_at = datetime.now()
            self.recovery_registry[recovery_id] = asdict(recovery_metadata)
            self._save_recovery_registry()
            
            # Attempt rollback if enabled
            if self.config.enable_rollback:
                logger.warning("Restore failed, attempting rollback")
                await self._rollback_restore(recovery_id)
        
        finally:
            # Clean up active recovery
            if recovery_id in self.active_recoveries:
                del self.active_recoveries[recovery_id]
            
            # Clean up temporary files
            await self._cleanup_temp_files(recovery_id)
    
    async def _find_backup_file(self, backup_id: str) -> Optional[str]:
        """Find backup file by ID"""
        # This would integrate with the backup manager
        # For now, search common backup locations
        backup_locations = ["backups", "backups/full"]
        
        for location in backup_locations:
            if os.path.exists(location):
                for file in os.listdir(location):
                    if backup_id in file:
                        return os.path.join(location, file)
        
        return None
    
    async def _create_rollback_backup(self, recovery_id: str) -> str:
        """Create rollback backup before restore"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rollback_filename = f"rollback_{recovery_id}_{timestamp}.db"
        rollback_path = os.path.join(self.rollback_dir, rollback_filename)
        
        # Copy current database
        shutil.copy2(self.db_path, rollback_path)
        
        # Clean up old rollback files
        await self._cleanup_old_rollback_files()
        
        return rollback_path
    
    async def _cleanup_old_rollback_files(self):
        """Clean up old rollback files based on retention policy"""
        try:
            rollback_files = []
            for file in os.listdir(self.rollback_dir):
                if file.startswith("rollback_") and file.endswith(".db"):
                    file_path = os.path.join(self.rollback_dir, file)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    rollback_files.append((file_path, file_time))
            
            # Sort by creation time (oldest first)
            rollback_files.sort(key=lambda x: x[1])
            
            # Remove files older than retention period
            cutoff_time = datetime.now() - timedelta(hours=self.config.rollback_retention_hours)
            for file_path, file_time in rollback_files:
                if file_time < cutoff_time:
                    os.unlink(file_path)
                    logger.info(f"Removed old rollback file: {file_path}")
            
            # If still too many files, remove oldest
            current_files = [f for f in os.listdir(self.rollback_dir) if f.startswith("rollback_")]
            if len(current_files) > self.config.max_rollback_files:
                rollback_files = [(os.path.join(self.rollback_dir, f), 
                                 datetime.fromtimestamp(os.path.getctime(os.path.join(self.rollback_dir, f)))) 
                                for f in current_files]
                rollback_files.sort(key=lambda x: x[1])
                
                while len(current_files) > self.config.max_rollback_files:
                    oldest_file = rollback_files.pop(0)[0]
                    os.unlink(oldest_file)
                    current_files.remove(os.path.basename(oldest_file))
                    logger.info(f"Removed excess rollback file: {oldest_file}")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old rollback files: {e}")
    
    async def _extract_backup(self, backup_path: str, recovery_id: str) -> str:
        """Extract compressed backup"""
        temp_dir = tempfile.mkdtemp(prefix=f"recovery_{recovery_id}_")
        
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Find the database file
        for file in os.listdir(temp_dir):
            if file.endswith('.db'):
                return os.path.join(temp_dir, file)
        
        raise Exception("No database file found in backup archive")
    
    async def _restore_database(self, backup_db_path: str, recovery_id: str):
        """Restore database from backup"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self._restore_database_sync, backup_db_path)
    
    def _restore_database_sync(self, backup_db_path: str):
        """Synchronous database restore"""
        # Close any existing connections
        # (This would need to be coordinated with the application)
        
        # Replace current database with backup
        shutil.copy2(backup_db_path, self.db_path)
        
        # Set appropriate permissions
        os.chmod(self.db_path, 0o644)
    
    async def _get_restore_statistics(self, backup_db_path: str) -> Tuple[int, int]:
        """Get statistics about the restore"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._get_restore_statistics_sync, backup_db_path)
    
    def _get_restore_statistics_sync(self, backup_db_path: str) -> Tuple[int, int]:
        """Synchronous statistics gathering"""
        try:
            conn = sqlite3.connect(backup_db_path)
            cursor = conn.cursor()
            
            # Get table count
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            tables_restored = cursor.fetchone()[0]
            
            # Get total record count
            records_restored = 0
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                records_restored += cursor.fetchone()[0]
            
            conn.close()
            return tables_restored, records_restored
        
        except Exception as e:
            logger.error(f"Failed to get restore statistics: {e}")
            return 0, 0
    
    async def _validate_restore(self, recovery_id: str) -> bool:
        """Validate the restored database"""
        try:
            # Integrity check
            if self.config.integrity_check_enabled:
                if not await self._check_database_integrity():
                    logger.error("Database integrity check failed")
                    return False
            
            # Schema validation
            if self.config.schema_validation:
                if not await self._validate_database_schema():
                    logger.error("Database schema validation failed")
                    return False
            
            # Record count validation (if we have expected counts)
            if self.config.record_count_validation:
                # This would compare against expected counts from backup metadata
                pass
            
            return True
        
        except Exception as e:
            logger.error(f"Restore validation failed: {e}")
            return False
    
    async def _check_database_integrity(self) -> bool:
        """Check database integrity"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._check_database_integrity_sync)
    
    def _check_database_integrity_sync(self) -> bool:
        """Synchronous integrity check"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            return result[0] == "ok"
        except Exception:
            return False
    
    async def _validate_database_schema(self) -> bool:
        """Validate database schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for required tables
            required_tables = ['users', 'conversations', 'memories']
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = set(required_tables) - set(existing_tables)
            if missing_tables:
                logger.error(f"Missing required tables: {missing_tables}")
                conn.close()
                return False
            
            # Check for required indexes
            required_indexes = [
                'idx_conversations_user_created',
                'idx_conversations_channel_created',
                'idx_memories_user_key',
                'idx_users_username'
            ]
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            existing_indexes = [row[0] for row in cursor.fetchall()]
            
            missing_indexes = set(required_indexes) - set(existing_indexes)
            if missing_indexes:
                logger.warning(f"Missing recommended indexes: {missing_indexes}")
            
            conn.close()
            return True
        
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False
    
    async def _rollback_restore(self, recovery_id: str):
        """Rollback a failed restore"""
        try:
            # Find rollback file for this recovery
            rollback_files = []
            for file in os.listdir(self.rollback_dir):
                if recovery_id in file and file.startswith("rollback_"):
                    rollback_files.append(os.path.join(self.rollback_dir, file))
            
            if not rollback_files:
                logger.error(f"No rollback file found for recovery: {recovery_id}")
                return False
            
            # Use the most recent rollback file
            rollback_file = max(rollback_files, key=os.path.getctime)
            
            # Restore from rollback
            shutil.copy2(rollback_file, self.db_path)
            
            logger.info(f"Successfully rolled back restore: {recovery_id}")
            return True
        
        except Exception as e:
            logger.error(f"Rollback failed for recovery {recovery_id}: {e}")
            return False
    
    async def _cleanup_temp_files(self, recovery_id: str):
        """Clean up temporary files from recovery"""
        try:
            # Clean up temp directories
            import tempfile
            temp_dir = tempfile.gettempdir()
            
            for item in os.listdir(temp_dir):
                if f"recovery_{recovery_id}_" in item:
                    item_path = os.path.join(temp_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.unlink(item_path)
        
        except Exception as e:
            logger.error(f"Failed to cleanup temp files for recovery {recovery_id}: {e}")
    
    async def get_recovery_status(self, recovery_id: str) -> Optional[RecoveryMetadata]:
        """Get recovery status"""
        if recovery_id in self.recovery_registry:
            return RecoveryMetadata(**self.recovery_registry[recovery_id])
        return None
    
    async def list_recoveries(self, status: Optional[RecoveryStatus] = None) -> List[RecoveryMetadata]:
        """List recoveries with optional filtering"""
        recoveries = []
        
        for recovery_data in self.recovery_registry.values():
            recovery = RecoveryMetadata(**recovery_data)
            
            # Apply filter
            if status and recovery.status != status:
                continue
            
            recoveries.append(recovery)
        
        # Sort by creation time (newest first)
        recoveries.sort(key=lambda x: x.created_at, reverse=True)
        return recoveries
    
    async def cancel_recovery(self, recovery_id: str) -> bool:
        """Cancel an active recovery"""
        if recovery_id in self.active_recoveries:
            task = self.active_recoveries[recovery_id]
            if not task.done():
                task.cancel()
                
                # Update status
                if recovery_id in self.recovery_registry:
                    recovery = RecoveryMetadata(**self.recovery_registry[recovery_id])
                    recovery.status = RecoveryStatus.FAILED
                    recovery.error_message = "Recovery cancelled"
                    recovery.completed_at = datetime.now()
                    self.recovery_registry[recovery_id] = asdict(recovery)
                    self._save_recovery_registry()
                
                logger.info(f"Cancelled recovery: {recovery_id}")
                return True
        
        return False
    
    async def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get recovery system statistics"""
        recoveries = await self.list_recoveries()
        
        stats = {
            "total_recoveries": len(recoveries),
            "completed_recoveries": len([r for r in recoveries if r.status == RecoveryStatus.COMPLETED]),
            "failed_recoveries": len([r for r in recoveries if r.status == RecoveryStatus.FAILED]),
            "validation_failed": len([r for r in recoveries if r.status == RecoveryStatus.VALIDATION_FAILED]),
            "total_records_restored": sum(r.records_restored for r in recoveries if r.status == RecoveryStatus.COMPLETED),
            "total_tables_restored": sum(r.tables_restored for r in recoveries if r.status == RecoveryStatus.COMPLETED),
            "oldest_recovery": min((r.created_at for r in recoveries), default=None),
            "newest_recovery": max((r.created_at for r in recoveries), default=None),
            "rollback_files_available": len([f for f in os.listdir(self.rollback_dir) if f.startswith("rollback_")])
        }
        
        return stats
    
    async def close(self):
        """Close recovery manager and cleanup resources"""
        # Cancel active recoveries
        for recovery_id, task in self.active_recoveries.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled recovery task: {recovery_id}")
        
        # Wait for tasks to complete
        if self.active_recoveries:
            await asyncio.gather(*self.active_recoveries.values(), return_exceptions=True)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        logger.info("RecoveryManager closed")
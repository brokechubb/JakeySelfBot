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


class BackupType(Enum):
    """Backup type enumeration"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(Enum):
    """Backup status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPTED = "corrupted"


@dataclass
class BackupMetadata:
    """Backup metadata structure"""
    backup_id: str
    backup_type: BackupType
    created_at: datetime
    file_path: str
    file_size: int
    checksum: str
    compressed: bool
    base_backup_id: Optional[str] = None  # For incremental/differential
    table_count: int = 0
    record_count: int = 0
    status: BackupStatus = BackupStatus.PENDING
    error_message: Optional[str] = None
    retention_days: int = 30
    storage_locations: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.storage_locations is None:
            self.storage_locations = []


@dataclass
class BackupConfig:
    """Backup configuration"""
    # Backup paths
    primary_backup_dir: str = "backups"
    secondary_backup_dir: Optional[str] = None
    tertiary_backup_dir: Optional[str] = None
    
    # Retention policies
    daily_retention_days: int = 7
    weekly_retention_weeks: int = 4
    monthly_retention_months: int = 12
    yearly_retention_years: int = 5
    
    # Backup settings
    compression_enabled: bool = True
    compression_level: int = 6
    checksum_enabled: bool = True
    verify_after_backup: bool = True
    
    # Scheduling
    auto_backup_enabled: bool = True
    backup_interval_hours: int = 6
    incremental_backup_interval_hours: int = 2
    
    # Performance
    max_concurrent_backups: int = 2
    backup_timeout_seconds: int = 3600
    
    # Database settings
    vacuum_before_backup: bool = True
    analyze_after_backup: bool = True


class BackupManager:
    """Main backup orchestration system"""
    
    def __init__(self, config: Optional[BackupConfig] = None, db_path: Optional[str] = None):
        self.config = config or BackupConfig()
        self.db_path = db_path or DATABASE_PATH
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_backups)
        
        # Ensure backup directories exist
        self._ensure_backup_directories()
        
        # Backup registry
        self.backup_registry_file = os.path.join(self.config.primary_backup_dir, "backup_registry.json")
        self.backup_registry = self._load_backup_registry()
        
        # Active backups tracking
        self.active_backups: Dict[str, asyncio.Task] = {}
        
        logger.info(f"BackupManager initialized with config: {self.config}")
    
    def _ensure_backup_directories(self):
        """Create backup directories if they don't exist"""
        directories = [self.config.primary_backup_dir]
        if self.config.secondary_backup_dir:
            directories.append(self.config.secondary_backup_dir)
        if self.config.tertiary_backup_dir:
            directories.append(self.config.tertiary_backup_dir)
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            # Create subdirectories
            os.makedirs(os.path.join(directory, "full"), exist_ok=True)
            os.makedirs(os.path.join(directory, "incremental"), exist_ok=True)
            os.makedirs(os.path.join(directory, "differential"), exist_ok=True)
    
    def _load_backup_registry(self) -> Dict[str, Dict]:
        """Load backup registry from disk"""
        if os.path.exists(self.backup_registry_file):
            try:
                with open(self.backup_registry_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load backup registry: {e}")
        return {}
    
    def _save_backup_registry(self):
        """Save backup registry to disk"""
        try:
            with open(self.backup_registry_file, 'w') as f:
                json.dump(self.backup_registry, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save backup registry: {e}")
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(f"{timestamp}{os.getpid()}".encode()).hexdigest()[:8]
        return f"backup_{timestamp}_{random_suffix}"
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _get_database_info(self) -> Tuple[int, int]:
        """Get database table and record count"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get table count
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # Get total record count
            record_count = 0
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                record_count += cursor.fetchone()[0]
            
            conn.close()
            return table_count, record_count
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return 0, 0
    
    async def create_full_backup(self, description: Optional[str] = None) -> BackupMetadata:
        """Create a full database backup"""
        backup_id = self._generate_backup_id()
        backup_metadata = BackupMetadata(
            backup_id=backup_id,
            backup_type=BackupType.FULL,
            created_at=datetime.now(),
            file_path="",
            file_size=0,
            checksum="",
            compressed=self.config.compression_enabled
        )
        
        # Get database info
        table_count, record_count = self._get_database_info()
        backup_metadata.table_count = table_count
        backup_metadata.record_count = record_count
        
        # Add to registry
        self.backup_registry[backup_id] = asdict(backup_metadata)
        self._save_backup_registry()
        
        # Start backup task
        task = asyncio.create_task(self._perform_full_backup(backup_id))
        self.active_backups[backup_id] = task
        
        logger.info(f"Started full backup: {backup_id}")
        return backup_metadata
    
    async def _perform_full_backup(self, backup_id: str):
        """Perform the actual full backup operation"""
        backup_metadata = None
        try:
            backup_metadata = BackupMetadata(**self.backup_registry[backup_id])
            backup_metadata.status = BackupStatus.IN_PROGRESS
            self.backup_registry[backup_id] = asdict(backup_metadata)
            self._save_backup_registry()
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Perform backup
            await self._backup_database(temp_path, backup_id)
            
            # Compress if enabled
            final_path = temp_path
            if self.config.compression_enabled:
                final_path = await self._compress_backup(temp_path, backup_id)
                os.unlink(temp_path)
            
            # Calculate checksum
            checksum = self._calculate_checksum(final_path) if self.config.checksum_enabled else ""
            
            # Move to primary backup location
            backup_filename = f"{backup_id}.{'zip' if self.config.compression_enabled else 'db'}"
            primary_path = os.path.join(self.config.primary_backup_dir, "full", backup_filename)
            shutil.move(final_path, primary_path)
            
            # Update metadata
            backup_metadata.file_path = primary_path
            backup_metadata.file_size = os.path.getsize(primary_path)
            backup_metadata.checksum = checksum
            backup_metadata.status = BackupStatus.COMPLETED
            backup_metadata.storage_locations = [primary_path]
            
            # Copy to secondary/tertiary locations
            await self._replicate_backup(primary_path, backup_metadata)
            
            # Verify backup if enabled
            if self.config.verify_after_backup:
                if not await self._verify_backup(primary_path, backup_metadata):
                    backup_metadata.status = BackupStatus.CORRUPTED
                    backup_metadata.error_message = "Backup verification failed"
            
            # Update registry
            self.backup_registry[backup_id] = asdict(backup_metadata)
            self._save_backup_registry()
            
            logger.info(f"Full backup completed: {backup_id}")
            
        except Exception as e:
            logger.error(f"Full backup failed {backup_id}: {e}")
            if backup_metadata is not None:
                backup_metadata.status = BackupStatus.FAILED
                backup_metadata.error_message = str(e)
                self.backup_registry[backup_id] = asdict(backup_metadata)
                self._save_backup_registry()
        
        finally:
            # Clean up active backup
            if backup_id in self.active_backups:
                del self.active_backups[backup_id]
    
    async def _backup_database(self, backup_path: str, backup_id: str):
        """Backup the database using SQLite backup API"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self._backup_database_sync, backup_path)
    
    def _backup_database_sync(self, backup_path: str):
        """Synchronous database backup"""
        source = sqlite3.connect(self.db_path)
        backup = sqlite3.connect(backup_path)
        
        try:
            # Vacuum before backup if enabled
            if self.config.vacuum_before_backup:
                source.execute("VACUUM")
            
            # Perform backup
            source.backup(backup)
            
            # Analyze after backup if enabled
            if self.config.analyze_after_backup:
                backup.execute("ANALYZE")
            
            backup.commit()
        finally:
            source.close()
            backup.close()
    
    async def _compress_backup(self, file_path: str, backup_id: str) -> str:
        """Compress backup file using ZIP"""
        compressed_path = file_path.replace('.db', '.zip')
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor, 
            self._compress_backup_sync, 
            file_path, 
            compressed_path
        )
        
        return compressed_path
    
    def _compress_backup_sync(self, source_path: str, target_path: str):
        """Synchronous backup compression"""
        with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=self.config.compression_level) as zipf:
            zipf.write(source_path, os.path.basename(source_path))
    
    async def _replicate_backup(self, primary_path: str, backup_metadata: BackupMetadata):
        """Replicate backup to secondary and tertiary locations"""
        backup_filename = os.path.basename(primary_path)
        
        # Secondary location
        if self.config.secondary_backup_dir:
            secondary_path = os.path.join(self.config.secondary_backup_dir, "full", backup_filename)
            try:
                shutil.copy2(primary_path, secondary_path)
                if backup_metadata.storage_locations:
                    backup_metadata.storage_locations.append(secondary_path)
            except Exception as e:
                logger.error(f"Failed to replicate to secondary location: {e}")
        
        # Tertiary location
        if self.config.tertiary_backup_dir:
            tertiary_path = os.path.join(self.config.tertiary_backup_dir, "full", backup_filename)
            try:
                shutil.copy2(primary_path, tertiary_path)
                if backup_metadata.storage_locations:
                    backup_metadata.storage_locations.append(tertiary_path)
            except Exception as e:
                logger.error(f"Failed to replicate to tertiary location: {e}")
    
    async def _verify_backup(self, backup_path: str, backup_metadata: BackupMetadata) -> bool:
        """Verify backup integrity"""
        try:
            # Verify checksum
            if self.config.checksum_enabled and backup_metadata.checksum:
                calculated_checksum = self._calculate_checksum(backup_path)
                if calculated_checksum != backup_metadata.checksum:
                    logger.error(f"Checksum mismatch for backup {backup_metadata.backup_id}")
                    return False
            
            # Verify database integrity
            if backup_path.endswith('.zip'):
                # Extract and verify
                with tempfile.TemporaryDirectory() as temp_dir:
                    with zipfile.ZipFile(backup_path, 'r') as zipf:
                        zipf.extractall(temp_dir)
                    
                    db_file = os.path.join(temp_dir, os.path.basename(backup_path).replace('.zip', '.db'))
                    if os.path.exists(db_file):
                        return await self._verify_database_integrity(db_file)
            else:
                return await self._verify_database_integrity(backup_path)
            
            return True
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False
    
    async def _verify_database_integrity(self, db_path: str) -> bool:
        """Verify database integrity using PRAGMA integrity_check"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._verify_database_integrity_sync, db_path)
    
    def _verify_database_integrity_sync(self, db_path: str) -> bool:
        """Synchronous database integrity verification"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            return result[0] == "ok"
        except Exception:
            return False
    
    async def get_backup_status(self, backup_id: str) -> Optional[BackupMetadata]:
        """Get backup status"""
        if backup_id in self.backup_registry:
            return BackupMetadata(**self.backup_registry[backup_id])
        return None
    
    async def list_backups(self, backup_type: Optional[BackupType] = None, status: Optional[BackupStatus] = None) -> List[BackupMetadata]:
        """List backups with optional filtering"""
        backups = []
        
        for backup_data in self.backup_registry.values():
            backup = BackupMetadata(**backup_data)
            
            # Apply filters
            if backup_type and backup.backup_type != backup_type:
                continue
            if status and backup.status != status:
                continue
            
            backups.append(backup)
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup and all its copies"""
        if backup_id not in self.backup_registry:
            return False
        
        backup_metadata = BackupMetadata(**self.backup_registry[backup_id])
        
        # Delete all copies
        for location in backup_metadata.storage_locations or []:
            try:
                if os.path.exists(location):
                    os.unlink(location)
            except Exception as e:
                logger.error(f"Failed to delete backup copy at {location}: {e}")
        
        # Remove from registry
        del self.backup_registry[backup_id]
        self._save_backup_registry()
        
        logger.info(f"Deleted backup: {backup_id}")
        return True
    
    async def cleanup_old_backups(self):
        """Clean up backups based on retention policies"""
        try:
            backups = await self.list_backups()
            now = datetime.now()
            
            for backup in backups:
                age_days = (now - backup.created_at).days
                
                # Check retention policies
                should_delete = False
                
                if age_days > backup.retention_days:
                    should_delete = True
                elif age_days > 365 * self.config.yearly_retention_years:
                    should_delete = True
                elif age_days > 30 * self.config.monthly_retention_months:
                    should_delete = True
                elif age_days > 7 * self.config.weekly_retention_weeks:
                    should_delete = True
                elif age_days > self.config.daily_retention_days:
                    should_delete = True
                
                if should_delete:
                    await self.delete_backup(backup.backup_id)
                    logger.info(f"Cleaned up old backup: {backup.backup_id}")
        
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
    
    async def get_backup_statistics(self) -> Dict[str, Any]:
        """Get backup system statistics"""
        backups = await self.list_backups()
        
        stats = {
            "total_backups": len(backups),
            "completed_backups": len([b for b in backups if b.status == BackupStatus.COMPLETED]),
            "failed_backups": len([b for b in backups if b.status == BackupStatus.FAILED]),
            "total_size_gb": sum(b.file_size for b in backups if b.status == BackupStatus.COMPLETED) / (1024**3),
            "oldest_backup": min((b.created_at for b in backups), default=None),
            "newest_backup": max((b.created_at for b in backups), default=None),
            "backup_types": {
                "full": len([b for b in backups if b.backup_type == BackupType.FULL]),
                "incremental": len([b for b in backups if b.backup_type == BackupType.INCREMENTAL]),
                "differential": len([b for b in backups if b.backup_type == BackupType.DIFFERENTIAL])
            }
        }
        
        return stats
    
    async def close(self):
        """Close backup manager and cleanup resources"""
        # Cancel active backups
        for backup_id, task in self.active_backups.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled backup task: {backup_id}")
        
        # Wait for tasks to complete
        if self.active_backups:
            await asyncio.gather(*self.active_backups.values(), return_exceptions=True)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        logger.info("BackupManager closed")
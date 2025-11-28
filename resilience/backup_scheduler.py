import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum

from utils.logging_config import get_logger

logger = get_logger(__name__)


class ScheduleType(Enum):
    """Schedule type enumeration"""
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ScheduleStatus(Enum):
    """Schedule status enumeration"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass
class BackupSchedule:
    """Backup schedule configuration"""
    schedule_id: str
    name: str
    schedule_type: ScheduleType
    backup_type: str
    enabled: bool
    
    # Timing configuration
    interval_hours: Optional[int] = None
    daily_time: Optional[str] = None
    weekly_day: Optional[int] = None
    weekly_time: Optional[str] = None
    monthly_day: Optional[int] = None
    monthly_time: Optional[str] = None
    
    # Schedule metadata
    created_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    
    # Configuration
    retention_days: int = 30
    validation_level: str = "standard"
    auto_cleanup: bool = True
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class SchedulerConfig:
    """Backup scheduler configuration"""
    enabled: bool = True
    max_concurrent_schedules: int = 5
    schedule_check_interval_seconds: int = 60
    default_retention_days: int = 30
    default_validation_level: str = "standard"
    auto_cleanup_enabled: bool = True
    max_retry_attempts: int = 3
    retry_delay_minutes: int = 5
    success_notifications: bool = False
    failure_notifications: bool = True
    backup_timeout_minutes: int = 60


class BackupScheduler:
    """Automated backup scheduling system"""
    
    def __init__(self, backup_manager: Any = None, integrity_manager: Any = None,
                 config: Optional[SchedulerConfig] = None):
        self.backup_manager = backup_manager
        self.integrity_manager = integrity_manager
        self.config = config or SchedulerConfig()
        
        # Scheduler storage
        self.scheduler_dir = "scheduler"
        os.makedirs(self.scheduler_dir, exist_ok=True)
        self.schedules_file = os.path.join(self.scheduler_dir, "schedules.json")
        self.schedules = self._load_schedules()
        
        # Active tasks
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # Event callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            'backup_started': [],
            'backup_completed': [],
            'backup_failed': [],
            'schedule_missed': []
        }
        
        logger.info(f"BackupScheduler initialized with {len(self.schedules)} schedules")
    
    def _load_schedules(self) -> Dict[str, Dict]:
        """Load schedules from disk"""
        if os.path.exists(self.schedules_file):
            try:
                with open(self.schedules_file, 'r') as f:
                    data = json.load(f)
                    # Convert string enums back to enum objects
                    for schedule_data in data.values():
                        schedule_data['schedule_type'] = ScheduleType(schedule_data['schedule_type'])
                    return data
            except Exception as e:
                logger.error(f"Failed to load schedules: {e}")
        return {}
    
    def _save_schedules(self):
        """Save schedules to disk"""
        try:
            with open(self.schedules_file, 'w') as f:
                json.dump(self.schedules, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")
    
    def _generate_schedule_id(self) -> str:
        """Generate unique schedule ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"schedule_{timestamp}"
    
    def add_callback(self, event: str, callback: Callable):
        """Add event callback"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def _trigger_callbacks(self, event: str, data: Any):
        """Trigger event callbacks"""
        for callback in self.callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(data))
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")
    
    def create_schedule(self, name: str, schedule_type: ScheduleType, backup_type: str,
                       interval_hours: Optional[int] = None, daily_time: Optional[str] = None,
                       weekly_day: Optional[int] = None, weekly_time: Optional[str] = None,
                       monthly_day: Optional[int] = None, monthly_time: Optional[str] = None,
                       retention_days: Optional[int] = None, validation_level: Optional[str] = None) -> BackupSchedule:
        """Create a new backup schedule"""
        
        schedule_id = self._generate_schedule_id()
        
        schedule = BackupSchedule(
            schedule_id=schedule_id,
            name=name,
            schedule_type=schedule_type,
            backup_type=backup_type,
            enabled=True,
            interval_hours=interval_hours,
            daily_time=daily_time,
            weekly_day=weekly_day,
            weekly_time=weekly_time,
            monthly_day=monthly_day,
            monthly_time=monthly_time,
            retention_days=retention_days or self.config.default_retention_days,
            validation_level=validation_level or self.config.default_validation_level,
            auto_cleanup=self.config.auto_cleanup_enabled
        )
        
        # Calculate next run time
        schedule.next_run = self._calculate_next_run(schedule)
        
        # Save schedule
        self.schedules[schedule_id] = asdict(schedule)
        self._save_schedules()
        
        logger.info(f"Created backup schedule: {name} ({schedule_id})")
        return schedule
    
    def _calculate_next_run(self, schedule: BackupSchedule) -> datetime:
        """Calculate next run time for a schedule"""
        now = datetime.now()
        
        if schedule.schedule_type == ScheduleType.INTERVAL:
            if schedule.last_run and schedule.interval_hours:
                return schedule.last_run + timedelta(hours=schedule.interval_hours)
            else:
                return now + timedelta(hours=schedule.interval_hours or 1)
        
        elif schedule.schedule_type == ScheduleType.DAILY:
            if schedule.daily_time:
                try:
                    hour, minute = map(int, schedule.daily_time.split(':'))
                    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if next_run <= now:
                        next_run += timedelta(days=1)
                    return next_run
                except ValueError:
                    logger.warning(f"Invalid daily time format: {schedule.daily_time}")
            
            return now + timedelta(days=1)
        
        elif schedule.schedule_type == ScheduleType.WEEKLY:
            if schedule.weekly_day is not None and schedule.weekly_time:
                try:
                    hour, minute = map(int, schedule.weekly_time.split(':'))
                    days_ahead = schedule.weekly_day - now.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    
                    next_run = now + timedelta(days=days_ahead)
                    next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    return next_run
                except ValueError:
                    logger.warning(f"Invalid weekly time format: {schedule.weekly_time}")
            
            return now + timedelta(weeks=1)
        
        elif schedule.schedule_type == ScheduleType.MONTHLY:
            if schedule.monthly_day is not None:
                hour, minute = 0, 0
                if schedule.monthly_time:
                    try:
                        hour, minute = map(int, schedule.monthly_time.split(':'))
                    except ValueError:
                        logger.warning(f"Invalid monthly time format: {schedule.monthly_time}")
                
                # Find next occurrence of the specified day
                if now.day <= schedule.monthly_day:
                    next_run = now.replace(day=schedule.monthly_day, hour=hour, minute=minute, 
                                         second=0, microsecond=0)
                else:
                    # Next month
                    if now.month == 12:
                        next_run = now.replace(year=now.year+1, month=1, day=schedule.monthly_day,
                                             hour=hour, minute=minute, second=0, microsecond=0)
                    else:
                        next_run = now.replace(month=now.month+1, day=schedule.monthly_day,
                                             hour=hour, minute=minute, second=0, microsecond=0)
                return next_run
            
            return now + timedelta(days=30)
        
        return now + timedelta(hours=1)  # Default fallback
    
    async def start(self):
        """Start the backup scheduler"""
        if not self.config.enabled:
            logger.info("Backup scheduler is disabled")
            return
        
        if self.scheduler_task and not self.scheduler_task.done():
            logger.warning("Backup scheduler is already running")
            return
        
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Backup scheduler started")
    
    async def stop(self):
        """Stop the backup scheduler"""
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
            logger.info("Backup scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("Backup scheduler loop started")
        
        while True:
            try:
                await self._check_and_run_schedules()
                await asyncio.sleep(self.config.schedule_check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(self.config.schedule_check_interval_seconds)
    
    async def _check_and_run_schedules(self):
        """Check schedules and run any that are due"""
        now = datetime.now()
        
        for schedule_id, schedule_data in self.schedules.items():
            try:
                schedule = BackupSchedule(**schedule_data)
                
                # Skip disabled schedules
                if not schedule.enabled:
                    continue
                
                # Skip if already running
                if schedule_id in self.active_tasks:
                    continue
                
                # Check if schedule is due
                if schedule.next_run and now >= schedule.next_run:
                    await self._run_scheduled_backup(schedule)
            
            except Exception as e:
                logger.error(f"Error checking schedule {schedule_id}: {e}")
    
    async def _run_scheduled_backup(self, schedule: BackupSchedule):
        """Run a scheduled backup"""
        logger.info(f"Running scheduled backup: {schedule.name}")
        
        # Update schedule
        schedule.last_run = datetime.now()
        schedule.run_count += 1
        schedule.next_run = self._calculate_next_run(schedule)
        
        try:
            # Trigger backup started callback
            self._trigger_callbacks('backup_started', schedule)
            
            # Create backup (placeholder - would integrate with backup manager)
            if self.backup_manager:
                try:
                    backup_metadata = await self.backup_manager.create_full_backup()
                    schedule.success_count += 1
                    
                    # Trigger backup completed callback
                    self._trigger_callbacks('backup_completed', {'schedule': schedule, 'backup': backup_metadata})
                    
                    if self.config.success_notifications:
                        logger.info(f"Scheduled backup completed successfully: {schedule.name}")
                
                except Exception as e:
                    schedule.failure_count += 1
                    logger.error(f"Scheduled backup failed: {schedule.name} - {str(e)}")
                    
                    # Trigger backup failed callback
                    self._trigger_callbacks('backup_failed', {'schedule': schedule, 'error': str(e)})
            else:
                logger.warning("No backup manager available, simulating backup completion")
                schedule.success_count += 1
        
        except Exception as e:
            schedule.failure_count += 1
            logger.error(f"Scheduled backup error: {schedule.name} - {str(e)}")
            
            # Trigger backup failed callback
            self._trigger_callbacks('backup_failed', {'schedule': schedule, 'error': str(e)})
        
        finally:
            # Save updated schedule
            self.schedules[schedule.schedule_id] = asdict(schedule)
            self._save_schedules()
    
    def get_schedule(self, schedule_id: str) -> Optional[BackupSchedule]:
        """Get schedule by ID"""
        if schedule_id in self.schedules:
            return BackupSchedule(**self.schedules[schedule_id])
        return None
    
    def list_schedules(self, enabled_only: bool = False) -> List[BackupSchedule]:
        """List all schedules"""
        schedules = []
        
        for schedule_data in self.schedules.values():
            schedule = BackupSchedule(**schedule_data)
            
            if enabled_only and not schedule.enabled:
                continue
            
            schedules.append(schedule)
        
        # Sort by next run time
        schedules.sort(key=lambda x: x.next_run or datetime.max)
        return schedules
    
    def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a schedule"""
        if schedule_id in self.schedules:
            schedule = BackupSchedule(**self.schedules[schedule_id])
            schedule.enabled = True
            schedule.next_run = self._calculate_next_run(schedule)
            self.schedules[schedule_id] = asdict(schedule)
            self._save_schedules()
            logger.info(f"Enabled schedule: {schedule.name}")
            return True
        return False
    
    def disable_schedule(self, schedule_id: str) -> bool:
        """Disable a schedule"""
        if schedule_id in self.schedules:
            schedule = BackupSchedule(**self.schedules[schedule_id])
            schedule.enabled = False
            self.schedules[schedule_id] = asdict(schedule)
            self._save_schedules()
            logger.info(f"Disabled schedule: {schedule.name}")
            return True
        return False
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule"""
        if schedule_id in self.schedules:
            schedule = BackupSchedule(**self.schedules[schedule_id])
            del self.schedules[schedule_id]
            self._save_schedules()
            logger.info(f"Deleted schedule: {schedule.name}")
            return True
        return False
    
    async def run_schedule_now(self, schedule_id: str) -> bool:
        """Run a schedule immediately"""
        if schedule_id not in self.schedules:
            return False
        
        schedule = BackupSchedule(**self.schedules[schedule_id])
        
        # Check if already running
        if schedule_id in self.active_tasks:
            logger.warning(f"Schedule {schedule.name} is already running")
            return False
        
        # Run backup
        await self._run_scheduled_backup(schedule)
        return True
    
    async def get_scheduler_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        schedules = self.list_schedules()
        
        stats = {
            "total_schedules": len(schedules),
            "enabled_schedules": len([s for s in schedules if s.enabled]),
            "disabled_schedules": len([s for s in schedules if not s.enabled]),
            "active_tasks": len(self.active_tasks),
            "total_runs": sum(s.run_count for s in schedules),
            "successful_runs": sum(s.success_count for s in schedules),
            "failed_runs": sum(s.failure_count for s in schedules),
            "next_run_time": min((s.next_run for s in schedules if s.enabled and s.next_run), default=None),
            "schedule_types": {
                schedule_type.value: len([s for s in schedules if s.schedule_type == schedule_type])
                for schedule_type in ScheduleType
            }
        }
        
        return stats
    
    # Predefined schedule templates
    def create_hourly_incremental_schedule(self) -> BackupSchedule:
        """Create hourly incremental backup schedule"""
        return self.create_schedule(
            name="Hourly Incremental Backup",
            schedule_type=ScheduleType.INTERVAL,
            backup_type="incremental",
            interval_hours=1,
            retention_days=7
        )
    
    def create_daily_full_schedule(self, time_str: str = "02:00") -> BackupSchedule:
        """Create daily full backup schedule"""
        return self.create_schedule(
            name="Daily Full Backup",
            schedule_type=ScheduleType.DAILY,
            backup_type="full",
            daily_time=time_str,
            retention_days=30
        )
    
    def create_weekly_full_schedule(self, day: int = 6, time_str: str = "01:00") -> BackupSchedule:
        """Create weekly full backup schedule (default: Sunday 1 AM)"""
        return self.create_schedule(
            name="Weekly Full Backup",
            schedule_type=ScheduleType.WEEKLY,
            backup_type="full",
            weekly_day=day,
            weekly_time=time_str,
            retention_days=90
        )
    
    def create_monthly_full_schedule(self, day: int = 1, time_str: str = "00:30") -> BackupSchedule:
        """Create monthly full backup schedule"""
        return self.create_schedule(
            name="Monthly Full Backup",
            schedule_type=ScheduleType.MONTHLY,
            backup_type="full",
            monthly_day=day,
            monthly_time=time_str,
            retention_days=365
        )
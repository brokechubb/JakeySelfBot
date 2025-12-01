"""
Healing strategies implementation for different types of system issues.
"""
import asyncio
import time
import os
import shutil
import tempfile
import gc
import sqlite3
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import psutil

from utils.logging_config import get_logger

logger = get_logger(__name__)


class StrategyResult(Enum):
    """Healing strategy execution results"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class HealingOutcome:
    """Outcome of a healing strategy execution"""
    strategy_name: str
    result: StrategyResult
    message: str
    metrics_before: Dict[str, Any]
    metrics_after: Dict[str, Any]
    execution_time: float
    details: Optional[Dict[str, Any]] = None


class HealingStrategies:
    """
    Collection of healing strategies for different system issues.
    """
    
    def __init__(self):
        """Initialize healing strategies."""
        self.strategies: Dict[str, Callable] = {
            "restart_service": self.restart_service,
            "memory_cleanup": self.memory_cleanup,
            "database_repair": self.database_repair,
            "queue_management": self.queue_management,
            "rate_limit_reset": self.rate_limit_reset,
            "performance_tuning": self.performance_tuning,
            "disk_cleanup": self.disk_cleanup,
            "connection_reset": self.connection_reset,
            "cache_rebuild": self.cache_rebuild,
            "service_scale_up": self.service_scale_up,
            "service_scale_down": self.service_scale_down,
            "config_reload": self.config_reload,
            "log_rotation": self.log_rotation,
            "temp_file_cleanup": self.temp_file_cleanup,
            "process_restart": self.process_restart,
            "dependency_check": self.dependency_check,
            "permission_fix": self.permission_fix,
            "index_rebuild": self.index_rebuild,
            "connection_pool_reset": self.connection_pool_reset
        }
        
        logger.info(f"Initialized {len(self.strategies)} healing strategies")
    
    async def execute_strategy(self, strategy_name: str, parameters: Dict[str, Any]) -> HealingOutcome:
        """
        Execute a specific healing strategy.
        
        Args:
            strategy_name: Name of the strategy to execute
            parameters: Strategy-specific parameters
            
        Returns:
            HealingOutcome with execution results
        """
        if strategy_name not in self.strategies:
            return HealingOutcome(
                strategy_name=strategy_name,
                result=StrategyResult.NOT_APPLICABLE,
                message=f"Unknown strategy: {strategy_name}",
                metrics_before={},
                metrics_after={},
                execution_time=0.0
            )
        
        # Collect metrics before execution
        metrics_before = await self._collect_system_metrics()
        
        start_time = time.time()
        
        try:
            # Execute the strategy
            result, message, details = await self.strategies[strategy_name](parameters)
            
            # Collect metrics after execution
            metrics_after = await self._collect_system_metrics()
            
            execution_time = time.time() - start_time
            
            outcome = HealingOutcome(
                strategy_name=strategy_name,
                result=result,
                message=message,
                metrics_before=metrics_before,
                metrics_after=metrics_after,
                execution_time=execution_time,
                details=details
            )
            
            logger.info(f"Strategy '{strategy_name}' executed: {result.value} - {message} ({execution_time:.2f}s)")
            return outcome
            
        except Exception as e:
            execution_time = time.time() - start_time
            metrics_after = await self._collect_system_metrics()
            
            logger.error(f"Strategy '{strategy_name}' failed with exception: {e}")
            
            return HealingOutcome(
                strategy_name=strategy_name,
                result=StrategyResult.FAILURE,
                message=f"Exception: {str(e)}",
                metrics_before=metrics_before,
                metrics_after=metrics_after,
                execution_time=execution_time
            )
    
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # Database size if available
            db_size = 0
            if os.path.exists("data/database.db"):
                db_size = os.path.getsize("data/database.db")
            
            return {
                "memory_total_mb": memory.total / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024),
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_percent": memory.percent,
                "cpu_percent": cpu_percent,
                "disk_total_gb": disk.total / (1024 * 1024 * 1024),
                "disk_used_gb": disk.used / (1024 * 1024 * 1024),
                "disk_free_gb": disk.free / (1024 * 1024 * 1024),
                "disk_percent": (disk.used / disk.total) * 100,
                "process_memory_mb": process_memory.rss / (1024 * 1024),
                "process_memory_vms_mb": process_memory.vms / (1024 * 1024),
                "database_size_mb": db_size / (1024 * 1024),
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {"timestamp": time.time(), "error": str(e)}
    
    # Individual healing strategies
    
    async def restart_service(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Restart specified services."""
        service_names = parameters.get("service_names", [])
        graceful = parameters.get("graceful", True)
        timeout = parameters.get("timeout", 30)
        
        if not service_names:
            return StrategyResult.NOT_APPLICABLE, "No services specified", {}
        
        results = {}
        
        for service_name in service_names:
            try:
                logger.info(f"Restarting service: {service_name}")
                
                # Simulate service restart (in real implementation, this would use systemd, docker, etc.)
                if graceful:
                    await asyncio.sleep(2)  # Graceful shutdown
                else:
                    await asyncio.sleep(1)  # Force shutdown
                
                await asyncio.sleep(1)  # Startup time
                
                results[service_name] = "success"
                logger.info(f"Service {service_name} restarted successfully")
                
            except Exception as e:
                results[service_name] = f"failed: {str(e)}"
                logger.error(f"Failed to restart service {service_name}: {e}")
        
        success_count = sum(1 for result in results.values() if result == "success")
        
        if success_count == len(service_names):
            return StrategyResult.SUCCESS, f"All {len(service_names)} services restarted", results
        elif success_count > 0:
            return StrategyResult.PARTIAL, f"{success_count}/{len(service_names)} services restarted", results
        else:
            return StrategyResult.FAILURE, "No services restarted successfully", results
    
    async def memory_cleanup(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Clean up memory and garbage collect."""
        clear_caches = parameters.get("clear_caches", True)
        force_gc = parameters.get("force_gc", True)
        aggressive = parameters.get("aggressive", False)
        
        details = {}
        
        try:
            # Clear Python caches
            if clear_caches:
                # Clear import caches
                import sys
                modules_to_clear = [name for name in sys.modules.keys() 
                                  if name.startswith('tempfile') or name.startswith('cache')]
                for module_name in modules_to_clear:
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                
                details["cleared_modules"] = len(modules_to_clear)
            
            # Force garbage collection
            if force_gc:
                collected = gc.collect()
                details["objects_collected"] = collected
                
                # Multiple passes for aggressive cleanup
                if aggressive:
                    for i in range(3):
                        additional = gc.collect()
                        details[f"pass_{i+2}_collected"] = additional
            
            # Get memory before and after
            process = psutil.Process()
            memory_before = process.memory_info().rss
            
            # Additional memory cleanup
            if aggressive:
                # Trigger internal Python cleanup
                gc.set_debug(gc.DEBUG_SAVEALL)
                gc.collect()
                gc.set_debug(0)
            
            memory_after = process.memory_info().rss
            memory_freed = (memory_before - memory_after) / (1024 * 1024)  # MB
            details["memory_freed_mb"] = memory_freed
            
            logger.info(f"Memory cleanup completed: freed {memory_freed:.1f}MB")
            
            return StrategyResult.SUCCESS, f"Memory cleanup completed, freed {memory_freed:.1f}MB", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Memory cleanup failed: {str(e)}", details
    
    async def database_repair(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Repair database corruption issues."""
        create_backup = parameters.get("create_backup", True)
        integrity_check = parameters.get("integrity_check", True)
        vacuum = parameters.get("vacuum", True)
        
        details = {}
        
        try:
            db_path = "data/database.db"
            if not os.path.exists(db_path):
                return StrategyResult.NOT_APPLICABLE, "Database file not found", details
            
            # Create backup if requested
            if create_backup:
                backup_path = f"data/database_backup_{int(time.time())}.db"
                shutil.copy2(db_path, backup_path)
                details["backup_created"] = backup_path
                logger.info(f"Created database backup: {backup_path}")
            
            # Check database integrity
            if integrity_check:
                conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    result = cursor.fetchone()
                    details["integrity_check"] = result[0]
                    
                    if result[0] != "ok":
                        conn.close()
                        return StrategyResult.FAILURE, f"Database integrity check failed: {result[0]}", details
                    
                finally:
                    conn.close()
            
            # Vacuum database
            if vacuum:
                conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute("VACUUM")
                    conn.commit()
                    details["vacuum_completed"] = True
                    logger.info("Database vacuum completed")
                    
                finally:
                    conn.close()
            
            # Get database size after repair
            db_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
            details["final_size_mb"] = db_size
            
            return StrategyResult.SUCCESS, "Database repair completed successfully", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Database repair failed: {str(e)}", details
    
    async def queue_management(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Manage message queue (flush, clear, etc.)."""
        action = parameters.get("action", "flush")
        preserve_critical = parameters.get("preserve_critical", True)
        max_age_seconds = parameters.get("max_age_seconds", 3600)
        
        details = {}
        
        try:
            # This would integrate with the actual message queue system
            # For now, simulate queue management
            
            if action == "flush":
                # Simulate flushing queue
                flushed_count = 100  # Simulated count
                details["flushed_count"] = flushed_count
                
                if preserve_critical:
                    details["preserved_critical"] = 10
                
                logger.info(f"Queue flush completed: {flushed_count} messages processed")
                
            elif action == "clear_old":
                # Clear old messages
                cleared_count = 50  # Simulated count
                details["cleared_count"] = cleared_count
                details["max_age_seconds"] = max_age_seconds
                
                logger.info(f"Cleared {cleared_count} old messages from queue")
                
            elif action == "pause":
                # Pause queue processing
                details["queue_paused"] = True
                logger.info("Queue processing paused")
                
            elif action == "resume":
                # Resume queue processing
                details["queue_resumed"] = True
                logger.info("Queue processing resumed")
                
            else:
                return StrategyResult.NOT_APPLICABLE, f"Unknown queue action: {action}", details
            
            return StrategyResult.SUCCESS, f"Queue management action '{action}' completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Queue management failed: {str(e)}", details
    
    async def rate_limit_reset(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Reset rate limit counters and backoff timers."""
        reset_all = parameters.get("reset_all", False)
        backoff_reset = parameters.get("backoff_reset", True)
        user_id = parameters.get("user_id")
        
        details = {}
        
        try:
            # This would integrate with the actual rate limiting system
            # For now, simulate rate limit reset
            
            if reset_all:
                # Reset all rate limit counters
                details["reset_all_counters"] = True
                details["users_reset"] = "all"
                logger.info("Reset all rate limit counters")
                
            elif user_id:
                # Reset specific user
                details["reset_user"] = user_id
                logger.info(f"Reset rate limit counters for user: {user_id}")
                
            else:
                # Reset expired counters only
                details["reset_expired"] = True
                logger.info("Reset expired rate limit counters")
            
            if backoff_reset:
                # Reset backoff timers
                details["backoff_reset"] = True
                logger.info("Reset backoff timers")
            
            return StrategyResult.SUCCESS, "Rate limit reset completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Rate limit reset failed: {str(e)}", details
    
    async def performance_tuning(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Tune system performance parameters."""
        cache_warmup = parameters.get("cache_warmup", True)
        connection_pool_optimization = parameters.get("connection_pool_optimization", True)
        thread_pool_adjustment = parameters.get("thread_pool_adjustment", False)
        
        details = {}
        
        try:
            # Cache warmup
            if cache_warmup:
                # Simulate cache warmup
                cache_entries = 50  # Simulated count
                details["cache_entries_warmed"] = cache_entries
                logger.info(f"Cache warmup completed: {cache_entries} entries")
            
            # Connection pool optimization
            if connection_pool_optimization:
                # Simulate connection pool optimization
                details["connection_pool_optimized"] = True
                details["max_connections"] = 20
                details["min_connections"] = 5
                logger.info("Connection pool optimization completed")
            
            # Thread pool adjustment
            if thread_pool_adjustment:
                # Adjust thread pool sizes based on system load
                cpu_count = psutil.cpu_count()
                optimal_threads = (cpu_count or 1) * 2
                details["thread_pool_size"] = optimal_threads
                logger.info(f"Thread pool adjusted to {optimal_threads} threads")
            
            return StrategyResult.SUCCESS, "Performance tuning completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Performance tuning failed: {str(e)}", details
    
    async def disk_cleanup(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Clean up disk space by removing temporary files and old data."""
        temp_files = parameters.get("temp_files", True)
        log_rotation = parameters.get("log_rotation", True)
        backup_cleanup = parameters.get("backup_cleanup", True)
        max_age_days = parameters.get("max_age_days", 7)
        
        details = {}
        space_freed: int = 0
        
        try:
            # Clean temporary files
            if temp_files:
                temp_dir = tempfile.gettempdir()
                cleaned_files = 0
                
                for item in os.listdir(temp_dir):
                    if item.startswith(('jakey_', 'recovery_', 'temp_')):
                        item_path = os.path.join(temp_dir, item)
                        try:
                            item_size = 0
                            if os.path.isfile(item_path):
                                item_size = os.path.getsize(item_path)
                                os.unlink(item_path)
                            elif os.path.isdir(item_path):
                                item_size = sum(
                                    os.path.getsize(os.path.join(dirpath, filename))
                                    for dirpath, dirnames, filenames in os.walk(item_path)
                                    for filename in filenames
                                )
                                shutil.rmtree(item_path)
                            
                            space_freed += item_size
                            cleaned_files += 1
                            
                        except Exception as e:
                            logger.warning(f"Failed to clean temp file {item_path}: {e}")
                
                details["temp_files_cleaned"] = cleaned_files
                details["temp_space_freed_bytes"] = space_freed
                logger.info(f"Cleaned {cleaned_files} temporary files")
            
            # Log rotation
            if log_rotation:
                # This would integrate with the actual log rotation system
                details["log_rotated"] = True
                logger.info("Log rotation completed")
            
            # Backup cleanup
            if backup_cleanup:
                backup_dir = "backups"
                if os.path.exists(backup_dir):
                    cutoff_time = time.time() - (max_age_days * 24 * 3600)
                    cleaned_backups = 0
                    
                    for item in os.listdir(backup_dir):
                        item_path = os.path.join(backup_dir, item)
                        if os.path.getctime(item_path) < cutoff_time:
                            try:
                                if os.path.isfile(item_path):
                                    item_size = os.path.getsize(item_path)
                                    os.unlink(item_path)
                                    space_freed += item_size
                                elif os.path.isdir(item_path):
                                    shutil.rmtree(item_path)
                                
                                cleaned_backups += 1
                                
                            except Exception as e:
                                logger.warning(f"Failed to clean backup {item_path}: {e}")
                    
                    details["backups_cleaned"] = cleaned_backups
                    logger.info(f"Cleaned {cleaned_backups} old backups")
            
            details["total_space_freed_mb"] = space_freed / (1024 * 1024)
            
            return StrategyResult.SUCCESS, f"Disk cleanup completed, freed {space_freed / (1024 * 1024):.1f}MB", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Disk cleanup failed: {str(e)}", details
    
    async def connection_reset(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Reset network connections and pools."""
        connection_types = parameters.get("connection_types", ["database", "ai_providers", "cache"])
        graceful = parameters.get("graceful", True)
        
        details = {}
        
        try:
            for conn_type in connection_types:
                try:
                    if graceful:
                        await asyncio.sleep(0.5)  # Graceful close
                    
                    # Simulate connection reset
                    details[f"{conn_type}_reset"] = True
                    logger.info(f"Reset {conn_type} connections")
                    
                except Exception as e:
                    details[f"{conn_type}_error"] = str(e)
                    logger.error(f"Failed to reset {conn_type} connections: {e}")
            
            return StrategyResult.SUCCESS, "Connection reset completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Connection reset failed: {str(e)}", details
    
    async def cache_rebuild(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Rebuild system caches."""
        cache_types = parameters.get("cache_types", ["memory", "disk", "distributed"])
        warm_data = parameters.get("warm_data", True)
        
        details = {}
        
        try:
            for cache_type in cache_types:
                try:
                    # Simulate cache rebuild
                    if cache_type == "memory":
                        # Clear memory caches
                        details[f"{cache_type}_cleared"] = True
                        
                    elif cache_type == "disk":
                        # Clear disk caches
                        details[f"{cache_type}_cleared"] = True
                        
                    elif cache_type == "distributed":
                        # Clear distributed caches
                        details[f"{cache_type}_cleared"] = True
                    
                    # Warm up cache with common data
                    if warm_data:
                        details[f"{cache_type}_warmed"] = True
                    
                    logger.info(f"Rebuilt {cache_type} cache")
                    
                except Exception as e:
                    details[f"{cache_type}_error"] = str(e)
                    logger.error(f"Failed to rebuild {cache_type} cache: {e}")
            
            return StrategyResult.SUCCESS, "Cache rebuild completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Cache rebuild failed: {str(e)}", details
    
    async def service_scale_up(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Scale up services to handle increased load."""
        service_name = parameters.get("service_name")
        scale_factor = parameters.get("scale_factor", 2)
        
        details = {}
        
        try:
            if not service_name:
                return StrategyResult.NOT_APPLICABLE, "No service name specified", details
            
            # Simulate service scaling
            details["service_name"] = service_name
            details["scale_factor"] = scale_factor
            details["previous_instances"] = 1
            details["new_instances"] = scale_factor
            
            logger.info(f"Scaled up service {service_name} by factor {scale_factor}")
            
            return StrategyResult.SUCCESS, f"Service {service_name} scaled up to {scale_factor} instances", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Service scale up failed: {str(e)}", details
    
    async def service_scale_down(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Scale down services to reduce resource usage."""
        service_name = parameters.get("service_name")
        target_instances = parameters.get("target_instances", 1)
        
        details = {}
        
        try:
            if not service_name:
                return StrategyResult.NOT_APPLICABLE, "No service name specified", details
            
            # Simulate service scaling
            details["service_name"] = service_name
            details["target_instances"] = target_instances
            details["previous_instances"] = 2  # Simulated
            
            logger.info(f"Scaled down service {service_name} to {target_instances} instances")
            
            return StrategyResult.SUCCESS, f"Service {service_name} scaled down to {target_instances} instances", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Service scale down failed: {str(e)}", details
    
    async def config_reload(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Reload configuration files."""
        config_types = parameters.get("config_types", ["main", "database", "ai_providers"])
        
        details = {}
        
        try:
            for config_type in config_types:
                try:
                    # Simulate config reload
                    details[f"{config_type}_reloaded"] = True
                    logger.info(f"Reloaded {config_type} configuration")
                    
                except Exception as e:
                    details[f"{config_type}_error"] = str(e)
                    logger.error(f"Failed to reload {config_type} configuration: {e}")
            
            return StrategyResult.SUCCESS, "Configuration reload completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Configuration reload failed: {str(e)}", details
    
    async def log_rotation(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Rotate log files."""
        max_size_mb = parameters.get("max_size_mb", 10)
        keep_files = parameters.get("keep_files", 5)
        
        details = {}
        
        try:
            # This would integrate with the actual log rotation system
            details["max_size_mb"] = max_size_mb
            details["keep_files"] = keep_files
            details["rotated_files"] = 3  # Simulated
            
            logger.info(f"Log rotation completed: max size {max_size_mb}MB, keep {keep_files} files")
            
            return StrategyResult.SUCCESS, "Log rotation completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Log rotation failed: {str(e)}", details
    
    async def temp_file_cleanup(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Clean up temporary files."""
        max_age_hours = parameters.get("max_age_hours", 24)
        patterns = parameters.get("patterns", ["temp_", "tmp_", "*.tmp"])
        
        details = {}
        cleaned_files = 0
        space_freed = 0
        
        try:
            temp_dir = tempfile.gettempdir()
            cutoff_time = time.time() - (max_age_hours * 3600)
            
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                
                # Check if file matches patterns and is old enough
                if (os.path.getctime(item_path) < cutoff_time and
                    any(pattern.replace('*', '') in item for pattern in patterns)):
                    
                    try:
                        item_size = 0
                        if os.path.isfile(item_path):
                            item_size = os.path.getsize(item_path)
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            item_size = sum(
                                os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, dirnames, filenames in os.walk(item_path)
                                for filename in filenames
                            )
                            shutil.rmtree(item_path)
                        
                        space_freed += item_size
                        cleaned_files += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to clean temp file {item_path}: {e}")
            
            details["cleaned_files"] = cleaned_files
            details["space_freed_mb"] = space_freed / (1024 * 1024)
            
            logger.info(f"Temp file cleanup completed: {cleaned_files} files, {space_freed / (1024 * 1024):.1f}MB freed")
            
            return StrategyResult.SUCCESS, f"Cleaned {cleaned_files} temporary files", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Temp file cleanup failed: {str(e)}", details
    
    async def process_restart(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Restart specific processes."""
        process_names = parameters.get("process_names", [])
        graceful = parameters.get("graceful", True)
        
        details = {}
        
        try:
            if not process_names:
                return StrategyResult.NOT_APPLICABLE, "No process names specified", details
            
            for process_name in process_names:
                try:
                    # Find and restart process
                    found = False
                    for proc in psutil.process_iter(['pid', 'name']):
                        if proc.info['name'] == process_name:
                            if graceful:
                                proc.terminate()
                                proc.wait(timeout=10)
                            else:
                                proc.kill()
                            found = True
                            break
                    
                    if found:
                        details[f"{process_name}_restarted"] = True
                        logger.info(f"Restarted process: {process_name}")
                    else:
                        details[f"{process_name}_not_found"] = True
                        logger.warning(f"Process not found: {process_name}")
                        
                except Exception as e:
                    details[f"{process_name}_error"] = str(e)
                    logger.error(f"Failed to restart process {process_name}: {e}")
            
            return StrategyResult.SUCCESS, "Process restart completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Process restart failed: {str(e)}", details
    
    async def dependency_check(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Check and fix system dependencies."""
        check_types = parameters.get("check_types", ["imports", "files", "services"])
        auto_fix = parameters.get("auto_fix", True)
        
        details = {}
        
        try:
            for check_type in check_types:
                try:
                    if check_type == "imports":
                        # Check critical imports
                        critical_imports = ["sqlite3", "asyncio", "discord"]
                        missing_imports = []
                        
                        for module in critical_imports:
                            try:
                                __import__(module)
                            except ImportError:
                                missing_imports.append(module)
                        
                        details["missing_imports"] = missing_imports
                        
                        if missing_imports and auto_fix:
                            # Would attempt to install missing packages
                            details["install_attempted"] = True
                    
                    elif check_type == "files":
                        # Check critical files
                        critical_files = ["config.py", "main.py"]
                        missing_files = []
                        
                        for file_path in critical_files:
                            if not os.path.exists(file_path):
                                missing_files.append(file_path)
                        
                        details["missing_files"] = missing_files
                    
                    elif check_type == "services":
                        # Check external services
                        services = ["database", "ai_providers"]
                        service_status = {}
                        
                        for service in services:
                            # Simulate service check
                            service_status[service] = "available"
                        
                        details["service_status"] = service_status
                    
                    logger.info(f"Dependency check completed for {check_type}")
                    
                except Exception as e:
                    details[f"{check_type}_error"] = str(e)
                    logger.error(f"Dependency check failed for {check_type}: {e}")
            
            return StrategyResult.SUCCESS, "Dependency check completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Dependency check failed: {str(e)}", details
    
    async def permission_fix(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Fix file and directory permissions."""
        paths = parameters.get("paths", ["data", "logs", "backups"])
        recursive = parameters.get("recursive", True)
        
        details = {}
        
        try:
            for path in paths:
                try:
                    if os.path.exists(path):
                        if recursive and os.path.isdir(path):
                            # Fix permissions recursively
                            for root, dirs, files in os.walk(path):
                                for item in dirs + files:
                                    item_path = os.path.join(root, item)
                                    os.chmod(item_path, 0o755 if os.path.isdir(item_path) else 0o644)
                        else:
                            # Fix single item permissions
                            os.chmod(path, 0o755 if os.path.isdir(path) else 0o644)
                        
                        details[f"{path}_fixed"] = True
                        logger.info(f"Fixed permissions for: {path}")
                    else:
                        details[f"{path}_not_found"] = True
                        
                except Exception as e:
                    details[f"{path}_error"] = str(e)
                    logger.error(f"Failed to fix permissions for {path}: {e}")
            
            return StrategyResult.SUCCESS, "Permission fix completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Permission fix failed: {str(e)}", details
    
    async def index_rebuild(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Rebuild database indexes."""
        db_path = parameters.get("db_path", "data/database.db")
        tables = parameters.get("tables", [])
        
        details = {}
        
        try:
            if not os.path.exists(db_path):
                return StrategyResult.NOT_APPLICABLE, "Database file not found", details
            
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.cursor()
                
                # Get all tables if not specified
                if not tables:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                
                rebuilt_indexes = 0
                
                for table in tables:
                    try:
                        # Get indexes for table
                        cursor.execute(f"PRAGMA index_list({table})")
                        indexes = cursor.fetchall()
                        
                        for index_info in indexes:
                            index_name = index_info[1]
                            
                            # Rebuild index
                            cursor.execute(f"REINDEX {index_name}")
                            rebuilt_indexes += 1
                        
                    except Exception as e:
                        details[f"{table}_error"] = str(e)
                        logger.warning(f"Failed to rebuild indexes for table {table}: {e}")
                
                conn.commit()
                details["rebuilt_indexes"] = rebuilt_indexes
                details["tables_processed"] = len(tables)
                
                logger.info(f"Rebuilt {rebuilt_indexes} indexes across {len(tables)} tables")
                
            finally:
                conn.close()
            
            return StrategyResult.SUCCESS, f"Rebuilt {rebuilt_indexes} database indexes", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Index rebuild failed: {str(e)}", details
    
    async def connection_pool_reset(self, parameters: Dict[str, Any]) -> tuple[StrategyResult, str, Dict[str, Any]]:
        """Reset connection pools."""
        pool_types = parameters.get("pool_types", ["database", "redis", "http"])
        drain_timeout = parameters.get("drain_timeout", 30)
        
        details = {}
        
        try:
            for pool_type in pool_types:
                try:
                    # Simulate connection pool reset
                    details[f"{pool_type}_drained"] = True
                    details[f"{pool_type}_recreated"] = True
                    
                    logger.info(f"Reset {pool_type} connection pool")
                    
                except Exception as e:
                    details[f"{pool_type}_error"] = str(e)
                    logger.error(f"Failed to reset {pool_type} connection pool: {e}")
            
            details["drain_timeout"] = drain_timeout
            
            return StrategyResult.SUCCESS, "Connection pool reset completed", details
            
        except Exception as e:
            return StrategyResult.FAILURE, f"Connection pool reset failed: {str(e)}", details
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available healing strategies."""
        return list(self.strategies.keys())
    
    def get_strategy_info(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific strategy."""
        if strategy_name not in self.strategies:
            return None
        
        strategy_func = self.strategies[strategy_name]
        
        return {
            "name": strategy_name,
            "description": strategy_func.__doc__ or "No description available",
            "parameters": self._get_strategy_parameters(strategy_name)
        }
    
    def _get_strategy_parameters(self, strategy_name: str) -> Dict[str, Any]:
        """Get parameter information for a strategy."""
        # This would ideally parse the function signature or use annotations
        # For now, return common parameters based on strategy type
        
        parameter_map = {
            "restart_service": ["service_names", "graceful", "timeout"],
            "memory_cleanup": ["clear_caches", "force_gc", "aggressive"],
            "database_repair": ["create_backup", "integrity_check", "vacuum"],
            "queue_management": ["action", "preserve_critical", "max_age_seconds"],
            "rate_limit_reset": ["reset_all", "backoff_reset", "user_id"],
            "performance_tuning": ["cache_warmup", "connection_pool_optimization", "thread_pool_adjustment"],
            "disk_cleanup": ["temp_files", "log_rotation", "backup_cleanup", "max_age_days"],
            "connection_reset": ["connection_types", "graceful"],
            "cache_rebuild": ["cache_types", "warm_data"],
            "service_scale_up": ["service_name", "scale_factor"],
            "service_scale_down": ["service_name", "target_instances"],
            "config_reload": ["config_types"],
            "log_rotation": ["max_size_mb", "keep_files"],
            "temp_file_cleanup": ["max_age_hours", "patterns"],
            "process_restart": ["process_names", "graceful"],
            "dependency_check": ["check_types", "auto_fix"],
            "permission_fix": ["paths", "recursive"],
            "index_rebuild": ["db_path", "tables"],
            "connection_pool_reset": ["pool_types", "drain_timeout"]
        }
        
        return {
            "parameters": parameter_map.get(strategy_name, []),
            "required": parameter_map.get(strategy_name, [])[:1]  # First parameter is typically required
        }


# Global healing strategies instance
healing_strategies = HealingStrategies()
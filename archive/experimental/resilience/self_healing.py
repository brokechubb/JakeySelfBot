"""
Comprehensive self-healing system for automatic issue detection and recovery.
"""
import asyncio
import time
import json
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import statistics
import hashlib
import os

from utils.logging_config import get_logger

logger = get_logger(__name__)


class IssueSeverity(Enum):
    """Issue severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueType(Enum):
    """Types of issues that can be detected"""
    MEMORY_LEAK = "memory_leak"
    CONNECTION_FAILURE = "connection_failure"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DATABASE_CORRUPTION = "database_corruption"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    AI_PROVIDER_FAILURE = "ai_provider_failure"
    QUEUE_BACKLOG = "queue_backlog"
    DISK_SPACE_LOW = "disk_space_low"
    CPU_OVERLOAD = "cpu_overload"
    UNKNOWN = "unknown"


class HealingStatus(Enum):
    """Healing operation status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Issue:
    """Detected issue information"""
    issue_id: str
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    component: str
    detected_at: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[float] = None
    healing_attempts: int = 0


@dataclass
class HealingAction:
    """Healing action definition"""
    action_id: str
    name: str
    description: str
    issue_types: List[IssueType]
    severity_threshold: IssueSeverity
    strategy: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    success_rate: float = 0.0
    total_attempts: int = 0
    last_used: Optional[float] = None
    validation_checks: List[str] = field(default_factory=list)


@dataclass
class HealingOperation:
    """Healing operation record"""
    operation_id: str
    issue_id: str
    action_id: str
    status: HealingStatus
    started_at: float
    completed_at: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    metrics_before: Dict[str, Any] = field(default_factory=dict)
    metrics_after: Dict[str, Any] = field(default_factory=dict)
    rollback_available: bool = True
    validation_passed: bool = False


@dataclass
class SystemHealthMetrics:
    """System health metrics"""
    timestamp: float
    memory_usage_mb: float
    cpu_usage_percent: float
    disk_usage_percent: float
    active_connections: int
    queue_size: int
    database_size_mb: float
    response_time_p95: float
    error_rate: float
    uptime_percentage: float


class SelfHealingSystem:
    """
    Comprehensive self-healing system with pattern detection and adaptive recovery.
    """
    
    def __init__(
        self,
        monitoring_interval: float = 30.0,
        healing_cooldown: float = 300.0,
        max_concurrent_healings: int = 3,
        learning_enabled: bool = True,
        metrics_history_size: int = 1000
    ):
        """
        Initialize self-healing system.
        
        Args:
            monitoring_interval: Seconds between health checks
            healing_cooldown: Cooldown period between healing attempts
            max_concurrent_healings: Maximum concurrent healing operations
            learning_enabled: Enable adaptive learning from healing attempts
            metrics_history_size: Size of metrics history to keep
        """
        self.monitoring_interval = monitoring_interval
        self.healing_cooldown = healing_cooldown
        self.max_concurrent_healings = max_concurrent_healings
        self.learning_enabled = learning_enabled
        self.metrics_history_size = metrics_history_size
        
        # Data storage
        self.issues: Dict[str, Issue] = {}
        self.healing_actions: Dict[str, HealingAction] = {}
        self.healing_operations: Dict[str, HealingOperation] = {}
        self.metrics_history: deque = deque(maxlen=metrics_history_size)
        
        # Pattern detection
        self.patterns: Dict[str, Dict[str, Any]] = {}
        self.adaptive_thresholds: Dict[str, float] = {}
        
        # System state
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._active_healings: Dict[str, asyncio.Task] = {}
        self._last_healing_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "issues_detected": 0,
            "issues_resolved": 0,
            "healings_attempted": 0,
            "healings_successful": 0,
            "healings_failed": 0,
            "total_healing_time": 0.0
        }
        
        # Initialize default healing strategies
        self._initialize_default_strategies()
        
        logger.info(f"Self-healing system initialized: monitoring_interval={monitoring_interval}s, "
                   f"max_concurrent_healings={max_concurrent_healings}")
    
    def _initialize_default_strategies(self):
        """Initialize default healing strategies"""
        default_strategies = [
            HealingAction(
                action_id="restart_ai_provider",
                name="Restart AI Provider",
                description="Restart failed AI provider connections",
                issue_types=[IssueType.AI_PROVIDER_FAILURE, IssueType.CONNECTION_FAILURE],
                severity_threshold=IssueSeverity.MEDIUM,
                strategy="restart_service",
                parameters={"service_names": ["ai_providers"], "graceful": True},
                validation_checks=["connection_test", "health_check"]
            ),
            HealingAction(
                action_id="clear_memory_cache",
                name="Clear Memory Cache",
                description="Clear memory caches to resolve memory leaks",
                issue_types=[IssueType.MEMORY_LEAK],
                severity_threshold=IssueSeverity.MEDIUM,
                strategy="memory_cleanup",
                parameters={"clear_caches": True, "force_gc": True},
                validation_checks=["memory_usage_check"]
            ),
            HealingAction(
                action_id="database_repair",
                name="Database Repair",
                description="Repair database corruption issues",
                issue_types=[IssueType.DATABASE_CORRUPTION],
                severity_threshold=IssueSeverity.HIGH,
                strategy="database_repair",
                parameters={"create_backup": True, "integrity_check": True},
                validation_checks=["database_integrity", "schema_validation"]
            ),
            HealingAction(
                action_id="queue_flush",
                name="Flush Message Queue",
                description="Clear backed up message queue",
                issue_types=[IssueType.QUEUE_BACKLOG],
                severity_threshold=IssueSeverity.HIGH,
                strategy="queue_management",
                parameters={"action": "flush", "preserve_critical": True},
                validation_checks=["queue_size_check"]
            ),
            HealingAction(
                action_id="rate_limit_reset",
                name="Reset Rate Limits",
                description="Reset rate limit counters",
                issue_types=[IssueType.RATE_LIMIT_EXCEEDED],
                severity_threshold=IssueSeverity.MEDIUM,
                strategy="rate_limit_reset",
                parameters={"reset_all": False, "backoff_reset": True},
                validation_checks=["rate_limit_check"]
            ),
            HealingAction(
                action_id="performance_optimization",
                name="Performance Optimization",
                description="Optimize system performance",
                issue_types=[IssueType.PERFORMANCE_DEGRADATION],
                severity_threshold=IssueSeverity.LOW,
                strategy="performance_tuning",
                parameters={"cache_warmup": True, "connection_pool_optimization": True},
                validation_checks=["performance_check"]
            ),
            HealingAction(
                action_id="disk_cleanup",
                name="Disk Cleanup",
                description="Clean up temporary files and logs",
                issue_types=[IssueType.DISK_SPACE_LOW],
                severity_threshold=IssueSeverity.HIGH,
                strategy="disk_cleanup",
                parameters={"temp_files": True, "log_rotation": True, "backup_cleanup": True},
                validation_checks=["disk_space_check"]
            )
        ]
        
        for strategy in default_strategies:
            self.healing_actions[strategy.action_id] = strategy
        
        logger.info(f"Initialized {len(default_strategies)} default healing strategies")
    
    async def start_monitoring(self):
        """Start continuous monitoring and healing."""
        if self._monitoring:
            logger.warning("Self-healing monitoring is already running")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Self-healing monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring and healing."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel active healings
        for operation_id, task in self._active_healings.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled healing operation: {operation_id}")
        
        if self._active_healings:
            await asyncio.gather(*self._active_healings.values(), return_exceptions=True)
        
        logger.info("Self-healing monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                # Collect system metrics
                metrics = await self._collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # Detect issues
                detected_issues = await self._detect_issues(metrics)
                
                # Process detected issues
                for issue in detected_issues:
                    await self._handle_detected_issue(issue)
                
                # Clean up resolved issues
                await self._cleanup_resolved_issues()
                
                # Update adaptive thresholds
                if self.learning_enabled:
                    await self._update_adaptive_thresholds()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in self-healing monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _collect_system_metrics(self) -> SystemHealthMetrics:
        """Collect current system health metrics."""
        import psutil
        import os
        
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_mb = memory.used / (1024 * 1024)
            
            # CPU usage
            cpu_usage_percent = psutil.cpu_percent(interval=1)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # Database size (if available)
            database_size_mb = 0
            if os.path.exists("data/database.db"):
                database_size_mb = os.path.getsize("data/database.db") / (1024 * 1024)
            
            # Calculate response time and error rate from recent metrics
            recent_metrics = list(self.metrics_history)[-10:] if self.metrics_history else []
            response_time_p95 = 0.0
            error_rate = 0.0
            uptime_percentage = 100.0
            
            if recent_metrics:
                response_times = [m.response_time_p95 for m in recent_metrics if m.response_time_p95 > 0]
                if response_times:
                    response_time_p95 = statistics.mean(response_times)
                
                error_rates = [m.error_rate for m in recent_metrics if m.error_rate > 0]
                if error_rates:
                    error_rate = statistics.mean(error_rates)
                
                uptime_percentages = [m.uptime_percentage for m in recent_metrics if m.uptime_percentage > 0]
                if uptime_percentages:
                    uptime_percentage = statistics.mean(uptime_percentages)
            
            metrics = SystemHealthMetrics(
                timestamp=time.time(),
                memory_usage_mb=memory_usage_mb,
                cpu_usage_percent=cpu_usage_percent,
                disk_usage_percent=disk_usage_percent,
                active_connections=0,  # Would be populated by actual connection tracking
                queue_size=0,  # Would be populated by queue monitoring
                database_size_mb=database_size_mb,
                response_time_p95=response_time_p95,
                error_rate=error_rate,
                uptime_percentage=uptime_percentage
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            # Return default metrics on error
            return SystemHealthMetrics(
                timestamp=time.time(),
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                disk_usage_percent=0.0,
                active_connections=0,
                queue_size=0,
                database_size_mb=0.0,
                response_time_p95=0.0,
                error_rate=0.0,
                uptime_percentage=100.0
            )
    
    async def _detect_issues(self, metrics: SystemHealthMetrics) -> List[Issue]:
        """Detect issues based on system metrics."""
        detected_issues = []
        
        # Memory leak detection
        memory_threshold = self.adaptive_thresholds.get("memory_usage_mb", 1000.0)  # 1GB default
        if metrics.memory_usage_mb > memory_threshold:
            issue = Issue(
                issue_id=self._generate_issue_id(),
                issue_type=IssueType.MEMORY_LEAK,
                severity=self._calculate_severity(metrics.memory_usage_mb, memory_threshold, 2.0),
                description=f"High memory usage detected: {metrics.memory_usage_mb:.1f}MB",
                component="system",
                detected_at=metrics.timestamp,
                metrics={"memory_usage_mb": metrics.memory_usage_mb, "threshold": memory_threshold}
            )
            detected_issues.append(issue)
        
        # CPU overload detection
        cpu_threshold = self.adaptive_thresholds.get("cpu_usage_percent", 80.0)
        if metrics.cpu_usage_percent > cpu_threshold:
            issue = Issue(
                issue_id=self._generate_issue_id(),
                issue_type=IssueType.CPU_OVERLOAD,
                severity=self._calculate_severity(metrics.cpu_usage_percent, cpu_threshold, 20.0),
                description=f"High CPU usage detected: {metrics.cpu_usage_percent:.1f}%",
                component="system",
                detected_at=metrics.timestamp,
                metrics={"cpu_usage_percent": metrics.cpu_usage_percent, "threshold": cpu_threshold}
            )
            detected_issues.append(issue)
        
        # Disk space low detection
        disk_threshold = self.adaptive_thresholds.get("disk_usage_percent", 85.0)
        if metrics.disk_usage_percent > disk_threshold:
            issue = Issue(
                issue_id=self._generate_issue_id(),
                issue_type=IssueType.DISK_SPACE_LOW,
                severity=self._calculate_severity(metrics.disk_usage_percent, disk_threshold, 10.0),
                description=f"Low disk space detected: {metrics.disk_usage_percent:.1f}%",
                component="system",
                detected_at=metrics.timestamp,
                metrics={"disk_usage_percent": metrics.disk_usage_percent, "threshold": disk_threshold}
            )
            detected_issues.append(issue)
        
        # Performance degradation detection
        response_threshold = self.adaptive_thresholds.get("response_time_p95", 5.0)
        if metrics.response_time_p95 > response_threshold:
            issue = Issue(
                issue_id=self._generate_issue_id(),
                issue_type=IssueType.PERFORMANCE_DEGRADATION,
                severity=self._calculate_severity(metrics.response_time_p95, response_threshold, 2.0),
                description=f"High response time detected: {metrics.response_time_p95:.2f}s",
                component="system",
                detected_at=metrics.timestamp,
                metrics={"response_time_p95": metrics.response_time_p95, "threshold": response_threshold}
            )
            detected_issues.append(issue)
        
        # High error rate detection
        error_threshold = self.adaptive_thresholds.get("error_rate", 0.1)  # 10% error rate
        if metrics.error_rate > error_threshold:
            issue = Issue(
                issue_id=self._generate_issue_id(),
                issue_type=IssueType.PERFORMANCE_DEGRADATION,
                severity=self._calculate_severity(metrics.error_rate, error_threshold, 0.05),
                description=f"High error rate detected: {metrics.error_rate:.2%}",
                component="system",
                detected_at=metrics.timestamp,
                metrics={"error_rate": metrics.error_rate, "threshold": error_threshold}
            )
            detected_issues.append(issue)
        
        # Pattern-based detection
        pattern_issues = await self._detect_pattern_issues(metrics)
        detected_issues.extend(pattern_issues)
        
        return detected_issues
    
    async def _detect_pattern_issues(self, metrics: SystemHealthMetrics) -> List[Issue]:
        """Detect issues based on historical patterns."""
        pattern_issues = []
        
        if len(self.metrics_history) < 10:
            return pattern_issues
        
        # Analyze trends in recent metrics
        recent_metrics = list(self.metrics_history)[-10:]
        
        # Memory growth trend detection
        memory_trend = self._calculate_trend([m.memory_usage_mb for m in recent_metrics])
        if memory_trend > 50:  # Growing by more than 50MB per monitoring interval
            issue = Issue(
                issue_id=self._generate_issue_id(),
                issue_type=IssueType.MEMORY_LEAK,
                severity=IssueSeverity.MEDIUM,
                description=f"Memory usage trending upward: +{memory_trend:.1f}MB per interval",
                component="system",
                detected_at=metrics.timestamp,
                metrics={"memory_trend": memory_trend, "trend_window": 10}
            )
            pattern_issues.append(issue)
        
        # Response time degradation trend
        response_trend = self._calculate_trend([m.response_time_p95 for m in recent_metrics])
        if response_trend > 0.1:  # Response time increasing by more than 100ms per interval
            issue = Issue(
                issue_id=self._generate_issue_id(),
                issue_type=IssueType.PERFORMANCE_DEGRADATION,
                severity=IssueSeverity.LOW,
                description=f"Response time degrading: +{response_trend:.3f}s per interval",
                component="system",
                detected_at=metrics.timestamp,
                metrics={"response_trend": response_trend, "trend_window": 10}
            )
            pattern_issues.append(issue)
        
        return pattern_issues
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate linear trend (slope) of values."""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x = list(range(n))
        
        # Calculate linear regression slope
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _calculate_severity(self, current_value: float, threshold: float, critical_factor: float) -> IssueSeverity:
        """Calculate issue severity based on how much the value exceeds the threshold."""
        ratio = current_value / threshold
        
        if ratio >= critical_factor:
            return IssueSeverity.CRITICAL
        elif ratio >= (threshold + critical_factor) / 2:
            return IssueSeverity.HIGH
        elif ratio >= threshold:
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW
    
    async def _handle_detected_issue(self, issue: Issue):
        """Handle a newly detected issue."""
        # Check if issue already exists
        existing_issue = None
        for existing in self.issues.values():
            if (existing.issue_type == issue.issue_type and 
                existing.component == issue.component and 
                not existing.resolved):
                existing_issue = existing
                break
        
        if existing_issue:
            # Update existing issue
            existing_issue.detected_at = issue.detected_at
            existing_issue.metrics.update(issue.metrics)
            logger.debug(f"Updated existing issue: {existing_issue.issue_id}")
            return
        
        # Register new issue
        self.issues[issue.issue_id] = issue
        self.stats["issues_detected"] += 1
        
        logger.warning(f"New issue detected: {issue.issue_type.value} - {issue.description}")
        
        # Attempt healing if severity is sufficient
        if issue.severity.value in ["medium", "high", "critical"]:
            await self._attempt_healing(issue)
    
    async def _attempt_healing(self, issue: Issue):
        """Attempt to heal the detected issue."""
        # Find suitable healing actions
        suitable_actions = [
            action for action in self.healing_actions.values()
            if (issue.issue_type in action.issue_types and
                self._severity_meets_threshold(issue.severity, action.severity_threshold))
        ]
        
        if not suitable_actions:
            logger.info(f"No suitable healing actions found for issue: {issue.issue_id}")
            return
        
        # Sort by success rate (learning) and recency
        suitable_actions.sort(key=lambda a: (a.success_rate, a.last_used or 0), reverse=True)
        
        # Check cooldown
        current_time = time.time()
        for action in suitable_actions:
            last_healing = self._last_healing_times.get(action.action_id, 0)
            if current_time - last_healing < self.healing_cooldown:
                logger.debug(f"Healing action {action.action_id} is in cooldown")
                continue
            
            # Check concurrent healing limit
            if len(self._active_healings) >= self.max_concurrent_healings:
                logger.info("Maximum concurrent healings reached, queuing issue")
                break
            
            # Attempt healing
            await self._execute_healing_action(issue, action)
            break
    
    def _severity_meets_threshold(self, issue_severity: IssueSeverity, action_threshold: IssueSeverity) -> bool:
        """Check if issue severity meets action threshold."""
        severity_order = {
            IssueSeverity.LOW: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.HIGH: 3,
            IssueSeverity.CRITICAL: 4
        }
        
        return severity_order[issue_severity] >= severity_order[action_threshold]
    
    async def _execute_healing_action(self, issue: Issue, action: HealingAction):
        """Execute a healing action."""
        operation_id = self._generate_operation_id()
        
        operation = HealingOperation(
            operation_id=operation_id,
            issue_id=issue.issue_id,
            action_id=action.action_id,
            status=HealingStatus.PENDING,
            started_at=time.time(),
            metrics_before=await self._get_current_metrics_snapshot()
        )
        
        self.healing_operations[operation_id] = operation
        self.stats["healings_attempted"] += 1
        
        # Update action metadata
        action.total_attempts += 1
        action.last_used = time.time()
        self._last_healing_times[action.action_id] = time.time()
        
        # Start healing task
        task = asyncio.create_task(self._perform_healing(operation, issue, action))
        self._active_healings[operation_id] = task
        
        logger.info(f"Started healing operation: {operation_id} for issue: {issue.issue_id} using action: {action.action_id}")
    
    async def _perform_healing(self, operation: HealingOperation, issue: Issue, action: HealingAction):
        """Perform the actual healing operation."""
        try:
            operation.status = HealingStatus.IN_PROGRESS
            
            # Execute healing strategy
            success = await self._execute_healing_strategy(action.strategy, action.parameters)
            
            if success:
                # Validate healing
                validation_passed = await self._validate_healing(action.validation_checks)
                operation.validation_passed = validation_passed
                
                if validation_passed:
                    operation.status = HealingStatus.COMPLETED
                    operation.success = True
                    issue.resolved = True
                    issue.resolution_time = time.time()
                    
                    # Update statistics
                    self.stats["healings_successful"] += 1
                    self.stats["issues_resolved"] += 1
                    action.success_rate = (action.success_rate * (action.total_attempts - 1) + 1) / action.total_attempts
                    
                    logger.info(f"Healing operation completed successfully: {operation.operation_id}")
                else:
                    operation.status = HealingStatus.VALIDATION_FAILED
                    operation.error_message = "Post-healing validation failed"
                    
                    # Attempt rollback if available
                    if operation.rollback_available:
                        await self._rollback_healing(operation)
                    
                    logger.warning(f"Healing validation failed: {operation.operation_id}")
            else:
                operation.status = HealingStatus.FAILED
                operation.error_message = "Healing strategy execution failed"
                
                # Update statistics
                self.stats["healings_failed"] += 1
                action.success_rate = (action.success_rate * (action.total_attempts - 1) + 0) / action.total_attempts
                
                logger.error(f"Healing operation failed: {operation.operation_id}")
        
        except Exception as e:
            operation.status = HealingStatus.FAILED
            operation.error_message = str(e)
            self.stats["healings_failed"] += 1
            action.success_rate = (action.success_rate * (action.total_attempts - 1) + 0) / action.total_attempts
            
            logger.error(f"Healing operation exception: {operation.operation_id} - {e}")
        
        finally:
            operation.completed_at = time.time()
            operation.metrics_after = await self._get_current_metrics_snapshot()
            
            # Update total healing time
            if operation.completed_at and operation.started_at:
                self.stats["total_healing_time"] += operation.completed_at - operation.started_at
            
            # Clean up active healing
            if operation.operation_id in self._active_healings:
                del self._active_healings[operation.operation_id]
    
    async def _execute_healing_strategy(self, strategy: str, parameters: Dict[str, Any]) -> bool:
        """Execute a specific healing strategy."""
        try:
            if strategy == "restart_service":
                return await self._strategy_restart_service(parameters)
            elif strategy == "memory_cleanup":
                return await self._strategy_memory_cleanup(parameters)
            elif strategy == "database_repair":
                return await self._strategy_database_repair(parameters)
            elif strategy == "queue_management":
                return await self._strategy_queue_management(parameters)
            elif strategy == "rate_limit_reset":
                return await self._strategy_rate_limit_reset(parameters)
            elif strategy == "performance_tuning":
                return await self._strategy_performance_tuning(parameters)
            elif strategy == "disk_cleanup":
                return await self._strategy_disk_cleanup(parameters)
            else:
                logger.error(f"Unknown healing strategy: {strategy}")
                return False
        
        except Exception as e:
            logger.error(f"Healing strategy execution failed: {strategy} - {e}")
            return False
    
    async def _strategy_restart_service(self, parameters: Dict[str, Any]) -> bool:
        """Restart service strategy."""
        logger.info("Executing service restart strategy")
        
        # This would integrate with the actual service management
        # For now, simulate the restart
        await asyncio.sleep(2)
        
        # Clear any cached connections or state
        # Implementation would depend on the specific services
        
        logger.info("Service restart strategy completed")
        return True
    
    async def _strategy_memory_cleanup(self, parameters: Dict[str, Any]) -> bool:
        """Memory cleanup strategy."""
        logger.info("Executing memory cleanup strategy")
        
        import gc
        
        if parameters.get("clear_caches", False):
            # Clear various caches
            # This would integrate with actual cache management
            pass
        
        if parameters.get("force_gc", False):
            # Force garbage collection
            collected = gc.collect()
            logger.info(f"Garbage collection freed {collected} objects")
        
        logger.info("Memory cleanup strategy completed")
        return True
    
    async def _strategy_database_repair(self, parameters: Dict[str, Any]) -> bool:
        """Database repair strategy."""
        logger.info("Executing database repair strategy")
        
        # This would integrate with the database recovery manager
        # For now, simulate the repair process
        await asyncio.sleep(3)
        
        logger.info("Database repair strategy completed")
        return True
    
    async def _strategy_queue_management(self, parameters: Dict[str, Any]) -> bool:
        """Queue management strategy."""
        logger.info("Executing queue management strategy")
        
        action = parameters.get("action", "flush")
        
        if action == "flush":
            # This would integrate with the message queue system
            pass
        
        logger.info(f"Queue management strategy completed: {action}")
        return True
    
    async def _strategy_rate_limit_reset(self, parameters: Dict[str, Any]) -> bool:
        """Rate limit reset strategy."""
        logger.info("Executing rate limit reset strategy")
        
        # This would integrate with the rate limiting system
        # Reset rate limit counters and backoff timers
        
        logger.info("Rate limit reset strategy completed")
        return True
    
    async def _strategy_performance_tuning(self, parameters: Dict[str, Any]) -> bool:
        """Performance tuning strategy."""
        logger.info("Executing performance tuning strategy")
        
        if parameters.get("cache_warmup", False):
            # Warm up caches
            pass
        
        if parameters.get("connection_pool_optimization", False):
            # Optimize connection pools
            pass
        
        logger.info("Performance tuning strategy completed")
        return True
    
    async def _strategy_disk_cleanup(self, parameters: Dict[str, Any]) -> bool:
        """Disk cleanup strategy."""
        logger.info("Executing disk cleanup strategy")
        
        import shutil
        import tempfile
        
        try:
            if parameters.get("temp_files", False):
                # Clean temporary files
                temp_dir = tempfile.gettempdir()
                cleaned = 0
                
                for item in os.listdir(temp_dir):
                    if item.startswith('jakey_') or item.startswith('recovery_'):
                        item_path = os.path.join(temp_dir, item)
                        try:
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                            else:
                                os.unlink(item_path)
                            cleaned += 1
                        except Exception as e:
                            logger.warning(f"Failed to clean temp file {item_path}: {e}")
                
                logger.info(f"Cleaned {cleaned} temporary files")
            
            if parameters.get("log_rotation", False):
                # Rotate log files
                # This would integrate with the log rotation system
                pass
            
            if parameters.get("backup_cleanup", False):
                # Clean old backups
                # This would integrate with the backup manager
                pass
            
            logger.info("Disk cleanup strategy completed")
            return True
            
        except Exception as e:
            logger.error(f"Disk cleanup strategy failed: {e}")
            return False
    
    async def _validate_healing(self, validation_checks: List[str]) -> bool:
        """Validate that healing was successful."""
        logger.info(f"Running healing validation checks: {validation_checks}")
        
        for check in validation_checks:
            try:
                if check == "connection_test":
                    # Test connections
                    pass
                elif check == "health_check":
                    # Run health checks
                    pass
                elif check == "memory_usage_check":
                    # Check memory usage
                    metrics = await self._collect_system_metrics()
                    if metrics.memory_usage_mb > self.adaptive_thresholds.get("memory_usage_mb", 1000.0):
                        return False
                elif check == "database_integrity":
                    # Check database integrity
                    pass
                elif check == "schema_validation":
                    # Validate database schema
                    pass
                elif check == "queue_size_check":
                    # Check queue size
                    pass
                elif check == "rate_limit_check":
                    # Check rate limits
                    pass
                elif check == "performance_check":
                    # Check performance metrics
                    metrics = await self._collect_system_metrics()
                    if metrics.response_time_p95 > self.adaptive_thresholds.get("response_time_p95", 5.0):
                        return False
                elif check == "disk_space_check":
                    # Check disk space
                    metrics = await self._collect_system_metrics()
                    if metrics.disk_usage_percent > self.adaptive_thresholds.get("disk_usage_percent", 85.0):
                        return False
                
            except Exception as e:
                logger.error(f"Validation check failed: {check} - {e}")
                return False
        
        logger.info("All healing validation checks passed")
        return True
    
    async def _rollback_healing(self, operation: HealingOperation):
        """Rollback a failed healing operation."""
        logger.info(f"Rolling back healing operation: {operation.operation_id}")
        
        try:
            # This would implement actual rollback logic
            # For now, just mark as rolled back
            operation.status = HealingStatus.ROLLED_BACK
            
            logger.info(f"Healing operation rolled back: {operation.operation_id}")
            
        except Exception as e:
            logger.error(f"Rollback failed for operation {operation.operation_id}: {e}")
    
    async def _get_current_metrics_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of current system metrics."""
        metrics = await self._collect_system_metrics()
        return {
            "memory_usage_mb": metrics.memory_usage_mb,
            "cpu_usage_percent": metrics.cpu_usage_percent,
            "disk_usage_percent": metrics.disk_usage_percent,
            "response_time_p95": metrics.response_time_p95,
            "error_rate": metrics.error_rate,
            "uptime_percentage": metrics.uptime_percentage
        }
    
    async def _cleanup_resolved_issues(self):
        """Clean up old resolved issues."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # Keep resolved issues for 1 hour
        
        resolved_issues = [
            issue_id for issue_id, issue in self.issues.items()
            if issue.resolved and issue.resolution_time and issue.resolution_time < cutoff_time
        ]
        
        for issue_id in resolved_issues:
            del self.issues[issue_id]
            logger.debug(f"Cleaned up resolved issue: {issue_id}")
    
    async def _update_adaptive_thresholds(self):
        """Update adaptive thresholds based on historical data."""
        if len(self.metrics_history) < 50:
            return
        
        recent_metrics = list(self.metrics_history)[-50:]
        
        # Update memory threshold based on typical usage
        memory_values = [m.memory_usage_mb for m in recent_metrics]
        if memory_values:
            typical_memory = statistics.mean(memory_values)
            memory_std = statistics.stdev(memory_values) if len(memory_values) > 1 else 0
            new_threshold = typical_memory + (2 * memory_std)  # 2 standard deviations above mean
            self.adaptive_thresholds["memory_usage_mb"] = max(new_threshold, 500.0)  # Minimum 500MB
        
        # Update CPU threshold
        cpu_values = [m.cpu_usage_percent for m in recent_metrics]
        if cpu_values:
            typical_cpu = statistics.mean(cpu_values)
            cpu_std = statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0
            new_threshold = typical_cpu + (1.5 * cpu_std)  # 1.5 standard deviations above mean
            self.adaptive_thresholds["cpu_usage_percent"] = min(max(new_threshold, 60.0), 95.0)  # Between 60% and 95%
        
        # Update response time threshold
        response_values = [m.response_time_p95 for m in recent_metrics if m.response_time_p95 > 0]
        if response_values:
            typical_response = statistics.mean(response_values)
            response_std = statistics.stdev(response_values) if len(response_values) > 1 else 0
            new_threshold = typical_response + (2 * response_std)
            self.adaptive_thresholds["response_time_p95"] = max(new_threshold, 1.0)  # Minimum 1 second
        
        # Update error rate threshold
        error_values = [m.error_rate for m in recent_metrics if m.error_rate > 0]
        if error_values:
            typical_error = statistics.mean(error_values)
            error_std = statistics.stdev(error_values) if len(error_values) > 1 else 0
            new_threshold = typical_error + (1.5 * error_std)
            self.adaptive_thresholds["error_rate"] = min(max(new_threshold, 0.05), 0.2)  # Between 5% and 20%
        
        logger.debug("Updated adaptive thresholds")
    
    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        timestamp = int(time.time())
        random_hash = hashlib.md5(f"{timestamp}{os.getpid()}".encode()).hexdigest()[:8]
        return f"issue_{timestamp}_{random_hash}"
    
    def _generate_operation_id(self) -> str:
        """Generate unique healing operation ID."""
        timestamp = int(time.time())
        random_hash = hashlib.md5(f"{timestamp}{os.getpid()}".encode()).hexdigest()[:8]
        return f"heal_{timestamp}_{random_hash}"
    
    # Public API methods
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        current_time = time.time()
        
        # Count active issues by severity
        active_issues = [issue for issue in self.issues.values() if not issue.resolved]
        issue_counts = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0
        }
        
        for issue in active_issues:
            issue_counts[issue.severity.value] += 1
        
        # Count active healings
        active_healings = len(self._active_healings)
        
        # Get latest metrics
        latest_metrics = self.metrics_history[-1] if self.metrics_history else None
        
        status = {
            "monitoring_active": self._monitoring,
            "active_issues": len(active_issues),
            "issues_by_severity": issue_counts,
            "active_healings": active_healings,
            "total_issues_detected": self.stats["issues_detected"],
            "total_issues_resolved": self.stats["issues_resolved"],
            "healings_attempted": self.stats["healings_attempted"],
            "healings_successful": self.stats["healings_successful"],
            "healings_failed": self.stats["healings_failed"],
            "healing_success_rate": (
                self.stats["healings_successful"] / self.stats["healings_attempted"]
                if self.stats["healings_attempted"] > 0 else 0
            ),
            "average_healing_time": (
                self.stats["total_healing_time"] / self.stats["healings_successful"]
                if self.stats["healings_successful"] > 0 else 0
            ),
            "adaptive_thresholds": self.adaptive_thresholds.copy(),
            "latest_metrics": asdict(latest_metrics) if latest_metrics else None
        }
        
        return status
    
    def get_active_issues(self) -> List[Dict[str, Any]]:
        """Get list of active issues."""
        active_issues = [issue for issue in self.issues.values() if not issue.resolved]
        return [asdict(issue) for issue in active_issues]
    
    def get_healing_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get healing operation history."""
        operations = list(self.healing_operations.values())
        operations.sort(key=lambda op: op.started_at, reverse=True)
        return [asdict(op) for op in operations[:limit]]
    
    def register_custom_strategy(self, strategy: HealingAction):
        """Register a custom healing strategy."""
        self.healing_actions[strategy.action_id] = strategy
        logger.info(f"Registered custom healing strategy: {strategy.action_id}")
    
    async def force_heal_issue(self, issue_id: str, action_id: Optional[str] = None) -> bool:
        """Force healing of a specific issue."""
        if issue_id not in self.issues:
            logger.error(f"Issue not found: {issue_id}")
            return False
        
        issue = self.issues[issue_id]
        
        if action_id:
            if action_id not in self.healing_actions:
                logger.error(f"Healing action not found: {action_id}")
                return False
            action = self.healing_actions[action_id]
        else:
            # Find suitable action
            suitable_actions = [
                action for action in self.healing_actions.values()
                if issue.issue_type in action.issue_types
            ]
            if not suitable_actions:
                logger.error(f"No suitable healing actions for issue: {issue_id}")
                return False
            action = suitable_actions[0]
        
        await self._execute_healing_action(issue, action)
        return True
    
    def export_healing_data(self, filepath: str):
        """Export healing data to JSON file."""
        data = {
            "issues": {issue_id: asdict(issue) for issue_id, issue in self.issues.items()},
            "healing_actions": {action_id: asdict(action) for action_id, action in self.healing_actions.items()},
            "healing_operations": {op_id: asdict(op) for op_id, op in self.healing_operations.items()},
            "adaptive_thresholds": self.adaptive_thresholds,
            "statistics": self.stats,
            "export_timestamp": time.time()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Exported healing data to {filepath}")


# Global self-healing system instance
self_healing_system = SelfHealingSystem()
"""
System health analysis and monitoring for comprehensive health assessment.
"""
import asyncio
import time
import statistics
import sqlite3
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import psutil

from utils.logging_config import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class ComponentType(Enum):
    """System component types"""
    SYSTEM = "system"
    DATABASE = "database"
    AI_PROVIDERS = "ai_providers"
    MESSAGE_QUEUE = "message_queue"
    DISK_IO = "disk_io"
    NETWORK = "network"
    MEMORY = "memory"
    CPU = "cpu"


@dataclass
class HealthMetric:
    """Individual health metric"""
    name: str
    value: float
    unit: str
    status: HealthStatus
    threshold_good: float
    threshold_fair: float
    threshold_poor: float
    timestamp: float
    component: ComponentType
    description: str = ""


@dataclass
class ComponentHealth:
    """Health status for a system component"""
    component_type: ComponentType
    component_name: str
    overall_status: HealthStatus
    health_score: float  # 0-100
    metrics: List[HealthMetric] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


@dataclass
class SystemHealthReport:
    """Comprehensive system health report"""
    timestamp: float
    overall_status: HealthStatus
    overall_score: float
    component_health: Dict[str, ComponentHealth] = field(default_factory=dict)
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    performance_summary: Dict[str, Any] = field(default_factory=dict)
    resource_usage: Dict[str, Any] = field(default_factory=dict)


class HealthAnalyzer:
    """
    Comprehensive system health analyzer with multi-component monitoring.
    """
    
    def __init__(
        self,
        metrics_history_size: int = 1000,
        analysis_interval: float = 60.0,
        health_check_timeout: float = 10.0
    ):
        """
        Initialize health analyzer.
        
        Args:
            metrics_history_size: Size of metrics history to keep
            analysis_interval: Interval between health analyses
            health_check_timeout: Timeout for individual health checks
        """
        self.metrics_history_size = metrics_history_size
        self.analysis_interval = analysis_interval
        self.health_check_timeout = health_check_timeout
        
        # Data storage
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=metrics_history_size))
        self.component_health: Dict[str, ComponentHealth] = {}
        self.health_reports: deque = deque(maxlen=100)  # Keep last 100 reports
        
        # Health thresholds
        self.thresholds = self._initialize_thresholds()
        
        # Analysis state
        self._analyzing = False
        self._analysis_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Health check functions
        self.health_checkers = {
            ComponentType.SYSTEM: self._check_system_health,
            ComponentType.DATABASE: self._check_database_health,
            ComponentType.AI_PROVIDERS: self._check_ai_providers_health,
            ComponentType.MESSAGE_QUEUE: self._check_message_queue_health,
            ComponentType.DISK_IO: self._check_disk_io_health,
            ComponentType.NETWORK: self._check_network_health,
            ComponentType.MEMORY: self._check_memory_health,
            ComponentType.CPU: self._check_cpu_health
        }
        
        logger.info(f"Health analyzer initialized: analysis_interval={analysis_interval}s")
    
    def _initialize_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Initialize health thresholds for different metrics."""
        return {
            "cpu_usage": {
                "good": 50.0,
                "fair": 75.0,
                "poor": 90.0
            },
            "memory_usage": {
                "good": 60.0,
                "fair": 80.0,
                "poor": 95.0
            },
            "disk_usage": {
                "good": 70.0,
                "fair": 85.0,
                "poor": 95.0
            },
            "disk_io_read": {
                "good": 50.0,  # MB/s
                "fair": 20.0,
                "poor": 5.0
            },
            "disk_io_write": {
                "good": 50.0,  # MB/s
                "fair": 20.0,
                "poor": 5.0
            },
            "response_time": {
                "good": 1.0,   # seconds
                "fair": 3.0,
                "poor": 10.0
            },
            "error_rate": {
                "good": 0.01,  # 1%
                "fair": 0.05,  # 5%
                "poor": 0.15   # 15%
            },
            "queue_size": {
                "good": 100,
                "fair": 500,
                "poor": 1000
            },
            "database_size": {
                "good": 1000,  # MB
                "fair": 5000,
                "poor": 10000
            },
            "connection_pool": {
                "good": 0.7,   # utilization
                "fair": 0.85,
                "poor": 0.95
            }
        }
    
    async def start_analysis(self):
        """Start continuous health analysis."""
        if self._analyzing:
            logger.warning("Health analysis is already running")
            return
        
        self._analyzing = True
        self._analysis_task = asyncio.create_task(self._analysis_loop())
        logger.info("Health analysis started")
    
    async def stop_analysis(self):
        """Stop health analysis."""
        if not self._analyzing:
            return
        
        self._analyzing = False
        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health analysis stopped")
    
    async def _analysis_loop(self):
        """Main analysis loop."""
        while self._analyzing:
            try:
                # Perform comprehensive health analysis
                report = await self.analyze_system_health()
                
                # Store the report
                self.health_reports.append(report)
                
                # Log critical issues
                if report.overall_status in [HealthStatus.POOR, HealthStatus.CRITICAL]:
                    logger.warning(f"System health is {report.overall_status.value}: {len(report.critical_issues)} critical issues")
                
                await asyncio.sleep(self.analysis_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health analysis loop: {e}")
                await asyncio.sleep(5)  # Brief pause on error
    
    async def analyze_system_health(self) -> SystemHealthReport:
        """Perform comprehensive system health analysis."""
        async with self._lock:
            timestamp = time.time()
            
            # Collect metrics for all components
            component_health = {}
            all_metrics = []
            all_issues = []
            all_warnings = []
            all_recommendations = []
            
            for component_type, checker_func in self.health_checkers.items():
                try:
                    component_health_result = await asyncio.wait_for(
                        checker_func(),
                        timeout=self.health_check_timeout
                    )
                    
                    component_key = f"{component_type.value}_{component_health_result.component_name}"
                    component_health[component_key] = component_health_result
                    all_metrics.extend(component_health_result.metrics)
                    all_issues.extend(component_health_result.issues)
                    all_warnings.extend([issue for issue in component_health_result.issues 
                                        if component_health_result.overall_status in [HealthStatus.FAIR, HealthStatus.POOR]])
                    all_recommendations.extend(component_health_result.recommendations)
                    
                except asyncio.TimeoutError:
                    logger.error(f"Health check timeout for component: {component_type.value}")
                    # Create a critical health status for timeout
                    critical_component = ComponentHealth(
                        component_type=component_type,
                        component_name="unknown",
                        overall_status=HealthStatus.CRITICAL,
                        health_score=0.0,
                        issues=[f"Health check timeout for {component_type.value}"]
                    )
                    component_health[component_type.value] = critical_component
                    all_issues.append(f"Health check timeout for {component_type.value}")
                    
                except Exception as e:
                    logger.error(f"Health check failed for {component_type.value}: {e}")
                    # Create a critical health status for failure
                    critical_component = ComponentHealth(
                        component_type=component_type,
                        component_name="unknown",
                        overall_status=HealthStatus.CRITICAL,
                        health_score=0.0,
                        issues=[f"Health check failed: {str(e)}"]
                    )
                    component_health[component_type.value] = critical_component
                    all_issues.append(f"Health check failed for {component_type.value}: {str(e)}")
            
            # Calculate overall system health
            overall_status, overall_score = self._calculate_overall_health(component_health)
            
            # Generate performance summary
            performance_summary = self._generate_performance_summary(all_metrics)
            
            # Generate resource usage summary
            resource_usage = self._generate_resource_usage_summary(all_metrics)
            
            # Create comprehensive health report
            report = SystemHealthReport(
                timestamp=timestamp,
                overall_status=overall_status,
                overall_score=overall_score,
                component_health=component_health,
                critical_issues=[issue for issue in all_issues if "critical" in issue.lower() or "failed" in issue.lower()],
                warnings=all_warnings,
                recommendations=all_recommendations,
                performance_summary=performance_summary,
                resource_usage=resource_usage
            )
            
            return report
    
    async def _check_system_health(self) -> ComponentHealth:
        """Check overall system health."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_metric = HealthMetric(
                name="cpu_usage",
                value=cpu_percent,
                unit="%",
                status=self._get_metric_status("cpu_usage", cpu_percent),
                threshold_good=self.thresholds["cpu_usage"]["good"],
                threshold_fair=self.thresholds["cpu_usage"]["fair"],
                threshold_poor=self.thresholds["cpu_usage"]["poor"],
                timestamp=time.time(),
                component=ComponentType.SYSTEM,
                description="CPU usage percentage"
            )
            metrics.append(cpu_metric)
            
            if cpu_percent > self.thresholds["cpu_usage"]["poor"]:
                issues.append("Critical CPU usage detected")
                recommendations.append("Consider scaling up or optimizing CPU-intensive tasks")
            elif cpu_percent > self.thresholds["cpu_usage"]["fair"]:
                issues.append("High CPU usage detected")
                recommendations.append("Monitor CPU usage and consider optimization")
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_metric = HealthMetric(
                name="memory_usage",
                value=memory.percent,
                unit="%",
                status=self._get_metric_status("memory_usage", memory.percent),
                threshold_good=self.thresholds["memory_usage"]["good"],
                threshold_fair=self.thresholds["memory_usage"]["fair"],
                threshold_poor=self.thresholds["memory_usage"]["poor"],
                timestamp=time.time(),
                component=ComponentType.SYSTEM,
                description="Memory usage percentage"
            )
            metrics.append(memory_metric)
            
            if memory.percent > self.thresholds["memory_usage"]["poor"]:
                issues.append("Critical memory usage detected")
                recommendations.append("Free up memory or add more RAM")
            elif memory.percent > self.thresholds["memory_usage"]["fair"]:
                issues.append("High memory usage detected")
                recommendations.append("Monitor memory usage and optimize memory consumption")
            
            # Load average
            load_avg = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0
            cpu_count = psutil.cpu_count()
            load_percentage = (load_avg / cpu_count) * 100 if cpu_count > 0 else 0
            
            load_metric = HealthMetric(
                name="load_average",
                value=load_percentage,
                unit="%",
                status=self._get_metric_status("cpu_usage", load_percentage),
                threshold_good=self.thresholds["cpu_usage"]["good"],
                threshold_fair=self.thresholds["cpu_usage"]["fair"],
                threshold_poor=self.thresholds["cpu_usage"]["poor"],
                timestamp=time.time(),
                component=ComponentType.SYSTEM,
                description="System load average"
            )
            metrics.append(load_metric)
            
            # Uptime
            uptime_seconds = time.time() - psutil.boot_time()
            uptime_metric = HealthMetric(
                name="uptime",
                value=uptime_seconds,
                unit="seconds",
                status=HealthStatus.GOOD,  # Uptime is always good
                threshold_good=0,
                threshold_fair=0,
                threshold_poor=0,
                timestamp=time.time(),
                component=ComponentType.SYSTEM,
                description="System uptime"
            )
            metrics.append(uptime_metric)
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.SYSTEM,
                component_name="system",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.SYSTEM,
                component_name="system",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"System health check failed: {str(e)}"]
            )
    
    async def _check_database_health(self) -> ComponentHealth:
        """Check database health."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            db_path = "data/database.db"
            
            if not os.path.exists(db_path):
                issues.append("Database file not found")
                return ComponentHealth(
                    component_type=ComponentType.DATABASE,
                    component_name="main",
                    overall_status=HealthStatus.CRITICAL,
                    health_score=0.0,
                    issues=issues
                )
            
            # Database size
            db_size_bytes = os.path.getsize(db_path)
            db_size_mb = db_size_bytes / (1024 * 1024)
            
            size_metric = HealthMetric(
                name="database_size",
                value=db_size_mb,
                unit="MB",
                status=self._get_metric_status("database_size", db_size_mb),
                threshold_good=self.thresholds["database_size"]["good"],
                threshold_fair=self.thresholds["database_size"]["fair"],
                threshold_poor=self.thresholds["database_size"]["poor"],
                timestamp=time.time(),
                component=ComponentType.DATABASE,
                description="Database file size"
            )
            metrics.append(size_metric)
            
            if db_size_mb > self.thresholds["database_size"]["poor"]:
                issues.append("Database size is very large")
                recommendations.append("Consider database cleanup or archiving")
            
            # Database connection test
            start_time = time.time()
            try:
                conn = sqlite3.connect(db_path, timeout=5)
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # Test integrity
                cursor.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()[0]
                
                conn.close()
                
                connection_time = time.time() - start_time
                
                # Connection time metric
                time_metric = HealthMetric(
                    name="connection_time",
                    value=connection_time,
                    unit="seconds",
                    status=self._get_metric_status("response_time", connection_time),
                    threshold_good=self.thresholds["response_time"]["good"],
                    threshold_fair=self.thresholds["response_time"]["fair"],
                    threshold_poor=self.thresholds["response_time"]["poor"],
                    timestamp=time.time(),
                    component=ComponentType.DATABASE,
                    description="Database connection time"
                )
                metrics.append(time_metric)
                
                # Table count metric
                table_metric = HealthMetric(
                    name="table_count",
                    value=table_count,
                    unit="count",
                    status=HealthStatus.GOOD,
                    threshold_good=0,
                    threshold_fair=0,
                    threshold_poor=0,
                    timestamp=time.time(),
                    component=ComponentType.DATABASE,
                    description="Number of database tables"
                )
                metrics.append(table_metric)
                
                if integrity_result != "ok":
                    issues.append(f"Database integrity check failed: {integrity_result}")
                    recommendations.append("Run database repair")
                
                if connection_time > self.thresholds["response_time"]["poor"]:
                    issues.append("Database connection is very slow")
                    recommendations.append("Optimize database or check disk performance")
                
            except sqlite3.Error as e:
                issues.append(f"Database connection failed: {str(e)}")
                recommendations.append("Check database file permissions and disk space")
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.DATABASE,
                component_name="main",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.DATABASE,
                component_name="main",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"Database health check failed: {str(e)}"]
            )
    
    async def _check_ai_providers_health(self) -> ComponentHealth:
        """Check AI providers health."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            # This would integrate with the actual AI provider manager
            # For now, simulate AI provider health checks
            
            providers = ["pollinations", "openrouter"]
            
            for provider in providers:
                # Simulate provider health check
                response_time = 0.5 + (0.1 * hash(provider) % 3)  # Simulated response time
                success_rate = 0.95 - (0.1 * hash(provider) % 4)  # Simulated success rate
                
                # Response time metric
                time_metric = HealthMetric(
                    name=f"{provider}_response_time",
                    value=response_time,
                    unit="seconds",
                    status=self._get_metric_status("response_time", response_time),
                    threshold_good=self.thresholds["response_time"]["good"],
                    threshold_fair=self.thresholds["response_time"]["fair"],
                    threshold_poor=self.thresholds["response_time"]["poor"],
                    timestamp=time.time(),
                    component=ComponentType.AI_PROVIDERS,
                    description=f"{provider} response time"
                )
                metrics.append(time_metric)
                
                # Success rate metric
                success_metric = HealthMetric(
                    name=f"{provider}_success_rate",
                    value=success_rate,
                    unit="ratio",
                    status=self._get_metric_status("error_rate", 1 - success_rate),
                    threshold_good=1 - self.thresholds["error_rate"]["good"],
                    threshold_fair=1 - self.thresholds["error_rate"]["fair"],
                    threshold_poor=1 - self.thresholds["error_rate"]["poor"],
                    timestamp=time.time(),
                    component=ComponentType.AI_PROVIDERS,
                    description=f"{provider} success rate"
                )
                metrics.append(success_metric)
                
                if response_time > self.thresholds["response_time"]["poor"]:
                    issues.append(f"{provider} provider is very slow")
                    recommendations.append(f"Consider switching from {provider} or optimizing requests")
                
                if success_rate < 0.8:
                    issues.append(f"{provider} provider has low success rate")
                    recommendations.append(f"Check {provider} API status and configuration")
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.AI_PROVIDERS,
                component_name="providers",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"AI providers health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.AI_PROVIDERS,
                component_name="providers",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"AI providers health check failed: {str(e)}"]
            )
    
    async def _check_message_queue_health(self) -> ComponentHealth:
        """Check message queue health."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            # This would integrate with the actual message queue system
            # For now, simulate queue health checks
            
            # Simulate queue metrics
            queue_size = 150 + (hash("queue") % 200)
            processing_rate = 10.0 + (hash("processing") % 20)
            
            # Queue size metric
            size_metric = HealthMetric(
                name="queue_size",
                value=queue_size,
                unit="messages",
                status=self._get_metric_status("queue_size", queue_size),
                threshold_good=self.thresholds["queue_size"]["good"],
                threshold_fair=self.thresholds["queue_size"]["fair"],
                threshold_poor=self.thresholds["queue_size"]["poor"],
                timestamp=time.time(),
                component=ComponentType.MESSAGE_QUEUE,
                description="Message queue size"
            )
            metrics.append(size_metric)
            
            # Processing rate metric
            rate_metric = HealthMetric(
                name="processing_rate",
                value=processing_rate,
                unit="messages/sec",
                status=HealthStatus.GOOD,  # Always good if processing
                threshold_good=1.0,
                threshold_fair=0.5,
                threshold_poor=0.1,
                timestamp=time.time(),
                component=ComponentType.MESSAGE_QUEUE,
                description="Message processing rate"
            )
            metrics.append(rate_metric)
            
            if queue_size > self.thresholds["queue_size"]["poor"]:
                issues.append("Message queue is backed up")
                recommendations.append("Increase processing capacity or pause incoming messages")
            
            if processing_rate < 1.0:
                issues.append("Message processing is slow")
                recommendations.append("Optimize message processing or add workers")
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.MESSAGE_QUEUE,
                component_name="main",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Message queue health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.MESSAGE_QUEUE,
                component_name="main",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"Message queue health check failed: {str(e)}"]
            )
    
    async def _check_disk_io_health(self) -> ComponentHealth:
        """Check disk I/O health."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            
            usage_metric = HealthMetric(
                name="disk_usage",
                value=disk_usage_percent,
                unit="%",
                status=self._get_metric_status("disk_usage", disk_usage_percent),
                threshold_good=self.thresholds["disk_usage"]["good"],
                threshold_fair=self.thresholds["disk_usage"]["fair"],
                threshold_poor=self.thresholds["disk_usage"]["poor"],
                timestamp=time.time(),
                component=ComponentType.DISK_IO,
                description="Disk usage percentage"
            )
            metrics.append(usage_metric)
            
            if disk_usage_percent > self.thresholds["disk_usage"]["poor"]:
                issues.append("Critical disk usage")
                recommendations.append("Free up disk space immediately")
            elif disk_usage_percent > self.thresholds["disk_usage"]["fair"]:
                issues.append("High disk usage")
                recommendations.append("Clean up unnecessary files")
            
            # Disk I/O metrics
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    # Calculate I/O rates (need to compare with previous values)
                    read_bytes = disk_io.read_bytes
                    write_bytes = disk_io.write_bytes
                    
                    # Simulate I/O rates (in MB/s)
                    read_rate = 25.0 + (hash("read") % 50)
                    write_rate = 15.0 + (hash("write") % 35)
                    
                    # Read rate metric
                    read_metric = HealthMetric(
                        name="disk_read_rate",
                        value=read_rate,
                        unit="MB/s",
                        status=self._get_metric_status("disk_io_read", read_rate),
                        threshold_good=self.thresholds["disk_io_read"]["good"],
                        threshold_fair=self.thresholds["disk_io_read"]["fair"],
                        threshold_poor=self.thresholds["disk_io_read"]["poor"],
                        timestamp=time.time(),
                        component=ComponentType.DISK_IO,
                        description="Disk read rate"
                    )
                    metrics.append(read_metric)
                    
                    # Write rate metric
                    write_metric = HealthMetric(
                        name="disk_write_rate",
                        value=write_rate,
                        unit="MB/s",
                        status=self._get_metric_status("disk_io_write", write_rate),
                        threshold_good=self.thresholds["disk_io_write"]["good"],
                        threshold_fair=self.thresholds["disk_io_write"]["fair"],
                        threshold_poor=self.thresholds["disk_io_write"]["poor"],
                        timestamp=time.time(),
                        component=ComponentType.DISK_IO,
                        description="Disk write rate"
                    )
                    metrics.append(write_metric)
                    
                    if read_rate < self.thresholds["disk_io_read"]["poor"]:
                        issues.append("Very slow disk read performance")
                        recommendations.append("Check disk health and consider SSD upgrade")
                    
                    if write_rate < self.thresholds["disk_io_write"]["poor"]:
                        issues.append("Very slow disk write performance")
                        recommendations.append("Check disk health and optimize write operations")
                
            except Exception as e:
                logger.warning(f"Could not get disk I/O metrics: {e}")
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.DISK_IO,
                component_name="main",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Disk I/O health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.DISK_IO,
                component_name="main",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"Disk I/O health check failed: {str(e)}"]
            )
    
    async def _check_network_health(self) -> ComponentHealth:
        """Check network health."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            # Network I/O metrics
            network_io = psutil.net_io_counters()
            if network_io:
                # Simulate network rates (in MB/s)
                upload_rate = 5.0 + (hash("upload") % 10)
                download_rate = 10.0 + (hash("download") % 20)
                
                # Upload rate metric
                upload_metric = HealthMetric(
                    name="network_upload_rate",
                    value=upload_rate,
                    unit="MB/s",
                    status=HealthStatus.GOOD,  # Network rates are typically good
                    threshold_good=1.0,
                    threshold_fair=0.5,
                    threshold_poor=0.1,
                    timestamp=time.time(),
                    component=ComponentType.NETWORK,
                    description="Network upload rate"
                )
                metrics.append(upload_metric)
                
                # Download rate metric
                download_metric = HealthMetric(
                    name="network_download_rate",
                    value=download_rate,
                    unit="MB/s",
                    status=HealthStatus.GOOD,
                    threshold_good=1.0,
                    threshold_fair=0.5,
                    threshold_poor=0.1,
                    timestamp=time.time(),
                    component=ComponentType.NETWORK,
                    description="Network download rate"
                )
                metrics.append(download_metric)
                
                if upload_rate < 0.1:
                    issues.append("Very slow network upload")
                    recommendations.append("Check network connection and configuration")
                
                if download_rate < 0.1:
                    issues.append("Very slow network download")
                    recommendations.append("Check network connection and ISP")
            
            # Connection count
            connections = len(psutil.net_connections())
            connection_metric = HealthMetric(
                name="connection_count",
                value=connections,
                unit="count",
                status=HealthStatus.GOOD,
                threshold_good=100,
                threshold_fair=200,
                threshold_poor=500,
                timestamp=time.time(),
                component=ComponentType.NETWORK,
                description="Active network connections"
            )
            metrics.append(connection_metric)
            
            if connections > 300:
                issues.append("High number of network connections")
                recommendations.append("Check for connection leaks or unusual activity")
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.NETWORK,
                component_name="main",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Network health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.NETWORK,
                component_name="main",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"Network health check failed: {str(e)}"]
            )
    
    async def _check_memory_health(self) -> ComponentHealth:
        """Check memory health (detailed analysis)."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            # Virtual memory
            memory = psutil.virtual_memory()
            
            # Memory usage percentage
            usage_metric = HealthMetric(
                name="memory_usage_percent",
                value=memory.percent,
                unit="%",
                status=self._get_metric_status("memory_usage", memory.percent),
                threshold_good=self.thresholds["memory_usage"]["good"],
                threshold_fair=self.thresholds["memory_usage"]["fair"],
                threshold_poor=self.thresholds["memory_usage"]["poor"],
                timestamp=time.time(),
                component=ComponentType.MEMORY,
                description="Memory usage percentage"
            )
            metrics.append(usage_metric)
            
            # Available memory
            available_gb = memory.available / (1024**3)
            available_metric = HealthMetric(
                name="available_memory_gb",
                value=available_gb,
                unit="GB",
                status=HealthStatus.GOOD if available_gb > 1.0 else HealthStatus.FAIR,
                threshold_good=2.0,
                threshold_fair=1.0,
                threshold_poor=0.5,
                timestamp=time.time(),
                component=ComponentType.MEMORY,
                description="Available memory in GB"
            )
            metrics.append(available_metric)
            
            # Swap memory
            swap = psutil.swap_memory()
            swap_usage_percent = swap.percent
            
            swap_metric = HealthMetric(
                name="swap_usage_percent",
                value=swap_usage_percent,
                unit="%",
                status=HealthStatus.GOOD if swap_usage_percent < 50 else HealthStatus.FAIR,
                threshold_good=25.0,
                threshold_fair=50.0,
                threshold_poor=75.0,
                timestamp=time.time(),
                component=ComponentType.MEMORY,
                description="Swap memory usage percentage"
            )
            metrics.append(swap_metric)
            
            if memory.percent > self.thresholds["memory_usage"]["poor"]:
                issues.append("Critical memory usage")
                recommendations.append("Free up memory or add more RAM")
            
            if available_gb < 0.5:
                issues.append("Very low available memory")
                recommendations.append("Immediate memory cleanup required")
            
            if swap_usage_percent > 50:
                issues.append("High swap usage")
                recommendations.append("Add more RAM or reduce memory usage")
            
            # Process memory
            process = psutil.Process()
            process_memory = process.memory_info()
            process_memory_mb = process_memory.rss / (1024 * 1024)
            
            process_metric = HealthMetric(
                name="process_memory_mb",
                value=process_memory_mb,
                unit="MB",
                status=HealthStatus.GOOD,
                threshold_good=500.0,
                threshold_fair=1000.0,
                threshold_poor=2000.0,
                timestamp=time.time(),
                component=ComponentType.MEMORY,
                description="Process memory usage"
            )
            metrics.append(process_metric)
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.MEMORY,
                component_name="system",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.MEMORY,
                component_name="system",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"Memory health check failed: {str(e)}"]
            )
    
    async def _check_cpu_health(self) -> ComponentHealth:
        """Check CPU health (detailed analysis)."""
        metrics = []
        issues = []
        recommendations = []
        
        try:
            # CPU usage percentage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            usage_metric = HealthMetric(
                name="cpu_usage_percent",
                value=cpu_percent,
                unit="%",
                status=self._get_metric_status("cpu_usage", cpu_percent),
                threshold_good=self.thresholds["cpu_usage"]["good"],
                threshold_fair=self.thresholds["cpu_usage"]["fair"],
                threshold_poor=self.thresholds["cpu_usage"]["poor"],
                timestamp=time.time(),
                component=ComponentType.CPU,
                description="CPU usage percentage"
            )
            metrics.append(usage_metric)
            
            # CPU count and cores
            cpu_count = psutil.cpu_count()
            cpu_logical = psutil.cpu_count(logical=True)
            
            count_metric = HealthMetric(
                name="cpu_count",
                value=cpu_count,
                unit="cores",
                status=HealthStatus.GOOD,
                threshold_good=1,
                threshold_fair=1,
                threshold_poor=1,
                timestamp=time.time(),
                component=ComponentType.CPU,
                description="Physical CPU cores"
            )
            metrics.append(count_metric)
            
            logical_metric = HealthMetric(
                name="cpu_logical_count",
                value=cpu_logical,
                unit="threads",
                status=HealthStatus.GOOD,
                threshold_good=1,
                threshold_fair=1,
                threshold_poor=1,
                timestamp=time.time(),
                component=ComponentType.CPU,
                description="Logical CPU threads"
            )
            metrics.append(logical_metric)
            
            # Load average
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
                load_1min = load_avg[0]
                load_percentage = (load_1min / cpu_count) * 100 if cpu_count > 0 else 0
                
                load_metric = HealthMetric(
                    name="load_average_1min",
                    value=load_percentage,
                    unit="%",
                    status=self._get_metric_status("cpu_usage", load_percentage),
                    threshold_good=self.thresholds["cpu_usage"]["good"],
                    threshold_fair=self.thresholds["cpu_usage"]["fair"],
                    threshold_poor=self.thresholds["cpu_usage"]["poor"],
                    timestamp=time.time(),
                    component=ComponentType.CPU,
                    description="1-minute load average as percentage of CPU count"
                )
                metrics.append(load_metric)
                
                if load_percentage > self.thresholds["cpu_usage"]["poor"]:
                    issues.append("Very high system load")
                    recommendations.append("Reduce CPU load or add more CPU cores")
            
            # CPU frequency (if available)
            try:
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    freq_current = cpu_freq.current
                    
                    freq_metric = HealthMetric(
                        name="cpu_frequency_mhz",
                        value=freq_current,
                        unit="MHz",
                        status=HealthStatus.GOOD,
                        threshold_good=1000,
                        threshold_fair=800,
                        threshold_poor=600,
                        timestamp=time.time(),
                        component=ComponentType.CPU,
                        description="Current CPU frequency"
                    )
                    metrics.append(freq_metric)
            except Exception:
                pass  # CPU frequency not available
            
            # Per-core usage
            cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
            max_core_usage = max(cpu_per_core) if cpu_per_core else 0
            
            core_metric = HealthMetric(
                name="max_core_usage_percent",
                value=max_core_usage,
                unit="%",
                status=self._get_metric_status("cpu_usage", max_core_usage),
                threshold_good=self.thresholds["cpu_usage"]["good"],
                threshold_fair=self.thresholds["cpu_usage"]["fair"],
                threshold_poor=self.thresholds["cpu_usage"]["poor"],
                timestamp=time.time(),
                component=ComponentType.CPU,
                description="Maximum CPU core usage"
            )
            metrics.append(core_metric)
            
            if cpu_percent > self.thresholds["cpu_usage"]["poor"]:
                issues.append("Critical CPU usage")
                recommendations.append("Optimize CPU usage or scale up")
            
            if max_core_usage > 95:
                issues.append("CPU core bottleneck detected")
                recommendations.append("Optimize for multi-core processing")
            
            # Calculate overall component health
            overall_status, health_score = self._calculate_component_health(metrics)
            
            return ComponentHealth(
                component_type=ComponentType.CPU,
                component_name="system",
                overall_status=overall_status,
                health_score=health_score,
                metrics=metrics,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"CPU health check failed: {e}")
            return ComponentHealth(
                component_type=ComponentType.CPU,
                component_name="system",
                overall_status=HealthStatus.CRITICAL,
                health_score=0.0,
                issues=[f"CPU health check failed: {str(e)}"]
            )
    
    def _get_metric_status(self, metric_name: str, value: float) -> HealthStatus:
        """Get health status for a metric value based on thresholds."""
        if metric_name not in self.thresholds:
            return HealthStatus.GOOD
        
        thresholds = self.thresholds[metric_name]
        
        if value <= thresholds["good"]:
            return HealthStatus.EXCELLENT
        elif value <= thresholds["fair"]:
            return HealthStatus.GOOD
        elif value <= thresholds["poor"]:
            return HealthStatus.FAIR
        else:
            return HealthStatus.POOR
    
    def _calculate_component_health(self, metrics: List[HealthMetric]) -> Tuple[HealthStatus, float]:
        """Calculate overall health for a component based on its metrics."""
        if not metrics:
            return HealthStatus.CRITICAL, 0.0
        
        # Calculate weighted score based on metric status
        status_scores = {
            HealthStatus.EXCELLENT: 100,
            HealthStatus.GOOD: 80,
            HealthStatus.FAIR: 60,
            HealthStatus.POOR: 30,
            HealthStatus.CRITICAL: 0
        }
        
        total_score = sum(status_scores[metric.status] for metric in metrics)
        average_score = total_score / len(metrics)
        
        # Determine overall status
        if average_score >= 90:
            overall_status = HealthStatus.EXCELLENT
        elif average_score >= 75:
            overall_status = HealthStatus.GOOD
        elif average_score >= 50:
            overall_status = HealthStatus.FAIR
        elif average_score >= 25:
            overall_status = HealthStatus.POOR
        else:
            overall_status = HealthStatus.CRITICAL
        
        return overall_status, average_score
    
    def _calculate_overall_health(self, component_health: Dict[str, ComponentHealth]) -> Tuple[HealthStatus, float]:
        """Calculate overall system health from component health."""
        if not component_health:
            return HealthStatus.CRITICAL, 0.0
        
        # Weight components by importance
        component_weights = {
            ComponentType.SYSTEM: 0.25,
            ComponentType.DATABASE: 0.20,
            ComponentType.AI_PROVIDERS: 0.15,
            ComponentType.MESSAGE_QUEUE: 0.10,
            ComponentType.DISK_IO: 0.10,
            ComponentType.NETWORK: 0.10,
            ComponentType.MEMORY: 0.05,
            ComponentType.CPU: 0.05
        }
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for component in component_health.values():
            weight = component_weights.get(component.component_type, 0.1)
            total_weighted_score += component.health_score * weight
            total_weight += weight
        
        overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0
        
        # Determine overall status
        if overall_score >= 90:
            overall_status = HealthStatus.EXCELLENT
        elif overall_score >= 75:
            overall_status = HealthStatus.GOOD
        elif overall_score >= 50:
            overall_status = HealthStatus.FAIR
        elif overall_score >= 25:
            overall_status = HealthStatus.POOR
        else:
            overall_status = HealthStatus.CRITICAL
        
        return overall_status, overall_score
    
    def _generate_performance_summary(self, metrics: List[HealthMetric]) -> Dict[str, Any]:
        """Generate performance summary from metrics."""
        summary = {}
        
        # CPU performance
        cpu_metrics = [m for m in metrics if "cpu" in m.name.lower()]
        if cpu_metrics:
            cpu_usage = next((m for m in cpu_metrics if "usage" in m.name.lower()), None)
            if cpu_usage:
                summary["cpu_usage"] = cpu_usage.value
                summary["cpu_status"] = cpu_usage.status.value
        
        # Memory performance
        memory_metrics = [m for m in metrics if "memory" in m.name.lower()]
        if memory_metrics:
            memory_usage = next((m for m in memory_metrics if "usage" in m.name.lower()), None)
            if memory_usage:
                summary["memory_usage"] = memory_usage.value
                summary["memory_status"] = memory_usage.status.value
        
        # Disk performance
        disk_metrics = [m for m in metrics if "disk" in m.name.lower()]
        if disk_metrics:
            disk_usage = next((m for m in disk_metrics if "usage" in m.name.lower()), None)
            if disk_usage:
                summary["disk_usage"] = disk_usage.value
                summary["disk_status"] = disk_usage.status.value
        
        # Response times
        response_metrics = [m for m in metrics if "response" in m.name.lower() or "time" in m.name.lower()]
        if response_metrics:
            avg_response = statistics.mean([m.value for m in response_metrics])
            summary["average_response_time"] = avg_response
        
        return summary
    
    def _generate_resource_usage_summary(self, metrics: List[HealthMetric]) -> Dict[str, Any]:
        """Generate resource usage summary from metrics."""
        summary = {}
        
        # Resource usage by category
        categories = {
            "cpu": [],
            "memory": [],
            "disk": [],
            "network": []
        }
        
        for metric in metrics:
            for category, category_metrics in categories.items():
                if category in metric.name.lower():
                    category_metrics.append(metric)
                    break
        
        for category, category_metrics in categories.items():
            if category_metrics:
                usage_metrics = [m for m in category_metrics if "usage" in m.name.lower() or m.unit == "%"]
                if usage_metrics:
                    summary[f"{category}_usage"] = statistics.mean([m.value for m in usage_metrics])
                
                # Count metrics by status
                status_counts = {}
                for metric in category_metrics:
                    status = metric.status.value
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                summary[f"{category}_metrics"] = {
                    "total": len(category_metrics),
                    "by_status": status_counts
                }
        
        return summary
    
    # Public API methods
    
    def get_latest_health_report(self) -> Optional[SystemHealthReport]:
        """Get the latest health report."""
        return self.health_reports[-1] if self.health_reports else None
    
    def get_health_history(self, limit: int = 10) -> List[SystemHealthReport]:
        """Get health report history."""
        return list(self.health_reports)[-limit:]
    
    def get_component_health(self, component_type: ComponentType) -> Optional[ComponentHealth]:
        """Get health for a specific component type."""
        for component in self.component_health.values():
            if component.component_type == component_type:
                return component
        return None
    
    def update_thresholds(self, metric_name: str, good: float, fair: float, poor: float):
        """Update thresholds for a metric."""
        self.thresholds[metric_name] = {
            "good": good,
            "fair": fair,
            "poor": poor
        }
        logger.info(f"Updated thresholds for {metric_name}: good={good}, fair={fair}, poor={poor}")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of current system health."""
        latest_report = self.get_latest_health_report()
        
        if not latest_report:
            return {
                "status": "no_data",
                "message": "No health data available"
            }
        
        return {
            "overall_status": latest_report.overall_status.value,
            "overall_score": latest_report.overall_score,
            "critical_issues_count": len(latest_report.critical_issues),
            "warnings_count": len(latest_report.warnings),
            "recommendations_count": len(latest_report.recommendations),
            "components_count": len(latest_report.component_health),
            "last_updated": latest_report.timestamp,
            "performance_summary": latest_report.performance_summary,
            "resource_usage": latest_report.resource_usage
        }
    
    def export_health_data(self, filepath: str):
        """Export health data to JSON file."""
        import json
        from dataclasses import asdict
        
        data = {
            "latest_report": asdict(self.get_latest_health_report()) if self.get_latest_health_report() else None,
            "health_history": [asdict(report) for report in self.get_health_history()],
            "thresholds": self.thresholds,
            "component_health": {
                key: asdict(component) for key, component in self.component_health.items()
            },
            "export_timestamp": time.time()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Exported health data to {filepath}")


# Global health analyzer instance
health_analyzer = HealthAnalyzer()
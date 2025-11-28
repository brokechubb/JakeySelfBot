"""
Load shedding and resource management system for protecting the bot during overload conditions.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

try:
    import psutil
except ImportError:
    psutil = None

from utils.logging_config import get_logger

logger = get_logger(__name__)


class LoadLevel(Enum):
    """System load levels for load shedding decisions."""
    NORMAL = "normal"          # < 50% resource usage
    ELEVATED = "elevated"      # 50-70% resource usage
    HIGH = "high"             # 70-85% resource usage
    CRITICAL = "critical"      # 85-95% resource usage
    EMERGENCY = "emergency"    # > 95% resource usage


class SheddingStrategy(Enum):
    """Load shedding strategies."""
    CONSERVATIVE = "conservative"    # Shed only luxury features
    MODERATE = "moderate"           # Shed luxury + optional features
    AGGRESSIVE = "aggressive"       # Shed luxury + optional + some important
    EMERGENCY = "emergency"         # Shed everything except critical


@dataclass
class ResourceMetrics:
    """Current system resource metrics."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: float
    active_connections: int
    queue_size: int
    response_time_p95: float
    error_rate: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class LoadSheddingAction:
    """A load shedding action that was taken."""
    timestamp: float
    load_level: LoadLevel
    strategy: SheddingStrategy
    features_disabled: List[str]
    resources_freed: float
    reason: str
    effectiveness_score: float = 0.0


class LoadShedder:
    """
    Intelligent load shedding system that protects the bot during overload conditions
    by selectively disabling non-critical features.
    """
    
    def __init__(
        self,
        check_interval: float = 5.0,
        resource_window_minutes: int = 10,
        auto_shedding: bool = True,
        min_shedding_duration: float = 30.0
    ):
        """
        Initialize load shedder.
        
        Args:
            check_interval: Seconds between load checks
            resource_window_minutes: Time window for resource averaging
            auto_shedding: Whether to automatically shed load
            min_shedding_duration: Minimum time between shedding actions
        """
        self.check_interval = check_interval
        self.resource_window_minutes = resource_window_minutes
        self.auto_shedding = auto_shedding
        self.min_shedding_duration = min_shedding_duration
        
        # Resource monitoring
        self.resource_history: List[ResourceMetrics] = []
        self.max_history_size = int(resource_window_minutes * 60 / check_interval)
        
        # Load shedding state
        self.current_load_level = LoadLevel.NORMAL
        self.last_shedding_time = 0.0
        self.shedding_history: List[LoadSheddingAction] = []
        self.active_shedding: Set[str] = set()
        
        # Feature manager (initialized later)
        self.feature_manager = None
        
        # Monitoring
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Statistics
        self.total_shedding_events = 0
        self.total_features_disabled = 0
        self.total_resources_freed = 0.0
        
        # Custom resource monitors
        self.custom_monitors: Dict[str, Callable[[], float]] = {}
        
        logger.info(f"Load shedder initialized: interval={check_interval}s, auto={auto_shedding}")
    
    def _initialize_feature_manager(self):
        """Initialize feature manager reference."""
        if self.feature_manager is None:
            try:
                from .feature_manager import feature_manager, FeatureTier, FeatureStatus
                self.feature_manager = feature_manager
                self.FeatureTier = FeatureTier
                self.FeatureStatus = FeatureStatus
            except ImportError:
                logger.warning("Feature manager not available")
                self.feature_manager = None
                self.FeatureTier = None
                self.FeatureStatus = None
    
    def register_custom_monitor(self, name: str, monitor_func: Callable[[], float]):
        """Register a custom resource monitor."""
        self.custom_monitors[name] = monitor_func
        logger.info(f"Registered custom monitor '{name}'")
    
    async def start_monitoring(self):
        """Start continuous load monitoring."""
        if self._monitoring:
            logger.warning("Load monitoring is already running")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Load monitoring started")
    
    async def stop_monitoring(self):
        """Stop continuous load monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Load monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                await self._check_system_load()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in load monitoring loop: {e}")
                await asyncio.sleep(1)
    
    async def _check_system_load(self):
        """Check current system load and take action if needed."""
        metrics = await self._collect_resource_metrics()
        
        async with self._lock:
            # Update history
            self.resource_history.append(metrics)
            if len(self.resource_history) > self.max_history_size:
                self.resource_history = self.resource_history[-self.max_history_size:]
            
            # Determine load level
            old_load_level = self.current_load_level
            self.current_load_level = self._calculate_load_level(metrics)
            
            # Log level changes
            if old_load_level != self.current_load_level:
                logger.info(f"Load level changed: {old_load_level.value} -> {self.current_load_level.value}")
            
            # Auto-shedding if enabled
            if self.auto_shedding and self.current_load_level.value in ["high", "critical", "emergency"]:
                await self._consider_load_shedding()
    
    async def _collect_resource_metrics(self) -> ResourceMetrics:
        """Collect current system resource metrics."""
        try:
            # System metrics
            if psutil:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Network metrics
                network = psutil.net_io_counters()
                network_io = (network.bytes_sent + network.bytes_recv) / (1024 * 1024)  # MB
                
                # Connection metrics
                connections = len(psutil.net_connections())
            else:
                # Fallback values when psutil is not available
                cpu_percent = 0.0
                memory_percent = 0.0
                disk_percent = 0.0
                network_io = 0.0
                connections = 0
            
            # Custom monitors
            queue_size = 0
            response_time_p95 = 0.0
            error_rate = 0.0
            
            for name, monitor in self.custom_monitors.items():
                try:
                    value = monitor()
                    if "queue" in name.lower():
                        queue_size = max(queue_size, int(value))
                    elif "response" in name.lower() or "latency" in name.lower():
                        response_time_p95 = max(response_time_p95, float(value))
                    elif "error" in name.lower():
                        error_rate = max(error_rate, float(value))
                except Exception as e:
                    logger.warning(f"Custom monitor '{name}' failed: {e}")
            
            if psutil:
                return ResourceMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    disk_percent=disk.percent,
                    network_io=network_io,
                    active_connections=connections,
                    queue_size=queue_size,
                    response_time_p95=response_time_p95,
                    error_rate=error_rate
                )
            else:
                return ResourceMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    disk_percent=disk_percent,
                    network_io=network_io,
                    active_connections=connections,
                    queue_size=queue_size,
                    response_time_p95=response_time_p95,
                    error_rate=error_rate
                )
            
        except Exception as e:
            logger.error(f"Failed to collect resource metrics: {e}")
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                network_io=0.0,
                active_connections=0,
                queue_size=0,
                response_time_p95=0.0,
                error_rate=0.0
            )
    
    def _calculate_load_level(self, metrics: ResourceMetrics) -> LoadLevel:
        """Calculate current load level based on metrics."""
        # Calculate weighted load score
        load_score = (
            metrics.cpu_percent * 0.3 +
            metrics.memory_percent * 0.25 +
            metrics.disk_percent * 0.15 +
            min(metrics.queue_size / 100, 100) * 0.15 +  # Queue pressure
            min(metrics.error_rate * 100, 100) * 0.1 +   # Error pressure
            min(metrics.response_time_p95 / 10, 100) * 0.05  # Response time pressure
        )
        
        # Determine load level
        if load_score < 50:
            return LoadLevel.NORMAL
        elif load_score < 70:
            return LoadLevel.ELEVATED
        elif load_score < 85:
            return LoadLevel.HIGH
        elif load_score < 95:
            return LoadLevel.CRITICAL
        else:
            return LoadLevel.EMERGENCY
    
    async def _consider_load_shedding(self):
        """Consider whether to shed load based on current conditions."""
        current_time = time.time()
        
        # Check minimum duration between shedding actions
        if current_time - self.last_shedding_time < self.min_shedding_duration:
            return
        
        # Determine shedding strategy based on load level
        strategy = self._get_shedding_strategy()
        
        # Get candidates for shedding
        candidates = self._get_shedding_candidates(strategy)
        
        if not candidates:
            logger.info("No candidates available for load shedding")
            return
        
        # Calculate how many features to disable
        features_to_disable = self._select_features_to_disable(candidates, strategy)
        
        if features_to_disable:
            await self._execute_load_shedding(features_to_disable, strategy)
    
    def _get_shedding_strategy(self) -> SheddingStrategy:
        """Get appropriate shedding strategy based on current load level."""
        strategy_map = {
            LoadLevel.NORMAL: SheddingStrategy.CONSERVATIVE,
            LoadLevel.ELEVATED: SheddingStrategy.CONSERVATIVE,
            LoadLevel.HIGH: SheddingStrategy.MODERATE,
            LoadLevel.CRITICAL: SheddingStrategy.AGGRESSIVE,
            LoadLevel.EMERGENCY: SheddingStrategy.EMERGENCY
        }
        return strategy_map.get(self.current_load_level, SheddingStrategy.CONSERVATIVE)
    
    def _get_shedding_candidates(self, strategy: SheddingStrategy) -> List[str]:
        """Get features that can be shed based on strategy."""
        self._initialize_feature_manager()
        if not self.feature_manager or not self.FeatureTier or not self.FeatureStatus:
            return []
        
        # Get enabled features by tier based on strategy
        candidates = []
        
        if strategy in [SheddingStrategy.CONSERVATIVE, SheddingStrategy.MODERATE]:
            candidates.extend(self.feature_manager.get_features_by_tier(self.FeatureTier.LUXURY))
        
        if strategy in [SheddingStrategy.MODERATE, SheddingStrategy.AGGRESSIVE]:
            candidates.extend(self.feature_manager.get_features_by_tier(self.FeatureTier.OPTIONAL))
        
        if strategy == SheddingStrategy.AGGRESSIVE:
            # Only shed some important features, not all
            important_features = self.feature_manager.get_features_by_tier(self.FeatureTier.IMPORTANT)
            candidates.extend(important_features[:len(important_features) // 2])
        
        if strategy == SheddingStrategy.EMERGENCY:
            candidates.extend(self.feature_manager.get_features_by_tier(self.FeatureTier.IMPORTANT))
        
        # Filter to only enabled features that can be disabled
        enabled_candidates = []
        for feature_name in candidates:
            if feature_name in self.feature_manager.feature_states:
                state = self.feature_manager.feature_states[feature_name]
                if state.status == self.FeatureStatus.ENABLED:
                    can_disable, _ = self.feature_manager.can_disable_feature(feature_name)
                    if can_disable:
                        enabled_candidates.append(feature_name)
        
        return enabled_candidates
    
    def _select_features_to_disable(
        self, 
        candidates: List[str], 
        strategy: SheddingStrategy
    ) -> List[str]:
        """Select which features to disable based on resource impact."""
        if not candidates:
            return []
        
        self._initialize_feature_manager()
        if not self.feature_manager:
            return []
        
        # Calculate resource pressure
        current_metrics = self.resource_history[-1] if self.resource_history else None
        if not current_metrics:
            return []
        
        # Determine target reduction based on load level
        target_reduction = self._calculate_target_reduction(strategy)
        
        # Sort candidates by resource cost (highest first)
        candidate_costs = []
        for feature_name in candidates:
            config = self.feature_manager.features[feature_name]
            cost = config.resource_cost + config.network_cost
            candidate_costs.append((cost, feature_name))
        
        candidate_costs.sort(reverse=True)
        
        # Select features until target reduction is met
        selected_features = []
        total_reduction = 0.0
        
        for cost, feature_name in candidate_costs:
            if total_reduction >= target_reduction:
                break
            selected_features.append(feature_name)
            total_reduction += cost
        
        return selected_features
    
    def _calculate_target_reduction(self, strategy: SheddingStrategy) -> float:
        """Calculate target resource reduction based on strategy."""
        reduction_map = {
            SheddingStrategy.CONSERVATIVE: 0.1,   # 10% reduction
            SheddingStrategy.MODERATE: 0.25,     # 25% reduction
            SheddingStrategy.AGGRESSIVE: 0.5,    # 50% reduction
            SheddingStrategy.EMERGENCY: 0.8      # 80% reduction
        }
        return reduction_map.get(strategy, 0.1)
    
    async def _execute_load_shedding(self, features: List[str], strategy: SheddingStrategy):
        """Execute load shedding by disabling features."""
        self._initialize_feature_manager()
        if not self.feature_manager:
            return
        
        current_time = time.time()
        disabled_features = []
        resources_freed = 0.0
        
        for feature_name in features:
            try:
                # Disable the feature
                success = await self.feature_manager.disable_feature(
                    feature_name, 
                    f"Load shedding - {strategy.value}"
                )
                
                if success:
                    disabled_features.append(feature_name)
                    self.active_shedding.add(feature_name)
                    
                    # Calculate resources freed
                    config = self.feature_manager.features[feature_name]
                    resources_freed += config.resource_cost + config.network_cost
                    
                    logger.info(f"Load shedding disabled feature: {feature_name}")
                
            except Exception as e:
                logger.error(f"Failed to disable feature '{feature_name}' during load shedding: {e}")
        
        # Record the action
        if disabled_features:
            action = LoadSheddingAction(
                timestamp=current_time,
                load_level=self.current_load_level,
                strategy=strategy,
                features_disabled=disabled_features,
                resources_freed=resources_freed,
                reason=f"Automatic load shedding at {self.current_load_level.value} level"
            )
            
            self.shedding_history.append(action)
            self.last_shedding_time = current_time
            self.total_shedding_events += 1
            self.total_features_disabled += len(disabled_features)
            self.total_resources_freed += resources_freed
            
            logger.warning(f"Load shedding executed: disabled {len(disabled_features)} features, "
                         f"freed {resources_freed:.2f} resources")
    
    async def restore_features(self, max_features: Optional[int] = None) -> int:
        """
        Restore previously disabled features when conditions improve.
        
        Args:
            max_features: Maximum number of features to restore
            
        Returns:
            Number of features restored
        """
        self._initialize_feature_manager()
        if not self.feature_manager:
            return 0
        
        # Only restore if load level is normal or elevated
        if self.current_load_level not in [LoadLevel.NORMAL, LoadLevel.ELEVATED]:
            return 0
        
        # Get restoration candidates
        candidates = self.feature_manager.get_restoration_candidates()
        
        # Filter to only features disabled by load shedding
        shedding_candidates = [f for f in candidates if f in self.active_shedding]
        
        if not shedding_candidates:
            return 0
        
        # Limit number of features to restore
        if max_features:
            shedding_candidates = shedding_candidates[:max_features]
        
        restored_count = 0
        
        for feature_name in shedding_candidates:
            try:
                success = await self.feature_manager.enable_feature(
                    feature_name, 
                    "Load conditions improved"
                )
                
                if success:
                    self.active_shedding.discard(feature_name)
                    restored_count += 1
                    logger.info(f"Restored feature: {feature_name}")
                
            except Exception as e:
                logger.error(f"Failed to restore feature '{feature_name}': {e}")
        
        if restored_count > 0:
            logger.info(f"Restored {restored_count} features as load conditions improved")
        
        return restored_count
    
    def get_load_status(self) -> Dict[str, Any]:
        """Get comprehensive load shedding status."""
        current_metrics = self.resource_history[-1] if self.resource_history else None
        
        # Calculate averages over the window
        avg_metrics = {}
        if self.resource_history:
            avg_metrics = {
                "avg_cpu": sum(m.cpu_percent for m in self.resource_history) / len(self.resource_history),
                "avg_memory": sum(m.memory_percent for m in self.resource_history) / len(self.resource_history),
                "avg_disk": sum(m.disk_percent for m in self.resource_history) / len(self.resource_history),
                "avg_queue_size": sum(m.queue_size for m in self.resource_history) / len(self.resource_history),
                "avg_error_rate": sum(m.error_rate for m in self.resource_history) / len(self.resource_history),
                "avg_response_time": sum(m.response_time_p95 for m in self.resource_history) / len(self.resource_history)
            }
        
        return {
            "current_load_level": self.current_load_level.value,
            "monitoring_active": self._monitoring,
            "auto_shedding_enabled": self.auto_shedding,
            "active_shedding_count": len(self.active_shedding),
            "active_shedding_features": list(self.active_shedding),
            "current_metrics": {
                "cpu_percent": current_metrics.cpu_percent if current_metrics else 0,
                "memory_percent": current_metrics.memory_percent if current_metrics else 0,
                "disk_percent": current_metrics.disk_percent if current_metrics else 0,
                "queue_size": current_metrics.queue_size if current_metrics else 0,
                "error_rate": current_metrics.error_rate if current_metrics else 0,
                "response_time_p95": current_metrics.response_time_p95 if current_metrics else 0
            } if current_metrics else {},
            "average_metrics": avg_metrics,
            "statistics": {
                "total_shedding_events": self.total_shedding_events,
                "total_features_disabled": self.total_features_disabled,
                "total_resources_freed": self.total_resources_freed,
                "last_shedding_time": self.last_shedding_time,
                "shedding_history_count": len(self.shedding_history)
            },
            "recent_shedding_actions": [
                {
                    "timestamp": action.timestamp,
                    "load_level": action.load_level.value,
                    "strategy": action.strategy.value,
                    "features_disabled": len(action.features_disabled),
                    "resources_freed": action.resources_freed,
                    "reason": action.reason
                }
                for action in self.shedding_history[-10:]  # Last 10 actions
            ]
        }
    
    def force_load_shedding(self, strategy: SheddingStrategy) -> int:
        """
        Force immediate load shedding with specified strategy.
        
        Args:
            strategy: Shedding strategy to use
            
        Returns:
            Number of features disabled
        """
        candidates = self._get_shedding_candidates(strategy)
        features_to_disable = self._select_features_to_disable(candidates, strategy)
        
        if features_to_disable:
            # Run the shedding asynchronously
            asyncio.create_task(self._execute_load_shedding(features_to_disable, strategy))
            return len(features_to_disable)
        
        return 0
    
    def reset_statistics(self):
        """Reset all load shedding statistics."""
        self.total_shedding_events = 0
        self.total_features_disabled = 0
        self.total_resources_freed = 0.0
        self.shedding_history.clear()
        self.active_shedding.clear()
        self.last_shedding_time = 0.0
        logger.info("Load shedding statistics reset")


# Global load shedder instance
load_shedder = LoadShedder()
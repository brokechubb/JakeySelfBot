"""
Degradation state monitoring system for tracking and managing system degradation.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from utils.logging_config import get_logger

logger = get_logger(__name__)


class DegradationLevel(Enum):
    """System degradation levels."""
    NONE = "none"              # No degradation - full functionality
    MINIMAL = "minimal"        # Minor degradation - luxury features disabled
    MODERATE = "moderate"      # Moderate degradation - optional features disabled
    SEVERE = "severe"          # Severe degradation - important features disabled
    CRITICAL = "critical"      # Critical degradation - only core features


class RecoveryStatus(Enum):
    """Recovery status tracking."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    STALLED = "stalled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DegradationEvent:
    """A degradation event that occurred."""
    timestamp: float
    level: DegradationLevel
    trigger_reason: str
    features_disabled: List[str]
    system_load: Dict[str, float]
    user_impact_score: float
    recovery_status: RecoveryStatus = RecoveryStatus.NOT_STARTED
    recovery_start_time: Optional[float] = None
    recovery_completion_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryMetrics:
    """Metrics for recovery progress."""
    start_time: float
    target_level: DegradationLevel
    current_level: DegradationLevel
    features_restored: int
    total_features_to_restore: int
    estimated_completion_time: Optional[float]
    progress_percentage: float
    obstacles: List[str] = field(default_factory=list)


class DegradationMonitor:
    """
    Monitors system degradation state and manages recovery processes.
    """
    
    def __init__(
        self,
        check_interval: float = 10.0,
        recovery_check_interval: float = 30.0,
        degradation_threshold: float = 0.7,
        recovery_threshold: float = 0.3
    ):
        """
        Initialize degradation monitor.
        
        Args:
            check_interval: Seconds between degradation checks
            recovery_check_interval: Seconds between recovery checks
            degradation_threshold: Load level that triggers degradation
            recovery_threshold: Load level that allows recovery
        """
        self.check_interval = check_interval
        self.recovery_check_interval = recovery_check_interval
        self.degradation_threshold = degradation_threshold
        self.recovery_threshold = recovery_threshold
        
        # State tracking
        self.current_level = DegradationLevel.NONE
        self.previous_level = DegradationLevel.NONE
        self.degradation_history: List[DegradationEvent] = []
        self.active_recovery: Optional[RecoveryMetrics] = None
        
        # Component references (initialized later)
        self.feature_manager = None
        self.load_shedder = None
        
        # Monitoring
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Statistics
        self.total_degradation_events = 0
        self.total_recovery_events = 0
        self.total_degradation_time = 0.0
        self.last_degradation_time = 0.0
        
        # Custom monitors
        self.degradation_monitors: List[Callable[[], float]] = []
        self.recovery_monitors: List[Callable[[], bool]] = []
        
        logger.info(f"Degradation monitor initialized: check_interval={check_interval}s")
    
    def _initialize_components(self):
        """Initialize component references."""
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
        
        if self.load_shedder is None:
            try:
                from .load_shedder import load_shedder
                self.load_shedder = load_shedder
            except ImportError:
                logger.warning("Load shedder not available")
                self.load_shedder = None
    
    def register_degradation_monitor(self, monitor_func: Callable[[], float]):
        """Register a custom degradation monitor (returns 0-1 degradation score)."""
        self.degradation_monitors.append(monitor_func)
        logger.info("Registered custom degradation monitor")
    
    def register_recovery_monitor(self, monitor_func: Callable[[], bool]):
        """Register a custom recovery monitor (returns True if recovery is possible)."""
        self.recovery_monitors.append(monitor_func)
        logger.info("Registered custom recovery monitor")
    
    async def start_monitoring(self):
        """Start continuous degradation monitoring."""
        if self._monitoring:
            logger.warning("Degradation monitoring is already running")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Degradation monitoring started")
    
    async def stop_monitoring(self):
        """Stop continuous degradation monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Degradation monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                await self._check_degradation_level()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in degradation monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _check_degradation_level(self):
        """Check current degradation level and take action if needed."""
        self._initialize_components()
        
        degradation_score = await self._calculate_degradation_score()
        new_level = self._determine_degradation_level(degradation_score)
        
        async with self._lock:
            old_level = self.current_level
            
            if new_level != old_level:
                await self._handle_level_change(old_level, new_level, degradation_score)
    
    async def _calculate_degradation_score(self) -> float:
        """Calculate overall degradation score (0-1)."""
        scores = []
        
        # Load shedder contribution
        if self.load_shedder:
            load_status = self.load_shedder.get_load_status()
            current_metrics = load_status.get("current_metrics", {})
            
            # High resource usage contributes to degradation
            load_score = max(
                current_metrics.get("cpu_percent", 0) / 100,
                current_metrics.get("memory_percent", 0) / 100,
                current_metrics.get("error_rate", 0) * 10,  # Error rate weighted heavily
                current_metrics.get("response_time_p95", 0) / 10
            )
            scores.append(load_score)
        
        # Feature manager contribution
        if self.feature_manager:
            feature_status = self.feature_manager.get_all_features_status()
            total_features = feature_status.get("total_features", 1)
            disabled_features = feature_status.get("disabled_features", 0)
            
            # High percentage of disabled features indicates degradation
            feature_score = disabled_features / total_features
            scores.append(feature_score)
        
        # Custom monitors
        for monitor in self.degradation_monitors:
            try:
                score = monitor()
                scores.append(max(0, min(1, score)))  # Clamp to 0-1
            except Exception as e:
                logger.warning(f"Custom degradation monitor failed: {e}")
        
        # Return maximum score (worst case)
        return max(scores) if scores else 0.0
    
    def _determine_degradation_level(self, score: float) -> DegradationLevel:
        """Determine degradation level from score."""
        if score < 0.1:
            return DegradationLevel.NONE
        elif score < 0.3:
            return DegradationLevel.MINIMAL
        elif score < 0.5:
            return DegradationLevel.MODERATE
        elif score < 0.8:
            return DegradationLevel.SEVERE
        else:
            return DegradationLevel.CRITICAL
    
    async def _handle_level_change(self, old_level: DegradationLevel, new_level: DegradationLevel, score: float):
        """Handle degradation level changes."""
        self.previous_level = old_level
        self.current_level = new_level
        
        if new_level.value in ["minimal", "moderate", "severe", "critical"]:
            # Degradation occurred
            await self._handle_degradation(old_level, new_level, score)
        elif new_level == DegradationLevel.NONE and old_level != DegradationLevel.NONE:
            # Recovery started
            await self._handle_recovery_start(old_level)
        
        logger.info(f"Degradation level changed: {old_level.value} -> {new_level.value} (score: {score:.3f})")
    
    async def _handle_degradation(self, old_level: DegradationLevel, new_level: DegradationLevel, score: float):
        """Handle degradation event."""
        self._initialize_components()
        
        # Get currently disabled features
        disabled_features = []
        if self.feature_manager:
            disabled_features = self.feature_manager.get_disabled_features()
        
        # Calculate user impact
        user_impact_score = self._calculate_user_impact(new_level, disabled_features)
        
        # Create degradation event
        event = DegradationEvent(
            timestamp=time.time(),
            level=new_level,
            trigger_reason=f"Degradation score {score:.3f} exceeded threshold",
            features_disabled=disabled_features.copy(),
            system_load=self._get_current_load_metrics(),
            user_impact_score=user_impact_score
        )
        
        self.degradation_history.append(event)
        self.total_degradation_events += 1
        self.last_degradation_time = event.timestamp
        
        # Start recovery monitoring if not already running
        if not self._recovery_task or self._recovery_task.done():
            self._recovery_task = asyncio.create_task(self._recovery_monitor_loop())
    
    async def _handle_recovery_start(self, from_level: DegradationLevel):
        """Handle the start of recovery process."""
        # Find the most recent degradation event
        if self.degradation_history:
            last_event = self.degradation_history[-1]
            if last_event.recovery_status == RecoveryStatus.NOT_STARTED:
                last_event.recovery_status = RecoveryStatus.IN_PROGRESS
                last_event.recovery_start_time = time.time()
                
                # Create recovery metrics
                self.active_recovery = RecoveryMetrics(
                    start_time=time.time(),
                    target_level=DegradationLevel.NONE,
                    current_level=from_level,
                    features_restored=0,
                    total_features_to_restore=len(last_event.features_disabled),
                    estimated_completion_time=None,
                    progress_percentage=0.0
                )
                
                self.total_recovery_events += 1
                logger.info(f"Recovery started from {from_level.value} degradation")
    
    async def _recovery_monitor_loop(self):
        """Monitor recovery progress."""
        while self._monitoring and self.current_level != DegradationLevel.NONE:
            try:
                await self._check_recovery_progress()
                await asyncio.sleep(self.recovery_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in recovery monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def _check_recovery_progress(self):
        """Check and update recovery progress."""
        if not self.active_recovery:
            return
        
        self._initialize_components()
        
        # Check if recovery is possible
        can_recover = True
        for monitor in self.recovery_monitors:
            try:
                if not monitor():
                    can_recover = False
                    break
            except Exception as e:
                logger.warning(f"Recovery monitor failed: {e}")
        
        if not can_recover:
            if self.active_recovery:
                self.active_recovery.obstacles.append("Recovery conditions not met")
            return
        
        # Try to restore features
        restored_count = 0
        if self.load_shedder:
            restored_count = await self.load_shedder.restore_features(max_features=5)
        
        if self.active_recovery:
            self.active_recovery.features_restored += restored_count
            self.active_recovery.progress_percentage = (
                self.active_recovery.features_restored / 
                max(1, self.active_recovery.total_features_to_restore) * 100
            )
            
            # Update current degradation level
            current_score = await self._calculate_degradation_score()
            self.active_recovery.current_level = self._determine_degradation_level(current_score)
            
            # Check if recovery is complete
            if self.current_level == DegradationLevel.NONE:
                await self._complete_recovery()
    
    async def _complete_recovery(self):
        """Complete the recovery process."""
        if self.degradation_history:
            last_event = self.degradation_history[-1]
            last_event.recovery_status = RecoveryStatus.COMPLETED
            last_event.recovery_completion_time = time.time()
            
            # Calculate total degradation time
            if last_event.recovery_start_time:
                degradation_time = last_event.recovery_completion_time - last_event.recovery_start_time
                self.total_degradation_time += degradation_time
                logger.info(f"Recovery completed in {degradation_time:.1f} seconds")
        
        self.active_recovery = None
    
    def _calculate_user_impact(self, level: DegradationLevel, disabled_features: List[str]) -> float:
        """Calculate user impact score (0-1)."""
        # Base impact by level
        level_impact = {
            DegradationLevel.NONE: 0.0,
            DegradationLevel.MINIMAL: 0.1,
            DegradationLevel.MODERATE: 0.3,
            DegradationLevel.SEVERE: 0.6,
            DegradationLevel.CRITICAL: 0.9
        }
        
        base_impact = level_impact.get(level, 0.0)
        
        # Additional impact based on feature importance
        if self.feature_manager and self.FeatureTier:
            critical_disabled = any(
                self.feature_manager.features.get(f, {}).get("tier") == self.FeatureTier.CRITICAL
                for f in disabled_features
            )
            important_disabled = any(
                self.feature_manager.features.get(f, {}).get("tier") == self.FeatureTier.IMPORTANT
                for f in disabled_features
            )
            
            if critical_disabled:
                base_impact = min(1.0, base_impact + 0.3)
            elif important_disabled:
                base_impact = min(1.0, base_impact + 0.2)
        
        return base_impact
    
    def _get_current_load_metrics(self) -> Dict[str, float]:
        """Get current system load metrics."""
        metrics = {}
        
        if self.load_shedder:
            load_status = self.load_shedder.get_load_status()
            current = load_status.get("current_metrics", {})
            metrics.update({
                "cpu_percent": current.get("cpu_percent", 0),
                "memory_percent": current.get("memory_percent", 0),
                "error_rate": current.get("error_rate", 0),
                "response_time": current.get("response_time_p95", 0)
            })
        
        return metrics
    
    def get_degradation_status(self) -> Dict[str, Any]:
        """Get comprehensive degradation status."""
        # Calculate uptime percentage
        total_time = time.time() - (self.degradation_history[0].timestamp if self.degradation_history else time.time())
        degradation_time = self.total_degradation_time
        if self.current_level != DegradationLevel.NONE and self.last_degradation_time > 0:
            degradation_time += time.time() - self.last_degradation_time
        
        uptime_percentage = max(0, (total_time - degradation_time) / max(1, total_time)) * 100
        
        return {
            "current_level": self.current_level.value,
            "previous_level": self.previous_level.value,
            "monitoring_active": self._monitoring,
            "uptime_percentage": uptime_percentage,
            "statistics": {
                "total_degradation_events": self.total_degradation_events,
                "total_recovery_events": self.total_recovery_events,
                "total_degradation_time": self.total_degradation_time,
                "last_degradation_time": self.last_degradation_time
            },
            "active_recovery": {
                "status": self.active_recovery.recovery_status.value if self.active_recovery else None,
                "progress_percentage": self.active_recovery.progress_percentage if self.active_recovery else 0,
                "features_restored": self.active_recovery.features_restored if self.active_recovery else 0,
                "total_features_to_restore": self.active_recovery.total_features_to_restore if self.active_recovery else 0,
                "obstacles": self.active_recovery.obstacles if self.active_recovery else []
            } if self.active_recovery else None,
            "recent_events": [
                {
                    "timestamp": event.timestamp,
                    "level": event.level.value,
                    "trigger_reason": event.trigger_reason,
                    "features_disabled": len(event.features_disabled),
                    "user_impact_score": event.user_impact_score,
                    "recovery_status": event.recovery_status.value,
                    "duration": (event.recovery_completion_time or time.time()) - event.timestamp
                }
                for event in self.degradation_history[-10:]  # Last 10 events
            ]
        }
    
    def force_degradation_check(self) -> Dict[str, Any]:
        """Force an immediate degradation check."""
        current_score = asyncio.run(self._calculate_degradation_score())
        new_level = self._determine_degradation_level(current_score)
        
        return {
            "current_score": current_score,
            "current_level": new_level.value,
            "previous_level": self.current_level.value,
            "recommendations": self._get_degradation_recommendations(new_level)
        }
    
    def _get_degradation_recommendations(self, level: DegradationLevel) -> List[str]:
        """Get recommendations for handling degradation."""
        recommendations = []
        
        if level == DegradationLevel.NONE:
            recommendations.append("System operating normally")
        elif level == DegradationLevel.MINIMAL:
            recommendations.append("Monitor system load closely")
            recommendations.append("Consider disabling luxury features if load increases")
        elif level == DegradationLevel.MODERATE:
            recommendations.append("Disable optional features to reduce load")
            recommendations.append("Increase monitoring frequency")
        elif level == DegradationLevel.SEVERE:
            recommendations.append("Disable non-essential important features")
            recommendations.append("Alert administrators")
            recommendations.append("Prepare for potential service disruption")
        elif level == DegradationLevel.CRITICAL:
            recommendations.append("Emergency mode - disable all non-critical features")
            recommendations.append("Immediate administrator attention required")
            recommendations.append("Consider service restart if conditions don't improve")
        
        return recommendations
    
    def reset_statistics(self):
        """Reset all degradation monitoring statistics."""
        self.total_degradation_events = 0
        self.total_recovery_events = 0
        self.total_degradation_time = 0.0
        self.last_degradation_time = 0.0
        self.degradation_history.clear()
        self.active_recovery = None
        logger.info("Degradation monitoring statistics reset")


# Global degradation monitor instance
degradation_monitor = DegradationMonitor()
"""
Feature tier management system for graceful degradation.
Organizes features by importance and manages their availability during system stress.
"""
import asyncio
import time
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from utils.logging_config import get_logger

logger = get_logger(__name__)


class FeatureTier(Enum):
    """Feature importance tiers for degradation decisions."""
    CRITICAL = "critical"      # Core bot functionality - never disable
    IMPORTANT = "important"    # Important features - disable last
    OPTIONAL = "optional"      # Nice-to-have features - disable first
    LUXURY = "luxury"          # Extra features - disable immediately


class FeatureStatus(Enum):
    """Current status of a feature."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


@dataclass
class FeatureConfig:
    """Configuration for a feature in the degradation system."""
    name: str
    tier: FeatureTier
    description: str
    dependencies: List[str] = field(default_factory=list)
    resource_cost: float = 1.0  # CPU/memory cost multiplier
    network_cost: float = 1.0   # Network usage cost multiplier
    enable_func: Optional[Callable] = None
    disable_func: Optional[Callable] = None
    status_check_func: Optional[Callable] = None
    fallback_func: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureState:
    """Current state of a feature."""
    name: str
    status: FeatureStatus
    tier: FeatureTier
    last_status_change: float
    disable_count: int = 0
    enable_count: int = 0
    total_disable_time: float = 0.0
    last_disable_reason: Optional[str] = None
    performance_impact: float = 0.0
    user_impact_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeatureManager:
    """
    Manages feature tiers and handles graceful enabling/disabling of features
    based on system conditions and degradation levels.
    """
    
    def __init__(self):
        """Initialize the feature manager."""
        self.features: Dict[str, FeatureConfig] = {}
        self.feature_states: Dict[str, FeatureState] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.reverse_dependency_graph: Dict[str, Set[str]] = {}
        
        # Feature groups for batch operations
        self.feature_groups: Dict[str, List[str]] = {}
        
        # Statistics
        self.total_disables = 0
        self.total_enables = 0
        self.degradation_events = 0
        
        logger.info("Feature manager initialized")
    
    def register_feature(self, config: FeatureConfig):
        """
        Register a feature with the degradation system.
        
        Args:
            config: Feature configuration
        """
        self.features[config.name] = config
        
        # Initialize feature state
        self.feature_states[config.name] = FeatureState(
            name=config.name,
            status=FeatureStatus.ENABLED,
            tier=config.tier,
            last_status_change=time.time()
        )
        
        # Build dependency graphs
        self.dependency_graph[config.name] = set(config.dependencies)
        for dep in config.dependencies:
            if dep not in self.reverse_dependency_graph:
                self.reverse_dependency_graph[dep] = set()
            self.reverse_dependency_graph[dep].add(config.name)
        
        logger.info(f"Registered feature '{config.name}' in tier {config.tier.value}")
    
    def unregister_feature(self, feature_name: str):
        """Unregister a feature from the degradation system."""
        if feature_name in self.features:
            config = self.features[feature_name]
            
            # Remove from dependency graphs
            for dep in config.dependencies:
                if dep in self.reverse_dependency_graph:
                    self.reverse_dependency_graph[dep].discard(feature_name)
            
            del self.dependency_graph[feature_name]
            if feature_name in self.reverse_dependency_graph:
                del self.reverse_dependency_graph[feature_name]
            
            del self.features[feature_name]
            del self.feature_states[feature_name]
            
            logger.info(f"Unregistered feature '{feature_name}'")
    
    def create_feature_group(self, group_name: str, feature_names: List[str]):
        """Create a group of related features for batch operations."""
        valid_features = [name for name in feature_names if name in self.features]
        self.feature_groups[group_name] = valid_features
        logger.info(f"Created feature group '{group_name}' with {len(valid_features)} features")
    
    def get_features_by_tier(self, tier: FeatureTier) -> List[str]:
        """Get all features in a specific tier."""
        return [name for name, config in self.features.items() if config.tier == tier]
    
    def get_enabled_features(self) -> List[str]:
        """Get all currently enabled features."""
        return [
            name for name, state in self.feature_states.items()
            if state.status == FeatureStatus.ENABLED
        ]
    
    def get_disabled_features(self) -> List[str]:
        """Get all currently disabled features."""
        return [
            name for name, state in self.feature_states.items()
            if state.status == FeatureStatus.DISABLED
        ]
    
    def can_disable_feature(self, feature_name: str) -> tuple[bool, List[str]]:
        """
        Check if a feature can be disabled based on dependencies.
        
        Returns:
            Tuple of (can_disable, blocking_features)
        """
        if feature_name not in self.features:
            return False, []
        
        # Check if any enabled features depend on this one
        blocking_features = []
        if feature_name in self.reverse_dependency_graph:
            for dependent in self.reverse_dependency_graph[feature_name]:
                if (dependent in self.feature_states and 
                    self.feature_states[dependent].status == FeatureStatus.ENABLED):
                    blocking_features.append(dependent)
        
        can_disable = len(blocking_features) == 0
        return can_disable, blocking_features
    
    async def enable_feature(self, feature_name: str, reason: str = "Manual enable") -> bool:
        """
        Enable a feature and its dependencies if needed.
        
        Args:
            feature_name: Name of the feature to enable
            reason: Reason for enabling
            
        Returns:
            True if successful, False otherwise
        """
        if feature_name not in self.features:
            logger.warning(f"Feature '{feature_name}' not found")
            return False
        
        config = self.features[feature_name]
        state = self.feature_states[feature_name]
        
        if state.status == FeatureStatus.ENABLED:
            return True
        
        # Enable dependencies first
        for dep in config.dependencies:
            if not await self.enable_feature(dep, f"Dependency for {feature_name}"):
                logger.error(f"Failed to enable dependency '{dep}' for feature '{feature_name}'")
                return False
        
        # Call enable function if provided
        if config.enable_func:
            try:
                if asyncio.iscoroutinefunction(config.enable_func):
                    await config.enable_func()
                else:
                    config.enable_func()
            except Exception as e:
                logger.error(f"Enable function failed for feature '{feature_name}': {e}")
                return False
        
        # Update state
        old_status = state.status
        state.status = FeatureStatus.ENABLED
        state.last_status_change = time.time()
        state.enable_count += 1
        state.last_disable_reason = None
        
        self.total_enables += 1
        
        logger.info(f"Feature '{feature_name}' enabled ({reason}) - was {old_status.value}")
        return True
    
    async def disable_feature(self, feature_name: str, reason: str = "Manual disable") -> bool:
        """
        Disable a feature and features that depend on it.
        
        Args:
            feature_name: Name of the feature to disable
            reason: Reason for disabling
            
        Returns:
            True if successful, False otherwise
        """
        if feature_name not in self.features:
            logger.warning(f"Feature '{feature_name}' not found")
            return False
        
        config = self.features[feature_name]
        state = self.feature_states[feature_name]
        
        if state.status == FeatureStatus.DISABLED:
            return True
        
        # Never disable critical features unless explicitly forced
        if config.tier == FeatureTier.CRITICAL and "forced" not in reason.lower():
            logger.warning(f"Refusing to disable critical feature '{feature_name}'")
            return False
        
        # Disable dependent features first
        if feature_name in self.reverse_dependency_graph:
            for dependent in list(self.reverse_dependency_graph[feature_name]):
                await self.disable_feature(dependent, f"Dependency {feature_name} disabled")
        
        # Call disable function if provided
        if config.disable_func:
            try:
                if asyncio.iscoroutinefunction(config.disable_func):
                    await config.disable_func()
                else:
                    config.disable_func()
            except Exception as e:
                logger.error(f"Disable function failed for feature '{feature_name}': {e}")
                return False
        
        # Update state
        old_status = state.status
        state.status = FeatureStatus.DISABLED
        state.last_status_change = time.time()
        state.disable_count += 1
        state.last_disable_reason = reason
        
        self.total_disables += 1
        
        logger.info(f"Feature '{feature_name}' disabled ({reason}) - was {old_status.value}")
        return True
    
    async def enable_features_by_tier(self, tier: FeatureTier, reason: str = "Tier enable") -> int:
        """
        Enable all features in a specific tier.
        
        Returns:
            Number of features successfully enabled
        """
        features = self.get_features_by_tier(tier)
        success_count = 0
        
        for feature_name in features:
            if await self.enable_feature(feature_name, reason):
                success_count += 1
        
        logger.info(f"Enabled {success_count}/{len(features)} features in {tier.value} tier")
        return success_count
    
    async def disable_features_by_tier(self, tier: FeatureTier, reason: str = "Tier disable") -> int:
        """
        Disable all features in a specific tier.
        
        Returns:
            Number of features successfully disabled
        """
        features = self.get_features_by_tier(tier)
        success_count = 0
        
        for feature_name in features:
            if await self.disable_feature(feature_name, reason):
                success_count += 1
        
        logger.info(f"Disabled {success_count}/{len(features)} features in {tier.value} tier")
        return success_count
    
    def calculate_resource_usage(self) -> Dict[str, Any]:
        """Calculate total resource usage by enabled features."""
        total_cpu = 0.0
        total_network = 0.0
        tier_usage = {tier.value: {"cpu": 0.0, "network": 0.0} for tier in FeatureTier}
        
        for feature_name, state in self.feature_states.items():
            if state.status == FeatureStatus.ENABLED:
                config = self.features[feature_name]
                total_cpu += config.resource_cost
                total_network += config.network_cost
                
                tier_usage[config.tier.value]["cpu"] += config.resource_cost
                tier_usage[config.tier.value]["network"] += config.network_cost
        
        return {
            "total_cpu": total_cpu,
            "total_network": total_network,
            "by_tier": tier_usage
        }
    
    def get_feature_status(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific feature."""
        if feature_name not in self.features:
            return None
        
        config = self.features[feature_name]
        state = self.feature_states[feature_name]
        
        can_disable, blocking = self.can_disable_feature(feature_name)
        
        return {
            "name": feature_name,
            "tier": config.tier.value,
            "status": state.status.value,
            "description": config.description,
            "dependencies": config.dependencies,
            "resource_cost": config.resource_cost,
            "network_cost": config.network_cost,
            "can_disable": can_disable,
            "blocking_features": list(blocking),
            "disable_count": state.disable_count,
            "enable_count": state.enable_count,
            "total_disable_time": state.total_disable_time,
            "last_status_change": state.last_status_change,
            "last_disable_reason": state.last_disable_reason,
            "performance_impact": state.performance_impact,
            "user_impact_score": state.user_impact_score
        }
    
    def get_all_features_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all features."""
        resource_usage = self.calculate_resource_usage()
        
        tier_counts = {}
        for tier in FeatureTier:
            tier_features = self.get_features_by_tier(tier)
            enabled = sum(1 for f in tier_features if self.feature_states[f].status == FeatureStatus.ENABLED)
            tier_counts[tier.value] = {
                "total": len(tier_features),
                "enabled": enabled,
                "disabled": len(tier_features) - enabled
            }
        
        return {
            "total_features": len(self.features),
            "enabled_features": len(self.get_enabled_features()),
            "disabled_features": len(self.get_disabled_features()),
            "tier_counts": tier_counts,
            "resource_usage": resource_usage,
            "statistics": {
                "total_disables": self.total_disables,
                "total_enables": self.total_enables,
                "degradation_events": self.degradation_events
            },
            "features": {
                name: self.get_feature_status(name)
                for name in self.features.keys()
            }
        }
    
    async def health_check_all_features(self) -> Dict[str, bool]:
        """
        Perform health checks on all features that have status check functions.
        
        Returns:
            Dictionary mapping feature names to health status
        """
        health_results = {}
        
        for feature_name, config in self.features.items():
            if config.status_check_func:
                try:
                    if asyncio.iscoroutinefunction(config.status_check_func):
                        is_healthy = await config.status_check_func()
                    else:
                        is_healthy = config.status_check_func()
                    
                    health_results[feature_name] = bool(is_healthy)
                    
                    # Auto-disable unhealthy features
                    if not is_healthy and self.feature_states[feature_name].status == FeatureStatus.ENABLED:
                        await self.disable_feature(feature_name, "Health check failed")
                        
                except Exception as e:
                    logger.error(f"Health check failed for feature '{feature_name}': {e}")
                    health_results[feature_name] = False
        
        return health_results
    
    def get_degradation_candidates(self, resource_pressure: float = 0.5) -> List[str]:
        """
        Get features that can be disabled to reduce resource usage.
        
        Args:
            resource_pressure: 0-1 scale of resource pressure (higher = more pressure)
            
        Returns:
            Ordered list of features to disable (from least to most important)
        """
        candidates = []
        
        # Sort by tier priority and resource cost
        tier_priority = {
            FeatureTier.LUXURY: 0,
            FeatureTier.OPTIONAL: 1,
            FeatureTier.IMPORTANT: 2,
            FeatureTier.CRITICAL: 3
        }
        
        enabled_features = self.get_enabled_features()
        
        for feature_name in enabled_features:
            config = self.features[feature_name]
            state = self.feature_states[feature_name]
            
            # Skip critical features unless under extreme pressure
            if config.tier == FeatureTier.CRITICAL and resource_pressure < 0.9:
                continue
            
            can_disable, _ = self.can_disable_feature(feature_name)
            if not can_disable:
                continue
            
            # Calculate priority score (lower = better candidate for disabling)
            priority_score = (
                tier_priority[config.tier] * 1000 +
                config.resource_cost * 100 +
                state.user_impact_score * 10
            )
            
            candidates.append((priority_score, feature_name))
        
        # Sort by priority score (lower first)
        candidates.sort(key=lambda x: x[0])
        
        return [feature_name for _, feature_name in candidates]
    
    def get_restoration_candidates(self) -> List[str]:
        """
        Get features that can be safely re-enabled.
        
        Returns:
            Ordered list of features to enable (from most to least important)
        """
        candidates = []
        
        # Sort by tier priority
        tier_priority = {
            FeatureTier.CRITICAL: 0,
            FeatureTier.IMPORTANT: 1,
            FeatureTier.OPTIONAL: 2,
            FeatureTier.LUXURY: 3
        }
        
        disabled_features = self.get_disabled_features()
        
        for feature_name in disabled_features:
            config = self.features[feature_name]
            state = self.feature_states[feature_name]
            
            # Check if dependencies are available
            deps_available = all(
                dep in self.feature_states and 
                self.feature_states[dep].status == FeatureStatus.ENABLED
                for dep in config.dependencies
            )
            
            if not deps_available:
                continue
            
            # Calculate priority score (lower = better candidate for enabling)
            priority_score = (
                tier_priority[config.tier] * 1000 +
                state.user_impact_score * 10 -
                config.resource_cost * 1
            )
            
            candidates.append((priority_score, feature_name))
        
        # Sort by priority score (lower first)
        candidates.sort(key=lambda x: x[0])
        
        return [feature_name for _, feature_name in candidates]


# Global feature manager instance
feature_manager = FeatureManager()
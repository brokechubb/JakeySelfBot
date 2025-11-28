"""
Main graceful degradation orchestrator that coordinates all degradation components.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import logging

from utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SystemStatus:
    """Overall system status for user communication."""
    level: str
    message: str
    affected_features: List[str]
    estimated_recovery: Optional[float]
    user_actions: List[str]
    timestamp: float


class GracefulDegradationOrchestrator:
    """
    Main orchestrator for the graceful degradation system.
    Coordinates feature management, load shedding, and degradation monitoring.
    """
    
    def __init__(self):
        """Initialize the graceful degradation orchestrator."""
        # Component references
        self.feature_manager = None
        self.load_shedder = None
        self.degradation_monitor = None
        
        # Status communication
        self.status_messages: Dict[str, SystemStatus] = {}
        self.user_notification_callbacks: List[Callable[[SystemStatus], None]] = []
        
        # Configuration
        self.auto_start = True
        self.communication_enabled = True
        
        # State
        self._initialized = False
        self._running = False
        
        logger.info("Graceful degradation orchestrator initialized")
    
    async def initialize(self):
        """Initialize all components and start monitoring."""
        if self._initialized:
            return
        
        logger.info("Initializing graceful degradation system...")
        
        # Initialize components
        await self._initialize_components()
        
        # Register default features
        await self._register_default_features()
        
        # Start monitoring
        if self.auto_start:
            await self.start_monitoring()
        
        self._initialized = True
        logger.info("Graceful degradation system initialized successfully")
    
    async def _initialize_components(self):
        """Initialize all degradation components."""
        try:
            # Feature Manager
            from .feature_manager import feature_manager, FeatureTier, FeatureStatus
            self.feature_manager = feature_manager
            self.FeatureTier = FeatureTier
            self.FeatureStatus = FeatureStatus
            logger.info("Feature manager initialized")
        except ImportError as e:
            logger.error(f"Failed to initialize feature manager: {e}")
        
        try:
            # Load Shedder
            from .load_shedder import load_shedder
            self.load_shedder = load_shedder
            logger.info("Load shedder initialized")
        except ImportError as e:
            logger.error(f"Failed to initialize load shedder: {e}")
        
        try:
            # Degradation Monitor
            from .degradation_monitor import degradation_monitor
            self.degradation_monitor = degradation_monitor
            logger.info("Degradation monitor initialized")
        except ImportError as e:
            logger.error(f"Failed to initialize degradation monitor: {e}")
    
    async def _register_default_features(self):
        """Register default bot features with the degradation system."""
        if not self.feature_manager or not self.FeatureTier:
            return
        
        # Critical features - never disable
        critical_features = [
            ("message_handling", "Core Discord message processing"),
            ("database_access", "Database operations"),
            ("authentication", "User authentication"),
            ("error_handling", "Error handling and logging")
        ]
        
        for feature_name, description in critical_features:
            from .feature_manager import FeatureConfig
            config = FeatureConfig(
                name=feature_name,
                tier=self.FeatureTier.CRITICAL,
                description=description,
                resource_cost=2.0,
                network_cost=1.0
            )
            self.feature_manager.register_feature(config)
        
        # Important features - disable last
        important_features = [
            ("ai_chat", "AI chat functionality"),
            ("user_commands", "User command processing"),
            ("memory_system", "Memory and context system"),
            ("rate_limiting", "Rate limiting and protection")
        ]
        
        for feature_name, description in important_features:
            from .feature_manager import FeatureConfig
            config = FeatureConfig(
                name=feature_name,
                tier=self.FeatureTier.IMPORTANT,
                description=description,
                resource_cost=3.0,
                network_cost=2.0
            )
            self.feature_manager.register_feature(config)
        
        # Optional features - disable first
        optional_features = [
            ("image_generation", "AI image generation"),
            ("crypto_prices", "Cryptocurrency price tracking"),
            ("airdrop_claiming", "Airdrop claiming functionality"),
            ("keno_gaming", "Keno game functionality"),
            ("tip_system", "Tipping and reward system"),
            ("reaction_roles", "Reaction role management"),
            ("conversation_history", "Conversation history tracking")
        ]
        
        for feature_name, description in optional_features:
            from .feature_manager import FeatureConfig
            config = FeatureConfig(
                name=feature_name,
                tier=self.FeatureTier.OPTIONAL,
                description=description,
                resource_cost=2.0,
                network_cost=3.0
            )
            self.feature_manager.register_feature(config)
        
        # Luxury features - disable immediately
        luxury_features = [
            ("analytics", "Usage analytics and metrics"),
            ("advanced_filters", "Advanced message filtering"),
            ("custom_commands", "Custom command creation"),
            ("music_player", "Music playback functionality"),
            ("weather_updates", "Weather information services")
        ]
        
        for feature_name, description in luxury_features:
            from .feature_manager import FeatureConfig
            config = FeatureConfig(
                name=feature_name,
                tier=self.FeatureTier.LUXURY,
                description=description,
                resource_cost=1.0,
                network_cost=2.0
            )
            self.feature_manager.register_feature(config)
        
        logger.info(f"Registered {len(critical_features + important_features + optional_features + luxury_features)} default features")
    
    async def start_monitoring(self):
        """Start all monitoring components."""
        if self._running:
            return
        
        logger.info("Starting graceful degradation monitoring...")
        
        # Start component monitoring
        if self.load_shedder:
            await self.load_shedder.start_monitoring()
        
        if self.degradation_monitor:
            await self.degradation_monitor.start_monitoring()
        
        self._running = True
        logger.info("Graceful degradation monitoring started")
    
    async def stop_monitoring(self):
        """Stop all monitoring components."""
        if not self._running:
            return
        
        logger.info("Stopping graceful degradation monitoring...")
        
        # Stop component monitoring
        if self.load_shedder:
            await self.load_shedder.stop_monitoring()
        
        if self.degradation_monitor:
            await self.degradation_monitor.stop_monitoring()
        
        self._running = False
        logger.info("Graceful degradation monitoring stopped")
    
    def register_notification_callback(self, callback: Callable[[SystemStatus], None]):
        """Register a callback for user notifications."""
        self.user_notification_callbacks.append(callback)
        logger.info("Registered user notification callback")
    
    async def force_degradation_level(self, level: str, reason: str = "Manual") -> bool:
        """
        Force a specific degradation level.
        
        Args:
            level: Target degradation level
            reason: Reason for the change
            
        Returns:
            True if successful, False otherwise
        """
        if not self.feature_manager or not self.FeatureTier:
            return False
        
        level_map = {
            "none": [],
            "minimal": [self.FeatureTier.LUXURY],
            "moderate": [self.FeatureTier.LUXURY, self.FeatureTier.OPTIONAL],
            "severe": [self.FeatureTier.LUXURY, self.FeatureTier.OPTIONAL, self.FeatureTier.IMPORTANT],
            "critical": [self.FeatureTier.LUXURY, self.FeatureTier.OPTIONAL, self.FeatureTier.IMPORTANT]
        }
        
        tiers_to_disable = level_map.get(level.lower(), [])
        
        # Disable features by tier
        for tier in tiers_to_disable:
            await self.feature_manager.disable_features_by_tier(tier, f"Manual degradation: {reason}")
        
        # Create status message
        status = SystemStatus(
            level=level.upper(),
            message=f"System manually set to {level} degradation: {reason}",
            affected_features=self.feature_manager.get_disabled_features(),
            estimated_recovery=None,
            user_actions=self._get_user_actions(level),
            timestamp=time.time()
        )
        
        await self._notify_users(status)
        
        logger.warning(f"Manual degradation set to {level}: {reason}")
        return True
    
    async def restore_full_functionality(self, reason: str = "Manual restore") -> bool:
        """
        Restore full system functionality.
        
        Args:
            reason: Reason for restoration
            
        Returns:
            True if successful, False otherwise
        """
        if not self.feature_manager:
            return False
        
        # Enable all features
        all_features = list(self.feature_manager.features.keys())
        success_count = 0
        
        for feature_name in all_features:
            if await self.feature_manager.enable_feature(feature_name, reason):
                success_count += 1
        
        # Create status message
        status = SystemStatus(
            level="NONE",
            message=f"Full functionality restored: {reason}",
            affected_features=[],
            estimated_recovery=None,
            user_actions=["All features are now available"],
            timestamp=time.time()
        )
        
        await self._notify_users(status)
        
        logger.info(f"Full functionality restored: {reason} ({success_count}/{len(all_features)} features)")
        return success_count > 0
    
    async def _notify_users(self, status: SystemStatus):
        """Notify users about system status changes."""
        if not self.communication_enabled:
            return
        
        # Store status message
        self.status_messages[status.level] = status
        
        # Call notification callbacks
        for callback in self.user_notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(status)
                else:
                    callback(status)
            except Exception as e:
                logger.error(f"User notification callback failed: {e}")
    
    def _get_user_actions(self, level: str) -> List[str]:
        """Get recommended user actions for a degradation level."""
        actions = {
            "none": ["All features are available"],
            "minimal": ["Some luxury features may be unavailable"],
            "moderate": ["Non-essential features are disabled", "Core functionality remains available"],
            "severe": ["Only essential features are available", "Please avoid non-critical operations"],
            "critical": ["System running in emergency mode", "Only critical functions available", "Expect limited functionality"]
        }
        return actions.get(level.lower(), ["System status unknown"])
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        status = {
            "initialized": self._initialized,
            "running": self._running,
            "auto_start": self.auto_start,
            "communication_enabled": self.communication_enabled,
            "components": {},
            "current_status": None,
            "recent_status_messages": {}
        }
        
        # Component status
        if self.feature_manager:
            status["components"]["feature_manager"] = self.feature_manager.get_all_features_status()
        
        if self.load_shedder:
            status["components"]["load_shedder"] = self.load_shedder.get_load_status()
        
        if self.degradation_monitor:
            status["components"]["degradation_monitor"] = self.degradation_monitor.get_degradation_status()
        
        # Current degradation level
        if self.degradation_monitor:
            degradation_status = self.degradation_monitor.get_degradation_status()
            current_level = degradation_status.get("current_level", "unknown")
            
            status["current_status"] = {
                "level": current_level.upper(),
                "message": self._get_status_message(current_level),
                "affected_features": self.feature_manager.get_disabled_features() if self.feature_manager else [],
                "uptime_percentage": degradation_status.get("uptime_percentage", 0),
                "user_actions": self._get_user_actions(current_level)
            }
        
        # Recent status messages
        recent_messages = sorted(
            self.status_messages.values(),
            key=lambda x: x.timestamp,
            reverse=True
        )[:5]  # Last 5 messages
        
        status["recent_status_messages"] = {
            msg.level: {
                "message": msg.message,
                "timestamp": msg.timestamp,
                "affected_features": len(msg.affected_features)
            }
            for msg in recent_messages
        }
        
        return status
    
    def _get_status_message(self, level: str) -> str:
        """Get user-friendly status message for degradation level."""
        messages = {
            "none": "System operating normally",
            "minimal": "Experiencing minor load - some luxury features disabled",
            "moderate": "Under moderate load - non-essential features disabled",
            "severe": "High load detected - only essential features available",
            "critical": "System under extreme stress - emergency mode active"
        }
        return messages.get(level, "System status unknown")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of the degradation system."""
        health = {
            "overall_healthy": True,
            "components": {},
            "issues": [],
            "recommendations": []
        }
        
        # Check feature manager
        if self.feature_manager:
            try:
                feature_health = await self.feature_manager.health_check_all_features()
                unhealthy_features = [f for f, healthy in feature_health.items() if not healthy]
                
                health["components"]["feature_manager"] = {
                    "healthy": len(unhealthy_features) == 0,
                    "unhealthy_features": unhealthy_features,
                    "total_features": len(feature_health)
                }
                
                if unhealthy_features:
                    health["issues"].append(f"{len(unhealthy_features)} features have health issues")
                    health["overall_healthy"] = False
                    
            except Exception as e:
                health["components"]["feature_manager"] = {"healthy": False, "error": str(e)}
                health["issues"].append(f"Feature manager health check failed: {e}")
                health["overall_healthy"] = False
        else:
            health["issues"].append("Feature manager not initialized")
            health["overall_healthy"] = False
        
        # Check load shedder
        if self.load_shedder:
            try:
                load_status = self.load_shedder.get_load_status()
                current_load = load_status.get("current_load_level", "unknown")
                
                health["components"]["load_shedder"] = {
                    "healthy": load_status.get("monitoring_active", False),
                    "current_load": current_load,
                    "active_shedding": load_status.get("active_shedding_count", 0)
                }
                
                if current_load in ["critical", "emergency"]:
                    health["issues"].append(f"System under {current_load} load")
                    health["recommendations"].append("Consider manual intervention if load persists")
                    
            except Exception as e:
                health["components"]["load_shedder"] = {"healthy": False, "error": str(e)}
                health["issues"].append(f"Load shedder health check failed: {e}")
                health["overall_healthy"] = False
        else:
            health["issues"].append("Load shedder not initialized")
            health["overall_healthy"] = False
        
        # Check degradation monitor
        if self.degradation_monitor:
            try:
                degradation_status = self.degradation_monitor.get_degradation_status()
                current_level = degradation_status.get("current_level", "unknown")
                
                health["components"]["degradation_monitor"] = {
                    "healthy": degradation_status.get("monitoring_active", False),
                    "current_level": current_level,
                    "degradation_events": degradation_status.get("statistics", {}).get("total_degradation_events", 0)
                }
                
                if current_level != "none":
                    health["issues"].append(f"System currently in {current_level} degradation")
                    
            except Exception as e:
                health["components"]["degradation_monitor"] = {"healthy": False, "error": str(e)}
                health["issues"].append(f"Degradation monitor health check failed: {e}")
                health["overall_healthy"] = False
        else:
            health["issues"].append("Degradation monitor not initialized")
            health["overall_healthy"] = False
        
        return health
    
    def enable_communication(self):
        """Enable user status communication."""
        self.communication_enabled = True
        logger.info("Status communication enabled")
    
    def disable_communication(self):
        """Disable user status communication."""
        self.communication_enabled = False
        logger.info("Status communication disabled")
    
    def get_user_friendly_status(self) -> str:
        """Get a user-friendly status message."""
        if not self._initialized:
            return "🔄 System initializing..."
        
        if self.degradation_monitor:
            degradation_status = self.degradation_monitor.get_degradation_status()
            current_level = degradation_status.get("current_level", "unknown")
            uptime = degradation_status.get("uptime_percentage", 0)
            
            status_emoji = {
                "none": "✅",
                "minimal": "⚠️",
                "moderate": "🟡",
                "severe": "🟠",
                "critical": "🔴"
            }
            
            emoji = status_emoji.get(current_level, "❓")
            message = self._get_status_message(current_level)
            
            return f"{emoji} {message} (Uptime: {uptime:.1f}%)"
        
        return "❓ System status unknown"
    
    async def shutdown(self):
        """Shutdown the graceful degradation system."""
        logger.info("Shutting down graceful degradation system...")
        
        await self.stop_monitoring()
        
        # Restore all features if possible
        if self.feature_manager:
            await self.restore_full_functionality("System shutdown")
        
        self._initialized = False
        logger.info("Graceful degradation system shutdown complete")


# Global orchestrator instance
graceful_degradation_orchestrator = GracefulDegradationOrchestrator()
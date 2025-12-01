"""
Integration example for the graceful degradation system.
Demonstrates how to integrate the degradation system with the Jakey.
"""
import asyncio
import time
import logging
from typing import Dict, Any

# Mock imports for demonstration
try:
    from resilience.graceful_degradation import graceful_degradation_orchestrator, SystemStatus
    from resilience.feature_manager import FeatureConfig, FeatureTier
    from resilience.load_shedder import SheddingStrategy
except ImportError:
    print("Warning: Graceful degradation modules not available")
    graceful_degradation_orchestrator = None

logger = logging.getLogger(__name__)


class JakeyDegradationIntegration:
    """
    Integration layer for graceful degradation with Jakey.
    """
    
    def __init__(self, bot_client):
        """Initialize the integration with bot client."""
        self.bot_client = bot_client
        self.orchestrator = graceful_degradation_orchestrator
        self.status_channel_id = None  # Channel for status notifications
        self.admin_role_id = None      # Role for admin notifications
        
    async def initialize(self):
        """Initialize the degradation system."""
        if not self.orchestrator:
            logger.warning("Graceful degradation orchestrator not available")
            return
        
        logger.info("Initializing Jakey graceful degradation...")
        
        # Register notification callbacks
        self.orchestrator.register_notification_callback(self._on_status_change)
        self.orchestrator.register_notification_callback(self._notify_admins)
        self.orchestrator.register_notification_callback(self._update_status_channel)
        
        # Register custom monitors
        self._register_custom_monitors()
        
        # Register bot-specific features
        await self._register_bot_features()
        
        # Initialize the system
        await self.orchestrator.initialize()
        
        logger.info("Jakey graceful degradation initialized")
    
    def _register_custom_monitors(self):
        """Register bot-specific custom monitors."""
        if not self.orchestrator:
            return
        
        # Discord API rate limit monitor
        def discord_rate_limit_monitor():
            # Check if we're hitting Discord rate limits
            rate_limiter = getattr(self.bot_client, 'rate_limiter', None)
            if rate_limiter:
                # Return 0-1 score based on rate limit usage
                return rate_limiter.get_usage_percentage() / 100
            return 0.0
        
        # Message queue size monitor
        def message_queue_monitor():
            message_queue = getattr(self.bot_client, 'message_queue', None)
            if message_queue:
                queue_size = len(message_queue)
                # Return 0-1 score (0.5 = 100 messages, 1.0 = 200+ messages)
                return min(queue_size / 200, 1.0)
            return 0.0
        
        # AI provider health monitor
        def ai_provider_health_monitor():
            ai_manager = getattr(self.bot_client, 'ai_manager', None)
            if ai_manager:
                # Check if AI providers are healthy
                healthy_providers = ai_manager.get_healthy_providers_count()
                total_providers = ai_manager.get_total_providers_count()
                if total_providers > 0:
                    health_ratio = healthy_providers / total_providers
                    # Return degradation score (0 = all healthy, 1 = none healthy)
                    return 1.0 - health_ratio
            return 0.0
        
        # Register monitors
        if hasattr(self.orchestrator.degradation_monitor, 'register_degradation_monitor'):
            self.orchestrator.degradation_monitor.register_degradation_monitor(discord_rate_limit_monitor)
            self.orchestrator.degradation_monitor.register_degradation_monitor(message_queue_monitor)
            self.orchestrator.degradation_monitor.register_degradation_monitor(ai_provider_health_monitor)
        
        # Recovery monitors
        def discord_recovery_monitor():
            # Check if Discord API is responsive
            try:
                # Ping Discord API
                latency = self.bot_client.latency
                return latency < 1.0  # Consider recovered if latency < 1 second
            except:
                return False
        
        def ai_recovery_monitor():
            # Check if AI providers are available
            ai_manager = getattr(self.bot_client, 'ai_manager', None)
            if ai_manager:
                return ai_manager.get_healthy_providers_count() > 0
            return False
        
        if hasattr(self.orchestrator.degradation_monitor, 'register_recovery_monitor'):
            self.orchestrator.degradation_monitor.register_recovery_monitor(discord_recovery_monitor)
            self.orchestrator.degradation_monitor.register_recovery_monitor(ai_recovery_monitor)
    
    async def _register_bot_features(self):
        """Register JakeySelfBot specific features."""
        if not self.orchestrator or not self.orchestrator.feature_manager:
            return
        
        feature_manager = self.orchestrator.feature_manager
        
        # Core Discord functionality
        core_features = [
            ("discord_events", "Discord event handling", FeatureTier.CRITICAL, 3.0, 2.0),
            ("message_processing", "Message processing pipeline", FeatureTier.CRITICAL, 2.5, 1.5),
            ("command_execution", "Command execution engine", FeatureTier.IMPORTANT, 2.0, 1.0),
        ]
        
        # AI and chat features
        ai_features = [
            ("ai_chat", "AI chat functionality", FeatureTier.IMPORTANT, 3.0, 2.5),
            ("ai_image_generation", "AI image generation", FeatureTier.OPTIONAL, 4.0, 3.0),
            ("context_memory", "Conversation memory", FeatureTier.IMPORTANT, 1.5, 1.0),
        ]
        
        # Utility features
        utility_features = [
            ("crypto_prices", "Cryptocurrency price tracking", FeatureTier.OPTIONAL, 2.0, 2.5),
            ("airdrop_claiming", "Airdrop claiming automation", FeatureTier.OPTIONAL, 2.5, 3.0),
            ("keno_game", "Keno game functionality", FeatureTier.OPTIONAL, 1.5, 1.0),
            ("tip_system", "Tipping and rewards", FeatureTier.OPTIONAL, 2.0, 2.0),
        ]
        
        # Advanced features
        advanced_features = [
            ("analytics", "Usage analytics and metrics", FeatureTier.LUXURY, 1.0, 1.5),
            ("auto_moderation", "Automatic moderation", FeatureTier.IMPORTANT, 2.0, 1.5),
            ("custom_commands", "Custom command creation", FeatureTier.LUXURY, 1.5, 1.0),
            ("reaction_roles", "Reaction role management", FeatureTier.OPTIONAL, 1.0, 1.0),
        ]
        
        # Register all features
        all_features = core_features + ai_features + utility_features + advanced_features
        
        for name, description, tier, resource_cost, network_cost in all_features:
            config = FeatureConfig(
                name=name,
                tier=tier,
                description=description,
                resource_cost=resource_cost,
                network_cost=network_cost,
                enable_func=self._create_enable_func(name),
                disable_func=self._create_disable_func(name),
                status_check_func=self._create_status_check_func(name)
            )
            feature_manager.register_feature(config)
        
        logger.info(f"Registered {len(all_features)} Jakey features")
    
    def _create_enable_func(self, feature_name):
        """Create enable function for a feature."""
        async def enable_feature():
            logger.info(f"Enabling feature: {feature_name}")
            # Implementation depends on the specific feature
            if feature_name == "ai_chat":
                # Enable AI chat
                ai_manager = getattr(self.bot_client, 'ai_manager', None)
                if ai_manager:
                    ai_manager.enable_chat()
            elif feature_name == "crypto_prices":
                # Enable crypto price updates
                crypto_updater = getattr(self.bot_client, 'crypto_updater', None)
                if crypto_updater:
                    crypto_updater.start()
            # Add more feature-specific enable logic
            return True
        return enable_feature
    
    def _create_disable_func(self, feature_name):
        """Create disable function for a feature."""
        async def disable_feature():
            logger.info(f"Disabling feature: {feature_name}")
            # Implementation depends on the specific feature
            if feature_name == "ai_chat":
                # Disable AI chat
                ai_manager = getattr(self.bot_client, 'ai_manager', None)
                if ai_manager:
                    ai_manager.disable_chat()
            elif feature_name == "crypto_prices":
                # Disable crypto price updates
                crypto_updater = getattr(self.bot_client, 'crypto_updater', None)
                if crypto_updater:
                    crypto_updater.stop()
            # Add more feature-specific disable logic
            return True
        return disable_feature
    
    def _create_status_check_func(self, feature_name):
        """Create status check function for a feature."""
        def check_status():
            # Check if the feature is healthy
            if feature_name == "ai_chat":
                ai_manager = getattr(self.bot_client, 'ai_manager', None)
                if ai_manager:
                    return ai_manager.is_healthy()
            elif feature_name == "crypto_prices":
                crypto_updater = getattr(self.bot_client, 'crypto_updater', None)
                if crypto_updater:
                    return crypto_updater.is_running()
            # Default to healthy
            return True
        return check_status
    
    async def _on_status_change(self, status: SystemStatus):
        """Handle status change notifications."""
        logger.info(f"System status changed: {status.level} - {status.message}")
        
        # Update bot presence based on status
        await self._update_bot_presence(status)
    
    async def _notify_admins(self, status: SystemStatus):
        """Notify administrators about status changes."""
        if not self.bot_client or not self.admin_role_id:
            return
        
        # Only notify for significant changes
        if status.level in ["SEVERE", "CRITICAL"]:
            try:
                # Find admin channel or create notification
                admin_message = (
                    f"🚨 **System Alert**: {status.level}\n"
                    f"{status.message}\n"
                    f"Affected features: {len(status.affected_features)}\n"
                    f"Actions: {', '.join(status.user_actions)}"
                )
                
                # Send to admin channel/DMs
                await self._send_admin_notification(admin_message)
                
            except Exception as e:
                logger.error(f"Failed to notify admins: {e}")
    
    async def _update_status_channel(self, status: SystemStatus):
        """Update the status channel with current system status."""
        if not self.bot_client or not self.status_channel_id:
            return
        
        try:
            channel = self.bot_client.get_channel(self.status_channel_id)
            if channel:
                # Create status embed
                embed = self._create_status_embed(status)
                await channel.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Failed to update status channel: {e}")
    
    def _create_status_embed(self, status: SystemStatus):
        """Create a Discord embed for status updates."""
        # This would create a proper Discord embed
        # For now, return a simple dict representation
        color_map = {
            "NONE": 0x00ff00,      # Green
            "MINIMAL": 0xffff00,   # Yellow
            "MODERATE": 0xffa500,  # Orange
            "SEVERE": 0xff4500,    # Red-orange
            "CRITICAL": 0xff0000   # Red
        }
        
        return {
            "title": f"System Status: {status.level}",
            "description": status.message,
            "color": color_map.get(status.level, 0x808080),
            "fields": [
                {
                    "name": "Affected Features",
                    "value": str(len(status.affected_features)),
                    "inline": True
                },
                {
                    "name": "Recommended Actions",
                    "value": "\n".join(status.user_actions[:3]),
                    "inline": True
                }
            ],
            "timestamp": status.timestamp
        }
    
    async def _update_bot_presence(self, status: SystemStatus):
        """Update bot presence based on system status."""
        if not self.bot_client:
            return
        
        status_map = {
            "NONE": "🟢 Full Operation",
            "MINIMAL": "🟡 Reduced Features",
            "MODERATE": "🟠 Limited Operation",
            "SEVERE": "🔴 Critical Mode",
            "CRITICAL": "💥 Emergency Mode"
        }
        
        presence = status_map.get(status.level, "❓ Unknown Status")
        
        try:
            await self.bot_client.change_presence(
                activity=type('Activity', (), {'name': presence})()
            )
        except Exception as e:
            logger.error(f"Failed to update bot presence: {e}")
    
    async def _send_admin_notification(self, message: str):
        """Send notification to administrators."""
        # Implementation depends on bot structure
        # This could send to a specific channel, DM admins, etc.
        logger.info(f"Admin notification: {message}")
    
    def set_status_channel(self, channel_id: int):
        """Set the channel for status updates."""
        self.status_channel_id = channel_id
    
    def set_admin_role(self, role_id: int):
        """Set the admin role for notifications."""
        self.admin_role_id = role_id
    
    async def get_system_dashboard(self) -> Dict[str, Any]:
        """Get a comprehensive system dashboard."""
        if not self.orchestrator:
            return {"error": "Graceful degradation not available"}
        
        system_status = self.orchestrator.get_system_status()
        health = await self.orchestrator.health_check()
        
        return {
            "system_status": system_status,
            "health_check": health,
            "bot_specific": {
                "latency": getattr(self.bot_client, 'latency', 0),
                "guild_count": len(getattr(self.bot_client, 'guilds', [])),
                "user_count": sum(len(guild.members) for guild in getattr(self.bot_client, 'guilds', [])),
                "uptime": time.time() - getattr(self.bot_client, 'start_time', time.time())
            }
        }
    
    async def handle_manual_degradation(self, level: str, reason: str = "Manual"):
        """Handle manual degradation requests."""
        if not self.orchestrator:
            return False
        
        return await self.orchestrator.force_degradation_level(level, reason)
    
    async def handle_manual_recovery(self, reason: str = "Manual recovery"):
        """Handle manual recovery requests."""
        if not self.orchestrator:
            return False
        
        return await self.orchestrator.restore_full_functionality(reason)


# Example usage
async def setup_graceful_degradation(bot_client):
    """Set up graceful degradation for the bot."""
    integration = JakeyDegradationIntegration(bot_client)
    
    # Configure channels and roles
    integration.set_status_channel(123456789012345678)  # Status channel ID
    integration.set_admin_role(987654321098765432)      # Admin role ID
    
    # Initialize
    await integration.initialize()
    
    return integration


# Discord command examples
async def status_command(ctx, integration):
    """Handle !status command."""
    dashboard = await integration.get_system_dashboard()
    
    status_msg = (
        f"**System Status**: {dashboard['system_status']['current_status']['level']}\n"
        f"**Message**: {dashboard['system_status']['current_status']['message']}\n"
        f"**Uptime**: {dashboard['bot_specific']['uptime']:.1f}s\n"
        f"**Latency**: {dashboard['bot_specific']['latency']*1000:.0f}ms\n"
        f"**Guilds**: {dashboard['bot_specific']['guild_count']}\n"
        f"**Users**: {dashboard['bot_specific']['user_count']}"
    )
    
    await ctx.send(status_msg)


async def degrade_command(ctx, integration, level: str):
    """Handle !degrade command."""
    if not hasattr(ctx.author, 'guild_permissions') or not ctx.author.guild_permissions.administrator:
        await ctx.send("Only administrators can use this command.")
        return
    
    success = await integration.handle_manual_degradation(level, f"Manual by {ctx.author.name}")
    
    if success:
        await ctx.send(f"✅ System degraded to {level.upper()} level")
    else:
        await ctx.send("❌ Failed to degrade system")


async def recover_command(ctx, integration):
    """Handle !recover command."""
    if not hasattr(ctx.author, 'guild_permissions') or not ctx.author.guild_permissions.administrator:
        await ctx.send("Only administrators can use this command.")
        return
    
    success = await integration.handle_manual_recovery(f"Manual by {ctx.author.name}")
    
    if success:
        await ctx.send("✅ System functionality restored")
    else:
        await ctx.send("❌ Failed to restore system")


if __name__ == "__main__":
    print("Jakey Graceful Degradation Integration")
    print("This module demonstrates how to integrate the graceful degradation system")
    print("with the Jakey for enhanced resilience and user experience.")
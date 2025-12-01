# Configuration Complexity Reduction Plan

## Current Issues
- **70+ configuration parameters** in single file
- **Mixed concerns**: Discord, AI, database, features all together
- **No validation**: Raw environment variables without type checking
- **Hard to discover**: No clear grouping or documentation
- **Maintenance burden**: Changes affect entire config system

## Proposed Configuration Architecture

```python
# config/__init__.py
from .discord_config import DiscordConfig
from .ai_config import AIConfig
from .database_config import DatabaseConfig
from .feature_config import FeatureConfig
from .validation import ConfigValidator

class AppConfig:
    """Main configuration container with validation"""

    def __init__(self):
        self.discord = DiscordConfig()
        self.ai = AIConfig()
        self.database = DatabaseConfig()
        self.features = FeatureConfig()

        # Validate all configurations
        validator = ConfigValidator()
        validator.validate(self)

    def reload(self):
        """Reload configuration from environment"""
        # Implementation for hot reloading
        pass

# Global config instance
config = AppConfig()
```

## Configuration Modules

### Discord Configuration (`config/discord_config.py`)
```python
@dataclass
class DiscordConfig:
    """Discord-specific configuration"""
    token: str = field(default_factory=lambda: _get_required_env("DISCORD_TOKEN"))
    command_prefix: str = "%"
    max_message_length: int = 2000
    heartbeat_timeout: float = 60.0

    # Admin settings
    admin_user_ids: List[str] = field(default_factory=_parse_admin_ids)

    # Guild settings
    guild_blacklist: List[str] = field(default_factory=_parse_guild_blacklist)
    welcome_server_ids: List[str] = field(default_factory=_parse_welcome_servers)
    welcome_channel_ids: List[str] = field(default_factory=_parse_welcome_channels)

    # Webhook relay
    webhook_relay_mappings: Dict[str, str] = field(default_factory=_parse_webhook_mappings)
    relay_mention_role_mappings: Dict[str, str] = field(default_factory=_parse_mention_mappings)
    use_webhook_relay: bool = True
    webhook_exclude_ids: List[str] = field(default_factory=_parse_exclude_ids)
```

### AI Configuration (`config/ai_config.py`)
```python
@dataclass
class AIConfig:
    """AI provider configuration"""
    default_model: str = "evil"

    # Pollinations settings
    pollinations_api_token: Optional[str] = field(default_factory=lambda: os.getenv("POLLINATIONS_API_TOKEN"))
    pollinations_text_timeout: int = 45
    pollinations_image_timeout: int = 30

    # OpenRouter settings
    openrouter_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY"))
    openrouter_enabled: bool = True
    openrouter_default_model: str = "nvidia/nemotron-nano-9b-v2:free"
    openrouter_timeout: int = 30

    # Arta settings
    arta_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ARTA_API_KEY"))

    # Rate limiting
    text_api_rate_limit: int = 20  # requests per minute
    image_api_rate_limit: int = 20

    # Response uniqueness
    enable_response_uniqueness: bool = True
    anti_repetition_threshold: float = 0.8
```

### Database Configuration (`config/database_config.py`)
```python
@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "data/jakey.db"
    connection_pool_size: int = 5
    enable_wal_mode: bool = True

    # Memory settings
    mcp_memory_enabled: bool = False
    mcp_memory_server_url: Optional[str] = None

    # Message queue (if enabled)
    message_queue_enabled: bool = False
    message_queue_db_path: str = "data/message_queue.db"

    # Cache settings
    enable_query_cache: bool = True
    cache_ttl_seconds: int = 300
```

### Feature Configuration (`config/feature_config.py`)
```python
@dataclass
class FeatureConfig:
    """Feature flags and settings"""

    # Airdrop settings
    airdrop_enabled: bool = True
    airdrop_presence: str = "invisible"
    airdrop_smart_delay: bool = True
    airdrop_ignore_drops_under: float = 0.0

    # Welcome system
    welcome_enabled: bool = True
    welcome_prompt: str = "..."

    # Gender roles
    gender_roles_enabled: bool = True
    gender_role_mappings: Dict[str, str] = field(default_factory=dict)

    # External integrations
    coinmarketcap_api_key: Optional[str] = field(default_factory=lambda: os.getenv("COINMARKETCAP_API_KEY"))
    searxng_url: str = "http://localhost:8086"

    # Rate limiting
    user_rate_limit: int = 20
    rate_limit_cooldown: int = 60
```

## Configuration Validation

```python
# config/validation.py
from typing import List
import re

class ConfigValidator:
    """Configuration validation with detailed error messages"""

    def validate(self, config: AppConfig) -> None:
        """Validate entire configuration"""
        errors = []

        # Discord validation
        if not config.discord.token:
            errors.append("DISCORD_TOKEN is required")

        if not self._is_valid_discord_token(config.discord.token):
            errors.append("DISCORD_TOKEN format is invalid")

        # AI validation
        if not config.ai.pollinations_api_token and not config.ai.openrouter_api_key:
            errors.append("At least one AI provider (Pollinations or OpenRouter) must be configured")

        # Database validation
        if not config.database.path:
            errors.append("Database path cannot be empty")

        if errors:
            raise ConfigurationError(f"Configuration validation failed: {', '.join(errors)}")

    def _is_valid_discord_token(self, token: str) -> bool:
        """Validate Discord token format"""
        # Discord tokens are 59 characters long
        return len(token) == 59 and '.' in token
```

## Migration Strategy

### Phase 1: Create Configuration Modules
- Extract related settings into separate dataclasses
- Add type hints and default values
- Implement basic validation

### Phase 2: Add Validation Layer
- Create comprehensive validation rules
- Add helpful error messages
- Support environment-specific validation

### Phase 3: Update Imports
- Change all `from config import X` to `from config import config; config.X`
- Update main.py and other entry points
- Maintain backward compatibility during transition

### Phase 4: Add Advanced Features
- Configuration hot reloading
- Environment-specific configs
- Configuration documentation generation

## Benefits
- **Organization**: Related settings grouped logically
- **Validation**: Type safety and input validation
- **Maintainability**: Changes isolated to specific areas
- **Documentation**: Self-documenting configuration classes
- **Testing**: Each config module can be tested independently
- **Flexibility**: Easy to add new configuration areas
# AGENTS.md

This file provides guidance to agentic coding agents working with code in this repository.

## Common Development Commands

### Running the Bot

- **Standard startup**: `./scripts/jakey.sh` - Starts bot with MCP memory server, monitoring, and proper error handling
- **Direct Python**: `python main.py` - Simple startup without additional services
- **Skip MCP server**: `./scripts/jakey.sh --skip-mcp` - Start without memory server

### MCP Memory Server

- **Start MCP server**: `./scripts/start_mcp_server.sh` - Start memory server independently

### Service Management

- **Systemd setup**: `./scripts/setup_systemd.sh` - Install as systemd service
- **Service control**: `./scripts/service_control.sh` - Start/stop systemd service
- **Status check**: `./scripts/check_status.sh` - Check bot and service status
- **PM2 Management**: `pm2 start pm2-ecosystem.yml` - Production process management

## Architecture Overview

### Core Components

**Entry Point & Initialization (`main.py`)**

- Dependency injection container with all services
- Graceful shutdown handling with signal handlers
- File locking to prevent multiple instances
- MCP server health checks
- Automatic reconnection with exponential backoff

**Bot Client (`bot/client.py`)**

- Main Discord bot implementation with discord.py-self
- 35 registered commands across 8 categories
- Advanced message processing with tool integration
- Response uniqueness system to prevent repetition
- Comprehensive error handling and sanitization
- Rate limiting and user permissions

**Configuration (`config.py`)**

- Environment-based configuration with dotenv
- 70+ configurable parameters
- Features: AI models, rate limits, timeouts, admin controls
- System prompt with personality and tool hierarchy
- Guild blacklists and webhook relay mappings

### AI Integration

**AI Provider Management (`ai/ai_provider_manager.py`)**

- Primary: Pollinations API with fallback to OpenRouter
- Automatic failover and restoration logic
- Rate limiting and timeout monitoring
- Response uniqueness enforcement

**Image Generation (`ai/arta.py`)**

- 49 professional artistic styles (Fantasy Art, Van Gogh, etc.)
- 9 aspect ratios for flexible dimensions
- Asynchronous generation with status polling
- Prompt sanitization and Discord mention support

### Tool System

**Tool Manager (`tools/tool_manager.py`)**

- 12 specialized tools for various operations
- Function calling integration with AI providers
- Discord-specific tools for server management
- Memory tools for user preference storage

**Key Tools:**

- `web_search` - Self-hosted SearXNG integration
- `crypto_price` - CoinMarketCap API integration
- `discord_*` tools - Server and channel management
- `remember_user_*` - Memory system with MCP backend

### Database & Storage

**SQLite Database (`data/` directory)**

- Async operations with aiosqlite
- Conversation history and user preferences
- Tip.cc transaction tracking
- Airdrop claiming records

**MCP Memory Server (`tools/mcp_memory_server.py`)**

- Optional external memory service
- Dynamic port assignment
- HTTP API with health endpoints
- Persistent storage across bot restarts

## Key Dependencies

### ⚠️ CRITICAL: discord.py-self vs discord.py

**THIS PROJECT USES discord.py-self, NOT REGULAR discord.py!**

- **discord.py-self**: Primary Discord self-bot framework - this is the ONLY dependency used for Discord functionality
- **URGENT**: Do NOT use regular discord.py - they are fundamentally different libraries
- **CRITICAL DIFFERENCES**:
    - **NO INTENTS**: discord.py-self does NOT use intents parameter - this will cause errors if added
    - **User Accounts vs Bot Accounts**: discord.py-self enables user account automation, not bot accounts
    - **Self-Bot Specific**: Designed for self-bots running on user accounts, not official bot applications
    - **API Differences**: While compatible with discord.py syntax, some features work differently or are removed

### 🚨 IMPORTANT USAGE NOTES

- **NEVER** add `intents=` parameter to client initialization - this will break discord.py-self
- **USE**: `discord.Client()` or `commands.Bot(command_prefix='!', self_bot=True)`
- **AVOID**: Any discord.py documentation that mentions intents, bot tokens, or developer portals
- **REMEMBER**: This is a self-bot project using user accounts, not a bot application

### Installation

```bash
pip install -U discord.py-self  # NOT discord.py!
```

### External APIs

- **Pollinations API**: Primary AI text/image generation
- **OpenRouter**: Fallback AI provider when Pollinations fails
- **Arta API**: Professional artistic image generation (49 styles)
- **CoinMarketCap**: Cryptocurrency price data
- **SearXNG**: Self-hosted web search (localhost:8086 or public instances)
- **tip.cc**: Discord cryptocurrency tipping bot integration

### Core Python Packages

- `discord.py-self`: Discord self-bot framework
- `aiohttp`: Async HTTP client for API calls
- `aiosqlite`: Async SQLite database operations
- `python-dotenv`: Environment variable management
- `pytz`: Timezone handling for time/date commands

## Development Guidelines

### Command System

- Commands use `%` prefix (e.g., `%help`, `%image`, `%bal`)
- Tip.cc commands (`%bal`, `%transactions`, `%tipstats`) are admin-only
- Admin commands require user ID in `ADMIN_USER_IDS` env var
- All commands support comprehensive help with examples
- Rate limiting enforced per user (configurable)

### Error Handling

- Sanitized error messages for user-facing responses
- Full error details logged for debugging
- Graceful degradation when external services fail
- Automatic reconnection for Discord connectivity issues

### Testing Strategy

- 44 comprehensive unit tests covering all major features
- Test modules follow `test_*.py` naming convention
- Tests verify commands, database operations, API integration
- Mock external dependencies for reliable testing

### Configuration Management

- All secrets in `.env` file (never in code)
- Feature flags for enabling/disabling components
- Comprehensive default values for all settings
- Environment-specific overrides supported

### Security Considerations

- Input sanitization for all user inputs
- SQL injection protection with parameterized queries
- Rate limiting to prevent abuse
- Admin-only commands with proper authorization
- Guild blacklist support for selective response

## Code Style Guidelines

### Imports

- Standard library imports first, then third-party, then local imports
- Group imports logically with blank lines between groups
- Use explicit imports (`from module import Class`) rather than wildcards

### Formatting

- Line length: 88 characters (default Black formatting)
- Indentation: 4 spaces
- Use double quotes for strings unless single quotes are needed for escaping

### Types and Naming

- Use type hints for function parameters and return values
- Variable names: snake_case
- Class names: PascalCase
- Constants: UPPER_SNAKE_CASE

### Error Handling

- Prefer specific exception handling over broad except clauses
- Always log errors with context
- Use f-strings for error messages

### Testing

- Use unittest framework
- Test files named test\_\*.py
- Test classes inherit from unittest.TestCase
- Test methods start with test\_
- Mock external dependencies

### Additional Rules

- No inline comments unless explaining complex logic
- Keep functions focused and small
- Use docstrings for all public functions and classes

## Project Structure

### 📁 Directory Layout

```
Jakey/
├── data/              # Database and data storage
│   ├── __init__.py
│   └── database.py
├── tools/             # Tool implementations and servers
│   ├── __init__.py
│   ├── tool_manager.py
│   ├── mcp_memory_client.py
│   └── mcp_memory_server.py
├── ai/                # AI service integrations
├── bot/               # Discord bot core
├── utils/             # Utility functions
├── tests/             # Test suite
├── docs/              # Documentation (all .md files moved here)
└── media/             # Media generation
```

### Message Relay Configuration

The message relay feature now uses webhooks exclusively instead of direct channel-to-channel relaying. This provides better compatibility and functionality for self-bots.

#### Environment Variables

- `WEBHOOK_RELAY_MAPPINGS`: JSON format mapping source channels to webhook URLs
    - Example: `{"123456789": "https://discord.com/api/webhooks/987654321/webhook_token"}`
    - Maps source channel IDs to target webhook URLs where messages should be relayed

- `RELAY_MENTION_ROLE_MAPPINGS`: JSON format mapping webhooks to role IDs for mentions
    - Example: `{"https://discord.com/api/webhooks/987654321/webhook_token": "111222333"}`
    - Maps webhook URLs to role IDs that should be mentioned when messages are relayed through them

- `USE_WEBHOOK_RELAY`: Enable or disable webhook relay functionality (default: true)
    - Set to `"true"` to use webhook-based relaying exclusively
    - Set to `"false"` to disable (though relay functionality will not work properly)

```

### 🔧 Key Components

#### Data Layer (`data/`)

- **database.py**: SQLite database manager for user data, memories, and configurations
- All database operations centralized in this module

#### Tools Layer (`tools/`)

- **tool_manager.py**: Main tool orchestrator with rate limiting and fallback logic
- **mcp_memory_client.py**: HTTP client for MCP memory server integration
- **mcp_memory_server.py**: HTTP API server for enhanced memory operations
- **Auto-started**: MCP memory server starts automatically with `./jakey.sh`

#### MCP Memory Integration

- **Server**: HTTP API on dynamically assigned port with health check endpoint
- **Client**: Async HTTP client with dynamic port discovery
- **Fallback**: Graceful degradation to SQLite when MCP server unavailable
- **Rate Limiting**: Built-in rate limiting for memory operations
- **Configuration**: Controlled via `MCP_MEMORY_ENABLED` environment variable

### 🚀 Startup Process

1. **MCP Memory Server**: Starts automatically on a random available port
2. **Port Discovery**: Server writes port to `.mcp_port` file for client discovery
3. **Health Check**: Verifies MCP server is responsive on the dynamic port
4. **Main Bot**: Starts with MCP memory integration enabled
5. **Cleanup**: MCP server shuts down gracefully and removes port file when bot exits

### 🧪 Testing

#### MCP Memory Tests

- **Location**: `tests/test_mcp_memory_integration.py`
- **Coverage**: 10 tests covering client, server, and integration scenarios
- **Features**: Connection handling, fallback behavior, rate limiting
- **Command**: `python -m tests.test_mcp_memory_integration`

#### Full Test Suite

- **Total Tests**: 81 tests (including 10 MCP integration tests)
- **Command**: `python -m tests.test_runner`
- **Categories**: Unit tests, integration tests, MCP memory tests

## 🚨 Common discord.py-self Errors to Avoid

### Error: "missing 1 required keyword-only argument: 'intents'"

**CAUSE**: Using regular discord.py syntax with discord.py-self
**SOLUTION**: Remove `intents=` parameter completely
**WRONG**: `client = discord.Client(intents=intents)`
**CORRECT**: `client = discord.Client()`

### Error: "missing 1 required keyword-only argument: 'intents'" with Bot

**CAUSE**: Using discord.py Bot syntax with discord.py-self
**SOLUTION**: Use `self_bot=True` instead of intents
**WRONG**: `bot = commands.Bot(command_prefix='!', intents=intents)`
**CORRECT**: `bot = commands.Bot(command_prefix='!', self_bot=True)`

### Error: Bot token or application ID related issues

**CAUSE**: Following discord.py bot setup guides
**SOLUTION**: Remember this is a self-bot using USER ACCOUNT tokens, not bot tokens
**WRONG**: Using Discord Developer Portal for bot setup
**CORRECT**: Using user account token from browser/dev tools

### Error: Features not working (slash commands, UI components, etc.)

**CAUSE**: discord.py-self has limitations compared to discord.py
**SOLUTION**: User accounts cannot use bot-specific features like:

- Application commands (slash commands)
- Discord UI components (modals, select menus, etc.)
- Bot-only intents and privileges
  **REMEMBER**: Self-bots have different capabilities than official bots
## Key Files to Understand

- **`main.py`** - Application entry point and dependency setup
- **`config.py`** - All configuration options and environment variables
- **`bot/client.py`** - Core Discord bot implementation with message processing
- **`bot/commands.py`** - All 35 bot commands with admin controls and error handling
- **`tools/tool_manager.py`** - AI tool integration and function calling system
- **`ai/ai_provider_manager.py`** - Multi-provider AI system with failover
- **`ai/pollinations.py`** - Primary AI API integration with response uniqueness
- **`ai/openrouter.py`** - Fallback AI provider for reliability
- **`utils/tipcc_manager.py`** - Cryptocurrency tipping integration
- **`utils/jakey_airdrop.py`** - Automated airdrop claiming system
- **`data/database.py`** - SQLite database operations for conversation/memory
- **`tests/test_runner.py`** - Test suite execution and reporting

## 🚨 Common discord.py-self Errors to Avoid

### Error: "missing 1 required keyword-only argument: 'intents'"

**CAUSE**: Using regular discord.py syntax with discord.py-self
**SOLUTION**: Remove `intents=` parameter completely
**WRONG**: `client = discord.Client(intents=intents)`
**CORRECT**: `client = discord.Client()`

### Error: "missing 1 required keyword-only argument: 'intents'" with Bot

**CAUSE**: Using discord.py Bot syntax with discord.py-self
**SOLUTION**: Use `self_bot=True` instead of intents
**WRONG**: `bot = commands.Bot(command_prefix='!', intents=intents)`
**CORRECT**: `bot = commands.Bot(command_prefix='!', self_bot=True)`

### Error: Bot token or application ID related issues

**CAUSE**: Following discord.py bot setup guides
**SOLUTION**: Remember this is a self-bot using USER ACCOUNT tokens, not bot tokens
**WRONG**: Using Discord Developer Portal for bot setup
**CORRECT**: Using user account token from browser/dev tools

### Error: Features not working (slash commands, UI components, etc.)

**CAUSE**: discord.py-self has limitations compared to discord.py
**SOLUTION**: User accounts cannot use bot-specific features like:

- Application commands (slash commands)
- Discord UI components (modals, select menus, etc.)
- Bot-only intents and privileges
  **REMEMBER**: Self-bots have different capabilities than official bots
```

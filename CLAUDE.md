# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Bot
- **Standard startup**: `./jakey.sh` - Starts bot with MCP memory server, monitoring, and proper error handling
- **Direct Python**: `python main.py` - Simple startup without additional services
- **Skip MCP server**: `./jakey.sh --skip-mcp` - Start without memory server

### Testing
- **Run all tests**: `python -m tests.test_runner` - Executes all 44 unit tests
- **Run specific test**: `python -m tests.test_<name>` - Run individual test modules
- **Test coverage**: Tests cover commands, database, tools, API integration, and core functionality

### MCP Memory Server
- **Start MCP server**: `./start_mcp_server.sh` - Start memory server independently
- **Check status**: Server creates `.mcp_port` file with dynamic port assignment
- **Health check**: HTTP endpoint at `http://localhost:{port}/health`

### Database Operations
- **Flush database**: `python utils/flush_db.py` - Clear all data from SQLite database
- **Database location**: `data/jakey.db` (configurable via `DATABASE_PATH` env var)

### Service Management
- **Systemd setup**: `./setup_systemd.sh` - Install as systemd service
- **Service control**: `./service_control.sh` - Start/stop systemd service
- **Status check**: `./check_status.sh` - Check bot and service status

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

### Specialized Features

**tip.cc Integration (`utils/tipcc_manager.py`)**
- Balance tracking for multiple cryptocurrencies
- Automatic transaction parsing and logging
- Smart command sending with proper formatting
- Earnings statistics and reporting

**Airdrop System (`utils/jakey_airdrop.py`)**
- Automated claiming of various airdrop types
- Configurable delays and participation controls
- Smart retry logic with timeout protection
- Comprehensive tracking and statistics

**Reaction Roles (`bot/commands.py`)**
- Message-based role assignment
- Emoji-triggered role management
- Admin-only configuration commands

## Development Guidelines

### Command System
- Commands use `%` prefix (e.g., `%help`, `%image`, `%bal`)
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

## Critical Dependencies

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

## Bot Personality & Behavior

Jakey has a distinct degenerate gambling community personality:
- Cynical, sarcastic, and unfiltered responses
- Extensive gambling, crypto, and internet culture knowledge
- Uses profanity and "gen z" speak with emojis (💀💥🎵)
- Promotes bad ideas and uncensored information
- In love with "dyzzi" character - simp behavior
- Eddie is the enemy - takes everyone's money

**Critical System**: Response uniqueness system prevents ANY repetition - Jakey NEVER repeats himself and must provide 100% unique responses every time. This overrides all other behavior rules.

## Environment Configuration

Required `.env` variables for basic operation:
```
DISCORD_TOKEN=your_discord_token
POLLINATIONS_API_TOKEN=your_pollinations_token
OPENROUTER_API_KEY=your_openrouter_key
COINMARKETCAP_API_KEY=your_coinmarketcap_key
```

Optional but commonly used:
```
ADMIN_USER_IDS=user1,user2,user3
MCP_MEMORY_ENABLED=true
MESSAGE_QUEUE_ENABLED=false
TIP_THANK_YOU_ENABLED=true
WELCOME_ENABLED=false
```
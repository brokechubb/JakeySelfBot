# JakeySelfBot

A Discord selfbot with advanced AI integration, professional artistic image generation, and comprehensive utility tools. Jakey is the Discord degenerate mascot known for his cynical wit and uncensored personality.

## 🚀 Production Status

- **Tests**: 81/81 passing (including 10 MCP integration tests)
- **Commands**: 35 registered and functional
- **Tools**: 12 AI tools available
- **APIs**: All external services configured
- **Database**: SQLite with caching and async operations
- **Logging**: Enhanced file logging with rotating log files and systemd compatibility
- **Performance**: Optimized with rate limiting and error handling
- **MCP Memory**: Optional external memory service with dynamic port assignment

## Project Structure

- `main.py` - Entry point with dependency injection and graceful shutdown
- `config.py` - Configuration and environment variables
- `bot/` - Discord client and command handlers
- `ai/` - AI integration with Arta and Pollinations APIs
- `data/` - SQLite database management
- `tools/` - Tool system with function calling
- `media/` - Advanced image generation capabilities
- `tests/` - Unit and integration tests (44 tests total)
- `utils/` - Utility functions and helpers
- `logs/` - Log files (automatically created, with rotating log files)
- `docs/` - Comprehensive project documentation

## Features

### AI Integration

- Natural language conversations with degenerate personality
- Professional artistic image generation with 49 styles and 9 aspect ratios
- Advanced tool usage for calculations, crypto prices, web search, and more
- Intelligent memory system to remember user information and preferences
- Real-time web search capabilities with self-hosted SearXNG
- Designed for free-to-use AI models and APIs

### Enhanced tip.cc Integration

- **Comprehensive Balance Tracking**: Automatic tracking of all cryptocurrency balances with USD value conversion
- **Transaction History**: Detailed logging of all tips, airdrops, deposits, and withdrawals
- **Smart Command Sending**: Properly formatted tip.cc commands sent as separate messages
- **Earnings Statistics**: Track airdrop winnings, tips sent/received, and net profit
- **Automated Parsing**: Intelligent parsing of tip.cc bot responses to update balances
- **Multi-Currency Support**: Handle all supported cryptocurrencies with real-time price conversion

### Airdrop Claiming

- Automated claiming of various cryptocurrency airdrops
- Support for standard airdrops, trivia drops, math drops, phrase drops, and red packets
- Configurable delays and participation controls
- Smart retry logic with timeout protection
- **Enhanced Tracking**: Automatic recording of airdrop entries and winnings in database

### Advanced Image Generation

- 49 Professional Artistic Styles (Fantasy Art, Vincent Van Gogh, Photographic, Watercolor, etc.)
- 9 Aspect Ratios (1:1, 16:9, 3:2, etc.) for flexible image dimensions
- Asynchronous generation with status polling
- Automatic prompt sanitization for special characters
- Support for Discord user mentions in prompts
- High-quality outputs with professional artistic rendering

### MCP Memory Server

- Optional external memory service with HTTP API
- Dynamic port assignment for service management
- Persistent storage across bot restarts
- Health check endpoints for service monitoring

### Utility Tools

- Crypto price checking with CoinMarketCap API
- Currency conversion and financial calculations
- Mathematical calculations with safe evaluation
- Web search capabilities with self-hosted SearXNG
- Bonus schedule information for gambling sites
- User memory and preference storage
- Audio generation with multiple voice options
- Image analysis and description
- Keno number generation with visual board
- Random Indian name and address generator

## Setup

1. Create a virtual environment:

    ```bash
    python -m venv venv
    ```

2. Activate the virtual environment:

    ```bash
    source venv/bin/activate  # Linux/Mac
    venv\Scripts\activate     # Windows
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Configure the bot by editing `.env` file with your Discord token and other settings.

5. Run the bot:
    ```bash
    python main.py
    ```

Or use the preferred startup script:

```bash
./jakey.sh
```

## Commands

Jakey supports 35 comprehensive commands for various functions:

### Core Commands (8)

- `%help` - Show comprehensive help information
- `%ping` - Check if Jakey is alive and responsive
- `%stats` - Show bot statistics and performance metrics
- `%model [model_name]` - Show or set current AI model (admin only)
- `%models` - List all available AI models
- `%imagemodels` - List all 49 artistic styles for image generation
- `%time [timezone]` - Display current time for specific timezone
- `%date [timezone]` - Display current date for specific timezone

### AI and Media Commands (4)

- `%image <prompt>` - Generate professional artistic images with 49 styles
- `%audio <text>` - Generate audio from text with multiple voice options
- `%analyze <image_url> [prompt]` - Analyze and describe images
- `%aistatus` - Display AI system and API status

### Memory and User Commands (2)

- `%remember <type> <info>` - Remember important information about users
- `%friends` - List Jakey's friends

### Gambling and Utility Commands (7)

- `%rigged` - Classic Jakey response about everything being rigged
- `%wen <item>` - Get bonus schedule information for gambling sites
- `%keno` - Generate random Keno numbers with visual board
- `%airdropstatus` - Show current airdrop configuration and status
- `%channelstats` - Show conversation statistics for the current channel
- `%ind_addr` - Generate a random Indian name and address

### tip.cc Commands (3)

- `%bal` / `%bals` - Check Jakey's tip.cc balances with detailed tracking
- `%transactions [limit]` - Show recent tip.cc transaction history
- `%tipstats` - Show tip.cc statistics and earnings

### Admin Commands (8)

- `%tip <recipient> <amount> <currency> [message]` - Send a tip using tip.cc (admin only)
- `%airdrop <amount> <currency> <duration>` - Create an airdrop using tip.cc (admin only)
- `%userinfo [user]` - Get information about a user (admin only)
- `%clearhistory [user]` - Clear conversation history for a user (admin only)
- `%clearallhistory` - Clear ALL conversation history (admin only)
- `%clearchannelhistory` - Clear conversation history for the current channel (admin only)
- `%set_gender_roles <gender:role_id,...>` - Set gender role mappings (admin only)
- `%show_gender_roles` - Show current gender role mappings (admin only)

### Role Management Commands (4)

- `%add_reaction_role <message_id> <emoji> <role>` - Add reaction role to message (admin only)
- `%remove_reaction_role <message_id> <emoji>` - Remove reaction role from message (admin only)
- `%list_reaction_roles` - List all configured reaction roles (admin only)

## Configuration

See `config.py` for all available configuration options. Key settings include:

- Discord token and presence settings
- AI model preferences
- Airdrop claiming behavior
- Rate limiting controls
- Admin user IDs for restricted commands
- Welcome message configuration
- Tip thank you message settings
- MCP memory server settings
- Tool-specific configurations
- Free-to-use AI provider settings

For detailed configuration documentation, see [CONFIGURATION.md](docs/CONFIGURATION.md).
For detailed configuration documentation, see [CONFIGURATION.md](docs/CONFIGURATION.md).

## Enhanced Features

### Advanced Image Generation

Jakey uses the Arta API for professional artistic image generation:

- **49 Artistic Styles**: Fantasy Art, Vincent Van Gogh, Photographic, Watercolor, and more
- **9 Aspect Ratios**: 1:1, 16:9, 3:2, 4:3, etc. for flexible image dimensions
- **Automatic Prompt Sanitization**: Handles special characters and Discord mentions
- **Asynchronous Processing**: Non-blocking generation with status polling
- **High-Quality Outputs**: Professional artistic rendering with detailed compositions

### Improved AI Capabilities

- **Free-to-Use Design**: Optimized for free AI models and APIs
- **Multi-Provider Support**: Primary Pollinations API with OpenRouter fallback
- **Enhanced Tool System**: Access to web search, crypto prices, calculations, and more
- **Memory System**: Remembers user information and preferences
- **Personality-Driven Responses**: Consistent degenerate gambling personality throughout
- **Rate Limiting**: Automatic request throttling to prevent API abuse
- **Error Handling**: Comprehensive error handling with user-friendly messages

### Self-Hosted Search Infrastructure

- **SearXNG Integration**: Fast, reliable web search with multiple engine support
- **Multiple Search Engines**: Google, Bing, DuckDuckGo, Brave with fallback capabilities
- **Local Caching**: Optimized search performance with local caching
- **No External Dependencies**: Self-hosted solution eliminates broken public service dependencies
- **Free-to-Use**: Self-hosted infrastructure ensures continued operation without cost

### MCP Memory Server

- **Optional External Memory**: HTTP-based memory service for persistent data
- **Dynamic Port Assignment**: Automatic port detection and assignment
- **Health Monitoring**: Built-in health check endpoints
- **Persistent Storage**: Data persistence across bot restarts

### Robust Command System

- **35 Commands**: Comprehensive set of utility and gambling-related commands
- **Proper Help System**: Detailed help with examples and usage information
- **Admin Controls**: Restricted commands for authorized users only
- **Performance Monitoring**: Built-in statistics and performance tracking

### Reliability and Stability

- **Multi-Provider AI**: Automatic failover between AI providers
- **Error Resilience**: Handles network failures, API errors, and invalid inputs
- **Graceful Shutdown**: Proper cleanup and state preservation on shutdown
- **Automatic Reconnection**: Discord connection recovery with exponential backoff
- **Comprehensive Testing**: 44 unit tests covering all major functionality

### Admin Configuration

Some commands are restricted to admin users only. To configure admin users:

1. Set the `ADMIN_USER_IDS` environment variable in your `.env` file
2. Add comma-separated Discord user IDs of admins:
    ```
    ADMIN_USER_IDS=123456789,987654321
    ```

Only users whose IDs are listed will be able to use these restricted commands.

## Conversation History Configuration

JakeySelfBot allows you to customize how much conversation history is used for AI context. The following parameters can be configured in your environment variables or `config.py`:

- `CONVERSATION_HISTORY_LIMIT`: Number of previous conversations to include (default: 10)
- `MAX_CONVERSATION_TOKENS`: Maximum tokens for conversation context (default: 1500)
- `CHANNEL_CONTEXT_MINUTES`: Minutes of channel context to include (default: 30)
- `CHANNEL_CONTEXT_MESSAGE_LIMIT`: Maximum messages in channel context (default: 10)

Example configuration in `.env`:

```
CONVERSATION_HISTORY_LIMIT=5
MAX_CONVERSATION_TOKENS=2000
CHANNEL_CONTEXT_MINUTES=60
CHANNEL_CONTEXT_MESSAGE_LIMIT=20
```

For more details, see [docs/CONVERSATION_HISTORY.md](docs/CONVERSATION_HISTORY.md).

## Logging Configuration

JakeySelfBot features enhanced logging with multiple output options:

### File Logging

- **Automatic log directory**: The `logs/` directory is created automatically
- **Rotating log files**: Prevents log files from growing too large (10MB max per file, 5 backup files)
- **Systemd compatibility**: Optimized logging for systemd journal integration
- **PM2 compatibility**: Proper formatting when running under PM2 process manager

### Log File Location

- Default log file: `logs/jakey_selfbot.log`
- Log files are automatically rotated when they reach 10MB
- Up to 5 backup log files are retained

### Log Format

- Console logs include colors and detailed timestamps when run directly
- Systemd journal logs use optimized format without excessive detail
- File logs include full timestamps and all debugging information

### Configuration

Logging is configured in `main.py` and can be customized:

```
setup_logging(
    level="INFO",                    # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    log_to_file=True,                # Enable file logging
    log_file_path="logs/jakey_selfbot.log",  # Log file path
    max_file_size=10*1024*1024,      # Max file size before rotation (10MB)
    backup_count=5                   # Number of backup files to keep
)
```

## Gender Role Recognition

Jakey supports intelligent gender role recognition based on Discord roles. By configuring role-to-gender mappings, Jakey automatically detects users' genders and uses appropriate pronouns in conversations.

**Features**:

- Automatic gender detection from Discord roles
- Support for male, female, and neutral pronouns
- Real-time role change detection
- Integration with memory system for consistency

**Configuration**:

- Environment variable: `GENDER_ROLE_MAPPINGS=male:123456789,female:987654321,neutral:111222333`
- Admin commands: `%set_gender_roles`, `%show_gender_roles`
- Full documentation: [Gender Roles](docs/GENDER_ROLES.md)

## Reaction Role System

Jakey includes a comprehensive reaction role system for automated role assignment through emoji reactions.

**Features**:

- Message-based role assignment
- Emoji-triggered role management
- Admin-only configuration
- Real-time role updates

**Commands**:

- `%add_reaction_role` - Add reaction role to message
- `%remove_reaction_role` - Remove reaction role
- `%list_reaction_roles` - View all reaction roles

**Documentation**: [Reaction Roles](docs/REACTION_ROLES.md)

## MCP Memory Server

Jakey optionally integrates with an external memory service using the MCP protocol:

- **HTTP-based API**: RESTful endpoints for memory operations
- **Dynamic Port Assignment**: Automatic detection of available ports
- **Health Monitoring**: Built-in health check endpoints
- **Persistent Storage**: Data persistence across bot restarts

**Configuration**:

- `MCP_MEMORY_ENABLED=true` in `.env` to enable
- `MCP_PORT` to specify port (defaults to dynamic assignment)
- Start with `./start_mcp_server.sh`

## Running the Bot

### Standard Startup

```bash
./jakey.sh
```

Starts bot with MCP memory server, monitoring, and proper error handling.

### Direct Python Startup

```bash
python main.py
```

Simple startup without additional services.

### Startup Without MCP Server

```bash
./jakey.sh --skip-mcp
```

Start without memory server.

### MCP Memory Server Only

```bash
./start_mcp_server.sh
```

Start memory server independently with dynamic port assignment.

### PM2 Process Management (Recommended for Production)

```bash
pm2 start pm2-ecosystem.yml          # Start all processes
pm2 reload jakey-self-bot            # Reload bot after code changes
pm2 logs jakey-self-bot              # View bot logs
pm2 stop pm2-ecosystem.yml           # Stop all processes
```

### Systemd Service

Install as a systemd service:

```bash
./setup_systemd.sh
```

Control service:

```bash
./service_control.sh start  # Start service
./service_control.sh stop   # Stop service
./service_control.sh status # Check status
```

Check bot and service status:

```bash
./check_status.sh
```

This starts the bot with MCP memory server, monitoring, and proper error handling.

### Direct Python Startup

```bash
python main.py
```

Simple startup without additional services.

### Startup Without MCP Server

```bash
./jakey.sh --skip-mcp
```

Start without the memory server.

### Systemd Service

Install as a systemd service:

```bash
./setup_systemd.sh
```

Control the service:

```bash
./service_control.sh start  # Start service
./service_control.sh stop   # Stop service
./service_control.sh status # Check status
```

Check bot and service status:

```bash
./check_status.sh
```

## Database Management

Jakey uses SQLite for persistent storage:

- **Location**: `data/jakey.db` (configurable via `DATABASE_PATH`)
- **Operations**: Async with connection pooling
- **Tables**: Conversations, user preferences, tip.cc transactions, airdrop records

### Database Utilities

```bash
python utils/flush_db.py  # Clear all data from database
```

## Testing

Run all tests with:

```bash
python -m tests.test_runner
```

Or run individual test files:

```bash
python -m tests.test_<name>
```

Run specific test method:

```bash
python -m unittest tests.test_<name>.TestClassName.test_method_name
```

### MCP Memory Tests

```bash
python -m tests.test_mcp_memory_integration
```

### Test Categories

- **Unit Tests**: Core functionality, commands, database operations
- **Integration Tests**: API integration, tool system, AI providers
- **MCP Memory Tests**: Client/server integration, fallback behavior, rate limiting

### Test Results

- **Total Tests**: 81 (including 10 MCP integration tests)
- **Status**: ✅ All passing
- **Coverage**: Core functionality, commands, database, tools, API integration, and MCP memory system
- **Performance**: Fast execution with comprehensive error handling

## Dependencies

### Core Requirements

- `discord.py-self`: Discord self-bot framework (NOT regular discord.py)
- `requests`: HTTP client for API calls
- `beautifulsoup4`: HTML parsing for web content
- `python-dotenv`: Environment variable management
- `aiohttp`: Async HTTP client
- aiosqlite: Async SQLite database operations
- pytz: Timezone handling for time/date commands

### AI APIs Used

- Designed for free-to-use AI models and APIs
- Pollinations API: Primary text generation and image creation
- OpenRouter API: Fallback AI provider
- Arta API: Professional artistic image generation
- CoinMarketCap API: Cryptocurrency prices
- SearXNG: Self-hosted web search
- tip.cc API: Cryptocurrency tipping and balance tracking

## Documentation

For detailed information about specific features and commands, see documentation in `docs/` directory:

- [Command Reference](docs/COMMANDS.md) - Complete list of all 35 commands
- [Image Generation](docs/ARTA_IMAGE_GENERATION.md) - Detailed information about artistic image generation
- [Airdrop Claiming](docs/AIRDROP_CLAIMING.md) - Airdrop configuration and usage
- [tip.cc Integration](docs/TIPCC_INTEGRATION.md) - Cryptocurrency tipping features
- [Reaction Roles](docs/REACTION_ROLES.md) - Automated role assignment system
- [Gender Roles](docs/GENDER_ROLES.md) - Gender recognition and pronoun system
- [API Documentation](docs/POLLINATIONS_API.md) - Information about AI APIs used
- [Memory System](docs/MEMORY_SYSTEM.md) - User memory and preference storage
- [MCP Memory](docs/MCP_MEMORY_ROADMAP.md) - MCP memory server architecture and security
- [Configuration](docs/CONFIGURATION.md) - Detailed setup and configuration guide
- [Production Status](docs/PRODUCTION_STATUS.md) - Current production deployment status
- [And many more...](docs/)

## Development Guidelines

- Follow [CLAUDE.md](CLAUDE.md) development guidelines for working with codebase
- Follow [AGENTS.md](AGENTS.md) guidelines for agentic coding agents
- Use proper startup scripts for development
- Maintain bot's unique personality while adding new features
- Ensure all new features have proper error handling and logging
- **CRITICAL**: This project uses discord.py-self, NOT regular discord.py - never add `intents=` parameter

## License

This project is for educational and personal use only.

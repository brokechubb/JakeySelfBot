# Jakey - Project Summary

## Overview

Jakey is a Discord self-bot with advanced AI integration, professional artistic image generation, and comprehensive utility tools. The bot features a distinctive degenerate gambling personality and provides extensive cryptocurrency tipping, gambling utilities, and AI-powered responses.

## Current Status

- **Production Ready**: ✅ All systems operational
- **Tests**: 44/44 passing (71 total tests with comprehensive coverage)
- **Commands**: 22 registered and functional
- **Tools**: 12 AI tools with function calling capabilities
- **APIs**: All external services configured and working

## Core Features

### AI Integration

- Natural language conversations with degenerate gambling personality
- Professional artistic image generation with 49 styles and 9 aspect ratios
- Text-to-speech conversion with multiple voice options
- Advanced tool usage for web search, crypto prices, calculations, and more
- Intelligent memory system for user preferences and facts
- Real-time web search with self-hosted SearXNG

### tip.cc Integration

- **Comprehensive Balance Tracking**: Automatic tracking of all cryptocurrency balances with USD value conversion
- **Transaction History**: Detailed logging of all tips, airdrops, deposits, and withdrawals
- **Smart Command Sending**: Properly formatted tip.cc commands
- **Earnings Statistics**: Track tips sent/received, airdrop winnings, and net profit
- **Multi-Currency Support**: Handle all supported cryptocurrencies with real-time price conversion

### Airdrop System

- Automated claiming of various cryptocurrency airdrops
- Support for standard, trivia, math, phrase drops, and red packets
- Configurable delays and participation controls
- Smart retry logic with timeout protection
- Enhanced tracking of entries and winnings

### Utility Tools

- Crypto price checking with CoinMarketCap API
- Currency conversion and financial calculations
- Mathematical calculations with safe evaluation
- Web search capabilities with self-hosted SearXNG
- Bonus schedule information for gambling sites
- User memory and preference storage
- Keno number generation with visual 8x5 board
- Random Indian name and address generator

## Command Structure (22 Total)

### Core Commands (6)

- `%help` - Comprehensive help information
- `%ping` - Bot connectivity check
- `%stats` - Performance metrics
- `%model [model]` - AI model management (admin only)
- `%models` - List available text models
- `%imagemodels` - List 49 artistic styles

### AI & Media Commands (3)

- `%image <prompt>` - Professional image generation
- `%audio <text>` - Text-to-speech conversion
- `%analyze <url> [prompt]` - Image analysis

### Memory & User Commands (2)

- `%remember <type> <info>` - Store user information
- `%friends` - List Jakey's friends

### Gambling & Utility Commands (7)

- `%rigged` - Classic Jakey response
- `%wen <item>` - Bonus schedule information
- `%keno` - Keno number generator with visual board
- `%airdropstatus` - Airdrop configuration
- `%channelstats` - Channel conversation statistics
- `%ind_addr` - Random Indian name/address generator

### tip.cc Commands (Admin Only) (3)

- `%bal` / `%bals` - Balance tracking
- `%transactions [limit]` - Transaction history
- `%tipstats` - Comprehensive tip statistics

### Admin Commands (2)

- `%userinfo [user]` - User information
- `%clearhistory [user]` - Clear conversation history
- `%clearallhistory` - Clear all history
- `%clearchannelhistory` - Clear channel history

## Architecture

### Core Components

- **Main Entry Point**: `main.py` with dependency injection and graceful shutdown
- **Bot Client**: `bot/client.py` with self-bot command processing and rate limiting
- **Command System**: `bot/commands.py` with 22 registered commands
- **AI Integration**: `ai/` directory with Pollinations and Arta API clients
- **Database Layer**: `storage/database.py` with SQLite and async operations
- **Tool System**: `tools/tool_manager.py` with dynamic tool registration
- **Image Generation**: `media/image_generator.py` with Arta API integration

### Configuration

- Environment variables in `.env` file
- Discord token and presence settings
- AI model preferences and API keys
- Airdrop claiming behavior and rate limiting
- Welcome message configuration
- Tip thank you message settings
- Admin user IDs for restricted commands

### Dependencies

- `discord.py-self`: Discord self-bot framework
- `requests`: HTTP client for API calls
- `beautifulsoup4`: HTML parsing for web content
- `python-dotenv`: Environment variable management
- `aiohttp`: Async HTTP client
- Self-hosted SearXNG for reliable web search

## Development

### Running the Bot

```bash
./jakey.sh
# or
python main.py
```

### Testing

```bash
python -m tests.test_runner
# or individual tests
python -m tests.test_<name>
```

### Development Commands

- Create venv: `python -m venv venv`
- Activate: `source venv/bin/activate`
- Install: `pip install -r requirements.txt`

## Infrastructure

### Self-Hosted Services

- **SearXNG**: Fast, reliable web search with multiple engine support (Google, Bing, DuckDuckGo, Brave)
- **Local Caching**: Optimized search performance with fallback capabilities
- **No External Dependencies**: Eliminates broken public service dependencies

### Error Handling

- Comprehensive logging with colored output
- Rate limiting with exponential backoff
- NaN value checking for Discord latency
- Graceful degradation for API failures
- File locking for single-instance enforcement

## Security & Reliability

- Admin command restrictions with configurable user IDs
- Rate limiting to prevent API abuse
- Secure configuration management
- Graceful shutdown handling
- Connection retry logic with exponential backoff
- Transaction safety for database operations

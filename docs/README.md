# Jakey Self-Bot Documentation

Comprehensive documentation for Jakey, the Discord self-bot with AI capabilities, crypto tools, and gambling features.

## Documentation Structure

### Core Documentation

- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Project overview and status
- [COMMANDS.md](COMMANDS.md) - Command reference (35 commands)
- [PRODUCTION_STATUS.md](PRODUCTION_STATUS.md) - Production readiness and tests

### Feature Documentation

- [TIPCC_INTEGRATION.md](TIPCC_INTEGRATION.md) - Crypto tipping and balance tracking
- [ARTA_IMAGE_GENERATION.md](ARTA_IMAGE_GENERATION.md) - Artistic image generation (49 styles)
- [AIRDROP_CLAIMING.md](AIRDROP_CLAIMING.md) - Automated airdrop claiming
- [AIRDROP_SERVER_WHITELIST.md](AIRDROP_SERVER_WHITELIST.md) - Server whitelist configuration
- [TRIVIA_SYSTEM.md](TRIVIA_SYSTEM.md) - Trivia database and auto-answering system
- [KENO_FEATURE.md](KENO_FEATURE.md) - Keno number generation
- [CRYPTO_PRICE.md](CRYPTO_PRICE.md) - Cryptocurrency price integration

### Technical Documentation

- [POLLINATIONS_API.md](POLLINATIONS_API.md) - AI API integration
- [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) - User memory storage
- [MCP_MEMORY_SECURITY.md](MCP_MEMORY_SECURITY.md) - Memory system security
- [LOGGING.md](LOGGING.md) - Logging configuration

### Role Management

- [REACTION_ROLES.md](REACTION_ROLES.md) - Reaction role system
- [GENDER_ROLES.md](GENDER_ROLES.md) - Gender role recognition

### Additional Features

- [WELCOME_MESSAGES.md](WELCOME_MESSAGES.md) - AI welcome messages
- [TIP_THANK_YOU_FEATURE.md](TIP_THANK_YOU_FEATURE.md) - Auto thank you messages
- [TIME_DATE_FEATURES.md](TIME_DATE_FEATURES.md) - Time and date commands
- [MODERATION_TOOLS.md](MODERATION_TOOLS.md) - AI-powered moderation tools

## Quick Reference

### Available Commands (35 Total)

- **Core**: `%help`, `%ping`, `%stats`, `%model`, `%models`, `%imagemodels`, `%time`, `%date`
- **AI/Media**: `%image`, `%audio`, `%analyze`, `%aistatus`
- **Memory**: `%remember`, `%friends`
- **Gambling**: `%rigged`, `%wen`, `%keno`, `%airdropstatus`, `%channelstats`, `%ind_addr`
- **Financial (Admin)**: `%bal`, `%transactions`, `%tipstats`, `%tip`, `%airdrop`
- **Admin**: `%userinfo`, `%clearhistory`, `%clearallhistory`, `%clearchannelhistory`
- **Roles**: `%set_gender_roles`, `%show_gender_roles`, `%add_reaction_role`, `%remove_reaction_role`, `%list_reaction_roles`

### Key Features

- Professional image generation with 49 artistic styles
- Self-hosted SearXNG web search
- Comprehensive tip.cc integration with balance tracking
- Automated airdrop claiming with server whitelist support
- AI-powered welcome messages
- Rate-limited API integration
- Secure admin command system

## Getting Started

1. **Setup**: Configure your `.env` file with required API keys
2. **Dependencies**: Install with `pip install -r requirements.txt`
3. **Run**: Start with `python main.py` or `./jakey.sh`
4. **Test**: Verify with `python -m tests.test_runner`

## Architecture Overview

- **Main Entry Point**: `main.py` with dependency injection
- **Bot Client**: `bot/client.py` with self-bot functionality
- **Commands**: `bot/commands.py` with 35 registered commands
- **AI Integration**: `ai/` directory with API clients
- **Database**: `data/database.py` with SQLite operations
- **Tools**: `tools/tool_manager.py` with function calling
- **Media**: `media/` directory with image generation

## Support

For issues or questions, check individual docs or run tests:

```bash
python -m tests.test_runner
```

Documentation reflects current production state with 81 passing tests.

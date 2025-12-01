# Jakey Self-Bot Documentation

Welcome to the comprehensive documentation for Jakey, the degenerate gambling Discord self-bot. This documentation covers all features, commands, and integration capabilities.

## Documentation Structure

### Core Documentation

- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Complete project overview and current status
- [COMMANDS.md](COMMANDS.md) - Detailed command reference (22 commands)
- [PRODUCTION_STATUS.md](PRODUCTION_STATUS.md) - Production readiness and test results

### Feature-Specific Documentation

- [TIPCC_INTEGRATION.md](TIPCC_INTEGRATION.md) - Cryptocurrency tipping and balance tracking
- [ARTA_IMAGE_GENERATION.md](ARTA_IMAGE_GENERATION.md) - Professional artistic image generation (49 styles)
- [AIRDROP_CLAIMING.md](AIRDROP_CLAIMING.md) - Automated airdrop claiming system
- [KENO_FEATURE.md](KENO_FEATURE.md) - Keno number generation with visual board

### Technical Documentation

- [POLLINATIONS_API.md](POLLINATIONS_API.md) - AI API integration details
- [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) - User memory and preference storage
- [LOGGING.md](LOGGING.md) - Logging and error handling configuration
- [MCP_MEMORY_ROADMAP.md](MCP_MEMORY_ROADMAP.md) - MCP Memory Server integration roadmap

### Role Management Documentation

- [REACTION_ROLES.md](REACTION_ROLES.md) - Reaction role system for automated role assignment
- [GENDER_ROLES.md](GENDER_ROLES.md) - Gender role recognition and pronoun system

### Development Documentation

- [WELCOME_MESSAGES.md](WELCOME_MESSAGES.md) - AI-powered welcome message system
- [TIP_THANK_YOU_FEATURE.md](TIP_THANK_YOU_FEATURE.md) - Automatic thank you message system
- [TIME_DATE_FEATURES.md](TIME_DATE_FEATURES.md) - Time and date command features

## Quick Reference

### Available Commands (35 Total)

- **Core**: `%help`, `%ping`, `%stats`, `%model`, `%models`, `%imagemodels`, `%time`, `%date`
- **AI/Media**: `%image`, `%audio`, `%analyze`, `%aistatus`
- **Memory**: `%remember`, `%friends`
- **Gambling**: `%rigged`, `%wen`, `%keno`, `%airdropstatus`, `%channelstats`, `%ind_addr`
- **tip.cc (Admin Only)**: `%bal`, `%transactions`, `%tipstats`
- **Admin**: `%tip`, `%airdrop`, `%userinfo`, `%clearhistory`, `%clearallhistory`, `%clearchannelhistory`, `%set_gender_roles`, `%show_gender_roles`
- **Role Management**: `%add_reaction_role`, `%remove_reaction_role`, `%list_reaction_roles`

### Key Features

- Professional image generation with 49 artistic styles
- Self-hosted SearXNG web search
- Comprehensive tip.cc integration with balance tracking
- Automated airdrop claiming
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
- **Commands**: `bot/commands.py` with 22 registered commands
- **AI Integration**: `ai/` directory with API clients
- **Storage**: `storage/database.py` with SQLite operations
- **Tools**: `tools/tool_manager.py` with function calling
- **Media**: `media/` directory with image generation

## Support

For issues or questions, refer to the individual documentation files or run the test suite to verify functionality:

```bash
python -m tests.test_runner
```

All documentation reflects the current production-ready state with 44 passing tests and full feature implementation.

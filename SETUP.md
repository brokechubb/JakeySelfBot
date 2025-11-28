# JakeySelfBot Setup Guide

This guide will help you set up JakeySelfBot for your own use with your own API keys and configuration.

## Prerequisites

- Python 3.8 or higher
- A Discord account
- API keys for various services (optional but recommended for full functionality)

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/JakeySelfBot.git
cd JakeySelfBot
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Then edit the `.env` file with your own API keys and configuration:

```bash
nano .env
```

#### Required Configuration

- `DISCORD_TOKEN`: Your Discord user token (required)
- `ADMIN_USER_IDS`: Your Discord user ID for admin commands (comma-separated)

#### Optional API Keys

For full functionality, you can configure these optional services:

- `POLLINATIONS_API_TOKEN`: Pollinations.ai API token
- `OPENROUTER_API_KEY`: OpenRouter API key (fallback)
- `COINMARKETCAP_API_KEY`: CoinMarketCap API key
- `EXA_API_KEY`: Exa API key

### 5. Run the Bot

```bash
./jakey.sh
```

Or directly with Python:

```bash
python main.py
```

## Configuration Options

The bot is highly configurable through the `.env` file. Key options include:

- `DEFAULT_MODEL`: Choose between different AI models
- `MCP_MEMORY_ENABLED`: Enable/disable the memory server
- `RATE_LIMIT_*`: Configure rate limiting for API calls
- `AIRDROP_*`: Configure airdrop claiming behavior
- `WELCOME_*`: Configure welcome messages for new members
- `GUILD_BLACKLIST`: Specify servers where the bot should not respond

## Security Considerations

⚠️ **Important Security Notes:**

- Never commit your `.env` file to version control
- Keep your Discord token secure and never share it
- Regularly rotate your API keys
- The `.gitignore` file is configured to exclude sensitive files
- Only grant admin privileges to trusted users

## API Services Used

JakeySelfBot uses several external APIs:

- **Pollinations.ai**: Primary AI text/image generation
- **OpenRouter**: Fallback AI provider
- **CoinMarketCap**: Cryptocurrency price data
- **Exa**: Web search capabilities
- **SearXNG**: Self-hosted web search (uses public instances by default)

Most of these services offer free tiers that are suitable for personal use.

## Database

The bot uses SQLite for local data storage. Database files are automatically created and managed by the bot. The database stores:

- Conversation history
- User preferences
- Tip.cc transaction history
- Reminders
- Airdrop records
- User memories

## Development

To contribute to the project:

1. Create a fork of the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

Make sure to follow the existing code style and add documentation for new features.

## Troubleshooting

- If you get "token not found" errors, verify your Discord token in `.env`
- If AI features aren't working, check your API keys in `.env`
- If the bot doesn't respond, check that your user ID is in `ADMIN_USER_IDS` (for admin commands)
- Check the logs in the `logs/` directory for detailed error information
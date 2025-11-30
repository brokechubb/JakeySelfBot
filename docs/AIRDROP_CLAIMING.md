# Airdrop Claiming System

Jakey includes an automated airdrop claiming system that can participate in various types of cryptocurrency drops on Discord. The system is designed to automatically detect and claim different types of airdrops from the tip.cc bot.

## Supported Drop Types

The bot can automatically claim the following types of airdrops:

1. **Standard Airdrops** (`$airdrop`) - Clicks the claim button automatically
2. **Trivia Drops** (`$triviadrop`) - Automatically answers trivia questions
3. **Math Drops** (`$mathdrop`) - Solves basic math problems
4. **Phrase Drops** (`$phrasedrop`) - Repeats the required phrase
5. **Red Packets** (`$redpacket`) - Claims red packet rewards

## Configuration

The airdrop system can be configured through environment variables in your `.env` file:

### Delay Settings
- `AIRDROP_SMART_DELAY` (default: true) - Uses smart delay based on drop timer
- `AIRDROP_RANGE_DELAY` (default: false) - Uses random delay within a range
- `AIRDROP_DELAY_MIN` (default: 0.0) - Minimum delay in seconds
- `AIRDROP_DELAY_MAX` (default: 1.0) - Maximum delay in seconds

### Participation Controls
- `AIRDROP_IGNORE_DROPS_UNDER` (default: 0.0) - Ignore drops worth less than this amount
- `AIRDROP_IGNORE_TIME_UNDER` (default: 0.0) - Ignore drops with less than this time remaining
- `AIRDROP_IGNORE_USERS` (default: "") - Comma-separated list of user IDs to ignore
- `AIRDROP_SERVER_WHITELIST` (default: "") - Comma-separated list of server IDs where airdrops should be collected

### Drop Type Toggles
- `AIRDROP_DISABLE_AIRDROP` (default: false) - Disable standard airdrop claiming
- `AIRDROP_DISABLE_TRIVIADROP` (default: false) - Disable trivia drop claiming
- `AIRDROP_DISABLE_MATHDROP` (default: false) - Disable math drop claiming
- `AIRDROP_DISABLE_PHRASEDROP` (default: false) - Disable phrase drop claiming
- `AIRDROP_DISABLE_REDPACKET` (default: false) - Disable red packet claiming

### Typing Simulation
- `AIRDROP_CPM_MIN` (default: 200) - Minimum characters per minute for typing simulation
- `AIRDROP_CPM_MAX` (default: 310) - Maximum characters per minute for typing simulation

## How It Works

1. **Server Filtering**: Checks if the server is in the whitelist (if configured)
2. **Detection**: The bot monitors all channels it has access to for airdrop commands (`$airdrop`, `$triviadrop`, etc.)
3. **Response Waiting**: It waits for the tip.cc bot to respond with the actual drop message (up to 15 seconds)
4. **Delay Application**: Applies configured delays before claiming (smart, range, or fixed)
5. **Claim Execution**: Automatically claims the drop using appropriate methods:
   - Button clicks for standard airdrops and red packets
   - Automated responses for phrase, math, and trivia drops
6. **Retry Logic**: Implements retry logic with exponential backoff for failed interactions

## Error Handling

The system includes robust error handling:

- **Timeout Protection**: All Discord interactions have 10-second timeouts
- **Retry Logic**: Failed button clicks are retried up to 3 times with exponential backoff
- **Error Logging**: All failures are logged for debugging
- **Graceful Degradation**: System continues operating even if individual claims fail

## Requirements

- The bot must be in the same Discord server as the tip.cc bot
- The bot must have permission to read messages and send messages in drop channels
- The tip.cc bot must be active and functioning properly

## Server Whitelist

The server whitelist feature allows you to restrict airdrop collection to specific Discord servers only:

### Configuration
```bash
# Only collect airdrops in specific servers
AIRDROP_SERVER_WHITELIST=123456789012345678,987654321098765432

# Collect in all servers (default)
AIRDROP_SERVER_WHITELIST=
```

### Behavior
- **Empty whitelist**: Bot collects airdrops in all servers
- **Populated whitelist**: Bot ONLY collects in specified servers
- **Status Display**: Use `%airdrop` command to see whitelist status

### How to Get Server IDs
1. Enable Developer Mode in Discord settings
2. Right-click on server name → "Copy Server ID"

## Best Practices

1. **Rate Limiting**: Configure appropriate delays to avoid being rate-limited
2. **Channel Permissions**: Ensure the bot has proper permissions in all drop channels
3. **Monitoring**: Regularly check logs for failed claims
4. **Value Filtering**: Use `AIRDROP_IGNORE_DROPS_UNDER` to avoid claiming low-value drops
5. **Selective Participation**: Disable specific drop types that may not be worth your time
6. **Server Control**: Use the whitelist to focus on specific communities and reduce bot load
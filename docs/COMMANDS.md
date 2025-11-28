# Command Reference

This document provides detailed information about all 35 available commands in Jakey.

## Command Summary

Jakey supports 35 commands across 7 categories:

- **Core Commands** (7): Help, ping, stats, model management, time/date
- **AI & Media Commands** (4): Image generation, audio, analysis, AI status
- **Memory & User Commands** (2): User info, memory management
- **Gambling & Utility Commands** (7): Gambling tools, utilities, airdrops
- **Admin Commands** (8): Restricted to authorized users
- **tip.cc Commands** (3): Cryptocurrency tipping and balance tracking
- **Role Management Commands** (4): Reaction roles and gender role configuration

## Enhanced Search Capabilities

Jakey's search functionality has been significantly improved:

- **Web search**: Now returns 7 results (instead of 3) for better context and more comprehensive information
- **Company research**: Provides 7 detailed results with comprehensive company information
- **Search engine**: Uses SearXNG meta-search engine with multiple search providers (Google, Bing, DuckDuckGo, Brave)
- **Content length**: Increased from 200 to 300 characters per result for richer context
- **Result quality**: Better information gathering for AI responses

## Core Commands

### %ping

Check if Jakey is alive and responsive.

**Usage**: `%ping`

**Response**: Shows latency information and confirms Jakey is running.

### %help

Show comprehensive help information about Jakey's commands.

**Usage**: `%help`

**Response**: Shows a formatted help message with all available commands and usage examples.

### %stats

Show bot statistics and performance metrics.

**Usage**: `%stats`

**Response**: Displays bot uptime, latency, user count, conversation count, and other performance metrics.

### %model [model_name] (Admin Only)

Show or set the current AI model.

**Usage**:

- `%model` - Show current model
- `%model <model_name>` - Set current model

**Examples**:

- `%model`
- `%model gemini`

**Note**: This command is restricted to admin users only.

### %models

List available AI models (summary).

**Usage**: `%models`

**Response**: Shows a summary of available text and image models.

### %imagemodels

List all available image AI models (49 artistic styles).

**Usage**: `%imagemodels`

**Response**: Shows all 49 available artistic styles for image generation.

### %time [timezone]

Display the current time for a specific timezone or default timezone.

**Usage**: `%time [timezone]`

**Examples**:

- `%time` - Current time in default timezone
- `%time EST` - Current time in Eastern Standard Time
- `%time UTC` - Current time in UTC

**Response**: Shows the current time with timezone information.

### %date [timezone]

Display the current date for a specific timezone or default timezone.

**Usage**: `%date [timezone]`

**Examples**:

- `%date` - Current date in default timezone
- `%date PST` - Current date in Pacific Standard Time

**Response**: Shows the current date with timezone information.

## AI and Media Commands

### %image <prompt>

Generate an image using Arta API with artistic styles and aspect ratios.

**Usage**: `%image <prompt>`

**Examples**:

- `%image Fantasy Art a degenerate gambler at a slot machine`
- `%image Vincent Van Gogh a poker table with chips`
- `%image 16:9 cinematic a slot machine winning big`

**Response**: Returns an image URL with professional artistic rendering.

**Note**: Supports 49 artistic styles and 9 aspect ratios for enhanced image generation.

### %audio <text>

Generate audio from text using Pollinations API.

**Usage**: `%audio <text>`

**Examples**:

- `%audio Hello, I'm Jakey the degenerate gambler`
- `%audio Everything is rigged, especially Eddie's code`

**Response**: Returns audio file with generated speech.

### %analyze <image_url> [prompt]

Analyze an image using Pollinations API vision capabilities.

**Usage**: `%analyze <image_url> [prompt]`

**Examples**:

- `%analyze https://example.com/image.jpg`
- `%analyze https://example.com/image.jpg Describe this gambling scene`

**Response**: Returns detailed analysis of the image content.

### %aistatus

Display the current status of AI systems and APIs.

**Usage**: `%aistatus`

**Response**: Shows status of Pollinations API, OpenRouter fallback, and other AI services.

## Memory and User Commands

### %remember <type> <info>

Remember important information about the user.

**Usage**: `%remember <type> <info>`

**Examples**:

- `%remember favorite_team Dallas Cowboys`
- `%remember gambling_preference Slots and plinko`
- `%remember location Las Vegas`

**Response**: Confirms the information has been stored in memory.

### %friends

List Jakey's friends (self-bot specific feature).

**Usage**: `%friends`

**Response**: Shows list of friends (if available).

## Gambling and Utility Commands

### %rigged

Classic Jakey response.

**Usage**: `%rigged`

**Response**: "💀 Everything's rigged bro, especially Eddie's code"

### %wen <item>

Get bonus schedule information for gambling sites.

**Usage**: `%wen <item>`

**Examples**:

- `%wen monthly`
- `%wen stake`
- `%wen shuffle`

**Response**: Shows relevant bonus schedule information.

### %keno

Generate random Keno numbers (3-10 numbers from 1-40) with 8x5 visual board.

**Usage**: `%keno [count]`

**Examples**:

- `%keno` - Generate 10 random numbers
- `%keno 5` - Generate 5 random numbers

**Response**: Shows visual Keno board with selected numbers highlighted.

### %airdropstatus

Show current airdrop configuration and status.

**Usage**: `%airdropstatus`

**Response**: Shows airdrop settings, rates, and current status.

### %channelstats

Show conversation statistics for the current channel.

**Usage**: `%channelstats`

**Response**: Shows message count, user activity, and other channel statistics.

### %ind_addr

Generate a random Indian name and address.

**Usage**: `%ind_addr`

**Response**: Returns randomly generated Indian name and address information.

## tip.cc Commands

### %bal / %bals

Check tip.cc balances and click button on response.

**Usage**: `%bal` or `%bals`

**Response**: Shows balance information with interactive button for detailed breakdown.

### %transactions [limit]

Show recent tip.cc transaction history.

**Usage**: `%transactions [limit]`

**Examples**:

- `%transactions` - Show last 10 transactions
- `%transactions 25` - Show last 25 transactions

**Response**: Shows recent transaction history with timestamps and values.

### %tipstats

Show tip.cc statistics and earnings.

**Usage**: `%tipstats`

**Response**: Shows comprehensive statistics including tips sent/received, airdrop winnings, and net profit.

## Admin Commands

### %userinfo [user] (Admin Only)

Get information about a user.

**Usage**:

- `%userinfo` - Get info about yourself
- `%userinfo @user` - Get info about another user

**Response**: Shows user information.

**Note**: This command is restricted to admin users only.

### %clearhistory [user] (Admin Only)

Clear conversation history for a user.

**Usage**:

- `%clearhistory` - Clear your own history
- `%clearhistory @user` - Clear another user's history (admin only)

**Note**: Clearing another user's history requires admin privileges.

### %clearallhistory (Admin Only)

Clear ALL conversation history for all users.

**Usage**: `%clearallhistory`

**Note**: This command is restricted to admin users only and should be used with caution.

### %clearchannelhistory (Admin Only)

Clear conversation history for the current channel.

**Usage**: `%clearchannelhistory`

**Note**: This command is restricted to admin users only.

### %tip <recipient> <amount> <currency> [message] (Admin Only)

Send a tip to a user using tip.cc.

**Usage**: `%tip <recipient> <amount> <currency> [message]`

**Examples**:

- `%tip @user 100 DOGE`
- `%tip @user 5 USD Thanks for the help`

**Response**: Sends properly formatted tip command to tip.cc bot.

**Note**: This command is restricted to admin users only.

### %airdrop <amount> <currency> <duration> (Admin Only)

Create an airdrop using tip.cc.

**Usage**: `%airdrop <amount> <currency> <duration>`

**Examples**:

- `%airdrop 1000 DOGE 5m`
- `%airdrop 10 USD 10m`

**Response**: Creates airdrop with specified parameters.

**Note**: This command is restricted to admin users only.

### %set_gender_roles <gender:role_id,...> (Admin Only)

Set gender role mappings for automatic pronoun detection.

**Usage**: `%set_gender_roles <gender:role_id,...>`

**Examples**:

- `%set_gender_roles male:123456789,female:987654321,neutral:111222333`

**Response**: Updates gender role configuration for pronoun detection.

**Note**: This command is restricted to admin users only.

### %show_gender_roles (Admin Only)

Display current gender role mappings.

**Usage**: `%show_gender_roles`

**Response**: Shows configured gender role mappings and detected roles.

**Note**: This command is restricted to admin users only.

## Role Management Commands

### %add_reaction_role <message_id> <emoji> <role> (Admin Only)

Add a reaction role to a message.

**Usage**: `%add_reaction_role <message_id> <emoji> <role>`

**Examples**:

- `%add_reaction_role 123456789012345678 🎮 Gamer`

**Response**: Adds reaction role configuration for the specified message.

**Note**: This command is restricted to admin users only.

### %remove_reaction_role <message_id> <emoji> (Admin Only)

Remove a reaction role from a message.

**Usage**: `%remove_reaction_role <message_id> <emoji>`

**Examples**:

- `%remove_reaction_role 123456789012345678 🎮`

**Response**: Removes the reaction role configuration.

**Note**: This command is restricted to admin users only.

### %list_reaction_roles (Admin Only)

List all configured reaction roles.

**Usage**: `%list_reaction_roles`

**Response**: Shows all reaction role configurations with message IDs, emojis, and roles.

**Note**: This command is restricted to admin users only.

## Best Practices

1. **Use appropriate prefixes**: All commands start with `%`
2. **Provide complete information**: Some commands require specific parameters
3. **Check responses**: Commands provide feedback on success or failure
4. **Respect rate limits**: Avoid spamming commands rapidly

## Command Availability

All commands are available in:

- Direct messages to Jakey
- Servers where Jakey is present (when mentioned or replied to)

## Admin Configuration

The following commands are restricted to admin users only:

- `%model [model_name]` - Show or set current AI model
- `%userinfo [user]` - Get information about a user
- `%clearhistory [user]` - Clear conversation history for a user
- `%clearallhistory` - Clear ALL conversation history
- `%clearchannelhistory` - Clear conversation history for current channel
- `%tip <recipient> <amount> <currency> [message]` - Send tips
- `%airdrop <amount> <currency> <duration>` - Create airdrops

To configure admin users, set `ADMIN_USER_IDS` in your `.env` file with comma-separated Discord user IDs.

## Error Handling

Commands include proper error handling and will inform users of:

- Missing parameters
- Invalid inputs
- API errors
- Rate limiting
- Permission issues

## Examples

### Core Commands

```
%ping
%model gemini
%models
%imagemodels
%stats
%help
```

### AI & Media Commands

```
%image Fantasy Art a degenerate gambler at a slot machine
%image 16:9 cinematic a slot machine winning big
%audio Hello, I'm Jakey the degenerate gambler
%analyze https://example.com/image.jpg Describe this scene
```

### Memory & User Commands

```
%remember favorite_team Dallas Cowboys
%remember gambling_preference Slots and plinko
%friends
```

### Gambling & Utility Commands

```
%rigged
%wen monthly
%wen stake weekly
%keno
%keno 5
%airdropstatus
%channelstats
%ind_addr
```

### tip.cc Commands

```
%bal
%bals
%transactions
%transactions 25
%tipstats
```

### Admin Commands

```
%userinfo
%userinfo @user
%clearhistory
%clearallhistory
%clearchannelhistory
%tip @user 100 DOGE
%airdrop 1000 DOGE 5m
```

# Command Reference

This document provides detailed information about all 51 available commands in Jakey.

## Command Summary

Jakey supports 51 commands across 10 categories:

- **Core Commands** (6): Help, admin help, ping, stats, time/date
- **AI Model Commands** (5): Model management, AI status, fallback status
- **Memory Commands** (5): Memory search, status, clearing, and remember
- **AI & Media Commands** (3): Image generation, audio, image analysis
- **User & Channel Commands** (5): User info, friends, history management
- **Gambling & Utility Commands** (4): Gambling tools and utilities
- **tip.cc Commands** (9): Cryptocurrency tipping, balances, and tracking
- **Trivia Commands** (6): Trivia database management and search
- **Role & Keyword Management Commands** (9): Reaction roles, gender roles, keywords
- **System Commands** (1): Cache management

## Enhanced Search Capabilities

Jakey's search functionality has been significantly improved:

- **Web search**: Now returns 7 results (instead of 3) for better context and more comprehensive information
- **Company research**: Provides 7 detailed results with comprehensive company information
- **Search engine**: Uses SearXNG meta-search engine with multiple search providers (Google, Bing, DuckDuckGo, Brave)
- **Content length**: Increased from 200 to 300 characters per result for richer context
- **Result quality**: Better information gathering for AI responses

---

## Core Commands

### %ping

Check if Jakey is alive and responsive.

**Usage**: `%ping`

**Response**: Shows latency information and confirms Jakey is running.

### %help

Show comprehensive help information about Jakey's commands.

**Usage**: `%help`

**Response**: Shows a formatted help message with all available commands and usage examples for regular users.

### %adminhelp (Admin Only)

Show comprehensive help information about admin-only commands.

**Usage**: `%adminhelp`

**Response**: Shows a formatted help message with all admin commands including AI management, user/channel management, reaction roles, gender roles, keywords, tip.cc, and trivia commands.

**Note**: This command is restricted to admin users only.

### %stats

Show bot statistics and performance metrics.

**Usage**: `%stats`

**Response**: Displays bot uptime, latency, user count, conversation count, and other performance metrics.

### %time [timezone]

Display the current time for a specific timezone or default timezone.

**Usage**: `%time [timezone]`

**Examples**:

- `%time` - Current time in default timezone
- `%time EST` - Current time in Eastern Standard Time
- `%time UTC` - Current time in UTC
- `%time Europe/London` - Current time in London

**Response**: Shows the current time with timezone information.

### %date [timezone]

Display the current date for a specific timezone or default timezone (alias for time command).

**Usage**: `%date [timezone]`

**Examples**:

- `%date` - Current date in default timezone
- `%date PST` - Current date in Pacific Standard Time

**Response**: Shows the current date with timezone information.

---

## AI Model Commands

### %model [model_name] (Admin Only)

Show or set the current AI model.

**Usage**:

- `%model` - Show current model
- `%model <model_name>` - Set current model

**Examples**:

- `%model`
- `%model gemini`

**Note**: This command is restricted to admin users only.

### %models (Admin Only)

List all available AI models with enhanced information.

**Usage**: `%models`

**Response**: Shows all available text, image, and audio models with descriptions and usage instructions.

**Note**: This command is restricted to admin users only.

### %imagemodels (Admin Only)

List all available image AI models (49 artistic styles).

**Usage**: `%imagemodels`

**Response**: Shows all 49 available artistic styles for image generation.

**Note**: This command is restricted to admin users only.

### %aistatus (Admin Only)

Display the current status of AI systems and APIs.

**Usage**: `%aistatus`

**Response**: Shows status of Pollinations API, OpenRouter fallback, and other AI services.

**Note**: This command is restricted to admin users only.

### %fallbackstatus (Admin Only)

Show OpenRouter fallback restoration status.

**Usage**: `%fallbackstatus`

**Response**: Shows current provider, current model, auto-restore settings, restore timeout, fallback duration, time until restore, and progress percentage.

**Note**: This command is restricted to admin users only.

---

## Memory Commands

### %memories [query]

Search your memories that Jakey has saved from conversations.

**Usage**: `%memories [query]`

**Examples**:

- `%memories` - Show all your stored memories
- `%memories favorite` - Search memories containing "favorite"
- `%memories gambling` - Search memories about gambling

**Response**: Shows grouped memories by type with categories and information.

### %remember <type> <info>

Remember important information about the user.

**Usage**: `%remember <type> <info>`

**Examples**:

- `%remember favorite_team Dallas Cowboys`
- `%remember gambling_preference Slots and plinko`
- `%remember location Las Vegas`

**Response**: Confirms the information has been stored in memory.

### %clearmemories (Admin Only)

Clear all your stored memories (cannot be undone).

**Usage**: `%clearmemories`

**Response**: Clears all memories associated with the user and confirms deletion with count.

**Note**: This command is restricted to admin users only.

### %memorystatus (Admin Only)

Show memory statistics and system status.

**Usage**: `%memorystatus`

**Response**: Displays memory system configuration (auto-extraction, auto-cleanup, max age), user memory count broken down by type, and system health status with backend availability.

**Note**: This command is restricted to admin users only.

---

## AI & Media Commands

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
- `%analyze` (with image attachment) - Analyze attached image

**Response**: Returns detailed analysis of the image content.

---

## User & Channel Commands

### %friends

List Jakey's friends (self-bot specific feature).

**Usage**: `%friends`

**Response**: Shows list of friends (if available).

### %userinfo [user] (Admin Only)

Get information about a user.

**Usage**:

- `%userinfo` - Get info about yourself
- `%userinfo @user` - Get info about another user

**Response**: Shows user information.

**Note**: This command is restricted to admin users only.

### %clearhistory [user]

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

### %channelstats (Admin Only)

Show conversation statistics for the current channel.

**Usage**: `%channelstats`

**Response**: Shows message count, user activity, and other channel statistics.

**Note**: This command is restricted to admin users only.

---

## Gambling & Utility Commands

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
- `%wen payout`

**Response**: Shows relevant bonus schedule information.

### %keno [count]

Generate random Keno numbers (3-10 numbers from 1-40) with 8x5 visual board.

**Usage**: `%keno [count]`

**Examples**:

- `%keno` - Generate 10 random numbers
- `%keno 5` - Generate 5 random numbers

**Response**: Shows visual Keno board with selected numbers highlighted.

### %ind_addr

Generate a random Indian name and address.

**Usage**: `%ind_addr`

**Response**: Returns randomly generated Indian name and address information.

---

## tip.cc Commands

### %bal / %bals (Admin Only)

Check tip.cc balances and click button on response.

**Usage**: `%bal` or `%bals`

**Response**: Shows balance information with interactive button for detailed breakdown.

**Note**: This command is restricted to admin users only.

### %confirm (Admin Only)

Manually check for and click Confirm button on tip.cc confirmation messages.

**Usage**: `%confirm`

**Response**: Searches for and interacts with tip.cc confirmation messages.

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

**Usage**: `%airdrop <amount> <currency> [for] <duration>`

**Examples**:

- `%airdrop 1000 DOGE 5m`
- `%airdrop 10 USD 10m`

**Response**: Creates airdrop with specified parameters.

**Note**: This command is restricted to admin users only.

### %transactions [limit] (Admin Only)

Show recent tip.cc transaction history.

**Usage**: `%transactions [limit]`

**Examples**:

- `%transactions` - Show last 10 transactions
- `%transactions 25` - Show last 25 transactions

**Response**: Shows recent transaction history with timestamps and values.

**Note**: This command is restricted to admin users only.

### %tipstats (Admin Only)

Show tip.cc statistics and earnings.

**Usage**: `%tipstats`

**Response**: Shows comprehensive statistics including tips sent/received, airdrop winnings, and net profit.

**Note**: This command is restricted to admin users only.

### %clearstats (Admin Only)

Clear all tip.cc transaction history and statistics.

**Usage**: `%clearstats`

**Response**: Clears all tip.cc transactions and balances for a fresh start.

**Note**: This command is restricted to admin users only and cannot be undone.

### %airdropstatus (Admin Only)

Show current airdrop configuration and status.

**Usage**: `%airdropstatus`

**Response**: Shows airdrop settings (presence, smart delay, range delay, CPM), ignore thresholds, server whitelist status, disabled features, and filters.

**Note**: This command is restricted to admin users only.

---

## Message Queue Commands (Admin Only)

### %queuestatus (Admin Only)

Show message queue status and statistics.

**Usage**: `%queuestatus`

**Response**: Shows queue statistics including:

- Total messages, pending, processing, completed, failed, dead letter counts
- Oldest message age
- Processing stats (processed count, success rate, average time, rate)
- Health status and active alerts

**Note**: This command is restricted to admin users only. Requires MESSAGE_QUEUE_ENABLED=true.

### %processqueue (Admin Only)

Manually trigger queue processing.

**Usage**: `%processqueue`

**Response**: Processes one batch of messages from the queue and reports how many were processed.

**Note**: This command is restricted to admin users only.

---

## Trivia Commands

### %triviacats

List all available trivia categories.

**Usage**: `%triviacats`

**Response**: Shows all trivia categories with question counts and cache status (🟢 = cached, 🔴 = not cached).

### %triviasearch <query> [category]

Search for trivia questions.

**Usage**: `%triviasearch <query> [category]`

**Examples**:

- `%triviasearch Beatles`
- `%triviasearch video games Entertainment`

**Response**: Shows matching trivia questions with answers.

### %triviastats (Admin Only)

Show trivia database statistics and health.

**Usage**: `%triviastats`

**Response**: Shows database health status, health score, total categories, total questions, total attempts, and top categories.

**Note**: This command is restricted to admin users only.

### %seedtrivia (Admin Only)

Seed trivia database with questions from external sources.

**Usage**: `%seedtrivia`

**Response**: Seeds the database with questions from multiple categories including Music, Anime, Video Games, Film, Television, Books, Science, Geography, History, and more.

**Note**: This command is restricted to admin users only. May take several minutes to complete.

### %addtrivia <category> <question> <answer> (Admin Only)

Add a custom trivia question to the database.

**Usage**: `%addtrivia <category> <question> <answer>`

**Examples**:

- `%addtrivia "General Knowledge" "What is 2+2?" "4"`

**Response**: Confirms the question was added with its ID.

**Note**: This command is restricted to admin users only.

### %triviatest (Admin Only)

Test trivia system with sample questions.

**Usage**: `%triviatest`

**Response**: Runs test cases against the trivia database and reports pass/fail status.

**Note**: This command is restricted to admin users only.

---

## Role Management Commands

### %add_reaction_role <message_id> <emoji> <role> (Admin Only)

Add a reaction role to a message.

**Usage**: `%add_reaction_role <message_id> <emoji> <@role>`

**Examples**:

- `%add_reaction_role 123456789012345678 🎮 @Gamer`

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

### %set_gender_roles <gender:role_id,...> (Admin Only)

Set gender role mappings for automatic pronoun detection.

**Usage**: `%set_gender_roles <gender:role_id,...>`

**Examples**:

- `%set_gender_roles male:123456789,female:987654321,neutral:111222333`

**Response**: Updates gender role configuration for pronoun detection.

**Note**: This command is restricted to admin users only.

### %show_gender_roles

Display current gender role mappings.

**Usage**: `%show_gender_roles`

**Response**: Shows configured gender role mappings and detected roles.

---

## Keyword Management Commands (Admin Only)

### %add_keyword <keyword> (Admin Only)

Add a keyword that Jakey will respond to.

**Usage**: `%add_keyword <keyword>`

**Examples**:

- `%add_keyword casino`

**Response**: Confirms the keyword was added.

**Note**: This command is restricted to admin users only.

### %remove_keyword <keyword> (Admin Only)

Remove a keyword that Jakey responds to.

**Usage**: `%remove_keyword <keyword>`

**Examples**:

- `%remove_keyword casino`

**Response**: Confirms the keyword was removed.

**Note**: This command is restricted to admin users only.

### %list_keywords (Admin Only)

List all configured keywords that Jakey responds to.

**Usage**: `%list_keywords`

**Response**: Shows all configured keywords in the system with total count.

**Note**: This command is restricted to admin users only.

### %enable_keyword <keyword> (Admin Only)

Enable a previously disabled keyword.

**Usage**: `%enable_keyword <keyword>`

**Examples**:

- `%enable_keyword casino`

**Response**: Confirms the keyword was enabled.

**Note**: This command is restricted to admin users only.

### %disable_keyword <keyword> (Admin Only)

Disable a keyword without removing it.

**Usage**: `%disable_keyword <keyword>`

**Examples**:

- `%disable_keyword casino`

**Response**: Confirms the keyword was disabled.

**Note**: This command is restricted to admin users only.

---

## System Commands

### %clearcache (Admin Only)

Clear the model capabilities cache.

**Usage**: `%clearcache`

**Response**: Confirms the model capabilities cache was cleared successfully.

**Note**: This command is restricted to admin users only.

---

## Best Practices

1. **Use appropriate prefixes**: All commands start with `%`
2. **Provide complete information**: Some commands require specific parameters
3. **Check responses**: Commands provide feedback on success or failure
4. **Respect rate limits**: Avoid spamming commands rapidly
5. **Use admin commands responsibly**: Admin commands can affect all users

## Command Availability

All commands are available in:

- Direct messages to Jakey
- Servers where Jakey is present (when mentioned or replied to)

## Admin Configuration

The following commands are restricted to admin users only:

**AI & Model Management:**

- `%model [model_name]` - Show or set current AI model
- `%models` - List all available AI models
- `%imagemodels` - List all available image AI models
- `%aistatus` - Display the current status of AI systems and APIs
- `%fallbackstatus` - Show OpenRouter fallback restoration status
- `%clearcache` - Clear the model capabilities cache

**Memory & User Management:**

- `%adminhelp` - Show admin command help
- `%clearmemories` - Clear all your stored memories
- `%memorystatus` - Show memory statistics and system status
- `%userinfo [user]` - Get information about a user
- `%clearhistory [user]` - Clear conversation history for a user
- `%clearallhistory` - Clear ALL conversation history
- `%clearchannelhistory` - Clear conversation history for current channel
- `%channelstats` - Show conversation statistics for current channel

**Queue Management:**

- `%queuestatus` - Show message queue status and statistics
- `%processqueue` - Manually trigger queue processing

**Role & Keyword Management:**

- `%add_reaction_role` - Add a reaction role to a message
- `%remove_reaction_role` - Remove a reaction role from a message
- `%list_reaction_roles` - List all reaction roles
- `%set_gender_roles` - Set gender role mappings
- `%add_keyword` - Add a keyword
- `%remove_keyword` - Remove a keyword
- `%list_keywords` - List all configured keywords
- `%enable_keyword` - Enable a disabled keyword
- `%disable_keyword` - Disable a keyword

**tip.cc Commands:**

- `%bal` / `%bals` - Check tip.cc balances
- `%confirm` - Click Confirm button on tip.cc messages
- `%transactions [limit]` - Show recent transaction history
- `%tipstats` - Show tip.cc statistics and earnings
- `%clearstats` - Clear all tip.cc transaction history
- `%airdropstatus` - Show airdrop configuration and status
- `%tip` - Send tips
- `%airdrop` - Create airdrops

**Trivia Commands:**

- `%triviastats` - Show trivia database statistics
- `%seedtrivia` - Seed trivia database from external sources
- `%addtrivia` - Add custom trivia question
- `%triviatest` - Test trivia system

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
%help
%adminhelp
%stats
%time
%time EST
%date
```

### AI Model Commands

```
%model
%model gemini
%models
%imagemodels
%aistatus
%fallbackstatus
```

### Memory Commands

```
%memories
%memories gambling
%remember favorite_team Dallas Cowboys
%remember gambling_preference Slots and plinko
%clearmemories
%memorystatus
```

### AI & Media Commands

```
%image Fantasy Art a degenerate gambler at a slot machine
%image 16:9 cinematic a slot machine winning big
%audio Hello, I'm Jakey the degenerate gambler
%analyze https://example.com/image.jpg Describe this scene
```

### User & Channel Commands

```
%friends
%userinfo
%userinfo @user
%clearhistory
%clearallhistory
%clearchannelhistory
%channelstats
```

### Gambling & Utility Commands

```
%rigged
%wen monthly
%wen stake weekly
%keno
%keno 5
%ind_addr
```

### tip.cc Commands

```
%bal
%bals
%transactions
%transactions 25
%tipstats
%clearstats
%airdropstatus
%tip @user 100 DOGE
%airdrop 1000 DOGE 5m
```

### Queue Commands

```
%queuestatus
%processqueue
```

### Trivia Commands

```
%triviacats
%triviasearch Beatles
%triviastats
%seedtrivia
%addtrivia "General Knowledge" "What is 2+2?" "4"
%triviatest
```

### Role & Keyword Management

```
%add_reaction_role 123456789012345678 🎮 @Gamer
%remove_reaction_role 123456789012345678 🎮
%list_reaction_roles
%set_gender_roles male:123,female:456,neutral:789
%show_gender_roles
%add_keyword casino
%remove_keyword casino
%list_keywords
%enable_keyword casino
%disable_keyword casino
```

### System Commands

```
%clearcache
```

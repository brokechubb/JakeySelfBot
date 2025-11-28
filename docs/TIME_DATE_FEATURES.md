# Time and Date Features

## Overview

Jakey now supports displaying current time and date information with timezone support. This feature allows users to quickly check the current time in different timezones around the world, and more importantly, **the AI can now access real-time information to answer time-related questions**!

## Commands

### `%time [timezone]`
Show current time and date information.

**Parameters:**
- `timezone` (optional): Timezone name or alias (defaults to UTC)

**Examples:**
- `%time` - Show current time in UTC
- `%time est` - Show current time in US Eastern Time
- `%time pst` - Show current time in US Pacific Time
- `%time Europe/London` - Show current time in London

### `%date [timezone]`
Show current date information (alias for `%time` command).

**Parameters:**
- `timezone` (optional): Timezone name or alias (defaults to UTC)

**Examples:**
- `%date` - Show current date in UTC
- `%date est` - Show current date in US Eastern Time

## AI Tool Integration

**The AI can now access real-time date and time information through the `get_current_time` tool!**

### New AI Tool: `get_current_time`
- **Purpose**: Get current time and date information for any timezone worldwide
- **Parameters**: 
  - `timezone` (optional): Timezone name or alias, defaults to "UTC"
- **Usage**: The AI will automatically use this tool when asked time/date related questions

### Updated System Prompt Behavior
The AI system prompt has been updated to prioritize time queries:
- `"what time" → get_current_time`
- `"what date" → get_current_time` 
- `"current time" → get_current_time`
- `"now" → get_current_time`

**Tool Hierarchy (Updated):**
1. `get_current_time` (ANY time/date questions)
2. `web_search` (ANY knowledge question)
3. `crypto_price` (crypto prices)
4. `stock_price` (stock prices)
5. `calculate` (math/numbers)
6. `search_user_memory` (stored info)
7. Other tools as needed

## Supported Timezone Aliases

The following common timezone aliases are supported for both user commands and AI tool usage:

| Alias | Full Timezone Name | Description |
|-------|-------------------|-------------|
| `est` | `US/Eastern` | US Eastern Time |
| `edt` | `US/Eastern` | US Eastern Daylight Time |
| `cst` | `US/Central` | US Central Time |
| `cdt` | `US/Central` | US Central Daylight Time |
| `mst` | `US/Mountain` | US Mountain Time |
| `mdt` | `US/Mountain` | US Mountain Daylight Time |
| `pst` | `US/Pacific` | US Pacific Time |
| `pdt` | `US/Pacific` | US Pacific Daylight Time |
| `gmt` | `GMT` | Greenwich Mean Time |
| `bst` | `Europe/London` | British Summer Time |
| `cet` | `Europe/Paris` | Central European Time |
| `ist` | `Asia/Kolkata` | India Standard Time |
| `jst` | `Asia/Tokyo` | Japan Standard Time |
| `aest` | `Australia/Sydney` | Australian Eastern Standard Time |
| `utc` | `UTC` | Coordinated Universal Time |

## Output Format

### User Commands
The time command displays comprehensive information:

```
🕰️ CURRENT TIME & DATE 💀

📍 Timezone: US/Eastern
⏰ Time: 7:30:45 PM
📅 Date: Thursday, October 02, 2025
📆 ISO Format: 2025-10-02 19:30:45 EDT
🔢 Day of Year: 275
📊 Week: 40
🌍 Offset: UTC-04:00

🌏 POPULAR TIMEZONES:
%time utc - Coordinated Universal Time
%time est - US Eastern Time
%time pst - US Pacific Time
%time ist - India Standard Time
%time jst - Japan Standard Time
%time Europe/London - London Time
```

### AI Tool Output
The AI tool returns concise time information:
```
Current time in US/Eastern:
Time: 7:30:45 PM
Date: Thursday, October 02, 2025
ISO: 2025-10-02 19:30:45 EDT
Day of Year: 275
Week: 40
Offset: UTC-4:00
```

## Features

- **Multiple Timezone Support**: Supports all IANA timezone names
- **Common Aliases**: Easy-to-use aliases for popular timezones
- **AI Integration**: The AI can now access real-time time/date information
- **Fallback Handling**: Automatically falls back to UTC for invalid timezones
- **Comprehensive Information**: Shows time, date, ISO format, day of year, week number, and UTC offset
- **Rate Limiting**: Prevents excessive tool usage
- **Error Handling**: Gracefully handles timezone errors and provides helpful feedback

## Implementation Details

### Dependencies
- `pytz`: Python timezone library for comprehensive timezone support
- `datetime`: Python's built-in datetime module

### Error Handling
- Invalid timezone names automatically fall back to UTC
- Missing timezone parameter defaults to UTC
- All errors are logged and user-friendly error messages are displayed

### Performance
- Timezone lookups are cached by pytz for optimal performance
- Minimal computational overhead for timezone calculations
- Fast response times even with complex timezone operations
- Rate limiting prevents abuse

## Usage Examples

### User Commands
**User**: `%time`
**Jakey**: 
```
🕰️ CURRENT TIME & DATE 💀

📍 Timezone: UTC
⏰ Time: 11:30:45 PM
📅 Date: Thursday, October 02, 2025
📆 ISO Format: 2025-10-02 23:30:45 UTC
🔢 Day of Year: 275
📊 Week: 40
🌍 Offset: UTC+00:00
```

**User**: `%time est`
**Jakey**: 
```
🕰️ CURRENT TIME & DATE 💀

📍 Timezone: US/Eastern
⏰ Time: 7:30:45 PM
📅 Date: Thursday, October 02, 2025
📆 ISO Format: 2025-10-02 19:30:45 EDT
🔢 Day of Year: 275
📊 Week: 40
🌍 Offset: UTC-04:00
```

### AI Usage (Automatic)
**User**: "What time is it in New York?"
**AI**: Automatically calls `get_current_time(timezone="US/Eastern")` and responds with current New York time.

**User**: "What date is it?"
**AI**: Automatically calls `get_current_time()` and provides current date information.

## Testing

The time/date functionality includes comprehensive tests:

- **User Command Tests**: Command registration tests, timezone handling, error handling
- **AI Tool Tests**: Tool registration, availability in tool list, execution through tool manager
- **Integration Tests**: System prompt integration, tool hierarchy verification

Run tests with:
```bash
# User commands
python -m tests.test_time_commands

# AI tool integration
python -m tests.test_time_tool
```

## Future Enhancements

Potential future improvements could include:
- User timezone preferences (remember user's default timezone)
- Time conversion between timezones
- World clock display showing multiple timezones
- Sunrise/sunset times based on timezone
- Holiday and special date information per timezone
- Time-based reminder system
- Meeting scheduling across timezones
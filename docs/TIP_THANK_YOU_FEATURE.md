# Tip Thank You Feature

## Overview

The Tip Thank You feature automatically sends personalized thank you messages when Jakey receives cryptocurrency tips via tip.cc. This feature enhances community engagement by acknowledging tips with friendly, randomized responses.

## Features

- **Automatic Detection**: Automatically detects when Jakey receives tips via tip.cc
- **Personalized Messages**: Sends randomized thank you messages with emojis
- **Configurable**: Fully configurable via environment variables
- **Cooldown System**: Prevents spam with configurable cooldown periods
- **Channel Selection**: Intelligently selects appropriate channels to send thank you messages
- **Error Handling**: Gracefully handles errors and edge cases

## Configuration

The feature is configured using environment variables in `.env`:

```env
# Enable/disable the tip thank you feature
TIP_THANK_YOU_ENABLED=true

# Comma-separated list of thank you messages
TIP_THANK_YOU_MESSAGES=Thanks for the tip bro! 🙏,Appreciate the tip! 💰,Thanks for the love! ❤️,You're the real MVP! 🎯,Thanks for looking out! 🤝

# Comma-separated list of emojis to append to messages
TIP_THANK_YOU_EMOJIS=🙏,💰,❤️,🎯,🤝,💀,💥,🎵

# Cooldown period in seconds (default: 300 = 5 minutes)
TIP_THANK_YOU_COOLDOWN=300
```

## How It Works

### 1. Transaction Detection
The feature monitors tip.cc bot messages and parses transaction embeds to identify when Jakey receives tips.

### 2. Message Generation
When a tip is received:
- A random thank you message is selected from the configured list
- A random emoji is selected from the configured list
- Messages are formatted as: `<@sender> {message} {emoji}`

### 3. Channel Selection
The feature finds an appropriate channel by:
- Checking all guilds where both Jakey and the sender are present
- Looking for text channels where Jakey has send permissions
- Ensuring the sender can view the channel
- Selecting the first suitable channel found

### 4. Cooldown System
- Tracks the last thank you time for each user
- Respects the configured cooldown period
- Prevents spamming users with multiple thank you messages

## Example Usage

### When someone tips Jakey:
```
@User sent @Jakey 0.001 BTC (≈ $50.00)
```

### Jakey automatically responds:
```
@User Thanks for the tip bro! 🙏
```

## Testing

The feature includes comprehensive test coverage:

```bash
# Run tip thank you tests
python -m unittest tests.test_tip_thank_you -v

# Run all tests to ensure no regressions
python -m unittest discover tests -v
```

### Test Coverage
- ✅ Configuration enable/disable functionality
- ✅ Cooldown tracking and enforcement
- ✅ Transaction parsing (tip received vs tip sent)
- ✅ Thank you message formatting
- ✅ Channel selection logic
- ✅ Error handling scenarios
- ✅ Integration testing

## Implementation Details

### Core Components

1. **Configuration** (`config.py`):
   - Environment variable handling
   - Default values and validation

2. **TipCC Manager** (`utils/tipcc_manager.py`):
   - Transaction parsing logic
   - Thank you message generation
   - Channel selection algorithm
   - Cooldown management

3. **Bot Integration** (`bot/client.py`):
   - Message handling integration
   - Tip.cc bot response processing

### Key Methods

#### `_parse_transaction_embed()`
Parses tip.cc transaction embeds to extract:
- Transaction type (sent/received/airdrop/etc.)
- Sender and recipient IDs
- Amount and currency
- USD value

#### `_send_tip_thank_you()`
Sends thank you messages:
- Validates configuration and cooldown
- Generates random message and emoji
- Finds suitable channel
- Sends message with error handling

### Transaction Type Detection

The feature uses sophisticated logic to determine transaction types:

```python
# Analyzes title and description structure
# Looks for bot's position in "sender sent recipient" format
# Correctly identifies sent vs received transactions
```

## Error Handling

The feature gracefully handles various error scenarios:

- **No suitable channel**: Logs warning and continues
- **Permission errors**: Catches Discord exceptions and logs errors
- **Configuration issues**: Validates settings before processing
- **Network issues**: Handles async operation failures

## Performance Considerations

- **Minimal overhead**: Only processes tip.cc bot messages
- **Efficient caching**: Uses in-memory cooldown tracking
- **Async operations**: Non-blocking message sending
- **Rate limiting**: Respects Discord rate limits naturally

## Security Considerations

- **Bot validation**: Only processes messages from official tip.cc bot
- **Permission checking**: Verifies channel permissions before sending
- **No sensitive data**: Only sends public thank you messages
- **User privacy**: Only mentions users who have already interacted publicly

## Troubleshooting

### Common Issues

**Thank you messages not sending:**
1. Check `TIP_THANK_YOU_ENABLED=true` in configuration
2. Verify tip.cc bot ID is correct (617037497574359050)
3. Ensure bot has send permissions in target channels

**Messages sending to wrong channels:**
1. Verify channel permissions for both bot and recipient
2. Check guild membership for both users
3. Review channel selection logic in logs

**Cooldown not working:**
1. Verify `TIP_THANK_YOU_COOLDOWN` setting
2. Check bot restarts (cooldown is in-memory only)

### Debug Logging

Enable debug logging to troubleshoot:

```python
import logging
logging.getLogger('utils.tipcc_manager').setLevel(logging.DEBUG)
```

## Future Enhancements

Potential improvements for future versions:

- **Persistent cooldown**: Store cooldown in database for bot restarts
- **Custom messages per user**: User-specific thank you preferences
- **Message analytics**: Track engagement and response rates
- **Multi-language support**: Localized thank you messages
- **Tip amount scaling**: Different messages based on tip size

## Contributing

When modifying this feature:

1. **Add tests**: Ensure comprehensive test coverage for new features
2. **Update documentation**: Keep this document current
3. **Test integration**: Verify with actual tip.cc messages when possible
4. **Consider edge cases**: Handle unusual transaction formats gracefully

---

*This feature is part of JakeySelfBot's community engagement system.*
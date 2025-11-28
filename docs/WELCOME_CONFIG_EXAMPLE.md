# Enable welcome messages
WELCOME_ENABLED=true

# Server ID where welcome messages should be sent
WELCOME_SERVER_IDS=123456789

# Optional: Specific channel IDs (leave empty for auto-detection)
WELCOME_CHANNEL_IDS=

# Use default welcome prompt
WELCOME_PROMPT=Welcome {username} to {server_name}! Generate a personalized, witty welcome message that fits Jakey's degenerate gambling personality. Keep it brief and engaging.
```

## Advanced Configuration

Enable welcome messages for multiple servers with custom channels and personalized prompts:

```env
# Enable welcome messages
WELCOME_ENABLED=true

# Multiple server IDs
WELCOME_SERVER_IDS=123456789,987654321,555555555

# Specific welcome channels for each server
WELCOME_CHANNEL_IDS=111111111,222222222,333333333

# Custom Jakey-style welcome prompt
WELCOME_PROMPT=Yo {username}#{discriminator} just dropped into {server_name}! We got {member_count} degenerates in here now. Give 'em a proper Jakey-style welcome with some gambling energy! Make it cynical and funny like Jakey would. Include some gambling references and maybe ask "wen bonus?" 💰🎲💀
```

## Minimal Configuration

Simple setup with auto-detected channels:

```env
WELCOME_ENABLED=true
WELCOME_SERVER_IDS=123456789
```

## Server-Specific Configuration

Different configurations for different server types:

### For Gambling/Casino Servers
```env
WELCOME_ENABLED=true
WELCOME_SERVER_IDS=123456789
WELCOME_PROMPT=Welcome {username} to the casino! Another degenerate joins the ranks. Ready to lose some money? Everything's rigged anyway! Wen bonus drop? EZ money awaits! 🎰💀🎲
```

### For General Community Servers
```env
WELCOME_ENABLED=true
WELCOME_SERVER_IDS=987654321
WELCOME_PROMPT=What's up {username}! Welcome to {server_name}! We've got {member_count} members now. Hope you're ready for some chaos and degenerate energy! 💥
```

### For Crypto/Trading Servers
```env
WELCOME_ENABLED=true
WELCOME_SERVER_IDS=555555555
WELCOME_PROMPT=Welcome {username} to the crypto den! Another trader joins the {member_count} degenerates in {server_name}. Ready to get rugged or make some gains? Remember: DYOR and HODL! 💰🚀
```

## Template Variables

The welcome prompt supports these template variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{username}` | New member's username | `CryptoTrader` |
| `{discriminator}` | New member's discriminator | `1234` |
| `{server_name}` | Server name | `CrashDaddy's Courtyard` |
| `{member_count}` | Current member count | `42` |

### Example with All Variables
```env
WELCOME_PROMPT=Yo {username}#{discriminator}! Welcome to {server_name} - we now have {member_count} degenerates in here! Ready to gamble? 💀
```

## Finding Server and Channel IDs

### To get Server ID:
1. Enable Developer Mode in Discord settings
2. Right-click on the server icon
3. Click "Copy Server ID"

### To get Channel ID:
1. Enable Developer Mode in Discord settings  
2. Right-click on the channel name
3. Click "Copy Channel ID"

## Sample Welcome Messages

Based on different configurations, here are examples of what Jakey might generate:

### Default Style
> "Welcome NewUser to CrashDaddy's Courtyard! Another degenerate joins the ranks. EZ money awaits! 💀🎰"

### Gambling Style
> "Yo NewUser just dropped into the casino! We got 42 degenerates in here now. Ready to lose some money? Everything's rigged anyway! Wen bonus? 💰🎲💀"

### Crypto Style  
> "Welcome CryptoTrader to the crypto den! Another trader joins the 69 degenerates. Ready to get rugged or make some gains? Remember: DYOR and HODL! 💰🚀"

### Brief Style
> "NewUser in the house! Welcome to the degenerate squad. Let's get this money! 💰"

## Troubleshooting Tips

### Welcome Messages Not Sending
- Verify `WELCOME_ENABLED=true`
- Check that server ID is in `WELCOME_SERVER_IDS`
- Ensure bot has "Send Messages" permission
- Check bot logs for errors

### Messages Going to Wrong Channel
- Configure `WELCOME_CHANNEL_IDS` with correct channel IDs
- Ensure bot has permissions in specified channels
- Or rename channels to include "general", "welcome", or "lobby"

### Messages Don't Sound Like Jakey
- Customize `WELCOME_PROMPT` with Jakey's personality keywords
- Include terms like "degenerate", "gambling", "EZ money", "rigged", "wen"
- Add gambling references and emojis

## Best Practices

1. **Keep prompts concise** - Better AI response quality
2. **Use personality keywords** - "degenerate", "gambling", "EZ money", "rigged"
3. **Include template variables** - For personalization
4. **Add appropriate emojis** - 💀🎰💰🎲💥
5. **Test different prompts** - Find what works best for your community
6. **Monitor bot logs** - Check for any errors or issues

## Complete Example .env Section

```env
# ===== WELCOME MESSAGE CONFIGURATION =====
# Enable/disable welcome messages feature
WELCOME_ENABLED=true

# Comma-separated list of server IDs where welcome messages should be sent
WELCOME_SERVER_IDS=123456789,987654321

# Comma-separated list of channel IDs where welcome messages should be sent (optional)
# If empty, Jakey will auto-detect general/welcome/lobby channels
WELCOME_CHANNEL_IDS=111111111,222222222

# Custom welcome prompt template (optional)
# Available variables: {username}, {discriminator}, {server_name}, {member_count}
WELCOME_PROMPT=Welcome {username} to {server_name}! Another degenerate joins the {member_count} members in the courtyard. Ready to gamble? Everything's rigged anyway! Wen bonus? EZ money! 💀🎰
```

This configuration will enable AI-powered welcome messages that sound exactly like Jakey would say them!
# Welcome Messages Feature

The JakeySelfBot now supports AI-powered welcome messages for new server members. This feature generates personalized, witty welcome messages using Jakey's degenerate gambling personality.

## Configuration

Add the following environment variables to your `.env` file:

```env
# Enable/disable welcome messages feature
WELCOME_ENABLED=true

# Comma-separated list of server IDs where welcome messages should be sent
WELCOME_SERVER_IDS=123456789,987654321

# Comma-separated list of channel IDs where welcome messages should be sent (optional)
WELCOME_CHANNEL_IDS=111111111,222222222

# Custom welcome prompt template (optional)
WELCOME_PROMPT=Welcome {username} to {server_name}! Generate a personalized, witty welcome message that fits Jakey's degenerate gambling personality. Keep it brief and engaging.
```

### Configuration Details

#### WELCOME_ENABLED
- **Type**: Boolean (`true`/`false`)
- **Default**: `false`
- **Description**: Enables or disables the welcome message feature globally

#### WELCOME_SERVER_IDS
- **Type**: Comma-separated string of server IDs
- **Default**: Empty string
- **Description**: List of server IDs where welcome messages should be triggered
- **Example**: `123456789,987654321`

#### WELCOME_CHANNEL_IDS
- **Type**: Comma-separated string of channel IDs
- **Default**: Empty string
- **Description**: List of channel IDs where welcome messages should be sent. If not specified, Jakey will auto-detect appropriate channels
- **Example**: `111111111,222222222`

#### WELCOME_PROMPT
- **Type**: String with template variables
- **Default**: `Welcome {username} to {server_name}! Generate a personalized, witty welcome message that fits Jakey's degenerate gambling personality. Keep it brief and engaging.`
- **Description**: Template prompt used to generate welcome messages

### Template Variables

The welcome prompt supports the following template variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{username}` | New member's username | `NewUser` |
| `{discriminator}` | New member's discriminator | `1234` |
| `{server_name}` | Server name | `CrashDaddy's Courtyard` |
| `{member_count}` | Current server member count | `42` |

## Channel Selection Logic

When a new member joins, Jakey follows this logic to determine where to send the welcome message:

1. **Configured Channels**: If `WELCOME_CHANNEL_IDS` is specified, Jakey checks each channel in order:
   - Uses the first channel where the bot has send permissions
   - Skips channels where the bot lacks permissions

2. **Auto-Detection**: If no channels are configured or none are accessible, Jakey searches for:
   - Channels named "general", "welcome", or "lobby" (case-insensitive)
   - The first available text channel where the bot has send permissions

3. **Fallback**: If no suitable channel is found, the welcome message is not sent and an error is logged

## Usage Examples

### Basic Configuration

```env
WELCOME_ENABLED=true
WELCOME_SERVER_IDS=123456789
```

This will enable welcome messages for server `123456789` and use the default prompt with auto-detected channels.

### Advanced Configuration

```env
WELCOME_ENABLED=true
WELCOME_SERVER_IDS=123456789,987654321
WELCOME_CHANNEL_IDS=111111111,222222222
WELCOME_PROMPT=Yo {username}#{discriminator} just dropped into {server_name}! We got {member_count} degenerates in here now. Give 'em a proper Jakey-style welcome with some gambling energy! 💰🎲
```

This configuration:
- Enables welcome messages for two servers
- Specifies two preferred channels for welcome messages
- Uses a custom prompt with more personality and all available variables

### Minimal Configuration

```env
WELCOME_ENABLED=true
WELCOME_SERVER_IDS=123456789
WELCOME_CHANNEL_IDS=111111111
```

This uses the default prompt but targets a specific channel.

## Sample Welcome Messages

Based on Jakey's personality, here are examples of welcome messages the AI might generate:

### Standard Welcome
> "Welcome NewUser to CrashDaddy's Courtyard! Another degenerate joins the ranks. EZ money awaits! 💀🎰"

### Engaging Welcome
> "Yo NewUser just dropped in! We got 42 degenerates in this courtyard now. Ready to lose some money? Wen bonus? 💥"

### Humorous Welcome
> "Well look who decided to join the casino! Welcome NewUser, hope you brought your gambling money because everything's rigged anyway! 🎲💀"

### Brief Welcome
> "NewUser in the house! Welcome to the degenerate squad. Let's get this money! 💰"

## Troubleshooting

### Common Issues

#### Welcome Messages Not Sending
**Problem**: New members join but no welcome messages appear.

**Solutions**:
1. Verify `WELCOME_ENABLED` is set to `true`
2. Check that the server ID is in `WELCOME_SERVER_IDS`
3. Ensure the bot has "Send Messages" permission in the target channel
4. Check the bot logs for error messages

#### Wrong Channel
**Problem**: Welcome messages are sent to the wrong channel.

**Solutions**:
1. Configure `WELCOME_CHANNEL_IDS` with the correct channel IDs
2. Ensure the bot has permissions in the specified channels
3. Rename channels to include "general", "welcome", or "lobby" for auto-detection

#### Generic Messages
**Problem**: Welcome messages don't sound like Jakey.

**Solutions**:
1. Customize `WELCOME_PROMPT` to better match Jakey's personality
2. Include keywords like "degenerate", "gambling", "EZ money", "rigged", "wen"
3. Add emoji and slang to the prompt template

#### API Errors
**Problem**: Errors about AI API failures in logs.

**Solutions**:
1. Check that the AI API is accessible
2. Verify API keys are correctly configured
3. Monitor rate limits and API quotas
4. The feature includes retry logic, so temporary failures should resolve automatically

### Finding Server and Channel IDs

To get server and channel IDs:

1. **Server ID**:
   - Enable Developer Mode in Discord settings
   - Right-click on the server icon
   - Click "Copy Server ID"

2. **Channel ID**:
   - Enable Developer Mode in Discord settings
   - Right-click on the channel name
   - Click "Copy Channel ID"

### Debug Logging

To debug welcome message issues, check the bot logs:

```bash
tail -f jakey.log | grep -i welcome
```

Look for these log messages:
- `👋 New member ... joined server ...` - Member join detected
- `✅ Sent welcome message to ...` - Successful welcome message
- `❌ No suitable welcome channel found` - Channel detection failed
- `❌ Failed to generate welcome message` - AI generation failed

## Performance Considerations

### Rate Limiting
- Welcome messages are subject to the same rate limits as other bot functions
- The feature includes built-in cooldowns to prevent API abuse
- Multiple joins in quick succession may experience slight delays

### API Usage
- Each welcome message consumes one AI API call
- Monitor your API usage if you have large servers with frequent joins
- The feature handles API failures gracefully without crashing

### Server Performance
- The feature is designed to be lightweight and non-blocking
- Welcome message generation runs asynchronously
- No impact on other bot functionality

## Security Considerations

### Permissions
- The bot only sends messages to channels where it has explicit permissions
- No sensitive information is included in welcome messages
- Member usernames and server names are public information

### Privacy
- Only publicly available Discord information is used (username, discriminator, server name, member count)
- No private messages or sensitive data is accessed
- All data processing is done locally

## Best Practices

### Prompt Crafting
- Keep prompts concise for better AI response quality
- Include personality keywords that match Jakey's character
- Use template variables for personalization
- Add appropriate emojis for visual appeal

### Channel Setup
- Use dedicated welcome channels for better organization
- Ensure the bot has necessary permissions before enabling
- Consider channel visibility and notification settings

### Monitoring
- Regularly check logs for errors or issues
- Monitor API usage if you have rate limits
- Test the feature after configuration changes

## Future Enhancements

Potential future improvements to consider:

- **Customizable Personality**: Allow different personality styles per server
- **Welcome Images**: Option to include AI-generated welcome images
- **Member Milestones**: Special messages for member count milestones
- **Role Assignment**: Automatic role assignment with welcome messages
- **Welcome Reactions**: Add emoji reactions to welcome messages
- **Multi-language Support**: Welcome messages in different languages
- **Welcome Analytics**: Track welcome message engagement and effectiveness

## Support

If you encounter issues with the welcome message feature:

1. Check this documentation for common solutions
2. Review the bot logs for error messages
3. Verify your configuration settings
4. Test with different prompt variations
5. Ensure all required permissions are properly configured

For additional support, refer to the main project documentation or create an issue in the project repository.
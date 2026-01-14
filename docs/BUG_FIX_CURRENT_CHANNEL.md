# Bug Fix - AI Not Using "current" for Channel ID

## Issue Report (Jan 4, 2026)

**User Command:** "use your tools to read the channel history"

**Symptom:** AI tries to list all guilds/channels instead of using current channel

**AI's Reasoning:**
```
We need channel ID. Not provided. We could use discord_list_channels to get list, 
but we need to know which channel. The context is from recent channel conversation, 
but we don't have channel ID.
```

## Root Cause

The bot has **automatic channel_id resolution** code at `bot/client.py:1037-1046`:

```python
# Handle special "current" channel_id for Discord tools
channel_id_arg_names = ["channel_id", "channel"]
for arg_name in channel_id_arg_names:
    if arg_name in arguments:
        val = str(arguments[arg_name]).lower().strip()
        if val in ("current", "current channel", "this channel", "here"):
            arguments[arg_name] = str(message.channel.id)
```

**But the AI didn't know it could use "current"!** 

The tool descriptions never mentioned this feature, so the AI thought it needed to:
1. Get user info
2. List all guilds
3. List all channels in each guild
4. Read each channel looking for the right one

## Fix Applied

Updated tool descriptions to explicitly tell AI about the "current" keyword:

### discord_read_channel
**Before:**
```json
{
  "channel_id": {
    "type": "string",
    "description": "The Discord channel ID to read messages from"
  }
}
```

**After:**
```json
{
  "channel_id": {
    "type": "string",
    "description": "The Discord channel ID to read messages from. Use 'current' to read from the channel where the user sent the message."
  }
}
```

### discord_search_messages
**Updated:** Added `"Use 'current' for the channel where the user sent the message."`

### discord_send_message
**Updated:** Added `"Use 'current' for the channel where the user sent the message."`

## Impact

**Before:**
- AI tries to make multiple tool calls
- Complex chain: get_user_info → list_guilds → list_channels → read_channel
- Fails with multi-round tool calling error
- User gets no response

**After:**
- AI knows it can use `"current"` as channel_id
- Single tool call: `discord_read_channel(channel_id="current", limit=50)`
- Works immediately
- User gets channel history

## Testing

```bash
# These should now work with single tool call:
"read the channel history"
"show me recent messages"
"what was said in this channel"
"search for 'bitcoin' in this channel"

# Should use discord_read_channel with channel_id="current"
```

Expected logs:
```
INFO Executing tool: discord_read_channel with args: {'channel_id': 'current', 'limit': 50}
INFO Replaced 'current' channel_id with actual ID: 123456789012345678
INFO Tool result: discord_read_channel -> [Recent 50 messages from #channel-name]
```

## Related Keyword Support

The automatic resolver supports these keywords (case-insensitive):
- `"current"`
- `"current channel"`  
- `"this channel"`
- `"here"`

All will be automatically replaced with `str(message.channel.id)`

## Files Modified

1. **`tools/tool_manager.py:679-707`** - Updated discord_read_channel and discord_search_messages descriptions
2. **`tools/tool_manager.py:770-790`** - Updated discord_send_message description

## Why This Worked Before

This feature existed in the code since the beginning, but:
- Older models might have been better at inferring the "current" keyword
- Or the system prompt previously included examples showing "current" usage
- Or channel context was formatted differently

The explicit description makes it work reliably with all models.

## Future Enhancements

Consider adding similar features for:
- `guild_id: "current"` - Use current guild
- `user_id: "me"` - Use bot's user ID
- `user_id: "sender"` - Use message author's ID

These could all be auto-resolved from message context.

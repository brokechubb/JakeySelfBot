# Airdrop Server Whitelist Feature

## Overview

The airdrop server whitelist feature allows you to restrict Jakey's airdrop collection to specific Discord servers only. This is useful when you want the bot to participate in airdrops only in certain communities while ignoring others.

## Configuration

Add the following environment variable to your `.env` file:

```bash
AIRDROP_SERVER_WHITELIST=server_id1,server_id2,server_id3
```

### How to Get Server IDs

1. Right-click on any server name in Discord
2. Select "Copy Server ID" (you may need to enable Developer Mode in Discord settings)
3. Paste the ID into your whitelist

### Behavior

- **When whitelist is empty or not set**: Jakey will collect airdrops in all servers (default behavior)
- **When whitelist contains server IDs**: Jakey will ONLY collect airdrops in the specified servers
- **When a message appears in a non-whitelized server**: Jakey will ignore the airdrop command completely

### Example Configuration

```bash
# Only collect airdrops in specific servers
AIRDROP_SERVER_WHITELIST=123456789012345678,987654321098765432

# Collect airdrops in all servers (default)
AIRDROP_SERVER_WHITELIST=

# Disable whitelist entirely
# AIRDROP_SERVER_WHITELIST= (leave empty or remove the line)
```

## Status Command

The `%airdrop` status command now shows whitelist information:

```
🎯 AIRDROP STATUS 💀

Configuration:
• Presence: active
• Smart Delay: Enabled
• Range Delay: Disabled
• Delay Range: 0.0-2.5s
• CPM: 200-310
• Server Whitelist: Enabled (2 servers)
```

If the whitelist is disabled, it will show:
```
• Server Whitelist: Disabled (all servers)
```

## Implementation Details

- The whitelist check happens before any other airdrop processing
- Server IDs are compared as strings to avoid type conversion issues
- Empty entries and whitespace in the whitelist are automatically ignored
- The feature is integrated with existing airdrop configuration options

## Use Cases

1. **Targeted Participation**: Only participate in airdrops from communities you're active in
2. **Resource Management**: Reduce bot load by ignoring servers you don't care about
3. **Safety**: Avoid accidental participation in unknown or potentially problematic servers
4. **Testing**: Restrict airdrop collection to specific test servers during development

## Troubleshooting

- **Airdrops not working**: Check that the server ID is correct and the whitelist is properly formatted
- **Bot ignoring all servers**: Make sure the whitelist isn't empty when you want it enabled
- **Server ID format**: Server IDs should be numeric strings without quotes or extra characters
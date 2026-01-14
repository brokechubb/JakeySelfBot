# Moderation Tools & Features

Jakey now includes a comprehensive suite of moderation tools that allow him to manage users and messages within Discord servers where he has appropriate permissions. These tools are accessible via natural language requests to the AI.

## Overview

The moderation system is built on three key components:
1.  **AI Tools**: Wrapper functions exposed to the AI model (e.g., `discord_kick_user`, `discord_purge_messages`).
2.  **Permission Awareness**: Automatic checking and storage of the bot's permissions in each guild.
3.  **Safety & Rate Limiting**: Built-in safeguards to prevent abuse and API spam.

## Available Tools

The following tools are available to the AI when responding to user requests:

### User Management
*   **Kick User** (`discord_kick_user`): Kicks a member from the server.
    *   *Usage*: "Kick @user for being spammy"
    *   *Requires*: `Kick Members` permission
*   **Ban User** (`discord_ban_user`): Bans a member from the server, optionally deleting recent messages.
    *   *Usage*: "Ban @user for raiding"
    *   *Requires*: `Ban Members` permission
*   **Unban User** (`discord_unban_user`): Unbans a user by ID.
    *   *Usage*: "Unban user 123456789"
    *   *Requires*: `Ban Members` permission
*   **Timeout User** (`discord_timeout_user`): Mutes/timeouts a member for a specified duration (minutes).
    *   *Usage*: "Timeout @user for 10 minutes"
    *   *Requires*: `Moderate Members` permission
*   **Remove Timeout** (`discord_remove_timeout`): Removes a timeout from a member.
    *   *Usage*: "Remove timeout from @user", "Unmute @user"
    *   *Requires*: `Moderate Members` permission

### Message Management
*   **Purge Messages** (`discord_purge_messages`): Bulk deletes messages from a channel.
    *   *Usage*: "Purge last 10 messages", "Delete last 5 messages from @user"
    *   *Requires*: `Manage Messages` permission
    *   *Limit*: Max 100 messages per call
*   **Delete Message** (`discord_delete_message`): Deletes a single message by ID.
    *   *Usage*: "Delete that message" (replying to it), "Delete message 123456789"
    *   *Requires*: `Manage Messages` permission
*   **Pin Message** (`discord_pin_message`): Pins a message to the channel.
    *   *Usage*: "Pin this message"
    *   *Requires*: `Manage Messages` permission
*   **Unpin Message** (`discord_unpin_message`): Unpins a message from the channel.
    *   *Usage*: "Unpin that message"
    *   *Requires*: `Manage Messages` permission

## Permission System

Jakey automatically checks his permissions in each server to know what he can and cannot do.

1.  **On Startup**: Checks permissions for all connected guilds.
2.  **On Join**: Checks permissions immediately upon joining a new guild.
3.  **Storage**: Permissions (e.g., "ADMINISTRATOR", "KICK_MEMBERS") are stored in Jakey's memory for that specific guild context.

This allows the AI to refuse requests if it knows it lacks the necessary permissions, providing a better user experience.

## Usage Examples

**User**: "Jakey, kick @SpamBot for spamming links."
**Jakey**: *Calls `discord_kick_user(guild_id, user_id, reason="spamming links")`*
**Response**: "👢 **Kicked SpamBot.** Don't let the door hit you on the way out."

**User**: "Clear the last 5 messages."
**Jakey**: *Calls `discord_purge_messages(channel_id, limit=5)`*
**Response**: "🧹 **Cleared 5 messages.** Channel looks cleaner now."

**User**: "Timeout this guy for 1 hour." (replying to a user)
**Jakey**: *Calls `discord_timeout_user(guild_id, user_id, duration_minutes=60)`*
**Response**: "🤐 **Timed out User for 60 minutes.** Sit in the corner and think about what you did."

## Safety Features

*   **Rate Limits**: Moderation actions are rate-limited (e.g., 2 seconds between kicks/bans) to prevent mass-action accidents.
*   **Hierarchy Checks**: The bot cannot moderate users with roles higher than its own.
*   **Self-Protection**: The bot cannot ban or kick itself or the server owner.

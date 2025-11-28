# Memory System

Jakey's Memory System provides persistent storage of user information, preferences, and facts. This system allows Jakey to remember important details about users across conversations and sessions.

## Purpose

The Memory System is designed to provide personalized experiences by remembering:

- User preferences
- Personal facts
- Interests and hobbies
- Gambling preferences
- Location information
- And other important user-specific details

## How It Works

The memory system operates on two levels:

1. **Automatic Integration**: Stored memories are automatically included in the system prompt for context
2. **Tool-based Storage**: The AI can use the `remember_user_info` tool to store new information
3. **Manual Storage**: Users can use the `%remember` command to store information

## Usage

### For Users

Users can manually store information using the `%remember` command:

```
%remember favorite_team Dallas Cowboys
%remember gambling_preference Slots and plinko
%remember location Las Vegas
```

### For AI

The AI can automatically choose to use the remember_user_info tool when it identifies important information to store:

```json
{
  "name": "remember_user_info",
  "arguments": {
    "user_id": "123456789",
    "information_type": "favorite_sport",
    "information": "NFL football"
  }
}
```

## Memory Storage

Memories are stored in the SQLite database in the `memories` table with the following structure:

- `user_id`: Discord user ID
- `key`: Type of information (e.g., "favorite_team")
- `value`: The stored information (e.g., "Dallas Cowboys")
- `created_at`: Timestamp of when the memory was created

## Features

- **Persistence**: Memories are stored in the database and persist across sessions
- **User-specific**: Each user has their own memory space
- **Automatic Context**: Memories are automatically included in conversation context
- **Rate Limiting**: Prevents abuse of the memory storage system

## Best Practices

1. Store meaningful, relevant information that enhances user experience
2. Respect user privacy - don't store sensitive personal information
3. Use descriptive keys for better organization
4. Update memories when users provide new information
5. Consider memory capacity - store the most important information

## Memory Retrieval

Stored memories are automatically included in the system prompt under the "User-Specific Information" section, making them available to the AI during conversation processing.

## Example Memory Context

When a user with stored memories interacts with Jakey, the system prompt automatically includes:

```
User-Specific Information:
- favorite_team: Dallas Cowboys
- gambling_preference: Slots and plinko
- location: Las Vegas
```

This allows Jakey to provide personalized responses based on known user information.
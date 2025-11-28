# Conversation History Configuration

This document explains how to configure the conversation history parameters for JakeySelfBot to control how much context is used in AI responses.

## Configuration Options

The following parameters can be configured in your environment variables or in the `config.py` file:

### Environment Variables

- `CONVERSATION_HISTORY_LIMIT`: Number of previous conversations to include in AI context (default: 10)
- `MAX_CONVERSATION_TOKENS`: Maximum tokens to use for conversation context (default: 1500)
- `CHANNEL_CONTEXT_MINUTES`: Minutes of channel context to include (default: 30)
- `CHANNEL_CONTEXT_MESSAGE_LIMIT`: Maximum messages in channel context (default: 10)

### Example Configuration

```bash
# In your .env file or environment:
CONVERSATION_HISTORY_LIMIT=5          # Use only last 5 conversations
MAX_CONVERSATION_TOKENS=2000          # Allow up to 2000 tokens for context
CHANNEL_CONTEXT_MINUTES=60            # Include 60 minutes of channel history
CHANNEL_CONTEXT_MESSAGE_LIMIT=20      # Limit to 20 messages in channel context
```

## How It Works

### Conversation History
- The bot stores conversation history in the SQLite database
- When processing a new message, it retrieves recent conversations for that user
- Previous conversations are added to the AI context to provide continuity
- The `CONVERSATION_HISTORY_LIMIT` controls how many past conversations are included

### Channel Context
- Recent channel messages are collected for additional context
- Messages within the time window (`CHANNEL_CONTEXT_MINUTES`) are included
- The total number of messages is limited by `CHANNEL_CONTEXT_MESSAGE_LIMIT`

### Token Management
- The system tracks token usage to prevent context overflow
- Total tokens are limited by `MAX_CONVERSATION_TOKENS`
- If adding a conversation would exceed the limit, it's skipped

## Configuration Examples

### Conservative (Light History)
```bash
CONVERSATION_HISTORY_LIMIT=3
MAX_CONVERSATION_TOKENS=1000
CHANNEL_CONTEXT_MINUTES=15
CHANNEL_CONTEXT_MESSAGE_LIMIT=5
```

### Balanced (Recommended)
```bash
CONVERSATION_HISTORY_LIMIT=10
MAX_CONVERSATION_TOKENS=1500
CHANNEL_CONTEXT_MINUTES=30
CHANNEL_CONTEXT_MESSAGE_LIMIT=10
```

### Rich Context (Heavy History)
```bash
CONVERSATION_HISTORY_LIMIT=20
MAX_CONVERSATION_TOKENS=2500
CHANNEL_CONTEXT_MINUTES=120
CHANNEL_CONTEXT_MESSAGE_LIMIT=50
```

## Performance Considerations

- Higher limits provide more context but use more API tokens and resources
- Larger context windows may slow down AI response times
- Consider your API rate limits when setting high token limits
- Monitor bot performance and adjust accordingly

## Default Values

If no configuration is provided, the system uses these defaults:
- `CONVERSATION_HISTORY_LIMIT`: 10 conversations
- `MAX_CONVERSATION_TOKENS`: 1500 tokens
- `CHANNEL_CONTEXT_MINUTES`: 30 minutes
- `CHANNEL_CONTEXT_MESSAGE_LIMIT`: 10 messages

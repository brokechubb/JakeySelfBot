# Automatic Memory Extraction System

This document describes Jakey's automatic memory extraction system that remembers important details about users from conversations.

## Overview

The auto-memory extraction system automatically:
- Extracts meaningful information from conversations
- Stores it in a unified memory backend
- Retrieves relevant memories to provide personalized responses
- Maintains memories for long-term recall (years)

## Features

### 1. Information Extraction

The system extracts several types of information:

#### Personal Information
- Name, age, birthday, location
- Occupation, hobbies, interests
- Family relationships

#### Preferences & Opinions
- Likes and dislikes
- Favorite things (movies, food, etc.)
- Personal opinions

#### Important Facts
- Life events and milestones
- Plans and intentions
- Health information
- Travel plans

#### Contextual Information
- Current activities and projects
- Recent life updates
- Temporary situations

### 2. Smart Filtering

The system includes intelligent filtering to:
- Skip trivial information (yes/no, thanks, hello)
- Remove duplicates and near-duplicates
- Filter by confidence levels
- Respect minimum information length

### 3. Memory Storage

Memories are stored using the unified memory backend:
- **Primary**: SQLite database (always available)
- **Optional**: MCP Memory Server (if enabled)
- **Fallback**: Graceful degradation between backends

### 4. Memory Retrieval

The system provides context to AI responses by:
- Searching for relevant memories based on current message
- Formatting memories for AI consumption
- Prioritizing recent and high-confidence memories

## Configuration

Add these environment variables to your `.env` file:

```env
# Enable/disable automatic memory extraction
AUTO_MEMORY_EXTRACTION_ENABLED=true

# Minimum confidence threshold for storing memories (0.0-1.0)
AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD=0.4

# Enable/disable periodic cleanup of old memories
AUTO_MEMORY_CLEANUP_ENABLED=true

# Maximum age of memories to keep (days)
AUTO_MEMORY_MAX_AGE_DAYS=365
```

## How It Works

### Extraction Process

1. **Pattern Matching**: Uses regex patterns to identify personal information
2. **Importance Detection**: Looks for keywords and important topics
3. **Context Analysis**: Extracts contextual information about user activities
4. **Confidence Scoring**: Rates each extracted piece of information
5. **Filtering**: Removes low-quality or duplicate information

### Storage Process

1. **Backend Selection**: Uses unified memory backend with priority
2. **Metadata Storage**: Saves confidence, source, and extraction time
3. **Unique IDs**: Generates unique identifiers for each memory
4. **Error Handling**: Graceful fallback if storage fails

### Retrieval Process

1. **Query Analysis**: Extracts keywords from user messages
2. **Memory Search**: Searches for relevant memories using multiple strategies
3. **Context Formatting**: Formats memories for AI consumption
4. **Integration**: Adds context to AI messages without explicit mention

## Example

### Input conversation:
```
User: Hey Jakey, my name is Sarah and I'm a graphic designer from New York. I love Italian food but I'm allergic to shellfish.
Jakey: Nice to meet you, Sarah! Being a graphic designer in New York must be exciting. I'll definitely remember about the shellfish allergy - that's important!
```

### Extracted Memories:
```json
[
  {
    "type": "personal_info",
    "category": "name",
    "information": "Sarah",
    "confidence": 0.9
  },
  {
    "type": "personal_info", 
    "category": "occupation",
    "information": "graphic designer",
    "confidence": 0.9
  },
  {
    "type": "personal_info",
    "category": "location", 
    "information": "New York",
    "confidence": 0.9
  },
  {
    "type": "preference",
    "category": "likes",
    "information": "Italian food",
    "confidence": 0.8
  },
  {
    "type": "personal_info",
    "category": "health",
    "information": "allergic to shellfish",
    "confidence": 0.9
  }
]
```

### Future conversation with context:
```
User: I'm thinking about where to eat tonight
Jakey: Since you love Italian food and need to avoid shellfish, maybe try that new pasta place in Brooklyn? They have great options that would be perfect for you!
```

## Testing

Run the test script to verify the system:

```bash
python test_auto_memory.py
```

## Memory Persistence

Memories are designed to persist for years:
- **Default retention**: 365 days (configurable)
- **Periodic cleanup**: Runs daily to remove old memories
- **Confidence-based pruning**: Low confidence memories are removed first

## Privacy Considerations

- All memories are stored locally by default
- No data is sent to external services (unless MCP server is enabled)
- Users can request memory deletion through the `%clearhistory` command
- Automatic cleanup prevents indefinite data retention

## Integration

The system integrates with:
- **Bot Client**: Automatically processes messages
- **AI Provider**: Adds context to AI responses  
- **Tool Manager**: Provides memory search tools
- **Database**: Persists memories across restarts

## Troubleshooting

### Memories not being saved:
1. Check `AUTO_MEMORY_EXTRACTION_ENABLED` is `true`
2. Verify database permissions
3. Check logs for extraction errors

### Too many memories being saved:
1. Increase `AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD`
2. Lower `AUTO_MEMORY_MAX_AGE_DAYS` 
3. Check for false positives in patterns

### Memories not appearing in responses:
1. Verify memory backend is accessible
2. Check confidence thresholds
3. Review memory search logs

## Future Enhancements

Planned improvements:
- Machine learning-based extraction
- Sentiment analysis for memories
- Memory summarization over time
- User feedback on memory accuracy
- Cross-server memory consolidation
# Trivia System

Jakey includes a comprehensive trivia system that automatically answers trivia drops from tip.cc and learns from successful interactions. The system maintains a local database of trivia questions and answers, with intelligent learning capabilities.

## Overview

The trivia system consists of:

- **Local Database**: SQLite database storing categories, questions, answers, and statistics
- **Learning System**: Automatically learns new questions from successful trivia drops
- **Multi-Source Lookup**: Checks local database, cache, and external sources for answers
- **Statistics Tracking**: Records usage statistics and performance metrics
- **Admin Commands**: Tools for managing and seeding the trivia database

## Database Schema

### Categories Table

```sql
CREATE TABLE trivia_categories (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    display_name TEXT,
    description TEXT,
    is_active BOOLEAN DEFAULT 1,
    question_count INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Questions Table

```sql
CREATE TABLE trivia_questions (
    id INTEGER PRIMARY KEY,
    category_id INTEGER,
    question_text TEXT,
    answer_text TEXT,
    difficulty INTEGER DEFAULT 1,
    source TEXT DEFAULT 'manual',
    external_id TEXT,
    is_active BOOLEAN DEFAULT 1,
    times_asked INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    last_used TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES trivia_categories(id)
);
```

### Statistics Table

```sql
CREATE TABLE trivia_stats (
    id INTEGER PRIMARY KEY,
    question_id INTEGER,
    channel_id TEXT,
    guild_id TEXT,
    answered BOOLEAN,
    response_time_ms INTEGER,
    timestamp TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES trivia_questions(id)
);
```

### Cache Table

```sql
CREATE TABLE trivia_cache (
    category_name TEXT PRIMARY KEY,
    questions_json TEXT,
    expires_at TIMESTAMP,
    last_updated TIMESTAMP
);
```

## How It Works

### Answer Lookup Process

1. **Local Database Check**: First checks the local SQLite database for known questions
2. **Cache Check**: Falls back to cached external questions if not found locally
3. **External Source**: Fetches from GitHub external trivia sources as last resort
4. **Learning**: Records successful answers and unknown questions for future reference

### Learning Mechanism

- **Successful Answers**: When Jakey correctly answers an unknown question, it records the Q&A pair
- **Unknown Questions**: Questions that can't be answered are stored with "UNKNOWN_ANSWER" marker
- **Statistics**: Tracks success rates, usage patterns, and performance metrics

## Commands

### User Commands

- `%triviastats` - Show database statistics and health
- `%triviacats` - List all available trivia categories
- `%triviatest` - Test the trivia system with a sample question

### Admin Commands

- `%seedtrivia` - Populate database with questions from external sources
- `%addtrivia <category> <question> <answer>` - Add custom trivia question

## Configuration

### Environment Variables

- `TRIVIA_CACHE_TTL` (default: 3600) - Cache time-to-live in seconds
- `TRIVIA_EXTERNAL_TIMEOUT` (default: 5.0) - Timeout for external API calls
- `TRIVIA_MAX_CACHE_SIZE` (default: 100) - Maximum cached questions per category

### Airdrop Integration

The trivia system integrates with the airdrop claiming system:

- `AIRDROP_DISABLE_TRIVIADROP` (default: false) - Disable trivia drop claiming
- Automatic category validation to prevent injection attacks
- Timeout protection to prevent blocking on slow lookups

## External Sources

The system uses the following external trivia sources:

- **Primary**: GitHub repository with categorized trivia questions
- **Backup**: Multiple fallback sources for reliability
- **Caching**: Local caching to reduce external API calls

## Statistics and Analytics

### Database Health Metrics

- Total categories and questions
- Cache hit rates and performance
- Success rates by category
- Response time analytics

### Usage Tracking

- Questions asked per category
- Correct answer percentages
- Channel and guild usage patterns
- Learning progress over time

## Best Practices

### Database Management

1. **Regular Seeding**: Use `%seedtrivia` to keep the database current
2. **Cache Monitoring**: Monitor cache performance and refresh as needed
3. **Category Validation**: Only enable trusted categories for auto-claiming

### Performance Optimization

1. **Indexing**: Database is properly indexed for fast lookups
2. **Caching**: Multi-level caching reduces external API calls
3. **Timeouts**: All operations have timeouts to prevent blocking
4. **Async Operations**: Fully async implementation for scalability

### Security

1. **Input Validation**: All inputs are validated and sanitized
2. **Rate Limiting**: Built-in protection against abuse
3. **Source Verification**: External sources are validated
4. **Error Handling**: Comprehensive error handling and logging

## Troubleshooting

### Common Issues

- **No Answers Found**: Database may need seeding with `%seedtrivia`
- **Slow Responses**: Check cache status and refresh if needed
- **Category Errors**: Validate category names and enable trusted ones only

### Maintenance

- **Database Cleanup**: Regularly clean old or unused questions
- **Cache Refresh**: Refresh external caches periodically
- **Statistics Reset**: Use admin commands to reset statistics if needed

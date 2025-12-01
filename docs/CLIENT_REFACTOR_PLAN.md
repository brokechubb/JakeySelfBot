# Proposed Refactored Structure for bot/client.py

## Current Issues
- **5084 lines** - Too large for maintainability
- **Multiple responsibilities** in single class
- **Mixed concerns** (Discord events, AI processing, airdrop logic, etc.)

## Proposed Structure

```
bot/
├── client.py              # Main bot class (Discord integration only)
├── message_processor.py   # Message processing and AI integration
├── airdrop_processor.py   # Airdrop claiming logic
├── reaction_handler.py    # Reaction event handling
├── reminder_system.py     # Reminder functionality
├── welcome_system.py      # Welcome message generation
├── rate_limiter.py        # Rate limiting logic
├── context_builder.py     # Channel/user context collection
└── utils.py              # Shared utilities and constants
```

## Migration Plan

### Phase 1: Extract Utilities (High Priority)
- Move `JakeyConstants` to `bot/utils.py`
- Move error handling functions to `bot/utils.py`
- Move helper methods (`typing_delay`, `safe_eval_math`, etc.) to `bot/utils.py`

### Phase 2: Extract Core Processing (High Priority)
- Move message processing logic to `bot/message_processor.py`
- Move AI response generation to `bot/message_processor.py`
- Move context building to `bot/context_builder.py`

### Phase 3: Extract Specialized Systems (Medium Priority)
- Move airdrop logic to `bot/airdrop_processor.py`
- Move reaction handling to `bot/reaction_handler.py`
- Move reminder system to `bot/reminder_system.py`
- Move welcome system to `bot/welcome_system.py`

### Phase 4: Simplify Main Client (Low Priority)
- Keep only Discord event handlers in `bot/client.py`
- Delegate all business logic to specialized modules
- Maintain clean dependency injection

## Benefits
- **Maintainability**: Each module has single responsibility
- **Testability**: Smaller modules easier to unit test
- **Readability**: Clear separation of concerns
- **Reusability**: Logic can be reused across different contexts
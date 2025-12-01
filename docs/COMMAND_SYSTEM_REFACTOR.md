# Command System Refactor Plan

## Current Issues
- **2179 lines** in single `commands.py` file
- **35+ commands** mixed together
- **No clear categorization** or separation
- **Hard to maintain** and test individual commands

## Proposed Structure

```
bot/commands/
├── __init__.py              # Command registration and imports
├── ai_commands.py           # %image, %ask, %model, %status
├── utility_commands.py      # %time, %calc, %help, %ping
├── crypto_commands.py       # %balance, %tip, %crypto, %stock
├── admin_commands.py        # Admin-only commands (%shutdown, %stats)
├── memory_commands.py       # %remember, %recall, %forget
├── moderation_commands.py   # %kick, %ban, %mute (if any)
└── fun_commands.py          # %keno, %trivia, %roll, etc.
```

## Migration Strategy

### Phase 1: Create Base Command Structure
```python
# bot/commands/__init__.py
from .ai_commands import setup_ai_commands
from .utility_commands import setup_utility_commands
from .crypto_commands import setup_crypto_commands
# ... other imports

def setup_commands(bot):
    """Register all command modules with the bot"""
    setup_ai_commands(bot)
    setup_utility_commands(bot)
    setup_crypto_commands(bot)
    # ... register other command groups
```

### Phase 2: Extract Command Groups

#### AI Commands (`ai_commands.py`)
- `%image` - Image generation
- `%ask` - AI text generation
- `%model` - Model switching
- `%status` - AI provider status

#### Utility Commands (`utility_commands.py`)
- `%help` - Help system
- `%ping` - Bot responsiveness
- `%time` - Time/date commands
- `%calc` - Calculator

#### Crypto Commands (`crypto_commands.py`)
- `%balance` - Check balances
- `%tip` - Send tips
- `%crypto` - Price lookups
- `%stock` - Stock prices

### Phase 3: Shared Utilities
```python
# bot/commands/base.py
class BaseCommand:
    """Base class for all commands with common functionality"""

    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, ctx) -> bool:
        """Common permission checking"""
        pass

    async def handle_error(self, ctx, error):
        """Common error handling"""
        pass
```

## Benefits
- **Modularity**: Each command group is self-contained
- **Maintainability**: Easier to find and modify specific commands
- **Testing**: Can test command groups independently
- **Scalability**: Easy to add new command categories
- **Code Reuse**: Shared utilities and base classes

## Implementation Priority
1. **High**: Extract AI commands (most complex)
2. **High**: Extract utility commands (frequently used)
3. **Medium**: Extract crypto commands (business logic)
4. **Low**: Extract remaining specialized commands
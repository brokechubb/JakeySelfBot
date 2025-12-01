# Error Handling Standardization Plan

## Current Issues
- **Inconsistent patterns**: Bare `except:` clauses mixed with specific exceptions
- **No centralized error handling**: Each module handles errors differently
- **Poor error classification**: No distinction between recoverable vs fatal errors
- **Inconsistent logging**: Different log levels and formats across modules

## Proposed Error Handling Hierarchy

```python
# utils/exceptions.py
from enum import Enum
from typing import Optional, Dict, Any

class ErrorSeverity(Enum):
    LOW = "low"          # Non-critical, can continue
    MEDIUM = "medium"    # Important but recoverable
    HIGH = "high"        # Critical, may require attention
    FATAL = "fatal"      # System-breaking, requires restart

class JakeyError(Exception):
    """Base exception for all Jakey-related errors"""

    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: Optional[Dict[str, Any]] = None, recoverable: bool = True):
        super().__init__(message)
        self.severity = severity
        self.context = context or {}
        self.recoverable = recoverable

class APIError(JakeyError):
    """API-related errors (Pollinations, OpenRouter, etc.)"""
    pass

class DatabaseError(JakeyError):
    """Database operation errors"""
    pass

class DiscordError(JakeyError):
    """Discord API errors"""
    pass

class ConfigurationError(JakeyError):
    """Configuration-related errors"""
    pass

class ValidationError(JakeyError):
    """Input validation errors"""
    pass
```

## Standardized Error Handler

```python
# utils/error_handler.py
import logging
from typing import Optional, Callable, Any
from .exceptions import JakeyError, ErrorSeverity

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling with consistent logging and recovery"""

    @staticmethod
    def handle_error(error: Exception, context: str = "",
                    user_id: Optional[str] = None,
                    recoverable_action: Optional[Callable] = None) -> str:
        """
        Handle an error with consistent logging and user messaging

        Args:
            error: The exception that occurred
            context: Description of where the error occurred
            user_id: User ID for context (optional)
            recoverable_action: Function to call if error is recoverable

        Returns:
            User-friendly error message
        """

        # Classify error
        if isinstance(error, JakeyError):
            jakey_error = error
        else:
            # Wrap unknown errors
            jakey_error = JakeyError(
                str(error),
                severity=ErrorSeverity.MEDIUM,
                context={"original_type": type(error).__name__}
            )

        # Log error with appropriate level
        log_message = f"{context}: {jakey_error.message}"
        if user_id:
            log_message = f"User {user_id} - {log_message}"

        if jakey_error.context:
            log_message += f" | Context: {jakey_error.context}"

        if jakey_error.severity == ErrorSeverity.FATAL:
            logger.critical(log_message)
        elif jakey_error.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif jakey_error.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Attempt recovery if possible
        if jakey_error.recoverable and recoverable_action:
            try:
                recoverable_action()
                logger.info(f"Successfully recovered from error in {context}")
            except Exception as recovery_error:
                logger.error(f"Recovery failed in {context}: {recovery_error}")

        # Return user-friendly message
        return ErrorHandler._get_user_message(jakey_error)

    @staticmethod
    def _get_user_message(error: JakeyError) -> str:
        """Generate user-friendly error messages"""
        base_messages = {
            ErrorSeverity.LOW: "Something minor happened, but I'm still working!",
            ErrorSeverity.MEDIUM: "I encountered an issue, but I'm handling it.",
            ErrorSeverity.HIGH: "I'm having some trouble right now.",
            ErrorSeverity.FATAL: "Critical error occurred. Please contact an administrator."
        }

        message = base_messages.get(error.severity, "An error occurred.")

        # Add specific guidance for common error types
        if isinstance(error, APIError):
            message += " The AI service might be temporarily unavailable."
        elif isinstance(error, DatabaseError):
            message += " There might be a temporary data issue."
        elif isinstance(error, ValidationError):
            message += " Please check your input and try again."

        return message
```

## Usage Examples

```python
# Before (inconsistent)
try:
    result = api_call()
except Exception as e:
    logger.error(f"API call failed: {e}")
    return "Something went wrong"

# After (standardized)
from utils.error_handler import ErrorHandler
from utils.exceptions import APIError

try:
    result = api_call()
except Exception as e:
    error_msg = ErrorHandler.handle_error(
        APIError("Failed to call external API", context={"api": "pollinations"}),
        context="AI text generation",
        user_id=str(ctx.author.id)
    )
    return error_msg
```

## Migration Strategy

### Phase 1: Create Exception Hierarchy
- Implement `utils/exceptions.py` with base error classes
- Define specific error types for different domains

### Phase 2: Create Error Handler
- Implement `utils/error_handler.py` with centralized logic
- Add consistent logging and user messaging

### Phase 3: Update Existing Code
- Replace bare `except:` clauses with specific exceptions
- Wrap external API calls with appropriate error types
- Update logging calls to use error handler

### Phase 4: Add Error Recovery
- Implement recovery actions for common error scenarios
- Add circuit breaker integration for repeated failures

## Benefits
- **Consistency**: All errors handled the same way
- **Debugging**: Better error classification and context
- **User Experience**: Appropriate error messages for different scenarios
- **Monitoring**: Centralized error tracking and alerting
- **Recovery**: Automatic handling of recoverable errors
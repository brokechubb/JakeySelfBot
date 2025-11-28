"""
Error handling utilities for JakeySelfBot.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from utils.logging_config import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories."""
    USER_INPUT = "user_input"
    PERMISSION = "permission"
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    API = "api"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class SanitizedError:
    """Sanitized error representation."""
    
    def __init__(
        self,
        user_message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.user_message = user_message
        self.category = category
        self.severity = severity
        self.error_id = error_id or f"ERR_{datetime.now().strftime('%H%M%S')}"
        self.context = context or {}
        self.original_error = original_error
        self.timestamp = datetime.now()


def sanitize_error_message(error_message: str) -> str:
    """
    Remove sensitive information from error messages.
    
    Args:
        error_message: Raw error message
        
    Returns:
        Sanitized error message
    """
    if not error_message:
        return "An error occurred"
    
    import re
    sanitized = error_message
    
    # Remove URLs first (before paths)
    sanitized = re.sub(r'https?://[^\s]+', '[URL]', sanitized)
    
    # Remove database connection strings
    sanitized = re.sub(r'(sqlite:///[^\s]+|mysql://[^\s]+|postgresql://[^\s]+)', '[DATABASE]', sanitized)
    
    # Remove file paths
    sanitized = re.sub(r'[/\\][a-zA-Z0-9_\-/\\\.]+', '[PATH]', sanitized)
    
    # Remove potential API keys (including sk- prefixes)
    sanitized = re.sub(r'\b[A-Za-z0-9]{15,}\b', '[KEY]', sanitized)
    sanitized = re.sub(r'sk-[A-Za-z0-9]{20,}', '[KEY]', sanitized)
    
    # Remove email addresses
    sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)
    
    # Remove IP addresses
    sanitized = re.sub(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '[IP]', sanitized)
    
    # Remove stack traces
    sanitized = re.sub(r'Traceback \(most recent call last\):.*?$', '', sanitized, flags=re.MULTILINE | re.DOTALL)
    
    # Clean up and limit length
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."
    
    return sanitized or "Sanitized error message"


def categorize_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorCategory:
    """
    Categorize an error based on type and context.
    
    Args:
        error: The exception to categorize
        context: Additional context
        
    Returns:
        ErrorCategory
    """
    error_type = type(error).__name__
    error_message = str(error).lower()
    
    # Check context first
    if context:
        operation = context.get('operation', '').lower()
        if 'api' in operation:
            return ErrorCategory.API
        if 'database' in operation:
            return ErrorCategory.DATABASE
        if 'permission' in operation:
            return ErrorCategory.PERMISSION
    
    # Categorize by exception type
    if error_type in ['ValueError', 'TypeError', 'AttributeError', 'KeyError']:
        return ErrorCategory.USER_INPUT
    elif error_type in ['PermissionError', 'Forbidden']:
        return ErrorCategory.PERMISSION
    elif error_type in ['ConnectionError', 'TimeoutError']:
        return ErrorCategory.NETWORK
    elif 'database' in error_message or 'sqlite' in error_message:
        return ErrorCategory.DATABASE
    elif 'api' in error_message or 'http' in error_message:
        return ErrorCategory.API
    elif 'permission' in error_message or 'forbidden' in error_message:
        return ErrorCategory.PERMISSION
    
    return ErrorCategory.UNKNOWN


def get_user_message(category: ErrorCategory, severity: ErrorSeverity) -> str:
    """
    Get appropriate user-friendly message for error category and severity.
    
    Args:
        category: Error category
        severity: Error severity
        
    Returns:
        User-friendly error message
    """
    messages = {
        ErrorCategory.USER_INPUT: {
            ErrorSeverity.LOW: "⚠️ Invalid input. Please check your command and try again.",
            ErrorSeverity.MEDIUM: "💀 Command format error. Please check the usage instructions.",
            ErrorSeverity.HIGH: "❌ Invalid command parameters. Please review the help documentation.",
            ErrorSeverity.CRITICAL: "🚫 Command rejected due to invalid input."
        },
        ErrorCategory.PERMISSION: {
            ErrorSeverity.LOW: "🔒 You don't have permission for this action.",
            ErrorSeverity.MEDIUM: "❌ Access denied. This action requires special permissions.",
            ErrorSeverity.HIGH: "🚫 Unauthorized action. This incident will be logged.",
            ErrorSeverity.CRITICAL: "⛔ Security violation detected. Access denied."
        },
        ErrorCategory.SYSTEM: {
            ErrorSeverity.LOW: "🔧 System temporarily unavailable. Please try again.",
            ErrorSeverity.MEDIUM: "💀 Internal system error. Please try again later.",
            ErrorSeverity.HIGH: "❌ System error. The issue has been logged for review.",
            ErrorSeverity.CRITICAL: "🚫 Critical system error. Please contact support."
        },
        ErrorCategory.NETWORK: {
            ErrorSeverity.LOW: "🌐 Connection issue. Please check your internet connection.",
            ErrorSeverity.MEDIUM: "💀 Network error. Please try again in a moment.",
            ErrorSeverity.HIGH: "❌ Network unavailable. Please try again later.",
            ErrorSeverity.CRITICAL: "🚫 Network failure. Service temporarily unavailable."
        },
        ErrorCategory.DATABASE: {
            ErrorSeverity.LOW: "📊 Data temporarily unavailable. Please try again.",
            ErrorSeverity.MEDIUM: "💀 Database error. Please try again in a moment.",
            ErrorSeverity.HIGH: "❌ Data access error. The issue has been logged.",
            ErrorSeverity.CRITICAL: "🚫 Database failure. Service temporarily unavailable."
        },
        ErrorCategory.API: {
            ErrorSeverity.LOW: "🔌 External service temporarily unavailable.",
            ErrorSeverity.MEDIUM: "💀 API error. Please try again in a moment.",
            ErrorSeverity.HIGH: "❌ External service error. Please try again later.",
            ErrorSeverity.CRITICAL: "🚫 External service failure. Service temporarily unavailable."
        },
        ErrorCategory.RATE_LIMIT: {
            ErrorSeverity.LOW: "⏱️ Please wait a moment before trying again.",
            ErrorSeverity.MEDIUM: "💀 Rate limit exceeded. Please wait before trying again.",
            ErrorSeverity.HIGH: "❌ Too many requests. Please wait before trying again.",
            ErrorSeverity.CRITICAL: "🚫 Rate limit exceeded. Please wait before trying again."
        },
        ErrorCategory.UNKNOWN: {
            ErrorSeverity.LOW: "❓ Something went wrong. Please try again.",
            ErrorSeverity.MEDIUM: "💀 An error occurred. Please try again later.",
            ErrorSeverity.HIGH: "❌ Unexpected error. The issue has been logged.",
            ErrorSeverity.CRITICAL: "🚫 Critical error. Please contact support."
        }
    }
    
    return messages.get(category, {}).get(severity, "💀 An error occurred. Please try again.")


def determine_severity(error: Exception, category: ErrorCategory) -> ErrorSeverity:
    """
    Determine error severity.
    
    Args:
        error: The exception
        category: Error category
        
    Returns:
        ErrorSeverity
    """
    error_type = type(error).__name__
    
    # Critical errors
    if error_type in ['SystemExit', 'KeyboardInterrupt', 'MemoryError']:
        return ErrorSeverity.CRITICAL
    
    # High severity
    if category in [ErrorCategory.PERMISSION]:
        return ErrorSeverity.HIGH
    if error_type in ['ImportError', 'ModuleNotFoundError']:
        return ErrorSeverity.HIGH
    
    # Medium severity
    if category in [ErrorCategory.DATABASE, ErrorCategory.API, ErrorCategory.SYSTEM]:
        return ErrorSeverity.MEDIUM
    
    # Low severity
    if category in [ErrorCategory.USER_INPUT, ErrorCategory.RATE_LIMIT]:
        return ErrorSeverity.LOW
    
    return ErrorSeverity.MEDIUM


def handle_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    custom_message: Optional[str] = None,
    user_id: Optional[str] = None
) -> SanitizedError:
    """
    Handle an error and return a sanitized version.
    
    Args:
        error: The exception to handle
        context: Additional context information
        custom_message: Optional custom user message
        user_id: User ID for rate limiting
        
    Returns:
        SanitizedError instance
    """
    category = categorize_error(error, context)
    severity = determine_severity(error, category)
    
    # Use custom message or get appropriate user message
    if custom_message:
        user_message = custom_message
    else:
        user_message = get_user_message(category, severity)
    
    # Create sanitized error
    sanitized_error = SanitizedError(
        user_message=user_message,
        category=category,
        severity=severity,
        context=context,
        original_error=error
    )
    
    # Log the detailed error internally
    log_level = {
        ErrorSeverity.LOW: logging.INFO,
        ErrorSeverity.MEDIUM: logging.WARNING,
        ErrorSeverity.HIGH: logging.ERROR,
        ErrorSeverity.CRITICAL: logging.CRITICAL
    }.get(severity, logging.WARNING)
    
    logger.log(
        log_level,
        f"Error {sanitized_error.error_id}: {sanitized_error.user_message} | "
        f"Original: {type(error).__name__}: {sanitize_error_message(str(error))} | "
        f"Context: {context}"
    )
    
    return sanitized_error


def safe_execute(func, *args, default_return=None, error_context=None, **kwargs):
    """
    Safely execute a function and handle any errors.
    
    Args:
        func: Function to execute
        *args: Function arguments
        default_return: Default return value on error
        error_context: Context for error handling
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in safe_execute: {type(e).__name__}: {str(e)}")
        if error_context:
            logger.error(f"Context: {error_context}")
        return default_return
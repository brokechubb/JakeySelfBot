"""
Tests for the error handling system.
"""

import unittest
import logging
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.error_handler import (
    sanitize_error_message, categorize_error, get_user_message,
    determine_severity, handle_error, safe_execute,
    ErrorSeverity, ErrorCategory, SanitizedError
)


class TestErrorSanitization(unittest.TestCase):
    """Test error message sanitization."""
    
    def test_sanitize_file_paths(self):
        """Test removing file paths from error messages."""
        raw_message = "File not found: /home/user/secrets.txt"
        sanitized = sanitize_error_message(raw_message)
        
        self.assertNotIn("/home/user/secrets.txt", sanitized)
        self.assertIn("[PATH]", sanitized)
    
    def test_sanitize_database_strings(self):
        """Test removing database connection strings."""
        raw_message = "Connection failed to sqlite:///home/user/data.db"
        sanitized = sanitize_error_message(raw_message)
        
        self.assertNotIn("sqlite:///home/user/data.db", sanitized)
        self.assertIn("[DATABASE]", sanitized)
    
    def test_sanitize_api_keys(self):
        """Test removing potential API keys."""
        raw_message = "Invalid API key: sk-1234567890abcdef1234567890abcdef"
        sanitized = sanitize_error_message(raw_message)
        
        self.assertNotIn("sk-1234567890abcdef1234567890abcdef", sanitized)
        self.assertIn("[KEY]", sanitized)
    
    def test_sanitize_emails(self):
        """Test removing email addresses."""
        raw_message = "Email sent to user@example.com failed"
        sanitized = sanitize_error_message(raw_message)
        
        self.assertNotIn("user@example.com", sanitized)
        self.assertIn("[EMAIL]", sanitized)
    
    def test_sanitize_ips(self):
        """Test removing IP addresses."""
        raw_message = "Connection to 192.168.1.1 failed"
        sanitized = sanitize_error_message(raw_message)
        
        self.assertNotIn("192.168.1.1", sanitized)
        self.assertIn("[IP]", sanitized)
    
    def test_sanitize_urls(self):
        """Test removing URLs."""
        raw_message = "Request to https://api.example.com/v1/users failed"
        sanitized = sanitize_error_message(raw_message)
        
        self.assertNotIn("https://api.example.com/v1/users", sanitized)
        self.assertIn("[URL]", sanitized)
    
    def test_sanitize_stack_traces(self):
        """Test removing stack traces."""
        raw_message = """Error occurred
Traceback (most recent call last):
  File "/home/user/app.py", line 42, in main
    raise ValueError("Test error")
ValueError: Test error"""
        
        sanitized = sanitize_error_message(raw_message)
        
        self.assertNotIn("Traceback", sanitized)
        self.assertNotIn("/home/user/app.py", sanitized)
    
    def test_truncate_long_messages(self):
        """Test truncating long error messages."""
        raw_message = "A" * 300
        sanitized = sanitize_error_message(raw_message)
        
        self.assertLessEqual(len(sanitized), 200)
        # Should be truncated if original was longer than 200
        self.assertLess(len(sanitized), len(raw_message))
    
    def test_empty_message(self):
        """Test handling empty error messages."""
        sanitized = sanitize_error_message("")
        self.assertEqual(sanitized, "An error occurred")
        
        sanitized = sanitize_error_message(None)
        self.assertEqual(sanitized, "An error occurred")


class TestErrorCategorization(unittest.TestCase):
    """Test error categorization."""
    
    def test_categorize_user_input_errors(self):
        """Test categorizing user input errors."""
        errors = [
            ValueError("Invalid input"),
            TypeError("Wrong type"),
            AttributeError("Missing attribute"),
            KeyError("Key not found")
        ]
        
        for error in errors:
            category = categorize_error(error)
            self.assertEqual(category, ErrorCategory.USER_INPUT)
    
    def test_categorize_permission_errors(self):
        """Test categorizing permission errors."""
        error = Exception("Permission denied")
        category = categorize_error(error)
        self.assertEqual(category, ErrorCategory.PERMISSION)
        
        error = Exception("Access forbidden")
        category = categorize_error(error)
        self.assertEqual(category, ErrorCategory.PERMISSION)
    
    def test_categorize_database_errors(self):
        """Test categorizing database errors."""
        error = Exception("SQLite database locked")
        category = categorize_error(error)
        self.assertEqual(category, ErrorCategory.DATABASE)
    
    def test_categorize_with_context(self):
        """Test categorizing with context."""
        error = Exception("Generic error")
        
        # API context
        context_api = {"operation": "api_call"}
        category = categorize_error(error, context_api)
        self.assertEqual(category, ErrorCategory.API)
        
        # Database context
        context_db = {"operation": "database_query"}
        category = categorize_error(error, context_db)
        self.assertEqual(category, ErrorCategory.DATABASE)


class TestSeverityDetermination(unittest.TestCase):
    """Test error severity determination."""
    
    def test_critical_severity(self):
        """Test critical severity errors."""
        critical_errors = [
            SystemExit("System exit"),
            KeyboardInterrupt("Interrupted"),
            MemoryError("Out of memory")
        ]
        
        for error in critical_errors:
            severity = determine_severity(error, ErrorCategory.SYSTEM)
            self.assertEqual(severity, ErrorSeverity.CRITICAL)
    
    def test_high_severity(self):
        """Test high severity errors."""
        error = Exception("Permission denied")
        severity = determine_severity(error, ErrorCategory.PERMISSION)
        self.assertEqual(severity, ErrorSeverity.HIGH)
        
        import_error = ImportError("Module not found")
        severity = determine_severity(import_error, ErrorCategory.SYSTEM)
        self.assertEqual(severity, ErrorSeverity.HIGH)
    
    def test_low_severity(self):
        """Test low severity errors."""
        error = ValueError("Invalid input")
        severity = determine_severity(error, ErrorCategory.USER_INPUT)
        self.assertEqual(severity, ErrorSeverity.LOW)


class TestUserMessages(unittest.TestCase):
    """Test user-friendly message generation."""
    
    def test_user_input_messages(self):
        """Test user input error messages."""
        low_msg = get_user_message(ErrorCategory.USER_INPUT, ErrorSeverity.LOW)
        self.assertIn("Invalid input", low_msg)
        
        high_msg = get_user_message(ErrorCategory.USER_INPUT, ErrorSeverity.HIGH)
        self.assertIn("Invalid command", high_msg)
    
    def test_permission_messages(self):
        """Test permission error messages."""
        msg = get_user_message(ErrorCategory.PERMISSION, ErrorSeverity.MEDIUM)
        self.assertIn("Access denied", msg)
    
    def test_system_messages(self):
        """Test system error messages."""
        msg = get_user_message(ErrorCategory.SYSTEM, ErrorSeverity.MEDIUM)
        self.assertIn("Internal system error", msg)


class TestErrorHandling(unittest.TestCase):
    """Test main error handling functions."""
    
    @patch('utils.error_handler.logger')
    def test_handle_error_basic(self, mock_logger):
        """Test basic error handling."""
        error = ValueError("Test error")
        context = {"test": "context"}
        
        sanitized = handle_error(error, context)
        
        self.assertIsInstance(sanitized, SanitizedError)
        self.assertEqual(sanitized.context, context)
        self.assertEqual(sanitized.original_error, error)
        self.assertEqual(sanitized.category, ErrorCategory.USER_INPUT)
        
        # Verify logging
        mock_logger.log.assert_called_once()
    
    @patch('utils.error_handler.logger')
    def test_handle_error_with_custom_message(self, mock_logger):
        """Test error handling with custom message."""
        error = ValueError("Test error")
        custom_message = "Custom error message"
        
        sanitized = handle_error(error, custom_message=custom_message)
        
        self.assertEqual(sanitized.user_message, custom_message)
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful function."""
        def success_func(x, y):
            return x + y
        
        result = safe_execute(success_func, 2, 3)
        self.assertEqual(result, 5)
    
    @patch('utils.error_handler.logger')
    def test_safe_execute_error(self, mock_logger):
        """Test safe_execute with function that raises error."""
        def error_func():
            raise ValueError("Test error")
        
        result = safe_execute(error_func, default_return="fallback")
        self.assertEqual(result, "fallback")
        
        # Verify error was logged
        mock_logger.error.assert_called_once()


class TestSanitizedError(unittest.TestCase):
    """Test SanitizedError class."""
    
    def test_sanitized_error_creation(self):
        """Test creating a sanitized error."""
        error = SanitizedError(
            user_message="Test error",
            category=ErrorCategory.USER_INPUT,
            severity=ErrorSeverity.LOW
        )
        
        self.assertEqual(error.user_message, "Test error")
        self.assertEqual(error.category, ErrorCategory.USER_INPUT)
        self.assertEqual(error.severity, ErrorSeverity.LOW)
        self.assertIsNotNone(error.error_id)
        self.assertIsNotNone(error.timestamp)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    @patch('utils.error_handler.logger')
    def test_complete_error_flow(self, mock_logger):
        """Test complete error handling flow."""
        # Simulate a realistic error
        try:
            raise Exception("Database connection failed to /home/user/data.db")
        except Exception as e:
            sanitized = handle_error(
                e, 
                context={
                    "operation": "database_query",
                    "user_id": "12345"
                }
            )
            
            # Verify sanitized error
            self.assertIsInstance(sanitized, SanitizedError)
            self.assertEqual(sanitized.category, ErrorCategory.DATABASE)
            self.assertNotIn("/home/user/data.db", sanitized.user_message)
            
            # Verify logging
            mock_logger.log.assert_called()
    
    def test_security_information_prevention(self):
        """Test that sensitive information is prevented from leaking."""
        sensitive_errors = [
            "API key 'sk-1234567890abcdef' is invalid",
            "Database connection to mysql://user:pass@localhost/db failed",
            "File /etc/passwd not found",
            "Email sent to admin@company.com failed",
            "Connection to 10.0.0.1:8080 timeout"
        ]
        
        for error_msg in sensitive_errors:
            sanitized = sanitize_error_message(error_msg)
            
            # Check that sensitive patterns are removed
            self.assertNotIn("sk-1234567890abcdef", sanitized)
            self.assertNotIn("mysql://user:pass@localhost/db", sanitized)
            self.assertNotIn("/etc/passwd", sanitized)
            self.assertNotIn("admin@company.com", sanitized)
            self.assertNotIn("10.0.0.1", sanitized)
            
            # Check that placeholders appear
            self.assertTrue(
                any(placeholder in sanitized for placeholder in ['[KEY]', '[DATABASE]', '[PATH]', '[EMAIL]', '[IP]'])
            )


if __name__ == '__main__':
    unittest.main()
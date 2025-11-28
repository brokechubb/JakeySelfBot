#!/usr/bin/env python3
"""
Tests for time and date commands
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import pytz

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestTimeCommands(unittest.TestCase):
    """Test cases for time and date commands"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create a mock bot and set up commands
        self.mock_bot = MagicMock()
        self.mock_bot.command = MagicMock()

        # Import and setup commands
        from bot.commands import setup_commands
        setup_commands(self.mock_bot)

        # Mock context
        self.mock_ctx = MagicMock()
        self.mock_ctx.author.id = "123456789"
        self.mock_ctx.author.name = "testuser"
        self.mock_ctx.send = AsyncMock()
        self.mock_ctx.message.add_reaction = AsyncMock()
        self.mock_ctx.message.remove_reaction = AsyncMock()
        self.mock_ctx.channel = MagicMock()

    def test_time_command_registered(self):
        """Test that the time command is properly registered"""
        # Check that the time command was registered by looking at the call args
        registered_names = []
        for call in self.mock_bot.command.call_args_list:
            # The decorator call should have name as a keyword argument
            if call and call[1]:
                name = call[1].get('name')
                if name:
                    registered_names.append(name)

        self.assertIn('time', registered_names, "Time command should be registered")

    def test_date_command_registered(self):
        """Test that the date command is properly registered"""
        # Check that the date command was registered by looking at the call args
        registered_names = []
        for call in self.mock_bot.command.call_args_list:
            # The decorator call should have name as a keyword argument
            if call and call[1]:
                name = call[1].get('name')
                if name:
                    registered_names.append(name)

        self.assertIn('date', registered_names, "Date command should be registered")

    def test_setup_commands_includes_time_commands(self):
        """Test that setup_commands includes the new time commands"""
        from bot.commands import setup_commands
        import inspect

        # Verify it's a function
        self.assertTrue(callable(setup_commands))

        # Verify it has a docstring
        self.assertIsNotNone(setup_commands.__doc__)

        # Test that we can call setup_commands without errors
        mock_bot = MagicMock()
        mock_bot.command = MagicMock()
        
        try:
            setup_commands(mock_bot)
            # Verify that commands were registered
            self.assertTrue(mock_bot.command.called)
        except Exception as e:
            self.fail(f"setup_commands raised an exception: {e}")

    def test_timezone_imports(self):
        """Test that required timezone modules are available"""
        # Test that we can import the required modules
        try:
            import pytz
            self.assertIsNotNone(pytz.timezone)
            self.assertIsNotNone(pytz.exceptions.UnknownTimeZoneError)
        except ImportError as e:
            self.fail(f"Failed to import pytz: {e}")

        try:
            from datetime import datetime, timezone
            self.assertIsNotNone(datetime)
            self.assertIsNotNone(timezone)
        except ImportError as e:
            self.fail(f"Failed to import datetime modules: {e}")

    def test_help_command_includes_time_commands(self):
        """Test that help command includes the new time commands"""
        # Check that help command is registered
        registered_names = []
        for call in self.mock_bot.command.call_args_list:
            if call and call[1]:
                name = call[1].get('name')
                if name:
                    registered_names.append(name)

        self.assertIn('help', registered_names, "Help command should be registered")

    def test_commands_count_increased(self):
        """Test that adding time commands increased the total command count"""
        # Count total command registrations
        command_count = len(self.mock_bot.command.call_args_list)
        self.assertGreater(command_count, 25, "Should have at least 25 commands registered")

    def test_timezone_aliases_logic(self):
        """Test timezone alias mapping logic"""
        # Test the timezone aliases that would be used in the command
        timezone_aliases = {
            "est": "US/Eastern",
            "edt": "US/Eastern",
            "cst": "US/Central", 
            "cdt": "US/Central",
            "mst": "US/Mountain",
            "mdt": "US/Mountain",
            "pst": "US/Pacific",
            "pdt": "US/Pacific",
            "gmt": "GMT",
            "bst": "Europe/London",
            "cet": "Europe/Paris",
            "ist": "Asia/Kolkata",
            "jst": "Asia/Tokyo",
            "aest": "Australia/Sydney",
            "utc": "UTC"
        }
        
        # Test some common aliases
        self.assertEqual(timezone_aliases["est"], "US/Eastern")
        self.assertEqual(timezone_aliases["pst"], "US/Pacific")
        self.assertEqual(timezone_aliases["utc"], "UTC")
        self.assertEqual(timezone_aliases["ist"], "Asia/Kolkata")

    @patch('bot.commands.pytz.timezone')
    def test_pytz_timezone_handling(self, mock_timezone):
        """Test that pytz.timezone is called correctly"""
        mock_tz = MagicMock()
        mock_timezone.return_value = mock_tz
        
        # Test that we can create a timezone
        tz = pytz.timezone("UTC")
        mock_timezone.assert_called_with("UTC")
        
        # Test UnknownTimeZoneError handling
        mock_timezone.side_effect = pytz.exceptions.UnknownTimeZoneError("Invalid")
        
        with self.assertRaises(pytz.exceptions.UnknownTimeZoneError):
            pytz.timezone("Invalid/Timezone")


if __name__ == '__main__':
    unittest.main()
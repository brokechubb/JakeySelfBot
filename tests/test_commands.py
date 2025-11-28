#!/usr/bin/env python3
"""
Tests for command functionality
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestCommands(unittest.TestCase):
    """Test cases for bot commands"""

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

    def test_commands_registered(self):
        """Test that commands are properly registered with the bot"""
        # Verify that bot.command was called (commands were registered)
        self.assertTrue(self.mock_bot.command.called)

        # Check that multiple commands were registered by counting calls
        call_count = self.mock_bot.command.call_count
        self.assertGreater(call_count, 5)  # Should have at least 5+ commands registered

    def test_setup_commands_no_errors(self):
        """Test that setup_commands can be called without errors"""
        # This test just verifies that the setup_commands function exists and can be called
        from bot.commands import setup_commands
        mock_bot = MagicMock()
        mock_bot.command = MagicMock()

        # Should not raise any exceptions
        try:
            setup_commands(mock_bot)
            # Verify that commands were registered
            self.assertTrue(mock_bot.command.called)
        except Exception as e:
            self.fail(f"setup_commands raised an exception: {e}")

    def test_command_names_registered(self):
        """Test that expected command names are registered"""
        # Check that key commands are registered by name
        registered_names = []
        for call in self.mock_bot.command.call_args_list:
            name = call[1].get('name')
            if name:
                registered_names.append(name)

        # Check for some key commands
        expected_commands = ['ping', 'model', 'remember', 'wen', 'image']
        for cmd in expected_commands:
            self.assertIn(cmd, registered_names, f"Command '{cmd}' should be registered")

    def test_setup_commands_structure(self):
        """Test that setup_commands has the expected structure"""
        from bot.commands import setup_commands
        import inspect

        # Verify it's a function
        self.assertTrue(callable(setup_commands))

        # Verify it has a docstring
        self.assertIsNotNone(setup_commands.__doc__)

        # Verify it takes one parameter (bot_instance)
        sig = inspect.signature(setup_commands)
        params = list(sig.parameters.keys())
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0], 'bot_instance')

if __name__ == '__main__':
    unittest.main()
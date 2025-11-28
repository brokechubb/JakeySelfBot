#!/usr/bin/env python3
"""
Tests for userinfo command role display functionality
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestUserInfoRoles(unittest.TestCase):
    """Test cases for userinfo command with role display"""

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

        # Mock guild and member for role testing
        self.mock_guild = MagicMock()
        self.mock_guild.id = 987654321
        self.mock_ctx.guild = self.mock_guild

        # Mock member with roles
        self.mock_member = MagicMock()
        self.mock_member.id = "123456789"
        self.mock_member.name = "testuser"
        self.mock_member.display_name = "Test User"
        self.mock_member.bot = False

        # Create mock roles
        self.mock_role1 = MagicMock()
        self.mock_role1.name = "Admin"
        self.mock_role2 = MagicMock()
        self.mock_role2.name = "Moderator"
        self.mock_role_everyone = MagicMock()
        self.mock_role_everyone.name = "@everyone"

        # Set up roles list (including @everyone)
        self.mock_member.roles = [self.mock_role_everyone, self.mock_role1, self.mock_role2]

        # Mock user
        self.mock_user = MagicMock()
        self.mock_user.id = "123456789"
        self.mock_user.name = "testuser"
        self.mock_user.bot = False

    def test_userinfo_command_exists(self):
        """Test that userinfo command exists and has correct docstring"""
        # Check that userinfo command was registered
        command_found = False
        for call in self.mock_bot.command.call_args_list:
            kwargs = call[1] if len(call) > 1 else {}
            if 'name' in kwargs and kwargs['name'] == 'userinfo':
                command_found = True
                break

        self.assertTrue(command_found, "userinfo command should be registered with the bot")

    def test_userinfo_command_registration(self):
        """Test that userinfo command is properly registered"""
        # Check that userinfo command was registered
        command_found = False
        for call in self.mock_bot.command.call_args_list:
            kwargs = call[1] if len(call) > 1 else {}
            if 'name' in kwargs and kwargs['name'] == 'userinfo':
                command_found = True
                break

        self.assertTrue(command_found, "userinfo command should be registered with the bot")

    def test_userinfo_docstring_updated(self):
        """Test that userinfo command docstring mentions roles"""
        # Import the commands module directly to check the function
        from bot.commands import setup_commands
        import inspect

        # Create a mock bot to capture the registered function
        mock_bot = MagicMock()
        mock_bot.command = MagicMock()

        # Store the registered function
        registered_functions = {}

        def mock_command_decorator(name=None):
            def decorator(func):
                registered_functions[name] = func
                return func
            return decorator

        mock_bot.command.side_effect = mock_command_decorator

        # Setup commands
        setup_commands(mock_bot)

        # Check that userinfo function mentions roles
        self.assertIn('userinfo', registered_functions)
        userinfo_func = registered_functions['userinfo']
        self.assertIn("roles", userinfo_func.__doc__.lower())

if __name__ == '__main__':
    unittest.main()

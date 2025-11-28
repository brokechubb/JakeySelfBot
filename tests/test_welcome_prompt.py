"""
Test suite for WELCOME_PROMPT functionality.
Tests that custom welcome prompts are properly loaded from environment variables
and that template variables are correctly substituted.
"""

import os
import sys
import unittest
from unittest.mock import Mock
import asyncio

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestWelcomePromptFunctionality(unittest.TestCase):
    """Test cases for WELCOME_PROMPT functionality"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear any existing environment variables
        if 'WELCOME_PROMPT' in os.environ:
            del os.environ['WELCOME_PROMPT']

        # Reload config to ensure clean state
        if 'config' in sys.modules:
            del sys.modules['config']

    def test_welcome_prompt_default_value(self):
        """Test that WELCOME_PROMPT has correct default value"""
        from config import WELCOME_PROMPT
        self.assertEqual(
            WELCOME_PROMPT,
            "Welcome {username} to {server_name}!  We got {member_count} degenerates in here now. Generate a personalized, witty welcome message that fits Jakey's degenerate gambling personality. Introduce yourself, then direct them to <#1423523047855358042> so they can pick roles. Keep it brief and engaging."
        )

    def test_welcome_prompt_custom_value(self):
        """Test that WELCOME_PROMPT loads custom value from environment"""
        # Set custom environment variable
        os.environ['WELCOME_PROMPT'] = "Yo {username}#{discriminator} welcome to {server_name}! We got {member_count} degenerates. Wen bonus? 💀"

        # Reload config to pick up environment variable
        if 'config' in sys.modules:
            del sys.modules['config']

        from config import WELCOME_PROMPT
        self.assertEqual(
            WELCOME_PROMPT,
            "Yo {username}#{discriminator} welcome to {server_name}! We got {member_count} degenerates. Wen bonus? 💀"
        )

    def test_welcome_prompt_substitution(self):
        """Test that template variables are substituted correctly"""
        # Create mock member
        mock_member = Mock()
        mock_member.name = "TestUser"
        mock_member.discriminator = "1234"
        mock_member.guild = Mock()
        mock_member.guild.name = "TestServer"
        mock_member.guild.member_count = 42

        # Set custom prompt with template variables
        custom_prompt = "Welcome {username} to {server_name}! We now have {member_count} degenerates. wen bonus? 💀"

        # Test template substitution directly
        template_vars = {
            "{username}": mock_member.name,
            "{discriminator}": mock_member.discriminator,
            "{server_name}": mock_member.guild.name,
            "{member_count}": str(mock_member.guild.member_count),
        }

        # Replace all template variables
        substituted_prompt = custom_prompt
        for var, value in template_vars.items():
            substituted_prompt = substituted_prompt.replace(var, str(value))

        # Check that template variables were substituted
        self.assertEqual(
            substituted_prompt,
            "Welcome TestUser to TestServer! We now have 42 degenerates. wen bonus? 💀"
        )

    def tearDown(self):
        """Clean up after tests"""
        # Clear environment variable
        if 'WELCOME_PROMPT' in os.environ:
            del os.environ['WELCOME_PROMPT']

        # Reload config to ensure clean state for next tests
        if 'config' in sys.modules:
            del sys.modules['config']


if __name__ == '__main__':
    unittest.main()

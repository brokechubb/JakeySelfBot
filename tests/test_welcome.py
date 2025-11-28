#!/usr/bin/env python3
"""
Test suite for welcome message functionality.
Tests AI-generated welcome messages for new server members.
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import discord
import asyncio
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.client import JakeyBot
from utils.dependency_container import BotDependencies


class TestWelcomeFunctionality(unittest.TestCase):
    """Test cases for welcome message functionality"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock dependencies
        self.mock_deps = Mock(spec=BotDependencies)
        self.mock_deps.command_prefix = '%'
        self.mock_deps.ai_client = Mock()
        self.mock_deps.database = Mock()
        self.mock_deps.tool_manager = Mock()

        # Mock AI client methods
        self.mock_deps.ai_client.generate_text = Mock(return_value={'choices': [{'message': {'content': 'Welcome test message!'}}]})

        # Create mock member and guild
        self.mock_member = Mock(spec=discord.Member)
        self.mock_member.id = 123456789
        self.mock_member.name = "NewUser"
        self.mock_member.discriminator = "1234"
        self.mock_member.mention = "<@123456789>"

        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_guild.id = 987654321
        self.mock_guild.name = "Test Server"
        self.mock_guild.member_count = 42
        self.mock_guild.text_channels = []
        self.mock_guild.me = Mock()

        self.mock_member.guild = self.mock_guild

        # Create mock channel
        self.mock_channel = Mock(spec=discord.TextChannel)
        self.mock_channel.id = 111111111
        self.mock_channel.name = "general"
        self.mock_channel.send = AsyncMock()
        self.mock_channel.permissions_for.return_value.send_messages = True

    def _create_test_bot(self):
        """Create a JakeyBot instance for testing"""
        # Create a mock that has the necessary attributes and methods
        mock_bot = Mock()
        mock_bot.pollinations_api = self.mock_deps.ai_client
        mock_bot._connection = Mock(heartbeat_timeout=60.0)
        mock_bot.current_model = "test-model"
        
        # Import the real on_member_join method and bind it to our mock
        from bot.client import JakeyBot
        mock_bot.on_member_join = JakeyBot.on_member_join.__get__(mock_bot, JakeyBot)
        
        return mock_bot

    def test_welcome_feature_disabled(self):
        """Test that welcome messages are not sent when feature is disabled"""
        with patch('config.WELCOME_ENABLED', False):
            real_bot = self._create_test_bot()
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_not_called()

    def test_welcome_server_not_configured(self):
        """Test that welcome messages are not sent for unconfigured servers"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['999999999']):
            real_bot = self._create_test_bot()
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_not_called()

    def test_welcome_server_configured(self):
        """Test that welcome messages are sent for configured servers"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['111111111']):
            real_bot = self._create_test_bot()
            self.mock_guild.get_channel = Mock(return_value=self.mock_channel)
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_called_once()
            self.mock_channel.send.assert_called_once()

    def test_welcome_channel_fallback(self):
        """Test fallback to general channel when no specific channel configured"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['']):
            real_bot = self._create_test_bot()
            # Set up text channels for fallback
            general_channel = Mock(spec=discord.TextChannel)
            general_channel.name = "general"
            general_channel.send = AsyncMock()
            general_channel.permissions_for.return_value.send_messages = True
            self.mock_guild.text_channels = [general_channel]
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_called_once()
            general_channel.send.assert_called_once()

    def test_welcome_no_suitable_channel(self):
        """Test handling when no suitable channel is found"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['999999999']):  # Non-existent channel
            real_bot = self._create_test_bot()
            self.mock_guild.get_channel = Mock(return_value=None)
            self.mock_guild.text_channels = []
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_not_called()

    def test_welcome_no_channel_permissions(self):
        """Test handling when bot has no permissions to send messages"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['111111111']):
            real_bot = self._create_test_bot()
            restricted_channel = Mock(spec=discord.TextChannel)
            restricted_channel.name = "restricted"
            restricted_channel.send = AsyncMock()
            restricted_channel.permissions_for.return_value.send_messages = False
            self.mock_guild.get_channel = Mock(return_value=restricted_channel)
            self.mock_guild.text_channels = []
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_not_called()

    def test_welcome_message_generation(self):
        """Test AI welcome message generation"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['111111111']), \
             patch('config.WELCOME_PROMPT', 'Welcome {username} to {server_name}!'):
            real_bot = self._create_test_bot()
            self.mock_guild.get_channel = Mock(return_value=self.mock_channel)
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_called_once()
            self.mock_channel.send.assert_called_once()

    def test_welcome_message_generation_empty_response(self):
        """Test handling of empty AI response"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['111111111']):
            real_bot = self._create_test_bot()
            self.mock_deps.ai_client.generate_text = Mock(return_value={'choices': [{'message': {'content': ''}}]})
            self.mock_guild.get_channel = Mock(return_value=self.mock_channel)
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_called_once()
            # Should not send empty message
            self.mock_channel.send.assert_not_called()

    def test_welcome_message_generation_error(self):
        """Test handling of AI generation errors"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['111111111']):
            real_bot = self._create_test_bot()
            self.mock_deps.ai_client.generate_text.side_effect = Exception("AI error")
            self.mock_guild.get_channel = Mock(return_value=self.mock_channel)
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_called_once()
            # Should not send message on error
            self.mock_channel.send.assert_not_called()

    def test_welcome_custom_prompt_variables(self):
        """Test that all prompt variables are properly substituted"""
        with patch('config.WELCOME_ENABLED', True), \
             patch('config.WELCOME_SERVER_IDS', ['987654321']), \
             patch('config.WELCOME_CHANNEL_IDS', ['111111111']), \
             patch('config.WELCOME_PROMPT', 'Welcome {username}#{discriminator} to {server_name}! We have {member_count} members.'):
            real_bot = self._create_test_bot()
            self.mock_guild.get_channel = Mock(return_value=self.mock_channel)
            result = asyncio.run(real_bot.on_member_join(self.mock_member))
            self.assertIsNone(result)
            self.mock_deps.ai_client.generate_text.assert_called_once()
            call_args = self.mock_deps.ai_client.generate_text.call_args
            messages = call_args[1]['messages']
            # messages[0] is system message, messages[1] is user message
            user_message = messages[1]['content']
            self.assertIn("NewUser", user_message)
            self.assertIn("1234", user_message)
            self.assertIn("Test Server", user_message)
            self.assertIn("42", user_message)


if __name__ == '__main__':
    unittest.main()
import unittest
from unittest.mock import Mock, AsyncMock, patch
import discord
from config import GUILD_BLACKLIST

class TestGuildBlacklist(unittest.TestCase):
    """Test that the bot respects guild blacklist configuration"""
    
    def setUp(self):
        # Create a mock bot instance
        from bot.client import JakeyBot
        self.bot = JakeyBot(dependencies=Mock())
        self.bot.user = Mock()
        self.bot.user.id = 12345
        
        # Mock database methods
        self.bot.db = AsyncMock()
        self.bot.db.acheck_message_for_keywords = AsyncMock(return_value=False)
        
        # Mock the response method
        self.bot.process_jakey_response = AsyncMock()
        
        # Mock command processing
        self.bot.command_prefix = "!"
        self.bot.all_commands = {}
        self.bot.invoke = AsyncMock()
    
    @patch('bot.client.GUILD_BLACKLIST', ['999999999', '888888888'])
    async def test_ignores_blacklisted_guild(self):
        """Test that bot ignores messages from blacklisted guilds"""
        # Create a message from a blacklisted guild
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        message.author == self.bot.user  # Not the bot itself
        
        # Create a guild that's blacklisted
        message.guild = Mock()
        message.guild.id = 999999999
        message.guild.name = "Blacklisted Server"
        
        await self.bot.on_message(message)
        
        # Should NOT have called process_jakey_response
        self.bot.process_jakey_response.assert_not_called()
    
    @patch('bot.client.GUILD_BLACKLIST', ['999999999', '888888888'])
    async def test_responds_to_non_blacklisted_guild(self):
        """Test that bot responds to messages from non-blacklisted guilds"""
        # Create a message from a non-blacklisted guild
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        message.author != self.bot.user  # Not the bot itself
        
        # Create a guild that's NOT blacklisted
        message.guild = Mock()
        message.guild.id = 777777777
        message.guild.name = "Allowed Server"
        
        await self.bot.on_message(message)
        
        # Should have called process_jakey_response
        self.bot.process_jakey_response.assert_called_once()
    
    @patch('bot.client.GUILD_BLACKLIST', ['999999999', '888888888'])
    async def test_responds_to_dms(self):
        """Test that bot still responds to DMs even with guild blacklist"""
        # Create a DM message
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        message.author != self.bot.user  # Not the bot itself
        
        # No guild for DMs
        message.guild = None
        
        await self.bot.on_message(message)
        
        # Should have called process_jakey_response
        self.bot.process_jakey_response.assert_called_once()
    
    def test_guild_blacklist_configuration(self):
        """Test that guild blacklist is properly configured"""
        # Test that GUILD_BLACKLIST is a list (even if empty)
        self.assertIsInstance(GUILD_BLACKLIST, list)
        
        # Test that all items in GUILD_BLACKLIST are strings
        for guild_id in GUILD_BLACKLIST:
            self.assertIsInstance(guild_id, str)

if __name__ == '__main__':
    unittest.main()
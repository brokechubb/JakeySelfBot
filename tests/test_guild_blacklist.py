import unittest
from unittest.mock import Mock, AsyncMock, patch, PropertyMock
import discord
from config import GUILD_BLACKLIST


class TestGuildBlacklist(unittest.TestCase):
    """Test that the bot respects guild blacklist configuration"""
    
    def setUp(self):
        """Set up test fixtures"""
        from bot.client import JakeyBot
        self.bot = JakeyBot(dependencies=Mock())
        
        # Mock user using spec and patch
        mock_user = Mock()
        mock_user.id = 12345
        
        # Use patch.object to set the user property
        type(self.bot).user = PropertyMock(return_value=mock_user)
        
        self.bot.db = AsyncMock()
        self.bot.db.acheck_message_for_keywords = AsyncMock(return_value=False)
        self.bot.process_jakey_response = AsyncMock()
        self.bot.command_prefix = "!"
        self.bot.all_commands = {}
        self.bot.invoke = AsyncMock()
    
    @patch('bot.client.GUILD_BLACKLIST', ['999999999', '888888888'])
    async def test_ignores_blacklisted_guild(self):
        """Test that bot ignores messages from blacklisted guilds"""
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        
        message.guild = Mock()
        message.guild.id = 999999999
        message.guild.name = "Blacklisted Server"
        
        await self.bot.on_message(message)
        
        self.bot.process_jakey_response.assert_not_called()
    
    @patch('bot.client.GUILD_BLACKLIST', ['999999999', '888888888'])
    async def test_responds_to_non_blacklisted_guild(self):
        """Test that bot responds to messages from non-blacklisted guilds"""
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        
        message.guild = Mock()
        message.guild.id = 777777777
        message.guild.name = "Allowed Server"
        
        await self.bot.on_message(message)
        
        self.bot.process_jakey_response.assert_called_once()
    
    @patch('bot.client.GUILD_BLACKLIST', ['999999999', '888888888'])
    async def test_responds_to_dms(self):
        """Test that bot still responds to DMs even with guild blacklist"""
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        
        message.guild = None
        message.channel = Mock()
        message.channel.type = discord.ChannelType.private
        
        await self.bot.on_message(message)
        
        self.bot.process_jakey_response.assert_called_once()


class TestGuildBlacklistConfiguration(unittest.TestCase):
    """Test guild blacklist configuration loading"""
    
    def test_guild_blacklist_is_list(self):
        """Test that GUILD_BLACKLIST is a list"""
        self.assertIsInstance(GUILD_BLACKLIST, list)
    
    @patch('config.GUILD_BLACKLIST', ['123456', '789012'])
    def test_guild_blacklist_can_be_patched(self):
        """Test that GUILD_BLACKLIST can be patched"""
        from config import GUILD_BLACKLIST
        self.assertEqual(GUILD_BLACKLIST, ['123456', '789012'])


if __name__ == '__main__':
    unittest.main()

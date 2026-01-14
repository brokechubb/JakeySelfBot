import unittest
from unittest.mock import Mock, AsyncMock, PropertyMock
import discord


class TestJakeNameRecognition(unittest.TestCase):
    """Test that the bot responds to both 'jakey' and 'jake' mentions"""
    
    def setUp(self):
        """Set up test fixtures"""
        from bot.client import JakeyBot
        self.bot = JakeyBot(dependencies=Mock())
        
        mock_user = Mock()
        mock_user.id = 12345
        mock_user.mentioned_in = Mock(return_value=False)
        
        type(self.bot).user = PropertyMock(return_value=mock_user)
        
        self.bot.db = AsyncMock()
        self.bot.db.acheck_message_for_keywords = AsyncMock(return_value=False)
        self.bot.process_jakey_response = AsyncMock()
    
    async def test_responds_to_jakey(self):
        """Test that bot responds to 'jakey' mentions"""
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        
        await self.bot.on_message(message)
        
        self.bot.process_jakey_response.assert_called_once()
    
    async def test_responds_to_jake(self):
        """Test that bot responds to 'jake' mentions"""
        message = Mock()
        message.content = "hello jake"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        
        await self.bot.on_message(message)
        
        self.bot.process_jakey_response.assert_called_once()
    
    async def test_does_not_respond_to_other_names(self):
        """Test that bot doesn't respond to unrelated names"""
        message = Mock()
        message.content = "hello john"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        
        await self.bot.on_message(message)
        
        self.bot.process_jakey_response.assert_not_called()


if __name__ == '__main__':
    unittest.main()

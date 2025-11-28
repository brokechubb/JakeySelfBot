import unittest
from unittest.mock import Mock, AsyncMock
import discord

class TestJakeNameRecognition(unittest.TestCase):
    """Test that the bot responds to both 'jakey' and 'jake' mentions"""
    
    def setUp(self):
        # Create a mock bot instance
        from bot.client import JakeyBot
        self.bot = JakeyBot(dependencies=Mock())
        self.bot.user = Mock()
        self.bot.user.id = 12345
        self.bot.user.mentioned_in = Mock(return_value=False)
        
        # Mock database methods
        self.bot.db = AsyncMock()
        self.bot.db.acheck_message_for_keywords = AsyncMock(return_value=False)
        
        # Mock the response method
        self.bot.process_jakey_response = AsyncMock()
    
    async def test_responds_to_jakey(self):
        """Test that bot responds to 'jakey' mentions"""
        message = Mock()
        message.content = "hello jakey"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        message.author == self.bot.user  # Not the bot itself
        
        await self.bot.on_message(message)
        
        # Should have called process_jakey_response
        self.bot.process_jakey_response.assert_called_once()
    
    async def test_responds_to_jake(self):
        """Test that bot responds to 'jake' mentions"""
        message = Mock()
        message.content = "hello jake"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        message.author != self.bot.user  # Not the bot itself
        
        await self.bot.on_message(message)
        
        # Should have called process_jakey_response
        self.bot.process_jakey_response.assert_called_once()
    
    async def test_does_not_respond_to_other_names(self):
        """Test that bot doesn't respond to unrelated names"""
        message = Mock()
        message.content = "hello john"
        message.author = Mock()
        message.author.id = 999
        message.author.bot = False
        message.author != self.bot.user  # Not the bot itself
        
        await self.bot.on_message(message)
        
        # Should NOT have called process_jakey_response
        self.bot.process_jakey_response.assert_not_called()

if __name__ == '__main__':
    unittest.main()
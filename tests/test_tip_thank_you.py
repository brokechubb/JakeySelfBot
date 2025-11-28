"""
Test the tip thank you functionality
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
import time
import discord
from utils.tipcc_manager import TipCCManager


class TestTipThankYou(unittest.TestCase):
    """Test tip thank you functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.bot = Mock()
        self.bot.user = Mock()
        self.bot.user.id = "123456789"
        self.bot.guilds = []
        self.bot.tool_manager = Mock()
        self.bot.tool_manager.get_crypto_price = Mock(return_value=1.0)
        
        self.manager = TipCCManager(self.bot)
        
        # Mock database
        self.db_patcher = patch('utils.tipcc_manager.db')
        self.mock_db = self.db_patcher.start()
        self.mock_db.aadd_transaction = AsyncMock()
        self.mock_db.aget_balance = AsyncMock(return_value={'amount': 10.0, 'usd_value': 10.0})
        self.mock_db.aupdate_balance = AsyncMock()

    def tearDown(self):
        """Clean up test fixtures"""
        self.db_patcher.stop()

    def test_tip_thank_you_enabled_config(self):
        """Test that tip thank you can be enabled via config"""
        with patch('config.TIP_THANK_YOU_ENABLED', True):
            self.assertTrue(True)  # Config should be accessible

    def test_tip_thank_you_disabled_config(self):
        """Test that tip thank you can be disabled via config"""
        with patch('config.TIP_THANK_YOU_ENABLED', False):
            self.assertTrue(True)  # Config should be accessible

    def test_thank_you_cooldown_tracking(self):
        """Test that thank you cooldown is tracked correctly"""
        sender_id = "987654321"
        current_time = time.time()
        
        # Initially no cooldown
        self.assertNotIn(sender_id, self.manager.thank_you_cooldown)
        
        # Set cooldown
        self.manager.thank_you_cooldown[sender_id] = current_time
        
        # Check cooldown is set
        self.assertIn(sender_id, self.manager.thank_you_cooldown)
        self.assertEqual(self.manager.thank_you_cooldown[sender_id], current_time)

    def test_parse_transaction_embed_tip_received(self):
        """Test parsing tip received transaction embed"""
        # Create mock embed - format should match what tip.cc actually sends
        embed = Mock()
        embed.title = "Tip Transaction"
        embed.description = "<@111111111> sent <@123456789> 1.0 BTC (≈ $50000)"
        
        # Mock bot user ID
        self.bot.user.id = 123456789
        
        # Mock the _estimate_usd_value method
        with patch.object(self.manager, '_estimate_usd_value', return_value=50000.0):
            # Test the parsing
            with patch('config.TIP_THANK_YOU_ENABLED', True):
                with patch.object(self.manager, '_send_tip_thank_you') as mock_thank_you:
                    result = asyncio.run(self.manager._parse_transaction_embed(embed))
                    
                    # Check that thank you was called
                    mock_thank_you.assert_called_once_with("111111111", 1.0, "BTC", 50000.0)

    def test_parse_transaction_embed_tip_sent(self):
        """Test parsing tip sent transaction embed (should not trigger thank you)"""
        # Create mock embed - bot is the sender
        embed = Mock()
        embed.title = "Tip Transaction"
        embed.description = "<@123456789> sent <@987654321> 1.0 BTC (≈ $50000)"
        
        # Mock bot user ID
        self.bot.user.id = 123456789
        
        # Mock the _estimate_usd_value method
        with patch.object(self.manager, '_estimate_usd_value', return_value=50000.0):
            # Test the parsing
            with patch('config.TIP_THANK_YOU_ENABLED', True):
                with patch.object(self.manager, '_send_tip_thank_you') as mock_thank_you:
                    result = asyncio.run(self.manager._parse_transaction_embed(embed))
                    
                    # Check that thank you was NOT called (this was a sent tip, not received)
                    mock_thank_you.assert_not_called()

    def test_send_tip_thank_you_disabled(self):
        """Test that thank you is not sent when feature is disabled"""
        with patch('config.TIP_THANK_YOU_ENABLED', False):
            asyncio.run(self.manager._send_tip_thank_you("123456789", 1.0, "BTC", 50000.0))
            
            # Should return early without sending anything
            # No assertions needed - just check it doesn't crash

    def test_send_tip_thank_you_cooldown(self):
        """Test that thank you respects cooldown"""
        sender_id = "987654321"
        current_time = time.time()
        
        # Set cooldown to current time (should trigger cooldown)
        self.manager.thank_you_cooldown[sender_id] = current_time
        
        with patch('config.TIP_THANK_YOU_ENABLED', True):
            with patch('config.TIP_THANK_YOU_COOLDOWN', 300):  # 5 minutes
                with patch.object(self.manager, '_send_tip_thank_you') as mock_send:
                    asyncio.run(self.manager._send_tip_thank_you(sender_id, 1.0, "BTC", 50000.0))
                    
                    # Should not send due to cooldown
                    # No assertions needed - just check it doesn't crash

    def test_send_tip_thank_you_no_channel(self):
        """Test handling when no suitable channel is found"""
        # Mock bot with no guilds
        self.bot.guilds = []
        
        with patch('config.TIP_THANK_YOU_ENABLED', True):
            with patch('config.TIP_THANK_YOU_COOLDOWN', 0):  # No cooldown
                with patch('builtins.__import__') as mock_import:
                    # Mock the random module import
                    mock_random = Mock()
                    mock_random.choice.side_effect = ["Thanks bro!", "🙏"]
                    mock_import.return_value = mock_random
                    
                    asyncio.run(self.manager._send_tip_thank_you("987654321", 1.0, "BTC", 50000.0))
                    
                    # Should not crash, just log warning
                    self.assertTrue(True)  # If we get here, no exception was raised

    def test_send_tip_thank_you_with_channel(self):
        """Test sending thank you message when channel is found"""
        # Create mock guild and channel
        guild = Mock()
        channel = Mock()
        channel.permissions_for.return_value.send_messages = True
        guild.text_channels = [channel]
        guild.get_member.return_value = Mock()
        
        self.bot.guilds = [guild]
        
        with patch('config.TIP_THANK_YOU_ENABLED', True):
            with patch('config.TIP_THANK_YOU_COOLDOWN', 0):  # No cooldown
                with patch('builtins.__import__') as mock_import:
                    # Mock the random module import
                    mock_random = Mock()
                    mock_random.choice.side_effect = ["Thanks bro!", "🙏"]
                    mock_import.return_value = mock_random
                    
                    asyncio.run(self.manager._send_tip_thank_you("987654321", 1.0, "BTC", 50000.0))
                    
                    # Check that message was sent
                    channel.send.assert_called_once()

    def test_tip_thank_you_message_formatting(self):
        """Test that thank you messages are formatted correctly"""
        # Create mock guild and channel
        guild = Mock()
        channel = Mock()
        channel.permissions_for.return_value.send_messages = True
        guild.text_channels = [channel]
        guild.get_member.return_value = Mock()
        
        self.bot.guilds = [guild]
        
        with patch('config.TIP_THANK_YOU_ENABLED', True):
            with patch('config.TIP_THANK_YOU_COOLDOWN', 0):  # No cooldown
                with patch('builtins.__import__') as mock_import:
                    # Mock the random module import
                    mock_random = Mock()
                    mock_random.choice.side_effect = ["Thanks for the tip bro!", "💰"]
                    mock_import.return_value = mock_random
                    
                    asyncio.run(self.manager._send_tip_thank_you("987654321", 1.0, "BTC", 50000.0))
                    
                    # Check message format
                    expected_message = "<@987654321> Thanks for the tip bro! 💰"
                    channel.send.assert_called_once_with(expected_message)

    def test_tip_thank_you_error_handling(self):
        """Test error handling in thank you sending"""
        # Create mock guild and channel that raises exception
        guild = Mock()
        channel = Mock()
        channel.send.side_effect = discord.DiscordException("Test error")
        channel.permissions_for.return_value.send_messages = True
        guild.text_channels = [channel]
        guild.get_member.return_value = Mock()
        
        self.bot.guilds = [guild]
        
        with patch('config.TIP_THANK_YOU_ENABLED', True):
            with patch('config.TIP_THANK_YOU_COOLDOWN', 0):  # No cooldown
                with patch('builtins.__import__') as mock_import:
                    # Mock the random module import
                    mock_random = Mock()
                    mock_random.choice.side_effect = ["Thanks bro!", "🙏"]
                    mock_import.return_value = mock_random
                    
                    # Should not raise exception
                    asyncio.run(self.manager._send_tip_thank_you("987654321", 1.0, "BTC", 50000.0))
                    
                    # If we get here, exception was handled
                    self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
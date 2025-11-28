#!/usr/bin/env python3
"""
Tests for the tip.cc manager functionality
"""

import unittest
import asyncio
import sys
import os

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.tipcc_manager import TipCCManager
from data.database import db
import json

class MockBot:
    """Mock bot instance for testing"""
    def __init__(self):
        self.tool_manager = MockToolManager()

class MockToolManager:
    """Mock tool manager for testing"""
    def get_crypto_price(self, currency):
        # Return mock prices
        prices = {
            'BTC': 45000.0,
            'ETH': 2500.0,
            'SOL': 100.0,
            'DOGE': 0.15
        }
        return prices.get(currency, 1.0)

class MockMessage:
    """Mock Discord message for testing"""
    def __init__(self, content="", author_id=None, embeds=None):
        self.content = content
        self.author_id = author_id
        self.embeds = embeds or []

class MockEmbedField:
    """Mock Discord embed field for testing"""
    def __init__(self, name="", value=""):
        self.name = name
        self.value = value

class MockEmbed:
    """Mock Discord embed for testing"""
    def __init__(self, title="", description="", fields=None):
        self.title = title
        self.description = description
        self.fields = fields or []

class TestTipCCManager(unittest.TestCase):
    """Test cases for TipCCManager"""

    def setUp(self):
        """Set up test environment"""
        self.bot = MockBot()
        self.manager = TipCCManager(self.bot)
        
        # Clean up database for testing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._cleanup_test_data())
        loop.close()
    
    async def _cleanup_test_data(self):
        """Clean up test data from database"""
        import sqlite3
        conn = sqlite3.connect('data/jakey.db')
        cursor = conn.cursor()
        
        # Clear tipcc_transactions table
        cursor.execute("DELETE FROM tipcc_transactions")
        
        # Clear tipcc_balances table  
        cursor.execute("DELETE FROM tipcc_balances")
        
        conn.commit()
        conn.close()

    def test_tip_cc_manager_initialization(self):
        """Test that TipCCManager initializes correctly"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(self.manager.tip_cc_bot_id, 617037497574359050)
        self.assertEqual(self.manager.balance_update_interval, 300)

    def test_parse_balance_embed(self):
        """Test parsing balance embeds"""
        # Create a mock balance embed with the actual format from tip.cc
        embed = MockEmbed(
            title="Your balances",
            description="**Bitcoin:** <:BTC:903867169568325642> 0.001234 BTC (≈ $55.56)\n**Ethereum:** <:ETH:903867169568325643> 0.1 ETH (≈ $250.00)\n**Dogecoin:** <:DOGE:903867169568325644> 1000 DOGE (≈ $150.00)"
        )

        # Test parsing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.manager._parse_balance_embed(embed))
        loop.close()

        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'balance_update')
        self.assertEqual(len(result['balances']), 3)

        # Check specific balances
        btc_balance = next((b for b in result['balances'] if b['currency'] == 'BTC'), None)
        self.assertIsNotNone(btc_balance)
        self.assertAlmostEqual(btc_balance['amount'], 0.001234)
        self.assertAlmostEqual(btc_balance['usd_value'], 55.56)
        
        eth_balance = next((b for b in result['balances'] if b['currency'] == 'ETHEREUM'), None)
        self.assertIsNotNone(eth_balance)
        self.assertAlmostEqual(eth_balance['amount'], 0.1)
        self.assertAlmostEqual(eth_balance['usd_value'], 250.0)

    def test_parse_transaction_message_airdrop(self):
        """Test parsing airdrop transaction messages"""
        message = MockMessage(
            content="You received 0.1 SOL from the airdrop!",
            author_id=617037497574359050  # tip.cc bot ID
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.manager._parse_transaction_message(message))
        loop.close()

        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'airdrop_result')
        self.assertEqual(result['currency'], 'SOL')
        self.assertAlmostEqual(result['amount'], 0.1)

    def test_estimate_usd_value(self):
        """Test USD value estimation"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Test BTC
        usd_value = loop.run_until_complete(self.manager._estimate_usd_value("0.001", "BTC"))
        self.assertAlmostEqual(usd_value, 45.0)

        # Test USD (should return same amount)
        usd_value = loop.run_until_complete(self.manager._estimate_usd_value("10.0", "USD"))
        self.assertAlmostEqual(usd_value, 10.0)

        loop.close()

    def test_transaction_emoji_mapping(self):
        """Test transaction emoji mapping"""
        self.assertEqual(self.manager._get_transaction_emoji('airdrop'), '🎁')
        self.assertEqual(self.manager._get_transaction_emoji('tip_sent'), '📤')
        self.assertEqual(self.manager._get_transaction_emoji('tip_received'), '📥')
        self.assertEqual(self.manager._get_transaction_emoji('unknown'), '💱')

    def test_database_integration(self):
        """Test database integration for balance tracking"""
        # Test adding a balance
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Add a test balance
        loop.run_until_complete(db.aupdate_balance('TEST', 100.0, 50.0))

        # Retrieve the balance
        balance = loop.run_until_complete(db.aget_balance('TEST'))
        self.assertIsNotNone(balance)
        self.assertEqual(balance['currency'], 'TEST')
        self.assertAlmostEqual(balance['amount'], 100.0)
        self.assertAlmostEqual(balance['usd_value'], 50.0)

        # Test transaction recording
        loop.run_until_complete(db.aadd_transaction('tip_sent', 'TEST', 10.0, 5.0, '123456789', 'Test tip', '987654321'))

        # Get transaction stats
        stats = loop.run_until_complete(db.aget_transaction_stats())
        self.assertIn('total_sent_usd', stats)
        self.assertEqual(stats['total_sent_usd'], 5.0)

        loop.close()

    def test_get_formatted_balances(self):
        """Test formatted balance output"""
        # Add some test balances
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(db.aupdate_balance('BTC', 0.001, 45.0))
        loop.run_until_complete(db.aupdate_balance('ETH', 0.1, 250.0))

        # Get formatted balances
        balances = loop.run_until_complete(self.manager.get_formatted_balances())
        self.assertIn('Jakey\'s tip.cc Balances', balances)
        self.assertIn('BTC', balances)
        self.assertIn('ETH', balances)

        loop.close()

if __name__ == '__main__':
    unittest.main()
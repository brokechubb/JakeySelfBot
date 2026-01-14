#!/usr/bin/env python3
"""
Tests for configuration loading
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestConfig(unittest.TestCase):
    """Test cases for configuration loading"""

    @unittest.skip("Pollinations API has been removed - test needs update for OpenRouter")
    def test_config_import(self):
        """Test that config can be imported without errors"""
        try:
            from config import (
                DISCORD_TOKEN,
                DEFAULT_MODEL,
                OPENROUTER_API_KEY,
                OPENROUTER_API_URL,
                COINMARKETCAP_API_KEY,
                SEARXNG_URL,
                DATABASE_PATH,
                SYSTEM_PROMPT
            )
            config_imported = True
        except Exception as e:
            config_imported = False
        
        self.assertTrue(config_imported, "Config should import without errors")
    
    def test_config_values(self):
        """Test that config values have expected types"""
        from config import (
            DISCORD_TOKEN,
            DEFAULT_MODEL,
            OPENROUTER_API_URL,
            DATABASE_PATH,
            SYSTEM_PROMPT
        )
        
        if DISCORD_TOKEN is not None:
            self.assertIsInstance(DISCORD_TOKEN, str)
        
        self.assertIsInstance(DEFAULT_MODEL, str)
        self.assertIsInstance(OPENROUTER_API_URL, str)
        self.assertIsInstance(DATABASE_PATH, str)
        self.assertIsInstance(SYSTEM_PROMPT, str)
        
        self.assertTrue(OPENROUTER_API_URL.startswith("http"))
        self.assertTrue(DATABASE_PATH.endswith(".db"))
    
    def test_system_prompt_content(self):
        """Test that system prompt contains expected content"""
        from config import SYSTEM_PROMPT
        
        self.assertIn("Jakey", SYSTEM_PROMPT)
        self.assertIn("gambling", SYSTEM_PROMPT)
        self.assertIn(" degenerate", SYSTEM_PROMPT.lower())
        self.assertIn("web_search", SYSTEM_PROMPT)
        self.assertIn("remember_user_info", SYSTEM_PROMPT)
        self.assertIn("search_user_memory", SYSTEM_PROMPT)


if __name__ == '__main__':
    unittest.main()

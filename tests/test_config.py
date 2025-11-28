#!/usr/bin/env python3
"""
Tests for configuration loading
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestConfig(unittest.TestCase):
    """Test cases for configuration loading"""
    
    def test_config_import(self):
        """Test that config can be imported without errors"""
        try:
            from config import (
                DISCORD_TOKEN,
                DEFAULT_MODEL,
                POLLINATIONS_API_TOKEN,
                POLLINATIONS_TEXT_API,
                POLLINATIONS_IMAGE_API,
                COINMARKETCAP_API_KEY,
                SEARXNG_URL,
                DATABASE_PATH,
                SYSTEM_PROMPT
            )
            # Config imported successfully
            config_imported = True
        except Exception as e:
            config_imported = False
        
        self.assertTrue(config_imported, "Config should import without errors")
    
    def test_config_values(self):
        """Test that config values have expected types"""
        from config import (
            DISCORD_TOKEN,
            DEFAULT_MODEL,
            POLLINATIONS_TEXT_API,
            POLLINATIONS_IMAGE_API,
            DATABASE_PATH,
            SYSTEM_PROMPT
        )
        
        # Test that required config values are strings
        if DISCORD_TOKEN is not None:
            self.assertIsInstance(DISCORD_TOKEN, str)
        
        self.assertIsInstance(DEFAULT_MODEL, str)
        self.assertIsInstance(POLLINATIONS_TEXT_API, str)
        self.assertIsInstance(POLLINATIONS_IMAGE_API, str)
        self.assertIsInstance(DATABASE_PATH, str)
        self.assertIsInstance(SYSTEM_PROMPT, str)
        
        # Test that API URLs are valid URLs
        self.assertTrue(POLLINATIONS_TEXT_API.startswith("http"))
        self.assertTrue(POLLINATIONS_IMAGE_API.startswith("http"))
    
    def test_system_prompt_content(self):
        """Test that system prompt contains expected content"""
        from config import SYSTEM_PROMPT
        
        # Check that system prompt contains key elements
        self.assertIn("Jakey", SYSTEM_PROMPT)
        self.assertIn("gambling", SYSTEM_PROMPT)
        self.assertIn(" degenerate", SYSTEM_PROMPT.lower())
        self.assertIn("web_search", SYSTEM_PROMPT)
        self.assertIn("remember_user_info**: Store user preferences", SYSTEM_PROMPT)

if __name__ == '__main__':
    unittest.main()
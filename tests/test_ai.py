#!/usr/bin/env python3
"""
Tests for AI integration functionality

NOTE: Pollinations API has been deprecated and removed.
These tests are skipped but kept for reference.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Try to import Pollinations, skip if not available (deprecated)
try:
    from ai.pollinations import PollinationsAPI
    POLLINATIONS_AVAILABLE = True
except ImportError:
    POLLINATIONS_AVAILABLE = False
    PollinationsAPI = None


@unittest.skipUnless(POLLINATIONS_AVAILABLE, "Pollinations API has been deprecated and removed")
class TestPollinationsAPI(unittest.TestCase):
    """Test cases for the PollinationsAPI class (DEPRECATED)"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.api = PollinationsAPI()
    
    def test_init(self):
        """Test that the API is initialized correctly"""
        self.assertIsNotNone(self.api.text_api_url)
        self.assertIsNotNone(self.api.image_api_url)
        # Check that default_model is set to whatever is configured (could be custom)
        self.assertIsNotNone(self.api.default_model)
        # Ensure it's a non-empty string
        self.assertIsInstance(self.api.default_model, str)
        self.assertGreater(len(self.api.default_model), 0)
    
    def test_generate_text_defaults(self):
        """Test generate_text with default parameters"""
        # This would normally make an API call, but we'll test the structure
        messages = [{"role": "user", "content": "Hello"}]
        
        # We won't actually call the API in tests, but we can test the method structure
        self.assertTrue(callable(self.api.generate_text))
    
    def test_generate_image(self):
        """Test generate_image method"""
        prompt = "a test image"
        url = self.api.generate_image(prompt)
        
        # Check that URL is generated correctly
        self.assertIn("prompt/", url)
        self.assertIn(prompt.replace(" ", "%20"), url)
    
    def test_list_text_models(self):
        """Test list_text_models method"""
        # This would normally make an API call
        self.assertTrue(callable(self.api.list_text_models))
    
    def test_list_image_models(self):
        """Test list_image_models method"""
        # This would normally make an API call
        self.assertTrue(callable(self.api.list_image_models))


class TestOpenRouterAPI(unittest.TestCase):
    """Test cases for the OpenRouterAPI class (current primary provider)"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        from ai.openrouter import OpenRouterAPI
        self.api = OpenRouterAPI()
    
    def test_init(self):
        """Test that the API is initialized correctly"""
        self.assertIsNotNone(self.api.api_url)
        self.assertIsNotNone(self.api.default_model)
        self.assertIsInstance(self.api.default_model, str)
        self.assertGreater(len(self.api.default_model), 0)
    
    def test_generate_text_callable(self):
        """Test generate_text method exists and is callable"""
        self.assertTrue(callable(self.api.generate_text))
    
    def test_list_models_callable(self):
        """Test list_models method exists and is callable"""
        self.assertTrue(callable(self.api.list_models))
    
    def test_check_service_health_callable(self):
        """Test check_service_health method exists and is callable"""
        self.assertTrue(callable(self.api.check_service_health))


if __name__ == '__main__':
    unittest.main()

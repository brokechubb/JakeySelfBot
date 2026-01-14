"""Test backward compatibility of AI implementations

NOTE: Pollinations API has been deprecated and removed.
This module now tests OpenRouter API compatibility instead.
"""
import sys
import os
import unittest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import Pollinations, skip if not available (deprecated)
try:
    from ai.pollinations import pollinations_api
    POLLINATIONS_AVAILABLE = True
except ImportError:
    POLLINATIONS_AVAILABLE = False
    pollinations_api = None

from ai.openrouter import openrouter_api


@unittest.skipUnless(POLLINATIONS_AVAILABLE, "Pollinations API has been deprecated and removed")
class TestPollinationsBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility of Pollinations API (DEPRECATED)"""
    
    def test_basic_text_generation(self):
        """Test basic text generation (backward compatibility)"""
        messages = [{"role": "user", "content": "What is 2+2?"}]
        response = pollinations_api.generate_text(messages=messages)
        self.assertIsInstance(response, dict)
    
    def test_basic_image_generation(self):
        """Test basic image generation (backward compatibility)"""
        url = pollinations_api.generate_image("A cat")
        self.assertIsNotNone(url)
        self.assertIsInstance(url, str)
    
    def test_model_listing(self):
        """Test model listing (backward compatibility)"""
        text_models = pollinations_api.list_text_models()
        image_models = pollinations_api.list_image_models()
        self.assertIsInstance(text_models, list)
        self.assertIsInstance(image_models, list)


class TestOpenRouterBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility of OpenRouter API (current primary provider)"""
    
    def test_api_initialization(self):
        """Test that OpenRouter API initializes correctly"""
        self.assertIsNotNone(openrouter_api)
        self.assertIsNotNone(openrouter_api.api_url)
        self.assertIsNotNone(openrouter_api.default_model)
    
    def test_generate_text_interface(self):
        """Test that generate_text has the expected interface"""
        self.assertTrue(callable(openrouter_api.generate_text))
        # Check it accepts the expected parameters
        import inspect
        sig = inspect.signature(openrouter_api.generate_text)
        param_names = list(sig.parameters.keys())
        self.assertIn('messages', param_names)
        self.assertIn('model', param_names)
        self.assertIn('temperature', param_names)
        self.assertIn('max_tokens', param_names)
    
    def test_list_models_interface(self):
        """Test that list_models has the expected interface"""
        self.assertTrue(callable(openrouter_api.list_models))
    
    def test_check_service_health_interface(self):
        """Test that check_service_health has the expected interface"""
        self.assertTrue(callable(openrouter_api.check_service_health))


def main():
    """Run backward compatibility tests"""
    print("Running backward compatibility tests...")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPollinationsBackwardCompatibility))
    suite.addTests(loader.loadTestsFromTestCase(TestOpenRouterBackwardCompatibility))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

"""Test async AI implementations

NOTE: Pollinations API has been deprecated and removed.
These tests are skipped but kept for reference.
The async AI functionality is now handled by ai_provider_manager.
"""
import asyncio
import sys
import os
import unittest
from unittest.mock import Mock, AsyncMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import async Pollinations, skip if not available (deprecated)
try:
    from ai.async_pollinations import pollinations_async_api
    ASYNC_POLLINATIONS_AVAILABLE = True
except ImportError:
    ASYNC_POLLINATIONS_AVAILABLE = False
    pollinations_async_api = None


@unittest.skipUnless(ASYNC_POLLINATIONS_AVAILABLE, "Async Pollinations API has been deprecated and removed")
class TestAsyncPollinations(unittest.TestCase):
    """Test cases for async pollinations functionality (DEPRECATED)"""

    def test_async_text_generation(self):
        """Test async text generation"""
        print("Testing async text generation...")
        
        messages = [
            {"role": "user", "content": "What is artificial intelligence?"}
        ]
        
        # Mock the API call to avoid actual network requests
        with patch.object(pollinations_async_api, 'generate_text', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = {
                'choices': [{
                    'message': {
                        'content': 'Artificial intelligence is a field of computer science focused on creating systems that can perform tasks requiring human intelligence.'
                    }
                }]
            }
            
            # Run the async test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(pollinations_async_api.generate_text(messages=messages, model="openai"))
            loop.close()
            
            print(f"Response: {response}")
            
            # Verify the mock was called correctly
            mock_generate.assert_called_once_with(messages=messages, model="openai")
            
            # Verify response structure
            self.assertIn('choices', response)
            self.assertGreater(len(response['choices']), 0)
            self.assertIn('message', response['choices'][0])
            self.assertIn('content', response['choices'][0]['message'])
            
            content = response['choices'][0]['message']['content']
            print(f"Success: Generated text with {len(content)} characters")
            self.assertGreater(len(content), 0)

    def test_async_text_generation_error(self):
        """Test async text generation error handling"""
        print("Testing async text generation error handling...")
        
        messages = [
            {"role": "user", "content": "What is artificial intelligence?"}
        ]
        
        # Mock the API call to return an error
        with patch.object(pollinations_async_api, 'generate_text', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = {'error': 'API Error'}
            
            # Run the async test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(pollinations_async_api.generate_text(messages=messages, model="openai"))
            loop.close()
            
            print(f"Response: {response}")
            
            # Verify error handling
            self.assertIn('error', response)
            self.assertEqual(response['error'], 'API Error')

    def test_async_image_generation(self):
        """Test async image generation"""
        print("Testing async image generation...")
        
        # Mock the API call to avoid actual network requests
        with patch.object(pollinations_async_api, 'generate_image', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "https://image.pollinations.ai/prompt/test"
            
            # Run the async test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            url = loop.run_until_complete(pollinations_async_api.generate_image("A beautiful sunset", model="flux"))
            loop.close()
            
            print(f"Image URL: {url}")
            
            # Verify the mock was called correctly
            mock_generate.assert_called_once_with("A beautiful sunset", model="flux")
            
            # Verify URL structure
            self.assertIsNotNone(url)
            self.assertTrue(url.startswith("https://image.pollinations.ai"))
            print("Success: Generated image URL")

    def test_async_image_generation_error(self):
        """Test async image generation error handling"""
        print("Testing async image generation error handling...")
        
        # Mock the API call to return None (error case)
        with patch.object(pollinations_async_api, 'generate_image', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = None
            
            # Run the async test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            url = loop.run_until_complete(pollinations_async_api.generate_image("A beautiful sunset", model="flux"))
            loop.close()
            
            print(f"Image URL: {url}")
            
            # Verify error handling
            self.assertIsNone(url)


class TestAIProviderManager(unittest.TestCase):
    """Test cases for the AI Provider Manager (current async implementation)"""
    
    def test_provider_manager_import(self):
        """Test that AI provider manager can be imported"""
        from ai.ai_provider_manager import ai_provider_manager
        self.assertIsNotNone(ai_provider_manager)
    
    def test_generate_text_is_async(self):
        """Test that generate_text is an async method"""
        from ai.ai_provider_manager import ai_provider_manager
        import inspect
        self.assertTrue(inspect.iscoroutinefunction(ai_provider_manager.generate_text))
    
    def test_generate_image_is_async(self):
        """Test that generate_image is an async method"""
        from ai.ai_provider_manager import ai_provider_manager
        import inspect
        self.assertTrue(inspect.iscoroutinefunction(ai_provider_manager.generate_image))


if __name__ == "__main__":
    unittest.main()

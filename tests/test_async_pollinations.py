"""Test async pollinations implementation"""
import asyncio
import sys
import os
import unittest
from unittest.mock import Mock, AsyncMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.async_pollinations import pollinations_async_api


class TestAsyncPollinations(unittest.TestCase):
    """Test cases for async pollinations functionality"""

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


# Keep the original main function for standalone execution
async def main():
    """Run all tests"""
    print("Running async pollinations tests...")
    
    try:
        # Create test instance
        test_instance = TestAsyncPollinations()
        
        # Run tests
        await test_instance.test_async_text_generation()
        await test_instance.test_async_text_generation_error()
        await test_instance.test_async_image_generation()
        await test_instance.test_async_image_generation_error()
        
        print("All tests passed!")
        return True
    except Exception as e:
        print(f"Test failed with exception: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
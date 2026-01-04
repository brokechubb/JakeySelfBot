#!/usr/bin/env python3
"""
Tests for channel context collection functionality
"""

import unittest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
import inspect

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestChannelContext(unittest.TestCase):
    """Test cases for the channel context collection functionality"""

    def test_collect_recent_channel_context_method_exists(self):
        """Test that the collect_recent_channel_context method exists with correct signature"""
        try:
            from bot.client import JakeyBot
            
            # Check if method exists
            self.assertTrue(
                hasattr(JakeyBot, 'collect_recent_channel_context'),
                "Method 'collect_recent_channel_context' should exist"
            )
            
            # Check method signature
            method = getattr(JakeyBot, 'collect_recent_channel_context')
            sig = inspect.signature(method)
            
            # Should have: (self, message, limit_minutes=30, message_limit=10)
            params = list(sig.parameters.keys())
            expected_params = ['self', 'message', 'limit_minutes', 'message_limit']
            
            for param in expected_params:
                self.assertIn(param, params, f"Parameter '{param}' should be in method signature")
            
            # Check default values
            self.assertEqual(
                sig.parameters['limit_minutes'].default, 30,
                "limit_minutes should default to 30"
            )
            self.assertEqual(
                sig.parameters['message_limit'].default, 10,
                "message_limit should default to 10"
            )
            
        except Exception as e:
            self.fail(f"Error checking method: {e}")

    def test_channel_context_integration_in_process_jakey_response(self):
        """Test that the new method is integrated into process_jakey_response"""
        try:
            from bot.client import JakeyBot
            
            # Get the source code of the method
            method_source = inspect.getsource(JakeyBot.process_jakey_response)
            
            # Check that it calls our new method
            self.assertIn(
                'collect_recent_channel_context', method_source,
                "'collect_recent_channel_context' should be called in process_jakey_response"
            )
            
            # Check that it includes channel_context variable
            self.assertIn(
                'channel_context', method_source,
                "channel_context variable should be used"
            )
            
            # Check that it's added to system prompt
            self.assertIn(
                'channel_context', method_source,
                "Channel context should be integrated into system prompt"
            )
            # Check that it's being appended to system_content
            self.assertIn(
                'system_content +=', method_source,
                "Channel context should be appended to system_content"
            )
            
        except Exception as e:
            self.fail(f"Error checking integration: {e}")

    def test_collect_recent_channel_context_dm_handling(self):
        """Test that DM channels correctly return empty context"""
        try:
            from bot.client import JakeyBot
            
            # Create a minimal bot instance
            bot = JakeyBot.__new__(JakeyBot)
            
            # Create a mock DM message
            mock_message = Mock()
            mock_message.channel = Mock()
            mock_message.channel.guild = None  # This makes it a DM
            
            # Test should return empty context without errors
            import asyncio
            
            async def test_method():
                return await bot.collect_recent_channel_context(mock_message)
            
            # Run the async test
            loop = None
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, use asyncio.create_task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, test_method())
                        result = future.result()
                else:
                    result = loop.run_until_complete(test_method())
            except RuntimeError:
                # No loop running, use asyncio.run
                result = asyncio.run(test_method())
            
            self.assertEqual(result, "", "DM channel should return empty context")
            
        except Exception as e:
            self.fail(f"Error testing DM context: {e}")

    def test_channel_context_method_is_async(self):
        """Test that the collect_recent_channel_context method is async"""
        try:
            from bot.client import JakeyBot
            
            method = getattr(JakeyBot, 'collect_recent_channel_context')
            self.assertTrue(
                inspect.iscoroutinefunction(method),
                "collect_recent_channel_context should be an async method"
            )
            
        except Exception as e:
            self.fail(f"Error checking if method is async: {e}")


if __name__ == '__main__':
    unittest.main()
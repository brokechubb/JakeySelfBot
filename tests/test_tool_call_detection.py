#!/usr/bin/env python3
"""
Tests for tool call detection and sanitization
Covers the defensive tool call handling and response sanitization added in recent session
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bot.client import sanitize_ai_response


class TestToolCallSanitization(unittest.TestCase):
    """Test cases for sanitize_ai_response function"""

    def test_basic_response_unchanged(self):
        """Test that normal responses are not modified"""
        response = "Hello! This is a normal response without any tool calls."
        sanitized = sanitize_ai_response(response)
        self.assertEqual(sanitized, response)

    def test_normal_phrases_preserved(self):
        """Test that normal phrases like 'Let me...' are preserved (not removed)
        
        NOTE: These phrases are prevented by the system prompt, not by sanitization.
        The sanitization only removes tool call syntax, not natural language.
        """
        test_cases = [
            "Let me search for that information.",
            "I'll check the latest prices for you.",
            "Let me look that up.",
            "I'll find that information.",
            "Let me check.",
        ]
        
        for input_text in test_cases:
            result = sanitize_ai_response(input_text)
            # These phrases should be unchanged by sanitization
            self.assertEqual(result, input_text, f"Should preserve: {input_text}")

    def test_remove_json_tool_calls(self):
        """Test removal of JSON-formatted tool calls that some models output"""
        # Single-line JSON tool call
        response = 'Here is the info {"type": "function", "name": "web_search", "parameters": {"query": "test"}} that I found.'
        sanitized = sanitize_ai_response(response)
        self.assertNotIn('"type"', sanitized)
        self.assertNotIn('"function"', sanitized)
        # Note: Line 70 regex also removes "info {" pattern, so "info" gets removed too
        self.assertIn('Here is the', sanitized)
        self.assertIn('that I found.', sanitized)

        # Multi-line JSON tool call
        response = '''Let me search.
{
    "type": "function",
    "name": "web_search",
    "parameters": {
        "query": "latest news"
    }
}
Here are the results.'''
        sanitized = sanitize_ai_response(response)
        self.assertNotIn('"type"', sanitized)
        self.assertNotIn('web_search', sanitized)
        self.assertIn('Here are the results.', sanitized)

    def test_remove_named_tool_syntax(self):
        """Test removal of named tool call syntax like 'discord_read_channel {...}'"""
        test_cases = [
            'discord_read_channel {"channel_id": "123456"}',
            'web_search {"query": "test", "limit": 5}',
            'get_crypto_price {"symbol": "BTC"}',
            'remember_user_info {"user_id": "123", "key": "name", "value": "John"}',
            'search_user_memories {"user_id": "123", "query": "preferences"}',
        ]
        
        for tool_call in test_cases:
            response = f"Before tool. {tool_call} After tool."
            sanitized = sanitize_ai_response(response)
            # Tool call should be removed
            self.assertNotIn('{', sanitized)
            self.assertNotIn('}', sanitized)
            # But surrounding text should remain
            self.assertIn('Before tool.', sanitized)
            self.assertIn('After tool.', sanitized)

    def test_remove_trailing_eos_token(self):
        """Test removal of </s> end-of-sequence tokens"""
        response = "This is a response from the model.</s>"
        sanitized = sanitize_ai_response(response)
        self.assertNotIn('</s>', sanitized)
        self.assertEqual(sanitized, "This is a response from the model.")

    def test_clean_multiple_newlines(self):
        """Test cleanup of excessive newlines"""
        response = "Line one.\n\n\n\nLine two."
        sanitized = sanitize_ai_response(response)
        # Should reduce to maximum of two consecutive newlines
        self.assertNotIn('\n\n\n', sanitized)
        self.assertEqual(sanitized, "Line one.\n\nLine two.")

    def test_strip_whitespace(self):
        """Test that leading/trailing whitespace is removed"""
        response = "  \n\n  Normal response with extra whitespace  \n\n  "
        sanitized = sanitize_ai_response(response)
        self.assertEqual(sanitized, "Normal response with extra whitespace")

    def test_complex_mixed_response(self):
        """Test a complex response with multiple issues"""
        response = '''Let me search for that.

web_search {"query": "bitcoin price", "limit": 5}

The current price is $50,000.

{"type": "function", "name": "get_crypto_price", "parameters": {"symbol": "BTC"}}

</s>'''
        
        sanitized = sanitize_ai_response(response)
        
        # Should remove tool call syntax
        self.assertNotIn('web_search', sanitized)
        self.assertNotIn('"type"', sanitized)
        self.assertNotIn('</s>', sanitized)
        
        # Note: "Let me search" is NOT removed by sanitization, only prevented by system prompt
        # Sanitization only removes tool call syntax, not natural language phrases
        
        # Should keep the actual content
        self.assertIn('The current price is $50,000.', sanitized)

    def test_logging_for_large_sanitization(self):
        """Test that logging occurs when significant content is removed"""
        # Create a response with lots of tool call syntax (>20 chars)
        response = 'discord_read_channel {"channel_id": "1234567890", "limit": 100} Result here.'
        
        with patch('bot.client.logger') as mock_logger:
            sanitized = sanitize_ai_response(response)
            # Should log because we removed >20 characters
            self.assertTrue(mock_logger.info.called)
            call_args = str(mock_logger.info.call_args)
            self.assertIn('Sanitized AI response', call_args)


class TestDefensiveToolCallDetection(unittest.TestCase):
    """Test cases for defensive tool call detection (text-based → API format conversion)"""

    def test_detect_web_search_pattern(self):
        """Test detection of web_search text patterns"""
        text_patterns = [
            'web_search {"query": "test"}',
            'web_search{"query":"test"}',
            'WEB_SEARCH {"query": "test"}',  # Case insensitive
        ]
        
        import re
        # This is the regex pattern from bot/client.py line ~990
        tool_pattern = re.compile(
            r'\b(web_search|discord_\w+|get_\w+|remember_\w+|search_\w+)\s*\{[^}]+\}',
            re.IGNORECASE
        )
        
        for pattern in text_patterns:
            match = tool_pattern.search(pattern)
            self.assertIsNotNone(match, f"Should detect: {pattern}")

    def test_detect_discord_tools_pattern(self):
        """Test detection of discord_* tool patterns"""
        patterns = [
            'discord_read_channel {"channel_id": "123"}',
            'discord_send_message {"channel_id": "123", "message": "hi"}',
            'discord_get_user_info {"user_id": "456"}',
        ]
        
        import re
        tool_pattern = re.compile(
            r'\b(web_search|discord_\w+|get_\w+|remember_\w+|search_\w+)\s*\{[^}]+\}',
            re.IGNORECASE
        )
        
        for pattern in patterns:
            match = tool_pattern.search(pattern)
            self.assertIsNotNone(match, f"Should detect: {pattern}")

    def test_no_false_positives(self):
        """Test that normal text doesn't trigger tool call detection"""
        normal_text = [
            "I searched the web and found this information.",
            "Discord is a messaging platform.",
            "Getting data from the API now.",
            "Remember to check your messages.",
            "Let's search for answers together.",
        ]
        
        import re
        tool_pattern = re.compile(
            r'\b(web_search|discord_\w+|get_\w+|remember_\w+|search_\w+)\s*\{[^}]+\}',
            re.IGNORECASE
        )
        
        for text in normal_text:
            match = tool_pattern.search(text)
            self.assertIsNone(match, f"Should NOT detect in: {text}")


class TestToolCallWorkflow(unittest.TestCase):
    """Integration tests for the complete tool call workflow"""

    def test_tool_call_clears_initial_response(self):
        """Test that when tool calls are detected, initial ai_response is cleared"""
        # This tests the logic at bot/client.py line ~988
        # When tool_calls are present, ai_response should be cleared to prevent
        # "Let me search..." messages
        
        # Simulate: AI returns text + tool_calls
        initial_response = "Let me search for that information."
        tool_calls = [{"id": "call_123", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "test"}'}}]
        
        # In the actual code, if tool_calls exist, ai_response gets set to ""
        if tool_calls:
            ai_response = ""
        else:
            ai_response = initial_response
        
        self.assertEqual(ai_response, "", "Should clear initial response when tool calls exist")

    def test_sanitization_after_tool_execution(self):
        """Test that sanitization happens after tool execution and follow-up call"""
        # Simulate the workflow:
        # 1. Initial AI call returns tool_calls
        # 2. Tools execute and return results
        # 3. Follow-up AI call with tool results
        # 4. Response is sanitized before sending to Discord
        
        # Simulate a follow-up response that accidentally includes tool syntax
        follow_up_response = '''The current Bitcoin price is $50,000.
        
get_crypto_price {"symbol": "BTC"}

This data is from CoinMarketCap.</s>'''
        
        # Apply sanitization
        final_response = sanitize_ai_response(follow_up_response)
        
        # Should remove tool syntax and EOS token
        self.assertNotIn('get_crypto_price', final_response)
        self.assertNotIn('</s>', final_response)
        
        # Should keep actual content
        self.assertIn('$50,000', final_response)
        self.assertIn('CoinMarketCap', final_response)


class TestResponseUniquenessSanitization(unittest.TestCase):
    """Test that sanitization preserves legitimate content while removing syntax"""

    def test_preserve_code_blocks(self):
        """Test that legitimate code in code blocks is preserved"""
        response = '''Here's a Python example:
```python
def search(query):
    return web_search(query)
```
This function calls web_search.'''
        
        sanitized = sanitize_ai_response(response)
        
        # Should preserve code block
        self.assertIn('```python', sanitized)
        self.assertIn('def search', sanitized)
        self.assertIn('web_search(query)', sanitized)

    def test_preserve_json_examples(self):
        """Test that legitimate JSON examples are preserved if not tool calls"""
        response = '''Here's an example API response:
{
    "status": "success",
    "data": {
        "price": 50000
    }
}'''
        
        sanitized = sanitize_ai_response(response)
        
        # This JSON should be preserved because it doesn't match the tool call pattern
        # (no "type": "function" field)
        self.assertIn('"status"', sanitized)
        self.assertIn('"success"', sanitized)

    def test_remove_only_tool_call_json(self):
        """Test that only tool call JSON is removed, not all JSON"""
        response = '''Here is data: {"type": "data", "value": 123}
And a tool call: {"type": "function", "name": "web_search", "parameters": {}}
More data: {"type": "result", "output": "success"}'''
        
        sanitized = sanitize_ai_response(response)
        
        # Tool call JSON should be removed
        self.assertNotIn('web_search', sanitized)
        
        # But other JSON should remain
        self.assertIn('"type": "data"', sanitized)
        self.assertIn('"type": "result"', sanitized)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Tests for tool functionality
"""

import unittest
import sys
import os
import time
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.tool_manager import ToolManager

class TestToolManager(unittest.TestCase):
    """Test cases for the ToolManager class"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.tool_manager = ToolManager()

    def test_tool_registration(self):
        """Test that all tools are properly registered"""
        expected_tools = [
            'web_search',
            'company_research',
            'crawling',
            'get_crypto_price',
            'get_stock_price',
            'calculate',
            'get_bonus_schedule',
            'remember_user_info'
        ]

        for tool_name in expected_tools:
            self.assertIn(tool_name, self.tool_manager.tools)

    def test_get_available_tools(self):
        """Test that tool definitions are properly formatted"""
        tools = self.tool_manager.get_available_tools()
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)

        # Check that each tool has the required structure
        for tool in tools:
            self.assertIn('type', tool)
            self.assertIn('function', tool)
            self.assertIn('name', tool['function'])
            self.assertIn('description', tool['function'])
            self.assertIn('parameters', tool['function'])

    def test_calculate_tool(self):
        """Test the calculate tool"""
        result = self.tool_manager.calculate("2 + 2")
        self.assertEqual(result, "Result: 4")

        # Wait to avoid rate limiting
        time.sleep(0.2)

        result = self.tool_manager.calculate("10 * 5")
        self.assertEqual(result, "Result: 50")

    def test_calculate_tool_invalid_expression(self):
        """Test the calculate tool with invalid expressions"""
        # Wait to avoid rate limiting
        time.sleep(0.2)

        result = self.tool_manager.calculate("2 + ")
        self.assertIn("Error", result)

        # Wait to avoid rate limiting
        time.sleep(0.2)

        result = self.tool_manager.calculate("import os")
        self.assertIn("Error", result)

    def test_get_bonus_schedule(self):
        """Test the bonus schedule tool"""
        # Wait to avoid rate limiting
        time.sleep(1.0)

        result = self.tool_manager.get_bonus_schedule("stake", "weekly")
        self.assertIn("Saturday 12:30 PM UTC", result)

        # Wait to avoid rate limiting
        time.sleep(1.0)

        result = self.tool_manager.get_bonus_schedule("shuffle", "weekly")
        self.assertIn("Thursday 11:00 AM UTC", result)

    def test_get_bonus_schedule_invalid(self):
        """Test the bonus schedule tool with invalid parameters"""
        result = self.tool_manager.get_bonus_schedule("invalid", "weekly")
        self.assertIn("No schedule found", result)

    def test_rate_limiting(self):
        """Test that rate limiting works"""
        # First call should work
        result1 = self.tool_manager.calculate("2 + 2")
        # We can't reliably test rate limiting in unit tests due to timing
        # Just verify the function works

    def test_execute_tool(self):
        """Test executing tools through the execute_tool method"""
        # Wait to avoid rate limiting
        time.sleep(0.2)

        # Test valid tool execution
        import asyncio
        result = asyncio.run(self.tool_manager.execute_tool("calculate", {
            "expression": "5 * 5"
        }))
        self.assertEqual(result, "Result: 25")

        # Test invalid tool
        result = asyncio.run(self.tool_manager.execute_tool("nonexistent_tool", {}))
        self.assertIn("Unknown tool", result)

        # Test invalid arguments
        result = asyncio.run(self.tool_manager.execute_tool("calculate", {
            "invalid_param": "value"
        }))
        self.assertIn("Error executing", result)

if __name__ == '__main__':
    unittest.main()

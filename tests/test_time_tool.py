#!/usr/bin/env python3
"""
Tests for time tool functionality in tool manager
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytz

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestTimeTool(unittest.TestCase):
    """Test cases for the time tool in tool manager"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        from tools.tool_manager import ToolManager
        self.tool_manager = ToolManager()

    def test_time_tool_registered(self):
        """Test that the time tool is registered in the tool manager"""
        self.assertIn("get_current_time", self.tool_manager.tools)
        self.assertTrue(callable(self.tool_manager.tools["get_current_time"]))

    def test_time_tool_in_available_tools(self):
        """Test that the time tool appears in available tools list"""
        available_tools = self.tool_manager.get_available_tools()

        # Find the time tool in the list
        time_tool_found = False
        for tool in available_tools:
            if isinstance(tool, dict) and "function" in tool:
                function_data = tool["function"]
                if function_data.get("name") == "get_current_time":
                    time_tool_found = True
                    # Verify description
                    self.assertEqual(function_data.get("description"), "Get current time and date information for any timezone worldwide")

                    # Verify parameters structure
                    parameters = function_data.get("parameters")
                    self.assertIsNotNone(parameters)
                    self.assertEqual(parameters.get("type"), "object")

                    properties = parameters.get("properties")
                    self.assertIsNotNone(properties)
                    self.assertIn("timezone", properties)

                    timezone_param = properties["timezone"]
                    self.assertEqual(timezone_param.get("default"), "UTC")

                    required_params = parameters.get("required", [])
                    self.assertEqual(required_params, [])
                    break

        self.assertTrue(time_tool_found, "get_current_time should be in available tools")

    @patch('tools.tool_manager.datetime')
    @patch('tools.tool_manager.pytz.timezone')
    def test_get_current_time_utc_default(self, mock_timezone, mock_datetime):
        """Test get_current_time with default UTC timezone"""
        # Mock timezone
        mock_tz = MagicMock()
        mock_tz.strftime.side_effect = [
            "03:30:45 PM",  # time_str
            "Thursday, October 02, 2025",  # date_str
            "2025-10-02 15:30:45 UTC",  # iso_str
            "275",  # day_of_year
            "+0000"  # offset
        ]
        mock_tz.isocalendar.return_value = (2025, 40, 4)  # year, week, day
        mock_timezone.return_value = mock_tz
        mock_datetime.now.return_value = mock_tz

        # Test the tool
        result = self.tool_manager.get_current_time()

        # Verify the result
        self.assertIn("Current time in UTC", result)
        self.assertIn("3:30:45 PM", result)  # No leading zero
        self.assertIn("Thursday, October 02, 2025", result)
        self.assertIn("Day of Year: 275", result)
        self.assertIn("Week: 40", result)
        self.assertIn("UTC+0:00", result)  # No leading zero in hours

    @patch('tools.tool_manager.datetime')
    @patch('tools.tool_manager.pytz.timezone')
    def test_get_current_time_with_timezone(self, mock_timezone, mock_datetime):
        """Test get_current_time with specific timezone"""
        # Mock timezone
        mock_tz = MagicMock()
        mock_tz.strftime.side_effect = [
            "11:30:45 PM",  # time_str
            "Thursday, October 02, 2025",  # date_str
            "2025-10-02 23:30:45 EDT",  # iso_str
            "275",  # day_of_year
            "-0400"  # offset
        ]
        mock_tz.isocalendar.return_value = (2025, 40, 4)
        mock_timezone.return_value = mock_tz
        mock_datetime.now.return_value = mock_tz

        # Test the tool with EST timezone
        result = self.tool_manager.get_current_time("est")

        # Verify pytz.timezone was called with US/Eastern
        mock_timezone.assert_called_with("US/Eastern")

        # Verify the result
        self.assertIn("Current time in US/Eastern", result)
        self.assertIn("11:30:45 PM", result)
        self.assertIn("UTC-4:00", result)  # No leading zero in hours

    @patch('tools.tool_manager.pytz.timezone')
    def test_get_current_time_invalid_timezone_fallback(self, mock_timezone):
        """Test get_current_time falls back to UTC for invalid timezone"""
        # Mock pytz to raise UnknownTimeZoneError first, then succeed for UTC
        mock_timezone.side_effect = [
            pytz.exceptions.UnknownTimeZoneError("Invalid/Timezone"),
            MagicMock()  # UTC fallback
        ]

        # Mock datetime for UTC fallback
        with patch('tools.tool_manager.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.side_effect = [
                "03:30:45 PM",  # time_str
                "Thursday, October 02, 2025",  # date_str
                "2025-10-02 15:30:45 UTC",  # iso_str
                "275",  # day_of_year
                "+0000"  # offset
            ]
            mock_now.isocalendar.return_value = (2025, 40, 4)
            mock_datetime.now.return_value = mock_now

            # Test the tool with invalid timezone
            result = self.tool_manager.get_current_time("Invalid/Timezone")

            # Should still return a valid result with UTC fallback
            self.assertIn("Current time in UTC", result)

    def test_get_current_time_rate_limiting(self):
        """Test that get_current_time respects rate limiting"""
        # Mock the rate limit check to return False (rate limited)
        with patch.object(self.tool_manager, '_check_rate_limit', return_value=False):
            result = self.tool_manager.get_current_time()
            self.assertEqual(result, "Rate limit exceeded. Please wait before checking time again.")

    def test_get_current_time_error_handling(self):
        """Test error handling in get_current_time"""
        # Mock pytz.timezone to raise an exception
        with patch('tools.tool_manager.pytz.timezone', side_effect=Exception("Test error")):
            result = self.tool_manager.get_current_time("invalid_timezone")
            self.assertIn("Error getting time:", result)



    def test_execute_tool_with_time_tool(self):
        """Test executing the time tool through execute_tool method"""
        # Test that the tool can be executed through the execute_tool method
        import asyncio
        result = asyncio.run(self.tool_manager.execute_tool("get_current_time", {"timezone": "UTC"}))

        # Verify that the result contains expected time information
        self.assertIn("Current time in", result)
        self.assertIn("Time:", result)
        self.assertIn("Date:", result)

    def test_system_prompt_includes_time_tool(self):
        """Test that the system prompt includes the time tool"""
        from config import SYSTEM_PROMPT

        self.assertIn("get_current_time", SYSTEM_PROMPT)
        self.assertIn("Current time and date for any timezone worldwide", SYSTEM_PROMPT)
        self.assertIn('"what time" → get_current_time', SYSTEM_PROMPT)
        self.assertIn('"current time" → get_current_time', SYSTEM_PROMPT)


if __name__ == '__main__':
    unittest.main()

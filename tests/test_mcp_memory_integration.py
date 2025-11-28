"""
Tests for MCP Memory Integration
"""
import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))

from tools.mcp_memory_client import MCPMemoryClient, get_mcp_server_url
from tools.tool_manager import ToolManager
from config import MCP_MEMORY_ENABLED


class TestMCPMemoryClient(unittest.TestCase):
    """Test cases for MCP Memory Client"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = MCPMemoryClient()
        self.client.enabled = True  # Force enable for testing
        
    def test_client_initialization(self):
        """Test MCP memory client initialization"""
        self.assertIsInstance(self.client, MCPMemoryClient)
        # Test that client gets a valid URL (either from port file or default)
        expected_url = get_mcp_server_url()
        self.assertEqual(self.client.server_url, expected_url)
        self.assertTrue(self.client.enabled)  # Should be True due to setUp
        
    def test_client_initialization_with_custom_url(self):
        """Test MCP memory client initialization with custom URL"""
        custom_url = "http://localhost:9999"
        client = MCPMemoryClient(custom_url)
        self.assertEqual(client.server_url, custom_url)
        
    def test_client_disabled(self):
        """Test client behavior when disabled"""
        import asyncio
        client = MCPMemoryClient()
        client.enabled = False
        
        result = asyncio.run(client.remember_user_info("user123", "preferences", "likes crypto"))
        self.assertIn("error", result)
        self.assertEqual(result["error"], "MCP memory server not enabled")
        
        result = asyncio.run(client.search_user_memory("user123", "crypto"))
        self.assertIn("error", result)
        self.assertEqual(result["error"], "MCP memory server not enabled")


class TestToolManagerMCPIntegration(unittest.TestCase):
    """Test cases for ToolManager MCP integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tool_manager = ToolManager()
        
    def test_mcp_tools_registered(self):
        """Test that MCP memory tools are registered"""
        self.assertIn("remember_user_mcp", self.tool_manager.tools)
        self.assertIn("search_user_memory", self.tool_manager.tools)
        
    def test_mcp_tools_in_available_tools(self):
        """Test that MCP memory tools are in available tools list"""
        available_tools = self.tool_manager.get_available_tools()
        tool_names = [tool["function"]["name"] for tool in available_tools]
        
        self.assertIn("remember_user_mcp", tool_names)
        self.assertIn("search_user_memory", tool_names)
        
    @patch('config.MCP_MEMORY_ENABLED', False)
    def test_remember_user_mcp_disabled(self):
        """Test remember_user_mcp when MCP is disabled"""
        result = self.tool_manager.remember_user_mcp("user123", "preferences", "likes crypto")
        # Should fallback to SQLite when MCP is disabled
        self.assertIn("Got it! I'll remember that", result)
        
    @patch('tools.tool_manager.MCP_MEMORY_ENABLED', False)
    def test_search_user_memory_disabled(self):
        """Test search_user_memory when MCP is disabled"""
        result = self.tool_manager.search_user_memory("user123", "crypto")
        self.assertIn("MCP memory server is not enabled", result)


class TestMCPMemoryIntegration(unittest.TestCase):
    """Integration tests for MCP memory system"""
    
    def test_dependency_container_includes_mcp_client(self):
        """Test that dependency container includes MCP memory client"""
        from utils.dependency_container import BotDependencies
        
        # Test that MCP memory client is included in the dataclass
        self.assertIn("mcp_memory_client", BotDependencies.__dataclass_fields__)
        
    @patch('config.MCP_MEMORY_ENABLED', True)
    def test_dependency_container_creates_mcp_client(self):
        """Test that dependency container creates MCP memory client when enabled"""
        from utils.dependency_container import BotDependencies
        
        deps = BotDependencies.create_defaults("test_token")
        self.assertIsNotNone(deps.mcp_memory_client)
        self.assertIsInstance(deps.mcp_memory_client, MCPMemoryClient)
        
    @patch('config.MCP_MEMORY_ENABLED', False)
    def test_dependency_container_skips_mcp_client(self):
        """Test that dependency container skips MCP memory client when disabled"""
        from utils.dependency_container import BotDependencies
        
        deps = BotDependencies.create_defaults("test_token")
        self.assertIsNone(deps.mcp_memory_client)


if __name__ == '__main__':
    # Run the tests
    unittest.main()
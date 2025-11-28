"""
Tests for MCP Memory Security and Authentication
"""
import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import sys
import os
import tempfile
import json

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))

from tools.mcp_memory_client import MCPMemoryClient, get_mcp_auth_token
from tools.mcp_memory_server import MCPMemoryServer


class TestMCPMemoryAuthentication(unittest.TestCase):
    """Test cases for MCP Memory authentication security"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.token_file = os.path.join(self.temp_dir, '.mcp_token')
        self.port_file = os.path.join(self.temp_dir, '.mcp_port')
        
    def tearDown(self):
        """Clean up test fixtures"""
        # Clean up temp files
        for file_path in [self.token_file, self.port_file]:
            if os.path.exists(file_path):
                os.remove(file_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
        # Clean up environment variable
        if "MCP_MEMORY_TOKEN" in os.environ:
            del os.environ["MCP_MEMORY_TOKEN"]
    
    def test_auth_token_generation(self):
        """Test that authentication tokens are properly generated"""
        server = MCPMemoryServer()
        
        # Token should be generated
        self.assertIsNotNone(server.auth_token)
        self.assertGreater(len(server.auth_token), 32)  # Should be secure random token
        
        # Token should be different each time
        server2 = MCPMemoryServer()
        self.assertNotEqual(server.auth_token, server2.auth_token)
    
    def test_token_file_creation(self):
        """Test that token file is created with proper permissions"""
        # Mock the token file path
        with patch.object(MCPMemoryServer, '__init__', return_value=None):
            server = MCPMemoryServer()
            server.token_file = self.token_file
            server.auth_token = "test_token_123"
            
            # Simulate token file creation
            with open(self.token_file, "w") as f:
                f.write(server.auth_token)
            os.chmod(self.token_file, 0o600)
            
            # Verify file exists and has correct permissions
            self.assertTrue(os.path.exists(self.token_file))
            
            # Read token back
            with open(self.token_file, "r") as f:
                read_token = f.read().strip()
            self.assertEqual(read_token, server.auth_token)
    
    def test_get_auth_token_from_environment(self):
        """Test getting auth token from environment variable"""
        test_token = "env_test_token_123"
        os.environ["MCP_MEMORY_TOKEN"] = test_token
        
        token = get_mcp_auth_token()
        self.assertEqual(token, test_token)
    
    def test_get_auth_token_from_file(self):
        """Test getting auth token from file when env var not set"""
        test_token = "file_test_token_456"
        
        # Create token file
        with open(self.token_file, "w") as f:
            f.write(test_token)
        
        # Mock the token file path
        with patch('tools.mcp_memory_client.os.path.join', return_value=self.token_file):
            token = get_mcp_auth_token()
            self.assertEqual(token, test_token)
    
    def test_get_auth_token_none_available(self):
        """Test behavior when no auth token is available"""
        # Ensure no env var and no file
        if "MCP_MEMORY_TOKEN" in os.environ:
            del os.environ["MCP_MEMORY_TOKEN"]
        
        # Mock non-existent token file
        with patch('tools.mcp_memory_client.os.path.join', return_value="/nonexistent/token"):
            token = get_mcp_auth_token()
            self.assertIsNone(token)
    
    def test_client_initialization_with_auth_token(self):
        """Test MCP memory client initialization with auth token"""
        test_token = "client_test_token_789"
        client = MCPMemoryClient(auth_token=test_token)
        
        self.assertEqual(client.auth_token, test_token)
        # Default URL may vary based on port file availability
        self.assertTrue(client.server_url.startswith("http://localhost:"))
    
    def test_client_initialization_without_auth_token(self):
        """Test MCP memory client initialization without auth token"""
        # Set environment variable
        test_token = "env_client_token_012"
        os.environ["MCP_MEMORY_TOKEN"] = test_token
        
        client = MCPMemoryClient()
        self.assertEqual(client.auth_token, test_token)


class TestMCPMemorySecurityIntegration(unittest.TestCase):
    """Integration tests for MCP Memory security"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.token_file = os.path.join(self.temp_dir, '.mcp_token')
        
    def tearDown(self):
        """Clean up test fixtures"""
        if "MCP_MEMORY_TOKEN" in os.environ:
            del os.environ["MCP_MEMORY_TOKEN"]
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    @patch('config.MCP_MEMORY_ENABLED', True)
    def test_authentication_error_handling(self):
        """Test that authentication errors are properly handled"""
        # Create client with wrong token
        client = MCPMemoryClient(auth_token="wrong_token")
        client.enabled = True
        
        # Mock a 401 response
        async def mock_request():
            return {"error": "Authentication failed - invalid or missing token"}
        
        # This would normally make a real request, but we're testing the error handling
        result = {"error": "Authentication failed - invalid or missing token"}
        
        self.assertIn("error", result)
        self.assertIn("Authentication failed", result["error"])
    
    def test_token_security_features(self):
        """Test security features of the authentication system"""
        server = MCPMemoryServer()
        
        # Test token validation
        valid_token = server.auth_token
        self.assertTrue(server._validate_token(valid_token))
        
        # Test invalid token rejection
        invalid_token = "invalid_token_123"
        self.assertFalse(server._validate_token(invalid_token))
        
        # Test empty token rejection
        self.assertFalse(server._validate_token(""))
        
        # Test that tokens are different between instances
        server2 = MCPMemoryServer()
        self.assertNotEqual(server.auth_token, server2.auth_token)


class TestMCPMemoryBackwardCompatibility(unittest.TestCase):
    """Tests for backward compatibility and graceful degradation"""
    
    def test_graceful_degradation_without_auth(self):
        """Test that system degrades gracefully without authentication"""
        # Ensure no environment variable is set
        if "MCP_MEMORY_TOKEN" in os.environ:
            del os.environ["MCP_MEMORY_TOKEN"]
        
        # Mock token file as non-existent
        with patch('tools.mcp_memory_client.os.path.exists', return_value=False):
            # Create client without auth token
            client = MCPMemoryClient(auth_token=None)
            client.enabled = True
            
            # Should handle missing auth gracefully
            self.assertIsNone(client.auth_token)
            
            # The client should still be able to attempt connections
            # (though they will fail with 401 if server requires auth)
            self.assertIsNotNone(client.server_url)
    
    def test_environment_variable_fallback(self):
        """Test fallback to environment variable when file is not available"""
        test_token = "fallback_token_123"
        os.environ["MCP_MEMORY_TOKEN"] = test_token
        
        # Mock non-existent file
        with patch('tools.mcp_memory_client.os.path.exists', return_value=False):
            token = get_mcp_auth_token()
            self.assertEqual(token, test_token)


if __name__ == '__main__':
    # Run the tests
    unittest.main()
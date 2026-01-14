"""
Simple MCP Memory Client for Jakey
Provides HTTP client interface to MCP Memory Server
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

import aiohttp

from config import MCP_MEMORY_ENABLED

logger = logging.getLogger(__name__)


def get_mcp_server_url():
    """Get the MCP server URL from port file or use default"""
    port_file = os.path.join(os.path.dirname(__file__), "..", ".mcp_port")
    if os.path.exists(port_file):
        try:
            with open(port_file, "r") as f:
                port = f.read().strip()
                return f"http://localhost:{port}"
        except Exception as e:
            logging.warning(f"Failed reading MCP port file: {e}")

    # Fallback to default port
    return "http://localhost:8001"


def get_mcp_auth_token():
    """Get the MCP authentication token from file or environment"""
    # First try environment variable
    token = os.environ.get("MCP_MEMORY_TOKEN")
    if token:
        return token

    # Then try token file
    token_file = os.path.join(os.path.dirname(__file__), "..", ".mcp_token")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                return f.read().strip()
        except Exception as e:
            logging.warning(f"MCP token file read error: {e}")

    # No token available
    return None


class MCPMemoryClient:
    """Simple HTTP client for MCP Memory Server with authentication"""

    def __init__(
        self, server_url: Optional[str] = None, auth_token: Optional[str] = None
    ):
        self.server_url = server_url or get_mcp_server_url()
        self.auth_token = auth_token or get_mcp_auth_token()
        self.enabled = MCP_MEMORY_ENABLED
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Logging optimization
        self.verbose_logging = os.environ.get("MCP_VERBOSE_LOGGING", "false").lower() == "true"
        self._last_log_time = {}
        self._operation_counts = {}
        self._log_cooldown = 30  # seconds between similar logs

    async def __aenter__(self):
        """Async context manager entry"""
        if self.enabled:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def check_connection(self) -> bool:
        """Check if MCP memory server is accessible and authenticated"""
        if not self.enabled or not self.session:
            return False

        try:
            # Health check doesn't require authentication
            async with self.session.get(
                f"{self.server_url}/health", timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Check if server has authentication enabled
                    auth_enabled = data.get("authentication_enabled", False)
                    if auth_enabled and not self.auth_token:
                        logger.warning("MCP server auth failed - no token")
                        return False
                    return True
                return False
        except Exception:
            return False

    def _should_log_operation(self, operation: str) -> bool:
        """Check if operation should be logged based on rate limiting"""
        current_time = time.time()
        last_time = self._last_log_time.get(operation, 0)
        
        # Always log if verbose mode is enabled or enough time has passed
        if self.verbose_logging or (current_time - last_time) > self._log_cooldown:
            self._last_log_time[operation] = current_time
            return True
        return False

    def _increment_operation_count(self, operation: str):
        """Track operation frequency for summary logging"""
        self._operation_counts[operation] = self._operation_counts.get(operation, 0) + 1

    def _log_operation_result(
        self, 
        operation: str, 
        user_id: Optional[str], 
        result: Dict[str, Any], 
        success_suffix: str = ""
    ) -> Dict[str, Any]:
        """Centralized logging for MCP memory operations with rate limiting"""
        self._increment_operation_count(operation)
        
        if "error" in result:
            # Always log errors at INFO level
            if user_id:
                logger.error(f"MCP {operation} failed for {user_id}: {result['error']}")
            else:
                logger.error(f"MCP {operation} failed: {result['error']}")
        else:
            # Only log successes if rate limiting allows or verbose mode is enabled
            if self._should_log_operation(operation):
                if user_id:
                    success_msg = f"MCP {operation} completed for {user_id}"
                else:
                    success_msg = f"MCP {operation} completed"
                
                if success_suffix:
                    success_msg += f": {success_suffix}"
                
                # Use DEBUG level for routine operations, INFO for important ones
                if operation in ["memory storage", "memory search"]:
                    logger.debug(success_msg)
                else:
                    logger.info(success_msg)
        
        return result

    def get_operation_summary(self) -> Dict[str, int]:
        """Get summary of operations performed since last check"""
        summary = self._operation_counts.copy()
        self._operation_counts.clear()
        return summary

    def log_operation_summary_if_needed(self) -> bool:
        """Log operation summary if there are operations to report"""
        if not self._operation_counts:
            return False
            
        summary = self.get_operation_summary()
        total_ops = sum(summary.values())
        
        if total_ops > 0:
            # Create a readable summary
            operations_str = ", ".join([f"{op}: {count}" for op, count in summary.items()])
            logger.info(f"MCP operations summary (last period) - {operations_str}")
            return True
        return False

    async def _make_request(
        self, endpoint: str, method: str = "GET", data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated HTTP request to MCP memory server"""
        if not self.enabled:
            return {"error": "MCP memory server not enabled"}

        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

        url = f"{self.server_url}/{endpoint}"

        # Prepare headers with authentication
        headers = {}
        if self.auth_token and endpoint != "health":  # Don't send auth for health check
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            if method == "GET":
                async with self.session.get(url, headers=headers) as response:
                    if response.status == 401:
                        return {
                            "error": "Authentication failed - invalid or missing token"
                        }
                    result = await response.json()
            elif method == "POST":
                async with self.session.post(
                    url, json=data, headers=headers
                ) as response:
                    if response.status == 401:
                        return {
                            "error": "Authentication failed - invalid or missing token"
                        }
                    result = await response.json()
            elif method == "DELETE":
                async with self.session.delete(url, headers=headers) as response:
                    if response.status == 401:
                        return {
                            "error": "Authentication failed - invalid or missing token"
                        }
                    result = await response.json()
            else:
                return {"error": f"Unsupported HTTP method: {method}"}

            return result

        except aiohttp.ClientError as e:
            logger.error(f"MCP connection error: {e}")
            return {"error": f"Connection error: {str(e)}"}
        except json.JSONDecodeError as e:
            logger.error(f"MCP memory server JSON decode error: {e}")
            return {"error": f"JSON decode error: {str(e)}"}
        except Exception as e:
            logger.error(f"MCP memory server unexpected error: {e}")
            return {"error": f"Unexpected error: {str(e)}"}

    async def remember_user_info(
        self, user_id: str, information_type: str, information: str
    ) -> Dict[str, Any]:
        """Store user information in MCP memory server"""
        data = {
            "user_id": user_id,
            "information_type": information_type,
            "information": information,
            "timestamp": asyncio.get_running_loop().time(),
        }

        result = await self._make_request("memories", method="POST", data=data)
        return self._log_operation_result("memory storage", user_id, result, information_type)

    async def search_user_memory(
        self, user_id: str, query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search user memories in MCP memory server"""
        params = {"user_id": user_id}
        if query:
            params["query"] = query

        # Build query string
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"memories/search?{query_string}"

        result = await self._make_request(endpoint, method="GET")
        return self._log_operation_result("memory search", user_id, result)

    async def get_user_memories(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get recent memories for a user"""
        endpoint = f"memories?user_id={user_id}&limit={limit}"

        result = await self._make_request(endpoint, method="GET")
        return self._log_operation_result("memory retrieval", user_id, result)

    async def delete_user_memories(
        self, user_id: str, memory_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete user memories from MCP memory server"""
        params = {"user_id": user_id}
        if memory_type:
            params["type"] = memory_type

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"memories?{query_string}"

        result = await self._make_request(endpoint, method="DELETE")
        return self._log_operation_result("memory deletion", user_id, result)

    async def health_check(self) -> Dict[str, Any]:
        """Check MCP memory server health"""
        result = await self._make_request("health", method="GET")
        return self._log_operation_result("health check", None, result)


# Global MCP memory client instance
mcp_memory_client = MCPMemoryClient()

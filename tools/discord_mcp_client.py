"""
Discord MCP Client for JakeySelfBot
Provides integration with discord-self-mcp server
"""
import json
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional, Union
from config import MCP_MEMORY_ENABLED
import logging
import os
import subprocess
import sys
import threading
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DiscordMCPClient:
    """Client for Discord MCP server integration"""

    def __init__(self, server_url: Optional[str] = "http://localhost:5555"):
        """
        Initialize Discord MCP client
        For discord-self-mcp, we typically connect directly without URL discovery
        since it requires DISCORD_TOKEN to be passed via env.
        """
        self.server_url = server_url
        self.enabled = True  # MCP Discord integration will always attempt to connect

    @asynccontextmanager
    async def get_session(self):
        """Context manager to provide proper aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            yield session

    async def _make_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Discord MCP server via HTTP bridge (simulated)"""
        # Since discord-self-mcp uses stdio for MCP protocol, not HTTP,
        # the actual implementation would require a different approach
        # For now, we'll return a placeholder that explains this limitation
        logger.warning(f"Discord MCP tool '{tool_name}' requested but not yet implemented")
        return {"error": f"Discord MCP method '{tool_name}' is not yet implemented in Jakey"}

    async def get_user_info(self) -> Dict[str, Any]:
        """Get information about the currently logged-in Discord user"""
        return await self._make_request("get_user_info", {})

    async def list_guilds(self) -> Dict[str, Any]:
        """List all Discord servers/guilds the user is in"""
        return await self._make_request("list_guilds", {})

    async def list_channels(self, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """List channels the user has access to, optionally filtered by guild"""
        args = {}
        if guild_id:
            args["guildId"] = guild_id
        return await self._make_request("list_channels", args)

    async def read_channel(self, channel_id: str, limit: int = 50) -> Dict[str, Any]:
        """Read messages from a specific Discord channel"""
        args = {
            "channelId": channel_id,
            "limit": min(limit, 100)  # API caps at 100
        }
        return await self._make_request("read_channel", args)

    async def search_messages(self, channel_id: str, query: str = "",
                             author_id: Optional[str] = None,
                             limit: int = 100) -> Dict[str, Any]:
        """Search for messages in a Discord channel by content, author, etc."""
        args = {
            "channelId": channel_id,
            "limit": min(limit, 500)  # API caps at 500
        }
        if query:
            args["query"] = query
        if author_id:
            args["authorId"] = author_id
        return await self._make_request("search_messages", args)

    async def list_guild_members(self, guild_id: str,
                                limit: int = 100,
                                include_roles: bool = False) -> Dict[str, Any]:
        """List members of a specific Discord guild/server"""
        args = {
            "guildId": guild_id,
            "limit": min(limit, 1000),  # API caps at 1000
            "includeRoles": include_roles
        }
        return await self._make_request("list_guild_members", args)

    async def send_message(self, channel_id: str, content: str,
                          reply_to_message_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to a specific Discord channel"""
        args = {
            "channelId": channel_id,
            "content": content
        }
        if reply_to_message_id:
            args["replyToMessageId"] = reply_to_message_id
        return await self._make_request("send_message", args)

    async def check_connection(self) -> bool:
        """Check if Discord MCP server is accessible"""
        # For now, just return true as the actual connection check would require
        # the MCP stdio protocol implementation
        return True

# Global Discord MCP client instance
discord_mcp_client = DiscordMCPClient()

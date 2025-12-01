"""
MCP Memory Backend

Implements the MemoryBackend interface using the MCP Memory Server.
"""
import time
import logging
from typing import Dict, Optional, Any, List

from .backend import MemoryBackend, MemoryConfig, MemoryEntry

logger = logging.getLogger(__name__)

class MCPMemoryBackend(MemoryBackend):
    """MCP Memory Server backend"""

    def __init__(self, config: MemoryConfig, mcp_client):
        super().__init__(config)
        self.mcp_client = mcp_client

    async def store(self, user_id: str, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """Store a memory entry using MCP server"""
        try:
            # MCP uses different storage format
            # Convert key-value to MCP format
            memory_data = {
                "type": "user_info",
                "key": key,
                "value": value,
                "metadata": metadata or {}
            }

            result = await self.mcp_client.remember_user_info(user_id, key, value)
            return "error" not in str(result).lower()
        except Exception as e:
            logger.error(f"MCP memory store failed: {e}")
            return False

    async def retrieve(self, user_id: str, key: str) -> Optional[MemoryEntry]:
        """Retrieve a specific memory entry from MCP server"""
        try:
            # MCP doesn't have direct key retrieval
            # Use search to find specific key
            results = await self.mcp_client.search_user_memory(user_id, key)
            if results and "memories" in results:
                for memory in results["memories"]:
                    if memory.get("key") == key:
                        return MemoryEntry(
                            user_id=user_id,
                            key=memory["key"],
                            value=memory.get("value", ""),
                            created_at=memory.get("created_at", time.time()),
                            updated_at=memory.get("updated_at", time.time()),
                            metadata=memory.get("metadata", {})
                        )
        except Exception as e:
            logger.error(f"MCP memory retrieve failed: {e}")
        return None

    async def search(self, user_id: str, query: Optional[str] = None, limit: int = 10) -> List[MemoryEntry]:
        """Search memory entries in MCP server"""
        try:
            results = await self.mcp_client.search_user_memory(user_id, query)
            entries = []

            if results and "memories" in results:
                for memory in results["memories"][:limit]:
                    entries.append(MemoryEntry(
                        user_id=user_id,
                        key=memory.get("key", ""),
                        value=memory.get("value", ""),
                        created_at=memory.get("created_at", time.time()),
                        updated_at=memory.get("updated_at", time.time()),
                        metadata=memory.get("metadata", {})
                    ))

            return entries
        except Exception as e:
            logger.error(f"MCP memory search failed: {e}")
            return []

    async def get_all(self, user_id: str) -> Dict[str, str]:
        """Get all memory entries for a user from MCP server"""
        try:
            results = await self.mcp_client.get_user_memories(user_id, limit=1000)
            memories = {}

            if results and "memories" in results:
                for memory in results["memories"]:
                    key = memory.get("key", "")
                    value = memory.get("value", "")
                    if key:
                        memories[key] = value

            return memories
        except Exception as e:
            logger.error(f"MCP get_all failed: {e}")
            return {}

    async def delete(self, user_id: str, key: Optional[str] = None) -> bool:
        """Delete memory entries from MCP server"""
        try:
            result = await self.mcp_client.delete_user_memories(user_id, key)
            return result.get("success", False)
        except Exception as e:
            logger.error(f"MCP memory delete failed: {e}")
            return False

    async def health_check(self) -> bool:
        """Check if MCP backend is healthy"""
        try:
            # Try a simple operation to check health
            result = await self.mcp_client.get_user_memories("health_check", limit=1)
            return isinstance(result, dict)
        except Exception as e:
            logger.error(f"MCP health check failed: {e}")
            return False

    async def cleanup(self, max_age_days: int = 30) -> int:
        """Clean up old entries (MCP handles its own cleanup)"""
        # MCP backend handles its own cleanup
        logger.info("MCP memory cleanup handled by server")
        return 0
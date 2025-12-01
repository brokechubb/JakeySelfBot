"""
Unified Memory Backend

Manages multiple memory backends with automatic failover and load balancing.
"""
import asyncio
import time
import logging
from typing import Dict, Optional, Any, List, Tuple

from .backend import MemoryBackend, MemoryConfig, MemoryEntry

logger = logging.getLogger(__name__)

class UnifiedMemoryBackend:
    """
    Unified memory backend that manages multiple backends with automatic failover
    and load balancing capabilities.
    """

    def __init__(self):
        self.backends: Dict[str, MemoryBackend] = {}
        self._initialize_backends()

    def _initialize_backends(self):
        """Initialize all available memory backends"""
        from data.database import db
        from tools.mcp_memory_client import MCPMemoryClient
        from config import MCP_MEMORY_ENABLED

        # Always add SQLite backend (primary/fallback)
        sqlite_config = MemoryConfig(enabled=True, priority=1)
        self.backends["sqlite"] = self._create_sqlite_backend(sqlite_config, db)

        # Add MCP backend if enabled (higher priority)
        if MCP_MEMORY_ENABLED:
            try:
                mcp_client = MCPMemoryClient()
                mcp_config = MemoryConfig(enabled=True, priority=2)  # Higher priority
                self.backends["mcp"] = self._create_mcp_backend(mcp_config, mcp_client)
                logger.info("MCP memory backend initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize MCP memory backend: {e}")

        logger.info(f"Initialized {len(self.backends)} memory backends")

    def _create_sqlite_backend(self, config: MemoryConfig, db_manager) -> MemoryBackend:
        """Create SQLite backend instance"""
        # Import here to avoid circular imports
        import importlib
        sqlite_module = importlib.import_module('memory.sqlite_backend')
        return sqlite_module.SQLiteMemoryBackend(config, db_manager)

    def _create_mcp_backend(self, config: MemoryConfig, mcp_client) -> MemoryBackend:
        """Create MCP backend instance"""
        # Import here to avoid circular imports
        import importlib
        mcp_module = importlib.import_module('memory.mcp_backend')
        return mcp_module.MCPMemoryBackend(config, mcp_client)

    async def store(self, user_id: str, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """Store to all available backends"""
        success_count = 0

        for backend_name, backend in self._get_backends_by_priority():
            if backend.config.enabled:
                try:
                    if await backend.store(user_id, key, value, metadata):
                        success_count += 1
                        logger.debug(f"Successfully stored to {backend_name}")
                    else:
                        logger.warning(f"Failed to store to {backend_name}")
                except Exception as e:
                    logger.error(f"Error storing to {backend_name}: {e}")

        return success_count > 0

    async def retrieve(self, user_id: str, key: str) -> Optional[MemoryEntry]:
        """Retrieve from highest priority healthy backend"""
        for backend_name, backend in self._get_backends_by_priority():
            if backend.config.enabled:
                try:
                    result = await backend.retrieve(user_id, key)
                    if result:
                        logger.debug(f"Retrieved from {backend_name}")
                        return result
                except Exception as e:
                    logger.error(f"Error retrieving from {backend_name}: {e}")

        return None

    async def search(self, user_id: str, query: Optional[str] = None, limit: int = 10) -> List[MemoryEntry]:
        """Search across all backends and merge results"""
        all_results = []

        for backend_name, backend in self._get_backends_by_priority():
            if backend.config.enabled:
                try:
                    results = await backend.search(user_id, query, limit)
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Error searching {backend_name}: {e}")

        # Remove duplicates (same user_id + key) and sort by priority/backend
        seen_keys = set()
        unique_results = []

        for result in all_results:
            key = (result.user_id, result.key)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_results.append(result)

        # Sort by updated_at (most recent first)
        unique_results.sort(key=lambda x: x.updated_at, reverse=True)

        return unique_results[:limit]

    async def get_all(self, user_id: str) -> Dict[str, str]:
        """Get all memories, merging from all backends"""
        all_memories = {}

        for backend_name, backend in self._get_backends_by_priority():
            if backend.config.enabled:
                try:
                    memories = await backend.get_all(user_id)
                    all_memories.update(memories)  # Later backends override earlier ones
                except Exception as e:
                    logger.error(f"Error getting all from {backend_name}: {e}")

        return all_memories

    async def delete(self, user_id: str, key: Optional[str] = None) -> bool:
        """Delete from all backends"""
        success_count = 0

        for backend_name, backend in self._get_backends_by_priority():
            if backend.config.enabled:
                try:
                    if await backend.delete(user_id, key):
                        success_count += 1
                        logger.debug(f"Successfully deleted from {backend_name}")
                except Exception as e:
                    logger.error(f"Error deleting from {backend_name}: {e}")

        return success_count > 0

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all backends"""
        health_status = {}

        # Run health checks concurrently
        tasks = []
        backend_names = []

        for name, backend in self.backends.items():
            tasks.append(backend.health_check())
            backend_names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(backend_names, results):
            if isinstance(result, Exception):
                logger.error(f"Health check failed for {name}: {result}")
                health_status[name] = False
            else:
                health_status[name] = result

        return health_status

    async def cleanup(self, max_age_days: int = 30) -> Dict[str, int]:
        """Clean up old entries in all backends"""
        cleanup_results = {}

        for backend_name, backend in self.backends.items():
            if backend.config.enabled:
                try:
                    cleaned = await backend.cleanup(max_age_days)
                    cleanup_results[backend_name] = cleaned
                except Exception as e:
                    logger.error(f"Cleanup failed for {backend_name}: {e}")
                    cleanup_results[backend_name] = 0

        return cleanup_results

    def _get_backends_by_priority(self) -> List[Tuple[str, MemoryBackend]]:
        """Get backends sorted by priority (highest first)"""
        return sorted(
            self.backends.items(),
            key=lambda x: x[1].config.priority,
            reverse=True
        )

    def get_backend_status(self) -> Dict[str, Dict]:
        """Get detailed status of all backends"""
        status = {}
        for name, backend in self.backends.items():
            status[name] = {
                "enabled": backend.config.enabled,
                "priority": backend.config.priority,
                "type": backend.__class__.__name__,
                "healthy": None  # Will be filled by health_check
            }
        return status

    async def get_full_status(self) -> Dict[str, Any]:
        """Get comprehensive status including health"""
        status = self.get_backend_status()
        health = await self.health_check()

        for backend_name in status:
            status[backend_name]["healthy"] = health.get(backend_name, False)

        return {
            "backends": status,
            "total_backends": len(self.backends),
            "healthy_backends": sum(health.values()),
            "timestamp": time.time()
        }
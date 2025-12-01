"""
SQLite Memory Backend

Implements the MemoryBackend interface using the existing SQLite database.
"""
import time
import logging
from typing import Dict, Optional, Any, List

from .backend import MemoryBackend, MemoryConfig, MemoryEntry

logger = logging.getLogger(__name__)

class SQLiteMemoryBackend(MemoryBackend):
    """SQLite-based memory backend using existing database"""

    def __init__(self, config: MemoryConfig, db_manager):
        super().__init__(config)
        self.db = db_manager

    async def store(self, user_id: str, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """Store a memory entry using SQLite database"""
        try:
            await self.db.aadd_memory(user_id, key, value)
            return True
        except Exception as e:
            logger.error(f"SQLite memory store failed: {e}")
            return False

    async def retrieve(self, user_id: str, key: str) -> Optional[MemoryEntry]:
        """Retrieve a specific memory entry from SQLite"""
        try:
            value = await self.db.aget_memory(user_id, key)
            if value:
                return MemoryEntry(
                    user_id=user_id,
                    key=key,
                    value=value,
                    created_at=time.time(),  # SQLite doesn't store timestamps in memory table
                    updated_at=time.time(),
                    metadata=None  # SQLite doesn't support metadata
                )
        except Exception as e:
            logger.error(f"SQLite memory retrieve failed: {e}")
        return None

    async def search(self, user_id: str, query: Optional[str] = None, limit: int = 10) -> List[MemoryEntry]:
        """Search memory entries in SQLite (basic implementation)"""
        try:
            # Get all memories for user
            all_memories = await self.db.aget_memories(user_id)
            entries = []

            # Filter by query if provided
            for key, value in all_memories.items():
                if not query or query.lower() in key.lower() or query.lower() in value.lower():
                    entries.append(MemoryEntry(
                        user_id=user_id,
                        key=key,
                        value=value,
                        created_at=time.time(),
                        updated_at=time.time(),
                        metadata=None
                    ))

            # Sort by key (basic ordering) and limit
            entries.sort(key=lambda x: x.key)
            return entries[:limit]
        except Exception as e:
            logger.error(f"SQLite memory search failed: {e}")
            return []

    async def get_all(self, user_id: str) -> Dict[str, str]:
        """Get all memory entries for a user as key-value pairs"""
        try:
            return await self.db.aget_memories(user_id)
        except Exception as e:
            logger.error(f"SQLite get_all failed: {e}")
            return {}

    async def delete(self, user_id: str, key: Optional[str] = None) -> bool:
        """Delete memory entries from SQLite"""
        # Note: Current SQLite implementation doesn't support deletion
        # This could be added by extending the database schema
        logger.warning("SQLite memory backend does not support deletion")
        return False

    async def health_check(self) -> bool:
        """Check if SQLite backend is healthy"""
        try:
            # Try a simple operation to check health
            test_result = await self.db.aget_memory("health_check", "test")
            return True
        except Exception as e:
            logger.error(f"SQLite health check failed: {e}")
            return False

    async def cleanup(self, max_age_days: int = 30) -> int:
        """Clean up old entries (not supported in current SQLite implementation)"""
        # SQLite memory table doesn't have timestamps
        # Could be enhanced to support cleanup if schema is extended
        logger.info("SQLite memory cleanup not implemented (no timestamps in schema)")
        return 0
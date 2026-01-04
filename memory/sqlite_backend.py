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
        try:
            if key:
                # Delete specific memory key (not currently implemented in database)
                # For now, delete all memories for the user
                logger.warning(f"SQLite backend does not support deleting specific keys. Deleting all memories for user {user_id}")
                await self.db.adelete_memories(user_id)
            else:
                # Delete all memories for the user
                deleted_count = await self.db.adelete_memories(user_id)
                logger.info(f"Deleted {deleted_count} memories for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"SQLite memory deletion failed: {e}")
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
        """Clean up old entries using timestamps in the database schema"""
        try:
            # Calculate the cutoff date
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=max_age_days)).isoformat()

            # Delete all memories older than the cutoff date for all users
            # The database schema includes created_at and updated_at timestamps
            total_deleted = 0
            deleted_count = await self.db.adelete_old_memories("", cutoff_date)
            total_deleted += deleted_count

            logger.info(f"SQLite memory cleanup completed: deleted {total_deleted} entries older than {max_age_days} days")
            return total_deleted
        except Exception as e:
            logger.error(f"SQLite memory cleanup failed: {e}")
            return 0
# Memory System Consolidation Plan

## Current Issues
- **Dual Interfaces**: SQLite and MCP memory have different APIs
- **Inconsistent Usage**: Code has to handle both systems separately
- **Fallback Logic**: Complex switching between memory systems
- **Maintenance Burden**: Changes require updates in multiple places

## Proposed Unified Memory Backend Architecture

```python
# memory/__init__.py
from .backend import MemoryBackend, MemoryConfig
from .sqlite_backend import SQLiteMemoryBackend
from .mcp_backend import MCPMemoryBackend
from .unified_backend import UnifiedMemoryBackend

# Global memory backend instance
memory_backend = UnifiedMemoryBackend()
```

## Core Interfaces

### Base Memory Backend
```python
# memory/backend.py
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

@dataclass
class MemoryConfig:
    """Configuration for memory backends"""
    enabled: bool = True
    priority: int = 1  # Higher priority = preferred backend
    timeout: float = 5.0
    max_retries: int = 2

@dataclass
class MemoryEntry:
    """Standardized memory entry format"""
    user_id: str
    key: str
    value: str
    created_at: float
    updated_at: float
    metadata: Dict[str, Any] = None

class MemoryBackend(ABC):
    """Abstract base class for all memory backends"""

    def __init__(self, config: MemoryConfig):
        self.config = config

    @abstractmethod
    async def store(self, user_id: str, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """Store a memory entry"""
        pass

    @abstractmethod
    async def retrieve(self, user_id: str, key: str) -> Optional[MemoryEntry]:
        """Retrieve a specific memory entry"""
        pass

    @abstractmethod
    async def search(self, user_id: str, query: Optional[str] = None, limit: int = 10) -> List[MemoryEntry]:
        """Search memory entries for a user"""
        pass

    @abstractmethod
    async def get_all(self, user_id: str) -> Dict[str, str]:
        """Get all memory entries for a user as key-value pairs"""
        pass

    @abstractmethod
    async def delete(self, user_id: str, key: Optional[str] = None) -> bool:
        """Delete memory entries (specific key or all for user)"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if backend is healthy"""
        pass

    @abstractmethod
    async def cleanup(self, max_age_days: int = 30) -> int:
        """Clean up old entries, return number cleaned"""
        pass
```

## Concrete Backend Implementations

### SQLite Backend
```python
# memory/sqlite_backend.py
class SQLiteMemoryBackend(MemoryBackend):
    """SQLite-based memory backend using existing database"""

    def __init__(self, config: MemoryConfig, db_manager):
        super().__init__(config)
        self.db = db_manager

    async def store(self, user_id: str, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        try:
            await self.db.aadd_memory(user_id, key, value)
            return True
        except Exception as e:
            logger.error(f"SQLite memory store failed: {e}")
            return False

    async def retrieve(self, user_id: str, key: str) -> Optional[MemoryEntry]:
        try:
            value = await self.db.aget_memory(user_id, key)
            if value:
                return MemoryEntry(
                    user_id=user_id,
                    key=key,
                    value=value,
                    created_at=time.time(),
                    updated_at=time.time()
                )
        except Exception as e:
            logger.error(f"SQLite memory retrieve failed: {e}")
        return None

    async def search(self, user_id: str, query: Optional[str] = None, limit: int = 10) -> List[MemoryEntry]:
        # SQLite has limited search capabilities
        # Return all memories for user (filtered by query if provided)
        try:
            all_memories = await self.db.aget_memories(user_id)
            entries = []

            for key, value in all_memories.items():
                if not query or query.lower() in key.lower() or query.lower() in value.lower():
                    entries.append(MemoryEntry(
                        user_id=user_id,
                        key=key,
                        value=value,
                        created_at=time.time(),
                        updated_at=time.time()
                    ))

            return entries[:limit]
        except Exception as e:
            logger.error(f"SQLite memory search failed: {e}")
            return []

    async def get_all(self, user_id: str) -> Dict[str, str]:
        try:
            return await self.db.aget_memories(user_id)
        except Exception as e:
            logger.error(f"SQLite get_all failed: {e}")
            return {}

    async def delete(self, user_id: str, key: Optional[str] = None) -> bool:
        # SQLite backend doesn't support delete operations
        # Could be added if needed
        return False

    async def health_check(self) -> bool:
        try:
            # Simple health check - try to get a test memory
            test_result = await self.db.aget_memory("health_check", "test")
            return True
        except Exception:
            return False

    async def cleanup(self, max_age_days: int = 30) -> int:
        # SQLite backend doesn't support cleanup
        # Could be added if needed
        return 0
```

### MCP Backend
```python
# memory/mcp_backend.py
class MCPMemoryBackend(MemoryBackend):
    """MCP Memory Server backend"""

    def __init__(self, config: MemoryConfig, mcp_client):
        super().__init__(config)
        self.mcp_client = mcp_client

    async def store(self, user_id: str, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
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
            return "error" not in result.lower()
        except Exception as e:
            logger.error(f"MCP memory store failed: {e}")
            return False

    async def retrieve(self, user_id: str, key: str) -> Optional[MemoryEntry]:
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
        try:
            result = await self.mcp_client.delete_user_memories(user_id, key)
            return result.get("success", False)
        except Exception as e:
            logger.error(f"MCP memory delete failed: {e}")
            return False

    async def health_check(self) -> bool:
        try:
            # Try a simple operation to check health
            result = await self.mcp_client.get_user_memories("health_check", limit=1)
            return isinstance(result, dict)
        except Exception:
            return False

    async def cleanup(self, max_age_days: int = 30) -> int:
        # MCP backend handles its own cleanup
        return 0
```

## Unified Backend (Main Interface)
```python
# memory/unified_backend.py
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

        # Always add SQLite backend (primary)
        sqlite_config = MemoryConfig(enabled=True, priority=1)
        self.backends["sqlite"] = SQLiteMemoryBackend(sqlite_config, db)

        # Add MCP backend if enabled
        if MCP_MEMORY_ENABLED:
            try:
                mcp_client = MCPMemoryClient()
                mcp_config = MemoryConfig(enabled=True, priority=2)  # Higher priority
                self.backends["mcp"] = MCPMemoryBackend(mcp_config, mcp_client)
            except Exception as e:
                logger.warning(f"Failed to initialize MCP memory backend: {e}")

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

        for backend_name, backend in self.backends.items():
            try:
                health_status[backend_name] = await backend.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {backend_name}: {e}")
                health_status[backend_name] = False

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
                "type": backend.__class__.__name__
            }
        return status
```

## Migration Strategy

### Phase 1: Create Memory Backend Infrastructure
- Implement `MemoryBackend` abstract base class
- Create `MemoryConfig` and `MemoryEntry` dataclasses
- Set up `memory/` package structure

### Phase 2: Implement Concrete Backends
- Create `SQLiteMemoryBackend` using existing database
- Create `MCPMemoryBackend` using existing MCP client
- Ensure both implement the full `MemoryBackend` interface

### Phase 3: Create Unified Backend
- Implement `UnifiedMemoryBackend` with failover logic
- Add priority-based backend selection
- Implement result merging and deduplication

### Phase 4: Update Tool Manager
- Replace direct database/MCP calls with unified backend
- Update `remember_user_info`, `search_user_memory` methods
- Maintain backward compatibility during transition

### Phase 5: Update Dependencies
- Update `utils/dependency_container.py` to include memory backend
- Update any other direct memory system usage
- Add memory backend to bot initialization

## Benefits
- **Unified API**: Single interface for all memory operations
- **Automatic Failover**: Seamless switching between backends
- **Load Balancing**: Priority-based backend selection
- **Extensibility**: Easy to add new memory backends
- **Consistency**: Same interface regardless of backend
- **Performance**: Parallel operations across backends
- **Reliability**: Graceful degradation when backends fail

## Usage Examples

```python
# Simple usage
from memory import memory_backend

# Store a memory
await memory_backend.store("user123", "favorite_color", "blue")

# Retrieve a memory
memory = await memory_backend.retrieve("user123", "favorite_color")
if memory:
    print(f"Color: {memory.value}")

# Search memories
results = await memory_backend.search("user123", "color", limit=5)

# Get all memories
all_memories = await memory_backend.get_all("user123")
```

This unified system provides a clean, consistent interface while maintaining the benefits of both memory systems and adding automatic failover capabilities.
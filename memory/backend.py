"""
Unified Memory Backend System for JakeySelfBot

This module provides a unified interface for all memory operations,
supporting multiple backend implementations with automatic failover.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import time
import logging

logger = logging.getLogger(__name__)

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
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "user_id": self.user_id,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create from dictionary"""
        return cls(
            user_id=data["user_id"],
            key=data["key"],
            value=data["value"],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {})
        )

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

    @property
    def name(self) -> str:
        """Get backend name"""
        return self.__class__.__name__.replace('MemoryBackend', '').lower()
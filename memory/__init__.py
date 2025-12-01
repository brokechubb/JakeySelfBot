"""
Memory System Package

Provides unified memory backend system with multiple storage implementations.

Usage:
    from memory import memory_backend
    await memory_backend.store(user_id, key, value)
    result = await memory_backend.retrieve(user_id, key)
"""

__version__ = "1.0.0"

# Initialize memory backend on import
try:
    from .unified_backend import UnifiedMemoryBackend
    memory_backend = UnifiedMemoryBackend()
except ImportError:
    memory_backend = None
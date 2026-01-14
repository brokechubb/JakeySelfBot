"""
Dependency injection container for JakeySelfBot
"""
from typing import Optional
from dataclasses import dataclass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.openrouter import openrouter_api, OpenRouterAPI
from data.database import db, DatabaseManager
from tools.tool_manager import tool_manager, ToolManager
from utils.tipcc_manager import TipCCManager
from tools.mcp_memory_client import MCPMemoryClient
from typing import Optional, Any

try:
    from memory import memory_backend
except ImportError:
    memory_backend = None


@dataclass
class BotDependencies:
    """Container for all bot dependencies"""
    database: DatabaseManager
    tool_manager: ToolManager
    ai_client: OpenRouterAPI
    discord_token: str
    tipcc_manager: Optional[TipCCManager] = None
    mcp_memory_client: Optional[MCPMemoryClient] = None
    memory_backend: Optional[Any] = None
    command_prefix: str = '%'

    @classmethod
    def create_defaults(cls, discord_token: str) -> 'BotDependencies':
        """Factory method to create default dependencies"""
        tipcc_manager = None
        from config import MCP_MEMORY_ENABLED
        mcp_memory_client = MCPMemoryClient() if MCP_MEMORY_ENABLED else None
        
        return cls(
            database=db,
            tool_manager=tool_manager,
            ai_client=openrouter_api,
            tipcc_manager=tipcc_manager,
            mcp_memory_client=mcp_memory_client,
            memory_backend=memory_backend,
            discord_token=discord_token
        )


_deps: Optional[BotDependencies] = None

def get_dependencies() -> BotDependencies:
    """Get global dependencies"""
    if _deps is None:
        raise RuntimeError("Dependencies not initialized. Call init_dependencies() first.")
    return _deps

def init_dependencies(discord_token: str) -> BotDependencies:
    """Initialize global dependencies"""
    global _deps
    _deps = BotDependencies.create_defaults(discord_token)
    return _deps

def set_dependencies(deps: BotDependencies) -> None:
    """Set global dependencies (for testing)"""
    global _deps
    _deps = deps

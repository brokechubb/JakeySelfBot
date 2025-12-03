import asyncio
import datetime
import json
import logging
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from config import DATABASE_PATH

# Configure logging with colored output
from utils.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    def __init__(self):
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self.db_path = DATABASE_PATH
        self.user_cache = {}  # Cache for user data
        self.cache_expiry = 300  # Cache expiry in seconds (5 minutes)
        # ThreadPool for async operations
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="db-worker"
        )
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                preferences TEXT,
                important_facts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create conversations table with channel support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                channel_id TEXT,
                message_history TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Create memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                key TEXT,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Add performance indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_created ON conversations(user_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_channel_created ON conversations(channel_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_channel ON conversations(user_id, channel_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_user_key ON memories(user_id, key)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )

        # Create settings table for bot configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create tip.cc balances table for tracking cryptocurrency balances
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tipcc_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency TEXT NOT NULL,
                amount REAL NOT NULL,
                usd_value REAL NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(currency)
            )
        """)

        # Create tip.cc transactions table for tracking all tip.cc transactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tipcc_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_type TEXT NOT NULL,
                currency TEXT NOT NULL,
                amount REAL,
                usd_value REAL NOT NULL,
                sender TEXT,
                recipient TEXT,
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                reminder_type TEXT NOT NULL,
                title TEXT,
                description TEXT,
                trigger_time TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'pending',
                channel_id TEXT,
                recurring_pattern TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Create reaction_roles table for reaction role functionality
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                emoji TEXT NOT NULL,
                role_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(message_id, emoji)
            )
        """)

        # Create keywords table for configurable trigger words
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add performance indexes for reminders
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_user_status ON reminders(user_id, status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_trigger_time ON reminders(trigger_time)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_user_status_time ON reminders(user_id, status, trigger_time)"
        )

        # Migration: Add sender column to tipcc_transactions if it doesn't exist
        cursor.execute("PRAGMA table_info(tipcc_transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        if "sender" not in columns:
            cursor.execute("ALTER TABLE tipcc_transactions ADD COLUMN sender TEXT")

        conn.commit()
        conn.close()

    def _is_cache_valid(self, timestamp):
        """Check if cache entry is still valid"""
        return time.time() - timestamp < self.cache_expiry

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user data by user_id with caching and validation"""
        # Validate user_id to prevent SQL injection
        if not isinstance(user_id, str) or not user_id.strip():
            logger.warning("Invalid user_id provided to get_user")
            return None
        
        try:
            # Additional validation for Discord user ID format
            import re
            if not re.match(r'^\d{17,19}$', user_id.strip()):
                logger.warning(f"Invalid Discord user ID format: {user_id}")
                return None
        except Exception:
            logger.warning("User ID validation failed")
            return None
        
        # Check cache first
        if user_id in self.user_cache:
            cached_data, timestamp = self.user_cache[user_id]
            if self._is_cache_valid(timestamp):
                return cached_data

        # Fetch from database with parameterized query
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id.strip(),))
        row = cursor.fetchone()

        if row:
            user_data = {
                "user_id": row[0],
                "username": row[1],
                "preferences": json.loads(row[2]) if row[2] else {},
                "important_facts": json.loads(row[3]) if row[3] else {},
                "created_at": row[4],
                "updated_at": row[5],
            }
            # Update cache
            self.user_cache[user_id] = (user_data, time.time())
            conn.close()
            return user_data

        conn.close()
        return None

    def create_or_update_user(
        self,
        user_id: str,
        username: str,
        preferences: Optional[Dict[str, Any]] = None,
        important_facts: Optional[Dict[str, Any]] = None,
    ):
        """Create or update user data with cache invalidation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO users (user_id, username, preferences, important_facts, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                user_id,
                username,
                json.dumps(preferences or {}),
                json.dumps(important_facts or {}),
            ),
        )

        conn.commit()
        conn.close()

        # Invalidate cache
        if user_id in self.user_cache:
            del self.user_cache[user_id]

    def add_conversation(
        self,
        user_id: str,
        message_history: List[Dict],
        channel_id: Optional[str] = None,
    ):
        """Add a conversation entry for a user in a specific channel"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO conversations (user_id, channel_id, message_history)
            VALUES (?, ?, ?)
        """,
            (user_id, channel_id or None, json.dumps(message_history)),
        )

        conn.commit()
        conn.close()

    def get_recent_conversations(self, user_id: str, limit: int = None) -> List[Dict]:
        """Get recent conversations for a user with optimized query"""
        from config import CONVERSATION_HISTORY_LIMIT

        if limit is None:
            limit = CONVERSATION_HISTORY_LIMIT
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT message_history, created_at, channel_id FROM conversations
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (user_id, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [{"messages": json.loads(row[0]), "timestamp": row[1], "channel_id": row[2]} for row in rows]

    def get_recent_channel_conversations(
        self, channel_id: str, limit: int = None
    ) -> List[Dict]:
        """Get recent conversations for a channel with optimized query"""
        from config import CONVERSATION_HISTORY_LIMIT

        if limit is None:
            limit = CONVERSATION_HISTORY_LIMIT
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT message_history, created_at FROM conversations
            WHERE channel_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (channel_id, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [{"messages": json.loads(row[0]), "timestamp": row[1]} for row in rows]

    def get_recent_user_channel_conversations(
        self, user_id: str, channel_id: str, limit: int = None
    ) -> List[Dict]:
        """Get recent conversations for a user in a specific channel"""
        from config import CONVERSATION_HISTORY_LIMIT

        if limit is None:
            limit = CONVERSATION_HISTORY_LIMIT
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT message_history, created_at FROM conversations
            WHERE user_id = ? AND channel_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (user_id, channel_id, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [{"messages": json.loads(row[0]), "timestamp": row[1]} for row in rows]

    def add_memory(self, user_id: str, key: str, value: str):
        """Add a memory entry for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO memories (user_id, key, value)
            VALUES (?, ?, ?)
        """,
            (user_id, key, value),
        )

        conn.commit()
        conn.close()

    def get_memories(self, user_id: str) -> Dict[str, str]:
        """Get all memories for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT key, value FROM memories WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()

        return {row[0]: row[1] for row in rows}

    def get_memory(self, user_id: str, key: str) -> Optional[str]:
        """Get a specific memory for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT value FROM memories WHERE user_id = ? AND key = ?", (user_id, key)
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None

    def clear_user_history(self, user_id: str):
        """Clear conversation history for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete all conversations for this user
        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))

        # Optionally, also clear memories for this user
        cursor.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()

        # Clear cache if this user is cached
        if user_id in self.user_cache:
            del self.user_cache[user_id]

    def clear_channel_history(self, channel_id: str):
        """Clear conversation history for a channel"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete all conversations for this channel
        cursor.execute("DELETE FROM conversations WHERE channel_id = ?", (channel_id,))

        conn.commit()
        conn.close()

    def clear_user_channel_history(self, user_id: str, channel_id: str):
        """Clear conversation history for a user in a specific channel"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete all conversations for this user in this channel
        cursor.execute(
            "DELETE FROM conversations WHERE user_id = ? AND channel_id = ?",
            (user_id, channel_id),
        )

        conn.commit()
        conn.close()

    def clear_all_history(self):
        """Clear all conversation history (admin/debug function)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete all conversations
        cursor.execute("DELETE FROM conversations")

        # Delete all memories
        cursor.execute("DELETE FROM memories")

        conn.commit()
        conn.close()

        # Clear entire cache
        self.user_cache.clear()

    def flush_database(self):
        """Completely flush and recreate the database (destructive operation)"""
        logger.warning(f"Flushing database at {self.db_path}")

        # Close any existing connections and delete the file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        # Clear cache
        self.user_cache.clear()

        # Reinitialize the database with empty tables
        self.init_database()

        logger.info("Database flushed and recreated")

    # Async database operations
    async def aget_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Async version of get_user"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_user, user_id)

    async def acreate_or_update_user(
        self,
        user_id: str,
        username: str,
        preferences: Optional[Dict[str, Any]] = None,
        important_facts: Optional[Dict[str, Any]] = None,
    ):
        """Async version of create_or_update_user"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.create_or_update_user,
            user_id,
            username,
            preferences,
            important_facts,
        )

    async def aadd_conversation(
        self,
        user_id: str,
        message_history: List[Dict],
        channel_id: Optional[str] = None,
    ):
        """Async version of add_conversation"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.add_conversation, user_id, message_history, channel_id
        )

    async def aget_recent_conversations(
        self, user_id: str, limit: int = None
    ) -> List[Dict]:
        """Async version of get_recent_conversations"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_recent_conversations, user_id, limit
        )

    async def aget_recent_channel_conversations(
        self, channel_id: str, limit: int = None
    ) -> List[Dict]:
        """Async version of get_recent_channel_conversations"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_recent_channel_conversations, channel_id, limit
        )

    async def aget_recent_user_channel_conversations(
        self, user_id: str, channel_id: str, limit: int = None
    ) -> List[Dict]:
        """Async version of get_recent_user_channel_conversations"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.get_recent_user_channel_conversations,
            user_id,
            channel_id,
            limit,
        )

    async def aadd_memory(self, user_id: str, key: str, value: str):
        """Async version of add_memory"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.add_memory, user_id, key, value
        )

    async def aget_memories(self, user_id: str) -> Dict[str, str]:
        """Async version of get_memories"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_memories, user_id)

    async def aget_memory(self, user_id: str, key: str) -> Optional[str]:
        """Async version of get_memory"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_memory, user_id, key)

    async def aclear_channel_history(self, channel_id: str):
        """Async version of clear_channel_history"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.clear_channel_history, channel_id
        )

    async def aclear_user_channel_history(self, user_id: str, channel_id: str):
        """Async version of clear_user_channel_history"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.clear_user_channel_history, user_id, channel_id
        )

    # tip.cc balance management methods
    def update_balance(self, currency: str, amount: float, usd_value: float):
        """Update or insert a cryptocurrency balance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tipcc_balances (currency, amount, usd_value, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (currency.upper(), amount, usd_value),
        )

        conn.commit()
        conn.close()

    def get_balance(self, currency: str) -> Optional[Dict[str, Any]]:
        """Get balance for a specific currency"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT currency, amount, usd_value, last_updated
            FROM tipcc_balances
            WHERE currency = ?
        """,
            (currency.upper(),),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "currency": row[0],
                "amount": row[1],
                "usd_value": row[2],
                "last_updated": row[3],
            }
        return None

    def get_all_balances(self) -> List[Dict[str, Any]]:
        """Get all cryptocurrency balances"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT currency, amount, usd_value, last_updated
            FROM tipcc_balances
            ORDER BY usd_value DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "currency": row[0],
                "amount": row[1],
                "usd_value": row[2],
                "last_updated": row[3],
            }
            for row in rows
        ]

    def clear_balances(self) -> bool:
        """Clear all cryptocurrency balances from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tipcc_balances")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error clearing balances: {e}")
            return False

    def get_total_usd_balance(self) -> float:
        """Get total USD value of all balances"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(usd_value) FROM tipcc_balances")
        result = cursor.fetchone()
        conn.close()

        return result[0] if result and result[0] else 0.0

    def add_transaction(
        self,
        transaction_type: str,
        currency: str,
        amount: Optional[float],
        usd_value: float,
        recipient: Optional[str] = None,
        message: Optional[str] = None,
        sender: Optional[str] = None,
    ):
        """Add a tip.cc transaction record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tipcc_transactions (transaction_type, currency, amount, usd_value, recipient, message, sender)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                transaction_type,
                currency.upper(),
                amount,
                usd_value,
                recipient,
                message,
                sender,
            ),
        )

        conn.commit()
        conn.close()

    def get_recent_transactions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent tip.cc transactions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT transaction_type, currency, amount, usd_value, recipient, message, timestamp, sender
            FROM tipcc_transactions
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "type": row[0],
                "currency": row[1],
                "amount": row[2],
                "usd_value": row[3],
                "recipient": row[4],
                "message": row[5],
                "timestamp": row[6],
                "sender": row[7],
            }
            for row in rows
        ]

    def get_transaction_stats(self) -> Dict[str, Any]:
        """Get transaction statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get total received from airdrops
        cursor.execute("""
            SELECT SUM(usd_value) FROM tipcc_transactions
            WHERE transaction_type = 'airdrop'
        """)
        total_airdrops = cursor.fetchone()[0] or 0.0

        # Get total sent tips
        cursor.execute("""
            SELECT SUM(usd_value) FROM tipcc_transactions
            WHERE transaction_type = 'tip_sent'
        """)
        total_sent = cursor.fetchone()[0] or 0.0

        # Get total received tips
        cursor.execute("""
            SELECT SUM(usd_value) FROM tipcc_transactions
            WHERE transaction_type = 'tip_received'
        """)
        total_received = cursor.fetchone()[0] or 0.0

        # Get transaction counts by type
        cursor.execute("""
            SELECT transaction_type, COUNT(*) FROM tipcc_transactions
            GROUP BY transaction_type
        """)
        type_counts = dict(cursor.fetchall())

        conn.close()

        return {
            "total_airdrops_usd": total_airdrops,
            "total_sent_usd": total_sent,
            "total_received_usd": total_received,
            "net_profit_usd": total_airdrops + total_received - total_sent,
            "transaction_counts": type_counts,
        }

    # Async versions of tip.cc methods
    async def aupdate_balance(self, currency: str, amount: float, usd_value: float):
        """Async version of update_balance"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.update_balance, currency, amount, usd_value
        )

    async def aget_balance(self, currency: str) -> Optional[Dict[str, Any]]:
        """Async version of get_balance"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_balance, currency)

    async def aget_all_balances(self) -> List[Dict[str, Any]]:
        """Async version of get_all_balances"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_all_balances)

    async def aclear_balances(self) -> bool:
        """Async version of clear_balances"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.clear_balances)

    async def aget_total_usd_balance(self) -> float:
        """Async version of get_total_usd_balance"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_total_usd_balance)

    async def aadd_transaction(
        self,
        transaction_type: str,
        currency: str,
        amount: float,
        usd_value: float,
        recipient: Optional[str] = None,
        message: Optional[str] = None,
        sender: Optional[str] = None,
    ):
        """Async version of add_transaction"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.add_transaction,
            transaction_type,
            currency,
            amount,
            usd_value,
            recipient,
            message,
            sender,
        )

    async def aget_recent_transactions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Async version of get_recent_transactions"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_recent_transactions, limit
        )

    async def aget_transaction_stats(self) -> Dict[str, Any]:
        """Async version of get_transaction_stats"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_transaction_stats)

    def close(self):
        """Cleanup resources"""
        self._executor.shutdown(wait=True)
        logger.info("Database executor shut down")

    def add_reminder(
        self,
        user_id: str,
        reminder_type: str,
        title: str,
        description: str,
        trigger_time: str,
        channel_id: str = None,
        recurring_pattern: str = None,
    ):
        """Add a new reminder"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO reminders (user_id, reminder_type, title, description, trigger_time, channel_id, recurring_pattern)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                reminder_type,
                title,
                description,
                trigger_time,
                channel_id,
                recurring_pattern,
            ),
        )

        conn.commit()
        conn.close()
        return cursor.lastrowid

    def get_reminder(self, reminder_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific reminder by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, reminder_type, title, description, trigger_time, status, channel_id, recurring_pattern, created_at
            FROM reminders WHERE id = ?
        """,
            (reminder_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "reminder_type": row[2],
                "title": row[3],
                "description": row[4],
                "trigger_time": row[5],
                "status": row[6],
                "channel_id": row[7],
                "recurring_pattern": row[8],
                "created_at": row[9],
            }
        return None

    def get_user_reminders(
        self, user_id: str, status: str = "pending"
    ) -> List[Dict[str, Any]]:
        """Get all reminders for a user with a specific status (default: pending)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, reminder_type, title, description, trigger_time, status, channel_id, recurring_pattern, created_at
            FROM reminders
            WHERE user_id = ? AND status = ?
            ORDER BY trigger_time ASC
        """,
            (user_id, status),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "user_id": row[1],
                "reminder_type": row[2],
                "title": row[3],
                "description": row[4],
                "trigger_time": row[5],
                "status": row[6],
                "channel_id": row[7],
                "recurring_pattern": row[8],
                "created_at": row[9],
            }
            for row in rows
        ]

    def get_due_reminders(self) -> List[Dict[str, Any]]:
        """Get all reminders that are due (current time >= trigger_time and status = pending)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, reminder_type, title, description, trigger_time, status, channel_id, recurring_pattern, created_at
            FROM reminders
            WHERE status = 'pending' AND trigger_time <= ?
        """,
            (datetime.datetime.now().isoformat(),),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "user_id": row[1],
                "reminder_type": row[2],
                "title": row[3],
                "description": row[4],
                "trigger_time": row[5],
                "status": row[6],
                "channel_id": row[7],
                "recurring_pattern": row[8],
                "created_at": row[9],
            }
            for row in rows
        ]

    def update_reminder_status(self, reminder_id: int, status: str):
        """Update the status of a reminder (pending, triggered, cancelled, etc.)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE reminders
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (status, reminder_id),
        )

        conn.commit()
        conn.close()

    def cancel_reminder(self, reminder_id: int, user_id: str = None) -> bool:
        """Cancel a reminder by updating its status to 'cancelled'"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if user_id:
            # If user_id provided, verify the reminder belongs to the user
            cursor.execute(
                """
                UPDATE reminders
                SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """,
                (reminder_id, user_id),
            )
        else:
            # Update without user verification
            cursor.execute(
                """
                UPDATE reminders
                SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (reminder_id,),
            )

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        return rows_affected > 0

    # Reaction roles methods
    def add_reaction_role(
        self, message_id: str, channel_id: str, emoji: str, role_id: str, guild_id: str
    ):
        """Add a reaction role mapping to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO reaction_roles (message_id, channel_id, emoji, role_id, guild_id)
            VALUES (?, ?, ?, ?, ?)
        """,
            (message_id, channel_id, emoji, role_id, guild_id),
        )

        conn.commit()
        conn.close()

    def remove_reaction_role(self, message_id: str, emoji: str):
        """Remove a reaction role mapping from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM reaction_roles WHERE message_id = ? AND emoji = ?
        """,
            (message_id, emoji),
        )

        conn.commit()
        conn.close()

    def get_reaction_roles_for_message(self, message_id: str):
        """Get all reaction roles for a specific message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT emoji, role_id FROM reaction_roles WHERE message_id = ?
        """,
            (message_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        return {row[0]: row[1] for row in rows}

    def get_reaction_role(self, message_id: str, emoji: str):
        """Get a specific reaction role for a message and emoji"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?
        """,
            (message_id, emoji),
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None

    def get_all_reaction_roles(self, guild_id: str):
        """Get all reaction roles for a guild"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT message_id, emoji, role_id, channel_id FROM reaction_roles WHERE guild_id = ?
        """,
            (guild_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "message_id": row[0],
                "emoji": row[1],
                "role_id": row[2],
                "channel_id": row[3],
            }
            for row in rows
        ]

    # Async versions of reminder methods
    async def aadd_reminder(
        self,
        user_id: str,
        reminder_type: str,
        title: str,
        description: str,
        trigger_time: str,
        channel_id: str = None,
        recurring_pattern: str = None,
    ):
        """Async version of add_reminder"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.add_reminder,
            user_id,
            reminder_type,
            title,
            description,
            trigger_time,
            channel_id,
            recurring_pattern,
        )

    # Async versions of reaction role methods
    async def aadd_reaction_role(
        self, message_id: str, channel_id: str, emoji: str, role_id: str, guild_id: str
    ):
        """Async version of add_reaction_role"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.add_reaction_role,
            message_id,
            channel_id,
            emoji,
            role_id,
            guild_id,
        )

    async def aremove_reaction_role(self, message_id: str, emoji: str):
        """Async version of remove_reaction_role"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.remove_reaction_role, message_id, emoji
        )

    async def aget_reaction_roles_for_message(self, message_id: str):
        """Async version of get_reaction_roles_for_message"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_reaction_roles_for_message, message_id
        )

    async def aget_reaction_role(self, message_id: str, emoji: str):
        """Async version of get_reaction_role"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_reaction_role, message_id, emoji
        )

    async def aget_all_reaction_roles(self, guild_id: str):
        """Async version of get_all_reaction_roles"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_all_reaction_roles, guild_id
        )

    async def aget_reminder(self, reminder_id: int) -> Optional[Dict[str, Any]]:
        """Async version of get_reminder"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_reminder, reminder_id
        )

    async def aget_user_reminders(
        self, user_id: str, status: str = "pending"
    ) -> List[Dict[str, Any]]:
        """Async version of get_user_reminders"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.get_user_reminders, user_id, status
        )

    async def aget_due_reminders(self) -> List[Dict[str, Any]]:
        """Async version of get_due_reminders"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_due_reminders)

    async def aupdate_reminder_status(self, reminder_id: int, status: str):
        """Async version of update_reminder_status"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.update_reminder_status, reminder_id, status
        )

    async def acancel_reminder(self, reminder_id: int, user_id: str = None) -> bool:
        """Async version of cancel_reminder"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.cancel_reminder, reminder_id, user_id
        )

    # Keyword management methods
    def add_keyword(self, keyword: str) -> bool:
        """Add a new trigger keyword"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT OR IGNORE INTO keywords (keyword) VALUES (?)",
                (keyword.lower(),),
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Added keyword: {keyword}")
            return success
        except sqlite3.Error as e:
            logger.error(f"Error adding keyword {keyword}: {e}")
            return False
        finally:
            conn.close()

    def remove_keyword(self, keyword: str) -> bool:
        """Remove a trigger keyword"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM keywords WHERE keyword = ?", (keyword.lower(),))
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Removed keyword: {keyword}")
            return success
        except sqlite3.Error as e:
            logger.error(f"Error removing keyword {keyword}: {e}")
            return False
        finally:
            conn.close()

    def get_keywords(self) -> List[str]:
        """Get all enabled keywords"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT keyword FROM keywords WHERE enabled = 1 ORDER BY keyword"
            )
            keywords = [row[0] for row in cursor.fetchall()]
            return keywords
        except sqlite3.Error as e:
            logger.error(f"Error getting keywords: {e}")
            return []
        finally:
            conn.close()

    def enable_keyword(self, keyword: str) -> bool:
        """Enable a keyword"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE keywords SET enabled = 1, updated_at = CURRENT_TIMESTAMP WHERE keyword = ?",
                (keyword.lower(),),
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Enabled keyword: {keyword}")
            return success
        except sqlite3.Error as e:
            logger.error(f"Error enabling keyword {keyword}: {e}")
            return False
        finally:
            conn.close()

    def disable_keyword(self, keyword: str) -> bool:
        """Disable a keyword"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE keywords SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE keyword = ?",
                (keyword.lower(),),
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Disabled keyword: {keyword}")
            return success
        except sqlite3.Error as e:
            logger.error(f"Error disabling keyword {keyword}: {e}")
            return False
        finally:
            conn.close()

    def check_message_for_keywords(self, message_content: str) -> bool:
        """Check if message contains any enabled keywords"""
        keywords = self.get_keywords()
        message_lower = message_content.lower()

        # Split message into words and check for exact keyword matches
        import re

        words = re.findall(r"\b\w+\b", message_lower)

        # Check for exact matches
        for keyword in keywords:
            if keyword in words:
                return True
            # Also check for multi-word phrases
            if " " in keyword and keyword in message_lower:
                return True

        return False

    # Async versions of keyword methods
    async def aadd_keyword(self, keyword: str) -> bool:
        """Async version of add_keyword"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.add_keyword, keyword)

    async def aremove_keyword(self, keyword: str) -> bool:
        """Async version of remove_keyword"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.remove_keyword, keyword)

    async def aget_keywords(self) -> List[str]:
        """Async version of get_keywords"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.get_keywords)

    async def aenable_keyword(self, keyword: str) -> bool:
        """Async version of enable_keyword"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.enable_keyword, keyword)

    async def adisable_keyword(self, keyword: str) -> bool:
        """Async version of disable_keyword"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self.disable_keyword, keyword)

    async def acheck_message_for_keywords(self, message_content: str) -> bool:
        """Async version of check_message_for_keywords"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self.check_message_for_keywords, message_content
        )

    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=True)
            logger.info("Database executor shut down")


# Global database instance
db = DatabaseManager()

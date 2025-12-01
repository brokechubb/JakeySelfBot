import asyncio
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class QueueMessage:
    id: str
    payload: Dict[str, Any]
    priority: MessagePriority
    status: MessageStatus
    created_at: float
    scheduled_at: float
    attempts: int
    max_attempts: int
    last_attempt: Optional[float]
    next_retry: Optional[float]
    error_message: Optional[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueMessage':
        data['priority'] = MessagePriority(data['priority'])
        data['status'] = MessageStatus(data['status'])
        return cls(**data)


class MessageQueue:
    """Persistent message queue with priority processing and dead letter queue support"""
    
    def __init__(self, db_path: str = "data/message_queue.db", max_batch_size: int = 100):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_batch_size = max_batch_size
        self._lock = asyncio.Lock()
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for message persistence"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    scheduled_at REAL NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    last_attempt REAL,
                    next_retry REAL,
                    error_message TEXT,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status_priority 
                ON messages(status, priority DESC, created_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_next_retry 
                ON messages(next_retry) WHERE next_retry IS NOT NULL
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dead_letter (
                    id TEXT PRIMARY KEY,
                    original_message TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    failed_at REAL NOT NULL,
                    final_error TEXT
                )
            """)
            
            conn.commit()
    
    async def enqueue(
        self,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        delay: float = 0,
        max_attempts: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a message to the queue"""
        message_id = str(uuid.uuid4())
        now = time.time()
        scheduled_at = now + delay
        
        message = QueueMessage(
            id=message_id,
            payload=payload,
            priority=priority,
            status=MessageStatus.PENDING,
            created_at=now,
            scheduled_at=scheduled_at,
            attempts=0,
            max_attempts=max_attempts,
            last_attempt=None,
            next_retry=None,
            error_message=None,
            metadata=metadata or {}
        )
        
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO messages 
                    (id, payload, priority, status, created_at, scheduled_at, 
                     attempts, max_attempts, last_attempt, next_retry, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.id,
                        json.dumps(message.payload),
                        message.priority.value,
                        message.status.value,
                        message.created_at,
                        message.scheduled_at,
                        message.attempts,
                        message.max_attempts,
                        message.last_attempt,
                        message.next_retry,
                        message.error_message,
                        json.dumps(message.metadata)
                    )
                )
                conn.commit()
        
        logger.debug(f"Enqueued message {message_id} with priority {priority.name}")
        return message_id
    
    async def dequeue(self, limit: Optional[int] = None) -> List[QueueMessage]:
        """Get next messages from queue based on priority and schedule"""
        limit = limit or self.max_batch_size
        now = time.time()
        
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get messages ready for processing
                cursor.execute(
                    """
                    SELECT * FROM messages 
                    WHERE status = 'pending' 
                    AND scheduled_at <= ?
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                    """,
                    (now, limit)
                )
                
                messages = []
                rows = cursor.fetchall()
                
                # Mark messages as processing first
                message_ids = [row[0] for row in rows]
                if message_ids:
                    placeholders = ','.join('?' * len(message_ids))
                    cursor.execute(
                        f"""
                        UPDATE messages 
                        SET status = 'processing', last_attempt = ?
                        WHERE id IN ({placeholders})
                        """,
                        [now] + message_ids
                    )
                
                # Now create message objects with updated status
                for row in rows:
                    message = self._row_to_message(row)
                    message.status = MessageStatus.PROCESSING  # Update status in memory
                    messages.append(message)
                
                conn.commit()
                return messages
    
    async def complete_message(self, message_id: str) -> bool:
        """Mark a message as successfully processed"""
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE messages SET status = 'completed' WHERE id = ?",
                    (message_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
    
    async def fail_message(
        self,
        message_id: str,
        error_message: str,
        retry_delay: Optional[float] = None
    ) -> bool:
        """Mark a message as failed and schedule retry if applicable"""
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current message
                cursor.execute(
                    """
                    SELECT attempts, max_attempts FROM messages 
                    WHERE id = ? AND status = 'processing'
                    """,
                    (message_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return False
                
                attempts, max_attempts = row
                attempts += 1
                
                if attempts >= max_attempts:
                    # Move to dead letter queue
                    await self._move_to_dead_letter(message_id, "Max attempts exceeded")
                    return True
                else:
                    # Schedule retry
                    next_retry = time.time() + (retry_delay or 60)
                    cursor.execute(
                        """
                        UPDATE messages 
                        SET status = 'pending', attempts = ?, next_retry = ?, error_message = ?
                        WHERE id = ?
                        """,
                        (attempts, next_retry, error_message, message_id)
                    )
                    conn.commit()
                    return True
    
    async def _move_to_dead_letter(self, message_id: str, reason: str):
        """Move a message to the dead letter queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get original message
            cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            row = cursor.fetchone()
            
            if row:
                message = self._row_to_message(row)
                
                # Add to dead letter
                cursor.execute(
                    """
                    INSERT INTO dead_letter (id, original_message, reason, failed_at, final_error)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        json.dumps(message.to_dict()),
                        reason,
                        time.time(),
                        message.error_message
                    )
                )
                
                # Remove from main queue
                cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
                
                conn.commit()
                logger.warning(f"Message {message_id} moved to dead letter: {reason}")
    
    def _row_to_message(self, row) -> QueueMessage:
        """Convert database row to QueueMessage object"""
        return QueueMessage(
            id=row[0],
            payload=json.loads(row[1]),
            priority=MessagePriority(row[2]),
            status=MessageStatus(row[3]),
            created_at=row[4],
            scheduled_at=row[5],
            attempts=row[6],
            max_attempts=row[7],
            last_attempt=row[8],
            next_retry=row[9],
            error_message=row[10],
            metadata=json.loads(row[11]) if row[11] else {}
        )
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Status counts
            cursor.execute("""
                SELECT status, COUNT(*) FROM messages GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Priority distribution
            cursor.execute("""
                SELECT priority, COUNT(*) FROM messages 
                WHERE status = 'pending' GROUP BY priority
            """)
            priority_counts = dict(cursor.fetchall())
            
            # Dead letter count
            cursor.execute("SELECT COUNT(*) FROM dead_letter")
            dead_letter_count = cursor.fetchone()[0]
            
            # Aging info
            cursor.execute("""
                SELECT 
                    AVG(created_at) as avg_age,
                    MIN(created_at) as oldest_age
                FROM messages WHERE status = 'pending'
            """)
            aging_row = cursor.fetchone()
            now = time.time()
            
            return {
                "pending": status_counts.get("pending", 0),
                "processing": status_counts.get("processing", 0),
                "completed": status_counts.get("completed", 0),
                "failed": status_counts.get("failed", 0),
                "dead_letter": dead_letter_count,
                "priority_distribution": {
                    MessagePriority(k).name: v for k, v in priority_counts.items()
                },
                "average_age_seconds": now - aging_row[0] if aging_row[0] else 0,
                "oldest_message_age_seconds": now - aging_row[1] if aging_row[1] else 0
            }
    
    async def get_dead_letter_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages from dead letter queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM dead_letter 
                ORDER BY failed_at DESC 
                LIMIT ?
                """,
                (limit,)
            )
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    "id": row[0],
                    "original_message": json.loads(row[1]),
                    "reason": row[2],
                    "failed_at": row[3],
                    "final_error": row[4]
                })
            
            return messages
    
    async def requeue_dead_letter(self, message_id: str) -> bool:
        """Requeue a message from dead letter queue"""
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get dead letter message
                cursor.execute(
                    "SELECT original_message FROM dead_letter WHERE id = ?",
                    (message_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return False
                
                original_data = json.loads(row[0])
                message = QueueMessage.from_dict(original_data)
                
                # Reset message state
                message.status = MessageStatus.PENDING
                message.attempts = 0
                message.last_attempt = None
                message.next_retry = None
                message.error_message = None
                message.created_at = time.time()
                message.scheduled_at = time.time()
                
                # Re-insert into main queue
                cursor.execute(
                    """
                    INSERT INTO messages 
                    (id, payload, priority, status, created_at, scheduled_at, 
                     attempts, max_attempts, last_attempt, next_retry, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.id,
                        json.dumps(message.payload),
                        message.priority.value,
                        message.status.value,
                        message.created_at,
                        message.scheduled_at,
                        message.attempts,
                        message.max_attempts,
                        message.last_attempt,
                        message.next_retry,
                        message.error_message,
                        json.dumps(message.metadata)
                    )
                )
                
                # Remove from dead letter
                cursor.execute("DELETE FROM dead_letter WHERE id = ?", (message_id,))
                
                conn.commit()
                logger.info(f"Requeued dead letter message {message_id}")
                return True
    
    async def cleanup_old_messages(self, days: int = 7) -> int:
        """Clean up old completed messages"""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM messages WHERE status = 'completed' AND last_attempt < ?",
                    (cutoff_time,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old completed messages")
                
                return deleted_count
    
    async def get_pending_count(self) -> int:
        """Get count of pending messages"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE status = 'pending' AND scheduled_at <= ?",
                (time.time(),)
            )
            return cursor.fetchone()[0]
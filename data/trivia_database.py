import asyncio
import datetime
import json
import logging
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from config import DATABASE_PATH

# Configure logging with colored output
from utils.logging_config import get_logger

logger = get_logger(__name__)


class TriviaDatabase:
    """Database manager for trivia questions, categories, and statistics"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Use same directory as main database but with trivia filename
            db_dir = os.path.dirname(DATABASE_PATH)
            db_path = os.path.join(db_dir, "trivia.db")

        # Create directory if it doesn't exist
        if db_path:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.cache = {}  # In-memory cache for frequently accessed data
        self.cache_expiry = 300  # Cache expiry in seconds (5 minutes)
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="trivia-db-worker"
        )
        self.init_database()

    def init_database(self):
        """Initialize the trivia database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create trivia categories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trivia_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                question_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create trivia questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trivia_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                difficulty INTEGER DEFAULT 1,
                source TEXT DEFAULT 'manual',
                external_id TEXT,
                is_active BOOLEAN DEFAULT 1,
                times_asked INTEGER DEFAULT 0,
                times_correct INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES trivia_categories(id) ON DELETE CASCADE
            )
        """)

        # Create trivia statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trivia_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                channel_id TEXT,
                guild_id TEXT,
                answered BOOLEAN,
                response_time_ms INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES trivia_questions(id) ON DELETE CASCADE
            )
        """)

        # Create trivia cache table for performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trivia_cache (
                category_name TEXT PRIMARY KEY,
                questions_json TEXT,
                expires_at TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for performance
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_questions_category ON trivia_questions(category_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_questions_active ON trivia_questions(is_active)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_questions_text ON trivia_questions(question_text)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_stats_timestamp ON trivia_stats(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_categories_active ON trivia_categories(is_active)"
        )

        conn.commit()
        conn.close()
        logger.info("Trivia database initialized")

    # Category Management
    async def add_category(
        self, name: str, display_name: str, description: Optional[str] = None
    ) -> Optional[int]:
        """Add a new trivia category"""

        def _add_category():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO trivia_categories (name, display_name, description)
                    VALUES (?, ?, ?)
                """,
                    (name, display_name, description),
                )
                category_id = cursor.lastrowid
                conn.commit()
                return category_id
            except sqlite3.IntegrityError:
                # Category already exists, return existing ID
                cursor.execute(
                    "SELECT id FROM trivia_categories WHERE name = ?", (name,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
            finally:
                conn.close()

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _add_category
        )

    async def get_category_by_name(self, name: str) -> Optional[Dict]:
        """Get category information by name"""

        def _get_category():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, display_name, description, is_active, question_count
                FROM trivia_categories WHERE name = ?
            """,
                (name,),
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "display_name": result[2],
                    "description": result[3],
                    "is_active": bool(result[4]),
                    "question_count": result[5],
                }
            return None

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _get_category
        )

    async def get_all_categories(self) -> List[Dict]:
        """Get all active trivia categories"""

        def _get_categories():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, display_name, description, question_count
                FROM trivia_categories WHERE is_active = 1
                ORDER BY display_name
            """)
            results = cursor.fetchall()
            conn.close()

            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "display_name": row[2],
                    "description": row[3],
                    "question_count": row[4],
                }
                for row in results
            ]

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _get_categories
        )

    # Question Management
    async def add_question(
        self,
        category_name: str,
        question_text: str,
        answer_text: str,
        difficulty: int = 1,
        source: str = "manual",
        external_id: Optional[str] = None,
    ) -> Optional[int]:
        """Add a new trivia question"""

        def _add_question():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                # Get category ID
                cursor.execute(
                    "SELECT id FROM trivia_categories WHERE name = ?", (category_name,)
                )
                category_result = cursor.fetchone()
                if not category_result:
                    # Create category if it doesn't exist
                    cursor.execute(
                        """
                        INSERT INTO trivia_categories (name, display_name)
                        VALUES (?, ?)
                    """,
                        (category_name, category_name),
                    )
                    category_id = cursor.lastrowid
                else:
                    category_id = category_result[0]

                # Insert question
                cursor.execute(
                    """
                    INSERT INTO trivia_questions
                    (category_id, question_text, answer_text, difficulty, source, external_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        category_id,
                        question_text,
                        answer_text,
                        difficulty,
                        source,
                        external_id,
                    ),
                )

                question_id = cursor.lastrowid

                # Update category question count
                cursor.execute(
                    """
                    UPDATE trivia_categories
                    SET question_count = (
                        SELECT COUNT(*) FROM trivia_questions
                        WHERE category_id = ? AND is_active = 1
                    )
                    WHERE id = ?
                """,
                    (category_id, category_id),
                )

                conn.commit()
                return question_id
            except Exception as e:
                logger.error(f"Error adding question: {e}")
                conn.rollback()
                return None
            finally:
                conn.close()

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _add_question
        )

    async def add_or_update_question(
        self,
        category_name: str,
        question_text: str,
        answer_text: str,
        difficulty: int = 1,
        source: str = "manual",
        external_id: Optional[str] = None,
    ) -> Optional[int]:
        """Add a new question or update existing one (including UNKNOWN_ANSWER entries)"""

        def _add_or_update_question():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                # Get category ID
                cursor.execute(
                    "SELECT id FROM trivia_categories WHERE name = ?", (category_name,)
                )
                category_result = cursor.fetchone()
                if not category_result:
                    # Create category if it doesn't exist
                    cursor.execute(
                        """
                        INSERT INTO trivia_categories (name, display_name)
                        VALUES (?, ?)
                    """,
                        (category_name, category_name),
                    )
                    category_id = cursor.lastrowid
                else:
                    category_id = category_result[0]

                # Check if question exists (including UNKNOWN_ANSWER entries)
                cursor.execute(
                    """
                    SELECT id FROM trivia_questions
                    WHERE category_id = ? AND question_text = ? AND is_active = 1
                """,
                    (category_id, question_text),
                )
                existing_question = cursor.fetchone()

                if existing_question:
                    # Update existing question
                    cursor.execute(
                        """
                        UPDATE trivia_questions
                        SET answer_text = ?, source = ?, last_used = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """,
                        (answer_text, source, existing_question[0]),
                    )
                    question_id = existing_question[0]
                    logger.info(
                        f"Updated existing trivia question: {question_text[:50]}..."
                    )
                else:
                    # Insert new question
                    cursor.execute(
                        """
                        INSERT INTO trivia_questions
                        (category_id, question_text, answer_text, difficulty, source, external_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            category_id,
                            question_text,
                            answer_text,
                            difficulty,
                            source,
                            external_id,
                        ),
                    )
                    question_id = cursor.lastrowid
                    logger.info(f"Added new trivia question: {question_text[:50]}...")

                # Update category question count
                cursor.execute(
                    """
                    UPDATE trivia_categories
                    SET question_count = (
                        SELECT COUNT(*) FROM trivia_questions
                        WHERE category_id = ? AND is_active = 1
                    )
                    WHERE id = ?
                """,
                    (category_id, category_id),
                )

                conn.commit()
                return question_id
            except Exception as e:
                logger.error(f"Error adding/updating question: {e}")
                conn.rollback()
                return None
            finally:
                conn.close()

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _add_or_update_question
        )

    async def find_answer(
        self, category_name: str, question_text: str
    ) -> Optional[str]:
        """Find answer for a specific question in a category"""

        def _find_answer():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Try exact match first
            cursor.execute(
                """
                SELECT q.answer_text FROM trivia_questions q
                JOIN trivia_categories c ON q.category_id = c.id
                WHERE c.name = ? AND q.question_text = ? AND q.is_active = 1
            """,
                (category_name, question_text),
            )
            result = cursor.fetchone()

            if result:
                # Update usage statistics
                question_id = None  # We'll need another query for this
                cursor.execute(
                    """
                    SELECT q.id FROM trivia_questions q
                    JOIN trivia_categories c ON q.category_id = c.id
                    WHERE c.name = ? AND q.question_text = ? AND q.is_active = 1
                """,
                    (category_name, question_text),
                )
                q_result = cursor.fetchone()
                if q_result:
                    question_id = q_result[0]
                    cursor.execute(
                        """
                        UPDATE trivia_questions
                        SET times_asked = times_asked + 1, last_used = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """,
                        (question_id,),
                    )

                conn.commit()
                conn.close()
                return result[0]

            # Try fuzzy match (contains)
            cursor.execute(
                """
                SELECT q.answer_text FROM trivia_questions q
                JOIN trivia_categories c ON q.category_id = c.id
                WHERE c.name = ? AND q.question_text LIKE ? AND q.is_active = 1
                LIMIT 1
            """,
                (category_name, f"%{question_text}%"),
            )
            result = cursor.fetchone()

            conn.close()
            return result[0] if result else None

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _find_answer
        )

    async def get_questions_by_category(
        self, category_name: str, limit: int = 100
    ) -> List[Dict]:
        """Get questions for a specific category"""

        def _get_questions():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT q.id, q.question_text, q.answer_text, q.difficulty,
                       q.times_asked, q.times_correct, q.created_at
                FROM trivia_questions q
                JOIN trivia_categories c ON q.category_id = c.id
                WHERE c.name = ? AND q.is_active = 1
                ORDER BY q.created_at DESC
                LIMIT ?
            """,
                (category_name, limit),
            )
            results = cursor.fetchall()
            conn.close()

            return [
                {
                    "id": row[0],
                    "question_text": row[1],
                    "answer_text": row[2],
                    "difficulty": row[3],
                    "times_asked": row[4],
                    "times_correct": row[5],
                    "created_at": row[6],
                }
                for row in results
            ]

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _get_questions
        )

    # Statistics
    async def record_trivia_attempt(
        self,
        question_id: int,
        channel_id: Optional[str] = None,
        guild_id: Optional[str] = None,
        answered: bool = True,
        response_time_ms: Optional[int] = None,
    ):
        """Record a trivia attempt for statistics"""

        def _record_attempt():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trivia_stats
                (question_id, channel_id, guild_id, answered, response_time_ms)
                VALUES (?, ?, ?, ?, ?)
            """,
                (question_id, channel_id, guild_id, answered, response_time_ms),
            )

            # Update question statistics
            if answered:
                cursor.execute(
                    """
                    UPDATE trivia_questions
                    SET times_correct = times_correct + 1
                    WHERE id = ?
                """,
                    (question_id,),
                )

            conn.commit()
            conn.close()

        await asyncio.get_running_loop().run_in_executor(self._executor, _record_attempt)

    async def get_category_stats(self, category_name: str) -> Dict:
        """Get statistics for a specific category"""

        def _get_stats():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(q.id) as total_questions,
                    SUM(q.times_asked) as total_attempts,
                    SUM(q.times_correct) as total_correct,
                    AVG(CASE WHEN q.times_asked > 0 THEN
                        (q.times_correct * 100.0 / q.times_asked) ELSE 0 END) as accuracy_rate
                FROM trivia_questions q
                JOIN trivia_categories c ON q.category_id = c.id
                WHERE c.name = ? AND q.is_active = 1
            """,
                (category_name,),
            )
            result = cursor.fetchone()
            conn.close()

            if result and result[0] > 0:
                return {
                    "total_questions": result[0],
                    "total_attempts": result[1] or 0,
                    "total_correct": result[2] or 0,
                    "accuracy_rate": round(result[3] or 0, 2),
                }
            return {
                "total_questions": 0,
                "total_attempts": 0,
                "total_correct": 0,
                "accuracy_rate": 0,
            }

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _get_stats
        )

    # Cache Management
    async def cache_category_questions(
        self, category_name: str, questions: List[Dict], ttl_hours: int = 1
    ):
        """Cache questions for a category"""

        def _cache_questions():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            expires_at = datetime.datetime.now() + datetime.timedelta(hours=ttl_hours)
            cursor.execute(
                """
                INSERT OR REPLACE INTO trivia_cache
                (category_name, questions_json, expires_at)
                VALUES (?, ?, ?)
            """,
                (category_name, json.dumps(questions), expires_at),
            )
            conn.commit()
            conn.close()

        await asyncio.get_running_loop().run_in_executor(self._executor, _cache_questions)

    async def get_cached_questions(self, category_name: str) -> Optional[List[Dict]]:
        """Get cached questions for a category"""

        def _get_cached():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT questions_json, expires_at FROM trivia_cache
                WHERE category_name = ? AND expires_at > CURRENT_TIMESTAMP
            """,
                (category_name,),
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                try:
                    return json.loads(result[0])
                except json.JSONDecodeError:
                    return None
            return None

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _get_cached
        )

    # Bulk Operations
    async def bulk_import_questions(self, questions_data: List[Dict]) -> int:
        """Import multiple questions in bulk"""

        def _bulk_import():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            imported_count = 0

            try:
                for question_data in questions_data:
                    category_name = question_data.get("category")
                    question_text = question_data.get("question")
                    answer_text = question_data.get("answer")
                    difficulty = question_data.get("difficulty", 1)
                    source = question_data.get("source", "bulk_import")
                    external_id = question_data.get("external_id")

                    if not all([category_name, question_text, answer_text]):
                        continue

                    # Get or create category
                    cursor.execute(
                        "SELECT id FROM trivia_categories WHERE name = ?",
                        (category_name,),
                    )
                    category_result = cursor.fetchone()
                    if not category_result:
                        cursor.execute(
                            """
                            INSERT INTO trivia_categories (name, display_name)
                            VALUES (?, ?)
                        """,
                            (category_name, category_name),
                        )
                        category_id = cursor.lastrowid
                    else:
                        category_id = category_result[0]

                    # Insert question (avoid duplicates)
                    cursor.execute(
                        """
                        SELECT id FROM trivia_questions
                        WHERE category_id = ? AND question_text = ?
                    """,
                        (category_id, question_text),
                    )
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            INSERT INTO trivia_questions
                            (category_id, question_text, answer_text, difficulty, source, external_id)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """,
                            (
                                category_id,
                                question_text,
                                answer_text,
                                difficulty,
                                source,
                                external_id,
                            ),
                        )
                        imported_count += 1

                # Update all category counts
                cursor.execute("""
                    UPDATE trivia_categories
                    SET question_count = (
                        SELECT COUNT(*) FROM trivia_questions
                        WHERE category_id = trivia_categories.id AND is_active = 1
                    )
                """)

                conn.commit()
                return imported_count
            except Exception as e:
                logger.error(f"Error in bulk import: {e}")
                conn.rollback()
                return imported_count
            finally:
                conn.close()

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _bulk_import
        )

    async def search_all_questions(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for questions across all categories"""

        def _search():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Search in question text and answer text
            search_pattern = f"%{query}%"
            cursor.execute(
                """
                SELECT q.id, q.question_text, q.answer_text, q.difficulty,
                       q.times_asked, q.times_correct, q.created_at,
                       c.display_name as category_name
                FROM trivia_questions q
                JOIN trivia_categories c ON q.category_id = c.id
                WHERE q.is_active = 1
                AND (q.question_text LIKE ? OR q.answer_text LIKE ?)
                ORDER BY q.times_asked DESC
                LIMIT ?
            """,
                (search_pattern, search_pattern, limit),
            )

            results = cursor.fetchall()
            conn.close()

            return [
                {
                    "id": row[0],
                    "question_text": row[1],
                    "answer_text": row[2],
                    "difficulty": row[3],
                    "times_asked": row[4],
                    "times_correct": row[5],
                    "created_at": row[6],
                    "category_name": row[7],
                }
                for row in results
            ]

        return await asyncio.get_running_loop().run_in_executor(self._executor, _search)

    async def get_database_stats(self) -> Dict:
        """Get overall database statistics"""

        def _get_stats():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Category stats
            cursor.execute("SELECT COUNT(*) FROM trivia_categories WHERE is_active = 1")
            total_categories = cursor.fetchone()[0]

            # Question stats
            cursor.execute("SELECT COUNT(*) FROM trivia_questions WHERE is_active = 1")
            total_questions = cursor.fetchone()[0]

            # Usage stats
            cursor.execute("SELECT COUNT(*) FROM trivia_stats")
            total_attempts = cursor.fetchone()[0]

            # Most popular categories
            cursor.execute("""
                SELECT c.display_name, COUNT(q.id) as question_count
                FROM trivia_categories c
                LEFT JOIN trivia_questions q ON c.id = q.category_id AND q.is_active = 1
                WHERE c.is_active = 1
                GROUP BY c.id, c.display_name
                ORDER BY question_count DESC
                LIMIT 5
            """)
            top_categories = cursor.fetchall()

            conn.close()

            return {
                "total_categories": total_categories,
                "total_questions": total_questions,
                "total_attempts": total_attempts,
                "top_categories": [
                    {"name": row[0], "count": row[1]} for row in top_categories
                ],
            }

        return await asyncio.get_running_loop().run_in_executor(
            self._executor, _get_stats
        )

    def close(self):
        """Close database connections and cleanup"""
        self._executor.shutdown(wait=True)
        logger.info("Trivia database connections closed")


# Global instance for easy access
trivia_db = TriviaDatabase()

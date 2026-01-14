import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

import aiohttp

from data.trivia_database import trivia_db
from utils.logging_config import get_logger

logger = get_logger(__name__)


class TriviaManager:
    """Enhanced trivia manager with local database and external source fallback"""

    def __init__(self):
        self.db = trivia_db
        self.session: Optional[aiohttp.ClientSession] = None
        self.github_base_url = (
            "https://raw.githubusercontent.com/QuartzWarrior/OTDB-Source/main"
        )
        self.cache_ttl = 3600  # 1 hour cache for external sources

        # Common category mappings for better matching
        self.category_mappings = {
            "Entertainment: Music": "Entertainment: Music",
            "Entertainment: Japanese Anime & Manga": "Entertainment: Japanese Anime & Manga",
            "Entertainment: Video Games": "Entertainment: Video Games",
            "Entertainment: Cartoon & Animations": "Entertainment: Cartoon & Animations",
            "Entertainment: Film": "Entertainment: Film",
            "Entertainment: Television": "Entertainment: Television",
            "Entertainment: Books": "Entertainment: Books",
            "Science & Nature": "Science & Nature",
            "Science: Computers": "Science: Computers",
            "Geography": "Geography",
            "History": "History",
            "General Knowledge": "General Knowledge",
            "Art": "Art",
            "Animals": "Animals",
            "Celebrities": "Celebrities",
            "Mythology": "Mythology",
            "Politics": "Politics",
        }

    async def initialize(self):
        """Initialize trivia manager"""
        self.session = aiohttp.ClientSession()

        # Pre-populate common categories if they don't exist
        await self._ensure_common_categories()

        # Refresh cache for categories that have questions but no cache
        await self._refresh_cache_if_needed()

        logger.info("Trivia manager initialized")

    async def close(self):
        """Close the trivia manager"""
        if self.session:
            await self.session.close()
        self.db.close()
        logger.info("Trivia manager closed")

    async def _ensure_common_categories(self):
        """Ensure common trivia categories exist in database"""
        common_categories = [
            ("Entertainment: Music", "Entertainment Music questions"),
            ("Entertainment: Japanese Anime & Manga", "Anime and Manga trivia"),
            ("Entertainment: Video Games", "Video game trivia questions"),
            ("Entertainment: Cartoon & Animations", "Cartoon and animation questions"),
            ("Entertainment: Film", "Movie and film trivia questions"),
            ("Entertainment: Television", "TV show trivia questions"),
            ("Entertainment: Books", "Book and literature trivia questions"),
            ("Science & Nature", "Science and nature trivia questions"),
            ("Science: Computers", "Computer science and technology questions"),
            ("Geography", "Geography and world places trivia questions"),
            ("History", "Historical events and figures trivia questions"),
            ("General Knowledge", "General knowledge and mixed trivia questions"),
            ("Art", "Art history and artists trivia questions"),
            ("Animals", "Animal facts and wildlife trivia questions"),
            ("Celebrities", "Celebrity and famous people trivia questions"),
            ("Mythology", "Mythology and legends trivia questions"),
            ("Politics", "Political trivia questions"),
        ]

        for name, description in common_categories:
            await self.db.add_category(name, name, description)

    async def _refresh_cache_if_needed(self):
        """Refresh cache for categories that have questions but no cache"""
        try:
            categories = await self.db.get_all_categories()

            for cat in categories:
                if cat["question_count"] > 0:
                    # Check if cache exists and is valid
                    cached = await self.db.get_cached_questions(cat["name"])
                    if not cached or len(cached) == 0:
                        # Refresh cache
                        questions = await self.db.get_questions_by_category(
                            cat["name"], 100
                        )
                        await self.db.cache_category_questions(
                            cat["name"], questions, ttl_hours=168
                        )
                        logger.info(f"Auto-refreshed cache for {cat['name']}")

        except Exception as e:
            logger.error(f"Error refreshing cache: {e}")

    def _normalize_category_name(self, category: str) -> str:
        """Normalize category name for consistent storage"""
        # Strip whitespace and normalize spacing
        normalized = " ".join(category.split())

        # Apply mappings if available
        return self.category_mappings.get(normalized, normalized)

    async def find_trivia_answer(self, category: str, question: str) -> Optional[str]:
        """
        Find answer for a trivia question with multiple fallback strategies:
        1. Local database lookup
        2. Cached external source
        3. Live external source fetch
        """
        start_time = asyncio.get_running_loop().time()

        try:
            # Use a shorter timeout for the entire operation to prevent blocking
            timeout_task = asyncio.wait_for(
                self._find_trivia_answer_impl(category, question),
                timeout=3.0,  # 3 second total timeout for all operations
            )
            return await timeout_task

        except asyncio.TimeoutError:
            logger.warning(f"Trivia lookup timed out for category: {category}")
            return None
        except Exception as e:
            logger.error(f"Error finding trivia answer: {e}")
            return None
        finally:
            # Record attempt statistics
            elapsed_ms = int((asyncio.get_running_loop().time() - start_time) * 1000)
            # We'll record this when we have question_id from successful lookup

    async def _find_trivia_answer_impl(
        self, category: str, question: str
    ) -> Optional[str]:
        """Implementation of find_trivia_answer without timeout wrapper"""
        # Strategy 1: Local database lookup
        answer = await self.db.find_answer(category, question)
        if answer:
            logger.info(f"Found answer in local database for category: {category}")
            return answer

        # Strategy 2: Try cached external source
        cached_questions = await self.db.get_cached_questions(category)
        if cached_questions:
            answer = self._search_in_cached_questions(cached_questions, question)
            if answer:
                logger.info(f"Found answer in cache for category: {category}")
                # Store in local database for future use
                await self.db.add_question(category, question, answer, source="cache")
                return answer

        # Strategy 3: Fetch from external source
        answer = await self._fetch_from_external_source(category, question)
        if answer:
            logger.info(f"Found answer from external source for category: {category}")
            # Store in local database and cache
            await self.db.add_question(category, question, answer, source="external")
            return answer

        logger.warning(f"No answer found for question in category: {category}")

        # Record unknown question for potential future learning with timeout to prevent blocking
        await self.record_unknown_question_with_timeout(category, question)

        return None

    def _search_in_cached_questions(
        self, questions: List[Dict], question_text: str
    ) -> Optional[str]:
        """Search for answer in cached questions list"""
        question_clean = question_text.strip().lower()

        for q in questions:
            cached_question = q.get("question", "").strip().lower()
            if (
                cached_question == question_clean
                or question_text in cached_question
                or cached_question in question_text
            ):
                return q.get("answer")

        return None

    async def _fetch_from_external_source(
        self, category: str, question: str
    ) -> Optional[str]:
        """Fetch trivia data from external GitHub source"""
        if not self.session:
            return None

        try:
            # Try normalized category name
            normalized_category = self._normalize_category_name(category)

            # Try original category first, then normalized
            for cat_to_try in [category, normalized_category]:
                url = f"{self.github_base_url}/{quote(cat_to_try)}.csv"

                try:
                    # Use a shorter timeout for individual requests
                    async with self.session.get(
                        url, timeout=aiohttp.ClientTimeout(total=1.5)
                    ) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            questions = self._parse_csv_content(content)

                            # Cache the questions for future use
                            await self.db.cache_category_questions(category, questions)

                            # Search for the specific question
                            answer = self._search_in_cached_questions(
                                questions, question
                            )
                            if answer:
                                return answer

                except asyncio.TimeoutError:
                    logger.debug(f"External source timeout for category: {cat_to_try}")
                    continue
                except Exception as e:
                    logger.debug(f"Failed to fetch from {url}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"Error fetching from external source: {e}")
            return None

    def _parse_csv_content(self, content: str) -> List[Dict]:
        """Parse CSV content into question-answer pairs"""
        questions = []

        try:
            lines = content.strip().splitlines()
            for line in lines:
                if "," in line:
                    # Split only on first comma to handle answers with commas
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        question = unquote(parts[0].strip())
                        answer = unquote(parts[1].strip())

                        if question and answer:
                            questions.append({"question": question, "answer": answer})
        except Exception as e:
            logger.error(f"Error parsing CSV content: {e}")

        return questions

    async def sync_category_from_external(self, category: str) -> Tuple[int, int]:
        """
        Sync a category from external source
        Returns: (questions_found, questions_imported)
        """
        if not self.session:
            return 0, 0

        try:
            normalized_category = self._normalize_category_name(category)

            for cat_to_try in [category, normalized_category]:
                url = f"{self.github_base_url}/{quote(cat_to_try)}.csv"

                try:
                    async with self.session.get(
                        url, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            questions = self._parse_csv_content(content)

                            # Convert to bulk import format
                            import_data = []
                            for q in questions:
                                import_data.append(
                                    {
                                        "category": category,
                                        "question": q["question"],
                                        "answer": q["answer"],
                                        "source": "github_sync",
                                        "difficulty": 1,
                                    }
                                )

                            # Bulk import to database
                            imported_count = await self.db.bulk_import_questions(
                                import_data
                            )

                            # Cache for performance
                            await self.db.cache_category_questions(category, questions)

                            logger.info(
                                f"Synced {imported_count} questions for category: {category}"
                            )
                            return len(questions), imported_count

                except Exception as e:
                    logger.debug(f"Failed to sync {cat_to_try}: {e}")
                    continue

            return 0, 0

        except Exception as e:
            logger.error(f"Error syncing category {category}: {e}")
            return 0, 0

    async def get_category_statistics(self, category: str) -> Dict:
        """Get comprehensive statistics for a category"""
        try:
            # Get database stats
            db_stats = await self.db.get_category_stats(category)

            # Get category info
            category_info = await self.db.get_category_by_name(category)

            # Check if we have cached data
            cached_questions = await self.db.get_cached_questions(category)
            cache_status = "fresh" if cached_questions else "empty"

            return {
                "category_name": category,
                "category_info": category_info,
                "database_stats": db_stats,
                "cache_status": cache_status,
                "cached_questions_count": len(cached_questions)
                if cached_questions
                else 0,
                "last_sync": category_info.get("updated_at") if category_info else None,
            }

        except Exception as e:
            logger.error(f"Error getting category statistics: {e}")
            return {"category_name": category, "error": str(e)}

    async def list_available_categories(self) -> List[Dict]:
        """List all available trivia categories with statistics"""
        try:
            categories = await self.db.get_all_categories()

            # Add statistics for each category
            for cat in categories:
                stats = await self.db.get_category_stats(cat["name"])
                cat.update(stats)

                # Check cache status
                cached = await self.db.get_cached_questions(cat["name"])
                cat["cached_questions"] = len(cached) if cached else 0
                cat["cache_status"] = "fresh" if cached and len(cached) > 0 else "empty"

            return categories

        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            return []

    async def search_questions(
        self, query: str, category: Optional[str] = None, limit: int = 20
    ) -> List[Dict]:
        """Search for questions matching a query"""
        try:
            if category:
                # Search within specific category
                questions = await self.db.get_questions_by_category(category, limit)
                # Filter by query within this category
                if query:
                    query_lower = query.lower()
                    questions = [
                        q
                        for q in questions
                        if query_lower in q["question_text"].lower()
                        or query_lower in q["answer_text"].lower()
                    ]
            else:
                # Search across all categories using database search function
                questions = await self.db.search_all_questions(query, limit)

            return questions[:limit]

        except Exception as e:
            logger.error(f"Error searching questions: {e}")
            return []

    async def record_successful_answer(
        self,
        category: str,
        question: str,
        answer: str,
        channel_id: Optional[str] = None,
        guild_id: Optional[str] = None,
    ):
        """Record a successful trivia answer for learning and statistics"""
        try:
            # Check if question already exists in database
            existing_answer = await self.db.find_answer(category, question)

            if not existing_answer or existing_answer == "UNKNOWN_ANSWER":
                # Add new question or update unknown answer
                question_id = await self.db.add_or_update_question(
                    category,
                    question,
                    answer,
                    difficulty=1,
                    source="trivia_drop_success",
                )

                if question_id:
                    logger.info(
                        f"Learned new trivia question from successful drop: {category}"
                    )

                    # Record the successful attempt
                    await self.db.record_trivia_attempt(
                        question_id=question_id,
                        channel_id=channel_id or "unknown",
                        guild_id=guild_id or "unknown",
                        answered=True,
                        response_time_ms=None,
                    )
            else:
                # Question exists with known answer, just update usage statistics
                # Find question ID to record attempt
                questions = await self.db.get_questions_by_category(
                    category, limit=1000
                )
                for q in questions:
                    if q["question_text"] == question:
                        await self.db.record_trivia_attempt(
                            question_id=q["id"],
                            channel_id=channel_id or "unknown",
                            guild_id=guild_id or "unknown",
                            answered=True,
                            response_time_ms=None,
                        )
                        break

        except Exception as e:
            logger.error(f"Error recording successful trivia answer: {e}")

    async def record_unknown_question(
        self,
        category: str,
        question: str,
        channel_id: Optional[str] = None,
        guild_id: Optional[str] = None,
    ):
        """Record an unknown trivia question for future reference and learning"""
        try:
            # Add to database with unknown answer marker
            question_id = await self.db.add_question(
                category,
                question,
                "UNKNOWN_ANSWER",
                difficulty=1,
                source="unknown_trivia_drop",
            )

            if question_id:
                logger.info(
                    f"Recorded unknown trivia question for future learning: {category}"
                )

                # Record the failed attempt
                await self.db.record_trivia_attempt(
                    question_id=question_id,
                    channel_id=channel_id or "unknown",
                    guild_id=guild_id or "unknown",
                    answered=False,
                    response_time_ms=None,
                )

        except Exception as e:
            logger.error(f"Error recording unknown trivia question: {e}")

    async def record_unknown_question_with_timeout(
        self,
        category: str,
        question: str,
        channel_id: Optional[str] = None,
        guild_id: Optional[str] = None,
    ):
        """Record an unknown trivia question with timeout to prevent blocking"""
        try:
            # Add timeout to prevent long-running operations
            await asyncio.wait_for(
                self.record_unknown_question(category, question, channel_id, guild_id),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Recording unknown trivia question timed out: {category}")
        except Exception as e:
            logger.error(f"Error in record_unknown_question_with_timeout: {e}")

    async def get_database_overview(self) -> Dict:
        """Get overall database statistics and health"""
        try:
            stats = await self.db.get_database_stats()

            # Add health indicators
            total_questions = stats.get("total_questions", 0)
            total_categories = stats.get("total_categories", 0)

            health_score = 0
            if total_categories >= 5:
                health_score += 30
            if total_questions >= 100:
                health_score += 40
            if stats.get("total_attempts", 0) > 0:
                health_score += 30

            stats["health_score"] = min(health_score, 100)
            stats["health_status"] = (
                "excellent"
                if health_score >= 80
                else "good"
                if health_score >= 60
                else "fair"
                if health_score >= 40
                else "poor"
            )

            return stats

        except Exception as e:
            logger.error(f"Error getting database overview: {e}")
            return {"error": str(e), "health_status": "error"}


# Global trivia manager instance
trivia_manager = TriviaManager()

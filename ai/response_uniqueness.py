"""
Response Uniqueness System

This module provides advanced repetition prevention for LLM responses.
It includes:
- Content hashing for exact duplicate detection
- Semantic similarity detection using Jaccard similarity
- Time-based expiration of old responses
- User-specific response tracking
- Repetitive pattern detection
- Enhanced system prompt generation
"""

import hashlib
import json
import re
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

import config
from utils.logging_config import setup_logging

logger = setup_logging(__name__)


class ResponseUniquenessManager:
    """
    Manages response uniqueness to prevent LLM repetition.
    """

    def __init__(self):
        # User-specific response history (deque for efficient append/pop)
        self.user_responses: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))

        # Content hashes for fast duplicate detection
        self.response_hashes: Dict[str, Set[str]] = defaultdict(set)

        # Track last activity time per user for TTL cleanup
        self.user_last_active: Dict[str, float] = {}

        # GLOBAL response tracking (across ALL users) - prevents same response to different users
        self.global_responses: deque = deque(maxlen=30)  # Last 30 responses globally
        self.global_hashes: Set[str] = set()

        # Time-based cleanup tracking
        self.last_cleanup = time.time()

        # Settings
        self.cleanup_interval = 300  # 5 minutes
        self.user_ttl = 3600  # 1 hour - remove inactive user data after this
        self.similarity_threshold = 0.70  # 70% word overlap threshold (was 80%)

    def _hash_content(self, content: str) -> str:
        """Generate SHA-256 hash of content for exact duplicate detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for similarity comparison."""
        # Convert to lowercase and remove extra whitespace
        text = re.sub(r"\s+", " ", text.lower().strip())
        # Remove punctuation for word-level comparison
        text = re.sub(r"[^\w\s]", "", text)
        return text

    def _get_jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate Jaccard similarity between two texts.
        This gives a measure of word overlap normalized by total unique words.
        """
        words1 = set(self._clean_text(text1).split())
        words2 = set(self._clean_text(text2).split())

        # Return 0 if either text is empty
        if not words1 or not words2:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    def _detect_repetitive_patterns(self, text: str) -> List[str]:
        """
        Detect internal repetition patterns within a single response.
        Returns a list of detected patterns.
        
        Only flags truly problematic repetition (same word 4+ times, 
        or phrases repeated 3+ times), not normal word reuse.
        """
        patterns = []
        cleaned_text = self._clean_text(text)
        words = cleaned_text.split()

        # Skip analysis for short texts (need enough words for meaningful analysis)
        if len(words) < 15:
            return patterns

        # Common words that naturally repeat in conversation - don't flag these
        common_words = {
            "just", "want", "know", "think", "like", "really", "actually",
            "gonna", "going", "would", "could", "should", "some", "that",
            "this", "what", "have", "been", "being", "with", "from", "about",
            "fuck", "shit", "damn", "hell", "yeah", "okay", "well", "right",
            "thing", "things", "something", "anything", "nothing", "everything",
        }

        # Word repetition detection - only flag excessive repetition (4+ times)
        word_count = {}
        for word in words:
            if len(word) > 4:  # Only count words longer than 4 characters
                word_count[word] = word_count.get(word, 0) + 1

        # Find words repeated 4+ times (excluding common words)
        repeated_words = [
            word for word, count in word_count.items() 
            if count >= 4 and word not in common_words
        ]
        if repeated_words:
            patterns.append(f"Repeated words: {', '.join(repeated_words)}")

        # Phrase repetition detection (2-3 word phrases repeated 3+ times)
        for phrase_length in [2, 3]:
            if len(words) < phrase_length * 3:  # Need enough words for meaningful phrase analysis
                continue

            phrase_count = {}
            for i in range(len(words) - phrase_length + 1):
                phrase = " ".join(words[i : i + phrase_length])
                phrase_count[phrase] = phrase_count.get(phrase, 0) + 1

            # Find phrases repeated 3+ times (was 2+, too sensitive)
            repeated_phrases = [
                phrase
                for phrase, count in phrase_count.items()
                if count >= 3 and len(phrase) > 8  # Require longer phrases
            ]

            if repeated_phrases:
                patterns.append(
                    f"Repeated {phrase_length}-word phrases: {', '.join(repeated_phrases[:3])}"
                )

        return patterns

    def _is_exact_duplicate(self, user_id: str, content: str) -> bool:
        """Check if content is an exact duplicate of a recent response."""
        content_hash = self._hash_content(content)
        user_hashes = self.response_hashes.get(user_id, set())

        logger.debug(
            f"   Checking against {len(user_hashes)} stored hashes for user {user_id}"
        )

        # Check if this exact content hash exists in user's recent responses
        if content_hash in user_hashes:
            logger.debug(f"   ✅ Hash match found - exact duplicate for this user!")
            return True

        # Also check GLOBAL hashes (prevents same response to different users)
        if content_hash in self.global_hashes:
            logger.debug(f"   ✅ Hash match found in GLOBAL responses - duplicate across users!")
            return True

        logger.debug("   ✅ No hash match found (user or global)")
        return False

    def _is_too_similar(self, user_id: str, content: str) -> Tuple[bool, float]:
        """
        Check if content is too similar to recent responses.
        Returns a tuple of (is_similar, similarity_score).
        
        Checks both user-specific history AND global history.
        Also checks for matching openings (same first N words).
        """
        user_history = list(self.user_responses.get(user_id, []))

        # Check against user's most recent 5 responses (increased from 3)
        recent_user_responses = user_history[-5:]
        
        # Also check against global recent responses (last 15 from all users)
        recent_global_responses = list(self.global_responses)[-15:]
        
        # Combine for checking
        all_recent = recent_user_responses + recent_global_responses

        logger.debug(
            f"   Comparing against {len(recent_user_responses)} user responses + "
            f"{len(recent_global_responses)} global responses "
            f"(threshold: {self.similarity_threshold:.0%})"
        )

        # Get first 15 words of new content for opening matching
        new_words = self._clean_text(content).split()[:15]
        new_opening = " ".join(new_words)

        for idx, recent_text in enumerate(all_recent):
            # OPENING CHECK: If first 10+ words match, it's repetitive
            recent_words = self._clean_text(recent_text).split()[:15]
            recent_opening = " ".join(recent_words)
            
            # Count matching words at the start
            matching_words = 0
            for i, (w1, w2) in enumerate(zip(new_words, recent_words)):
                if w1 == w2:
                    matching_words += 1
                else:
                    break
            
            # If 8+ consecutive opening words match, it's too similar
            if matching_words >= 8:
                logger.debug(
                    f"   ✅ Opening match! First {matching_words} words identical"
                )
                return True, 0.90  # Treat as 90% similar
            
            # Full similarity check
            similarity = self._get_jaccard_similarity(content, recent_text)
            source = "user" if idx < len(recent_user_responses) else "global"
            if similarity >= self.similarity_threshold:
                logger.debug(
                    f"   ✅ {source.title()} similarity {similarity:.2%} >= {self.similarity_threshold:.0%} - MATCH!"
                )
                return True, similarity

        logger.debug("   ✅ No response exceeded similarity threshold")
        return False, 0.0

    def has_internal_repetition(self, content: str) -> Tuple[bool, List[str]]:
        """
        Check if content has internal repetition patterns.
        Returns a tuple of (has_repetition, detected_patterns).
        """
        if len(content.strip().split()) < 3:  # Skip very short responses
            return False, []

        patterns = self._detect_repetitive_patterns(content)
        has_repetition = len(patterns) > 0

        if has_repetition:
            logger.debug(f"Internal repetition detected: {patterns}")

        return has_repetition, patterns

    def is_repetitive_response(self, user_id: str, content: str) -> Tuple[bool, str]:
        """
        Check if content is repetitive in any way.
        Returns a tuple of (is_repetitive, reason).
        """
        logger.debug(
            f"🔍 Checking for repetition for user {user_id}, "
            f"content length: {len(content)}, preview: {repr(content[:60])}"
        )

        # Show user's current history
        user_history = list(self.user_responses.get(user_id, []))
        logger.debug(
            f"📊 User {user_id} currently has {len(user_history)} responses in history"
        )
        if user_history:
            logger.debug(
                f"   Recent history: {[repr(h[:40]) for h in user_history[-3:]]}"
            )

        # 1. Check for exact duplicates
        logger.debug("1️⃣ Checking for exact duplicates...")
        if self._is_exact_duplicate(user_id, content):
            logger.warning(f"🚨 EXACT DUPLICATE detected for user {user_id}")
            return True, "Exact duplicate of recent response"
        logger.debug("   ✅ No exact duplicate found")

        # 2. Check for high similarity
        logger.debug("2️⃣ Checking for high similarity...")
        is_similar, similarity_score = self._is_too_similar(user_id, content)
        logger.debug(
            f"   Similarity score: {similarity_score:.2%} (threshold: {self.similarity_threshold:.0%})"
        )
        if is_similar:
            logger.warning(
                f"🚨 HIGH SIMILARITY detected for user {user_id}: "
                f"{similarity_score:.1%} overlap"
            )
            return (
                True,
                f"Too similar ({similarity_score:.1%} word overlap) to recent response",
            )
        logger.debug("   ✅ No high similarity found")

        # 3. Internal repetition check DISABLED
        # This was flagging normal word usage within single responses.
        # We only care about detecting when the bot repeats previous responses,
        # not when words naturally repeat within a single message.
        logger.debug("3️⃣ Internal repetition check skipped (disabled)")

        logger.debug(f"✅ No repetition detected for user {user_id}")
        return False, ""

    def add_response(self, user_id: str, content: str):
        """
        Add a response to the user's history and track its hash.
        Also adds to GLOBAL tracking to prevent cross-user duplicates.
        This should be called after successfully sending a response.
        """
        # Log what we're storing
        logger.info(
            f"Storing response for user {user_id}: "
            f"length={len(content)}, preview={repr(content[:60])}"
        )

        # Track user activity for TTL cleanup
        self.user_last_active[user_id] = time.time()

        # Check current storage before adding
        before_count = len(self.user_responses.get(user_id, []))
        before_hash_count = len(self.response_hashes.get(user_id, set()))

        # Add to user's response history
        self.user_responses[user_id].append(content)

        # Track the content hash (user-specific)
        content_hash = self._hash_content(content)
        self.response_hashes[user_id].add(content_hash)

        # Also add to GLOBAL tracking
        self.global_responses.append(content)
        self.global_hashes.add(content_hash)
        
        # Keep global hashes bounded (max 50 to match roughly 2x global_responses)
        if len(self.global_hashes) > 50:
            # Remove oldest hashes by rehashing from current global_responses
            self.global_hashes = {self._hash_content(r) for r in self.global_responses}

        # Verify it was stored
        after_count = len(self.user_responses.get(user_id, []))
        after_hash_count = len(self.response_hashes.get(user_id, set()))

        logger.debug(
            f"   History: {before_count} → {after_count} responses, "
            f"Hashes: {before_hash_count} → {after_hash_count} hashes, "
            f"Global: {len(self.global_responses)} responses"
        )

        # Note: When deque is at maxlen, count won't increase (old items are evicted)
        # This is expected behavior, not a failure
        if after_count >= before_count:
            logger.debug(f"   ✅ Response stored successfully for user {user_id}")
        else:
            logger.warning(
                f"   ⚠️  Response storage FAILED for user {user_id} - count decreased unexpectedly"
            )

        # Periodically clean up old data
        self._cleanup_if_needed()

    def _cleanup_if_needed(self):
        """Clean up old data if cleanup interval has passed."""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        logger.debug("Performing response uniqueness cleanup")

        # TTL-based cleanup: remove data for users inactive beyond user_ttl
        stale_users = []
        for user_id, last_active in list(self.user_last_active.items()):
            if current_time - last_active > self.user_ttl:
                stale_users.append(user_id)

        for user_id in stale_users:
            # Remove stale user data
            if user_id in self.user_responses:
                del self.user_responses[user_id]
            if user_id in self.response_hashes:
                del self.response_hashes[user_id]
            del self.user_last_active[user_id]

        if stale_users:
            logger.debug(f"Cleaned up {len(stale_users)} inactive users")

        # Keep only recent hashes (corresponding to the 10 most recent responses)
        for user_id in list(self.response_hashes.keys()):
            user_response_count = len(self.user_responses.get(user_id, []))
            if user_response_count == 0:
                # Clean up users with no responses
                del self.response_hashes[user_id]
                if user_id in self.user_last_active:
                    del self.user_last_active[user_id]
                continue

            # Limit hashes to match response count
            user_hashes = self.response_hashes[user_id]
            if len(user_hashes) > user_response_count:
                # Keep only the most recent hashes
                # Convert to deque to match response history behavior
                recent_hashes = deque(
                    list(user_hashes)[-user_response_count:], maxlen=10
                )
                self.response_hashes[user_id] = set(recent_hashes)

        self.last_cleanup = current_time

    def enhance_system_prompt_base(self, base_prompt: str) -> str:
        """
        Add anti-repetition instructions to the base system prompt.
        This can be called during response generation.
        """
        anti_repetition_rules = """

**CRITICAL Anti-Repetition Directives:**
- You MUST provide a unique response every single time
- Vary your vocabulary, sentence structure, and opening phrases
- Never use the same greeting, transition, or closing twice in a row
- If you find yourself repeating words or phrases, STOP and rephrase completely
- Be creative and original in every response
- Each word choice should feel fresh and intentional"""

        return base_prompt + anti_repetition_rules

    def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics about a user's response history."""
        user_responses = self.user_responses.get(user_id, deque())
        user_hashes = self.response_hashes.get(user_id, set())

        return {
            "response_count": len(user_responses),
            "unique_hashes": len(user_hashes),
            "recent_responses": list(user_responses)[-3:],  # Last 3 responses
        }

    def get_avoid_list(self, user_id: str, limit: int = 5) -> List[str]:
        """
        Get a list of recent response snippets to explicitly avoid.
        Used to provide the AI with examples of what NOT to say.
        Returns first 100 chars of each recent response.
        """
        user_responses = list(self.user_responses.get(user_id, []))
        global_responses = list(self.global_responses)
        
        # Combine user + global, prioritizing user's recent
        all_responses = user_responses[-3:] + global_responses[-5:]
        
        # Deduplicate and get snippets
        seen = set()
        snippets = []
        for resp in all_responses:
            snippet = resp[:150].strip()
            if snippet and snippet not in seen:
                seen.add(snippet)
                snippets.append(snippet)
                if len(snippets) >= limit:
                    break
        
        return snippets


# Global instance for use across the application
response_uniqueness = ResponseUniquenessManager()

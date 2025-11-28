"""
Advanced Anti-Repetition System - Efficient and Invisible

This module provides a sophisticated, lightweight approach to preventing LLM repetition
that operates silently in the background without impacting response quality or user experience.
"""
import hashlib
import json
import re
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple, NamedTuple

import config
from utils.logging_config import setup_logging

logger = setup_logging(__name__)


class ResponseSignature(NamedTuple):
    """Compact representation of response content for fast comparison."""
    content_hash: str
    word_set: frozenset
    key_phrases: tuple
    length: int


class ConversationContext(NamedTuple):
    """Lightweight context for conversation-aware responses."""
    topic_keywords: frozenset
    sentiment: str
    complexity: float


class AdvancedAntiRepetitionManager:
    """
    Advanced anti-repetition system that is efficient and invisible to users.

    Key improvements:
    - Pre-computed signatures for O(1) duplicate detection
    - Semantic fingerprinting instead of naive similarity
    - Conversation context awareness
    - Adaptive thresholds based on user interaction patterns
    - Silent operation without fallback responses
    """

    def __init__(self):
        # User-specific response signatures (compact and fast)
        self.user_signatures: Dict[str, deque] = defaultdict(lambda: deque(maxlen=7))

        # Conversation context tracking
        self.conversation_contexts: Dict[str, ConversationContext] = {}

        # Adaptive user patterns
        self.user_patterns: Dict[str, Dict] = defaultdict(lambda: {
            'avg_response_length': 50,
            'preferred_vocabulary': set(),
            'interaction_frequency': 0,
            'last_interaction': 0
        })

        # Performance optimization
        self.signature_cache: Dict[str, ResponseSignature] = {}
        self.cleanup_interval = 600  # 10 minutes
        self.last_cleanup = time.time()

        # Adaptive thresholds
        self.base_similarity_threshold = 0.75
        self.context_boost_factor = 0.1

    def _create_signature(self, content: str) -> ResponseSignature:
        """
        Create a compact signature for fast content comparison.
        Pre-computes expensive operations for O(1) lookups.
        """
        # Check cache first
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        if content_hash in self.signature_cache:
            return self.signature_cache[content_hash]

        # Clean and normalize text
        cleaned = re.sub(r'\s+', ' ', content.lower().strip())
        words = frozenset(re.findall(r'\b\w+\b', cleaned))

        # Extract key phrases (2-3 word combinations)
        word_list = list(words)
        key_phrases = tuple()
        if len(word_list) >= 2:
            # Sample key phrases for efficiency (max 5)
            phrases = set()
            for i in range(min(5, len(word_list) - 1)):
                if i < len(word_list) - 1:
                    phrases.add(tuple(sorted(word_list[i:i+2])))
            key_phrases = tuple(list(phrases)[:5])

        signature = ResponseSignature(
            content_hash=content_hash,
            word_set=words,
            key_phrases=key_phrases,
            length=len(content.split())
        )

        # Cache for performance
        self.signature_cache[content_hash] = signature
        return signature

    def _update_conversation_context(self, user_id: str, content: str):
        """Update conversation context for semantic awareness."""
        # Simple sentiment analysis
        positive_words = {'good', 'great', 'awesome', 'nice', 'love', 'happy', 'excellent'}
        negative_words = {'bad', 'terrible', 'hate', 'awful', 'sad', 'angry', 'worst'}

        words = set(re.findall(r'\b\w+\b', content.lower()))

        if words & positive_words:
            sentiment = 'positive'
        elif words & negative_words:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        # Topic keywords (most frequent meaningful words)
        meaningful_words = {w for w in words if len(w) > 3}
        topic_keywords = frozenset(list(meaningful_words)[:10])  # Top 10

        # Complexity based on vocabulary diversity
        complexity = len(meaningful_words) / max(len(content.split()), 1)

        self.conversation_contexts[user_id] = ConversationContext(
            topic_keywords=topic_keywords,
            sentiment=sentiment,
            complexity=min(complexity, 1.0)
        )

    def _update_user_patterns(self, user_id: str, content: str):
        """Update adaptive user behavior patterns."""
        current_time = time.time()
        patterns = self.user_patterns[user_id]

        # Update response length average
        response_length = len(content.split())
        patterns['avg_response_length'] = (
            patterns['avg_response_length'] * 0.8 + response_length * 0.2
        )

        # Update preferred vocabulary
        words = set(re.findall(r'\b\w+\b', content.lower()))
        meaningful_words = {w for w in words if len(w) > 4}
        patterns['preferred_vocabulary'].update(meaningful_words)

        # Keep vocabulary manageable
        if len(patterns['preferred_vocabulary']) > 100:
            patterns['preferred_vocabulary'] = set(
                list(patterns['preferred_vocabulary'])[-100:]
            )

        # Update interaction frequency
        if patterns['last_interaction'] > 0:
            time_diff = current_time - patterns['last_interaction']
            patterns['interaction_frequency'] = (
                patterns['interaction_frequency'] * 0.9 + (1 / max(time_diff, 1)) * 0.1
            )

        patterns['last_interaction'] = current_time

    def _get_adaptive_threshold(self, user_id: str) -> float:
        """Calculate adaptive similarity threshold based on user patterns."""
        patterns = self.user_patterns[user_id]
        context = self.conversation_contexts.get(user_id)

        threshold = self.base_similarity_threshold

        # Adjust based on interaction frequency (more frequent = higher threshold)
        if patterns['interaction_frequency'] > 0.1:
            threshold += 0.05

        # Adjust based on conversation complexity
        if context and context.complexity > 0.7:
            threshold += 0.05

        # Adjust based on user's preferred vocabulary diversity
        vocab_diversity = len(patterns['preferred_vocabulary'])
        if vocab_diversity > 50:
            threshold += 0.03

        return min(threshold, 0.85)  # Cap at 85%

    def _calculate_semantic_similarity(self, sig1: ResponseSignature, sig2: ResponseSignature) -> float:
        """
        Calculate semantic similarity using pre-computed signatures.
        Much faster than re-computing Jaccard similarity each time.
        """
        # Word set intersection (pre-computed, so fast)
        word_intersection = len(sig1.word_set & sig2.word_set)
        word_union = len(sig1.word_set | sig2.word_set)
        word_similarity = word_intersection / word_union if word_union > 0 else 0

        # Key phrase similarity bonus
        phrase_bonus = 0
        if sig1.key_phrases and sig2.key_phrases:
            phrase_intersection = len(set(sig1.key_phrases) & set(sig2.key_phrases))
            phrase_bonus = phrase_intersection / max(len(sig1.key_phrases), len(sig2.key_phrases)) * 0.2

        # Length similarity (small bonus for similar length responses)
        length_diff = abs(sig1.length - sig2.length) / max(sig1.length, sig2.length, 1)
        length_bonus = (1 - length_diff) * 0.1

        return min(word_similarity + phrase_bonus + length_bonus, 1.0)

    def _has_conceptual_repetition(self, user_id: str, signature: ResponseSignature) -> Tuple[bool, str]:
        """
        Check for conceptual repetition using conversation context.
        More sophisticated than simple word overlap.
        """
        context = self.conversation_contexts.get(user_id)
        if not context:
            return False, ""

        # Check if we're repeating the same topic with similar sentiment
        recent_signatures = list(self.user_signatures[user_id])[-3:]
        for recent_sig in recent_signatures:
            # Topic overlap
            topic_overlap = len(context.topic_keywords & recent_sig.word_set) / max(len(context.topic_keywords), 1)

            # Same sentiment and high topic overlap might indicate conceptual repetition
            if topic_overlap > 0.4 and signature.length == recent_sig.length:
                similarity = self._calculate_semantic_similarity(signature, recent_sig)
                if similarity > 0.65:  # Lower threshold for conceptual repetition
                    return True, f"Conceptual repetition detected (topic overlap: {topic_overlap:.1%})"

        return False, ""

    def should_enhance_response(self, user_id: str, content: str) -> Tuple[bool, str, List[str]]:
        """
        Determine if a response needs enhancement for uniqueness.
        Returns (should_enhance, reason, suggestions).
        """
        # Skip very short responses
        if len(content.strip().split()) < 4:
            return False, "", []

        signature = self._create_signature(content)

        # Check exact duplicates (fast hash lookup)
        user_hashes = {sig.content_hash for sig in self.user_signatures[user_id]}
        if signature.content_hash in user_hashes:
            return True, "Exact content repetition", ["Vary phrasing completely", "Use different vocabulary"]

        # Check semantic similarity with adaptive threshold
        threshold = self._get_adaptive_threshold(user_id)
        recent_signatures = list(self.user_signatures[user_id])[-3:]  # Only check recent 3

        for recent_sig in recent_signatures:
            similarity = self._calculate_semantic_similarity(signature, recent_sig)
            if similarity >= threshold:
                return True, f"Semantic similarity ({similarity:.1%})", [
                    "Introduce new concepts", "Change sentence structure", "Use different examples"
                ]

        # Check conceptual repetition
        has_conceptual, reason = self._has_conceptual_repetition(user_id, signature)
        if has_conceptual:
            return True, reason, ["Shift focus slightly", "Add new perspective", "Introduce contrast"]

        return False, "", []

    def enhance_system_prompt_context(self, user_id: str, base_prompt: str) -> str:
        """
        Enhance system prompt with user-specific context for natural variation.
        This is invisible to the user and guides the AI subtly.
        """
        patterns = self.user_patterns[user_id]
        context = self.conversation_contexts.get(user_id)

        # Only enhance if we have meaningful context
        if not context and patterns['avg_response_length'] < 10:
            return base_prompt

        enhancements = []

        # Vocabulary guidance (only if user has established vocabulary patterns)
        if patterns['preferred_vocabulary'] and len(patterns['preferred_vocabulary']) > 10:
            sample_words = list(patterns['preferred_vocabulary'])[:5]
            enhancements.append(f"Consider using varied vocabulary beyond: {', '.join(sample_words)}")

        # Length guidance (only if we have enough data)
        avg_length = patterns['avg_response_length']
        if avg_length > 20:  # Only for substantial responses
            enhancements.append(f"Vary response length from your usual {avg_length:.0f} words")

        # Context guidance
        if context:
            if context.sentiment != 'neutral':
                enhancements.append(f"Vary your {context.sentiment} tone with fresh perspectives")
            if context.complexity > 0.7:
                enhancements.append("Introduce simpler concepts alongside complex ones")

        # Conversation awareness
        recent_count = len(self.user_signatures[user_id])
        if recent_count >= 3:
            enhancements.append("Bring fresh insights to this ongoing conversation")

        if enhancements:
            context_guidance = "\n\n**Internal Guidance:**\n" + "\n".join(f"- {enh}" for enh in enhancements)
            return base_prompt + context_guidance

        return base_prompt

    def record_response(self, user_id: str, content: str):
        """
        Record a response for future anti-repetition analysis.
        Lightweight operation with automatic cleanup.
        """
        signature = self._create_signature(content)
        self.user_signatures[user_id].append(signature)

        # Update context and patterns
        self._update_conversation_context(user_id, content)
        self._update_user_patterns(user_id, content)

        # Periodic cleanup
        self._cleanup_if_needed()

    def _cleanup_if_needed(self):
        """Lightweight cleanup to maintain performance."""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        # Clean up signature cache (keep only recent)
        if len(self.signature_cache) > 1000:
            # Keep only the most recent 500 signatures
            recent_hashes = set()
            for signatures in self.user_signatures.values():
                recent_hashes.update(sig.content_hash for sig in signatures)

            self.signature_cache = {
                h: sig for h, sig in self.signature_cache.items()
                if h in recent_hashes
            }

        # Clean up inactive users
        current_time = time.time()
        inactive_users = [
            user_id for user_id, patterns in self.user_patterns.items()
            if current_time - patterns['last_interaction'] > 3600  # 1 hour
        ]

        for user_id in inactive_users:
            del self.user_patterns[user_id]
            if user_id in self.conversation_contexts:
                del self.conversation_contexts[user_id]
            if user_id in self.user_signatures:
                del self.user_signatures[user_id]

        self.last_cleanup = current_time

    def get_user_insights(self, user_id: str) -> Dict:
        """Get insights about user interaction patterns."""
        patterns = self.user_patterns[user_id]
        context = self.conversation_contexts.get(user_id)
        signatures = list(self.user_signatures[user_id])

        return {
            "total_responses": len(signatures),
            "avg_response_length": patterns['avg_response_length'],
            "vocabulary_diversity": len(patterns['preferred_vocabulary']),
            "interaction_frequency": patterns['interaction_frequency'],
            "current_sentiment": context.sentiment if context else 'neutral',
            "conversation_complexity": context.complexity if context else 0.0,
            "last_interaction": patterns['last_interaction']
        }


# Global instance
advanced_anti_repetition = AdvancedAntiRepetitionManager()
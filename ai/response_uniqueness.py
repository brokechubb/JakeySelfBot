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
        
        # Time-based cleanup tracking
        self.last_cleanup = time.time()
        
        # Settings
        self.cleanup_interval = 300  # 5 minutes
        self.similarity_threshold = 0.8  # 80% word overlap threshold
        
    def _hash_content(self, content: str) -> str:
        """Generate SHA-256 hash of content for exact duplicate detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for similarity comparison."""
        # Convert to lowercase and remove extra whitespace
        text = re.sub(r'\s+', ' ', text.lower().strip())
        # Remove punctuation for word-level comparison
        text = re.sub(r'[^\w\s]', '', text)
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
        """
        patterns = []
        cleaned_text = self._clean_text(text)
        words = cleaned_text.split()
        
        # Skip analysis for very short texts
        if len(words) < 3:
            return patterns
            
        # Word repetition detection (3+ character words only)
        word_count = {}
        for word in words:
            if len(word) > 3:  # Only count words longer than 3 characters
                word_count[word] = word_count.get(word, 0) + 1
                
        # Find words repeated 2+ times
        repeated_words = [word for word, count in word_count.items() if count >= 2]
        if repeated_words:
            patterns.append(f"Repeated words: {', '.join(repeated_words)}")
            
        # Phrase repetition detection (2-3 word phrases)
        for phrase_length in [2, 3]:
            if len(words) < phrase_length:
                continue
                
            phrase_count = {}
            for i in range(len(words) - phrase_length + 1):
                phrase = ' '.join(words[i:i + phrase_length])
                phrase_count[phrase] = phrase_count.get(phrase, 0) + 1
                
            # Find phrases repeated 2+ times
            repeated_phrases = [
                phrase for phrase, count in phrase_count.items() 
                if count >= 2 and len(phrase) > 6  # Ignore very short phrases
            ]
            
            if repeated_phrases:
                patterns.append(f"Repeated {phrase_length}-word phrases: {', '.join(repeated_phrases[:3])}")
                
        return patterns
    
    def _is_exact_duplicate(self, user_id: str, content: str) -> bool:
        """Check if content is an exact duplicate of a recent response."""
        content_hash = self._hash_content(content)
        user_hashes = self.response_hashes.get(user_id, set())
        
        # Check if this exact content hash exists in recent responses
        if content_hash in user_hashes:
            logger.debug(f"Exact duplicate detected for user {user_id}")
            return True
            
        return False
    
    def _is_too_similar(self, user_id: str, content: str) -> Tuple[bool, float]:
        """
        Check if content is too similar to recent responses.
        Returns a tuple of (is_similar, similarity_score).
        """
        user_history = list(self.user_responses.get(user_id, []))
        
        # Only check similarity against the most recent 3 responses
        recent_responses = user_history[-3:]
        
        for recent_text in recent_responses:
            similarity = self._get_jaccard_similarity(content, recent_text)
            if similarity >= self.similarity_threshold:
                logger.debug(f"High similarity detected for user {user_id}: {similarity:.2f}")
                return True, similarity
                
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
        # 1. Check for exact duplicates
        if self._is_exact_duplicate(user_id, content):
            return True, "Exact duplicate of recent response"
            
        # 2. Check for high similarity
        is_similar, similarity_score = self._is_too_similar(user_id, content)
        if is_similar:
            return True, f"Too similar ({similarity_score:.1%} word overlap) to recent response"
            
        # 3. Check for internal repetition patterns
        has_internal, patterns = self.has_internal_repetition(content)
        if has_internal:
            pattern_text = "; ".join(patterns[:2])  # Limit message length
            return True, f"Internal repetition detected: {pattern_text}"
            
        return False, ""
    
    def add_response(self, user_id: str, content: str):
        """
        Add a response to the user's history and track its hash.
        This should be called after successfully sending a response.
        """
        # Add to user's response history
        self.user_responses[user_id].append(content)
        
        # Track the content hash
        content_hash = self._hash_content(content)
        self.response_hashes[user_id].add(content_hash)
        
        # Periodically clean up old data
        self._cleanup_if_needed()
    
    def _cleanup_if_needed(self):
        """Clean up old data if cleanup interval has passed."""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
            
        logger.debug("Performing response uniqueness cleanup")
        
        # Keep only recent hashes (corresponding to the 10 most recent responses)
        for user_id in list(self.response_hashes.keys()):
            user_response_count = len(self.user_responses.get(user_id, []))
            if user_response_count == 0:
                # Clean up users with no responses
                del self.response_hashes[user_id]
                continue
                
            # Limit hashes to match response count
            user_hashes = self.response_hashes[user_id]
            if len(user_hashes) > user_response_count:
                # Keep only the most recent hashes
                # Convert to deque to match response history behavior
                recent_hashes = deque(list(user_hashes)[-user_response_count:], maxlen=10)
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


# Global instance for use across the application
response_uniqueness = ResponseUniquenessManager()
"""
Automatic Memory Extractor for Jakey

Analyzes conversations and automatically extracts and stores meaningful memories.
"""

import re
import json
import datetime
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


class AutoMemoryExtractor:
    """
    Extracts meaningful information from conversations for automatic memory storage.
    """

    # Patterns for information extraction
    PERSONAL_INFO_PATTERNS = {
        "name": [
            r"(?:my name is|i'm|i am|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"i(?:'m| am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        ],
        "location": [
            r"(?:i live in|i'm from|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"(?:live in|located in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ],
        "age": [
            r"(?:i am|i'm)\s+(\d+)\s*(?:years? old|yrs? old)",
            r"age\s+(?:is|:)\s*(\d+)",
        ],
        "birthday": [
            r"(?:my birthday|birthday)\s+(?:is|:)\s*([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?)",
            r"born\s+(?:on|:)\s*([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?)",
        ],
        "occupation": [
            r"(?:i work as|i'm a|i am a|my job is)\s+([a-zA-Z\s]+?)(?:\.|,|$| and)",
            r"(?:occupation|job|profession)\s+(?:is|:)\s+([a-zA-Z\s]+?)(?:\.|,|$| and)",
        ],
        "hobbies": [
            r"(?:i like|i enjoy|my hobby is|hobbies? (?:include|are))\s+([a-zA-Z\s,]+?)(?:\.|,|$| and)",
            r"hobbies?:\s*([a-zA-Z\s,]+?)(?:\.|,|$)",
        ],
        "preferences": [
            r"(?:i love|i really like|i prefer)\s+([a-zA-Z\s]+?)(?:\.|,|$| and)",
            r"(?:favorite|fav(?:ourite)?)\s+([a-zA-Z\s]+?)(?:\.|,|$|is|are)",
        ],
        "dislikes": [
            r"(?:i hate|i dislike|i can't stand)\s+([a-zA-Z\s]+?)(?:\.|,|$| and)",
            r"(?:don't like|do not like)\s+([a-zA-Z\s]+?)(?:\.|,|$| and)",
        ],
    }

    # Keywords that indicate important information
    IMPORTANCE_KEYWORDS = [
        "remember", "don't forget", "important", "note", "FYI", "for the record",
        "just so you know", "btw", "by the way", "fyi", "ps", "p.s.", "actually"
    ]

    # Topics that are generally worth remembering
    IMPORTANT_TOPICS = [
        "family", "work", "job", "school", "college", "university", "health",
        "relationship", "friend", "girlfriend", "boyfriend", "partner", "married",
        "birthday", "anniversary", "vacation", "holiday", "trip", "travel"
    ]

    # Patterns that indicate important context
    CONTEXT_PATTERNS = [
        r"(?:i have|i've got)\s+(\w+)\s+(?:who|that)",
        r"(?:my \w+ is|my \w+s are)",
        r"(?:i'm going|i am going|i will)\s+\w+\s+(?:to|for)",
        r"(?:i need|i must|i should)\s+\w+",
        r"(?:i want|i'd like)\s+\w+\s+to",
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def extract_memories_from_conversation(
        self, user_message: str, bot_response: str, user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Extract meaningful memories from a conversation exchange.
        
        Returns a list of memory objects to be stored.
        """
        memories = []
        
        # Combine user message and bot response for context
        full_context = f"{user_message} {bot_response}"
        
        # Extract personal information
        personal_memories = self._extract_personal_info(user_message, user_id)
        memories.extend(personal_memories)
        
        # Extract important facts
        fact_memories = self._extract_important_facts(full_context, user_id)
        memories.extend(fact_memories)
        
        # Extract preferences and opinions
        preference_memories = self._extract_preferences(full_context, user_id)
        memories.extend(preference_memories)
        
        # Extract context about what user is doing
        context_memories = self._extract_context(full_context, user_id)
        memories.extend(context_memories)
        
        # Extract relationships
        relationship_memories = self._extract_relationships(full_context, user_id)
        memories.extend(relationship_memories)
        
        # Filter out memories that are too short or not meaningful
        filtered_memories = self._filter_memories(memories)
        
        # Generate unique IDs and timestamps
        for memory in filtered_memories:
            memory['id'] = self._generate_memory_id(memory, user_id)
            memory['timestamp'] = datetime.datetime.utcnow().isoformat()
            memory['confidence'] = memory.get('confidence', 1.0)
        
        return filtered_memories

    def _extract_personal_info(self, text: str, user_id: str) -> List[Dict[str, Any]]:
        """Extract personal information from text."""
        memories = []
        text_lower = text.lower()
        
        for info_type, patterns in self.PERSONAL_INFO_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if len(value) > 2:  # Filter out very short matches
                        memories.append({
                            "type": "personal_info",
                            "category": info_type,
                            "information": value,
                            "source": "personal_info_pattern",
                            "confidence": 0.9
                        })
                        break  # Only take first match per type
        
        return memories

    def _extract_important_facts(self, text: str, user_id: str) -> List[Dict[str, Any]]:
        """Extract important facts from text."""
        memories = []
        text_lower = text.lower()
        
        # Check for importance indicators
        has_importance_indicator = any(keyword in text_lower for keyword in self.IMPORTANCE_KEYWORDS)
        
        # Check for important topics
        has_important_topic = any(topic in text_lower for topic in self.IMPORTANT_TOPICS)
        
        # Extract sentences that might contain important facts
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short sentences
                continue
                
            sentence_lower = sentence.lower()
            
            # Check if sentence contains important information
            important = (
                has_importance_indicator or
                has_important_topic or
                any(topic in sentence_lower for topic in self.IMPORTANT_TOPICS) or
                any(keyword in sentence_lower for keyword in self.IMPORTANCE_KEYWORDS) or
                re.search(r'(?:i have|i own|i bought|i got|i created)', sentence_lower) or
                re.search(r'(?:i will|i am going|i plan to)', sentence_lower)
            )
            
            if important:
                memories.append({
                    "type": "fact",
                    "category": "important_fact",
                    "information": sentence,
                    "source": "importance_detection",
                    "confidence": 0.7 if has_importance_indicator else 0.5
                })
        
        return memories

    def _extract_preferences(self, text: str, user_id: str) -> List[Dict[str, Any]]:
        """Extract user preferences and opinions."""
        memories = []
        
        # Preference patterns
        preference_patterns = [
            r"(?:i love|i really like|i enjoy|i prefer)\s+([^.!?]+)",
            r"(?:i hate|i dislike|i can't stand)\s+([^.!?]+)",
            r"(?:my favorite|favorite)\s+([^.!?]+)",
            r"(?:i think|i feel|i believe)\s+([^.!?]+)",
        ]
        
        for pattern in preference_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                preference = match.group(1).strip()
                if len(preference) > 3:
                    # Determine if it's a like or dislike
                    pref_text = match.group(0).lower()
                    if any(word in pref_text for word in ["love", "like", "enjoy", "prefer", "favorite"]):
                        category = "likes"
                    elif any(word in pref_text for word in ["hate", "dislike", "can't stand"]):
                        category = "dislikes"
                    else:
                        category = "opinion"
                    
                    memories.append({
                        "type": "preference",
                        "category": category,
                        "information": preference,
                        "source": "preference_pattern",
                        "confidence": 0.8
                    })
        
        return memories

    def _extract_context(self, text: str, user_id: str) -> List[Dict[str, Any]]:
        """Extract contextual information about what user is doing."""
        memories = []
        
        # Context patterns
        for pattern in self.CONTEXT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                context = match.group(0).strip()
                if len(context) > 10:
                    memories.append({
                        "type": "context",
                        "category": "user_context",
                        "information": context,
                        "source": "context_pattern",
                        "confidence": 0.6
                    })
        
        return memories

    def _extract_relationships(self, text: str, user_id: str) -> List[Dict[str, Any]]:
        """Extract information about relationships."""
        memories = []
        text_lower = text.lower()
        
        # Relationship keywords
        relationship_patterns = [
            r"(?:my \w+)\s+(?:is|are)\s+([^.!?]+)",
            r"(?:i have a|i have an)\s+(?:\w+\s+)?(friend|brother|sister|mother|father|son|daughter|husband|wife|partner|girlfriend|boyfriend)\s+([^.!?]+)?",
        ]
        
        for pattern in relationship_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                relationship_info = match.group(0).strip()
                if len(relationship_info) > 5:
                    memories.append({
                        "type": "relationship",
                        "category": "personal_relationship",
                        "information": relationship_info,
                        "source": "relationship_pattern",
                        "confidence": 0.7
                    })
        
        return memories

    def _filter_memories(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out low-quality or duplicate memories."""
        filtered = []
        seen_content = set()
        
        for memory in memories:
            info = memory.get("information", "").strip()
            
            # Skip if too short
            if len(info) < 3:
                continue
            
            # Skip if likely too generic
            if info.lower() in ["yes", "no", "ok", "okay", "maybe", "thanks", "thank you", "hi", "hello"]:
                continue
            
            # Skip duplicate content
            content_hash = hashlib.md5(info.lower().encode()).hexdigest()
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            
            # Skip if confidence is too low
            if memory.get("confidence", 0) < 0.4:
                continue
            
            filtered.append(memory)
        
        return filtered

    def _generate_memory_id(self, memory: Dict[str, Any], user_id: str) -> str:
        """Generate a unique ID for a memory."""
        content = f"{user_id}{memory.get('type', '')}{memory.get('information', '')}{memory.get('timestamp', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def store_memories(self, memories: List[Dict[str, Any]], user_id: str) -> List[bool]:
        """
        Store extracted memories using the unified memory backend.
        
        Returns a list of success indicators for each memory.
        """
        results = []
        
        try:
            # Import here to avoid circular dependencies
            from memory import memory_backend
            
            if memory_backend is None:
                logger.warning("Memory backend not available, skipping auto memory storage")
                return [False] * len(memories)
            
            for memory in memories:
                try:
                    # Create a unique memory key from type, category, and timestamp/hash
                    import hashlib
                    import time
                    # Create a short hash from the information content to ensure uniqueness
                    content_hash = hashlib.md5(memory.get("information", "").encode()).hexdigest()[:8]
                    memory_key = f"{memory['type']}_{memory['category']}_{content_hash}"
                    
                    # Store additional metadata
                    metadata = {
                        "source": memory.get("source", "auto_extracted"),
                        "confidence": memory.get("confidence", 1.0),
                        "extracted_at": datetime.datetime.utcnow().isoformat()
                    }
                    
                    # Store the memory
                    success = await memory_backend.store(
                        user_id=user_id,
                        key=memory_key,
                        value=memory.get("information", ""),
                        metadata=metadata
                    )
                    
                    results.append(success)
                    
                    if success:
                        logger.debug(f"Stored auto-extracted memory for user {user_id}: {memory_key}")
                    else:
                        logger.warning(f"Failed to store memory for user {user_id}: {memory_key}")
                        
                except Exception as e:
                    logger.error(f"Error storing individual memory: {e}")
                    results.append(False)
                    
        except ImportError as e:
            logger.error(f"Memory backend import error: {e}")
            return [False] * len(memories)
        except Exception as e:
            logger.error(f"Error in store_memories: {e}")
            return [False] * len(memories)
        
        return results


class MemoryCleanupManager:
    """
    Manages cleanup of old memories to prevent bloat.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def cleanup_old_memories(self, max_age_days: int = 365, confidence_threshold: float = 0.5):
        """
        Clean up old memories based on age and confidence.
        
        Args:
            max_age_days: Maximum age in days to keep memories
            confidence_threshold: Minimum confidence to keep memories
        """
        try:
            from memory import memory_backend
            
            if memory_backend is None:
                logger.warning("Memory backend not available for cleanup")
                return
            
            # Perform cleanup using the unified backend
            cleanup_result = await memory_backend.cleanup(max_age_days)
            
            total_cleaned = sum(cleanup_result.values())
            if total_cleaned > 0:
                self.logger.info(f"Cleaned up {total_cleaned} old memories")
                for backend, count in cleanup_result.items():
                    self.logger.info(f"  {backend}: {count}")
            else:
                self.logger.debug("No memories to clean up")
                
        except Exception as e:
            self.logger.error(f"Error during memory cleanup: {e}")
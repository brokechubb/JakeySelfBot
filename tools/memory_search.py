"""
Memory Search Tool for Jakey

Provides tools to search and retrieve user memories for AI context.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)


class MemorySearchTool:
    """
    Tool for searching and retrieving user memories to provide context to AI.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Simple cache to reduce repeated database queries
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 60  # Cache for 60 seconds
        self._cache_max_size = 100  # Maximum cached entries

    async def search_user_memories(
        self, 
        user_id: str, 
        query: Optional[str] = None, 
        limit: int = 10,
        min_confidence: float = 0.3
    ) -> Dict[str, Any]:
        """
        Search for user memories to provide context to AI responses.
        
        Args:
            user_id: The Discord user ID
            query: Optional search query to filter memories
            limit: Maximum number of memories to return
            min_confidence: Minimum confidence threshold for memories
            
        Returns:
            Dictionary with memories and metadata
        """
        try:
            from memory import memory_backend
            
            if memory_backend is None:
                return {"error": "Memory backend not available"}
            
            # Retrieve memories from the unified backend
            if query:
                memories = await memory_backend.search(user_id, query, limit)
            else:
                # Get all memories for the user
                all_memories = await memory_backend.get_all(user_id)
                memories = []
                
                # Convert to MemoryEntry objects and filter by confidence
                for key, value in all_memories.items():
                    # Get metadata if available
                    memory_entry = await memory_backend.retrieve(user_id, key)
                    if memory_entry and memory_entry.metadata:
                        confidence = memory_entry.metadata.get('confidence', 1.0)
                        if confidence >= min_confidence:
                            memories.append(memory_entry)
                
                # Sort by most recent and limit
                memories.sort(key=lambda x: x.updated_at, reverse=True)
                memories = memories[:limit]
            
            # Format memories for AI consumption
            formatted_memories = []
            for memory in memories:
                # Extract key information
                memory_type = memory.key.split('_', 1) if '_' in memory.key else ['info', memory.key]
                category = memory_type[1] if len(memory_type) > 1 else memory_type[0]
                
                # Get confidence from metadata if available
                confidence = 1.0
                if memory.metadata:
                    confidence = memory.metadata.get('confidence', 1.0)
                
                formatted_memories.append({
                    "type": memory_type[0],
                    "category": category,
                    "information": memory.value,
                    "confidence": confidence,
                    "last_updated": memory.updated_at
                })
            
            # Group memories by type for better organization
            grouped_memories = {}
            for memory in formatted_memories:
                mem_type = memory['type']
                if mem_type not in grouped_memories:
                    grouped_memories[mem_type] = []
                grouped_memories[mem_type].append(memory)
            
            return {
                "success": True,
                "user_id": user_id,
                "query": query,
                "total_memories": len(formatted_memories),
                "grouped_memories": grouped_memories,
                "all_memories": formatted_memories
            }
            
        except Exception as e:
            self.logger.error(f"Error searching user memories: {e}")
            return {"error": f"Failed to search memories: {str(e)}"}

    async def get_conversation_summary(
        self, 
        user_id: str,
        days: int = 7,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get a summary of recent memories and important facts about a user.
        
        Args:
            user_id: The Discord user ID
            days: Number of days to look back for recent memories
            limit: Maximum number of conversations to summarize
            
        Returns:
            Dictionary with conversation summary
        """
        try:
            from memory import memory_backend
            from datetime import datetime, timedelta
            
            if memory_backend is None:
                return {"error": "Memory backend not available"}
            
            # Get recent memories
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Search for recent memories
            memories = await memory_backend.search(user_id, None, limit)
            
            # Filter by date
            recent_memories = []
            for m in memories:
                try:
                    updated_at_str = m.updated_at
                    if isinstance(updated_at_str, float):
                        # Convert timestamp to string
                        updated_at_str = str(updated_at_str)
                    elif not isinstance(updated_at_str, str):
                        continue
                        
                    # Handle both Z and +00:00 timezone formats
                    if updated_at_str.endswith('Z'):
                        updated_at_str = updated_at_str.replace('Z', '+00:00')
                    
                    memory_date = datetime.fromisoformat(updated_at_str)
                    if memory_date >= cutoff_date:
                        recent_memories.append(m)
                except (ValueError, AttributeError) as e:
                    # Skip memories with invalid dates
                    self.logger.debug(f"Skipping memory with invalid date: {e}")
                    continue
            
            # Separate different types of memories
            personal_info = []
            preferences = []
            facts = []
            context = []
            relationships = []
            
            for memory in recent_memories:
                category = memory.key.split('_', 1)[0] if '_' in memory.key else 'info'
                
                if category == 'personal_info':
                    personal_info.append(memory)
                elif category == 'preference':
                    preferences.append(memory)
                elif category == 'fact':
                    facts.append(memory)
                elif category == 'context':
                    context.append(memory)
                elif category == 'relationship':
                    relationships.append(memory)
            
            # Build summary
            summary = {
                "success": True,
                "user_id": user_id,
                "date_range_days": days,
                "total_memories": len(recent_memories),
                "personal_information": [m.value for m in personal_info],
                "preferences": [m.value for m in preferences],
                "important_facts": [m.value for m in facts],
                "recent_context": [m.value for m in context[-5:]],  # Last 5 context memories
                "relationships": [m.value for m in relationships],
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting conversation summary: {e}")
            return {"error": f"Failed to get summary: {str(e)}"}

    def format_memories_for_ai(self, memories_data: Dict[str, Any]) -> str:
        """
        Format memories into a concise string for AI consumption.
        
        Args:
            memories_data: The data returned from search_user_memories
            
        Returns:
            Formatted string with key memories
        """
        if not memories_data.get('success') or not memories_data.get('grouped_memories'):
            return "No memories available."
        
        grouped = memories_data['grouped_memories']
        formatted_parts = []
        
        if 'personal_info' in grouped and grouped['personal_info']:
            formatted_parts.append("Personal Information:")
            for memory in grouped['personal_info'][:5]:  # Limit to 5 items
                category = memory['category'].replace('_', ' ').title()
                formatted_parts.append(f"  - {category}: {memory['information']}")
        
        if 'preference' in grouped and grouped['preference']:
            formatted_parts.append("Preferences:")
            for memory in grouped['preference'][:5]:  # Limit to 5 items
                category = memory['category'].replace('_', ' ').title()
                formatted_parts.append(f"  - {category}: {memory['information']}")
        
        if 'fact' in grouped and grouped['fact']:
            formatted_parts.append("Important Facts:")
            for memory in grouped['fact'][:5]:  # Limit to 5 items
                formatted_parts.append(f"  - {memory['information']}")
        
        if 'relationship' in grouped and grouped['relationship']:
            formatted_parts.append("Relationships:")
            for memory in grouped['relationship'][:3]:  # Limit to 3 items
                formatted_parts.append(f"  - {memory['information']}")
        
        if 'context' in grouped and grouped['context']:
            formatted_parts.append("Recent Context:")
            for memory in grouped['context'][:3]:  # Limit to 3 items
                formatted_parts.append(f"  - {memory['information']}")
        
        return '\n'.join(formatted_parts) if formatted_parts else "No relevant memories found."

    def _get_cache_key(self, user_id: str, query: str) -> str:
        """Generate cache key for memory searches."""
        return f"{user_id}:{hash(query.lower())}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Get result from cache if valid."""
        import time
        
        if cache_key not in self._cache:
            return None
            
        # Check if cache entry is still valid
        if cache_key in self._cache_timestamps:
            age = time.time() - self._cache_timestamps[cache_key]
            if age > self._cache_ttl:
                # Cache expired, remove it
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
                return None
        
        return self._cache.get(cache_key)
    
    def _store_in_cache(self, cache_key: str, result: str):
        """Store result in cache."""
        import time
        
        # Remove oldest entries if cache is full
        if len(self._cache) >= self._cache_max_size:
            oldest_key = min(self._cache_timestamps.keys(), 
                           key=lambda k: self._cache_timestamps[k])
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]
        
        self._cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()

    async def get_memory_context_for_message(
        self, 
        user_id: str, 
        message_content: str,
        limit: int = 10
    ) -> str:
        """
        Get relevant memory context for a specific message.
        OPTIMIZED: Single smart search + caching instead of 3 separate searches.
        
        Args:
            user_id: The Discord user ID
            message_content: The content of the user's message
            limit: Maximum number of memories to retrieve
            
        Returns:
            Formatted string with relevant memories
        """
        try:
            import time
            start_time = time.time()
            
            # Check cache first
            cache_key = self._get_cache_key(user_id, message_content)
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                self.logger.debug(f"Memory context from cache in {time.time() - start_time:.3f}s")
                return cached_result if cached_result else ""
            
            # Extract keywords from message for fallback
            import re
            words = re.findall(r'\b\w+\b', message_content.lower())
            
            # Skip common words
            skip_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
                'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us',
                'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'what',
                'when', 'where', 'why', 'how', 'who', 'which', 'that', 'this', 'these',
                'those', 'can', 'may', 'might', 'must', 'shall', 'hi', 'hello', 'hey',
                'thanks', 'thank', 'yes', 'no', 'ok', 'okay', 'yeah', 'yep', 'nope'
            }
            
            keywords = [w for w in words if w not in skip_words and len(w) > 2]
            
            # OPTIMIZED: Single comprehensive search strategy
            # Start with full message search, get recent memories as fallback in same query
            search_result = await self.search_user_memories(user_id, message_content, limit)
            
            # If full message search doesn't find enough memories, try keywords
            # BUT only if we have keywords and the first search was poor
            if (not search_result.get('success') or 
                search_result.get('total_memories', 0) < 2) and keywords:
                
                # Use keywords as fallback query
                keyword_query = ' '.join(keywords[:5])  # Use top 5 keywords
                keyword_search = await self.search_user_memories(user_id, keyword_query, limit)
                
                # Use keyword search only if it finds more memories
                if (keyword_search.get('success') and 
                    keyword_search.get('total_memories', 0) > search_result.get('total_memories', 0)):
                    search_result = keyword_search
            
            # If still no good results, get recent memories (final fallback)
            if not search_result.get('success') or search_result.get('total_memories', 0) == 0:
                recent_search = await self.search_user_memories(user_id, None, limit)
                if recent_search.get('success'):
                    search_result = recent_search
            
            # Format the memories for AI consumption
            if search_result and search_result.get('success'):
                formatted_memories = self.format_memories_for_ai(search_result)
                
                # Store in cache for future requests
                self._store_in_cache(cache_key, formatted_memories)
                
                # Log performance metrics
                search_time = time.time() - start_time
                self.logger.debug(
                    f"Memory context retrieved in {search_time:.3f}s: "
                    f"{search_result.get('total_memories', 0)} memories for user {user_id}"
                )
                
                return formatted_memories
            
            # Store empty result in cache too (to avoid repeated failed searches)
            self._store_in_cache(cache_key, "")
            
            # Log performance even for empty results
            search_time = time.time() - start_time
            self.logger.debug(f"Memory context search completed in {search_time:.3f}s: no memories found")
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error getting memory context: {e}")
            return ""


# Create a global instance for tool manager integration
memory_search_tool = MemorySearchTool()
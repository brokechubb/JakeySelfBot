#!/usr/bin/env python3
"""
Test script for automatic memory extraction system
"""

import asyncio
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.auto_memory_extractor import AutoMemoryExtractor


async def test_memory_extraction():
    """Test the memory extraction functionality"""
    print("Testing Automatic Memory Extraction System")
    print("=" * 50)
    
    extractor = AutoMemoryExtractor()
    
    # Test cases with different types of conversations
    test_cases = [
        {
            "user_message": "Hi Jakey, my name is John and I'm a software developer from California.",
            "bot_response": "Nice to meet you, John! It's great to connect with a fellow developer from California.",
            "expected_memories": ["name: John", "occupation: software developer", "location: California"]
        },
        {
            "user_message": "I really love hiking and mountain biking on weekends. My birthday is coming up next month.",
            "bot_response": "That sounds wonderful! Hiking and mountain biking are great activities. When exactly is your birthday?",
            "expected_memories": ["hobbies", "birthday"]
        },
        {
            "user_message": "Remember that I'm allergic to peanuts. Also, my wife Sarah and I are planning a trip to Japan next month.",
            "bot_response": "I'll definitely remember about your peanut allergy - that's important! Japan sounds amazing, Sarah and you will have a wonderful time.",
            "expected_memories": ["allergic", "wife Sarah", "trip to Japan"]
        },
        {
            "user_message": "I work at Google as a senior engineer. I have two kids, a boy and a girl.",
            "bot_response": "Wow, Google is an amazing place to work! It must be busy being a senior engineer there. How old are your kids?",
            "expected_memories": ["work at Google", "senior engineer", "two kids"]
        },
        {
            "user_message": "BTW, I hate horror movies but I love sci-fi. My favorite movie is Interstellar.",
            "bot_response": "I understand - horror can be intense! Interstellar is absolutely brilliant though. What do you like most about sci-fi movies?",
            "expected_memories": ["hate horror movies", "love sci-fi", "favorite movie: Interstellar"]
        }
    ]
    
    user_id = "test_user_123"
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}")
        print("-" * 30)
        print(f"User: {test_case['user_message']}")
        print(f"Bot: {test_case['bot_response']}")
        print("\nExtracted Memories:")
        
        # Extract memories
        memories = await extractor.extract_memories_from_conversation(
            test_case['user_message'],
            test_case['bot_response'],
            user_id
        )
        
        if memories:
            for memory in memories:
                print(f"  - [{memory['type']}.{memory['category']}] {memory['information']} (confidence: {memory['confidence']})")
                
            # Check if expected memory types were extracted
            found_types = [m['category'] for m in memories]
            for expected in test_case['expected_memories']:
                if any(expected.lower() in found_type.lower() for found_type in found_types):
                    print(f"    ✓ Found expected memory: {expected}")
        else:
            print("  No memories extracted")
    
    print("\n" + "=" * 50)
    print("Memory extraction test complete!")


async def test_memory_storage():
    """Test storing memories in the memory backend"""
    print("\nTesting Memory Storage")
    print("=" * 30)
    
    try:
        from memory import memory_backend
        
        if memory_backend is None:
            print("Memory backend not available - skipping storage test")
            return
        
        extractor = AutoMemoryExtractor()
        
        # Create some test memories
        test_memories = [
            {
                "type": "personal_info",
                "category": "name",
                "information": "Test User",
                "source": "test",
                "confidence": 0.9
            },
            {
                "type": "preference",
                "category": "likes",
                "information": "Python programming",
                "source": "test",
                "confidence": 0.8
            }
        ]
        
        user_id = "test_storage_user"
        
        # Store memories
        results = await extractor.store_memories(test_memories, user_id)
        
        successful = sum(1 for r in results if r)
        print(f"Stored {successful}/{len(test_memories)} memories")
        
        # Retrieve memories to verify
        all_memories = await memory_backend.get_all(user_id)
        print(f"Retrieved {len(all_memories)} memories from backend:")
        for key, value in all_memories.items():
            print(f"  - {key}: {value}")
        
    except ImportError as e:
        print(f"Memory backend import error: {e}")
    except Exception as e:
        print(f"Error testing memory storage: {e}")


async def main():
    """Main test function"""
    await test_memory_extraction()
    await test_memory_storage()


if __name__ == "__main__":
    asyncio.run(main())
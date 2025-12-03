#!/usr/bin/env python3
"""
Test script for trivia drop improvements
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.trivia_manager import trivia_manager
from utils.logging_config import get_logger

logger = get_logger(__name__)

async def test_trivia_improvements():
    """Test the improved trivia system"""
    
    print("🧪 Testing Trivia Drop Improvements\n")
    
    try:
        # Initialize trivia manager
        await trivia_manager.initialize()
        print("✅ Trivia manager initialized")
        
        # Test 1: Find known answer
        print("\n1. Testing known answer lookup...")
        known_answer = await trivia_manager.find_trivia_answer(
            "Entertainment: Music", 
            "Which Beatle led the way across the zebra crossing on the Abbey Road album cover?"
        )
        print(f"   Answer: {known_answer}")
        
        # Test 2: Try unknown question (should record as unknown)
        print("\n2. Testing unknown question handling...")
        unknown_answer = await trivia_manager.find_trivia_answer(
            "Entertainment: Music",
            "What is Jakey's favorite Discord bot feature?"
        )
        print(f"   Answer: {unknown_answer}")
        
        # Test 3: Record successful answer manually
        print("\n3. Testing manual answer recording...")
        await trivia_manager.record_successful_answer(
            "Entertainment: Music",
            "What is Jakey's favorite Discord bot feature?",
            "Airdrop automation",
            channel_id="test_channel",
            guild_id="test_guild"
        )
        print("   ✅ Successfully recorded manual answer")
        
        # Test 4: Verify the learned answer
        print("\n4. Testing learned answer lookup...")
        learned_answer = await trivia_manager.find_trivia_answer(
            "Entertainment: Music",
            "What is Jakey's favorite Discord bot feature?"
        )
        print(f"   Learned Answer: {learned_answer}")
        
        # Test 5: Show database stats
        print("\n5. Database statistics:")
        stats = await trivia_manager.get_database_overview()
        print(f"   Total Questions: {stats.get('total_questions', 0)}")
        print(f"   Total Categories: {stats.get('total_categories', 0)}")
        print(f"   Health Status: {stats.get('health_status', 'unknown')}")
        
        # Test 6: Show unknown questions
        print("\n6. Testing unknown question search...")
        unknown_questions = await trivia_manager.search_questions("UNKNOWN_ANSWER", limit=5)
        print(f"   Found {len(unknown_questions)} unknown questions")
        for q in unknown_questions[:3]:
            print(f"   - {q['question_text'][:50]}...")
        
        # Test 7: Test random selection scenario
        print("\n7. Testing random answer scenario...")
        # Simulate a question that won't be found anywhere
        random_test_answer = await trivia_manager.find_trivia_answer(
            "Entertainment: Music",
            "What is the airspeed velocity of an unladen swallow?"
        )
        print(f"   Random test answer: {random_test_answer}")
        
        print("\n🎉 All tests completed!")
        print("\n💡 New Features Added:")
        print("   ✅ Automatic learning from successful trivia drops")
        print("   ✅ Recording unknown questions for future learning")
        print("   ✅ Random answer fallback when no answer is known")
        print("   ✅ Manual answer management with %unknowntrivia and %addtrivia")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await trivia_manager.close()

if __name__ == "__main__":
    asyncio.run(test_trivia_improvements())
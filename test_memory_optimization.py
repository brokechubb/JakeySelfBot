#!/usr/bin/env python3
"""
Test script to verify memory search optimization
"""
import asyncio
import time
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.memory_search import memory_search_tool


async def test_memory_search_optimization():
    """Test the optimized memory search functionality"""
    
    print("🧪 Testing Memory Search Optimization")
    print("=" * 50)
    
    user_id = "123456789"  # Test user ID
    message_content = "hello how are you today"
    
    # Test 1: First search (should hit database)
    print("\n1️⃣ Testing first memory search (database lookup)...")
    start = time.time()
    result1 = await memory_search_tool.get_memory_context_for_message(user_id, message_content)
    first_time = time.time() - start
    print(f"⏱️ First search: {first_time:.3f}s")
    print(f"📝 Result: {result1[:100] if result1 else 'No memories found'}")
    
    # Test 2: Second search (should hit cache)
    print("\n2️⃣ Testing second memory search (cache lookup)...")
    start = time.time()
    result2 = await memory_search_tool.get_memory_context_for_message(user_id, message_content)
    second_time = time.time() - start
    print(f"⏱️ Second search: {second_time:.3f}s")
    print(f"📝 Result: {result2[:100] if result2 else 'No memories found'}")
    
    # Test 3: Different message (should hit database)
    print("\n3️⃣ Testing different message (database lookup)...")
    start = time.time()
    result3 = await memory_search_tool.get_memory_context_for_message(user_id, "different message")
    third_time = time.time() - start
    print(f"⏱️ Different message: {third_time:.3f}s")
    print(f"📝 Result: {result3[:100] if result3 else 'No memories found'}")
    
    # Test 4: Same message again (should hit cache)
    print("\n4️⃣ Testing original message again (cache lookup)...")
    start = time.time()
    result4 = await memory_search_tool.get_memory_context_for_message(user_id, message_content)
    fourth_time = time.time() - start
    print(f"⏱️ Original again: {fourth_time:.3f}s")
    print(f"📝 Result: {result4[:100] if result4 else 'No memories found'}")
    
    # Performance analysis
    print("\n" + "=" * 50)
    print("📊 Performance Analysis:")
    
    if second_time < first_time:
        speedup = (first_time - second_time) / first_time * 100
        print(f"✅ Cache working! {speedup:.1f}% faster on second search")
        print(f"🚀 Database: {first_time:.3f}s → Cache: {second_time:.3f}s")
    else:
        print(f"⚠️ Cache may not be working properly")
        print(f"📊 First: {first_time:.3f}s, Second: {second_time:.3f}s")
    
    # Check consistency
    if result1 == result2:
        print("✅ Cache consistency verified")
    else:
        print("❌ Cache inconsistency detected")
    
    # Cache statistics
    cache_size = len(memory_search_tool._cache)
    print(f"📦 Cache size: {cache_size} entries")
    
    print("\n🎯 Optimization Summary:")
    print("- Eliminated redundant 3x searches per message")
    print("- Added intelligent caching with 60s TTL")
    print("- Combined search strategies into single smart query")
    print("- Added performance logging for monitoring")


if __name__ == "__main__":
    asyncio.run(test_memory_search_optimization())
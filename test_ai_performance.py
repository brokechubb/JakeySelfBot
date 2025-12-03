#!/usr/bin/env python3
"""
Test script to verify AI performance improvements
"""
import asyncio
import time
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.pollinations import pollinations_api
from ai.ai_provider_manager import ai_provider_manager


async def test_ai_performance():
    """Test both direct API calls and AI provider manager"""
    
    print("🧪 Testing AI Performance Improvements")
    print("=" * 50)
    
    # Test message
    messages = [{'role': 'user', 'content': 'Say hello quickly'}]
    
    # Test 1: Direct Pollinations API
    print("\n1️⃣ Testing Direct Pollinations API...")
    start = time.time()
    result = pollinations_api.generate_text(messages=messages, max_tokens=50)
    pollinations_time = time.time() - start
    
    if 'choices' in result and result['choices']:
        content = result['choices'][0]['message']['content']
        print(f"✅ Pollinations: {pollinations_time:.2f}s")
        print(f"📝 Response: {content[:100]}...")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
        print(f"⏱️ Time: {pollinations_time:.2f}s")
    
    # Test 2: AI Provider Manager (with failover)
    print("\n2️⃣ Testing AI Provider Manager...")
    start = time.time()
    result = await ai_provider_manager.generate_text(messages=messages, max_tokens=50)
    manager_time = time.time() - start
    
    if 'choices' in result and result['choices']:
        content = result['choices'][0]['message']['content']
        print(f"✅ AI Manager: {manager_time:.2f}s")
        print(f"📝 Response: {content[:100]}...")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
        print(f"⏱️ Time: {manager_time:.2f}s")
    
    # Test 3: Get provider statistics
    print("\n3️⃣ Provider Statistics:")
    stats = ai_provider_manager.get_statistics()
    print(f"📊 Total requests: {stats['total_requests']}")
    print(f"✅ Successful: {stats['successful_requests']}")
    print(f"🔄 Failover count: {stats['failover_count']}")
    print(f"📈 Success rate: {stats['success_rate']:.1%}")
    print(f"🏥 Provider usage: {stats['provider_usage']}")
    
    # Test 4: Timeout statistics
    print("\n4️⃣ Timeout Statistics:")
    timeout_stats = stats.get('timeout_stats', {})
    if timeout_stats.get('monitoring_enabled'):
        pollinations_stats = timeout_stats.get('pollinations', {})
        print(f"⏱️ Pollinations avg response: {pollinations_stats.get('avg_response_time', 0):.2f}s")
        print(f"🔥 Pollinations timeout rate: {pollinations_stats.get('timeout_rate_percent', 0):.1f}%")
    else:
        print("📊 Timeout monitoring disabled")
    
    print("\n" + "=" * 50)
    print("🎯 Performance Summary:")
    
    if pollinations_time < 5:
        print(f"✅ Pollinations API is fast ({pollinations_time:.2f}s)")
    else:
        print(f"⚠️ Pollinations API is slow ({pollinations_time:.2f}s)")
    
    if manager_time < 10:
        print(f"✅ AI Manager is fast ({manager_time:.2f}s)")
    else:
        print(f"⚠️ AI Manager is slow ({manager_time:.2f}s)")
    
    if manager_time - pollinations_time < 2:
        print("✅ Low overhead from AI Manager")
    else:
        print(f"⚠️ High overhead from AI Manager: {manager_time - pollinations_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(test_ai_performance())
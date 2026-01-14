#!/usr/bin/env python3
"""
Test script to verify AI performance improvements

NOTE: Pollinations API has been deprecated. 
This test now focuses on OpenRouter via AI Provider Manager.
"""
import asyncio
import time
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.ai_provider_manager import ai_provider_manager
from ai.openrouter import openrouter_api


async def test_ai_performance():
    """Test AI provider manager performance"""
    
    print("🧪 Testing AI Performance")
    print("=" * 50)
    
    # Test message
    messages = [{'role': 'user', 'content': 'Say hello quickly'}]
    
    # Test 1: Direct OpenRouter API
    print("\n1️⃣ Testing Direct OpenRouter API...")
    start = time.time()
    result = openrouter_api.generate_text(messages=messages, max_tokens=50)
    openrouter_time = time.time() - start
    
    if 'choices' in result and result['choices']:
        content = result['choices'][0]['message']['content']
        print(f"✅ OpenRouter: {openrouter_time:.2f}s")
        print(f"📝 Response: {content[:100]}...")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
        print(f"⏱️ Time: {openrouter_time:.2f}s")
    
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
    
    # Test 4: OpenRouter Rate Limit Status
    print("\n4️⃣ Rate Limit Status:")
    rate_status = openrouter_api.check_rate_limits()
    print(f"📊 Can make request: {rate_status['can_request']}")
    print(f"📊 Requests per minute: {rate_status['requests_per_min']}/{rate_status['rate_limit_per_min']}")
    if rate_status.get('limits'):
        limits = rate_status['limits']
        print(f"📊 Free requests remaining: {limits.get('free_requests_remaining', 'N/A')}")
    
    print("\n" + "=" * 50)
    print("🎯 Performance Summary:")
    
    if openrouter_time < 5:
        print(f"✅ OpenRouter API is fast ({openrouter_time:.2f}s)")
    else:
        print(f"⚠️ OpenRouter API is slow ({openrouter_time:.2f}s)")
    
    if manager_time < 10:
        print(f"✅ AI Manager is fast ({manager_time:.2f}s)")
    else:
        print(f"⚠️ AI Manager is slow ({manager_time:.2f}s)")
    
    overhead = manager_time - openrouter_time
    if overhead < 2:
        print(f"✅ Low overhead from AI Manager ({overhead:.2f}s)")
    else:
        print(f"⚠️ High overhead from AI Manager: {overhead:.2f}s")


if __name__ == "__main__":
    asyncio.run(test_ai_performance())

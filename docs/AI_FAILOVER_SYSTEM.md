# AI Provider Failover System

A comprehensive AI provider failover system that automatically switches between Pollinations and OpenRouter when one fails, with health monitoring, performance tracking, and intelligent load balancing.

## 🚀 Features

### Core Functionality
- **Smart Failover**: Automatic switching between providers when one fails
- **Health Monitoring**: Continuous health checks for all providers
- **Performance Tracking**: Monitor response times, success rates, and quality metrics
- **Load Balancing**: Distribute requests across providers based on performance
- **Circuit Breaker Integration**: Prevent cascading failures with circuit breakers
- **Graceful Degradation**: Fallback strategies when all providers have issues
- **Recovery Logic**: Automatic return to primary provider when healthy

### Provider Support
- **Pollinations AI**: Primary provider with text and image generation
- **OpenRouter AI**: Secondary provider with text generation fallback
- **Extensible Design**: Easy to add new providers

## 📁 Architecture

```
resilience/
├── __init__.py
├── failover_manager.py      # Main failover logic and provider management
├── health_monitor.py        # Continuous health monitoring
└── performance_tracker.py   # Performance metrics and analytics

ai/
└── ai_provider_manager.py   # High-level interface and provider wrappers

tests/
└── test_failover.py         # Comprehensive test suite
```

## 🔧 Usage

### Basic Usage

```python
from ai.ai_provider_manager import ai_provider_manager

# Generate text with automatic failover
messages = [{"role": "user", "content": "Hello! How are you?"}]
result = await ai_provider_manager.generate_text(messages)

if "error" not in result:
    print(f"Response: {result['content']}")
    print(f"Provider used: {result.get('provider', 'Unknown')}")
else:
    print(f"Error: {result['error']}")

# Generate image (Pollinations only)
image_url = await ai_provider_manager.generate_image("A beautiful sunset")
print(f"Image URL: {image_url}")
```

### Advanced Usage

```python
# Prefer specific provider
result = await ai_provider_manager.generate_text(
    messages,
    preferred_provider="openrouter"  # Try OpenRouter first
)

# Generate with custom parameters
result = await ai_provider_manager.generate_text(
    messages,
    model="nvidia/nemotron-nano-9b-v2:free",
    temperature=0.8,
    max_tokens=1500,
    tools=[...],  # Function calling tools
    tool_choice="auto"
)
```

### Health Monitoring

```python
# Check all provider health
health_status = await ai_provider_manager.health_check_all()
for provider, status in health_status.items():
    print(f"{provider}: {'Healthy' if status.healthy else 'Unhealthy'}")
    print(f"Response time: {status.response_time:.3f}s")

# Get comprehensive status
status = ai_provider_manager.get_provider_status()
print(f"Total requests: {status['statistics']['total_requests']}")
print(f"Success rate: {status['statistics']['success_rate']:.1%}")
```

## ⚙️ Configuration

### Environment Variables

```bash
# Pollinations Configuration
POLLINATIONS_API_TOKEN=your_token_here
POLLINATIONS_TEXT_API=https://text.pollinations.ai/openai
POLLINATIONS_IMAGE_API=https://image.pollinations.ai/prompt/

# OpenRouter Configuration
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_ENABLED=true
OPENROUTER_DEFAULT_MODEL=nvidia/nemotron-nano-9b-v2:free

# Rate Limiting
TEXT_API_RATE_LIMIT=20  # requests per minute
IMAGE_API_RATE_LIMIT=20  # requests per minute
```

### Provider Configuration

The system automatically configures providers with these defaults:

#### Pollinations (Primary)
- **Priority**: 1 (highest)
- **Weight**: 2 (preferred in load balancing)
- **Timeout**: 15 seconds
- **Retry Attempts**: 2
- **Circuit Breaker**: Opens after 3 failures
- **Supports**: Text generation, Image generation, Function calling

#### OpenRouter (Secondary)
- **Priority**: 2 (fallback)
- **Weight**: 1 (lower preference)
- **Timeout**: 30 seconds
- **Retry Attempts**: 1
- **Circuit Breaker**: Opens after 3 failures
- **Supports**: Text generation, Function calling

## 📊 Monitoring & Statistics

### Performance Metrics

```python
# Get detailed statistics
stats = ai_provider_manager.get_statistics()

print(f"Total requests: {stats['total_requests']}")
print(f"Successful requests: {stats['successful_requests']}")
print(f"Failover count: {stats['failover_count']}")
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Provider usage: {stats['provider_usage']}")
```

### Health Status

```python
# Get provider health
status = ai_provider_manager.get_provider_status()

for provider_name, provider_info in status['providers'].items():
    print(f"\n{provider_name}:")
    print(f"  Enabled: {provider_info['enabled']}")
    print(f"  Usage count: {provider_info['usage_count']}")
    
    if provider_info.get('health'):
        health = provider_info['health']
        print(f"  Health: {health['status']}")
        print(f"  Consecutive failures: {health['consecutive_failures']}")
        print(f"  Last check: {health['last_check']}")
    
    if provider_info.get('performance'):
        perf = provider_info['performance']
        print(f"  Success rate: {perf['success_rate']:.1%}")
        print(f"  Avg response time: {perf['average_response_time']:.3f}s")
        print(f"  Requests/min: {perf['requests_per_minute']:.1f}")
```

## 🔄 Failover Strategies

The system supports multiple failover strategies:

### Primary Only (Default)
- Always tries providers in priority order
- Pollinations → OpenRouter
- Best for reliability and cost control

### Round Robin
- Cycles through available providers
- Good for load distribution

### Best Performance
- Routes to provider with best performance metrics
- Optimizes for speed and success rate

### Weighted Round Robin
- Distributes based on provider weights and performance
- Balances preference with performance

### Random Available
- Randomly selects from healthy providers
- Maximum distribution

```python
# Change failover strategy
from resilience.failover_manager import FailoverStrategy

ai_provider_manager.set_failover_strategy(FailoverStrategy.BEST_PERFORMANCE)
```

## 🛠️ Management Operations

### Provider Management

```python
# Disable a provider
ai_provider_manager.disable_provider("pollinations")

# Enable a provider
ai_provider_manager.enable_provider("openrouter")

# Force health check
await ai_provider_manager.force_health_check("pollinations")
```

### Statistics Management

```python
# Reset all statistics
ai_provider_manager.reset_statistics()

# Get current statistics
stats = ai_provider_manager.get_statistics()
```

## 🧪 Testing

### Run Tests

```bash
# Run comprehensive test suite
python test_failover_simple.py

# Run specific test categories
python -m tests.test_failover TestFailoverBasic
python -m tests.test_failover TestFailoverLogic
python -m tests.test_failover TestIntegration
```

### Test Coverage

The test suite covers:
- ✅ Provider registration and configuration
- ✅ Failover logic and decision making
- ✅ Health monitoring and status tracking
- ✅ Performance metrics and analytics
- ✅ Circuit breaker functionality
- ✅ Load balancing strategies
- ✅ End-to-end integration scenarios
- ✅ Error handling and edge cases

## 🔍 Troubleshooting

### Common Issues

#### Provider Always Fails
```python
# Check provider health
health = await ai_provider_manager.health_check_all()
print(health)

# Check configuration
status = ai_provider_manager.get_provider_status()
print(status['providers'])
```

#### High Failover Rate
```python
# Check performance metrics
stats = ai_provider_manager.get_statistics()
print(f"Failover count: {stats['failover_count']}")

# Check circuit breaker status
status = ai_provider_manager.get_provider_status()
for provider, info in status['providers'].items():
    if info.get('circuit_breaker'):
        cb = info['circuit_breaker']
        print(f"{provider}: {cb['state']} (failures: {cb['failure_count']})")
```

#### Slow Response Times
```python
# Check performance metrics
status = ai_provider_manager.get_provider_status()
for provider, info in status['providers'].items():
    if info.get('performance'):
        perf = info['performance']
        print(f"{provider}: {perf['average_response_time']:.3f}s avg")
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('ai.ai_provider_manager').setLevel(logging.DEBUG)
logging.getLogger('resilience').setLevel(logging.DEBUG)
```

## 🚀 Production Deployment

### Best Practices

1. **Monitor Health**: Regularly check provider health and performance
2. **Set Appropriate Timeouts**: Configure timeouts based on your use case
3. **Circuit Breaker Thresholds**: Adjust based on expected failure rates
4. **Rate Limiting**: Respect provider rate limits
5. **Error Handling**: Always check for errors in responses
6. **Statistics Tracking**: Monitor usage and performance trends

### Monitoring Setup

```python
# Set up periodic health checks
import asyncio

async def monitor_system():
    while True:
        # Check health
        health = await ai_provider_manager.health_check_all()
        
        # Log any issues
        for provider, status in health.items():
            if not status.healthy:
                logger.warning(f"Provider {provider} unhealthy: {status.error_message}")
        
        # Wait before next check
        await asyncio.sleep(60)  # Check every minute

# Start monitoring
asyncio.create_task(monitor_system())
```

## 📈 Performance Optimization

### Tips for Better Performance

1. **Use Preferred Provider**: Specify preferred provider when you know one is better
2. **Adjust Timeouts**: Set appropriate timeouts for your use case
3. **Monitor Metrics**: Use performance data to optimize provider selection
4. **Cache Results**: Cache responses when appropriate
5. **Batch Requests**: Group multiple requests when possible

### Example Optimization

```python
# Optimized text generation with preferred provider
result = await ai_provider_manager.generate_text(
    messages,
    preferred_provider="pollinations",  # Use faster provider first
    temperature=0.7,
    max_tokens=1000
)

# Check if failover occurred
if result.get('failover_occurred'):
    logger.info(f"Failover used: {result['provider_used']}")
```

## 🔮 Future Enhancements

Planned improvements:
- [ ] Additional provider integrations (Claude, Gemini, etc.)
- [ ] Advanced load balancing algorithms
- [ ] Real-time performance dashboards
- [ ] Automatic provider preference learning
- [ ] Geographic routing optimization
- [ ] Cost-aware routing
- [ ] Advanced caching strategies
- [ ] Custom health check endpoints

## 📝 License

This failover system is part of the JakeySelfBot project and follows the same licensing terms.

---

**Built with ❤️ for reliable AI provider management**
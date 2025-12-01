# Integration Testing Enhancement Plan

## Current Issues
- **Limited integration tests**: Mostly unit tests for individual components
- **No end-to-end user flows**: Missing tests for complete user interactions
- **Mock-heavy testing**: External dependencies not tested in realistic scenarios
- **No performance testing**: Integration tests don't cover performance requirements
- **Manual testing burden**: Complex scenarios require manual verification

## Proposed Integration Testing Framework

```python
# tests/integration/__init__.py
import pytest
from typing import Dict, Any
from unittest.mock import MagicMock

class IntegrationTestHarness:
    """Test harness for end-to-end integration testing"""

    def __init__(self):
        self.mock_discord = None
        self.mock_apis = {}
        self.test_database = None
        self.bot_instance = None

    async def setup_full_bot(self) -> 'JakeyBot':
        """Set up complete bot with all dependencies for integration testing"""
        # Create isolated test database
        # Mock external APIs
        # Initialize bot with test configuration
        # Return configured bot instance

    async def simulate_user_message(self, content: str, user_id: str = "test_user",
                                  channel_id: str = "test_channel") -> Dict[str, Any]:
        """Simulate a user message and return bot response"""
        # Create mock Discord message
        # Send through bot processing
        # Return response data

    def assert_response_quality(self, response: str, expected_characteristics: Dict[str, Any]):
        """Assert response meets quality standards"""
        # Check response length
        # Check for appropriate content
        # Check for error handling
        # Check performance metrics
```

## Critical User Flow Tests

### Message Processing Flow
```python
# tests/integration/test_message_flows.py
class TestMessageProcessingFlows:

    @pytest.mark.asyncio
    async def test_basic_ai_response_flow(self, harness):
        """Test complete flow: user message → AI processing → response"""
        # Arrange
        user_message = "%ask What is the capital of France?"

        # Act
        response = await harness.simulate_user_message(user_message)

        # Assert
        assert "Paris" in response.content
        assert response.processing_time < 5.0  # Performance requirement
        assert harness.mock_apis["pollinations"].called

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, harness):
        """Test rate limiting works across message processing"""
        # Arrange
        messages = ["%ask test"] * 25  # Exceed rate limit

        # Act & Assert
        responses = []
        for msg in messages:
            response = await harness.simulate_user_message(msg, user_id="rate_limit_test")
            responses.append(response)

        # Should have rate limited responses
        rate_limited = [r for r in responses if "rate limit" in r.content.lower()]
        assert len(rate_limited) > 0

    @pytest.mark.asyncio
    async def test_ai_failover_flow(self, harness):
        """Test AI provider failover during message processing"""
        # Arrange
        harness.mock_apis["pollinations"].set_failure_mode("timeout")

        # Act
        response = await harness.simulate_user_message("%ask Test failover")

        # Assert
        assert response.content is not None  # Should still get response
        assert harness.mock_apis["openrouter"].called  # Fallback triggered
        assert "failover" in harness.get_logs()  # Should log failover

    @pytest.mark.asyncio
    async def test_memory_integration_flow(self, harness):
        """Test memory system integration in conversations"""
        # Arrange
        harness.enable_memory_system()

        # Act: Multi-turn conversation
        await harness.simulate_user_message("%remember My favorite color is blue")
        response = await harness.simulate_user_message("%ask What is my favorite color?")

        # Assert
        assert "blue" in response.content
        assert harness.memory_system.was_queried()
```

### Command Integration Tests
```python
# tests/integration/test_command_flows.py
class TestCommandIntegrationFlows:

    @pytest.mark.asyncio
    async def test_image_generation_flow(self, harness):
        """Test complete image generation command flow"""
        # Arrange
        prompt = "%image A beautiful sunset over mountains"

        # Act
        response = await harness.simulate_user_message(prompt)

        # Assert
        assert "image" in response.embeds[0].url if response.embeds else False
        assert harness.mock_apis["pollinations"].image_called
        assert response.processing_time < 10.0

    @pytest.mark.asyncio
    async def test_crypto_balance_flow(self, harness):
        """Test cryptocurrency balance checking flow"""
        # Arrange
        harness.mock_apis["coinmarketcap"].set_balance("100.50")

        # Act
        response = await harness.simulate_user_message("%balance")

        # Assert
        assert "100.50" in response.content
        assert harness.database.balance_was_logged()

    @pytest.mark.asyncio
    async def test_reminder_system_flow(self, harness):
        """Test reminder creation and triggering flow"""
        # Arrange
        reminder_time = datetime.now() + timedelta(minutes=1)

        # Act
        create_response = await harness.simulate_user_message(
            f"%remind me in 1 minute: Test reminder"
        )
        await harness.advance_time(minutes=1)  # Simulate time passing
        reminder_triggered = await harness.check_reminders()

        # Assert
        assert "reminder set" in create_response.content.lower()
        assert len(reminder_triggered) == 1
        assert "Test reminder" in reminder_triggered[0].content
```

### Resilience & Recovery Tests
```python
# tests/integration/test_resilience_flows.py
class TestResilienceFlows:

    @pytest.mark.asyncio
    async def test_database_connection_recovery(self, harness):
        """Test database connection loss and recovery"""
        # Arrange
        harness.database.set_failure_mode("connection_lost")

        # Act
        response1 = await harness.simulate_user_message("%ask Test query")
        harness.database.restore_connection()
        response2 = await harness.simulate_user_message("%ask Test query after recovery")

        # Assert
        assert "error" in response1.content.lower()  # First should fail gracefully
        assert response2.content is not None  # Second should succeed

    @pytest.mark.asyncio
    async def test_external_api_timeout_recovery(self, harness):
        """Test external API timeout and recovery"""
        # Arrange
        harness.mock_apis["pollinations"].set_timeout_mode(30)  # Long timeout

        # Act
        start_time = time.time()
        response = await harness.simulate_user_message("%ask Test timeout")
        end_time = time.time()

        # Assert
        assert end_time - start_time < 35  # Should timeout gracefully
        assert "timeout" in response.content.lower() or "error" in response.content.lower()

    @pytest.mark.asyncio
    async def test_memory_system_fallback(self, harness):
        """Test memory system fallback when MCP server unavailable"""
        # Arrange
        harness.memory_system.set_mcp_server_offline()

        # Act
        response = await harness.simulate_user_message("%remember Test memory")

        # Assert
        assert response.content is not None  # Should still work
        assert harness.database.memory_was_stored()  # Fallback to SQLite
```

## Performance Integration Tests
```python
# tests/integration/test_performance_flows.py
class TestPerformanceFlows:

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_user_load(self, harness):
        """Test bot performance under concurrent user load"""
        # Arrange
        num_users = 50
        messages_per_user = 5

        # Act
        start_time = time.time()
        tasks = []
        for user_id in range(num_users):
            for msg_num in range(messages_per_user):
                task = harness.simulate_user_message(
                    f"%ask Performance test {msg_num}",
                    user_id=f"user_{user_id}"
                )
                tasks.append(task)

        responses = await asyncio.gather(*tasks)
        end_time = time.time()

        # Assert
        total_time = end_time - start_time
        avg_response_time = total_time / len(tasks)
        assert avg_response_time < 2.0  # Performance requirement
        assert all(r.content for r in responses)  # All should succeed

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_usage_under_load(self, harness):
        """Test memory usage during sustained load"""
        # Arrange
        initial_memory = harness.get_memory_usage()

        # Act: Sustained load
        for i in range(100):
            await harness.simulate_user_message(f"%ask Load test {i}")
            if i % 10 == 0:  # Check memory every 10 requests
                current_memory = harness.get_memory_usage()
                memory_increase = current_memory - initial_memory
                assert memory_increase < 50 * 1024 * 1024  # < 50MB increase

        # Assert
        final_memory = harness.get_memory_usage()
        total_increase = final_memory - initial_memory
        assert total_increase < 100 * 1024 * 1024  # < 100MB total increase
```

## Test Infrastructure Improvements

### Enhanced Test Fixtures
```python
# tests/conftest.py
@pytest.fixture(scope="session")
async def integration_harness():
    """Session-scoped integration test harness"""
    harness = IntegrationTestHarness()
    await harness.setup_full_bot()
    yield harness
    await harness.cleanup()

@pytest.fixture
async def mock_external_apis():
    """Mock external API responses"""
    with patch('aiohttp.ClientSession') as mock_session:
        # Configure mock responses
        yield mock_session
```

### Test Configuration
```python
# tests/integration_config.py
INTEGRATION_TEST_CONFIG = {
    "database": {
        "path": ":memory:",  # Use in-memory database for tests
        "enable_mcp_memory": False,  # Disable MCP for faster tests
    },
    "ai": {
        "mock_responses": True,  # Use mock AI responses
        "fast_timeout": 0.1,  # Fast timeouts for tests
    },
    "rate_limiting": {
        "disabled": True,  # Disable rate limiting in tests
    }
}
```

## Implementation Strategy

### Phase 1: Infrastructure Setup (High Priority)
- Create `IntegrationTestHarness` class
- Set up mock external APIs
- Create isolated test databases
- Add performance measurement utilities

### Phase 2: Core Flow Tests (High Priority)
- Implement message processing flow tests
- Add command integration tests
- Create basic resilience tests

### Phase 3: Advanced Scenarios (Medium Priority)
- Add concurrent load testing
- Implement memory usage monitoring
- Create complex multi-step user flows

### Phase 4: CI/CD Integration (Low Priority)
- Add integration tests to CI pipeline
- Create performance regression detection
- Add automated reporting and alerting

## Benefits
- **Confidence**: Verify complete user flows work end-to-end
- **Regression Detection**: Catch integration issues early
- **Performance Monitoring**: Ensure system meets performance requirements
- **Documentation**: Tests serve as living documentation of expected behavior
- **Debugging**: Easier to isolate issues in complex interactions
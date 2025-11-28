"""
Comprehensive test suite for the AI provider failover system.
"""
import asyncio
import time
import unittest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any


class MockAIProvider:
    """Mock AI provider for testing."""
    
    def __init__(self, name: str, should_fail: bool = False, response_time: float = 0.1):
        self.name = name
        self.should_fail = should_fail
        self.response_time = response_time
        self.call_count = 0
    
    async def generate_text(self, messages, **kwargs):
        """Mock text generation."""
        self.call_count += 1
        await asyncio.sleep(self.response_time)
        
        if self.should_fail:
            raise Exception(f"Provider {self.name} failed")
        
        return {"content": f"Response from {self.name}", "model": "test-model"}
    
    async def generate_image(self, prompt, **kwargs):
        """Mock image generation."""
        self.call_count += 1
        await asyncio.sleep(self.response_time)
        
        if self.should_fail:
            raise Exception(f"Provider {self.name} failed")
        
        return f"https://example.com/image/{self.name}.png"
    
    def check_service_health(self):
        """Mock health check."""
        return {
            "healthy": not self.should_fail,
            "status": "ok" if not self.should_fail else "unhealthy",
            "response_time": self.response_time
        }


class TestFailoverBasic(unittest.TestCase):
    """Basic failover functionality tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.provider1 = MockAIProvider("provider1", should_fail=False, response_time=0.1)
        self.provider2 = MockAIProvider("provider2", should_fail=False, response_time=0.2)
        self.provider3 = MockAIProvider("provider3", should_fail=True, response_time=0.3)
    
    def test_provider_creation(self):
        """Test mock provider creation."""
        self.assertEqual(self.provider1.name, "provider1")
        self.assertFalse(self.provider1.should_fail)
        self.assertEqual(self.provider1.response_time, 0.1)
        self.assertEqual(self.provider1.call_count, 0)
    
    def test_successful_text_generation(self):
        """Test successful text generation."""
        async def test_generation():
            result = await self.provider1.generate_text([{"role": "user", "content": "test"}])
            
            self.assertEqual(result["content"], "Response from provider1")
            self.assertEqual(result["model"], "test-model")
            self.assertEqual(self.provider1.call_count, 1)
        
        asyncio.run(test_generation())
    
    def test_failed_text_generation(self):
        """Test failed text generation."""
        async def test_failure():
            with self.assertRaises(Exception):
                await self.provider3.generate_text([{"role": "user", "content": "test"}])
            
            self.assertEqual(self.provider3.call_count, 1)
        
        asyncio.run(test_failure())
    
    def test_successful_image_generation(self):
        """Test successful image generation."""
        async def test_generation():
            result = await self.provider1.generate_image("test prompt")
            
            self.assertEqual(result, "https://example.com/image/provider1.png")
            self.assertEqual(self.provider1.call_count, 1)
        
        asyncio.run(test_generation())
    
    def test_health_check(self):
        """Test health check functionality."""
        health = self.provider1.check_service_health()
        
        self.assertTrue(health["healthy"])
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["response_time"], 0.1)
        
        # Test failing provider
        health_failing = self.provider3.check_service_health()
        self.assertFalse(health_failing["healthy"])
        self.assertEqual(health_failing["status"], "unhealthy")


class TestFailoverLogic(unittest.TestCase):
    """Test failover logic and decision making."""
    
    def setUp(self):
        """Set up test environment."""
        self.providers = {
            "primary": MockAIProvider("primary", should_fail=False, response_time=0.1),
            "secondary": MockAIProvider("secondary", should_fail=False, response_time=0.2),
            "tertiary": MockAIProvider("tertiary", should_fail=False, response_time=0.3)
        }
    
    def test_provider_selection_by_priority(self):
        """Test provider selection based on priority."""
        providers_config = [
            {"name": "primary", "priority": 1},
            {"name": "secondary", "priority": 2},
            {"name": "tertiary", "priority": 3}
        ]
        
        # Sort by priority (lower number = higher priority)
        sorted_providers = sorted(providers_config, key=lambda x: x["priority"])
        expected_order = ["primary", "secondary", "tertiary"]
        actual_order = [p["name"] for p in sorted_providers]
        
        self.assertEqual(actual_order, expected_order)
    
    def test_provider_selection_by_performance(self):
        """Test provider selection based on performance."""
        provider_performance = {
            "primary": {"response_time": 0.1, "success_rate": 0.95},
            "secondary": {"response_time": 0.2, "success_rate": 0.90},
            "tertiary": {"response_time": 0.3, "success_rate": 0.85}
        }
        
        # Calculate performance score: success_rate * 100 - response_time * 10
        def calculate_score(perf):
            return (perf["success_rate"] * 100) - (perf["response_time"] * 10)
        
        scores = {
            name: calculate_score(perf) 
            for name, perf in provider_performance.items()
        }
        
        # Sort by score (higher is better)
        best_provider = max(scores.keys(), key=lambda x: scores[x])
        
        self.assertEqual(best_provider, "primary")
    
    def test_round_robin_selection(self):
        """Test round-robin provider selection."""
        providers = ["provider1", "provider2", "provider3"]
        index = 0
        
        # Simulate round-robin selection
        selections = []
        for i in range(6):
            selected = providers[index % len(providers)]
            selections.append(selected)
            index += 1
        
        expected = ["provider1", "provider2", "provider3", "provider1", "provider2", "provider3"]
        self.assertEqual(selections, expected)
    
    def test_failover_scenario(self):
        """Test failover when primary provider fails."""
        async def test_failover():
            primary_provider = MockAIProvider("primary", should_fail=True)
            secondary_provider = MockAIProvider("secondary", should_fail=False)
            
            # Try primary first
            try:
                await primary_provider.generate_text([{"role": "user", "content": "test"}])
                self.fail("Primary provider should have failed")
            except Exception:
                pass  # Expected
            
            # Fall back to secondary
            result = await secondary_provider.generate_text([{"role": "user", "content": "test"}])
            
            self.assertEqual(result["content"], "Response from secondary")
            self.assertEqual(primary_provider.call_count, 1)
            self.assertEqual(secondary_provider.call_count, 1)
        
        asyncio.run(test_failover())


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions."""
        class MockCircuitBreaker:
            def __init__(self, failure_threshold=5):
                self.failure_threshold = failure_threshold
                self.failure_count = 0
                self.state = "closed"  # closed, open, half_open
            
            def record_failure(self):
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
            
            def record_success(self):
                self.failure_count = 0
                self.state = "closed"
            
            def is_open(self):
                return self.state == "open"
        
        circuit_breaker = MockCircuitBreaker(failure_threshold=3)
        
        # Initially closed
        self.assertEqual(circuit_breaker.state, "closed")
        self.assertFalse(circuit_breaker.is_open())
        
        # Record failures
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        self.assertEqual(circuit_breaker.state, "closed")
        self.assertFalse(circuit_breaker.is_open())
        
        # Third failure opens circuit
        circuit_breaker.record_failure()
        self.assertEqual(circuit_breaker.state, "open")
        self.assertTrue(circuit_breaker.is_open())
        
        # Success closes circuit
        circuit_breaker.record_success()
        self.assertEqual(circuit_breaker.state, "closed")
        self.assertFalse(circuit_breaker.is_open())


class TestPerformanceTracking(unittest.TestCase):
    """Test performance tracking functionality."""
    
    def test_metric_recording(self):
        """Test metric recording and calculation."""
        class MockPerformanceTracker:
            def __init__(self):
                self.metrics = []
            
            def record_metric(self, provider, operation, response_time, success):
                self.metrics.append({
                    "provider": provider,
                    "operation": operation,
                    "response_time": response_time,
                    "success": success,
                    "timestamp": time.time()
                })
            
            def get_provider_stats(self, provider):
                provider_metrics = [m for m in self.metrics if m["provider"] == provider]
                if not provider_metrics:
                    return None
                
                total_requests = len(provider_metrics)
                successful_requests = sum(1 for m in provider_metrics if m["success"])
                success_rate = successful_requests / total_requests
                avg_response_time = sum(m["response_time"] for m in provider_metrics) / total_requests
                
                return {
                    "provider": provider,
                    "total_requests": total_requests,
                    "successful_requests": successful_requests,
                    "success_rate": success_rate,
                    "average_response_time": avg_response_time
                }
        
        tracker = MockPerformanceTracker()
        
        # Record some metrics
        tracker.record_metric("provider1", "generate_text", 0.1, True)
        tracker.record_metric("provider1", "generate_text", 0.15, True)
        tracker.record_metric("provider1", "generate_text", 0.2, False)
        tracker.record_metric("provider2", "generate_text", 0.3, True)
        
        # Check provider1 stats
        stats1 = tracker.get_provider_stats("provider1")
        self.assertEqual(stats1["total_requests"], 3)
        self.assertEqual(stats1["successful_requests"], 2)
        self.assertAlmostEqual(stats1["success_rate"], 2/3, places=2)
        self.assertAlmostEqual(stats1["average_response_time"], 0.15, places=2)
        
        # Check provider2 stats
        stats2 = tracker.get_provider_stats("provider2")
        self.assertEqual(stats2["total_requests"], 1)
        self.assertEqual(stats2["successful_requests"], 1)
        self.assertEqual(stats2["success_rate"], 1.0)
    
    def test_best_provider_selection(self):
        """Test best provider selection based on performance."""
        provider_stats = {
            "provider1": {"success_rate": 0.95, "average_response_time": 0.1},
            "provider2": {"success_rate": 0.90, "average_response_time": 0.2},
            "provider3": {"success_rate": 0.85, "average_response_time": 0.15}
        }
        
        # Calculate performance score
def calculate_score(perf):
                return (perf["success_rate"] * 100) - (perf["avg_response_time"] * 10)
            
            scores = {
                name: calculate_score(perf) 
                for name, perf in provider_performance.items()
            }
            
            best_provider_name = max(scores.keys(), key=lambda x: scores[x])
            best_provider = fast_provider if best_provider_name == "fast" else slow_provider
            
            # Make request with best provider
            result = await best_provider.generate_text([{"role": "user", "content": "test"}])
            
            self.assertEqual(result["content"], "Response from fast")
            self.assertEqual(best_provider_name, "fast")
        
        asyncio.run(test_performance_routing())


if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
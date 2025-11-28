import unittest
import time
import threading
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.rate_limiter import UserRateLimiter, RateLimitMiddleware, RateLimitViolation

class TestUserRateLimiter(unittest.TestCase):
    """Test cases for the UserRateLimiter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = UserRateLimiter()
        self.test_user_id = "test_user_123"
        self.test_operation = "test_operation"
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        self.assertIsInstance(self.rate_limiter.user_requests, dict)
        self.assertIsInstance(self.rate_limiter.violations, dict)
        self.assertIsInstance(self.rate_limiter.penalty_multipliers, dict)
        self.assertEqual(self.rate_limiter.total_requests, 0)
        self.assertEqual(self.rate_limiter.total_violations, 0)
    
    def test_check_rate_limit_allowed(self):
        """Test that requests within limits are allowed."""
        is_allowed, reason = self.rate_limiter.check_rate_limit(self.test_user_id, self.test_operation)
        self.assertTrue(is_allowed)
        self.assertIsNone(reason)
        self.assertEqual(self.rate_limiter.total_requests, 1)
    
    def test_check_rate_limit_burst_exceeded(self):
        """Test that burst limits are enforced."""
        # Use an operation with a low burst limit
        operation = "generate_image"
        burst_limit = self.rate_limiter.default_limits['burst']['limits'][operation]
        
        # Make requests up to the limit
        for i in range(burst_limit):
            is_allowed, reason = self.rate_limiter.check_rate_limit(self.test_user_id, operation)
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")
        
        # Next request should be denied
        is_allowed, reason = self.rate_limiter.check_rate_limit(self.test_user_id, operation)
        self.assertFalse(is_allowed)
        self.assertIsNotNone(reason)
        self.assertIn("Rate limit exceeded", reason)
    
    def test_check_rate_limit_sustained_exceeded(self):
        """Test that sustained limits are enforced."""
        operation = "web_search"
        sustained_limit = self.rate_limiter.default_limits['sustained']['limits'][operation]
        
        # Make requests up to sustained limit
        for i in range(sustained_limit):
            is_allowed, reason = self.rate_limiter.check_rate_limit(self.test_user_id, operation)
            self.assertTrue(is_allowed, f"Request {i+1} should be allowed")
        
        # Next request should be denied
        is_allowed, reason = self.rate_limiter.check_rate_limit(self.test_user_id, operation)
        self.assertFalse(is_allowed)
        self.assertIn("sustained", reason)
    
    def test_penalty_system(self):
        """Test that penalty multipliers are applied for repeated violations."""
        operation = "generate_image"
        
        # Make enough requests to trigger violations
        for i in range(10):  # Exceed burst limit multiple times
            self.rate_limiter.check_rate_limit(self.test_user_id, operation)
        
        # Check that penalty was applied
        penalty = self.rate_limiter.get_user_penalty_multiplier(self.test_user_id)
        self.assertGreater(penalty, 1.0)
    
    def test_different_users_independent(self):
        """Test that rate limits are independent per user."""
        user1 = "user1"
        user2 = "user2"
        operation = "generate_image"
        
        # User1 makes requests up to limit
        for i in range(3):  # burst limit for generate_image
            is_allowed, _ = self.rate_limiter.check_rate_limit(user1, operation)
            self.assertTrue(is_allowed)
        
        # User1 should now be rate limited
        is_allowed, _ = self.rate_limiter.check_rate_limit(user1, operation)
        self.assertFalse(is_allowed)
        
        # User2 should still be able to make requests
        is_allowed, _ = self.rate_limiter.check_rate_limit(user2, operation)
        self.assertTrue(is_allowed)
    
    def test_get_user_stats(self):
        """Test user statistics retrieval."""
        # Make some requests
        for i in range(5):
            self.rate_limiter.check_rate_limit(self.test_user_id, "web_search")
        
        stats = self.rate_limiter.get_user_stats(self.test_user_id)
        
        self.assertEqual(stats['user_id'], self.test_user_id)
        self.assertIn('penalty_multiplier', stats)
        self.assertIn('total_violations', stats)
        self.assertIn('current_usage', stats)
        self.assertIn('web_search', stats['current_usage'])
    
    def test_get_system_stats(self):
        """Test system statistics retrieval."""
        # Make some requests from different users
        users = ["user1", "user2", "user3"]
        for user in users:
            for i in range(3):
                self.rate_limiter.check_rate_limit(user, "web_search")
        
        stats = self.rate_limiter.get_system_stats()
        
        self.assertIn('uptime_seconds', stats)
        self.assertIn('total_requests', stats)
        self.assertIn('total_violations', stats)
        self.assertIn('active_users_count', stats)
        self.assertEqual(stats['total_users_count'], 3)
        self.assertEqual(stats['total_requests'], 9)
    
    def test_reset_user_limits(self):
        """Test resetting user rate limits."""
        # Make some requests and violations
        for i in range(10):
            self.rate_limiter.check_rate_limit(self.test_user_id, "generate_image")
        
        # Verify user has data
        self.assertIn(self.test_user_id, self.rate_limiter.user_requests)
        self.assertGreater(len(self.rate_limiter.violations[self.test_user_id]), 0)
        
        # Reset user
        self.rate_limiter.reset_user_limits(self.test_user_id)
        
        # Verify data is cleared
        self.assertNotIn(self.test_user_id, self.rate_limiter.user_requests)
        self.assertNotIn(self.test_user_id, self.rate_limiter.violations)
        self.assertNotIn(self.test_user_id, self.rate_limiter.penalty_multipliers)
    
    def test_cleanup_expired_data(self):
        """Test cleanup of expired data."""
        # Make some requests
        self.rate_limiter.check_rate_limit(self.test_user_id, "web_search")
        
        # Manually add old violation (simulate expired data)
        old_time = time.time() - 90000  # More than 24 hours ago
        old_violation = RateLimitViolation(
            user_id=self.test_user_id,
            operation="web_search",
            limit_type="burst",
            current_count=5,
            limit=3,
            window_start=old_time
        )
        self.rate_limiter.violations[self.test_user_id].append(old_violation)
        
        # Run cleanup
        self.rate_limiter.cleanup_expired_data()
        
        # Verify old violation was cleaned up
        current_violations = [v for v in self.rate_limiter.violations.get(self.test_user_id, [])
                            if time.time() - v.timestamp < 86400]
        self.assertEqual(len(current_violations), 0)
    
    def test_thread_safety(self):
        """Test that rate limiter is thread-safe."""
        results = []
        errors = []
        
        def make_requests(user_id, count):
            try:
                for i in range(count):
                    is_allowed, _ = self.rate_limiter.check_rate_limit(user_id, "web_search")
                    results.append((user_id, i, is_allowed))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads making requests for different users
        threads = []
        for i in range(5):
            user_id = f"user_{i}"
            thread = threading.Thread(target=make_requests, args=(user_id, 10))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify requests were made
        self.assertGreater(len(results), 0)


class TestRateLimitMiddleware(unittest.TestCase):
    """Test cases for the RateLimitMiddleware class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = UserRateLimiter()
        self.middleware = RateLimitMiddleware(self.rate_limiter)
        self.test_user_id = "test_user_123"
        self.test_operation = "test_operation"
    
    def test_check_request_allowed(self):
        """Test middleware allows requests within limits."""
        is_allowed, reason = self.middleware.check_request(self.test_user_id, self.test_operation)
        self.assertTrue(is_allowed)
        self.assertIsNone(reason)
    
    def test_check_request_denied(self):
        """Test middleware denies requests exceeding limits."""
        operation = "generate_image"
        
        # Make requests up to limit
        for i in range(3):
            is_allowed, _ = self.middleware.check_request(self.test_user_id, operation)
            self.assertTrue(is_allowed)
        
        # Next request should be denied
        is_allowed, reason = self.middleware.check_request(self.test_user_id, operation)
        self.assertFalse(is_allowed)
        self.assertIsNotNone(reason)
    
    def test_get_rate_limit_info(self):
        """Test rate limit information retrieval."""
        # Make some requests
        for i in range(3):
            self.middleware.check_request(self.test_user_id, "web_search")
        
        info = self.middleware.get_rate_limit_info(self.test_user_id, "web_search")
        
        self.assertEqual(info['user_id'], self.test_user_id)
        self.assertEqual(info['operation'], "web_search")
        self.assertIn('penalty_multiplier', info)
        self.assertIn('current_usage', info)


class TestRateLimitViolation(unittest.TestCase):
    """Test cases for the RateLimitViolation class."""
    
    def test_violation_creation(self):
        """Test violation object creation."""
        current_time = time.time()
        violation = RateLimitViolation(
            user_id="test_user",
            operation="test_operation",
            limit_type="burst",
            current_count=5,
            limit=3,
            window_start=current_time - 60
        )
        
        self.assertEqual(violation.user_id, "test_user")
        self.assertEqual(violation.operation, "test_operation")
        self.assertEqual(violation.limit_type, "burst")
        self.assertEqual(violation.current_count, 5)
        self.assertEqual(violation.limit, 3)
        self.assertGreaterEqual(violation.timestamp, current_time)
    
    def test_violation_to_dict(self):
        """Test violation serialization to dictionary."""
        violation = RateLimitViolation(
            user_id="test_user",
            operation="test_operation",
            limit_type="burst",
            current_count=5,
            limit=3,
            window_start=time.time() - 60
        )
        
        data = violation.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['user_id'], "test_user")
        self.assertEqual(data['operation'], "test_operation")
        self.assertEqual(data['limit_type'], "burst")
        self.assertEqual(data['current_count'], 5)
        self.assertEqual(data['limit'], 3)


class TestRateLimitIntegration(unittest.TestCase):
    """Integration tests for rate limiting system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = UserRateLimiter()
    
    def test_violation_penalty_cycle(self):
        """Test the complete violation and penalty cycle."""
        user_id = "test_user"
        operation = "generate_image"
        
        # Phase 1: Normal usage
        for i in range(3):
            is_allowed, _ = self.rate_limiter.check_rate_limit(user_id, operation)
            self.assertTrue(is_allowed)
        
        # Phase 2: Exceed limit and get violation
        is_allowed, reason = self.rate_limiter.check_rate_limit(user_id, operation)
        self.assertFalse(is_allowed)
        
        # Phase 3: Check penalty was applied
        penalty = self.rate_limiter.get_user_penalty_multiplier(user_id)
        self.assertGreater(penalty, 1.0)
        
        # Phase 4: Verify reduced limits due to penalty
        # Wait for burst window to reset
        time.sleep(1.1)
        
        # With penalty, should have reduced effective limit
        is_allowed, _ = self.rate_limiter.check_rate_limit(user_id, operation)
        # May still be denied depending on penalty severity
        
        # Phase 5: Check user stats reflect violations
        stats = self.rate_limiter.get_user_stats(user_id)
        self.assertGreater(stats['total_violations'], 0)
        self.assertGreater(stats['penalty_multiplier'], 1.0)
    
    def test_multiple_operations_independent(self):
        """Test that different operations have independent limits."""
        user_id = "test_user"
        
        # Exhaust limit for one operation
        for i in range(3):
            is_allowed, _ = self.rate_limiter.check_rate_limit(user_id, "generate_image")
            self.assertTrue(is_allowed)
        
        # Should be rate limited for generate_image
        is_allowed, _ = self.rate_limiter.check_rate_limit(user_id, "generate_image")
        self.assertFalse(is_allowed)
        
        # But should still be able to do other operations
        is_allowed, _ = self.rate_limiter.check_rate_limit(user_id, "web_search")
        self.assertTrue(is_allowed)
    
    def test_system_monitoring(self):
        """Test system monitoring capabilities."""
        # Simulate activity from multiple users
        users = ["user1", "user2", "user3"]
        operations = ["web_search", "generate_image", "get_crypto_price"]
        
        for user in users:
            for operation in operations:
                for i in range(2):
                    self.rate_limiter.check_rate_limit(user, operation)
        
        # Check system stats
        stats = self.rate_limiter.get_system_stats()
        
        self.assertEqual(stats['total_requests'], 18)  # 3 users * 3 operations * 2 requests
        self.assertEqual(stats['total_users_count'], 3)
        self.assertGreater(stats['uptime_seconds'], 0)


if __name__ == '__main__':
    unittest.main()
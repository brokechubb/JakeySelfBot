import unittest
import asyncio
import tempfile
import os
import time
from unittest.mock import Mock, AsyncMock, patch
import sys
import json

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the modules directly
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'resilience'))

from message_queue import MessageQueue, QueueMessage, MessagePriority, MessageStatus
from retry_handler import RetryHandler, BackoffStrategy, AdaptiveRetryHandler
from queue_processor import QueueProcessor, ProcessingResult, SmartQueueProcessor
from queue_monitor import QueueMonitor, AlertThresholds


class TestMessageQueue(unittest.TestCase):
    """Test cases for MessageQueue"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_queue.db")
        self.queue = MessageQueue(db_path=self.db_path)
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_enqueue_message(self):
        """Test enqueuing a message"""
        async def test():
            message_id = await self.queue.enqueue(
                {"type": "test", "data": "hello"},
                priority=MessagePriority.HIGH
            )
            
            self.assertIsNotNone(message_id)
            self.assertEqual(len(message_id), 36)  # UUID length
            
            # Check queue stats
            stats = await self.queue.get_queue_stats()
            self.assertEqual(stats["pending"], 1)
        
        asyncio.run(test())
    
    def test_dequeue_message(self):
        """Test dequeuing messages"""
        async def test():
            # Enqueue test messages
            await self.queue.enqueue(
                {"type": "test1"},
                priority=MessagePriority.LOW
            )
            await self.queue.enqueue(
                {"type": "test2"},
                priority=MessagePriority.HIGH
            )
            
            # Dequeue messages
            messages = await self.queue.dequeue(limit=2)
            self.assertEqual(len(messages), 2)
            
            # High priority message should come first
            self.assertEqual(messages[0].payload["type"], "test2")
            self.assertEqual(messages[1].payload["type"], "test1")
            
            # Messages should be marked as processing
            self.assertEqual(messages[0].status, MessageStatus.PROCESSING)
        
        asyncio.run(test())
    
    def test_complete_message(self):
        """Test completing a message"""
        async def test():
            message_id = await self.queue.enqueue({"type": "test"})
            messages = await self.queue.dequeue()
            
            success = await self.queue.complete_message(messages[0].id)
            self.assertTrue(success)
            
            # Check stats
            stats = await self.queue.get_queue_stats()
            self.assertEqual(stats["completed"], 1)
        
        asyncio.run(test())
    
    def test_fail_message(self):
        """Test failing a message"""
        async def test():
            message_id = await self.queue.enqueue({"type": "test"})
            messages = await self.queue.dequeue()
            
            success = await self.queue.fail_message(
                messages[0].id,
                "Test error",
                retry_delay=1.0
            )
            self.assertTrue(success)
            
            # Message should be back in pending with retry scheduled
            stats = await self.queue.get_queue_stats()
            self.assertEqual(stats["pending"], 1)
        
        asyncio.run(test())
    
    def test_dead_letter_queue(self):
        """Test dead letter queue functionality"""
        async def test():
            message_id = await self.queue.enqueue(
                {"type": "test"},
                max_attempts=2
            )
            
            # Fail message twice to exceed max attempts
            for _ in range(2):
                messages = await self.queue.dequeue()
                await self.queue.fail_message(messages[0].id, "Test error")
            
            # Message should be in dead letter queue
            dead_letters = await self.queue.get_dead_letter_messages()
            self.assertEqual(len(dead_letters), 1)
            self.assertEqual(dead_letters[0]["id"], message_id)
            
            stats = await self.queue.get_queue_stats()
            self.assertEqual(stats["dead_letter"], 1)
        
        asyncio.run(test())
    
    def test_requeue_dead_letter(self):
        """Test requeuing dead letter messages"""
        async def test():
            message_id = await self.queue.enqueue({"type": "test"}, max_attempts=1)
            
            # Send to dead letter
            messages = await self.queue.dequeue()
            await self.queue.fail_message(messages[0].id, "Test error")
            
            # Requeue
            success = await self.queue.requeue_dead_letter(message_id)
            self.assertTrue(success)
            
            # Should be back in main queue
            stats = await self.queue.get_queue_stats()
            self.assertEqual(stats["pending"], 1)
            self.assertEqual(stats["dead_letter"], 0)
        
        asyncio.run(test())
    
    def test_queue_stats(self):
        """Test queue statistics"""
        async def test():
            # Add messages with different states
            await self.queue.enqueue({"type": "test1"})
            await self.queue.enqueue({"type": "test2"})
            
            messages = await self.queue.dequeue()
            await self.queue.complete_message(messages[0].id)
            
            stats = await self.queue.get_queue_stats()
            self.assertEqual(stats["pending"], 1)
            self.assertEqual(stats["completed"], 1)
            self.assertIn("priority_distribution", stats)
        
        asyncio.run(test())


class TestRetryHandler(unittest.TestCase):
    """Test cases for RetryHandler"""
    
    def test_exponential_backoff(self):
        """Test exponential backoff calculation"""
        handler = RetryHandler(
            base_delay=1.0,
            multiplier=2.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            jitter=False  # Disable jitter for predictable testing
        )
        
        delay1 = handler.calculate_delay_no_jitter(0)
        delay2 = handler.calculate_delay_no_jitter(1)
        delay3 = handler.calculate_delay_no_jitter(2)
        
        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 4.0)
    
    def test_linear_backoff(self):
        """Test linear backoff calculation"""
        handler = RetryHandler(
            base_delay=1.0,
            backoff_strategy=BackoffStrategy.LINEAR,
            jitter=False  # Disable jitter for predictable testing
        )
        
        delay1 = handler.calculate_delay_no_jitter(0)
        delay2 = handler.calculate_delay_no_jitter(1)
        delay3 = handler.calculate_delay_no_jitter(2)
        
        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 3.0)
    
    def test_jitter(self):
        """Test jitter addition"""
        handler = RetryHandler(
            base_delay=10.0,
            jitter=True,
            jitter_factor=0.1
        )
        
        delay = handler.calculate_delay(0)
        # Should be between 9.0 and 11.0
        self.assertGreaterEqual(delay, 9.0)
        self.assertLessEqual(delay, 11.0)
    
    def test_max_delay_cap(self):
        """Test maximum delay cap"""
        handler = RetryHandler(
            base_delay=1.0,
            max_delay=5.0,
            multiplier=10.0
        )
        
        delay = handler.calculate_delay(5)
        self.assertLessEqual(delay, 5.0)
    
    def test_retry_with_backoff_success(self):
        """Test successful retry with backoff"""
        async def test():
            handler = RetryHandler(max_attempts=3, base_delay=0.1)
            
            call_count = 0
            async def failing_func():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ConnectionError("Temporary failure")
                return "success"
            
            result = await handler.retry_with_backoff(failing_func)
            self.assertEqual(result, "success")
            self.assertEqual(call_count, 3)
        
        asyncio.run(test())
    
    def test_retry_with_backoff_failure(self):
        """Test failed retry with backoff"""
        async def test():
            handler = RetryHandler(max_attempts=2, base_delay=0.1)
            
            async def always_failing_func():
                raise ConnectionError("Permanent failure")
            
            with self.assertRaises(ConnectionError):
                await handler.retry_with_backoff(always_failing_func)
        
        asyncio.run(test())
    
    def test_adaptive_retry_handler(self):
        """Test adaptive retry handler"""
        handler = AdaptiveRetryHandler()
        
        # Record some failures
        for _ in range(5):
            handler.record_failure()
        
        # Failure rate should be high
        self.assertGreater(handler.get_failure_rate(), 0.5)
        
        # Adapt parameters
        handler.adapt_parameters()
        
        # Should have increased attempts or delays
        self.assertGreaterEqual(handler.max_attempts, 3)


class TestQueueProcessor(unittest.TestCase):
    """Test cases for QueueProcessor"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_processor.db")
        self.message_queue = MessageQueue(db_path=self.db_path)
        self.processor = QueueProcessor(
            self.message_queue,
            batch_size=2,
            max_concurrent_batches=1
        )
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_register_handler(self):
        """Test registering message handlers"""
        async def test_handler(payload):
            return "processed"
        
        self.processor.register_handler("test_type", test_handler)
        self.assertIn("test_type", self.processor.message_handlers)
    
    def test_process_message_success(self):
        """Test successful message processing"""
        async def test():
            # Register handler
            async def test_handler(payload):
                return "success"
            
            self.processor.register_handler("test", test_handler)
            
            # Create test message
            message = QueueMessage(
                id="test-id",
                payload={"type": "test", "data": "test"},
                priority=MessagePriority.NORMAL,
                status=MessageStatus.PROCESSING,
                created_at=time.time(),
                scheduled_at=time.time(),
                attempts=0,
                max_attempts=3,
                last_attempt=None,
                next_retry=None,
                error_message=None,
                metadata={}
            )
            
            result = await self.processor.process_message(message)
            self.assertEqual(result, ProcessingResult.SUCCESS)
        
        asyncio.run(test())
    
    def test_process_message_no_handler(self):
        """Test processing message with no handler"""
        async def test():
            message = QueueMessage(
                id="test-id",
                payload={"type": "unknown"},
                priority=MessagePriority.NORMAL,
                status=MessageStatus.PROCESSING,
                created_at=time.time(),
                scheduled_at=time.time(),
                attempts=0,
                max_attempts=3,
                last_attempt=None,
                next_retry=None,
                error_message=None,
                metadata={}
            )
            
            result = await self.processor.process_message(message)
            self.assertEqual(result, ProcessingResult.SKIP)
        
        asyncio.run(test())
    
    def test_process_batch(self):
        """Test batch processing"""
        async def test():
            # Register handler
            async def test_handler(payload):
                return f"processed_{payload['id']}"
            
            self.processor.register_handler("test", test_handler)
            
            # Create test messages
            messages = []
            for i in range(3):
                message = QueueMessage(
                    id=f"test-{i}",
                    payload={"type": "test", "id": i},
                    priority=MessagePriority.NORMAL,
                    status=MessageStatus.PROCESSING,
                    created_at=time.time(),
                    scheduled_at=time.time(),
                    attempts=0,
                    max_attempts=3,
                    last_attempt=None,
                    next_retry=None,
                    error_message=None,
                    metadata={}
                )
                messages.append(message)
            
            results = await self.processor.process_batch(messages)
            self.assertEqual(len(results), 3)
            self.assertTrue(all(r == ProcessingResult.SUCCESS for r in results))
        
        asyncio.run(test())
    
    def test_get_stats(self):
        """Test getting processor statistics"""
        stats = self.processor.get_stats()
        
        self.assertIn("overall", stats)
        self.assertIn("recent", stats)
        self.assertIn("configuration", stats)
        self.assertIn("status", stats)
        
        # Check configuration
        self.assertEqual(stats["configuration"]["batch_size"], 2)
        self.assertEqual(stats["configuration"]["max_concurrent_batches"], 1)
    
    def test_smart_queue_processor(self):
        """Test smart queue processor with adaptive batch sizing"""
        processor = SmartQueueProcessor(
            self.message_queue,
            batch_size=5
        )
        
        # Should start with configured batch size
        self.assertEqual(processor.batch_size, 5)
        self.assertEqual(processor.optimal_batch_size, 5)


class TestQueueMonitor(unittest.TestCase):
    """Test cases for QueueMonitor"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_monitor.db")
        self.message_queue = MessageQueue(db_path=self.db_path)
        self.monitor = QueueMonitor(
            self.message_queue,
            monitoring_interval=0.1
        )
    
    def tearDown(self):
        if hasattr(self, 'monitor'):
            asyncio.run(self.monitor.stop_monitoring())
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_collect_metrics(self):
        """Test metrics collection"""
        async def test():
            await self.monitor._collect_metrics()
            self.assertIsNotNone(self.monitor.current_metrics)
            
            metrics = self.monitor.current_metrics
            self.assertIsInstance(metrics.pending_count, int)
            self.assertIsInstance(metrics.processing_rate, float)
        
        asyncio.run(test())
    
    def test_alert_thresholds(self):
        """Test alert threshold checking"""
        async def test():
            # Set low thresholds for testing
            self.monitor.alert_thresholds.max_queue_depth = 1
            
            # Add messages to trigger alert
            await self.message_queue.enqueue({"type": "test1"})
            await self.message_queue.enqueue({"type": "test2"})
            
            await self.monitor._collect_metrics()
            await self.monitor._check_alerts()
            
            # Should have triggered queue depth alert
            self.assertIn("queue_depth_warning", self.monitor.active_alerts)
        
        asyncio.run(test())
    
    def test_alert_callbacks(self):
        """Test alert callback functionality"""
        callback_called = False
        
        async def test_callback(alert):
            nonlocal callback_called
            callback_called = True
        
        self.monitor.add_alert_callback(test_callback)
        
        async def test():
            # Trigger an alert
            self.monitor.alert_thresholds.max_queue_depth = 0
            await self.message_queue.enqueue({"type": "test"})
            
            await self.monitor._collect_metrics()
            await self.monitor._check_alerts()
            
            # Callback should have been called
            self.assertTrue(callback_called)
        
        asyncio.run(test())
    
    def test_performance_summary(self):
        """Test performance summary generation"""
        async def test():
            # Add some metrics history
            for i in range(10):
                await self.monitor._collect_metrics()
                await asyncio.sleep(0.01)  # Small delay
            
            summary = self.monitor.get_performance_summary(time_window=1.0)
            
            self.assertIn("time_window_seconds", summary)
            self.assertIn("sample_count", summary)
            self.assertIn("average_processing_rate", summary)
            self.assertIn("trend", summary)
        
        asyncio.run(test())
    
    def test_health_report(self):
        """Test health report generation"""
        async def test():
            await self.monitor._collect_metrics()
            report = await self.monitor.generate_health_report()
            
            self.assertIn("status", report)
            self.assertIn("issues", report)
            self.assertIn("recommendations", report)
            
            # Should be healthy with no issues
            self.assertEqual(report["status"], "healthy")
        
        asyncio.run(test())


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete message queue system"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_integration.db")
    
    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_end_to_end_processing(self):
        """Test complete end-to-end message processing"""
        async def test():
            # Setup components
            queue = MessageQueue(db_path=self.db_path)
            processor = QueueProcessor(queue, batch_size=2)
            monitor = QueueMonitor(queue)
            
            # Register handler
            processed_messages = []
            
            async def test_handler(payload):
                processed_messages.append(payload)
                if payload.get("should_fail"):
                    raise ValueError("Test failure")
                return "success"
            
            processor.register_handler("test", test_handler)
            
            # Enqueue messages
            await queue.enqueue({"type": "test", "id": 1})
            await queue.enqueue({"type": "test", "id": 2})
            await queue.enqueue({"type": "test", "id": 3, "should_fail": True})
            
            # Process messages
            messages = await queue.dequeue(limit=3)
            results = await processor.process_batch(messages)
            
            # Check results
            self.assertEqual(len(results), 3)
            self.assertEqual(results[0], ProcessingResult.SUCCESS)
            self.assertEqual(results[1], ProcessingResult.SUCCESS)
            self.assertEqual(results[2], ProcessingResult.FAILURE)
            
            # Check processed messages
            self.assertEqual(len(processed_messages), 3)
            
            # Check queue stats
            stats = await queue.get_queue_stats()
            self.assertEqual(stats["completed"], 2)
            self.assertGreater(stats["failed"], 0)
        
        asyncio.run(test())
    
    def test_monitoring_integration(self):
        """Test monitoring integration with processing"""
        async def test():
            queue = MessageQueue(db_path=self.db_path)
            processor = QueueProcessor(queue)
            monitor = QueueMonitor(queue, monitoring_interval=0.05)
            
            # Start monitoring
            await monitor.start_monitoring()
            
            # Add some activity
            await queue.enqueue({"type": "test"})
            await queue.enqueue({"type": "test"})
            
            messages = await queue.dequeue()
            await queue.complete_message(messages[0].id)
            
            # Wait for monitoring to collect metrics
            await asyncio.sleep(0.1)
            
            # Check metrics were collected
            self.assertIsNotNone(monitor.current_metrics)
            self.assertGreater(len(monitor.metrics_history), 0)
            
            # Stop monitoring
            await monitor.stop_monitoring()
        
        asyncio.run(test())


if __name__ == '__main__':
    unittest.main()
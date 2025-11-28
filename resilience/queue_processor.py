import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class ProcessingResult(Enum):
    SUCCESS = "success"
    RETRY = "retry"
    FAILURE = "failure"
    SKIP = "skip"


@dataclass
class ProcessingStats:
    processed_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    retry_count: int = 0
    skip_count: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    messages_per_second: float = 0.0


class QueueProcessor:
    """High-performance message processor with batch processing and circuit breaker integration"""
    
    def __init__(
        self,
        message_queue,
        batch_size: int = 10,
        max_concurrent_batches: int = 3,
        processing_timeout: float = 30.0,
        retry_handler=None,
        circuit_breaker_manager=None
    ):
        """
        Initialize queue processor
        
        Args:
            message_queue: Message queue instance
            batch_size: Number of messages to process in each batch
            max_concurrent_batches: Maximum number of concurrent batch processing
            processing_timeout: Timeout for individual message processing
            retry_handler: Retry handler for failed messages
            circuit_breaker_manager: Circuit breaker manager for fault tolerance
        """
        self.message_queue = message_queue
        self.batch_size = batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.processing_timeout = processing_timeout
        self.retry_handler = retry_handler
        self.circuit_breaker_manager = circuit_breaker_manager
        
        # Message handlers by type
        self.message_handlers: Dict[str, Callable] = {}
        
        # Processing statistics
        self.stats = ProcessingStats()
        self.processing_history = deque(maxlen=1000)  # Keep last 1000 processing records
        
        # Control flags
        self._running = False
        self._shutdown_requested = False
        
        # Semaphore for concurrent batch control
        self._batch_semaphore = asyncio.Semaphore(max_concurrent_batches)
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")
    
    async def process_message(self, message) -> ProcessingResult:
        """Process a single message"""
        start_time = time.time()
        message_type = message.payload.get("type", "default")
        
        try:
            # Get appropriate handler
            handler = self.message_handlers.get(message_type)
            if not handler:
                logger.warning(f"No handler found for message type: {message_type}")
                return ProcessingResult.SKIP
            
            # Get circuit breaker for this message type if available
            circuit_breaker = None
            if self.circuit_breaker_manager:
                circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(
                    f"message_processor_{message_type}",
                    failure_threshold=5,
                    recovery_timeout=30.0
                )
            
            # Process with circuit breaker protection if available
            async def protected_process():
                return await asyncio.wait_for(
                    handler(message.payload),
                    timeout=self.processing_timeout
                )
            
            if circuit_breaker:
                result = await circuit_breaker.call(protected_process)
            else:
                result = await protected_process()
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_stats(ProcessingResult.SUCCESS, processing_time)
            
            logger.debug(f"Successfully processed message {message.id} in {processing_time:.3f}s")
            return ProcessingResult.SUCCESS
            
        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            self._update_stats(ProcessingResult.RETRY, processing_time)
            logger.warning(f"Message {message.id} processing timed out after {processing_time:.3f}s")
            return ProcessingResult.RETRY
            
        except Exception as e:
            processing_time = time.time() - start_time
            self._update_stats(ProcessingResult.FAILURE, processing_time)
            logger.error(f"Failed to process message {message.id}: {e}")
            
            # Determine if should retry based on exception
            if self.retry_handler and self.retry_handler.should_retry(e):
                return ProcessingResult.RETRY
            else:
                return ProcessingResult.FAILURE
    
    async def process_batch(self, messages) -> List[ProcessingResult]:
        """Process a batch of messages concurrently"""
        if not messages:
            return []
        
        logger.debug(f"Processing batch of {len(messages)} messages")
        
        # Process messages concurrently
        tasks = [self.process_message(message) for message in messages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception in message processing: {result}")
                processed_results.append(ProcessingResult.FAILURE)
            else:
                processed_results.append(result)
        
        # Update message statuses based on results
        await self._update_message_statuses(messages, processed_results)
        
        return processed_results
    
    async def _update_message_statuses(
        self,
        messages,
        results: List[ProcessingResult]
    ):
        """Update message statuses in the queue based on processing results"""
        for message, result in zip(messages, results):
            try:
                if result == ProcessingResult.SUCCESS:
                    await self.message_queue.complete_message(message.id)
                elif result == ProcessingResult.RETRY:
                    retry_delay = 60  # Default retry delay
                    if self.retry_handler:
                        retry_delay = self.retry_handler.calculate_delay(message.attempts)
                    
                    await self.message_queue.fail_message(
                        message.id,
                        "Processing failed, will retry",
                        retry_delay=retry_delay
                    )
                elif result == ProcessingResult.FAILURE:
                    await self.message_queue.fail_message(
                        message.id,
                        "Processing failed permanently"
                    )
                elif result == ProcessingResult.SKIP:
                    # Requeue skipped messages with lower priority
                    await self.message_queue.fail_message(
                        message.id,
                        "No handler available, requeued"
                    )
            except Exception as e:
                logger.error(f"Failed to update message {message.id} status: {e}")
    
    def _update_stats(self, result: ProcessingResult, processing_time: float):
        """Update processing statistics"""
        self.stats.processed_count += 1
        self.stats.total_processing_time += processing_time
        self.stats.average_processing_time = (
            self.stats.total_processing_time / self.stats.processed_count
        )
        
        if result == ProcessingResult.SUCCESS:
            self.stats.success_count += 1
        elif result == ProcessingResult.FAILURE:
            self.stats.failure_count += 1
        elif result == ProcessingResult.RETRY:
            self.stats.retry_count += 1
        elif result == ProcessingResult.SKIP:
            self.stats.skip_count += 1
        
        # Calculate messages per second
        if self.stats.total_processing_time > 0:
            self.stats.messages_per_second = (
                self.stats.processed_count / self.stats.total_processing_time
            )
        
        # Add to processing history
        self.processing_history.append({
            "timestamp": time.time(),
            "result": result.value,
            "processing_time": processing_time
        })
    
    async def start_processing(self, poll_interval: float = 1.0):
        """Start continuous message processing"""
        self._running = True
        self._shutdown_requested = False
        
        logger.info("Starting queue processor")
        
        while self._running and not self._shutdown_requested:
            try:
                # Check if we can start a new batch
                if self._batch_semaphore._value > 0:
                    # Get next batch of messages
                    messages = await self.message_queue.dequeue(self.batch_size)
                    
                    if messages:
                        # Process batch with semaphore control
                        async with self._batch_semaphore:
                            if not self._shutdown_requested:
                                await self.process_batch(messages)
                    else:
                        # No messages available, wait
                        await asyncio.sleep(poll_interval)
                else:
                    # All batch slots occupied, wait
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(poll_interval)
        
        logger.info("Queue processor stopped")
    
    async def stop_processing(self, graceful: bool = True):
        """Stop message processing"""
        self._shutdown_requested = True
        
        if graceful:
            # Wait for current batches to complete
            logger.info("Waiting for current batches to complete...")
            while self._batch_semaphore._value < self.max_concurrent_batches:
                await asyncio.sleep(0.1)
        
        self._running = False
        logger.info("Queue processor stop requested")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        # Calculate recent performance metrics
        recent_history = list(self.processing_history)[-100:]  # Last 100 records
        recent_success_rate = 0.0
        recent_avg_time = 0.0
        
        if recent_history:
            recent_success_count = sum(
                1 for record in recent_history if record["result"] == ProcessingResult.SUCCESS.value
            )
            recent_success_rate = recent_success_count / len(recent_history)
            recent_avg_time = sum(record["processing_time"] for record in recent_history) / len(recent_history)
        
        return {
            "overall": {
                "processed_count": self.stats.processed_count,
                "success_count": self.stats.success_count,
                "failure_count": self.stats.failure_count,
                "retry_count": self.stats.retry_count,
                "skip_count": self.stats.skip_count,
                "success_rate": (
                    self.stats.success_count / self.stats.processed_count
                    if self.stats.processed_count > 0 else 0.0
                ),
                "average_processing_time": self.stats.average_processing_time,
                "messages_per_second": self.stats.messages_per_second
            },
            "recent": {
                "success_rate": recent_success_rate,
                "average_processing_time": recent_avg_time,
                "sample_size": len(recent_history)
            },
            "configuration": {
                "batch_size": self.batch_size,
                "max_concurrent_batches": self.max_concurrent_batches,
                "processing_timeout": self.processing_timeout,
                "registered_handlers": list(self.message_handlers.keys())
            },
            "status": {
                "running": self._running,
                "shutdown_requested": self._shutdown_requested,
                "active_batches": self.max_concurrent_batches - self._batch_semaphore._value
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the processor"""
        stats = self.get_stats()
        
        # Determine health status
        health_issues = []
        
        if stats["recent"]["success_rate"] < 0.8:
            health_issues.append("Low recent success rate")
        
        if stats["recent"]["average_processing_time"] > self.processing_timeout * 0.8:
            health_issues.append("High processing times")
        
        if stats["status"]["active_batches"] >= self.max_concurrent_batches:
            health_issues.append("Maximum concurrent batches reached")
        
        # Check circuit breaker status if available
        circuit_stats = {}
        if self.circuit_breaker_manager:
            try:
                circuit_stats = await self.circuit_breaker_manager.get_all_stats()
                for name, cb_stats in circuit_stats.items():
                    if cb_stats["state"] == "open":
                        health_issues.append(f"Circuit breaker open: {name}")
            except Exception as e:
                logger.error(f"Failed to get circuit breaker stats: {e}")
        
        return {
            "healthy": len(health_issues) == 0,
            "issues": health_issues,
            "stats": stats,
            "circuit_breakers": circuit_stats
        }
    
    def reset_stats(self):
        """Reset processing statistics"""
        self.stats = ProcessingStats()
        self.processing_history.clear()
        logger.info("Processing statistics reset")


class PriorityQueueProcessor(QueueProcessor):
    """Processor that prioritizes messages by priority and age"""
    
    async def process_batch(self, messages) -> List[ProcessingResult]:
        """Process batch with priority ordering"""
        if not messages:
            return []
        
        # Sort by priority (descending) then by age (ascending)
        messages.sort(key=lambda m: (m.priority.value, -m.created_at))
        
        return await super().process_batch(messages)


class SmartQueueProcessor(QueueProcessor):
    """Processor with adaptive batch sizing and intelligent load balancing"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.performance_history = deque(maxlen=50)
        self.optimal_batch_size = self.batch_size
    
    async def process_batch(self, messages) -> List[ProcessingResult]:
        """Process batch with adaptive performance optimization"""
        if not messages:
            return []
        
        start_time = time.time()
        results = await super().process_batch(messages)
        processing_time = time.time() - start_time
        
        # Record performance
        self.performance_history.append({
            "batch_size": len(messages),
            "processing_time": processing_time,
            "success_rate": sum(1 for r in results if r == ProcessingResult.SUCCESS) / len(results)
        })
        
        # Adapt batch size based on performance
        self._adapt_batch_size()
        
        return results
    
    def _adapt_batch_size(self):
        """Adapt batch size based on recent performance"""
        if len(self.performance_history) < 5:
            return
        
        recent_performance = list(self.performance_history)[-5:]
        avg_processing_time = sum(p["processing_time"] for p in recent_performance) / len(recent_performance)
        avg_success_rate = sum(p["success_rate"] for p in recent_performance) / len(recent_performance)
        
        # If processing is fast and successful, increase batch size
        if avg_processing_time < 1.0 and avg_success_rate > 0.9:
            self.optimal_batch_size = min(self.optimal_batch_size + 2, 50)
        # If processing is slow or failing, decrease batch size
        elif avg_processing_time > 5.0 or avg_success_rate < 0.7:
            self.optimal_batch_size = max(self.optimal_batch_size - 1, 1)
        
        if self.optimal_batch_size != self.batch_size:
            self.batch_size = self.optimal_batch_size
            logger.info(f"Adapted batch size to {self.batch_size}")
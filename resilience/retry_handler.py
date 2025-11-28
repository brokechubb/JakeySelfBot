import asyncio
import random
import time
import math
from typing import Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    FIBONACCI = "fibonacci"


class RetryHandler:
    """Intelligent retry handler with multiple backoff strategies and jitter"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 300.0,
        backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        jitter: bool = True,
        jitter_factor: float = 0.1,
        multiplier: float = 2.0
    ):
        """
        Initialize retry handler
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay between retries
            max_delay: Maximum delay cap
            backoff_strategy: Strategy for calculating delay
            jitter: Whether to add random jitter to delays
            jitter_factor: Amount of jitter to add (0.0 to 1.0)
            multiplier: Multiplier for exponential backoff
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_strategy = backoff_strategy
        self.jitter = jitter
        self.jitter_factor = jitter_factor
        self.multiplier = multiplier
        
        # Fibonacci sequence for fibonacci backoff
        self._fib_cache = {0: 0, 1: 1}
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number"""
        if self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.multiplier ** attempt)
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        elif self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.base_delay
        elif self.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.base_delay * self._fibonacci(attempt + 1)
        else:
            delay = self.base_delay
        
        # Apply max delay cap
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)  # Ensure non-negative
        
        return delay
    
    def calculate_delay_no_jitter(self, attempt: int) -> float:
        """Calculate delay without jitter for testing"""
        if self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.multiplier ** attempt)
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        elif self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.base_delay
        elif self.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.base_delay * self._fibonacci(attempt + 1)
        else:
            delay = self.base_delay
        
        return min(delay, self.max_delay)
    
    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number with memoization"""
        if n in self._fib_cache:
            return self._fib_cache[n]
        
        result = self._fibonacci(n - 1) + self._fibonacci(n - 2)
        self._fib_cache[n] = result
        return result
    
    async def retry_with_backoff(
        self,
        func: Callable,
        retry_exceptions: tuple = (Exception,),
        on_retry: Optional[Callable[[int, Exception], None]] = None,
        *args,
        **kwargs
    ):
        """
        Execute a function with retry logic and backoff
        
        Args:
            func: Function to execute
            retry_exceptions: Exception types that trigger retry
            on_retry: Callback called on each retry (attempt, exception)
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except retry_exceptions as e:
                last_exception = e
                
                if attempt == self.max_attempts - 1:
                    # Last attempt, don't wait
                    logger.error(f"Retry failed after {self.max_attempts} attempts: {e}")
                    raise e
                
                delay = self.calculate_delay(attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                
                if on_retry:
                    try:
                        on_retry(attempt + 1, e)
                    except Exception as callback_error:
                        logger.error(f"Retry callback failed: {callback_error}")
                
                await asyncio.sleep(delay)
        
        # This should never be reached, but just in case
        if last_exception is not None:
            raise last_exception
        else:
            raise Exception("All retry attempts failed")
    
    def get_retry_schedule(self, attempts: Optional[int] = None) -> list:
        """Get the schedule of delays for a given number of attempts"""
        attempts = attempts or self.max_attempts
        schedule = []
        
        for attempt in range(attempts):
            delay = self.calculate_delay(attempt)
            schedule.append(delay)
        
        return schedule
    
    def should_retry(self, exception: Exception) -> bool:
        """Determine if an exception should trigger a retry"""
        # Can be overridden for custom retry logic
        if exception is None:
            return False
        return isinstance(exception, (ConnectionError, TimeoutError, OSError))
    
    def get_stats(self) -> dict:
        """Get retry handler statistics"""
        return {
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_strategy": self.backoff_strategy.value,
            "jitter": self.jitter,
            "jitter_factor": self.jitter_factor,
            "multiplier": self.multiplier,
            "retry_schedule": self.get_retry_schedule()
        }


class AdaptiveRetryHandler(RetryHandler):
    """Retry handler that adapts based on success/failure patterns"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.success_count = 0
        self.failure_count = 0
        self.recent_failures = []  # Track recent failure timestamps
        self.adaptation_window = 300  # 5 minutes
        self.failure_rate_threshold = 0.5  # 50% failure rate triggers adaptation
    
    def record_success(self):
        """Record a successful operation"""
        self.success_count += 1
    
    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        now = time.time()
        self.recent_failures.append(now)
        
        # Clean old failures outside the adaptation window
        cutoff = now - self.adaptation_window
        self.recent_failures = [f for f in self.recent_failures if f > cutoff]
    
    def get_failure_rate(self) -> float:
        """Get recent failure rate"""
        total_attempts = self.success_count + self.failure_count
        if total_attempts == 0:
            return 0.0
        
        # Calculate recent failure rate
        recent_total = len(self.recent_failures) + self.success_count
        if recent_total == 0:
            return 0.0
        
        return len(self.recent_failures) / recent_total
    
    def adapt_parameters(self):
        """Adapt retry parameters based on recent performance"""
        failure_rate = self.get_failure_rate()
        
        if failure_rate > self.failure_rate_threshold:
            # High failure rate - increase delays and attempts
            self.base_delay = min(self.base_delay * 1.5, self.max_delay / 4)
            self.max_attempts = min(self.max_attempts + 1, 10)
            logger.info(f"Adapted retry parameters due to high failure rate ({failure_rate:.2f})")
        elif failure_rate < 0.1 and self.failure_count > 10:
            # Low failure rate - reduce delays for faster recovery
            self.base_delay = max(self.base_delay * 0.8, 0.5)
            self.max_attempts = max(self.max_attempts - 1, 3)
            logger.info(f"Adapted retry parameters due to low failure rate ({failure_rate:.2f})")
    
    async def retry_with_backoff(self, func, *args, **kwargs):
        """Execute with adaptive retry logic"""
        try:
            result = await super().retry_with_backoff(func, *args, **kwargs)
            self.record_success()
            self.adapt_parameters()
            return result
        except Exception as e:
            self.record_failure()
            self.adapt_parameters()
            raise e


class CircuitBreakerRetryHandler(RetryHandler):
    """Retry handler that integrates with circuit breaker pattern"""
    
    def __init__(self, circuit_breaker, **kwargs):
        super().__init__(**kwargs)
        self.circuit_breaker = circuit_breaker
    
    async def retry_with_backoff(self, func, *args, **kwargs):
        """Execute with circuit breaker protection"""
        # Wrap the function with circuit breaker
        async def protected_func(*args, **kwargs):
            return await self.circuit_breaker.call(func, *args, **kwargs)
        
        return await super().retry_with_backoff(protected_func, *args, **kwargs)


# Pre-configured retry handlers for different use cases
FAST_RETRY = RetryHandler(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    jitter=True
)

SLOW_RETRY = RetryHandler(
    max_attempts=5,
    base_delay=5.0,
    max_delay=300.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    jitter=True
)

AGGRESSIVE_RETRY = RetryHandler(
    max_attempts=10,
    base_delay=1.0,
    max_delay=600.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    jitter=True,
    multiplier=1.5
)

CONSERVATIVE_RETRY = RetryHandler(
    max_attempts=2,
    base_delay=2.0,
    max_delay=30.0,
    backoff_strategy=BackoffStrategy.LINEAR,
    jitter=False
)
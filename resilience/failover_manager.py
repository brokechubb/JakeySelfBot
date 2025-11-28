"""
AI Provider Failover Manager with intelligent switching, load balancing, and circuit breaker integration.
"""
import asyncio
import time
import random
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

from tools.circuit_breaker import CircuitBreaker, circuit_breaker_manager
from utils.logging_config import get_logger

logger = get_logger(__name__)


class FailoverStrategy(Enum):
    PRIMARY_ONLY = "primary_only"
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    BEST_PERFORMANCE = "best_performance"
    RANDOM_AVAILABLE = "random_available"


@dataclass
class ProviderConfig:
    """Configuration for an AI provider"""
    name: str
    priority: int  # Lower number = higher priority
    enabled: bool = True
    weight: int = 1  # For weighted load balancing
    max_concurrent_requests: int = 10
    timeout: float = 30.0
    retry_attempts: int = 2
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    health_checks: List[Callable] = field(default_factory=list)
    client_factory: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelState:
    """State information for model configuration"""
    original_model: Optional[str]
    original_provider: Optional[str]
    fallback_model: Optional[str]
    fallback_provider: Optional[str]
    timestamp: float
    user_preference: Optional[str] = None  # User's preferred model if set


@dataclass
class FailoverResult:
    """Result of a failover operation"""
    success: bool
    provider_used: Optional[str]
    response_time: float
    error_message: Optional[str] = None
    failover_occurred: bool = False
    attempts_made: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    model_state: Optional[ModelState] = None


class FailoverManager:
    """
    Intelligent failover manager for AI providers with health monitoring,
    performance tracking, and circuit breaker integration.
    """
    
    def __init__(
        self,
        strategy: FailoverStrategy = FailoverStrategy.BEST_PERFORMANCE,
        health_check_interval: float = 30.0,
        performance_window_minutes: int = 60,
        enable_circuit_breakers: bool = True
    ):
        """
        Initialize failover manager.
        
        Args:
            strategy: Failover strategy to use
            health_check_interval: Interval for health checks
            performance_window_minutes: Time window for performance analysis
            enable_circuit_breakers: Whether to enable circuit breakers
        """
        self.strategy = strategy
        self.enable_circuit_breakers = enable_circuit_breakers
        
        # Provider management
        self.providers: Dict[str, ProviderConfig] = {}
        self.provider_clients: Dict[str, Any] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Load balancing
        self._round_robin_index = 0
        self._weighted_round_robin_weights: Dict[str, int] = {}
        
        # Health and performance monitoring (initialized later)
        self.health_monitor = None
        self.performance_tracker = None
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failover_count = 0
        self.provider_usage: Dict[str, int] = {}
        
        # Model state management
        self.current_model_state: Optional[ModelState] = None
        self.default_model = "evil"  # Default model when no specific model is set
        self.model_preferences: Dict[str, str] = {}  # user_id -> model preference
        
        logger.info(f"Failover manager initialized: strategy={strategy.value}, "
                   f"circuit_breakers={enable_circuit_breakers}")
    
    def _initialize_monitors(self):
        """Initialize health and performance monitors."""
        if self.health_monitor is None:
            from .health_monitor import health_monitor
            self.health_monitor = health_monitor
        
        if self.performance_tracker is None:
            from .performance_tracker import performance_tracker
            self.performance_tracker = performance_tracker
    
    def register_provider(self, config: ProviderConfig):
        """
        Register an AI provider with the failover manager.
        
        Args:
            config: Provider configuration
        """
        self._initialize_monitors()
        
        self.providers[config.name] = config
        
        # Initialize client if factory provided
        if config.client_factory:
            try:
                self.provider_clients[config.name] = config.client_factory()
                logger.info(f"Initialized client for provider '{config.name}'")
            except Exception as e:
                logger.error(f"Failed to initialize client for provider '{config.name}': {e}")
                config.enabled = False
        
        # Initialize circuit breaker
        if self.enable_circuit_breakers:
            self.circuit_breakers[config.name] = circuit_breaker_manager.get_circuit_breaker(
                name=f"ai_provider_{config.name}",
                failure_threshold=config.circuit_breaker_threshold,
                recovery_timeout=config.circuit_breaker_timeout
            )
        
        # Register with health monitor
        if config.health_checks:
            self.health_monitor.register_provider(
                provider_name=config.name,
                health_checks=config.health_checks,
                initial_metadata=config.metadata
            )
        
        # Initialize usage tracking
        self.provider_usage[config.name] = 0
        
        logger.info(f"Registered provider '{config.name}' with priority {config.priority}")
    
    def unregister_provider(self, provider_name: str):
        """Unregister a provider from the failover manager."""
        if provider_name in self.providers:
            del self.providers[provider_name]
        if provider_name in self.provider_clients:
            del self.provider_clients[provider_name]
        if provider_name in self.circuit_breakers:
            del self.circuit_breakers[provider_name]
        if provider_name in self.provider_usage:
            del self.provider_usage[provider_name]
        
        if self.health_monitor:
            self.health_monitor.unregister_provider(provider_name)
        logger.info(f"Unregistered provider '{provider_name}'")
    
    async def execute_request(
        self,
        operation: str,
        *args,
        preferred_provider: Optional[str] = None,
        **kwargs
    ) -> FailoverResult:
        """
        Execute a request with automatic failover.
        
        Args:
            operation: Operation to perform (e.g., 'generate_text', 'generate_image')
            *args: Positional arguments for the operation
            preferred_provider: Preferred provider to use first
            **kwargs: Keyword arguments for the operation
            
        Returns:
            FailoverResult with the operation result
        """
        start_time = time.time()
        self.total_requests += 1
        
        # Get ordered list of providers to try
        providers_to_try = self._get_providers_to_try(preferred_provider)
        
        if not providers_to_try:
            return FailoverResult(
                success=False,
                provider_used=None,
                response_time=time.time() - start_time,
                error_message="No available providers",
                attempts_made=0
            )
        
        # Try each provider in order
        last_error = None
        for attempt, provider_name in enumerate(providers_to_try):
            try:
                result = await self._try_provider(
                    provider_name, operation, *args, **kwargs
                )
                
                if result.success:
                    self.successful_requests += 1
                    self.provider_usage[provider_name] += 1
                    
                    # Record performance metric
                    if self.performance_tracker:
                        self.performance_tracker.record_metric(
                            provider_name=provider_name,
                            operation_type=operation,
                            response_time=result.response_time,
                            success=True
                        )
                    
                    # Check if failover occurred
                    failover_occurred = attempt > 0 or preferred_provider != provider_name
                    if failover_occurred:
                        self.failover_count += 1
                        logger.info(f"Failover: Using '{provider_name}' after {attempt} failed attempts")
                    
                    result.failover_occurred = failover_occurred
                    result.attempts_made = attempt + 1
                    
                    return result
                else:
                    last_error = result.error_message
                    
                    # Record performance metric for failed attempt
                    if self.performance_tracker:
                        self.performance_tracker.record_metric(
                            provider_name=provider_name,
                            operation_type=operation,
                            response_time=result.response_time,
                            success=False,
                            error_type=result.error_message
                        )
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Provider '{provider_name}' failed: {e}")
                
                # Record performance metric for exception
                if self.performance_tracker:
                    self.performance_tracker.record_metric(
                        provider_name=provider_name,
                        operation_type=operation,
                        response_time=time.time() - start_time,
                        success=False,
                        error_type=type(e).__name__
                    )
        
        # All providers failed
        return FailoverResult(
            success=False,
            provider_used=None,
            response_time=time.time() - start_time,
            error_message=last_error or "All providers failed",
            attempts_made=len(providers_to_try)
        )
    
    def _get_providers_to_try(self, preferred_provider: Optional[str] = None) -> List[str]:
        """Get ordered list of providers to try based on strategy."""
        available_providers = []
        
        # Filter enabled and available providers
        for name, config in self.providers.items():
            if not config.enabled:
                continue
            
            # Check health status
            if self.health_monitor and not self.health_monitor.is_available(name):
                continue
            
            # Check circuit breaker status
            if self.enable_circuit_breakers:
                circuit_breaker = self.circuit_breakers.get(name)
                if circuit_breaker and circuit_breaker.get_state().value == "open":
                    continue
            
            available_providers.append(name)
        
        if not available_providers:
            return []
        
        # Apply strategy
        if self.strategy == FailoverStrategy.PRIMARY_ONLY:
            # Sort by priority (lower number = higher priority)
            available_providers.sort(key=lambda x: self.providers[x].priority)
            
        elif self.strategy == FailoverStrategy.ROUND_ROBIN:
            # Simple round-robin
            available_providers = available_providers[self._round_robin_index:] + \
                                available_providers[:self._round_robin_index]
            self._round_robin_index = (self._round_robin_index + 1) % len(available_providers)
            
        elif self.strategy == FailoverStrategy.WEIGHTED_ROUND_ROBIN:
            # Weighted round-robin based on provider weights and performance
            weights = []
            for name in available_providers:
                base_weight = self.providers[name].weight
                # Adjust weight based on performance
                if self.performance_tracker:
                    stats = self.performance_tracker.get_provider_stats(name)
                    if stats and stats.success_rate > 0:
                        performance_multiplier = stats.success_rate
                        weights.append(int(base_weight * performance_multiplier))
                    else:
                        weights.append(base_weight)
                else:
                    weights.append(base_weight)
            
            # Select based on weights
            available_providers = self._weighted_random_choice(available_providers, weights)
            
        elif self.strategy == FailoverStrategy.BEST_PERFORMANCE:
            # Sort by performance score
            def performance_score(provider_name: str) -> float:
                if not self.performance_tracker:
                    return 0
                
                stats = self.performance_tracker.get_provider_stats(provider_name)
                if not stats:
                    return 0
                
                # Score = success_rate * 100 - average_response_time * 10
                return (stats.success_rate * 100) - (stats.average_response_time * 10)
            
            available_providers.sort(key=performance_score, reverse=True)
            
        elif self.strategy == FailoverStrategy.RANDOM_AVAILABLE:
            # Random order
            random.shuffle(available_providers)
        
        # If preferred provider is specified, try it first
        if preferred_provider and preferred_provider in available_providers:
            available_providers.remove(preferred_provider)
            available_providers.insert(0, preferred_provider)
        
        return available_providers
    
    def _weighted_random_choice(self, items: List[str], weights: List[int]) -> List[str]:
        """Get items ordered by weighted random choice."""
        if not items or not weights:
            return items
        
        # Create weighted list
        weighted_items = []
        for item, weight in zip(items, weights):
            weighted_items.extend([item] * weight)
        
        # Shuffle and return unique items in order
        random.shuffle(weighted_items)
        seen = set()
        result = []
        for item in weighted_items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        
        return result
    
    async def _try_provider(
        self,
        provider_name: str,
        operation: str,
        *args,
        **kwargs
    ) -> FailoverResult:
        """Try to execute operation with a specific provider."""
        start_time = time.time()
        config = self.providers[provider_name]
        client = self.provider_clients.get(provider_name)
        
        if not client:
            return FailoverResult(
                success=False,
                provider_used=provider_name,
                response_time=time.time() - start_time,
                error_message=f"No client available for provider '{provider_name}'"
            )
        
        try:
            # Check circuit breaker
            if self.enable_circuit_breakers:
                circuit_breaker = self.circuit_breakers.get(provider_name)
                if circuit_breaker:
                    async def protected_call():
                        return await self._execute_operation(client, operation, *args, **kwargs)
                    
                    result = await circuit_breaker.call(protected_call)
                else:
                    result = await self._execute_operation(client, operation, *args, **kwargs)
            else:
                result = await self._execute_operation(client, operation, *args, **kwargs)
            
            response_time = time.time() - start_time
            
            if isinstance(result, dict) and "error" in result:
                return FailoverResult(
                    success=False,
                    provider_used=provider_name,
                    response_time=response_time,
                    error_message=result["error"]
                )
            
            return FailoverResult(
                success=True,
                provider_used=provider_name,
                response_time=response_time,
                metadata={"result": result} if isinstance(result, dict) else {}
            )
            
        except Exception as e:
            return FailoverResult(
                success=False,
                provider_used=provider_name,
                response_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def _execute_operation(self, client: Any, operation: str, *args, **kwargs) -> Any:
        """Execute the actual operation on the client."""
        if hasattr(client, operation):
            method = getattr(client, operation)
            if asyncio.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            else:
                return method(*args, **kwargs)
        else:
            raise AttributeError(f"Client does not have operation '{operation}'")
    
    def get_provider_status(self, provider_name: str) -> Dict[str, Any]:
        """Get comprehensive status for a specific provider."""
        config = self.providers.get(provider_name)
        if not config:
            return {"error": f"Provider '{provider_name}' not found"}
        
        health = self.health_monitor.get_provider_health(provider_name) if self.health_monitor else None
        performance = self.performance_tracker.get_provider_stats(provider_name) if self.performance_tracker else None
        circuit_breaker = self.circuit_breakers.get(provider_name)
        
        status = {
            "name": provider_name,
            "enabled": config.enabled,
            "priority": config.priority,
            "weight": config.weight,
            "usage_count": self.provider_usage.get(provider_name, 0),
            "health": {
                "status": health.status.value if health else "unknown",
                "consecutive_failures": health.consecutive_failures if health else 0,
                "consecutive_successes": health.consecutive_successes if health else 0,
                "last_check": health.last_check if health else 0,
                "last_error": health.last_error if health else None
            } if health else None,
            "performance": {
                "success_rate": performance.success_rate if performance else 0,
                "average_response_time": performance.average_response_time if performance else 0,
                "requests_per_minute": performance.requests_per_minute if performance else 0,
                "uptime_percentage": performance.uptime_percentage if performance else 0
            } if performance else None,
            "circuit_breaker": {
                "state": circuit_breaker.get_state().value if circuit_breaker else "disabled",
                "failure_count": circuit_breaker.failure_count if circuit_breaker else 0,
                "stats": circuit_breaker.get_stats() if circuit_breaker else None
            } if circuit_breaker else None
        }
        
        return status
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get comprehensive status for all providers."""
        health_summary = self.health_monitor.get_health_summary() if self.health_monitor else {}
        performance_summary = self.performance_tracker.get_performance_summary() if self.performance_tracker else {}
        
        return {
            "strategy": self.strategy.value,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failover_count": self.failover_count,
            "overall_success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "providers": {
                name: self.get_provider_status(name)
                for name in self.providers.keys()
            },
            "health_summary": health_summary,
            "performance_summary": performance_summary
        }
    
    def set_strategy(self, strategy: FailoverStrategy):
        """Change the failover strategy."""
        self.strategy = strategy
        logger.info(f"Failover strategy changed to: {strategy.value}")
    
    def enable_provider(self, provider_name: str):
        """Enable a provider."""
        if provider_name in self.providers:
            self.providers[provider_name].enabled = True
            logger.info(f"Provider '{provider_name}' enabled")
    
    def disable_provider(self, provider_name: str):
        """Disable a provider."""
        if provider_name in self.providers:
            self.providers[provider_name].enabled = False
            logger.info(f"Provider '{provider_name}' disabled")
    
    async def force_health_check(self, provider_name: Optional[str] = None):
        """Force health check for specific provider or all providers."""
        if not self.health_monitor:
            return None
        
        if provider_name:
            return await self.health_monitor.force_check(provider_name)
        else:
            return await self.health_monitor.force_check_all()
    
    def save_model_state(
        self,
        original_model: Optional[str],
        original_provider: Optional[str],
        fallback_model: Optional[str],
        fallback_provider: Optional[str],
        user_id: Optional[str] = None
    ) -> ModelState:
        """
        Save the current model state before failover.
        
        Args:
            original_model: The model that was being used before failover
            original_provider: The provider that was being used before failover
            fallback_model: The model being used for fallback
            fallback_provider: The provider being used for fallback
            user_id: Optional user ID for tracking user preferences
            
        Returns:
            ModelState object representing the saved state
        """
        user_preference = self.model_preferences.get(user_id) if user_id else None
        
        state = ModelState(
            original_model=original_model,
            original_provider=original_provider,
            fallback_model=fallback_model,
            fallback_provider=fallback_provider,
            timestamp=time.time(),
            user_preference=user_preference
        )
        
        self.current_model_state = state
        logger.info(f"Saved model state: {original_model}@{original_provider} -> {fallback_model}@{fallback_provider}")
        return state
    
    def should_restore_original_model(self, provider_name: str) -> bool:
        """
        Check if we should restore the original model after provider recovery.
        
        Args:
            provider_name: The provider that has recovered
            
        Returns:
            True if original model should be restored
        """
        if not self.current_model_state:
            return False
        
        # Check if the recovered provider was the original provider
        if self.current_model_state.original_provider != provider_name:
            return False
        
        # Check if enough time has passed (avoid flapping)
        time_since_failover = time.time() - self.current_model_state.timestamp
        if time_since_failover < 60:  # Wait at least 1 minute before restoration
            return False
        
        # Check if the original provider is healthy
        if self.health_monitor and not self.health_monitor.is_available(provider_name):
            return False
        
        # Check circuit breaker status
        if self.enable_circuit_breakers:
            circuit_breaker = self.circuit_breakers.get(provider_name)
            if circuit_breaker and circuit_breaker.get_state().value == "open":
                return False
        
        return True
    
    def get_restored_model_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the model configuration to restore after provider recovery.
        
        Args:
            provider_name: The provider that has recovered
            
        Returns:
            Dictionary with model configuration or None if no restoration needed
        """
        if not self.should_restore_original_model(provider_name):
            return None
        
        state = self.current_model_state
        
        # Determine which model to restore
        if state.user_preference:
            # User has a preferred model
            model_to_restore = state.user_preference
        elif state.original_model:
            # Use the original model that was being used
            model_to_restore = state.original_model
        else:
            # Use default model
            model_to_restore = self.default_model
        
        # Validate that the model is available on the provider
        if not self._is_model_available(model_to_restore, provider_name):
            logger.warning(f"Model {model_to_restore} not available on {provider_name}, using default")
            model_to_restore = self.default_model
        
        config = {
            "model": model_to_restore,
            "provider": provider_name,
            "restored_from_failover": True,
            "previous_state": {
                "fallback_model": state.fallback_model,
                "fallback_provider": state.fallback_provider,
                "failover_timestamp": state.timestamp
            }
        }
        
        logger.info(f"Restoring model configuration: {model_to_restore}@{provider_name}")
        return config
    
    def _is_model_available(self, model: str, provider: str) -> bool:
        """
        Check if a model is available on a specific provider.
        
        Args:
            model: Model name to check
            provider: Provider name
            
        Returns:
            True if model is available on the provider
        """
        # This is a simplified check - in practice, you'd query the provider's model list
        # For now, we'll assume common models are available on common providers
        provider_models = {
            "pollinations": [
                "evil", "nvidia/nemotron-nano-9b-v2:free",
                "deepseek/deepseek-chat-v3.1:free", "openai/gpt-oss-20b:free"
            ],
            "openrouter": [
                "nvidia/nemotron-nano-9b-v2:free", "deepseek/deepseek-chat-v3.1:free",
                "openai/gpt-oss-20b:free", "meta-llama/llama-3.3-70b-instruct:free"
            ]
        }
        
        available_models = provider_models.get(provider, [])
        return model in available_models
    
    def set_user_model_preference(self, user_id: str, model: str):
        """
        Set a user's preferred model.
        
        Args:
            user_id: User's Discord ID
            model: Preferred model name
        """
        self.model_preferences[user_id] = model
        logger.info(f"Set model preference for user {user_id}: {model}")
    
    def get_user_model_preference(self, user_id: str) -> Optional[str]:
        """
        Get a user's preferred model.
        
        Args:
            user_id: User's Discord ID
            
        Returns:
            Preferred model name or None
        """
        return self.model_preferences.get(user_id)
    
    def clear_model_state(self):
        """Clear the current model state (e.g., after successful restoration)."""
        if self.current_model_state:
            logger.info(f"Cleared model state: {self.current_model_state.original_model}@{self.current_model_state.original_provider}")
            self.current_model_state = None
    
    def reset_statistics(self):
        """Reset all statistics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failover_count = 0
        self.provider_usage.clear()
        self.current_model_state = None
        if self.performance_tracker:
            self.performance_tracker.reset_metrics()
        logger.info("Failover statistics reset")


# Global failover manager instance
failover_manager = FailoverManager()
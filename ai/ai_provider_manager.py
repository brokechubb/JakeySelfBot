"""
AI Provider integration with the failover system.
Connects existing Pollinations and OpenRouter clients to the resilience framework.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ai.openrouter import OpenRouterAPI
from ai.pollinations import PollinationsAPI
from utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderStatus:
    """Provider status information."""

    name: str
    healthy: bool
    response_time: float
    error_message: Optional[str] = None
    last_check: float = 0.0


@dataclass
class FailoverResult:
    """Result of a failover operation."""

    success: bool
    provider_used: Optional[str]
    response_time: float
    error_message: Optional[str] = None
    failover_occurred: bool = False
    attempts_made: int = 0


class SimpleAIProviderManager:
    """
    Simplified AI provider manager with basic failover capabilities.
    Integrates existing Pollinations and OpenRouter clients.
    """

    def __init__(self):
        """Initialize the AI provider manager."""
        # Initialize providers
        self.pollinations_api = PollinationsAPI()
        self.openrouter_api = OpenRouterAPI()

        # Provider status tracking
        self.provider_status = {
            "pollinations": ProviderStatus("pollinations", True, 0.0),
            "openrouter": ProviderStatus("openrouter", True, 0.0),
        }

        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failover_count": 0,
            "provider_usage": {"pollinations": 0, "openrouter": 0},
        }

        # Model state management
        self.current_model = None
        self.current_provider = None
        self.original_model_state = None
        self.default_model = "evil"
        self.user_model_preferences = {}  # user_id -> model preference

        logger.info("Simple AI Provider Manager initialized")

    async def check_provider_health(self, provider_name: str) -> ProviderStatus:
        """Check health of a specific provider."""
        if provider_name == "pollinations":
            try:
                result = self.pollinations_api.check_service_health()
                status = ProviderStatus(
                    name="pollinations",
                    healthy=result.get("healthy", False),
                    response_time=result.get("response_time", 0.0),
                    error_message=result.get("error")
                    if not result.get("healthy")
                    else None,
                    last_check=time.time(),
                )
            except Exception as e:
                status = ProviderStatus(
                    name="pollinations",
                    healthy=False,
                    response_time=0.0,
                    error_message=str(e),
                    last_check=time.time(),
                )

        elif provider_name == "openrouter":
            try:
                result = self.openrouter_api.check_service_health()
                status = ProviderStatus(
                    name="openrouter",
                    healthy=result.get("healthy", False),
                    response_time=result.get("response_time", 0.0),
                    error_message=result.get("error")
                    if not result.get("healthy")
                    else None,
                    last_check=time.time(),
                )
            except Exception as e:
                status = ProviderStatus(
                    name="openrouter",
                    healthy=False,
                    response_time=0.0,
                    error_message=str(e),
                    last_check=time.time(),
                )

        else:
            status = ProviderStatus(
                name=provider_name,
                healthy=False,
                response_time=0.0,
                error_message="Unknown provider",
            )

        self.provider_status[provider_name] = status
        return status

    async def generate_text(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        preferred_provider: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate text with automatic failover between providers.

        Args:
            messages: List of message dictionaries
            model: Model to use (optional)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            tools: List of tools for function calling
            tool_choice: Tool choice strategy
            preferred_provider: Preferred provider to use first
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        start_time = time.time()
        self.stats["total_requests"] += 1

        # Determine provider order
        providers_to_try = []

        if preferred_provider and preferred_provider in ["pollinations", "openrouter"]:
            providers_to_try.append(preferred_provider)

        # Add remaining providers in order of preference
        # OpenRouter is now primary, Pollinations is fallback
        for provider in ["openrouter", "pollinations"]:
            if provider not in providers_to_try:
                providers_to_try.append(provider)

        # Try each provider
        last_error = None
        for attempt, provider in enumerate(providers_to_try):
            try:
                # Skip health check completely for fastest response - let API call failures trigger failover
                # This eliminates the 5-10 second health check overhead on every request

                # Make request directly without executor overhead
                request_start = time.time()
                if provider == "pollinations":
                    logger.debug(
                        f"🚀 Making direct Pollinations API call (attempt {attempt + 1})"
                    )
                    logger.debug(f"📤 Model being used: {model}")
                    result = await asyncio.to_thread(
                        self.pollinations_api.generate_text,
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=tools,
                        tool_choice=tool_choice,
                        **kwargs,
                    )
                else:  # openrouter
                    logger.debug(
                        f"🚀 Making direct OpenRouter API call (attempt {attempt + 1})"
                    )
                    result = await asyncio.to_thread(
                        self.openrouter_api.generate_text,
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=tools,
                        tool_choice=tool_choice,
                        **kwargs,
                    )

                request_time = time.time() - request_start
                logger.debug(f"⏱️ {provider} API call completed in {request_time:.2f}s")

                # Check for errors in response
                if isinstance(result, dict) and "error" in result:
                    last_error = result["error"]
                    logger.warning(f"Provider {provider} returned error: {last_error}")
                    continue

                # Success
                response_time = time.time() - start_time
                self.stats["successful_requests"] += 1
                self.stats["provider_usage"][provider] += 1

                if attempt > 0:
                    self.stats["failover_count"] += 1
                    logger.info(f"Failover: {provider} after {attempt} attempts")

                logger.info(f"Generated text via {provider} ({response_time:.2f}s)")

                return result

            except Exception as e:
                last_error = str(e)
                logger.error(f"Provider {provider} failed: {e}")
                continue

        # All providers failed
        response_time = time.time() - start_time
        error_msg = last_error or "All providers failed"
        logger.error(
            f"Text generation failed after {len(providers_to_try)} attempts: {error_msg}"
        )

        return {"error": error_msg}

    async def generate_image(
        self,
        prompt: str,
        model: str = "flux",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Generate image using Pollinations (only provider that supports images).

        Args:
            prompt: Image generation prompt
            model: Model to use
            width: Image width
            height: Image height
            seed: Random seed
            **kwargs: Additional parameters

        Returns:
            Image URL or error message
        """
        start_time = time.time()
        self.stats["total_requests"] += 1

        try:
            # Check Pollinations health
            health = await self.check_provider_health("pollinations")
            if not health.healthy:
                error_msg = f"Pollinations is unhealthy: {health.error_message}"
                logger.error(f"Image generation failed: {error_msg}")
                return f"Error: {error_msg}"

            # Generate image
            result = self.pollinations_api.generate_image(
                prompt=prompt,
                model=model,
                width=width,
                height=height,
                seed=seed,
                **kwargs,
            )

            # Success
            response_time = time.time() - start_time
            self.stats["successful_requests"] += 1
            self.stats["provider_usage"]["pollinations"] += 1

            logger.info(f"Generated image via pollinations ({response_time:.2f}s)")

            return result

        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Image generation failed: {error_msg}")
            return f"Error: {error_msg}"

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        return {
            "providers": {
                name: {
                    "name": status.name,
                    "healthy": status.healthy,
                    "response_time": status.response_time,
                    "error_message": status.error_message,
                    "last_check": status.last_check,
                }
                for name, status in self.provider_status.items()
            },
            "statistics": self.get_statistics(),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics."""
        total_requests = self.stats["total_requests"]
        success_rate = (
            self.stats["successful_requests"] / total_requests
            if total_requests > 0
            else 0
        )

        return {
            "total_requests": total_requests,
            "successful_requests": self.stats["successful_requests"],
            "failover_count": self.stats["failover_count"],
            "success_rate": success_rate,
            "provider_usage": self.stats["provider_usage"].copy(),
            "timeout_stats": {
                "pollinations": self.pollinations_api.get_timeout_stats(),
                "openrouter": {
                    "monitoring_enabled": False
                },  # OpenRouter doesn't have timeout monitoring yet
            },
        }

    def reset_statistics(self):
        """Reset all statistics."""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failover_count": 0,
            "provider_usage": {"pollinations": 0, "openrouter": 0},
        }
        logger.info("AI Provider statistics reset")

    async def health_check_all(self) -> Dict[str, ProviderStatus]:
        """Perform health check on all providers."""
        results = {}
        for provider in ["pollinations", "openrouter"]:
            results[provider] = await self.check_provider_health(provider)
        return results

    def save_model_state(
        self,
        original_model: str,
        original_provider: str,
        fallback_model: str,
        fallback_provider: str,
        user_id: Optional[str] = None,
    ):
        """
        Save the current model state before failover.

        Args:
            original_model: The model that was being used before failover
            original_provider: The provider that was being used before failover
            fallback_model: The model being used for fallback
            fallback_provider: The provider being used for fallback
            user_id: Optional user ID for tracking user preferences
        """
        user_preference = self.user_model_preferences.get(user_id) if user_id else None

        self.original_model_state = {
            "original_model": original_model,
            "original_provider": original_provider,
            "fallback_model": fallback_model,
            "fallback_provider": fallback_provider,
            "timestamp": time.time(),
            "user_preference": user_preference,
        }

        logger.info(f"Saved model state: {original_model}@{original_provider} -> {fallback_model}@{fallback_provider}")

    def should_restore_original_model(self, provider_name: str) -> bool:
        """
        Check if we should restore the original model after provider recovery.

        Args:
            provider_name: The provider that has recovered

        Returns:
            True if original model should be restored
        """
        if not self.original_model_state:
            return False

        # Check if the recovered provider was the original provider
        if self.original_model_state["original_provider"] != provider_name:
            return False

        # Check if enough time has passed (avoid flapping)
        time_since_failover = time.time() - self.original_model_state["timestamp"]
        if time_since_failover < 60:  # Wait at least 1 minute before restoration
            return False

        # Check if the original provider is healthy
        health = self.provider_status.get(provider_name)
        if not health or not health.healthy:
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

        state = self.original_model_state
        if not state:
            return None

        # Determine which model to restore
        if state.get("user_preference"):
            # User has a preferred model
            model_to_restore = state["user_preference"]
        elif state.get("original_model"):
            # Use the original model that was being used
            model_to_restore = state["original_model"]
        else:
            # Use default model
            model_to_restore = self.default_model

        # Validate that the model is available on the provider
        if not self._is_model_available(model_to_restore, provider_name):
            logger.warning(
                f"Model {model_to_restore} not available on {provider_name}, using default"
            )
            model_to_restore = self.default_model

        config = {
            "model": model_to_restore,
            "provider": provider_name,
            "restored_from_failover": True,
            "previous_state": {
                "fallback_model": state.get("fallback_model"),
                "fallback_provider": state.get("fallback_provider"),
                "failover_timestamp": state.get("timestamp"),
            },
        }

        logger.info(f"Restoring model: {model_to_restore}@{provider_name}")
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
        # Simplified model availability check
        provider_models = {
            "pollinations": ["evil", "unity", "openai-large"],
            "openrouter": [
                "nvidia/nemotron-nano-9b-v2:free",
                "deepseek/deepseek-chat-v3.1:free",
                "openai/gpt-oss-20b:free",
            ],
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
        self.user_model_preferences[user_id] = model
        logger.info(f"Set model preference for user {user_id}: {model}")

    def get_user_model_preference(self, user_id: str) -> Optional[str]:
        """
        Get a user's preferred model.

        Args:
            user_id: User's Discord ID

        Returns:
            Preferred model name or None
        """
        return self.user_model_preferences.get(user_id)

    def clear_model_state(self):
        """Clear the current model state (e.g., after successful restoration)."""
        if self.original_model_state:
            logger.info(f"Cleared model state: {self.original_model_state['original_model']}@{self.original_model_state['original_provider']}")
            self.original_model_state = None

    def update_current_model(self, model: str, provider: str):
        """
        Update the current model and provider being used.

        Args:
            model: Current model name
            provider: Current provider name
        """
        self.current_model = model
        self.current_provider = provider
        logger.debug(f"Updated current model: {model}@{provider}")


# Global AI provider manager instance
ai_provider_manager = SimpleAIProviderManager()

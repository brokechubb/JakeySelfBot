"""
AI Provider integration - OpenRouter only.
Pollinations has been removed as the text models are no longer compatible.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ai.openrouter import openrouter_api
from config import OPENROUTER_DEFAULT_MODEL
from utils.logging_config import get_logger

logger = get_logger(__name__)

WEB_SEARCH_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

# Known working models for fallback
WORKING_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "xiaomi/mimo-v2-flash:free", 
    "openai/gpt-oss-120b:free",
    "mistralai/devstral-2512:free"
]

# Known broken models to replace
BROKEN_MODELS = [
    "mistralai/mistral-small-3.1-24b-instruct:free"
]


@dataclass
class ProviderStatus:
    """Provider status information."""

    name: str
    healthy: bool
    response_time: float
    error_message: Optional[str] = None
    last_check: float = 0.0


class SimpleAIProviderManager:
    """
    Simplified AI provider manager using OpenRouter only.
    Pollinations text models have been deprecated and removed.
    """

    def __init__(self):
        """Initialize the AI provider manager."""
        # Use the global singleton instance instead of creating a new one
        # This ensures rate limit tracking is shared across all usages
        self.openrouter_api = openrouter_api

        self.provider_status = {
            "openrouter": ProviderStatus("openrouter", True, 0.0),
        }

        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failover_count": 0,
            "provider_usage": {"openrouter": 0},
        }

        # Validate and fix the default model if it's a known broken model
        self.default_model = self._validate_model(OPENROUTER_DEFAULT_MODEL)
        
        # User model preferences
        self.user_model_preferences = {}  # user_id -> model preference
        
        logger.info("Simple AI Provider Manager initialized (OpenRouter only)")

    def _validate_model(self, model: str) -> str:
        """Validate model and replace if it's known to be broken."""
        if model in BROKEN_MODELS:
            logger.warning(f"Replacing broken model '{model}' with working model '{WORKING_MODELS[0]}'")
            return WORKING_MODELS[0]
        return model

    async def check_provider_health(self, provider_name: str) -> ProviderStatus:
        """Check health of a specific provider."""
        if provider_name == "openrouter":
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
        Generate text using OpenRouter.

        Args:
            messages: List of message dictionaries
            model: Model to use (optional)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            tools: List of tools for function calling
            tool_choice: Tool choice strategy
            preferred_provider: Preferred provider (ignored, OpenRouter only)
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        start_time = time.time()
        self.stats["total_requests"] += 1

        # DIAGNOSTIC LOGGING: Log tool calling configuration
        if tools:
            logger.info(
                f"🔧 API Request with {len(tools)} tools: {[t.get('function', {}).get('name', 'unknown') for t in tools]}"
            )
            logger.debug(
                f"Tool choice: {tool_choice}, Model: {model or self.default_model}"
            )
        else:
            logger.debug(
                f"API Request with NO tools, Model: {model or self.default_model}"
            )

        try:
            request_start = time.time()
            result = await asyncio.to_thread(
                self.openrouter_api.generate_text,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                reasoning={"enabled": False},  # Explicitly disable thinking for OpenRouter
                **kwargs,
            )

            request_time = time.time() - request_start
            logger.debug(f"OpenRouter API call completed in {request_time:.2f}s")

            if isinstance(result, dict) and "error" in result:
                logger.error(f"OpenRouter error: {result['error']}")
                return result

            response_time = time.time() - start_time
            self.stats["successful_requests"] += 1
            self.stats["provider_usage"]["openrouter"] += 1

            logger.info(f"Generated text via openrouter ({response_time:.2f}s)")

            return result

        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Text generation failed: {error_msg}")
            return {"error": error_msg}

    async def generate_text_for_web_search(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 800,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate text using a specific model optimized for web search responses.
        Uses a model that doesn't have reasoning/output separation issues.

        Args:
            messages: List of message dictionaries
            temperature: Lower temperature for focused responses
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        start_time = time.time()
        self.stats["total_requests"] += 1

        logger.debug(f"Web search API request with model: {WEB_SEARCH_MODEL}")

        try:
            request_start = time.time()
            result = await asyncio.to_thread(
                self.openrouter_api.generate_text,
                messages=messages,
                model=WEB_SEARCH_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=None,
                tool_choice=None,
                **kwargs,
            )

            request_time = time.time() - request_start
            logger.debug(f"Web search API call completed in {request_time:.2f}s")

            if isinstance(result, dict) and "error" in result:
                logger.error(f"Web search OpenRouter error: {result['error']}")
                return result

            response_time = time.time() - start_time
            self.stats["successful_requests"] += 1
            self.stats["provider_usage"]["openrouter"] += 1

            logger.info(f"Web search text generated via {WEB_SEARCH_MODEL} ({response_time:.2f}s)")

            return result

        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"Web search text generation failed: {error_msg}")
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
        Generate image using Arta API (if available).

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
        from media.image_generator import image_generator

        start_time = time.time()
        self.stats["total_requests"] += 1

        try:
            image_url = image_generator.generate_image(
                prompt=prompt,
                model=model,
                width=width,
                height=height,
                seed=seed,
                **kwargs,
            )

            response_time = time.time() - start_time
            self.stats["successful_requests"] += 1

            if not image_url.startswith("Error:"):
                logger.info(f"Generated image via Arta ({response_time:.2f}s)")
                return image_url
            else:
                logger.error(f"Image generation failed: {image_url}")
                return image_url

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
        }

    def reset_statistics(self):
        """Reset all statistics."""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failover_count": 0,
            "provider_usage": {"openrouter": 0},
        }
        logger.info("AI Provider statistics reset")

    async def health_check_all(self) -> Dict[str, ProviderStatus]:
        """Perform health check on all providers."""
        results = {}
        for provider in ["openrouter"]:
            results[provider] = await self.check_provider_health(provider)
        return results

    def _is_model_available(self, model: str, provider: str) -> bool:
        """
        Check if a model is available on a specific provider.
        """
        provider_models = {
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
        """
        self.user_model_preferences[user_id] = model
        logger.info(f"Set model preference for user {user_id}: {model}")

    def get_user_model_preference(self, user_id: str) -> Optional[str]:
        """
        Get a user's preferred model.
        """
        return self.user_model_preferences.get(user_id)


# Global AI provider manager instance
ai_provider_manager = SimpleAIProviderManager()

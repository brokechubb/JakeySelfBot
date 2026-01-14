import requests
import json
import time
import threading
import random
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    OPENROUTER_MODELS_URL,
    OPENROUTER_DEFAULT_MODEL,
    OPENROUTER_ENABLED,
    OPENROUTER_SITE_URL,
    OPENROUTER_APP_NAME,
    OPENROUTER_TEXT_TIMEOUT,
    OPENROUTER_HEALTH_TIMEOUT,
    TEXT_API_RATE_LIMIT,
)
import logging

# Configure logging
from utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class OpenRouterLimits:
    """OpenRouter API key limits and usage information."""
    label: str
    limit: Optional[float]  # Credit limit, None if unlimited
    limit_remaining: Optional[float]  # Remaining credits, None if unlimited
    usage: float  # Total credits used (all time)
    usage_daily: float  # Credits used today (UTC)
    usage_weekly: float  # Credits used this week
    usage_monthly: float  # Credits used this month
    is_free_tier: bool  # Whether user has paid before
    free_requests_today: int  # Tracked locally for free model requests
    free_requests_limit: int  # 50 if free tier, 1000 if paid
    last_updated: float  # Timestamp of last API check
    
    @property
    def free_requests_remaining(self) -> int:
        """Calculate remaining free requests for today."""
        return max(0, self.free_requests_limit - self.free_requests_today)
    
    @property
    def is_daily_limit_exceeded(self) -> bool:
        """Check if daily free request limit is exceeded."""
        return self.free_requests_today >= self.free_requests_limit
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/display."""
        return {
            "label": self.label,
            "limit": self.limit,
            "limit_remaining": self.limit_remaining,
            "usage_daily": self.usage_daily,
            "is_free_tier": self.is_free_tier,
            "free_requests_today": self.free_requests_today,
            "free_requests_limit": self.free_requests_limit,
            "free_requests_remaining": self.free_requests_remaining,
        }


class OpenRouterAPI:
    # OpenRouter API endpoints
    KEY_INFO_URL = "https://openrouter.ai/api/v1/key"
    GENERATION_STATS_URL = "https://openrouter.ai/api/v1/generation"
    
    # Free model rate limits per OpenRouter docs
    FREE_MODEL_RATE_LIMIT_PER_MIN = 20
    FREE_MODEL_DAILY_LIMIT_FREE_TIER = 50  # < 10 credits purchased
    FREE_MODEL_DAILY_LIMIT_PAID_TIER = 1000  # >= 10 credits purchased
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.api_url = OPENROUTER_API_URL
        self.models_url = OPENROUTER_MODELS_URL
        self.default_model = OPENROUTER_DEFAULT_MODEL
        self.enabled = bool(OPENROUTER_ENABLED and self.api_key)  # Ensure boolean, not API key leak
        self.site_url = OPENROUTER_SITE_URL
        self.app_name = OPENROUTER_APP_NAME
        
        # Timeout configuration
        self.text_timeout = OPENROUTER_TEXT_TIMEOUT
        self.health_timeout = OPENROUTER_HEALTH_TIMEOUT
        
        # Rate limiting setup - use stricter of config or OpenRouter's limit
        self.rate_limit = min(TEXT_API_RATE_LIMIT, self.FREE_MODEL_RATE_LIMIT_PER_MIN)
        self._requests = []
        self._rate_lock = threading.Lock()
        
        # Model cache
        self._models_cache = []
        self._models_cache_time = 0
        self._models_cache_duration = 3600  # cache for 1 hour
        
        # API limits tracking
        self._limits: Optional[OpenRouterLimits] = None
        self._limits_cache_duration = 300  # Check limits every 5 minutes
        self._free_requests_today = 0
        self._last_reset_date: Optional[str] = None  # Track UTC date for daily reset
        
        # Fallback models for automatic model routing
        # OpenRouter limits the models array to 3 items max
        # Avoid models with mandatory reasoning (openai/gpt-oss-120b)
        # Avoid Google models - OpenRouter's Google billing is often disabled (403 errors)
        self.fallback_models = [
            "xiaomi/mimo-v2-flash:free",
            "qwen/qwen3-coder:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ]
        
        logger.info(f"OpenRouter API initialized: enabled={self.enabled}, model={self.default_model}, timeout={self.text_timeout}s, rate_limit={self.rate_limit}/min")
    
    def _reset_daily_counter_if_needed(self) -> None:
        """Reset daily free request counter if UTC date has changed."""
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._last_reset_date != current_date:
            logger.info(f"OpenRouter: New UTC day ({current_date}), resetting free request counter")
            self._free_requests_today = 0
            self._last_reset_date = current_date
    
    def get_api_limits(self, force_refresh: bool = False) -> Optional[OpenRouterLimits]:
        """
        Get current API key limits and usage from OpenRouter.
        
        Returns OpenRouterLimits object with:
        - Credit limits and remaining
        - Daily/weekly/monthly usage
        - Free tier status
        - Local tracking of free model requests
        """
        if not self.enabled:
            return None
        
        # Reset daily counter if needed
        self._reset_daily_counter_if_needed()
        
        # Return cached limits if still valid
        current_time = time.time()
        if (not force_refresh 
            and self._limits 
            and current_time - self._limits.last_updated < self._limits_cache_duration):
            # Update local tracking in cached limits
            self._limits.free_requests_today = self._free_requests_today
            return self._limits
        
        try:
            response = requests.get(
                self.KEY_INFO_URL,
                headers=self._get_headers(),
                timeout=self.health_timeout
            )
            
            if response.status_code == 200:
                data = response.json().get("data", {})
                
                is_free_tier = data.get("is_free_tier", True)
                daily_limit = (self.FREE_MODEL_DAILY_LIMIT_FREE_TIER 
                              if is_free_tier 
                              else self.FREE_MODEL_DAILY_LIMIT_PAID_TIER)
                
                self._limits = OpenRouterLimits(
                    label=data.get("label", "unknown"),
                    limit=data.get("limit"),
                    limit_remaining=data.get("limit_remaining"),
                    usage=data.get("usage", 0),
                    usage_daily=data.get("usage_daily", 0),
                    usage_weekly=data.get("usage_weekly", 0),
                    usage_monthly=data.get("usage_monthly", 0),
                    is_free_tier=is_free_tier,
                    free_requests_today=self._free_requests_today,
                    free_requests_limit=daily_limit,
                    last_updated=current_time,
                )
                
                logger.debug(f"OpenRouter limits: {self._limits.to_dict()}")
                return self._limits
                
            elif response.status_code == 401:
                logger.error("OpenRouter: Invalid API key when checking limits")
                return None
            else:
                logger.warning(f"OpenRouter: Failed to get limits (HTTP {response.status_code})")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"OpenRouter: Error fetching limits: {e}")
            return None
    
    def check_rate_limits(self) -> Dict[str, Any]:
        """
        Check current rate limit status.
        
        Returns dict with:
        - can_request: bool - whether a request can be made now
        - reason: str - reason if can_request is False
        - limits: dict - current limit information
        """
        self._reset_daily_counter_if_needed()
        
        # Get limits from API
        limits = self.get_api_limits()
        
        result = {
            "can_request": True,
            "reason": None,
            "limits": limits.to_dict() if limits else None,
            "requests_per_min": len(self._requests),
            "rate_limit_per_min": self.rate_limit,
        }
        
        # Check per-minute rate limit
        current_time = time.time()
        with self._rate_lock:
            self._requests[:] = [t for t in self._requests if current_time - t < 60]
            if len(self._requests) >= self.rate_limit:
                result["can_request"] = False
                result["reason"] = f"Per-minute rate limit exceeded ({self.rate_limit}/min)"
                return result
        
        # Check daily free model limit
        if limits:
            if limits.is_daily_limit_exceeded:
                result["can_request"] = False
                result["reason"] = (
                    f"Daily free model limit exceeded ({limits.free_requests_limit}/day). "
                    f"Resets at UTC midnight."
                )
                return result
            
            # Check if credits are negative (402 errors will occur)
            if limits.limit_remaining is not None and limits.limit_remaining < 0:
                result["can_request"] = False
                result["reason"] = "Negative credit balance. Add credits to continue."
                return result
        
        return result
    
    def _record_free_request(self) -> None:
        """Record a free model request for daily tracking."""
        self._reset_daily_counter_if_needed()
        self._free_requests_today += 1
        
        if self._limits:
            self._limits.free_requests_today = self._free_requests_today
            
        logger.debug(f"OpenRouter: Free requests today: {self._free_requests_today}")
    
    def _is_free_model(self, model: str) -> bool:
        """Check if a model is a free model."""
        return model.endswith(":free")

    def _is_rate_limited(self, current_time: float) -> bool:
        """Check if we're currently rate limited"""
        with self._rate_lock:
            # Remove requests older than 60 seconds
            self._requests[:] = [t for t in self._requests if current_time - t < 60]
            
            # Check if we've exceeded the rate limit
            if len(self._requests) >= self.rate_limit:
                return True
            
            # Add current request
            self._requests.append(current_time)
            return False

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers for OpenRouter API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }
        return headers

    def check_service_health(self) -> Dict[str, Any]:
        """Check if OpenRouter service is healthy"""
        if not self.enabled:
            return {"healthy": False, "status": "disabled", "error": "OpenRouter is disabled"}
        
        try:
            # Try to fetch models as a health check
            response = requests.get(self.models_url, headers=self._get_headers(), timeout=self.health_timeout)
            if response.status_code == 200:
                return {"healthy": True, "status": "ok", "response_time": response.elapsed.total_seconds()}
            elif response.status_code == 401:
                return {"healthy": False, "status": "unauthorized", "error": "Invalid API key"}
            elif response.status_code == 429:
                return {"healthy": False, "status": "rate_limited", "error": "Rate limit exceeded"}
            else:
                return {"healthy": False, "status": f"http_{response.status_code}", "error": f"HTTP {response.status_code}"}
        except requests.exceptions.Timeout:
            return {"healthy": False, "status": "timeout", "error": "Request timeout"}
        except requests.exceptions.ConnectionError:
            return {"healthy": False, "status": "connection_error", "error": "Cannot connect to service"}
        except requests.exceptions.RequestException as e:
            return {"healthy": False, "status": "request_error", "error": str(e)}

    def list_models(self) -> List[str]:
        """List available text models from OpenRouter"""
        if not self.enabled:
            return []
        
        current_time = time.time()
        
        # Return cached models if cache is still valid
        if (current_time - self._models_cache_time < self._models_cache_duration 
            and self._models_cache):
            return [model["id"] for model in self._models_cache]
        
        try:
            response = requests.get(self.models_url, headers=self._get_headers(), timeout=self.health_timeout)
            response.raise_for_status()
            data = response.json()
            
            # Cache the models
            self._models_cache = data.get("data", [])
            self._models_cache_time = current_time
            
            # Extract model IDs
            models = [model["id"] for model in self._models_cache]
            logger.info(f"OpenRouter: Retrieved {len(models)} models")
            return models
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter: Failed to fetch models: {e}")
            return []

    def generate_text(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        # New parameters from OpenRouter API reference
        top_p: Optional[float] = None,  # Range: (0, 1]
        top_k: Optional[int] = None,  # Range: [1, Infinity)
        frequency_penalty: Optional[float] = None,  # Range: [-2, 2]
        presence_penalty: Optional[float] = None,  # Range: [-2, 2]
        repetition_penalty: Optional[float] = None,  # Range: (0, 2]
        seed: Optional[int] = None,  # For deterministic inference
        stop: Optional[Union[str, List[str]]] = None,  # Stop sequences
        response_format: Optional[Dict[str, str]] = None,  # {"type": "json_object"}
        # Reasoning tokens configuration
        reasoning: Optional[Dict[str, Any]] = None,  # Reasoning config object
        # Provider preferences
        provider: Optional[Dict[str, Any]] = None,  # Provider routing options
        # Model fallback routing
        fallback_models: Optional[List[str]] = None,  # Models to try if primary fails
        use_fallback_routing: bool = False,  # Enable OpenRouter's model fallback
        # User tracking for abuse detection
        user: Optional[str] = None,  # Stable identifier for end-users
    ) -> Dict[str, Any]:
        """
        Generate text using OpenRouter API with full parameter support.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model ID (e.g., 'openai/gpt-oss-120b:free')
            temperature: Creativity (0-2, default 0.7)
            max_tokens: Max response length
            tools: Function calling tools
            tool_choice: Tool selection mode ('auto', 'none', or specific)
            top_p: Nucleus sampling (0-1)
            top_k: Limit token choices
            frequency_penalty: Reduce token repetition based on frequency (-2 to 2)
            presence_penalty: Reduce token repetition based on presence (-2 to 2)
            repetition_penalty: Reduce repetition (0-2, 1.0 = no effect)
            seed: For deterministic output
            stop: Stop sequences
            response_format: Force output format (e.g., {"type": "json_object"})
            reasoning: Reasoning tokens config. Options:
                - {"enabled": True} - Enable with defaults (medium effort)
                - {"effort": "high"} - Set effort level (xhigh/high/medium/low/minimal/none)
                - {"max_tokens": 2000} - Set specific token budget
                - {"exclude": True} - Use reasoning but don't return it
                - {"effort": "none"} - Disable reasoning entirely
            provider: Provider routing preferences (sort, order, allow_fallbacks, etc.)
            fallback_models: List of models to try if primary fails
            use_fallback_routing: Use OpenRouter's built-in model fallback
            user: User identifier for abuse tracking
        """
        if not self.enabled:
            return {"error": "OpenRouter is disabled or not configured"}
        
        # Use default model if none specified
        if not model:
            model = self.default_model
        
        # Check if using free model and verify daily limits
        is_free = self._is_free_model(model)
        if is_free:
            rate_status = self.check_rate_limits()
            if not rate_status["can_request"]:
                logger.warning(f"OpenRouter: Request blocked - {rate_status['reason']}")
                return {
                    "error": rate_status["reason"],
                    "rate_limited": True,
                    "limits": rate_status.get("limits"),
                }
        
        # Check per-minute rate limiting
        current_time = time.time()
        if self._is_rate_limited(current_time):
            return {"error": "Per-minute rate limit exceeded. Please try again later.", "rate_limited": True}
        
        # Models that support function calling
        # Updated as of Jan 2026 based on OpenRouter free models
        # NOTE: Google models removed due to OpenRouter billing issues (403 errors)
        function_calling_models = [
            "openai/gpt-oss-120b:free",
            # "google/gemini-2.0-flash-exp:free",  # Disabled - OpenRouter Google billing broken
            # "google/gemma-3-27b-it:free",  # Disabled - OpenRouter Google billing broken
            "qwen/qwen3-coder:free",
            "xiaomi/mimo-v2-flash:free",
            "mistralai/devstral-2512:free",
            "kwaipilot/kat-coder-pro:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "nvidia/nemotron-nano-9b-v2:free",
            "nex-agi/deepseek-v3.1-nex-n1:free",
        ]
        
        # If tools are provided but model doesn't support function calling, use gpt-oss-120b
        if tools and model not in function_calling_models:
            original_model = model
            model = "openai/gpt-oss-120b:free"  # Best free model with function calling
            is_free = True  # This model is also free
            logger.debug(f"Model {original_model} doesn't support function calling. Switching to {model} for tool use.")
        
        # Build request payload with all supported parameters
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add optional sampling parameters (only if specified)
        if top_p is not None:
            payload["top_p"] = top_p
        if top_k is not None:
            payload["top_k"] = top_k
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty
        if seed is not None:
            payload["seed"] = seed
        if stop is not None:
            payload["stop"] = stop
        if response_format is not None:
            payload["response_format"] = response_format
        
        # Add reasoning configuration - disabled for all models per OpenRouter specifications
        # Supports: enabled, effort (xhigh/high/medium/low/minimal/none), max_tokens, exclude
        if reasoning is not None:
            payload["reasoning"] = reasoning
        else:
            # Default: disable reasoning for all models per OpenRouter specifications
            payload["reasoning"] = {"enabled": False}
        
        # Add tools if supported by the model
        if tools and tool_choice:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        
        # Add provider preferences for routing
        # Venice has frequent 502 errors, but we need to handle "all providers ignored" scenario
        default_ignore = []  # Start with empty ignore list to avoid 404 errors
        if provider is not None:
            # Merge user-specified ignores with default ignores
            existing_ignore = provider.get("ignore", [])
            provider["ignore"] = list(set(existing_ignore + default_ignore))
            payload["provider"] = provider
        else:
            # Only add ignore if we have specific providers to ignore
            if default_ignore:
                payload["provider"] = {"ignore": default_ignore}
        
        # Add model fallback routing
        if use_fallback_routing:
            models_to_use = fallback_models or self.fallback_models
            if model not in models_to_use:
                models_to_use = [model] + models_to_use
            # OpenRouter limits the models array to 3 items max
            models_to_use = models_to_use[:3]
            payload["models"] = models_to_use
            payload["route"] = "fallback"
            logger.debug(f"OpenRouter: Using fallback routing with models: {models_to_use}")
        
        # Add user identifier for abuse tracking
        if user is not None:
            payload["user"] = user
        
        # Retry loop for 429 Rate Limit and connection issues
        max_retries = 5
        retry_delay = 3.0  # initial delay
        
        # Increase timeout for requests with many tools (larger payloads)
        current_timeout = self.text_timeout
        if tools and len(tools) > 20:  # Large tool arrays need more time
            current_timeout = min(self.text_timeout * 2, 120)  # Double timeout, max 2 minutes
            logger.debug(f"OpenRouter: Increased timeout to {current_timeout}s for {len(tools)} tools")
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"OpenRouter: Making request to model {model} (Attempt {attempt+1}/{max_retries+1})")
                response = requests.post(
                    self.api_url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=current_timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Track free model usage
                    if is_free:
                        self._record_free_request()
                    logger.debug(f"OpenRouter: Successful response from {model}")
                    return result
                elif response.status_code == 401:
                    error_msg = "Invalid OpenRouter API key"
                    logger.error(f"OpenRouter: {error_msg}")
                    return {"error": error_msg}
                elif response.status_code == 402:
                    # Payment required - negative balance
                    error_msg = "OpenRouter: Negative credit balance. Add credits to continue."
                    logger.error(f"OpenRouter: {error_msg}")
                    return {"error": error_msg, "payment_required": True}
                elif response.status_code == 429:
                    error_msg = "OpenRouter rate limit exceeded"
                    
                    # Track as a free request anyway (it still counts against limits)
                    if is_free:
                        self._record_free_request()
                    
                    # If we have retries left, wait and retry
                    if attempt < max_retries:
                        sleep_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"OpenRouter: Rate limited (429). Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.error(f"OpenRouter: {error_msg} - Max retries reached")
                        return {"error": error_msg}
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Bad request")
                    logger.error(f"OpenRouter: {error_msg}")
                    logger.error(f"OpenRouter 400 full response: {error_data}")
                    logger.error(f"OpenRouter request model: {model}, tools provided: {bool(tools)}, tools count: {len(tools) if tools else 0}")
                    return {"error": f"OpenRouter API error: {error_msg}"}
                elif response.status_code in (502, 503, 504):
                    # Server/gateway errors - usually transient, retry
                    error_msg = f"OpenRouter HTTP {response.status_code}"
                    
                    if attempt < max_retries:
                        sleep_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"OpenRouter: {error_msg} (provider error). Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.error(f"OpenRouter: {error_msg} - Max retries reached - {response.text}")
                        return {"error": error_msg}
                else:
                    error_msg = f"OpenRouter HTTP {response.status_code}"
                    logger.error(f"OpenRouter: {error_msg} - {response.text}")
                    
                    # Special handling for "All providers have been ignored" error
                    if response.status_code == 404 and "All providers have been ignored" in response.text:
                        logger.warning("OpenRouter: All providers ignored - retrying without provider ignore list")
                        # Remove provider ignore and retry once
                        if "provider" in payload:
                            del payload["provider"]
                            try:
                                logger.debug(f"OpenRouter: Retrying request to model {model} without provider ignore")
                                response = requests.post(
                                    self.api_url,
                                    headers=self._get_headers(),
                                    json=payload,
                                    timeout=current_timeout
                                )
                                if response.status_code == 200:
                                    result = response.json()
                                    if is_free:
                                        self._record_free_request()
                                    logger.debug(f"OpenRouter: Successful response from {model} after removing provider ignore")
                                    return result
                            except Exception as retry_error:
                                logger.error(f"OpenRouter: Retry without provider ignore failed: {retry_error}")
                    
                    return {"error": error_msg}
                    
            except requests.exceptions.Timeout:
                error_msg = "OpenRouter request timeout"
                logger.error(f"OpenRouter: {error_msg}")
                # Optional: retry on timeout? 
                if attempt < max_retries:
                     logger.warning(f"OpenRouter: Timeout. Retrying...")
                     time.sleep(1)
                     continue
                return {"error": error_msg}
            except requests.exceptions.ConnectionError:
                error_msg = "Cannot connect to OpenRouter service"
                logger.error(f"OpenRouter: {error_msg}")
                if attempt < max_retries:
                     time.sleep(1)
                     continue
                return {"error": error_msg}
            except requests.exceptions.RequestException as e:
                error_msg = f"OpenRouter request error: {str(e)}"
                logger.error(f"OpenRouter: {error_msg}")
                
                # Special handling for connection issues that might be transient
                if "Response ended prematurely" in str(e) or "Connection broken" in str(e):
                    if attempt < max_retries:
                        sleep_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"OpenRouter: Connection issue. Retrying in {sleep_time:.2f}s... (Attempt {attempt+2}/{max_retries+1})")
                        time.sleep(sleep_time)
                        continue
                
                return {"error": error_msg}
            except json.JSONDecodeError as e:
                error_msg = f"OpenRouter JSON decode error: {str(e)}"
                logger.error(f"OpenRouter: {error_msg}")
                return {"error": error_msg}
        
        return {"error": "Unknown error after retries"}

    def get_free_models(self) -> List[str]:
        """Get list of free models from OpenRouter"""
        if not self.enabled:
            return []
        
        try:
            models = self.list_models()
            free_models = []
            
            # Check each model for free pricing
            for model_id in models:
                # Find the model in cache to check pricing
                for model in self._models_cache:
                    if model["id"] == model_id:
                        pricing = model.get("pricing", {})
                        prompt_price = float(pricing.get("prompt", 0))
                        completion_price = float(pricing.get("completion", 0))
                        
                        if prompt_price == 0 and completion_price == 0:
                            free_models.append(model_id)
                        break
            
            logger.info(f"OpenRouter: Found {len(free_models)} free models")
            return free_models
            
        except Exception as e:
            logger.error(f"OpenRouter: Error getting free models: {e}")
            return []

    def is_model_available(self, model: str) -> bool:
        """Check if a specific model is available"""
        if not self.enabled:
            return False
        
        try:
            models = self.list_models()
            return model in models
        except Exception as e:
            logger.error(f"OpenRouter: Error checking model availability: {e}")
            return False
    
    def get_generation_stats(self, generation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get generation statistics including native token counts and cost.
        
        Args:
            generation_id: The ID returned from a completion request (e.g., 'gen-xxxxxx')
            
        Returns:
            Dict with generation stats:
            - id: Generation ID
            - model: Model used
            - streamed: Whether streaming was used
            - generation_time: Time to generate (ms)
            - created_at: Timestamp
            - tokens_prompt: Native prompt token count
            - tokens_completion: Native completion token count
            - native_tokens_prompt: Native tokenizer prompt count
            - native_tokens_completion: Native tokenizer completion count
            - num_media_prompt: Number of media in prompt
            - num_media_completion: Number of media in completion
            - origin: Request origin
            - total_cost: Total cost in credits
        """
        if not self.enabled:
            return None
        
        try:
            response = requests.get(
                f"{self.GENERATION_STATS_URL}?id={generation_id}",
                headers=self._get_headers(),
                timeout=self.health_timeout
            )
            
            if response.status_code == 200:
                data = response.json().get("data", {})
                logger.debug(f"OpenRouter: Generation stats for {generation_id}: {data}")
                return data
            else:
                logger.warning(f"OpenRouter: Failed to get generation stats (HTTP {response.status_code})")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"OpenRouter: Error fetching generation stats: {e}")
            return None
    
    def create_provider_preferences(
        self,
        sort: Optional[str] = None,  # "price", "throughput", "latency"
        order: Optional[List[str]] = None,  # Provider order e.g., ["anthropic", "openai"]
        allow_fallbacks: bool = True,
        require_parameters: bool = False,
        data_collection: str = "allow",  # "allow" or "deny"
        ignore: Optional[List[str]] = None,  # Providers to skip
        only: Optional[List[str]] = None,  # Only these providers
        quantizations: Optional[List[str]] = None,  # e.g., ["int4", "int8", "fp8"]
    ) -> Dict[str, Any]:
        """
        Create provider preferences dict for routing control.
        
        Args:
            sort: Sort by "price", "throughput", or "latency"
            order: List of provider slugs to try in order
            allow_fallbacks: Whether to allow backup providers (default True)
            require_parameters: Only use providers supporting all parameters
            data_collection: "allow" or "deny" for data storage policies
            ignore: List of providers to skip
            only: Only allow these providers
            quantizations: Filter by quantization levels
            
        Returns:
            Dict suitable for the 'provider' parameter in generate_text()
        """
        preferences: Dict[str, Any] = {}
        
        if sort is not None:
            preferences["sort"] = sort
        if order is not None:
            preferences["order"] = order
        if not allow_fallbacks:
            preferences["allow_fallbacks"] = False
        if require_parameters:
            preferences["require_parameters"] = True
        if data_collection != "allow":
            preferences["data_collection"] = data_collection
        if ignore is not None:
            preferences["ignore"] = ignore
        if only is not None:
            preferences["only"] = only
        if quantizations is not None:
            preferences["quantizations"] = quantizations
            
        return preferences
    
    @staticmethod
    def create_reasoning_config(
        enabled: Optional[bool] = None,
        effort: Optional[str] = None,  # "xhigh", "high", "medium", "low", "minimal", "none"
        max_tokens: Optional[int] = None,
        exclude: bool = False,
    ) -> Dict[str, Any]:
        """
        Create reasoning configuration for models that support thinking/reasoning tokens.
        
        Supported models include:
        - OpenAI o-series (o1, o3, GPT-5 series)
        - Anthropic Claude 3.7+
        - Gemini thinking models
        - DeepSeek R1
        - xiaomi/mimo-v2-flash (MiMo-V2-Flash)
        - And more...
        
        Args:
            enabled: Enable reasoning with default (medium effort). 
                    Set to True for basic enablement.
            effort: Reasoning effort level:
                - "xhigh": ~95% of max_tokens for reasoning
                - "high": ~80% of max_tokens for reasoning  
                - "medium": ~50% of max_tokens for reasoning (default when enabled=True)
                - "low": ~20% of max_tokens for reasoning
                - "minimal": ~10% of max_tokens for reasoning
                - "none": Disable reasoning entirely
            max_tokens: Specific token budget for reasoning (Anthropic-style).
                       Takes precedence over effort if both specified.
            exclude: If True, model uses reasoning internally but doesn't return it.
                    Useful to save tokens in response while keeping reasoning quality.
        
        Returns:
            Dict suitable for the 'reasoning' parameter in generate_text()
            
        Examples:
            # Enable with defaults (medium effort)
            create_reasoning_config(enabled=True)
            
            # High effort reasoning
            create_reasoning_config(effort="high")
            
            # Disable reasoning on a thinking model
            create_reasoning_config(effort="none")
            
            # Specific token budget (Anthropic models)
            create_reasoning_config(max_tokens=2000)
            
            # Use reasoning but don't include in response
            create_reasoning_config(effort="high", exclude=True)
        """
        config: Dict[str, Any] = {}
        
        # Only one of enabled, effort, or max_tokens should be primary
        if max_tokens is not None:
            config["max_tokens"] = max_tokens
        elif effort is not None:
            config["effort"] = effort
        elif enabled is not None:
            config["enabled"] = enabled
        
        # exclude can be combined with any of the above
        if exclude:
            config["exclude"] = True
            
        return config


# Create global instance
openrouter_api = OpenRouterAPI()
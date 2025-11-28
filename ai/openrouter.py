import requests
import json
import time
import threading
from typing import List, Dict, Any, Optional, Union
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
)
import logging

# Configure logging
from utils.logging_config import get_logger

logger = get_logger(__name__)


class OpenRouterAPI:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.api_url = OPENROUTER_API_URL
        self.models_url = OPENROUTER_MODELS_URL
        self.default_model = OPENROUTER_DEFAULT_MODEL
        self.enabled = OPENROUTER_ENABLED and self.api_key
        self.site_url = OPENROUTER_SITE_URL
        self.app_name = OPENROUTER_APP_NAME
        
        # Timeout configuration
        self.text_timeout = OPENROUTER_TEXT_TIMEOUT
        self.health_timeout = OPENROUTER_HEALTH_TIMEOUT
        
        # Rate limiting setup (similar to Pollinations)
        self.rate_limit = 60  # requests per minute for free tier
        self._requests = []
        self._rate_lock = threading.Lock()
        
        # Model cache
        self._models_cache = []
        self._models_cache_time = 0
        self._models_cache_duration = 3600  # cache for 1 hour
        
        logger.info(f"OpenRouter API initialized: enabled={self.enabled}, model={self.default_model}, timeout={self.text_timeout}s")

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
    ) -> Dict[str, Any]:
        """Generate text using OpenRouter API"""
        if not self.enabled:
            return {"error": "OpenRouter is disabled or not configured"}
        
        # Check rate limiting
        current_time = time.time()
        if self._is_rate_limited(current_time):
            return {"error": "Rate limit exceeded. Please try again later."}
        
        # Use default model if none specified
        if not model:
            model = self.default_model
        
        # Prepare request payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add tools if supported by the model
        if tools and tool_choice:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        
        try:
            logger.debug(f"OpenRouter: Making request to model {model}")
            response = requests.post(
                self.api_url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.text_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"OpenRouter: Successful response from {model}")
                return result
            elif response.status_code == 401:
                error_msg = "Invalid OpenRouter API key"
                logger.error(f"OpenRouter: {error_msg}")
                return {"error": error_msg}
            elif response.status_code == 429:
                error_msg = "OpenRouter rate limit exceeded"
                logger.error(f"OpenRouter: {error_msg}")
                return {"error": error_msg}
            elif response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Bad request")
                logger.error(f"OpenRouter: {error_msg}")
                return {"error": f"OpenRouter API error: {error_msg}"}
            else:
                error_msg = f"OpenRouter HTTP {response.status_code}"
                logger.error(f"OpenRouter: {error_msg} - {response.text}")
                return {"error": error_msg}
                
        except requests.exceptions.Timeout:
            error_msg = "OpenRouter request timeout"
            logger.error(f"OpenRouter: {error_msg}")
            return {"error": error_msg}
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to OpenRouter service"
            logger.error(f"OpenRouter: {error_msg}")
            return {"error": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"OpenRouter request error: {str(e)}"
            logger.error(f"OpenRouter: {error_msg}")
            return {"error": error_msg}
        except json.JSONDecodeError as e:
            error_msg = f"OpenRouter JSON decode error: {str(e)}"
            logger.error(f"OpenRouter: {error_msg}")
            return {"error": error_msg}

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


# Create global instance
openrouter_api = OpenRouterAPI()
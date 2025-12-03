import json
import logging
import random
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Union

import requests

from config import (
    DEFAULT_MODEL,
    DYNAMIC_TIMEOUT_ENABLED,
    DYNAMIC_TIMEOUT_MAX,
    DYNAMIC_TIMEOUT_MIN,
    IMAGE_API_RATE_LIMIT,
    POLLINATIONS_API_TOKEN,
    POLLINATIONS_HEALTH_TIMEOUT,
    POLLINATIONS_IMAGE_API,
    POLLINATIONS_IMAGE_TIMEOUT,
    POLLINATIONS_TEXT_API,
    POLLINATIONS_TEXT_TIMEOUT,
    TEXT_API_RATE_LIMIT,
    TIMEOUT_HISTORY_SIZE,
    TIMEOUT_MONITORING_ENABLED,
)

# Configure logging
from utils.logging_config import get_logger

logger = get_logger(__name__)


class PollinationsAPI:
    def __init__(self):
        self.text_api_url = POLLINATIONS_TEXT_API
        self.image_api_url = POLLINATIONS_IMAGE_API
        self.api_token = POLLINATIONS_API_TOKEN
        self.default_model = DEFAULT_MODEL

        # Rate limiting setup
        self.text_rate_limit = TEXT_API_RATE_LIMIT
        self.image_rate_limit = IMAGE_API_RATE_LIMIT
        self._text_requests = []
        self._image_requests = []
        self._rate_lock = threading.Lock()

        # Timeout configuration
        self.text_timeout = POLLINATIONS_TEXT_TIMEOUT
        self.image_timeout = POLLINATIONS_IMAGE_TIMEOUT
        self.health_timeout = POLLINATIONS_HEALTH_TIMEOUT

        # Dynamic timeout adjustment
        self.dynamic_timeout_enabled = DYNAMIC_TIMEOUT_ENABLED
        self.dynamic_timeout_min = DYNAMIC_TIMEOUT_MIN
        self.dynamic_timeout_max = DYNAMIC_TIMEOUT_MAX

        # Performance monitoring
        self.timeout_monitoring_enabled = TIMEOUT_MONITORING_ENABLED
        self.timeout_history = []
        self.timeout_history_lock = threading.Lock()
        self.response_times = []

    def _is_rate_limited(self, request_type: str, current_time: float) -> bool:
        """Check if we're currently rate limited for the given request type"""
        with self._rate_lock:
            if request_type == "text":
                requests = self._text_requests
                rate_limit = self.text_rate_limit
            elif request_type == "image":
                requests = self._image_requests
                rate_limit = self.image_rate_limit
            else:
                return False

            # Remove requests older than 60 seconds
            requests[:] = [t for t in requests if current_time - t < 60]

            # Check if we've hit the rate limit
            if len(requests) >= rate_limit:
                return True

            return False

    def _record_request(self, request_type: str, current_time: float):
        """Record a request for rate limiting purposes"""
        with self._rate_lock:
            if request_type == "text":
                self._text_requests.append(current_time)
            elif request_type == "image":
                self._image_requests.append(current_time)

    def _get_dynamic_timeout(self, base_timeout: float) -> float:
        """Calculate dynamic timeout based on historical performance"""
        if not self.dynamic_timeout_enabled or not self.response_times:
            return base_timeout

        with self.timeout_history_lock:
            if len(self.response_times) < 5:  # Need at least 5 samples
                return base_timeout

            # Calculate average response time and standard deviation
            avg_response_time = sum(self.response_times) / len(self.response_times)
            variance = sum(
                (x - avg_response_time) ** 2 for x in self.response_times
            ) / len(self.response_times)
            std_dev = variance**0.5

            # Set timeout to average + 2 standard deviations, within bounds
            dynamic_timeout = avg_response_time + (2 * std_dev)
            dynamic_timeout = max(
                self.dynamic_timeout_min, min(dynamic_timeout, self.dynamic_timeout_max)
            )

            logger.debug(
                f"Dynamic timeout: {dynamic_timeout:.2f}s (avg: {avg_response_time:.2f}s, std: {std_dev:.2f}s)"
            )
            return dynamic_timeout

    def _record_response_time(self, response_time: float, success: bool):
        """Record response time for performance monitoring and dynamic adjustment"""
        if not self.timeout_monitoring_enabled:
            return

        with self.timeout_history_lock:
            # Record response time
            self.response_times.append(response_time)

            # Keep only recent history
            if len(self.response_times) > TIMEOUT_HISTORY_SIZE:
                self.response_times = self.response_times[-TIMEOUT_HISTORY_SIZE:]

            # Record timeout occurrence
            if not success:
                self.timeout_history.append(
                    {
                        "timestamp": time.time(),
                        "response_time": response_time,
                        "success": success,
                    }
                )

                # Keep timeout history manageable
                if len(self.timeout_history) > TIMEOUT_HISTORY_SIZE:
                    self.timeout_history = self.timeout_history[-TIMEOUT_HISTORY_SIZE:]

    def get_timeout_stats(self) -> Dict[str, Any]:
        """Get timeout performance statistics"""
        if not self.timeout_monitoring_enabled:
            return {"monitoring_enabled": False}

        with self.timeout_history_lock:
            total_requests = len(self.response_times)
            timeout_count = len([h for h in self.timeout_history if not h["success"]])
            timeout_rate = (
                (timeout_count / total_requests * 100) if total_requests > 0 else 0
            )

            avg_response_time = (
                (sum(self.response_times) / len(self.response_times))
                if self.response_times
                else 0
            )
            max_response_time = max(self.response_times) if self.response_times else 0
            min_response_time = min(self.response_times) if self.response_times else 0

            return {
                "monitoring_enabled": True,
                "total_requests": total_requests,
                "timeout_count": timeout_count,
                "timeout_rate_percent": round(timeout_rate, 2),
                "avg_response_time": round(avg_response_time, 2),
                "min_response_time": round(min_response_time, 2),
                "max_response_time": round(max_response_time, 2),
                "current_text_timeout": self.text_timeout,
                "dynamic_timeout_enabled": self.dynamic_timeout_enabled,
                "dynamic_timeout_min": self.dynamic_timeout_min,
                "dynamic_timeout_max": self.dynamic_timeout_max,
            }

    def generate_text(
        self,
        messages: Optional[List[Dict]] = None,
        model: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 500,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        top_p: float = 0.95,
        frequency_penalty: float = 0.2,
        presence_penalty: float = 0.0,
        stop: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate text using Pollinations API with OpenAI-compatible format
        """
        # Handle case where messages is None
        if messages is None:
            messages = []

        # Ensure messages is always a list
        if not isinstance(messages, list):
            messages = []

        if model is None:
            model = self.default_model

        # Validate and clean messages to prevent API errors
        cleaned_messages = []
        for msg in messages:
            # Create a copy to avoid modifying the original
            cleaned_msg = msg.copy() if msg else {}

            # Ensure content is never None
            if cleaned_msg.get("content") is None:
                cleaned_msg["content"] = ""

            # For assistant messages, ensure we have either content or tool_calls
            if cleaned_msg.get("role") == "assistant":
                has_content = bool(cleaned_msg.get("content", ""))
                has_tool_calls = bool(cleaned_msg.get("tool_calls"))

                # If both are empty, we need to add something
                if not has_content and not has_tool_calls:
                    cleaned_msg["content"] = (
                        ""  # At minimum, ensure content is an empty string
                    )

            cleaned_messages.append(cleaned_msg)

        # Validate role ordering to prevent API errors
        # OpenAI API requires: system (optional, first) -> user/assistant alternating -> tool (immediately after assistant with tool_calls)
        system_seen = False
        last_role = None

        for i, msg in enumerate(cleaned_messages):
            role = msg.get("role")

            # System message must be first if present
            if role == "system":
                if i > 0:
                    logger.warning(
                        f"System message found at position {i} (not first). Removing invalid system message."
                    )
                    cleaned_messages[i] = None  # Mark for removal
                    continue
                system_seen = True

            # Tool messages must come after assistant messages with tool_calls
            # They can be part of a sequence of tool messages after one assistant message
            elif role == "tool":
                if i == 0 or cleaned_messages[i - 1] is None:
                    logger.warning(
                        f"Tool message at position {i} without preceding message. Removing."
                    )
                    cleaned_messages[i] = None  # Mark for removal
                    continue

                # Find the most recent non-tool message before this one
                j = i - 1
                while (
                    j >= 0
                    and cleaned_messages[j] is not None
                    and cleaned_messages[j].get("role") == "tool"
                ):
                    j -= 1

                if j < 0 or cleaned_messages[j] is None:
                    logger.warning(
                        f"Tool message at position {i} without preceding assistant message. Removing."
                    )
                    cleaned_messages[i] = None  # Mark for removal
                    continue

                prev_role = cleaned_messages[j].get("role")
                if prev_role != "assistant":
                    logger.warning(
                        f"Tool message at position {i} after {prev_role} role (should be assistant). Removing."
                    )
                    cleaned_messages[i] = None  # Mark for removal
                    continue

                # Check if the assistant message has tool_calls
                prev_tool_calls = cleaned_messages[j].get("tool_calls")
                if not prev_tool_calls:
                    logger.warning(
                        f"Tool message at position {i} but previous assistant has no tool_calls. Removing."
                    )
                    cleaned_messages[i] = None  # Mark for removal
                    continue

            last_role = role

        # Remove None messages
        cleaned_messages = [msg for msg in cleaned_messages if msg is not None]

        payload = {"model": model, "messages": cleaned_messages}

        # Pollinations (Azure OpenAI) has limited parameter support
        # Only include parameters that are actually supported
        if model and "openai" not in model.lower():
            payload["temperature"] = temperature
            payload["max_tokens"] = max_tokens

        # Note: Pollinations/Azure OpenAI does NOT support these parameters:
        # - top_p
        # - frequency_penalty
        # - presence_penalty
        # - stop
        # So we exclude them to avoid "unsupported parameter" errors

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        headers = {"Content-Type": "application/json", "Referer": "jakeydegenbot"}

        # Add token if available
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            current_time = time.time()

            # Check rate limiting before making request
            if self._is_rate_limited("text", current_time):
                logger.warning(f"🔥 Rate limit hit for text API - too many requests")
                return {
                    "error": "Rate limit exceeded for text generation. Please wait before making another request."
                }

            # Debug: Log the payload being sent
            logger.debug(f"📤 Sending payload to {self.text_api_url}")
            logger.debug(f"📤 Model: {model}")
            logger.debug(f"📤 Messages count: {len(cleaned_messages)}")
            logger.debug(f"📤 Tools included: {'Yes' if tools else 'No'}")
            if tools:
                logger.debug(
                    f"📤 Available tools: {[tool['function']['name'] for tool in tools]}"
                )
            logger.debug(f"📤 Using default model from config: {self.default_model}")

            # Get dynamic timeout for this request
            request_timeout = self._get_dynamic_timeout(self.text_timeout)

            # Add improved retry logic for temporary network issues with exponential backoff
            max_retries = 1  # Allow 1 attempt before fallback, with fast timeout
            base_delay = 2  # Base delay in seconds

            response = None  # Initialize response variable
            request_start_time = time.time()

            for attempt in range(max_retries):
                try:
                    # Only log retry attempts, not the initial try
                    if attempt > 0:
                        logger.info(
                            f"Retrying Pollinations API (attempt {attempt + 1}/{max_retries})"
                        )
                    response = requests.post(
                        self.text_api_url,
                        headers=headers,
                        json=payload,
                        timeout=request_timeout,
                    )

                    # Handle specific HTTP status codes
                    if response.status_code == 502:
                        logger.warning(
                            f"🔥 API gateway error (502) - Pollinations service is down (attempt {attempt + 1}/{max_retries})"
                        )
                        if attempt < max_retries - 1:
                            # Use faster backoff for 502 errors (temporary service issues)
                            delay = min(
                                1 * (2**attempt), 8
                            )  # Max 8 seconds: 1, 2, 4, 8 seconds
                            logger.info(f"⏳ Retrying in {delay} seconds...")
                            time.sleep(delay)
                            continue
                        else:
                            logger.error(
                                "🚨 Pollinations service appears to be experiencing an outage after all retries"
                            )
                    elif response.status_code == 429:
                        logger.warning(f"🔥 Rate limit hit from Pollinations API (429)")
                        # Add a cooldown delay before returning error
                        time.sleep(1)  # Reduced for testing
                        return {
                            "error": "Rate limit exceeded from external API. Please wait a minute before trying again."
                        }

                    response.raise_for_status()

                    # Record successful request for rate limiting and performance monitoring
                    self._record_request("text", current_time)
                    response_time = time.time() - request_start_time
                    self._record_response_time(response_time, True)

                    # Only log success on retry, not on first attempt
                    if attempt > 0:
                        logger.info(
                            f"✅ Pollinations API call successful on attempt {attempt + 1}"
                        )
                    logger.debug(
                        f"Pollinations response time: {response_time:.2f}s (timeout: {request_timeout}s)"
                    )
                    return response.json()

                except requests.exceptions.Timeout:
                    response_time = time.time() - request_start_time
                    self._record_response_time(response_time, False)
                    logger.warning(
                        f"API timeout after {response_time:.2f}s (attempt {attempt + 1}/{max_retries}, timeout: {request_timeout}s)"
                    )
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        return {
                            "error": f"API timeout after {max_retries} attempts (timeout: {request_timeout}s)"
                        }

                except requests.exceptions.ConnectionError:
                    logger.warning(
                        f"Connection error (attempt {attempt + 1}/{max_retries}) - Pollinations API may be unreachable"
                    )
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        return {
                            "error": f"Connection error after {max_retries} attempts"
                        }

                except requests.exceptions.HTTPError as http_error:
                    if response is not None:
                        error_msg = f"HTTP {response.status_code}: {response.text}"
                        logger.error(f"HTTP Error: {error_msg}")

                        # Provide more specific error messages for common issues
                        if response.status_code == 502:
                            return {
                                "error": f"HTTP 502: Pollinations AI service is currently down - try again later"
                            }
                        elif response.status_code == 429:
                            return {
                                "error": f"HTTP 429: Rate limit exceeded - please wait before trying again"
                            }
                        else:
                            return {
                                "error": f"HTTP {response.status_code}: Bad request - check your message format"
                            }
                    else:
                        logger.error(f"HTTP Error: {http_error}")
                        return {"error": "HTTP Error occurred"}
                except requests.exceptions.RequestException as req_error:
                    logger.error(f"Request error: {req_error}")
                    return {"error": str(req_error)}

            # If we've exhausted all retries, return an error
            return {"error": "Failed to get response from API after all retries"}
        except Exception as e:
            logger.error(f"Critical error calling Pollinations API: {e}")
            return {"error": str(e)}

    def _enhance_image_prompt(self, user_prompt: str) -> str:
        """Enhance image prompt with stylistic additions for better results"""
        # If prompt is empty, return as is
        if not user_prompt or not user_prompt.strip():
            return user_prompt

        # Add stylistic enhancements for degenerate gambling theme
        enhanced = user_prompt.strip()

        # Add quality descriptors if not already present
        quality_terms = ["detailed", "high quality", "sharp", "professional"]
        if not any(term in enhanced.lower() for term in quality_terms):
            enhanced += " detailed high quality"

        # Add style descriptors for gambling theme
        gambling_terms = ["casino", "gambling", "poker", "slots", "dice", "cards"]
        if any(term in enhanced.lower() for term in gambling_terms):
            style_terms = ["dramatic lighting", "neon lights", "atmospheric"]
            if not any(term in enhanced.lower() for term in style_terms):
                enhanced += " dramatic lighting"

        return enhanced

    def generate_image(
        self,
        prompt: str,
        model: str = "flux",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        nologo: bool = True,
        private: bool = True,
        quality: str = "standard",
        guidance_scale: Optional[float] = None,
        num_inference_steps: Optional[int] = None,
    ) -> str:
        """
        Generate an uncensored image with automatic system prompt enhancement and return the image URL
        Images are marked as private by default to prevent public feed appearance
        """
        # Automatically enhance the prompt using the configured system prompt
        enhanced_prompt = self._enhance_image_prompt(prompt)

        # URL encode the enhanced prompt
        encoded_prompt = urllib.parse.quote(enhanced_prompt)

        # Build parameters - matching the desired format
        params = {
            "width": width,
            "height": height,
            "private": "true",  # Always mark images as private
            "enhance": "true",  # Enable image enhancement
            "model": model,
            "safe": "false",  # Disable content safety filtering
            "nologo": "true" if nologo else "false",  # Remove watermark
        }

        # Always include a random 6-digit seed
        if seed is not None:
            params["seed"] = str(seed)
        else:
            # Generate random 6-digit seed
            params["seed"] = f"{random.randint(100000, 999999)}"

        # Note: Removed quality, guidance_scale, steps, and token parameters
        # to match the desired URL format exactly

        # Build the full URL
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        image_url = f"{self.image_api_url}{encoded_prompt}?{param_string}"

        return image_url

    def check_service_health(self) -> Dict[str, Any]:
        """Check if Pollinations AI service is healthy"""
        url = "https://text.pollinations.ai/models"
        headers = {"Referer": "jakeydegenbot"}
        try:
            response = requests.get(url, headers=headers, timeout=self.health_timeout)
            if response.status_code == 200:
                return {
                    "healthy": True,
                    "status": "ok",
                    "response_time": response.elapsed.total_seconds(),
                }
            elif response.status_code == 502:
                return {
                    "healthy": False,
                    "status": "bad_gateway",
                    "error": "Service is down",
                }
            elif response.status_code == 503:
                return {
                    "healthy": False,
                    "status": "service_unavailable",
                    "error": "Service temporarily unavailable",
                }
            else:
                return {
                    "healthy": False,
                    "status": f"http_{response.status_code}",
                    "error": f"HTTP {response.status_code}",
                }
        except requests.exceptions.Timeout:
            return {"healthy": False, "status": "timeout", "error": "Request timeout"}
        except requests.exceptions.ConnectionError:
            return {
                "healthy": False,
                "status": "connection_error",
                "error": "Cannot connect to service",
            }
        except requests.exceptions.RequestException as e:
            return {"healthy": False, "status": "request_error", "error": str(e)}

    def list_text_models(self) -> List[str]:
        """List available text models"""
        url = "https://text.pollinations.ai/models?format=text"
        headers = {"Referer": "jakeydegenbot"}
        try:
            response = requests.get(url, headers=headers, timeout=self.health_timeout)
            response.raise_for_status()
            models_data = response.json()
            # Extract model names from the list of dictionaries
            return [
                model.get("name", "")
                for model in models_data
                if isinstance(model, dict) and "name" in model
            ]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching text models: {e}")
            return []

    def list_image_models(self) -> List[str]:
        """List available image models"""
        url = "https://image.pollinations.ai/models?format=text"
        headers = {"Referer": "jakeydegenbot"}
        try:
            response = requests.get(url, headers=headers, timeout=self.health_timeout)
            response.raise_for_status()
            models_data = response.json()
            # Extract model names from the list of dictionaries
            return [
                model.get("name", "")
                for model in models_data
                if isinstance(model, dict) and "name" in model
            ]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching image models: {e}")
            return []

    def generate_audio(
        self, text: str, model: str = "openai-audio", voice: str = "nova"
    ) -> str:
        """
        Generate audio from text using Pollinations API
        """
        # URL encode the text
        encoded_text = urllib.parse.quote(text)

        # Build parameters
        params = {"model": model, "voice": voice}

        # Add token if available
        if self.api_token:
            params["token"] = self.api_token

        # Build the full URL
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        audio_url = f"https://text.pollinations.ai/{encoded_text}?{param_string}"

        return audio_url

    def analyze_image(
        self, image_url: str, prompt: str = "Describe this image"
    ) -> Dict[str, Any]:
        """
        Analyze an image using Pollinations API vision capabilities
        """
        payload = {
            "model": "openai",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        }

        headers = {"Content-Type": "application/json", "Referer": "jakeydegenbot"}

        # Add token if available
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            current_time = time.time()

            # Check rate limiting before making request
            if self._is_rate_limited("text", current_time):
                logger.warning(f"🔥 Rate limit hit for text API - too many requests")
                return {
                    "error": "Rate limit exceeded for image analysis. Please wait before making another request."
                }

            response = requests.post(
                self.text_api_url,
                headers=headers,
                json=payload,
                timeout=self.text_timeout,
            )
            response.raise_for_status()

            # Record successful request for rate limiting
            self._record_request("text", current_time)

            return response.json()

        except requests.exceptions.RequestException as e:
            error_msg = f"Error analyzing image: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Critical error analyzing image: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    def get_model_info(self, model_type: str = "text") -> Dict[str, Any]:
        """
        Get detailed information about available models
        """
        # Fallback to listing models if info endpoint is not available
        try:
            if model_type == "text":
                models = self.list_text_models()
                return {"models": models, "type": "text"}
            elif model_type == "image":
                models = self.list_image_models()
                return {"models": models, "type": "image"}
            else:
                return {"error": "Invalid model type. Use 'text' or 'image'."}
        except Exception as e:
            logger.error(f"Error fetching model info: {e}")
            return {"error": str(e)}


# Global API instance
pollinations_api = PollinationsAPI()

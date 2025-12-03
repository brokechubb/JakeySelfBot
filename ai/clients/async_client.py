"""Async client for Pollinations API with Pydantic models"""
import httpx
import json
import urllib.parse
import time
import asyncio
import threading
from typing import List, Dict, Any, Optional, Union
from ai.models.text_models import TextGenerationRequest, TextGenerationResponse, Message
from ai.models.image_models import ImageGenerationRequest, ImageGenerationResponse
from config import POLLINATIONS_TEXT_API, POLLINATIONS_IMAGE_API, POLLINATIONS_API_TOKEN, DEFAULT_MODEL, TEXT_API_RATE_LIMIT, IMAGE_API_RATE_LIMIT
import logging

# Configure logging
from utils.logging_config import get_logger
logger = get_logger(__name__)


class AsyncPollinationsClient:
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

        # HTTP client
        self._client = httpx.AsyncClient(timeout=15.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    def _is_rate_limited(self, request_type: str, current_time: float) -> bool:
        """Check if we're currently rate limited for the given request type"""
        with self._rate_lock:
            if request_type == 'text':
                requests = self._text_requests
                rate_limit = self.text_rate_limit
            elif request_type == 'image':
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
            if request_type == 'text':
                self._text_requests.append(current_time)
            elif request_type == 'image':
                self._image_requests.append(current_time)

    async def generate_text(self, request: TextGenerationRequest) -> TextGenerationResponse:
        """
        Generate text using Pollinations API with OpenAI-compatible format
        """
        try:
            current_time = time.time()

            # Check rate limiting before making request
            if self._is_rate_limited('text', current_time):
                return TextGenerationResponse(error="Rate limit exceeded for text generation. Please wait before making another request.")

            # Prepare payload
            if request.model is None:
                request.model = self.default_model

            # Validate and clean messages to prevent API errors
            cleaned_messages = []
            for msg in request.messages:
                # Create a copy to avoid modifying the original
                cleaned_msg = {"role": msg.role, "content": msg.content or ""}
                
                # For assistant messages, ensure we have either content or tool_calls
                if cleaned_msg.get('role') == 'assistant':
                    has_content = bool(cleaned_msg.get('content', ''))
                    has_tool_calls = bool(cleaned_msg.get('tool_calls'))
                    
                    # If both are empty, we need to add something
                    if not has_content and not has_tool_calls:
                        cleaned_msg['content'] = ''  # At minimum, ensure content is an empty string
                        
                cleaned_messages.append(cleaned_msg)

            payload = {
                "model": request.model,
                "messages": cleaned_messages
            }
            
            # Only include temperature and max_tokens for models that support them
            if request.model and "openai" not in request.model.lower():
                payload["temperature"] = request.temperature
                payload["max_tokens"] = request.max_tokens
            
            if request.tools:
                payload["tools"] = request.tools
                payload["tool_choice"] = request.tool_choice
                
            headers = {
                "Content-Type": "application/json",
                "Referer": "jakeydegenbot"
            }

            # Add token if available
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"

            # Debug: Log the payload being sent
            logger.debug(f"📤 Sending payload to {self.text_api_url}")
            logger.debug(f"📤 Model: {request.model}")
            logger.debug(f"📤 Messages count: {len(cleaned_messages)}")
            logger.debug(f"📤 Tools included: {'Yes' if request.tools else 'No'}")
            if request.tools:
                logger.debug(f"📤 Available tools: {[tool['function']['name'] for tool in request.tools]}")
            logger.debug(f"📤 Using default model from config: {self.default_model}")

            # Add improved retry logic for temporary network issues with exponential backoff
            max_retries = 1  # Reduced for faster fallback to OpenRouter
            base_delay = 2   # Base delay in seconds

            for attempt in range(max_retries):
                try:
                    # Only log retry attempts, not the initial try
                    if attempt > 0:
                        logger.info(f"Retrying Pollinations API (attempt {attempt + 1}/{max_retries})")
                    response = await self._client.post(self.text_api_url, headers=headers, json=payload)

                    # Handle specific HTTP status codes
                    if response.status_code == 502:
                        logger.warning(f"API gateway error (502) - Pollinations service may be down")
                        if attempt < max_retries - 1:
                            # Use faster backoff for 502 errors (temporary service issues)
                            delay = min(1 * (2 ** attempt), 8)  # Max 8 seconds: 1, 2, 4, 8 seconds
                            logger.info(f"Retrying in {delay} seconds...")
                            await asyncio.sleep(delay)
                            continue
                    elif response.status_code == 429:
                        logger.warning(f"🔥 Rate limit hit from Pollinations API (429)")
                        # Add a cooldown delay before returning error
                        await asyncio.sleep(60)  # Wait 60 seconds
                        return TextGenerationResponse(error="Rate limit exceeded from external API. Please wait a minute before trying again.")

                    response.raise_for_status()

                    # Record successful request for rate limiting
                    self._record_request('text', current_time)

                    # Only log success on retry, not on first attempt
                    if attempt > 0:
                        logger.info(f"Pollinations success on attempt {attempt + 1}")
                    
                    response_data = response.json()
                    return TextGenerationResponse(
                        content=response_data.get("content"),
                        model=response_data.get("model"),
                        usage=response_data.get("usage")
                    )

                except httpx.TimeoutException:
                    logger.warning(f"API timeout (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.info(f"Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        return TextGenerationResponse(error=f"API timeout after {max_retries} attempts")

                except httpx.ConnectError:
                    logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}) - Pollinations API may be unreachable")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.info(f"Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        return TextGenerationResponse(error=f"Connection error after {max_retries} attempts")

                except httpx.HTTPStatusError as http_error:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.error(f"HTTP Error: {error_msg}")
                    return TextGenerationResponse(error=f"HTTP {response.status_code}: Bad request - check your message format")

                except httpx.RequestError as req_error:
                    logger.error(f"Request error: {req_error}")
                    return TextGenerationResponse(error=str(req_error))

            # If we've exhausted all retries, return an error
            return TextGenerationResponse(error="Failed to get response from API after all retries")
        except Exception as e:
            logger.error(f"Critical error calling Pollinations API: {e}")
            return TextGenerationResponse(error=str(e))

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

    def generate_image_url(self, request: ImageGenerationRequest) -> str:
        """
        Generate an uncensored image URL with automatic system prompt enhancement
        Images are marked as private by default to prevent public feed appearance
        """
        # Automatically enhance the prompt using the configured system prompt
        enhanced_prompt = self._enhance_image_prompt(request.prompt)

        # URL encode the enhanced prompt
        encoded_prompt = urllib.parse.quote(enhanced_prompt)

        # Build parameters - always private, no content filtering
        params = {
            "model": request.model,
            "width": request.width,
            "height": request.height,
            "nologo": "true" if request.nologo else "false",
            "private": "true"  # Always mark images as private
        }

        # Only add seed if it's not None
        if request.seed is not None:
            params["seed"] = str(request.seed)

        # Add token if available
        if self.api_token:
            params["token"] = self.api_token

        # Build the full URL
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        image_url = f"{self.image_api_url}{encoded_prompt}?{param_string}"

        return image_url

    async def list_text_models(self) -> List[str]:
        """List available text models"""
        url = "https://text.pollinations.ai/models?format=text"
        headers = {
            "Referer": "jakeydegenbot"
        }
        try:
            response = await self._client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            models_data = response.json()
            # Extract model names from the list of dictionaries
            return [model.get("name", "") for model in models_data if isinstance(model, dict) and "name" in model]
        except httpx.RequestError as e:
            logger.error(f"Error fetching text models: {e}")
            return []

    async def list_image_models(self) -> List[str]:
        """List available image models"""
        url = "https://image.pollinations.ai/models?format=text"
        headers = {
            "Referer": "jakeydegenbot"
        }
        try:
            response = await self._client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            models_data = response.json()
            # Extract model names from the list of dictionaries
            return [model.get("name", "") for model in models_data if isinstance(model, dict) and "name" in model]
        except httpx.RequestError as e:
            logger.error(f"Error fetching image models: {e}")
            return []


# Global API instance
async_pollinations_client = AsyncPollinationsClient()

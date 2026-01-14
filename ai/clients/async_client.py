"""Async client for OpenRouter API with Pydantic models"""
import httpx
import json
import time
import asyncio
from typing import List, Dict, Any, Optional, Union
from ai.models.text_models import TextGenerationRequest, TextGenerationResponse, Message
from ai.models.image_models import ImageGenerationRequest, ImageGenerationResponse
from config import OPENROUTER_API_URL, OPENROUTER_API_KEY, OPENROUTER_DEFAULT_MODEL, TEXT_API_RATE_LIMIT, OPENROUTER_TEXT_TIMEOUT
import logging

from utils.logging_config import get_logger
logger = get_logger(__name__)


class AsyncOpenRouterClient:
    def __init__(self):
        self.api_url = OPENROUTER_API_URL
        self.api_key = OPENROUTER_API_KEY
        self.default_model = OPENROUTER_DEFAULT_MODEL
        self.rate_limit = TEXT_API_RATE_LIMIT
        self._requests = []
        self._rate_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=OPENROUTER_TEXT_TIMEOUT)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def _is_rate_limited(self, current_time: float) -> bool:
        async with self._rate_lock:
            self._requests = [t for t in self._requests if current_time - t < 60]
            if len(self._requests) >= self.rate_limit:
                return True
            return False

    async def _record_request(self, current_time: float):
        async with self._rate_lock:
            self._requests.append(current_time)

    async def generate_text(self, request: TextGenerationRequest) -> TextGenerationResponse:
        try:
            current_time = time.time()

            if await self._is_rate_limited(current_time):
                return TextGenerationResponse(error="Rate limit exceeded. Please wait before making another request.")

            if request.model is None:
                request.model = self.default_model

            cleaned_messages = []
            for msg in request.messages:
                cleaned_msg = {"role": msg.role, "content": msg.content or ""}
                if cleaned_msg.get('role') == 'assistant':
                    has_content = bool(cleaned_msg.get('content', ''))
                    has_tool_calls = bool(cleaned_msg.get('tool_calls'))
                    if not has_content and not has_tool_calls:
                        cleaned_msg['content'] = ''
                cleaned_messages.append(cleaned_msg)

            payload = {
                "model": request.model,
                "messages": cleaned_messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "reasoning": {"enabled": False},
            }

            if request.tools:
                payload["tools"] = request.tools
                payload["tool_choice"] = request.tool_choice
                
            headers = {
                "Content-Type": "application/json",
                "Referer": "jakeydegenbot",
                "Authorization": f"Bearer {self.api_key}"
            }

            max_retries = 2
            base_delay = 2

            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        logger.info(f"Retrying OpenRouter API (attempt {attempt + 1}/{max_retries})")
                    
                    response = await self._client.post(self.api_url, headers=headers, json=payload)

                    if response.status_code == 502:
                        logger.warning(f"API gateway error (502) - OpenRouter service may be down")
                        if attempt < max_retries - 1:
                            delay = min(1 * (2 ** attempt), 8)
                            logger.info(f"Retrying in {delay} seconds...")
                            await asyncio.sleep(delay)
                            continue
                    elif response.status_code == 429:
                        logger.warning(f"Rate limit hit from OpenRouter API (429)")
                        await asyncio.sleep(60)
                        return TextGenerationResponse(error="Rate limit exceeded. Please wait a minute before trying again.")

                    response.raise_for_status()
                    await self._record_request(current_time)

                    if attempt > 0:
                        logger.info(f"OpenRouter success on attempt {attempt + 1}")
                    
                    response_data = response.json()
                    return TextGenerationResponse(
                        content=response_data.get("choices", [{}])[0].get("message", {}).get("content"),
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
                    logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}) - OpenRouter API may be unreachable")
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
                    return TextGenerationResponse(error=f"HTTP {response.status_code}: Bad request")

                except httpx.RequestError as req_error:
                    logger.error(f"Request error: {req_error}")
                    return TextGenerationResponse(error=str(req_error))

            return TextGenerationResponse(error="Failed to get response from API after all retries")
        except Exception as e:
            logger.error(f"Critical error calling OpenRouter API: {e}")
            return TextGenerationResponse(error=str(e))


# Global API instance
async_openrouter_client = AsyncOpenRouterClient()

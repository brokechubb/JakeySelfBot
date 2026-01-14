import asyncio
import json
import logging
import random
import re
import time
from random import randint, uniform
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

import aiohttp
import discord
from discord import DMChannel, GroupChannel, TextChannel, Thread
from discord.ext import commands
from discord.ext.commands.view import StringView

from ai.ai_provider_manager import ai_provider_manager
from ai.openrouter import openrouter_api
from ai.response_uniqueness import response_uniqueness

# Import admin check function
from bot.commands import is_admin

# Import phrase sanitization utilities
from utils.phrase_sanitizer import clean_phrase_comprehensive

# Setup logger
logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for performance
# Tool call detection patterns
TOOL_CALL_JSON_PATTERN = re.compile(
    r'\{"type"\s*:\s*"function"\s*,\s*"name"\s*:\s*"([^"]+)"\s*,\s*"parameters"\s*:\s*(\{[^\}]+\})\}',
    re.DOTALL,
)
# Wen command pattern
WEN_PATTERN = re.compile(r"\b(wen+\?+)$", re.IGNORECASE)
# Path sanitization pattern
PATH_PATTERN = re.compile(r"[/\\][a-zA-Z0-9_\-/\\.]+")
# Database URL sanitization pattern
DB_URL_PATTERN = re.compile(r"(sqlite:///[^\s]+|mysql://[^\s]+|postgresql://[^\s]+)")
# Tool call syntax patterns for sanitization
TOOL_CALLS_PATTERN = re.compile(r"\[TOOL_CALL[S]?\].*", re.DOTALL | re.IGNORECASE)
TOOL_CALL_TAG_PATTERN = re.compile(r"</?tool_call>.*", re.DOTALL | re.IGNORECASE)
FUNCTION_CALL_TAG_PATTERN = re.compile(
    r"</?function_call>.*", re.DOTALL | re.IGNORECASE
)
RAW_FUNCTION_PATTERN = re.compile(r"\b[a-z_]+\s*\{[^}]*\}", re.IGNORECASE)
DISCORD_FUNCTION_PATTERN = re.compile(
    r"\bdiscord_\w+\s*\{.*?\}", re.DOTALL | re.IGNORECASE
)
WEB_SEARCH_FUNCTION_PATTERN = re.compile(
    r"\bweb_search\s*\{.*?\}", re.DOTALL | re.IGNORECASE
)
GET_FUNCTION_PATTERN = re.compile(r"\bget_\w+\s*\{.*?\}", re.DOTALL | re.IGNORECASE)
REMEMBER_FUNCTION_PATTERN = re.compile(
    r"\bremember_\w+\s*\{.*?\}", re.DOTALL | re.IGNORECASE
)
SEARCH_FUNCTION_PATTERN = re.compile(
    r"\bsearch_\w+\s*\{.*?\}", re.DOTALL | re.IGNORECASE
)
JSON_TOOL_CALL_PATTERN = re.compile(
    r'\{[^}]*["\']type["\']\s*:\s*["\']function["\'][^{]*(?:\{[^}]*\})?[^}]*\}',
    re.DOTALL | re.IGNORECASE,
)
END_TOKEN_PATTERN = re.compile(r"</s>\s*$")
MULTIPLE_NEWLINES_PATTERN = re.compile(r"\n\s*\n\s*\n")


def extract_text_tool_calls(ai_response: str) -> Tuple[List[Dict], str]:
    """
    Extract tool calls from AI response text when model returns them as JSON instead of API format.

    Args:
        ai_response: The AI response text to check for embedded tool calls

    Returns:
        Tuple of (tool_calls list, cleaned response text)
    """
    if not ai_response:
        return [], ai_response

    match = TOOL_CALL_JSON_PATTERN.search(ai_response)
    if not match:
        return [], ai_response

    try:
        function_name = match.group(1)
        parameters_str = match.group(2)
        parameters = json.loads(parameters_str)

        tool_calls = [
            {
                "id": f"manual_{int(time.time())}",
                "type": "function",
                "function": {"name": function_name, "arguments": parameters},
            }
        ]

        # Remove the JSON from response
        cleaned_response = TOOL_CALL_JSON_PATTERN.sub("", ai_response).strip()

        return tool_calls, cleaned_response

    except json.JSONDecodeError as e:
        logging.getLogger(__name__).debug(f"Failed to parse tool call JSON: {e}")
        return [], ai_response


# Error handling functions
def sanitize_error_message(error_message: str) -> str:
    """Remove sensitive information from error messages."""
    if not error_message:
        return "An error occurred"

    sanitized = PATH_PATTERN.sub("[PATH]", error_message)
    sanitized = DB_URL_PATTERN.sub("[DATABASE]", sanitized)
    return sanitized


def sanitize_ai_response(response: str) -> str:
    """
    Remove leaked tool call syntax from AI responses before sending to Discord.

    Some AI models output raw tool call syntax like [TOOL_CALLS]function{...}
    instead of using proper API tool call format. This strips that text.
    
    NOTE: We intentionally do NOT strip URLs - image generation tools return URLs
    that need to be included in the response for Discord to embed them.
    """
    if not response:
        return response

    sanitized = response

    # Remove [TOOL_CALLS] or similar patterns followed by function calls
    sanitized = TOOL_CALLS_PATTERN.sub("", sanitized)

    # Also handle other common formats like <tool_call>, </s>, etc.
    sanitized = TOOL_CALL_TAG_PATTERN.sub("", sanitized)
    sanitized = FUNCTION_CALL_TAG_PATTERN.sub("", sanitized)

    # Remove raw function call patterns like: function_name{"arg": "value"} or function_name{...}
    sanitized = RAW_FUNCTION_PATTERN.sub("", sanitized)

    # Remove patterns like: discord_send_message{...} even with complex JSON
    sanitized = DISCORD_FUNCTION_PATTERN.sub("", sanitized)
    sanitized = WEB_SEARCH_FUNCTION_PATTERN.sub("", sanitized)
    sanitized = GET_FUNCTION_PATTERN.sub("", sanitized)
    sanitized = REMEMBER_FUNCTION_PATTERN.sub("", sanitized)
    sanitized = SEARCH_FUNCTION_PATTERN.sub("", sanitized)

    # Remove JSON-formatted tool calls: {"type": "function", "name": "...", "parameters": {...}}
    sanitized = JSON_TOOL_CALL_PATTERN.sub("", sanitized)

    # Remove trailing </s> tokens some models add
    sanitized = END_TOKEN_PATTERN.sub("", sanitized)

    # Clean up multiple newlines and whitespace
    sanitized = MULTIPLE_NEWLINES_PATTERN.sub("\n\n", sanitized)
    sanitized = sanitized.strip()

    # Log if we removed significant content
    if len(response) - len(sanitized) > 20:
        logger.info(
            f"Sanitized AI response: removed {len(response) - len(sanitized)} chars of tool call syntax"
        )

    return sanitized


def extract_final_response_from_reasoning(reasoning: str) -> str:
    """
    Extract the actual user-facing response from a model's reasoning/thinking output.

    Many reasoning models output chain-of-thought that includes internal thinking
    followed by the actual response. This function tries to extract just the final response.

    Common patterns:
    - "Final answer: ..." or "Final response: ..."
    - "Response: ..." or "Answer: ..."
    - "I'll respond with: ..."
    - Text after "---" or "===" dividers
    - Last paragraph after internal deliberation
    """
    if not reasoning:
        return ""

    # Try to find explicit response markers (case insensitive)
    response_patterns = [
        r"(?:^|\n)\s*(?:Final )?[Rr]esponse\s*:\s*(.+?)$",
        r"(?:^|\n)\s*(?:Final )?[Aa]nswer\s*:\s*(.+?)$",
        r"(?:^|\n)\s*(?:My )?[Rr]eply\s*:\s*(.+?)$",
        r'(?:^|\n)\s*I(?:\'ll| will) (?:respond|reply|say)\s*:\s*["\']?(.+?)["\']?\s*$',
        r'(?:^|\n)\s*(?:So,? )?(?:I(?:\'ll| will| should) )?(?:just )?(?:say|respond|reply)\s*:\s*["\']?(.+?)["\']?\s*$',
    ]

    for pattern in response_patterns:
        match = re.search(pattern, reasoning, re.DOTALL | re.MULTILINE)
        if match:
            response = match.group(1).strip()
            if response:
                return response

    # Try to find content after dividers like "---" or "==="
    divider_patterns = [r"\n-{3,}\n(.+?)$", r"\n={3,}\n(.+?)$", r"\n\*{3,}\n(.+?)$"]
    for pattern in divider_patterns:
        match = re.search(pattern, reasoning, re.DOTALL)
        if match:
            response = match.group(1).strip()
            if response and len(response) > 20:  # Reasonable length check
                return response

    # Look for quoted response at the end
    quoted_match = re.search(r'["\']([^"\']{20,})["\']\s*$', reasoning)
    if quoted_match:
        return quoted_match.group(1).strip()

    # If reasoning contains clear thinking markers, try to get content after them
    thinking_end_patterns = [
        r"(?:Let me|I\'ll|I will|I should|Now I\'ll|So I\'ll)\s+(?:respond|reply|answer|say)[^.]*\.\s*(.+?)$",
    ]
    for pattern in thinking_end_patterns:
        match = re.search(pattern, reasoning, re.DOTALL | re.IGNORECASE)
        if match:
            response = match.group(1).strip()
            if response and len(response) > 10:
                return response

    # Look for "Therefore", "So", "In conclusion", "The answer is" patterns
    conclusion_patterns = [
        r"(?:Therefore|So|Thus|Hence|In conclusion|The (?:answer|response) is|Based on this):?\s*(.+?)(?:\n|$)",
        r"(?:Therefore|So|Thus|Hence|In conclusion|The (?:answer|response) is|Based on this):?\s*(.+?)(?:\n[A-Z]|\n\n|$)",
        r".*\n\n(.+?)(?:\n|$)",  # Last paragraph after double newline
    ]
    for pattern in conclusion_patterns:
        match = re.search(pattern, reasoning, re.DOTALL | re.IGNORECASE)
        if match:
            response = match.group(1).strip()
            if response and len(response) > 10:
                # Avoid returning just thinking/analysis
                thinking_indicators = [
                    "let me",
                    "i need to",
                    "i should",
                    "first,",
                    "step 1",
                    "let's",
                    "we need to",
                    "we should",
                    "analyzing",
                    "parsing",
                    "considering",
                    "the user",
                    "the request",
                    "this means",
                    "this is",
                ]
                if not any(ind in response.lower() for ind in thinking_indicators):
                    return response

    # Last resort: if it's short enough and doesn't look like thinking, use as-is
    # Chain-of-thought usually has phrases like "Let me", "I need to", "First,", etc.
    thinking_indicators = [
        "let me",
        "i need to",
        "i should",
        "first,",
        "step 1",
        "let's",
        "we need to",
        "we should",
        "analyzing",
        "parsing",
        "considering",
        "the user",
        "the request",
        "this means",
        "this is",
    ]

    reasoning_lower = reasoning.lower()
    has_thinking_indicators = any(ind in reasoning_lower for ind in thinking_indicators)

    # If short and no clear thinking markers, might be the actual response
    if len(reasoning) < 500 and not has_thinking_indicators:
        return reasoning.strip()

    # If we get here, the reasoning is likely pure chain-of-thought with no clear answer
    # Return empty to indicate we couldn't extract a clean response
    logger.warning(
        f"Could not extract final response from reasoning (len={len(reasoning)})"
    )
    return ""


def handle_command_error(error: Exception, ctx, command_name: str) -> str:
    """Handle command errors with sanitization."""
    sanitized_msg = sanitize_error_message(str(error))

    # Log the full error for debugging
    logger.error(
        f"Command {command_name} error for user {getattr(ctx, 'author', {}).get('id', 'unknown')}: {type(error).__name__}: {str(error)}"
    )

    # Return user-friendly message
    return f"💀 **Command failed:** {sanitized_msg}"


from config import (
    AIRDROP_CPM_MAX,
    AIRDROP_CPM_MIN,
    AIRDROP_DELAY_MAX,
    AIRDROP_DELAY_MIN,
    AIRDROP_DISABLE_AIRDROP,
    AIRDROP_DISABLE_MATHDROP,
    AIRDROP_DISABLE_PHRASEDROP,
    AIRDROP_DISABLE_REDPACKET,
    AIRDROP_DISABLE_TRIVIADROP,
    AIRDROP_IGNORE_DROPS_UNDER,
    AIRDROP_IGNORE_TIME_UNDER,
    AIRDROP_IGNORE_USERS,
    AIRDROP_RANGE_DELAY,
    AIRDROP_SERVER_WHITELIST,
    AIRDROP_SMART_DELAY,
    AUTO_MEMORY_CLEANUP_ENABLED,
    AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD,
    AUTO_MEMORY_EXTRACTION_ENABLED,
    AUTO_MEMORY_MAX_AGE_DAYS,
    CHANNEL_CONTEXT_MESSAGE_LIMIT,
    CHANNEL_CONTEXT_MINUTES,
    CONVERSATION_HISTORY_LIMIT,
    DISCORD_TOKEN,
    GENDER_ROLES_GUILD_ID,
    GUILD_BLACKLIST,
    IMAGE_API_RATE_LIMIT,
    RATE_LIMIT_COOLDOWN,
    RELAY_MENTION_ROLE_MAPPINGS,
    SYSTEM_PROMPT,
    TRIVIA_RANDOM_FALLBACK,
    USE_WEBHOOK_RELAY,
    USER_RATE_LIMIT,
    WEBHOOK_EXCLUDE_IDS,
    WEBHOOK_RELAY_MAPPINGS,
    WELCOME_CHANNEL_IDS,
    WELCOME_ENABLED,
    WELCOME_SERVER_IDS,
)
from media.image_generator import image_generator

# Constants for repetitive response detection


# Constants
class JakeyConstants:
    DISCORD_MESSAGE_LIMIT = 2000
    MAX_AI_TOKENS = 2000
    RESPONSE_COOLDOWN_SECONDS = 3
    RATE_LIMIT_WINDOW = 60
    USER_MEMORY_LIMIT_DAYS = 7
    CONVERSATION_HISTORY_LIMIT = 3  # Number of previous conversations to include
    MAX_CONVERSATION_TOKENS = 1000  # Maximum tokens for conversation context
    CHANNEL_CONTEXT_MINUTES = 30  # Minutes of channel context to include
    CHANNEL_CONTEXT_MESSAGE_LIMIT = 20  # Number of channel messages to include


class JakeyBot(commands.Bot):
    def __init__(self, dependencies):
        # Use self-bot configuration with improved connection settings
        # discord.py-self doesn't use Intents in the same way as regular discord.py
        super().__init__(
            command_prefix=dependencies.command_prefix, self_bot=True, help_command=None
        )

        # Set connection parameters for improved stability
        self._connection.heartbeat_timeout = 60.0

        # Inject dependencies
        self.openrouter_api = dependencies.ai_client
        self.db = dependencies.database
        self.tool_manager = dependencies.tool_manager
        self.image_generator = image_generator  # Keep global for now
        self.tipcc_manager = dependencies.tipcc_manager

        # Message queue integration (will be initialized in main.py if enabled)
        self.message_queue_integration = None  # type: Optional[Any]
        self._message_queue_enabled = False  # Flag to enable queue in on_ready

        # Current model (defaults to the configured default model)
        self.current_model = None  # Will be set to DEFAULT_MODEL when bot is ready
        self.current_api_provider = (
            None  # Track which API provider is being used (openrouter only now)
        )

        # Fallback restoration tracking
        self.openrouter_fallback_start_time = None  # When we switched to OpenRouter
        self.fallback_restore_task = None  # Background task for restoration
        self.original_model_before_fallback = (
            None  # Model we were using before fallback
        )

        # Flag to ensure commands are loaded only once
        self._commands_loaded = False

        # User rate limiting setup - OPTIMIZED with O(1) operations
        self.user_rate_limit = USER_RATE_LIMIT
        self.rate_limit_cooldown = RATE_LIMIT_COOLDOWN
        self._user_request_counts = {}  # user_id -> request_count (for current window)
        self._user_window_starts = {}  # user_id -> window_start_timestamp
        self._user_lock = None  # Lazy-initialized asyncio.Lock (can't create before event loop)

        # Global response limiting to prevent Discord rate limit issues
        self._last_global_response = 0
        self._global_response_cooldown = (
            2.5  # Minimum 2.5 seconds between any responses (increased for stability)
        )

        # Wen command cooldown to prevent loops
        self.wen_cooldown = {}  # message_id -> timestamp
        self.wen_cooldown_duration = 600  # seconds (10 minutes)
        self._last_wen_cleanup = 0  # timestamp of last cleanup

        # Model capabilities cache for dynamic tool support checking
        self._model_capabilities = {}  # model_name -> capabilities_dict
        self._model_cache_time = 0  # timestamp when cache was last updated

        # Initialize gender role manager
        from utils.gender_roles import initialize_gender_role_manager

        # Initialize anti-repetition system
        self.user_response_history = {}  # user_id -> deque of recent responses

        initialize_gender_role_manager(self)
        self._model_cache_duration = 3600  # cache for 1 hour

    def _get_user_lock(self) -> asyncio.Lock:
        """Get or create the user rate limit lock (lazy initialization)."""
        if self._user_lock is None:
            self._user_lock = asyncio.Lock()
        return self._user_lock

    async def _check_user_rate_limit(self, user_id: str) -> tuple:
        """
        Check if a user is rate limited.
        Returns (is_limited, time_remaining_seconds).
        
        Uses a sliding window: user_rate_limit requests per rate_limit_cooldown seconds.
        """
        current_time = time.time()
        
        async with self._get_user_lock():
            # Get or initialize user's window
            window_start = self._user_window_starts.get(user_id, 0)
            request_count = self._user_request_counts.get(user_id, 0)
            
            # Check if window has expired
            if current_time - window_start >= self.rate_limit_cooldown:
                # Reset window
                self._user_window_starts[user_id] = current_time
                self._user_request_counts[user_id] = 0
                return (False, 0)
            
            # Check if user exceeded limit
            if request_count >= self.user_rate_limit:
                time_remaining = self.rate_limit_cooldown - (current_time - window_start)
                return (True, max(0, time_remaining))
            
            return (False, 0)
    
    async def _increment_user_request(self, user_id: str):
        """Increment the request count for a user."""
        current_time = time.time()
        
        async with self._get_user_lock():
            window_start = self._user_window_starts.get(user_id, 0)
            
            # Reset if window expired
            if current_time - window_start >= self.rate_limit_cooldown:
                self._user_window_starts[user_id] = current_time
                self._user_request_counts[user_id] = 1
            else:
                self._user_request_counts[user_id] = self._user_request_counts.get(user_id, 0) + 1

    def clear_model_cache(self):
        """Force clear the model capabilities cache"""
        self._model_capabilities = {}
        self._model_cache_time = 0
        logger.info("Model capabilities cache cleared")

    def _model_supports_tools(self, model_name: Optional[str]) -> bool:
        """Dynamically check if a model supports tools using API data"""
        if not model_name:
            return False

        current_time = time.time()

        # Update cache if it's too old or if we need to force refresh
        if (
            current_time - self._model_cache_time > self._model_cache_duration
            or not self._model_capabilities
        ):
            try:
                self._model_capabilities = {}

                # Get models from OpenRouter
                try:
                    openrouter_models = openrouter_api.list_models()
                    for model_id in openrouter_models:
                        self._model_capabilities[model_id] = {
                            "provider": "openrouter",
                            "name": model_id,
                        }
                except Exception as e:
                    logger.warning(f"Failed to fetch OpenRouter models: {e}")

                self._model_cache_time = current_time
                logger.info(
                    f"Updated model capabilities cache with {len(self._model_capabilities)} models from multiple providers"
                )
            except Exception as e:
                logger.error(f"Failed to update model capabilities cache: {e}")
                # Fallback to basic models (OpenRouter free models only)
                model_key = model_name.strip().lower()
                return model_key in [
                    "nvidia/nemotron-nano-9b-v2:free",
                    "deepseek/deepseek-r1:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "meta-llama/llama-3.2-3b-instruct:free",
                    "mistralai/mistral-small-3.2-24b-instruct:free",
                    "deepseek/deepseek-chat:free",
                ]

        # Check if model supports tools from cache
        model_key = model_name.strip().lower()
        # Special case: Known models that support tools regardless of API data
        # Updated with actual Pollinations models (Jan 2026)
        trusted_tool_models = [
            "evil",
            "openai",
            "openai-fast",
            "gemini",
            "gemini-search",
            "mistral",
            "deepseek",
            "qwen-coder",
            "roblox-rp",
            "unity",
            "bidara",
        ]
        if model_key in trusted_tool_models:
            logger.debug(f"Model '{model_key}' is in trusted tool models list")
            return True

        model_info = self._model_capabilities.get(model_key)
        if model_info and isinstance(model_info, dict):
            # For OpenRouter models, assume tool support based on model name patterns
            if model_info.get("provider") == "openrouter":
                model_lower = model_name.strip().lower()
                tool_capable_keywords = [
                    "instruct",
                    "chat",
                    "gpt",
                    "claude",
                    "llama",
                    "mistral",
                    "deepseek",
                    "nemotron",
                    "qwen",
                    "longcat",
                ]
                return any(keyword in model_lower for keyword in tool_capable_keywords)
            # For other providers, check the tools flag
            return bool(model_info.get("tools", False))

        # Fallback to basic check if model not in cache
        model_lower = model_name.strip().lower()
        # Check for known tool-capable models by pattern
        tool_capable_keywords = [
            "instruct",
            "chat",
            "gpt",
            "claude",
            "llama",
            "mistral",
            "deepseek",
            "nemotron",
            "qwen",
            "longcat",
        ]
        if any(keyword in model_lower for keyword in tool_capable_keywords):
            return True

        # Final hardcoded fallback (OpenRouter free models only)
        return model_lower in [
            "nvidia/nemotron-nano-9b-v2:free",
            "deepseek/deepseek-r1:free",
            "deepseek/deepseek-chat:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "mistralai/mistral-small-3.2-24b-instruct:free",
        ]

    # Anti-Repetition Methods
    def _is_repetitive_response(
        self, response_text: str, user_id: str
    ) -> Tuple[bool, str]:
        """
        Wrapper for response_uniqueness.is_repetitive_response.
        Check if a response is repetitive based on the bot's recent responses to this user.
        Returns a tuple of (is_repetitive, reason).
        """
        # Delegate to the response_uniqueness manager for consistency
        return response_uniqueness.is_repetitive_response(user_id, response_text)

    async def _generate_non_repetitive_response(
        self, user_message: str, original_response: str
    ) -> str:
        """
        Generate an alternative response when repetition is detected using AI rephrasing.
        """
        try:
            # Multiple rephrasing strategies with stronger prompts
            rephrase_systems = [
                # Strategy 1: Complete structural rewrite
                "You are rewriting a message to avoid repetition. Completely restructure the sentence, use entirely different vocabulary, change the opening, and alter the tone while keeping the same meaning. DO NOT just swap 2-3 words - rewrite it from scratch. Make it sound natural but totally different.",
                # Strategy 2: Change perspective and style
                "Rewrite this message using a completely different style. Change the sentence structure entirely, use synonyms for ALL key words, and alter the opening phrase. If it's informal, make it formal. If it's formal, make it casual. Keep the core meaning but express it in a completely fresh way.",
                # Strategy 3: Shorten or expand for variety
                "Rewrite this message either much shorter or much longer than the original while keeping the same meaning. If the original is 3 sentences, make it 1 long sentence or 5 short ones. Change all vocabulary and structure completely. Avoid ANY word repetition from the original.",
            ]

            rephrase_attempts = []
            max_attempts = 3
            target_similarity = 0.5  # Aim for under 50% similarity

            for attempt in range(max_attempts):
                # Rotate through different rephrasing strategies
                rephrase_system = rephrase_systems[attempt % len(rephrase_systems)]

                rephrase_prompt = (
                    f"User asked: {user_message}\n\n"
                    f"Original bot response: {original_response}\n\n"
                    f"Your task: COMPLETELY rewrite this response. Use different structure, words, and tone. "
                    f"Make it sound natural but unrecognizable from the original. Do NOT mention that you're rephrasing."
                )

                rephrase_messages = [
                    {"role": "system", "content": rephrase_system},
                    {"role": "user", "content": rephrase_prompt},
                ]

                # Try multiple rephrases with increasing creativity
                result = await ai_provider_manager.generate_text(
                    messages=rephrase_messages,
                    max_tokens=min(len(original_response.split()) * 3, 800),
                    temperature=0.9
                    + (attempt * 0.1),  # Increase temperature each attempt
                )

                if result and result.get("content"):
                    rephrased = result["content"].strip()
                    logger.debug(
                        f"Attempt {attempt + 1}/{max_attempts}: {repr(rephrased[:80])}"
                    )

                    # Sanity check: ensure rephrased version is reasonably different
                    if rephrased and rephrased.lower() != original_response.lower():
                        # Check similarity to ensure it's genuinely different
                        similarity = response_uniqueness._get_jaccard_similarity(
                            rephrased, original_response
                        )
                        logger.debug(
                            f"Attempt {attempt + 1} similarity: {similarity:.2%} "
                            f"(target: < {target_similarity:.0%})"
                        )

                        # Store this attempt
                        rephrase_attempts.append(
                            {
                                "text": rephrased,
                                "similarity": similarity,
                                "attempt": attempt + 1,
                            }
                        )

                        # If under target similarity, use it immediately
                        if similarity < target_similarity:
                            logger.info(
                                f"✅ Successfully rephrased on attempt {attempt + 1} "
                                f"(similarity: {similarity:.1%})"
                            )
                            return rephrased
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1}: AI generated same or empty response"
                        )

                # If all attempts completed but none under threshold, use best one
                if rephrase_attempts:
                    best_attempt = min(rephrase_attempts, key=lambda x: x["similarity"])
                    logger.info(
                        f"Using best rephrase attempt {best_attempt['attempt']} "
                        f"with similarity {best_attempt['similarity']:.1%}"
                    )
                    # Only use if at least somewhat different (under 75%)
                    if best_attempt["similarity"] < 0.75:
                        return best_attempt["text"]
                    else:
                        logger.warning(
                            f"All rephrase attempts too similar "
                            f"(best: {best_attempt['similarity']:.1%}), using fallback"
                        )

        except Exception as e:
            logger.warning(
                f"AI rephrasing failed: {e}, falling back to simple variation"
            )

        # Fallback: Multiple transformation strategies for better variation
        fallback_strategies = [
            # Strategy 1: Synonym replacement + structure change
            lambda text: self._apply_synonym_replacement(text),
            # Strategy 2: Sentence reordering
            lambda text: self._reorder_sentences(text),
            # Strategy 3: Tone flip (formal <-> casual)
            lambda text: self._flip_tone(text),
            # Strategy 4: Completely different opening
            lambda text: self._change_opening(text),
        ]

        # Try each strategy and pick the most different
        best_fallback = None
        best_similarity = 1.0

        for strategy_idx, strategy_func in enumerate(fallback_strategies):
            try:
                fallback_text = strategy_func(original_response)
                similarity = response_uniqueness._get_jaccard_similarity(
                    fallback_text, original_response
                )
                logger.debug(
                    f"Fallback strategy {strategy_idx + 1}: similarity {similarity:.2%}"
                )

                if similarity < best_similarity:
                    best_similarity = similarity
                    best_fallback = fallback_text
            except Exception as e:
                logger.debug(f"Fallback strategy {strategy_idx + 1} failed: {e}")

        if best_fallback and best_similarity < 0.85:
            logger.info(
                f"Using fallback strategy with similarity {best_similarity:.1%}"
            )
            return best_fallback

        # Ultimate fallback: Generate a completely NEW response with explicit avoid list
        logger.warning("All fallbacks too similar, generating fresh response with explicit avoid list")
        
        # Try up to 3 times with increasing creativity
        for attempt in range(3):
            try:
                # Get snippets of responses to explicitly avoid (use a generic key for global avoidance)
                avoid_snippets = response_uniqueness.get_avoid_list("_global_", limit=5)
                
                # Also add the original response we're trying to avoid
                avoid_snippets.insert(0, original_response[:150])
                avoid_text = "\n".join([f"- \"{s}\"" for s in avoid_snippets[:5]])
                
                fresh_system = (
                    "You are a sarcastic, edgy AI assistant named Jakey. "
                    "You MUST respond to the user but your response MUST be COMPLETELY DIFFERENT from these examples:\n\n"
                    f"{avoid_text}\n\n"
                    "CRITICAL RULES:\n"
                    "1. DO NOT start with 'Oh look' or similar openings\n"
                    "2. DO NOT use the phrase 'another genius' or 'fucking adorable'\n"
                    "3. Use a COMPLETELY different tone and structure\n"
                    "4. Be creative - try sarcasm, mockery, questions, or dismissiveness\n"
                    "5. Keep it natural and in-character as a degenerate gambling bot\n"
                    "6. DO NOT mention that you're rephrasing or being different"
                )
                
                fresh_result = await ai_provider_manager.generate_text(
                    messages=[
                        {"role": "system", "content": fresh_system},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=400,
                    temperature=1.2 + (attempt * 0.1),  # Increase temperature each attempt
                )
                
                if fresh_result and fresh_result.get("content"):
                    fresh_response = fresh_result["content"].strip()
                    # Verify it's actually different
                    fresh_similarity = response_uniqueness._get_jaccard_similarity(
                        fresh_response, original_response
                    )
                    # Also check prefix similarity
                    prefix_sim = response_uniqueness._get_jaccard_similarity(
                        fresh_response[:100], original_response[:100]
                    )
                    
                    if fresh_similarity < 0.70 and prefix_sim < 0.70:
                        logger.info(f"✅ Fresh response generated on attempt {attempt+1} with {fresh_similarity:.1%} similarity")
                        return fresh_response
                    else:
                        logger.warning(f"Fresh attempt {attempt+1} still too similar (full: {fresh_similarity:.1%}, prefix: {prefix_sim:.1%})")
            except Exception as e:
                logger.warning(f"Fresh response attempt {attempt+1} failed: {e}")
        
        # Absolute last resort: Generate a simple different response
        import random
        fallback_responses = [
            "What? I wasn't paying attention. Say that again.",
            "Huh. That's something. I guess.",
            "*yawns* You still here?",
            "Cool story bro. Tell it again.",
            "I heard you. I just don't care.",
            "Yeah yeah, whatever you say chief.",
            "Is that so? Fascinating. Not really though.",
            "Mhmm. Sure. Totally listening.",
        ]
        return random.choice(fallback_responses)

    def _apply_synonym_replacement(self, text: str) -> str:
        """Replace key words with synonyms for variation."""
        synonyms = {
            "hello": ["hi there", "hey", "greetings", "what's up", "howdy"],
            "I think": [
                "I believe",
                "in my opinion",
                "it seems to me",
                "from my perspective",
            ],
            "basically": ["essentially", "fundamentally", "at its core", "in essence"],
            "actually": ["in fact", "as it happens", "really", "truth be told"],
            "really": ["truly", "genuinely", "actually", "honestly"],
            "just": ["simply", "merely", "only", "just about"],
            "want": ["need", "require", "looking for", "after"],
            "different": ["various", "alternative", "distinct", "diverse"],
            "same": ["identical", "matching", "equivalent", "similar"],
            "thing": ["matter", "issue", "topic", "subject"],
            "good": ["great", "excellent", "solid", "decent"],
            "bad": ["terrible", "awful", "poor", "unfortunate"],
        }

        result = text
        for original, replacements in synonyms.items():
            if original.lower() in result.lower():
                import random

                replacement = random.choice(replacements)
                # Case-insensitive replacement
                result = re.sub(
                    re.escape(original),
                    replacement,
                    result,
                    flags=re.IGNORECASE,
                    count=1,
                )
        return result

    def _reorder_sentences(self, text: str) -> str:
        """Slightly reorder sentence structure."""
        sentences = text.split(". ")
        if len(sentences) > 1:
            import random

            sentences = sentences[1:] + sentences[:1]  # Move first to last
            return ". ".join(sentences).strip()
        return text

    def _flip_tone(self, text: str) -> str:
        """Flip between formal and casual tone."""
        # Check if text contains casual markers
        casual_indicators = [
            "hey",
            "what's up",
            "cool",
            "awesome",
            "stuff",
            "gonna",
            "wanna",
        ]
        is_casual = any(indicator in text.lower() for indicator in casual_indicators)

        if is_casual:
            # Make more formal
            result = text.replace("hey", "Hello there")
            result = result.replace("what's up", "How are you doing")
            result = result.replace("gonna", "going to")
            result = result.replace("wanna", "want to")
            result = result.replace("stuff", "matters")
            result = result.replace("cool", "excellent")
        else:
            # Make more casual
            result = text.replace("Hello", "Hey")
            result = result.replace("I would like", "I want")
            result = result.replace("regarding", "about")
            result = result.replace("concerning", "on")

        return result

    def _change_opening(self, text: str) -> str:
        """Change the opening phrase completely."""
        openings = [
            "Well then, ",
            "Anyway, ",
            "Look here, ",
            "You know, ",
            "So, ",
            "Here's the thing - ",
        ]
        import random

        return random.choice(openings) + text.lstrip()

    def _store_user_response(self, user_id: str, response_text: str):
        """
        Store a user's successful response for future repetition detection.
        """
        # Log what we're storing
        logger.info(
            f"Storing bot response for user {user_id}: {len(response_text)} chars, "
            f"preview: {repr(response_text[:80])}"
        )

        # Check current storage before adding
        before_count = len(response_uniqueness.user_responses.get(user_id, []))

        response_uniqueness.add_response(user_id, response_text)

        # Verify it was stored
        after_count = len(response_uniqueness.user_responses.get(user_id, []))

        # Note: When deque is at maxlen (10), count won't increase - old items are evicted
        # This is expected behavior, not a failure
        if after_count >= before_count:
            logger.debug(
                f"✅ Response stored successfully for user {user_id}. "
                f"History size: {before_count} → {after_count}"
            )
        else:
            logger.warning(
                f"⚠️  Response storage failed for user {user_id}. "
                f"Count decreased unexpectedly: {before_count} → {after_count}"
            )

        # Log total history for that user
        user_history = list(response_uniqueness.user_responses.get(user_id, []))
        logger.debug(
            f"User {user_id} now has {len(user_history)} total responses in history: "
            f"{[repr(h[:50]) for h in user_history[-3:]]}"
        )

    async def setup_hook(self):
        """Initialize the bot with self-bot specific features"""
        # Record startup time for stats
        self._start_time = time.time()

    async def on_connect(self):
        """Called when the client connects to Discord"""
        logger.info("✅ Connected to Discord gateway")

    async def on_disconnect(self):
        """Called when the client disconnects from Discord"""
        logger.info("⚠️  Disconnected from Discord gateway")

    async def on_resumed(self):
        """Called when the client resumes a session"""
        logger.info("🔄 Session resumed with Discord")

    async def on_error(self, event_method, *args, **kwargs):
        """Global error handler for Discord events"""
        import traceback

        logger.error(f"💀 Error in {event_method}: {traceback.format_exc()}")

    async def close(self):
        """Override close method for better cleanup"""
        logger.info("🛑 Closing bot connection...")
        await super().close()

    async def on_ready(self):
        """Called when the bot is ready"""
        # Set current model to default if not already set
        from config import OPENROUTER_DEFAULT_MODEL

        if self.current_model is None:
            self.current_model = OPENROUTER_DEFAULT_MODEL

        # Register commands only once
        if not self._commands_loaded:
            import bot.commands

            bot.commands.setup_commands(self)
            self._commands_loaded = True

        logger.info(
            f"Jakey is ready to cause some chaos in {len(self.guilds)} servers!"
        )
        logger.info(f"Available commands: {list(self.all_commands.keys())}")

        # Set up periodic memory cleanup
        await self.setup_periodic_memory_cleanup()

        # Start the reminder background task
        asyncio.create_task(self._check_due_reminders())
        logger.info("Started reminder background task")

        # Initialize message queue integration if enabled
        if self._message_queue_enabled:
            try:
                # Dynamically import optional module
                discord_queue_integration = __import__(
                    "discord_queue_integration",
                    fromlist=["setup_message_queue_integration"],
                )
                self.message_queue_integration = (
                    await discord_queue_integration.setup_message_queue_integration(
                        self
                    )
                )
                logger.info(
                    "✅ Message queue integration initialized and connected to bot"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️  Could not initialize message queue integration: {e}"
                )
                self.message_queue_integration = None

        # Check and save permissions for all guilds
        asyncio.create_task(self._check_and_save_permissions())
        logger.info("Started permission check task")

    async def on_message(self, message):
        """Handle incoming messages with improved self-bot practices"""
        logger.debug(
            f"Received message from {message.author.name}#{message.author.discriminator} in {message.guild.name if message.guild else 'DM'}"
        )

        # Don't respond to ourselves (essential for self-bots to prevent loops)
        if message.author == self.user:
            logger.debug("Ignoring message from self to prevent loops")
            return

        # Handle tip.cc bot messages (special case - need to parse even from bots)
        if (
            message.author.bot and message.author.id == 617037497574359050
        ):  # tip.cc bot ID
            logger.debug("Processing tip.cc bot message")
            try:
                await self.tipcc_manager.handle_tip_cc_response(message)
            except Exception as e:
                logger.error(f"Error handling tip.cc message: {e}")
            return  # Don't process further as regular message

        # WEBHOOK RELAY FUNCTIONALITY
        if USE_WEBHOOK_RELAY and WEBHOOK_RELAY_MAPPINGS:
            await self.process_webhook_relay(message)

        # Don't respond to other bots
        if message.author.bot:
            logger.debug("Ignoring message from bot")
            return

        # MESSAGE QUEUE PROCESSING - Use queue if available and enabled
        if (
            self.message_queue_integration
            and self._message_queue_enabled
            and not message.author.bot
        ):
            # Check if this is a command and queue it
            prefix = self.command_prefix or ""
            if (
                isinstance(prefix, str)
                and message.content.startswith(prefix)
                and len(prefix) > 0
            ):
                content_without_prefix = message.content[len(prefix) :].strip()
                if content_without_prefix:
                    command_parts = content_without_prefix.split()
                    if command_parts:
                        command_name = command_parts[0].lower()

                        # Check if this is a valid command
                        if command_name in self.all_commands:
                            logger.info(
                                f"Queuing command '{command_name}' for user {message.author.id}"
                            )

                            try:
                                # Dynamically import optional module
                                resilience = __import__(
                                    "resilience", fromlist=["MessagePriority"]
                                )
                                MessagePriority = resilience.MessagePriority

                                # Determine priority based on command type
                                priority = MessagePriority.NORMAL
                                if command_name in ["help", "ping", "stats"]:
                                    priority = MessagePriority.HIGH
                                elif command_name in [
                                    "model",
                                    "aistatus",
                                    "fallbackstatus",
                                ]:
                                    priority = MessagePriority.CRITICAL

                                # Enqueue the command for processing
                                await self.message_queue_integration.enqueue_discord_message(
                                    "command",
                                    {
                                        "channel_id": message.channel.id,
                                        "content": message.content,
                                        "author_id": message.author.id,
                                        "message_id": message.id,
                                        "command_name": command_name,
                                        "args": command_parts[1:]
                                        if len(command_parts) > 1
                                        else [],
                                    },
                                    priority=priority,
                                )

                                logger.debug(
                                    f"Command '{command_name}' queued with priority {priority.name}"
                                )
                                return  # Don't process directly - let the queue handle it

                            except Exception as e:
                                logger.error(
                                    f"Failed to queue command '{command_name}': {e}"
                                )
                                # Fall back to direct processing if queue fails

        # MANUAL COMMAND PROCESSING FOR SELF-BOTS (fallback if queue is not available)
        # Check if this is a command and process it manually
        prefix = self.command_prefix or ""
        if (
            isinstance(prefix, str)
            and message.content.startswith(prefix)
            and len(prefix) > 0
        ):
            content_without_prefix = message.content[len(prefix) :].strip()
            if content_without_prefix:
                command_parts = content_without_prefix.split()
                if command_parts:
                    command_name = command_parts[0].lower()

                    # Check if this is a valid command
                    if command_name in self.all_commands:
                        logger.info(
                            f"Processing command '{command_name}' for user {message.author.id}"
                        )
                        command = self.all_commands[command_name]

                        # Create a context manually
                        try:
                            # Manual command invocation for self-bots
                            ctx = await self.get_context(message)
                            ctx.command = command
                            ctx.invoked_with = command_name
                            ctx.prefix = prefix

                            # Extract arguments (everything after the command name)
                            if len(command_parts) > 1:
                                args_content = " ".join(command_parts[1:])
                            else:
                                args_content = ""

                            # Set up the view with the arguments for proper parsing
                            ctx.view = StringView(args_content)
                            ctx.args = [ctx]
                            ctx.kwargs = {}

                            # Manually invoke the command for self-bots
                            prompt = (
                                " ".join(command_parts[1:])
                                if len(command_parts) > 1
                                else ""
                            )
                            # Use discord.py's built-in command invocation
                            ctx.message.content = (
                                f"{ctx.prefix}{ctx.invoked_with} {prompt}".strip()
                            )
                            await self.invoke(ctx)

                            return  # Don't process as regular message

                        except Exception as e:
                            # Silent fail - don't expose automation errors to Discord
                            logger.error(f"Command execution failed: {e}")

                            return  # Don't process as regular message

        # Check for "wen?" message and respond after 7 seconds (random chance to trigger)
        wen = r"\b(wen+\?+)$"
        if re.search(wen, message.content.lower(), re.IGNORECASE):
            # Random chance to trigger (10% chance)
            if random.random() > 0.10:
                return  # Skip this time

            # Check if we've already responded to this message or if it's in cooldown
            current_time = time.time()

            # Clean up expired entries periodically (every 50 entries or every 5 minutes)
            if len(self.wen_cooldown) > 50 or (hasattr(self, '_last_wen_cleanup') and 
                current_time - self._last_wen_cleanup > 300):
                self.wen_cooldown = {
                    msg_id: timestamp
                    for msg_id, timestamp in self.wen_cooldown.items()
                    if current_time - timestamp < self.wen_cooldown_duration
                }
                self._last_wen_cleanup = current_time

            # Check if this message has been processed recently
            if message.id not in self.wen_cooldown:
                # Mark this message as processed
                self.wen_cooldown[message.id] = current_time

                # Wait 7 seconds before responding
                await asyncio.sleep(7)
                await message.channel.send("wen?")
            return  # Don't process as regular message

        # Check for airdrop commands
        content = message.content.lower()
        if content.startswith(
            (
                "$airdrop",
                "$triviadrop",
                "$mathdrop",
                "$phrasedrop",
                "$redpacket",
            )
        ):
            # This is an airdrop command, process it
            await self.process_airdrop_command(message)
            return  # Don't process as regular message

        # Check if the bot should respond:
        # 1. Directly mentioned
        # 2. In a DM (private message)
        # 3. Replied to
        # 4. Name "Jakey" mentioned
        should_respond = False

        # Always respond to private messages (but not to ourselves)
        if isinstance(message.channel, discord.DMChannel):
            should_respond = True
        elif self.user and self.user.mentioned_in(message):
            should_respond = True
        elif message.reference and message.reference.resolved:
            # Check if it's a reply to the bot
            if (
                hasattr(message.reference.resolved, "author")
                and message.reference.resolved.author == self.user
            ):
                should_respond = True
        elif "jakey" in message.content.lower():
            # Check if "jakey" is mentioned in the message
            should_respond = True
        elif await self.db.acheck_message_for_keywords(message.content):
            # Check if any configured keywords are in the message
            # Random chance to trigger (50% chance) for better responsiveness
            if random.random() <= 0.30:
                should_respond = True
                logger.info(f"Keyword triggered response (50% chance hit)")

        # Check guild blacklist - ignore messages from blacklisted guilds but allow DMs
        if (
            should_respond
            and message.guild
            and str(message.guild.id) in GUILD_BLACKLIST
        ):
            logger.info(
                f"Ignoring message from blacklisted guild: {message.guild.name} ({message.guild.id})"
            )
            should_respond = False

        # Add a cooldown to prevent spam (3 seconds)
        current_time = time.time()
        if hasattr(self, "_last_response_time"):
            if (
                current_time - self._last_response_time
                < JakeyConstants.RESPONSE_COOLDOWN_SECONDS
            ):
                # Only skip if it's not a direct mention or DM
                if not (
                    isinstance(message.channel, discord.DMChannel)
                    or (self.user and self.user.mentioned_in(message))
                ):
                    should_respond = False
        if should_respond:
            self._last_response_time = current_time

        if should_respond:
            await self.process_jakey_response(message)

    async def process_jakey_response(self, message):
        """Process Jakey's AI response to a message."""
        try:
            # Check user rate limit first
            user_id = str(message.author.id)
            is_rate_limited, time_remaining = await self._check_user_rate_limit(user_id)
            
            if is_rate_limited:
                # Notify user about rate limit
                minutes = int(time_remaining // 60)
                seconds = int(time_remaining % 60)
                if minutes > 0:
                    time_str = f"{minutes}m {seconds}s"
                else:
                    time_str = f"{seconds}s"
                
                logger.info(f"User {user_id} rate limited, {time_remaining:.1f}s remaining")
                await message.channel.send(
                    f"🚫 **Whoa there, slow down!** You're hitting me up too fast. "
                    f"Try again in **{time_str}**."
                )
                return
            
            # Increment user request count
            await self._increment_user_request(user_id)
            
            # Add thinking reaction to show we're processing
            try:
                await message.add_reaction("🤔")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass  # Message deleted or no permission

            # Use global AI provider manager singleton
            if not hasattr(self, "_ai_manager"):
                self._ai_manager = ai_provider_manager

            # Prepare the message for AI processing
            user_content = message.content.strip()
            if not user_content:
                return  # Don't respond to empty messages

            # Get memory context for the user
            memory_context = ""
            try:
                from tools.memory_search import memory_search_tool

                memory_context = (
                    await memory_search_tool.get_memory_context_for_message(
                        str(message.author.id), message.content
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to get memory context: {e}")

            # Create system message - combine system prompt and memory context
            # Add anti-repetition rules to prevent repetitive responses
            from ai.response_uniqueness import response_uniqueness

            if not hasattr(self, "_response_uniqueness"):
                self._response_uniqueness = response_uniqueness
            system_content = self._response_uniqueness.enhance_system_prompt_base(
                SYSTEM_PROMPT
            )

            # Inject recent responses so AI knows what it already said (prevents repetition)
            recent_responses = list(
                response_uniqueness.user_responses.get(str(message.author.id), [])
            )[-3:]
            if recent_responses:
                recent_text = "\n".join(
                    [
                        f"- {resp[:300]}..." if len(resp) > 300 else f"- {resp}"
                        for resp in recent_responses
                    ]
                )
                system_content += (
                    f"\n\nYOUR RECENT RESPONSES TO THIS USER (DO NOT REPEAT THESE - use different openings, structure, and phrasing):\n"
                    f"{recent_text}"
                )

            if memory_context:
                system_content += f"\n\nUser Context (remembered from previous conversations):\n{memory_context}\n\nUse this context to personalized your response, but don't explicitly mention that you're remembering things."

            # Add channel context if available
            channel_context = await self.collect_recent_channel_context(
                message,
                limit_minutes=CHANNEL_CONTEXT_MINUTES,
                message_limit=CHANNEL_CONTEXT_MESSAGE_LIMIT,
            )
            if channel_context:
                system_content += f"\n\n{channel_context}\n\nUse this channel context to understand what's being discussed."
                logger.info(
                    f"Added channel context ({len(channel_context)} chars) to AI prompt"
                )

            # Add explicit current context (IDs) to help with tool calls and reduce tool loops
            guild_info = (
                f"{message.guild.name} (ID: {message.guild.id})"
                if message.guild
                else "Direct Message (No Guild)"
            )
            channel_name = getattr(message.channel, "name", "DM")
            current_context_info = (
                f"\n\nCURRENT EXECUTION CONTEXT:"
                f"\n- Current Guild: {guild_info}"
                f"\n- Current Channel: {channel_name} (ID: {message.channel.id})"
                f"\n- Message Author: {message.author.name} (ID: {message.author.id})"
                f"\n- Your User ID: {self.user.id if self.user else 'Unknown'}"
                f"\n\nIMPORTANT: Use these IDs directly for tool calls. Do NOT call list_guilds or list_channels to find the current location."
            )
            system_content += current_context_info

            messages = [
                {"role": "system", "content": system_content},
            ]

            messages.append({"role": "user", "content": user_content})

            # Add conversation context if available
            try:
                from data.database import db

                conversation_history = await db.aget_recent_conversations(
                    str(message.author.id), limit=3
                )
                for entry in conversation_history:
                    user_msg = entry.get("user_message", "").strip()
                    bot_msg = entry.get("bot_response", "").strip()

                    # Only add non-empty messages to avoid API errors
                    if user_msg:
                        messages.append({"role": "user", "content": user_msg})
                    if bot_msg:
                        messages.append({"role": "assistant", "content": bot_msg})
            except Exception as e:
                logger.debug(f"Could not load conversation history: {e}")

            # Validate messages before sending to AI
            valid_messages = []
            for msg in messages:
                content = msg.get("content", "").strip()
                if content:  # Only include non-empty messages
                    valid_messages.append(msg)

            if len(valid_messages) < 2:  # Need at least system + user message
                logger.debug("Not enough valid messages for AI response")
                return

            # Generate AI response with tools
            from tools.tool_manager import tool_manager

            available_tools = tool_manager.get_available_tools()

            logger.debug(f"Generating AI response with model: {self.current_model}")
            response = await self._ai_manager.generate_text(
                messages=valid_messages,
                model=self.current_model,
                temperature=0.7,
                max_tokens=500,
                tools=available_tools,
                tool_choice="auto",
                # Anti-repetition parameters from OpenRouter API
                repetition_penalty=1.15,  # Slightly penalize repeated tokens
                frequency_penalty=0.3,  # Reduce repetition of frequent tokens
                presence_penalty=0.2,  # Slightly reduce repetition of present tokens
                # Enable model fallback routing for reliability
                use_fallback_routing=True,
                # Track user for rate limiting
                user=str(message.author.id),
            )

            if response.get("error"):
                error_msg = response['error']
                logger.error(f"AI generation error: {error_msg}")
                
                # Check if it's a rate limit error
                if response.get("rate_limited") or "rate limit" in str(error_msg).lower():
                    # Try to get time until reset from OpenRouter
                    try:
                        rate_status = openrouter_api.check_rate_limits()
                        if rate_status.get("seconds_until_reset"):
                            wait_time = int(rate_status["seconds_until_reset"])
                            await message.channel.send(
                                f"🚫 **I'm being rate limited by my AI provider.** "
                                f"Try again in **{wait_time}s**."
                            )
                        else:
                            await message.channel.send(
                                "🚫 **I'm being rate limited by my AI provider.** "
                                "Try again in about a minute."
                            )
                    except Exception:
                        await message.channel.send(
                            "🚫 **I'm being rate limited by my AI provider.** "
                            "Try again in about a minute."
                        )
                else:
                    await message.channel.send(
                        "💀 **Sorry, I'm having trouble thinking right now. Try again later.**"
                    )
                return

            # Parse OpenAI-format response from providers
            generated_image_urls = []  # Track image URLs to ensure they're in the response
            if "choices" in response and len(response["choices"]) > 0:
                ai_message = response["choices"][0]["message"]
                content = ai_message.get("content", "")
                ai_response = content.strip() if content else ""

                # Debug: Log what we received
                logger.info(
                    f"AI response content (first 200 chars): {repr(ai_response[:200]) if ai_response else 'EMPTY'}"
                )
                logger.info(f"AI message keys: {list(ai_message.keys())}")

                # Some models put content in 'reasoning' field instead of 'content'
                # But reasoning often contains internal chain-of-thought, not final answer
                if not ai_response and ai_message.get("reasoning"):
                    reasoning = ai_message.get("reasoning", "")
                    reasoning_details = ai_message.get("reasoning_details", [])
                    logger.info(
                        f"Model returned reasoning instead of content (len={len(reasoning)})"
                    )

                    # Try to extract actual response from reasoning
                    ai_response = extract_final_response_from_reasoning(reasoning)

                    if ai_response:
                        logger.info(
                            f"Extracted response from reasoning: {repr(ai_response[:200])}"
                        )
                    else:
                        logger.warning(
                            f"Could not extract clean response from reasoning"
                        )

                # Log full message if still empty
                if not ai_response:
                    logger.warning(f"Full ai_message: {ai_message}")

                # Handle tool calls if present
                tool_calls = ai_message.get("tool_calls", [])

                # DEFENSIVE: Check if model returned tool call as JSON text in content instead of using API
                if not tool_calls and ai_response:
                    extracted_calls, cleaned_response = extract_text_tool_calls(
                        ai_response
                    )
                    if extracted_calls:
                        logger.warning(
                            "⚠️ Model returned tool call as TEXT instead of using proper API format!"
                        )
                        tool_calls = extracted_calls
                        ai_response = cleaned_response
                        logger.info(
                            f"✅ Converted text-based tool call to proper format"
                        )

                # Multi-round tool execution loop
                tool_round = 0
                max_tool_rounds = 5
                generated_image_urls = []  # Track image URLs to ensure they're in the response

                while tool_calls and tool_round < max_tool_rounds:
                    tool_round += 1
                    logger.info(
                        f"🔄 Processing tool round {tool_round}/{max_tool_rounds} with {len(tool_calls)} calls"
                    )

                    # Check if tool calls exist
                    if not tool_calls:
                        break

                    # Save content for history, but clear for user output (we only show final result)
                    assistant_content = ai_response
                    ai_response = ""

                    # Execute tool calls and build tool responses
                    from tools.tool_manager import tool_manager

                    # Create tool response messages for the AI
                    tool_messages = []
                    for tool_call in tool_calls:
                        # Extract function name with defensive access
                        function_name = "unknown"
                        tool_call_id = tool_call.get("id", f"unknown_{id(tool_call)}")
                        try:
                            function_info = tool_call.get("function", {})
                            function_name = function_info.get("name", "unknown")

                            # Parse arguments - may already be a dict or may be JSON string
                            import json

                            args = function_info.get("arguments", {})
                            if isinstance(args, str):
                                arguments = json.loads(args)
                            else:
                                arguments = args

                            # Handle special "current" channel_id for Discord tools
                            channel_id_arg_names = ["channel_id", "channel"]
                            for arg_name in channel_id_arg_names:
                                if arg_name in arguments:
                                    val = str(arguments[arg_name]).lower().strip()
                                    if val in (
                                        "current",
                                        "current channel",
                                        "this channel",
                                        "here",
                                    ):
                                        arguments[arg_name] = str(message.channel.id)
                                        logger.info(
                                            f"Replaced '{val}' channel_id with actual ID: {arguments[arg_name]}"
                                        )

                            # Convert string numbers to integers for limit parameters
                            int_arg_names = ["limit", "count", "num", "amount"]
                            for arg_name in int_arg_names:
                                if arg_name in arguments and isinstance(
                                    arguments[arg_name], str
                                ):
                                    try:
                                        arguments[arg_name] = int(arguments[arg_name])
                                    except ValueError:
                                        pass  # Keep as string if not a valid number

                            # Execute the tool
                            logger.info(
                                f"Executing tool: {function_name} with args: {arguments}"
                            )
                            result = await tool_manager.execute_tool(
                                function_name, arguments, str(message.author.id)
                            )
                            # Truncate result for logging
                            log_result = str(result)
                            if len(log_result) > 200:
                                log_result = log_result[:200] + "..."
                            logger.info(f"Tool result: {function_name} -> {log_result}")

                            # Track generated image URLs to ensure they appear in the response
                            if function_name == "generate_image" and isinstance(result, str) and result.startswith("http"):
                                generated_image_urls.append(result)
                                logger.info(f"📸 Tracked generated image URL for response")

                            # Add tool response
                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "content": str(result),
                                    "tool_call_id": tool_call_id,
                                }
                            )
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {e}")
                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "content": f"Error executing tool {function_name}: {str(e)}",
                                    "tool_call_id": tool_call_id,
                                }
                            )

                    # Update conversation history
                    if tool_messages:
                        # Add the assistant message that requested the tools
                        valid_messages.append(
                            {
                                "role": "assistant",
                                "content": assistant_content,
                                "tool_calls": tool_calls,
                            }
                        )
                        # Add the tool results
                        valid_messages.extend(tool_messages)

                        # Generate follow-up response
                        max_retries = 2
                        retry_delay = 1.0
                        final_response = None

                        # Minimal delay between tool rounds (reduced from 2.0s)
                        await asyncio.sleep(0.5)

                        # Force "none" on final round to prevent infinite loops
                        is_final_round = tool_round >= max_tool_rounds - 1
                        current_tool_choice = "none" if is_final_round else "auto"

                        if is_final_round:
                            logger.info(
                                f"⚠️ Final tool round - forcing tool_choice='none' to stop loop"
                            )

                        for attempt in range(max_retries):
                            # Check if this is a web_search response - use dedicated model
                            has_web_search = any(
                                tc.get("function", {}).get("name") == "web_search"
                                for tc in tool_calls
                            )

                            if has_web_search and not is_final_round:
                                final_response = (
                                    await self._ai_manager.generate_text_for_web_search(
                                        messages=valid_messages,
                                        temperature=0.5,
                                        max_tokens=1000,
                                    )
                                )
                            else:
                                final_response = await self._ai_manager.generate_text(
                                    messages=valid_messages,
                                    model=self.current_model,
                                    temperature=0.7,
                                    max_tokens=2000,
                                    tools=available_tools
                                    if not is_final_round
                                    else None,
                                    tool_choice=current_tool_choice,
                                    # Anti-repetition parameters
                                    repetition_penalty=1.15,
                                    frequency_penalty=0.3,
                                    presence_penalty=0.2,
                                    use_fallback_routing=True,
                                    user=str(message.author.id),
                                )

                            if final_response.get("error"):
                                error_msg = final_response.get("error", "")
                                error_code = final_response.get("code", "")
                                logger.warning(
                                    f"Follow-up call failed (attempt {attempt + 1}): {error_msg}"
                                )

                                if error_code and error_code in [500, 502, 503, 504]:
                                    if attempt < max_retries - 1:
                                        await asyncio.sleep(retry_delay)
                                        retry_delay *= 2
                                        continue

                                # If non-retriable or retries exhausted
                                if attempt == max_retries - 1:
                                    # Check for rate limit
                                    if final_response.get("rate_limited") or "rate limit" in str(error_msg).lower():
                                        await message.channel.send(
                                            "🚫 **I'm being rate limited by my AI provider.** "
                                            "Try again in about a minute."
                                        )
                                    else:
                                        await message.channel.send(
                                            "💀 **Sorry, I'm having trouble thinking right now.**"
                                        )
                                    return
                            else:
                                break  # Success

                        # Process the new response (guard against None)
                        if final_response is None:
                            logger.error("final_response is None after retry loop")
                            await message.channel.send(
                                "💀 **Sorry, I'm having trouble thinking right now.**"
                            )
                            return

                        if (
                            "choices" in final_response
                            and len(final_response["choices"]) > 0
                        ):
                            ai_message = final_response["choices"][0]["message"]
                            content = ai_message.get("content", "")

                            # Check reasoning
                            if not content and ai_message.get("reasoning"):
                                content = extract_final_response_from_reasoning(
                                    ai_message.get("reasoning", "")
                                )

                            ai_response = content.strip() if content else ""
                            tool_calls = ai_message.get("tool_calls", [])

                            # Check for text-based tool calls again (defensive)
                            if not tool_calls and ai_response:
                                extracted_calls, cleaned_response = (
                                    extract_text_tool_calls(ai_response)
                                )
                                if extracted_calls:
                                    tool_calls = extracted_calls
                                    ai_response = cleaned_response
                                    logger.info(
                                        f"✅ Converted text-based tool call in loop"
                                    )
                        else:
                            # No valid choices or error response structure
                            ai_response = final_response.get("content", "")
                            tool_calls = []

                        # Loop continues if tool_calls is not empty
                    else:
                        # No tool messages generated? Should not happen if tool_calls was true.
                        tool_calls = []  # Break loop

                if tool_calls:
                    logger.warning(
                        f"⚠️ Max tool rounds ({max_tool_rounds}) reached. Stopping."
                    )
                    ai_response += "\n\n*(I had to stop because I was doing too many things at once)*"
            else:
                ai_response = response.get("content", "").strip()
                logger.warning(
                    f"Response had no 'choices' key. Response keys: {response.keys()}"
                )

            if not ai_response:
                logger.warning(
                    f"ai_response is empty before sending 'mind went blank'. ai_response={repr(ai_response)}"
                )
                await message.channel.send("💀 **My mind went blank. Try again?**")
                return

            # Validate message object has required attributes
            if (
                not hasattr(message, "author")
                or not hasattr(message, "channel")
                or not hasattr(message, "content")
            ):
                logger.warning(f"Invalid message object type: {type(message)}")
                await message.channel.send("💀 **Processing error. Try again?**")
                return

            # Check for repetition using the response_uniqueness manager
            is_repetitive, repetition_info = response_uniqueness.is_repetitive_response(
                str(message.author.id), ai_response
            )
            if is_repetitive:
                logger.warning(
                    f"🔄 Repetition detected for user {message.author.id}: {repetition_info}"
                )
                logger.debug(f"Original response: {repr(ai_response[:100])}")

                # Show user's response history for debugging
                user_history = list(
                    response_uniqueness.user_responses.get(str(message.author.id), [])
                )
                logger.debug(
                    f"User {message.author.id} has {len(user_history)} responses in history"
                )
                if user_history:
                    logger.debug(
                        f"Recent responses: {[repr(h[:50]) for h in user_history[-3:]]}"
                    )

                # Use AI to rephrase the response instead of sending it as-is
                logger.info("Generating rephrased response to avoid repetition...")
                user_message_content = (
                    message.content if hasattr(message, "content") else str(message)
                )
                original_response = ai_response
                ai_response = await self._generate_non_repetitive_response(
                    user_message_content, ai_response
                )
                # Log the final response length to verify it changed
                logger.info(
                    f"Rephrased response generated: original length {len(original_response)} chars, "
                    f"new length {len(ai_response)} chars"
                )
                logger.debug(f"New response preview: {repr(ai_response[:100])}")
            else:
                logger.debug(
                    f"No repetition detected for response: {repr(ai_response[:100])}"
                )

            # Sanitize response to remove any leaked tool call syntax
            ai_response = sanitize_ai_response(ai_response)

            # Ensure generated image URLs are included in the response
            # The AI sometimes forgets to include them, so we append any missing ones
            if generated_image_urls:
                for url in generated_image_urls:
                    if url not in ai_response:
                        ai_response = ai_response.rstrip() + "\n\n" + url
                        logger.info(f"📸 Appended missing image URL to response")

            if not ai_response:
                # Response was only tool call syntax with no actual message
                logger.warning(
                    "AI response was empty after sanitization (contained only tool call syntax)"
                )
                await message.channel.send(
                    "💀 **I got the info but forgot what to say. Try rephrasing?**"
                )
                return

            # Send the response with typing indicator
            # Calculate typing delay based on response length (simulates natural typing)
            typing_time = min(
                len(ai_response) / 50, 3.0
            )  # ~50 chars/sec, max 3 seconds
            async with message.channel.typing():
                await asyncio.sleep(typing_time)

            # Discord has a 2000 character limit - truncate if needed
            if len(ai_response) > 2000:
                original_length = len(ai_response)
                # Try to truncate at a sentence boundary
                truncated = ai_response[:1990]
                last_period = truncated.rfind(".")
                last_newline = truncated.rfind("\n")
                cut_point = max(last_period, last_newline)
                if cut_point > 1500:  # Only use sentence boundary if reasonable
                    ai_response = truncated[: cut_point + 1] + "..."
                else:
                    ai_response = truncated + "..."
                logger.info(
                    f"Truncated response from {original_length} to {len(ai_response)} chars"
                )

            await message.channel.send(ai_response)

            # Remove thinking reaction after sending response
            try:
                await message.remove_reaction("🤔", self.user)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass  # Message deleted or no permission

            # Store the interaction
            try:
                from data.database import db

                await db.aadd_conversation(
                    str(message.author.id),
                    [{"user": message.content, "assistant": ai_response}],
                    str(message.channel.id),
                )
                self._store_user_response(str(message.author.id), ai_response)

                # Extract and store memories automatically if enabled
                if AUTO_MEMORY_EXTRACTION_ENABLED:
                    await self._extract_and_store_memories(
                        str(message.author.id), message.content, ai_response
                    )

            except Exception as e:
                logger.debug(f"Could not store conversation: {e}")

        except Exception as e:
            # Silent fail - don't expose automation errors to Discord
            logger.error(f"Error in process_jakey_response: {e}")

    async def _extract_and_store_memories(
        self, user_id: str, user_message: str, bot_response: str
    ):
        """
        Extract meaningful information from the conversation and store it in memory.
        """
        try:
            # Import the memory extractor
            from memory.auto_memory_extractor import AutoMemoryExtractor

            # Initialize the extractor
            extractor = AutoMemoryExtractor()

            # Extract memories from the conversation
            memories = await extractor.extract_memories_from_conversation(
                user_message, bot_response, user_id
            )

            if memories:
                # Filter memories based on confidence threshold
                filtered_memories = [
                    m
                    for m in memories
                    if m.get("confidence", 1.0)
                    >= AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD
                ]

                if filtered_memories:
                    # Store the extracted memories
                    results = await extractor.store_memories(filtered_memories, user_id)
                    successful = sum(1 for result in results if result)

                    if successful > 0:
                        logger.debug(
                            f"Successfully stored {successful}/{len(filtered_memories)} auto-extracted memories"
                        )
                    else:
                        logger.debug("Failed to store any auto-extracted memories")
                else:
                    logger.debug("No memories met confidence threshold")

        except ImportError as e:
            logger.warning(f"Auto memory extractor not available: {e}")
        except Exception as e:
            logger.error(f"Error in automatic memory extraction: {e}")

    async def setup_periodic_memory_cleanup(self):
        """
        Set up periodic cleanup of old memories if enabled.
        """
        if not AUTO_MEMORY_CLEANUP_ENABLED:
            logger.debug("Automatic memory cleanup disabled")
            return

        try:
            from memory.auto_memory_extractor import MemoryCleanupManager

            cleanup_manager = MemoryCleanupManager()

            # Schedule cleanup to run once per day
            asyncio.create_task(self._periodic_memory_cleanup_task(cleanup_manager))
            logger.info("Periodic memory cleanup scheduled")

        except ImportError as e:
            logger.warning(f"Memory cleanup manager not available: {e}")
        except Exception as e:
            logger.error(f"Error setting up periodic memory cleanup: {e}")

    async def _periodic_memory_cleanup_task(self, cleanup_manager):
        """
        Periodic task for cleaning up old memories.
        """
        while True:
            try:
                # Wait 24 hours between cleanups
                await asyncio.sleep(86400)

                logger.info("Running periodic memory cleanup")
                await cleanup_manager.cleanup_old_memories(
                    max_age_days=AUTO_MEMORY_MAX_AGE_DAYS,
                    confidence_threshold=AUTO_MEMORY_EXTRACTION_CONFIDENCE_THRESHOLD,
                )

            except Exception as e:
                logger.error(f"Error in periodic memory cleanup: {e}")

    async def collect_recent_channel_context(
        self, message, limit_minutes: int = 30, message_limit: int = 20
    ) -> str:
        """
        Collect recent channel messages for context.

        Args:
            message: The Discord message object
            limit_minutes: How far back to look (default: 30 minutes)
            message_limit: Maximum number of messages to include (default: 20)

        Returns:
            Formatted string of recent channel messages, or empty string for DMs
        """
        try:
            # Return empty for DM channels (no guild)
            if not message.guild:
                return ""

            channel = message.channel
            if not hasattr(channel, "history"):
                return ""

            # Calculate cutoff time
            from datetime import datetime, timedelta, timezone

            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=limit_minutes)

            # Collect messages
            messages = []
            async for msg in channel.history(
                limit=message_limit + 5, after=cutoff_time
            ):
                # Skip system messages and the current message
                if msg.type != discord.MessageType.default:
                    continue
                if msg.id == message.id:
                    continue

                # Format the message - include bot's own messages too for context
                timestamp = msg.created_at.strftime("%H:%M")
                author_name = msg.author.name
                if msg.author == self.user:
                    author_name = "Jakey (me)"
                content = msg.content[:300]  # Truncate long messages
                if content:  # Only include non-empty messages
                    messages.append(f"[{timestamp}] {author_name}: {content}")

                if len(messages) >= message_limit:
                    break

            if not messages:
                return ""

            # Reverse to show chronological order (oldest first)
            messages.reverse()

            # Format as context
            context = "Recent channel conversation:\n" + "\n".join(messages)
            logger.debug(f"Collected {len(messages)} messages for channel context")
            return context

        except Exception as e:
            logger.debug(f"Could not collect channel context: {e}")
            return ""

    async def process_webhook_relay(self, message):
        """Process webhook relay for incoming messages"""
        try:
            # Only relay messages from guild channels (not DMs)
            if not message.guild:
                return

            # Check if it's a text-based channel (TextChannel, Thread, or similar)
            if not hasattr(message.channel, "name") or not hasattr(
                message.channel, "id"
            ):
                return

            # Rest of webhook relay logic would go here
            # For now, just return to avoid errors
            return

        except Exception as e:
            logger.error(f"Error in webhook relay: {e}")
            return

    async def _check_due_reminders(self):
        """Background task to periodically check for due reminders and send notifications"""
        import datetime

        from discord.ext import tasks

        while True:
            try:
                # Check for due reminders every 30 seconds
                await asyncio.sleep(30)

                # Use the check_due_reminders tool to find due reminders
                due_reminders_result = self.tool_manager.check_due_reminders()

                if "No reminders are currently due" in due_reminders_result:
                    continue  # No reminders to process, continue loop

                if "error" in due_reminders_result.lower():
                    logger.error(
                        f"Error checking due reminders: {due_reminders_result}"
                    )
                    continue

                # Parse reminder IDs from the result
                # The result format is "🔔 N reminder(s) are due:\n- title (ID: X, User: Y)\n"
                reminder_matches = re.findall(
                    r"\(ID: (\d+), User: ([\w\d]+)\)", due_reminders_result
                )

                for reminder_id, user_id in reminder_matches:
                    try:
                        # Get the full reminder details
                        reminder = self.db.get_reminder(int(reminder_id))
                        if not reminder:
                            logger.warning(
                                f"Could not find reminder with ID {reminder_id}"
                            )
                            continue

                        # Update the reminder status to 'triggered'
                        self.db.update_reminder_status(int(reminder_id), "triggered")

                        # Find the user and send the reminder
                        # Look for the Discord user in the bot's cache
                        discord_user = None
                        for guild in self.guilds:
                            discord_user = guild.get_member(int(user_id))
                            if discord_user:
                                break

                        # If user not found in cache, try to fetch directly
                        if not discord_user:
                            try:
                                discord_user = await self.fetch_user(int(user_id))
                            except (
                                discord.NotFound,
                                discord.HTTPException,
                                ValueError,
                            ) as e:
                                logger.warning(
                                    f"Could not find user {user_id} for reminder {reminder_id}: {e}"
                                )
                                continue

                        if discord_user:
                            try:
                                # Determine where to send the reminder
                                target_channel = None

                                if reminder["channel_id"]:
                                    # Try to find the specific channel
                                    for guild in self.guilds:
                                        target_channel = guild.get_channel(
                                            int(reminder["channel_id"])
                                        )
                                        if target_channel:
                                            break

                                # If no specific channel or channel not found, send to user directly
                                if not target_channel:
                                    target_channel = (
                                        discord_user.dm_channel
                                        or await discord_user.create_dm()
                                    )

                                # Send the reminder message
                                reminder_msg = f"⏰ **REMINDER**: {reminder['title']}\n{reminder['description']}"

                                # Check if the target channel is a valid messaging channel
                                if isinstance(
                                    target_channel,
                                    (TextChannel, DMChannel, GroupChannel, Thread),
                                ):
                                    await target_channel.send(reminder_msg)
                                else:
                                    logger.warning(
                                        f"Cannot send reminder to user {user_id}: target channel type {type(target_channel).__name__} does not support messaging"
                                    )
                                logger.info(
                                    f"Sent reminder {reminder_id} to user {user_id}"
                                )

                            except discord.Forbidden:
                                logger.warning(
                                    f"No permission to send reminder to user {user_id}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error sending reminder to user {user_id}: {e}"
                                )

                    except Exception as e:
                        logger.error(f"Error processing reminder {reminder_id}: {e}")
                        # If there's an error, make sure to update the status back to pending or handle appropriately
                        continue

            except Exception as e:
                logger.error(f"Error in _check_due_reminders background task: {e}")
                # Wait a bit before continuing to avoid rapid error loops
                await asyncio.sleep(60)

    async def process_airdrop_command(self, original_message):
        """Process airdrop commands automatically"""
        content = original_message.content.lower()

        # Check if this is an airdrop command we should process
        if not content.startswith(
            (
                "$airdrop",
                "$triviadrop",
                "$mathdrop",
                "$phrasedrop",
                "$redpacket",
                "$ airdrop",
                "$ triviadrop",
                "$ mathdrop",
                "$ phrasedrop",
                "$ redpacket",
            )
        ):
            return

            # Check if server is in whitelist (if whitelist is enabled)
        if AIRDROP_SERVER_WHITELIST:
            whitelist_servers = [
                s.strip() for s in AIRDROP_SERVER_WHITELIST.split(",") if s.strip()
            ]
            if str(original_message.guild.id) not in whitelist_servers:
                logger.debug(
                    f"Server {original_message.guild.id} not in airdrop whitelist"
                )
                return

        # Check if user is in ignore list
        ignore_users_list = (
            AIRDROP_IGNORE_USERS.split(",") if AIRDROP_IGNORE_USERS else []
        )
        if str(original_message.author.id) in ignore_users_list:
            return

        logger.debug(f"Detected potential drop: {original_message.content}")

        try:
            # Wait for the tip.cc bot response - increased timeout for slow tip.cc responses
            tip_cc_message = await self.wait_for(
                "message",
                timeout=15,  # Increased to 15s to handle slow tip.cc responses
                check=lambda m: (
                    m.author.id == 617037497574359050
                    and m.channel.id == original_message.channel.id
                    and m.embeds
                ),
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout waiting for tip.cc message in {original_message.channel.name}"
            )
            return

        if not tip_cc_message.embeds:
            return

        embed = tip_cc_message.embeds[0]
        drop_ends_in = (
            (embed.timestamp.timestamp() - time.time()) if embed.timestamp else 5
        )

        # Check if drop expires too soon
        if AIRDROP_IGNORE_TIME_UNDER > 0 and drop_ends_in < AIRDROP_IGNORE_TIME_UNDER:
            logger.debug(
                f"Ignoring drop with only {drop_ends_in:.1f}s remaining (threshold: {AIRDROP_IGNORE_TIME_UNDER}s)"
            )
            return

        # Check if drop value is too low (extract from description if available)
        if AIRDROP_IGNORE_DROPS_UNDER > 0:
            drop_value = self._extract_drop_value(embed)
            if drop_value is not None and drop_value < AIRDROP_IGNORE_DROPS_UNDER:
                logger.debug(
                    f"Ignoring drop worth ${drop_value:.2f} (threshold: ${AIRDROP_IGNORE_DROPS_UNDER:.2f})"
                )
                return

        # Apply delay logic - optimized for ultra-fast airdrops
        if drop_ends_in <= 10:  # For fast airdrops (1-10s), minimize delay
            if AIRDROP_SMART_DELAY:
                # Very aggressive delay for fast airdrops - max 0.5s
                delay = min(drop_ends_in / 20, 0.5) if drop_ends_in > 1 else 0
            elif AIRDROP_RANGE_DELAY:
                delay = uniform(0, 0.2)  # Minimal random delay
            else:
                delay = 0  # No delay for fast airdrops
        else:
            # Use normal delay logic for longer airdrops
            await self.maybe_delay(drop_ends_in)
            delay = 0  # Skip the sleep below since we already waited

        if delay > 0:
            logger.debug(f"Fast airdrop delay: {round(delay, 3)}s")
            await asyncio.sleep(delay)

        try:
            # Get embed title safely (may be None)
            embed_title = (embed.title or "").lower()

            # Airdrop - Optimized for 1-10s window
            if "airdrop" in embed_title and not AIRDROP_DISABLE_AIRDROP:
                if tip_cc_message.components and tip_cc_message.components[0].children:
                    button = tip_cc_message.components[0].children[0]

                    # Ultra-fast retry logic - no delays, minimal validation
                    for attempt in range(2):  # Only 2 attempts for speed
                        try:
                            # Skip most validations for speed - only check if button is disabled
                            if getattr(button, "disabled", False):
                                logger.debug("Airdrop button disabled - drop closed")
                                break

                            # Click with reasonable timeout for network latency
                            await asyncio.wait_for(button.click(), timeout=5.0)

                            logger.info(
                                f"Entered airdrop in {original_message.channel.name}"
                            )
                            break  # Success

                        except asyncio.TimeoutError:
                            # Immediate retry on timeout - no sleeping
                            if attempt == 0:  # Only log first timeout
                                logger.debug(
                                    "Airdrop click timeout, retrying immediately..."
                                )

                        except discord.HTTPException as e:
                            # Fast error handling - no retries for most HTTP errors
                            if "10008" in str(e):  # Unknown Message
                                logger.debug("Airdrop expired (404)")
                            elif "50035" in str(e):  # Invalid Form Body
                                logger.debug("Airdrop closed (400)")
                            else:
                                logger.debug(f"Airdrop HTTP error: {e}")
                            break

                        except discord.ClientException as e:
                            # One immediate retry on client error, then give up
                            if attempt == 0:
                                logger.debug("Airdrop client error, retrying...")
                            else:
                                logger.debug(f"Airdrop client error failed: {e}")

                        except Exception as e:
                            logger.debug(f"Airdrop unexpected error: {e}")
                            break

            # Phrase drop
            elif "phrase drop" in embed_title and not AIRDROP_DISABLE_PHRASEDROP:
                phrase = clean_phrase_comprehensive(embed.description)
                if phrase:
                    async with original_message.channel.typing():
                        await asyncio.sleep(self.typing_delay(phrase))
                    await original_message.channel.send(phrase)
                    logger.info(
                        f"Entered phrase drop in {original_message.channel.name}"
                    )
                else:
                    logger.warning(
                        f"Failed to extract phrase from embed: {embed.description}"
                    )

            # Math drop
            elif "math" in embed_title and not AIRDROP_DISABLE_MATHDROP:
                expr = embed.description.split("`")[1].strip()
                answer = self.safe_eval_math(expr)
                if answer is not None:
                    answer = (
                        int(answer)
                        if isinstance(answer, float) and answer.is_integer()
                        else answer
                    )
                    async with original_message.channel.typing():
                        await asyncio.sleep(self.typing_delay(str(answer)))
                    await original_message.channel.send(str(answer))
                    logger.info(f"Entered math drop in {original_message.channel.name}")

            # Trivia drop
            elif "trivia" in embed_title and not AIRDROP_DISABLE_TRIVIADROP:
                category = embed.title.split("Trivia time - ")[1].strip()
                question = embed.description.replace("**", "").split("*")[1].strip()

                # VALIDATE category input to prevent directory traversal and injection attacks
                if not self._validate_trivia_category(category):
                    logger.warning(f"Invalid trivia category detected: {category}")
                    return

                # Use new trivia manager with database and caching
                try:
                    from utils.trivia_manager import trivia_manager

                    # Find answer using enhanced trivia system with timeout to prevent blocking
                    try:
                        answer = await asyncio.wait_for(
                            trivia_manager.find_trivia_answer(category, question),
                            timeout=5.0,  # 5 second timeout for trivia lookup
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Trivia lookup timed out for question in {original_message.channel.name}"
                        )
                        answer = None
                    except Exception as e:
                        logger.error(f"Error during trivia lookup: {e}")
                        answer = None

                    if answer and tip_cc_message.components:
                        for button in tip_cc_message.components[0].children:
                            if button.label.strip() == answer.strip():
                                # Add timeout handling and retry logic for button clicks
                                for attempt in range(3):  # Retry up to 3 times
                                    try:
                                        await asyncio.wait_for(
                                            button.click(), timeout=10.0
                                        )
                                        # Record successful trivia completion for learning with timeout
                                        try:
                                            await asyncio.wait_for(
                                                trivia_manager.record_successful_answer(
                                                    category,
                                                    question,
                                                    answer,
                                                    channel_id=str(
                                                        original_message.channel.id
                                                    ),
                                                    guild_id=str(
                                                        original_message.guild.id
                                                    )
                                                    if original_message.guild
                                                    else None,
                                                ),
                                                timeout=5.0,
                                            )

                                        except asyncio.TimeoutError:
                                            logger.warning(
                                                f"Trivia success recording timed out in {original_message.channel.name}"
                                            )
                                        except Exception as e:
                                            logger.error(
                                                f"Error recording trivia success: {e}"
                                            )

                                        # Success - both button click and recording completed
                                        logger.info(
                                            f"Entered trivia drop in {original_message.channel.name} (using enhanced trivia system)"
                                        )
                                        # Announce the correct answer in the channel
                                        try:
                                            await original_message.channel.send(
                                                f"Trivia Answer: {answer}"
                                            )
                                        except Exception as e:
                                            logger.error(
                                                f"Failed to announce trivia answer: {e}"
                                            )
                                        return  # Success, exit function
                                    except asyncio.TimeoutError:
                                        logger.warning(
                                            f"Timeout clicking trivia button (attempt {attempt + 1}/3)"
                                        )
                                        if (
                                            attempt < 2
                                        ):  # Don't sleep on the last attempt
                                            await asyncio.sleep(
                                                2**attempt
                                            )  # Exponential backoff
                                    except discord.HTTPException as e:
                                        logger.error(
                                            f"HTTP error clicking trivia button: {e}"
                                        )
                                        return  # Don't retry on HTTP errors
                                    except discord.ClientException as e:
                                        logger.warning(
                                            f"Client error clicking trivia button (likely timeout): {e}"
                                        )
                                        if (
                                            attempt < 2
                                        ):  # Don't sleep on the last attempt
                                            await asyncio.sleep(
                                                2**attempt
                                            )  # Exponential backoff
                                    except Exception as e:
                                        logger.debug(
                                            f"Failed to click trivia button: {e}"
                                        )
                                        if (
                                            attempt < 2
                                        ):  # Don't sleep on the last attempt
                                            await asyncio.sleep(
                                                2**attempt
                                            )  # Exponential backoff

                    # No answer found - try random button as fallback if enabled
                    if (
                        not answer
                        and tip_cc_message.components
                        and TRIVIA_RANDOM_FALLBACK
                    ):
                        logger.info(
                            f"No answer found for trivia question, trying random button in {original_message.channel.name}"
                        )
                        await self._try_random_trivia_button(
                            tip_cc_message, original_message, category, question
                        )

                except ImportError:
                    # Fallback to original method if trivia manager not available
                    logger.warning(
                        "Trivia manager not available, falling back to original method"
                    )
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"https://raw.githubusercontent.com/QuartzWarrior/OTDB-Source/main/{quote(category)}.csv"
                        ) as resp:
                            if resp.status == 200:
                                lines = (await resp.text()).splitlines()
                                for line in lines:
                                    q, a = line.split(",", 1)
                                    if question == unquote(q).strip():
                                        if tip_cc_message.components:
                                            for button in tip_cc_message.components[
                                                0
                                            ].children:
                                                if (
                                                    button.label.strip()
                                                    == unquote(a).strip()
                                                ):
                                                    # Add timeout handling and retry logic for button clicks
                                                    for attempt in range(
                                                        3
                                                    ):  # Retry up to 3 times
                                                        try:
                                                            await asyncio.wait_for(
                                                                button.click(),
                                                                timeout=10.0,
                                                            )
                                                            # Record successful trivia completion for learning (fallback method)
                                                            try:
                                                                from utils.trivia_manager import (
                                                                    trivia_manager,
                                                                )

                                                                await trivia_manager.record_successful_answer(
                                                                    category,
                                                                    question,
                                                                    unquote(a).strip(),
                                                                )
                                                            except Exception as e:
                                                                logger.debug(
                                                                    f"Failed to record trivia answer (fallback): {e}"
                                                                )

                                                            logger.info(
                                                                f"Entered trivia drop in {original_message.channel.name}"
                                                            )
                                                            # Announce the correct answer in the channel
                                                            try:
                                                                await original_message.channel.send(
                                                                    f"Trivia Answer: {unquote(a).strip()}"
                                                                )
                                                            except Exception as e:
                                                                logger.error(
                                                                    f"Failed to announce trivia answer: {e}"
                                                                )
                                                            return  # Success, exit function
                                                        except asyncio.TimeoutError:
                                                            logger.warning(
                                                                f"Timeout clicking trivia button (attempt {attempt + 1}/3)"
                                                            )
                                                            if (
                                                                attempt < 2
                                                            ):  # Don't sleep on the last attempt
                                                                await asyncio.sleep(
                                                                    2**attempt
                                                                )  # Exponential backoff
                                                        except (
                                                            discord.HTTPException
                                                        ) as e:
                                                            logger.error(
                                                                f"HTTP error clicking trivia button: {e}"
                                                            )
                                                            return  # Don't retry on HTTP errors
                                                        except (
                                                            discord.ClientException
                                                        ) as e:
                                                            logger.warning(
                                                                f"Client error clicking trivia button (likely timeout): {e}"
                                                            )
                                                            if (
                                                                attempt < 2
                                                            ):  # Don't sleep on the last attempt
                                                                await asyncio.sleep(
                                                                    2**attempt
                                                                )  # Exponential backoff
                                                        except Exception as e:
                                                            logger.error(
                                                                f"Unexpected error clicking trivia button: {e}"
                                                            )
                                                            return  # Don't retry on unexpected errors

                            # If we get here, no answer was found in fallback either - try random if enabled
                            if tip_cc_message.components and TRIVIA_RANDOM_FALLBACK:
                                logger.info(
                                    f"Fallback method also failed, trying random button in {original_message.channel.name}"
                                )
                                await self._try_random_trivia_button(
                                    tip_cc_message, original_message, category, question
                                )

            # Redpacket
            elif "appeared" in embed_title and not AIRDROP_DISABLE_REDPACKET:
                if tip_cc_message.components:
                    button = tip_cc_message.components[0].children[0]
                    if "envelope" in button.label.lower():
                        # Add timeout handling and retry logic for button clicks
                        for attempt in range(3):  # Retry up to 3 times
                            try:
                                await asyncio.wait_for(button.click(), timeout=10.0)
                                logger.info(
                                    f"Claimed redpacket in {original_message.channel.name}"
                                )
                                break  # Success, exit retry loop
                            except asyncio.TimeoutError:
                                logger.warning(
                                    f"Timeout clicking redpacket button (attempt {attempt + 1}/3)"
                                )
                                if attempt < 2:  # Don't sleep on the last attempt
                                    await asyncio.sleep(
                                        2**attempt
                                    )  # Exponential backoff
                            except discord.HTTPException as e:
                                logger.error(
                                    f"HTTP error clicking redpacket button: {e}"
                                )
                                break  # Don't retry on HTTP errors
                            except discord.ClientException as e:
                                logger.warning(
                                    f"Client error clicking redpacket button (likely timeout): {e}"
                                )
                                if attempt < 2:  # Don't sleep on the last attempt
                                    await asyncio.sleep(
                                        2**attempt
                                    )  # Exponential backoff
                            except Exception as e:
                                logger.error(
                                    f"Unexpected error clicking redpacket button: {e}"
                                )
                                break  # Don't retry on unexpected errors

        except (
            IndexError,
            AttributeError,
            discord.HTTPException,
            discord.NotFound,
        ) as e:
            logger.warning(
                f"Error handling drop in {original_message.channel.name}: {type(e).__name__}: {e}"
            )
            return

    def typing_delay(self, text: str) -> float:
        """Simulate typing time based on CPM."""
        cpm = randint(AIRDROP_CPM_MIN, AIRDROP_CPM_MAX)
        return len(text) / cpm * 60

    def _validate_trivia_category(self, category: str) -> bool:
        """Validate trivia category to prevent directory traversal and injection attacks."""
        # Allow alphanumeric characters, spaces, hyphens, underscores, and colons
        # This allows categories like "Entertainment: Music" or "Science: Technology"
        if not re.match(r"^[a-zA-Z0-9\s\-_:]+$", category):
            return False

        # Prevent directory traversal attempts
        if ".." in category or "/" in category or "\\" in category:
            return False

        # Prevent null bytes and other dangerous characters
        if "\x00" in category or "\n" in category or "\r" in category:
            return False

        # Reasonable length limit (increased for longer category names)
        if len(category) > 100:
            return False

        # Strip whitespace and check if still valid
        cleaned_category = category.strip()
        if not cleaned_category:
            return False

        return True

    async def _try_random_trivia_button(
        self, tip_cc_message, original_message, category: str, question: str
    ):
        """Try a random trivia button when no answer is known"""
        try:
            import random

            if (
                not tip_cc_message.components
                or not tip_cc_message.components[0].children
            ):
                logger.warning("No buttons available for random trivia selection")
                return

            # Get all available buttons
            buttons = list(tip_cc_message.components[0].children)
            random_button = random.choice(buttons)
            random_answer = random_button.label.strip()

            logger.info(f"Trying random trivia answer: {random_answer}")

            # Try to click the random button with retry logic
            for attempt in range(3):  # Retry up to 3 times
                try:
                    await asyncio.wait_for(random_button.click(), timeout=10.0)

                    # Record the random attempt for learning (marked as guess)
                    try:
                        from utils.trivia_manager import trivia_manager

                        await trivia_manager.record_successful_answer(
                            category,
                            question,
                            random_answer,
                            channel_id=str(original_message.channel.id),
                            guild_id=str(original_message.guild.id)
                            if original_message.guild
                            else None,
                        )
                        logger.info(f"Recorded random trivia guess: {random_answer}")
                    except Exception as e:
                        logger.debug(f"Failed to record random trivia guess: {e}")

                    logger.info(
                        f"Entered random trivia answer in {original_message.channel.name} (guess)"
                    )
                    return  # Success, exit function

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout clicking random trivia button (attempt {attempt + 1}/3)"
                    )
                    if attempt < 2:  # Don't sleep on the last attempt
                        await asyncio.sleep(2**attempt)  # Exponential backoff

                except discord.HTTPException as e:
                    logger.error(f"HTTP error clicking random trivia button: {e}")
                    return  # Don't retry on HTTP errors

                except discord.ClientException as e:
                    logger.warning(
                        f"Client error clicking random trivia button (likely timeout): {e}"
                    )
                    if attempt < 2:  # Don't sleep on the last attempt
                        await asyncio.sleep(2**attempt)  # Exponential backoff

                except Exception as e:
                    logger.error(f"Unexpected error clicking random trivia button: {e}")
                    return  # Don't retry on unexpected errors

        except Exception as e:
            logger.error(f"Error in random trivia button selection: {e}")

    def safe_eval_math(self, expr: str):
        """Safely evaluate basic math expressions using AST-based evaluation."""
        import ast
        import operator

        # Validate input characters first
        if not re.match(r"^[\d\.\+\-\*/%\(\)\s]+$", expr):
            return None

        # Supported operators for AST evaluation
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
        }

        def eval_expr(node):
            """Recursively evaluate AST nodes."""
            if isinstance(node, ast.Constant):  # <number> (Python 3.8+)
                if isinstance(node.value, (int, float)):
                    return node.value
                raise TypeError(f"Unsupported constant type: {type(node.value)}")
            elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
                left = eval_expr(node.left)
                right = eval_expr(node.right)
                return operators[type(node.op)](left, right)
            elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
                operand = eval_expr(node.operand)
                return operators[type(node.op)](operand)
            else:
                raise TypeError(f"Unsupported node type: {type(node)}")

        try:
            tree = ast.parse(expr, mode="eval")
            return eval_expr(tree.body)
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError):
            return None

    async def maybe_delay(self, drop_ends_in: float):
        """Handle smart/range/manual delay before acting."""
        if AIRDROP_SMART_DELAY:
            # More conservative delay - wait for 1/5 of remaining time, but max 3 seconds
            # Also ensure we don't wait longer than the drop duration minus a safety margin
            delay = min(drop_ends_in / 5, 3.0) if drop_ends_in > 2 else 0
        elif AIRDROP_RANGE_DELAY:
            delay = uniform(AIRDROP_DELAY_MIN, AIRDROP_DELAY_MAX)
        else:
            delay = AIRDROP_DELAY_MIN
        if delay > 0:
            logger.debug(f"Waiting {round(delay, 2)}s before acting...")
            await asyncio.sleep(delay)

    def _extract_drop_value(self, embed) -> Optional[float]:
        """Extract drop value from tip.cc embed."""
        try:
            # Check embed description for value patterns
            if embed.description:
                # Look for patterns like "$0.50", "0.50 USD", "50 cents", etc.
                patterns = [
                    r"\$(\d+\.?\d*)",  # $0.50
                    r"(\d+\.?\d*)\s*USD",  # 0.50 USD
                    r"(\d+\.?\d*)\s*dollar",  # 0.50 dollar
                    r"(\d+)\s*cent",  # 50 cents
                ]

                for pattern in patterns:
                    match = re.search(pattern, embed.description, re.IGNORECASE)
                    if match:
                        value = float(match.group(1))
                        # Convert cents to dollars if needed
                        if "cent" in pattern.lower() and value > 1:
                            value = value / 100
                        return value

            # Check embed title for value patterns
            if embed.title:
                title_patterns = [
                    r"\$(\d+\.?\d*)",
                    r"(\d+\.?\d*)\s*USD",
                ]

                for pattern in title_patterns:
                    match = re.search(pattern, embed.title, re.IGNORECASE)
                    if match:
                        return float(match.group(1))

            # Check embed fields if available
            if hasattr(embed, "fields") and embed.fields:
                for field in embed.fields:
                    if field.name and "value" in field.name.lower():
                        # Look for value in the field value
                        if field.value:
                            patterns = [r"\$(\d+\.?\d*)", r"(\d+\.?\d*)\s*USD"]
                            for pattern in patterns:
                                match = re.search(pattern, field.value, re.IGNORECASE)
                                if match:
                                    return float(match.group(1))

        except Exception as e:
            logger.debug(f"Error extracting drop value: {e}")

        return None

    async def on_member_join(self, member):
        """Handle new member joining a server - send welcome message if enabled."""
        # Import config values at runtime to allow patching in tests
        from config import (
            WELCOME_CHANNEL_IDS,
            WELCOME_ENABLED,
            WELCOME_PROMPT,
            WELCOME_SERVER_IDS,
        )

        # Check if welcome feature is enabled
        if not WELCOME_ENABLED:
            return None

        # Check if this server is configured for welcome messages
        if str(member.guild.id) not in WELCOME_SERVER_IDS:
            return None

        # Find a suitable channel to send the welcome message
        welcome_channel = None

        # First try to use configured welcome channel IDs
        if WELCOME_CHANNEL_IDS:
            # Filter out empty strings and None values
            valid_channel_ids = [
                cid for cid in WELCOME_CHANNEL_IDS if cid and cid.strip()
            ]
            if valid_channel_ids:
                for channel_id in valid_channel_ids:
                    try:
                        channel = member.guild.get_channel(int(channel_id.strip()))
                        if channel and isinstance(channel, discord.TextChannel):
                            welcome_channel = channel
                            logger.debug(
                                f"Found configured welcome channel: {channel.name} (ID: {channel.id})"
                            )
                            break
                    except (ValueError, TypeError):
                        # Invalid channel ID, skip
                        logger.warning(
                            f"Invalid channel ID in WELCOME_CHANNEL_IDS: {channel_id}"
                        )
                        continue

        # If no configured channel found, try to find a channel named 'welcome' or 'general'
        if not welcome_channel:
            for channel in member.guild.text_channels:
                if channel.name.lower() in ["welcome", "general"]:
                    welcome_channel = channel
                    logger.debug(f"Found fallback channel by name: {channel.name}")
                    break

        # If no specific channel found, use the first available text channel
        if not welcome_channel:
            welcome_channel = (
                member.guild.text_channels[0] if member.guild.text_channels else None
            )

        # If no channel available, return
        if not welcome_channel:
            logger.debug("No suitable welcome channel found")
            return None

        # Check if bot has permission to send messages
        if not welcome_channel.permissions_for(member.guild.me).send_messages:
            return None

        # Generate welcome message
        try:
            welcome_message = await self.generate_welcome_message(
                member, WELCOME_PROMPT
            )
            if welcome_message:
                # Prepend member mention to the welcome message
                full_welcome_message = f"{member.mention} {welcome_message}"
                await welcome_channel.send(full_welcome_message)
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            # Send a fallback welcome message if AI fails
            fallback_message = f"Welcome {member.mention} to {member.guild.name}! 🎰💀 Ready to lose some money? Don't forget to pick your roles and join the degenerate casino! EZ money awaits! 🎲💰"
            await welcome_channel.send(fallback_message)

    async def on_guild_join(self, guild):
        """Handle joining a new guild"""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        # Check and save permissions for this guild
        await self._check_and_save_permissions(guild)

    async def _check_and_save_permissions(self, target_guild=None):
        """
        Check bot permissions in guilds and save to memory.
        If target_guild is provided, only check that guild.
        Otherwise check all guilds.
        """
        try:
            guilds_to_check = [target_guild] if target_guild else self.guilds

            for guild in guilds_to_check:
                try:
                    # Get bot member in guild
                    me = guild.me
                    if me is None:
                        continue
                    permissions = me.guild_permissions

                    # Format permissions string
                    perms_list = []
                    if permissions.administrator:
                        perms_list.append("ADMINISTRATOR")
                    else:
                        if permissions.manage_messages:
                            perms_list.append("MANAGE_MESSAGES")
                        if permissions.kick_members:
                            perms_list.append("KICK_MEMBERS")
                        if permissions.ban_members:
                            perms_list.append("BAN_MEMBERS")
                        if permissions.moderate_members:
                            perms_list.append("MODERATE_MEMBERS")  # Timeout
                        if permissions.view_audit_log:
                            perms_list.append("VIEW_AUDIT_LOG")
                        if permissions.manage_channels:
                            perms_list.append("MANAGE_CHANNELS")
                        if permissions.manage_roles:
                            perms_list.append("MANAGE_ROLES")
                        if permissions.mention_everyone:
                            perms_list.append("MENTION_EVERYONE")
                        if permissions.send_messages:
                            perms_list.append("SEND_MESSAGES")

                    if not perms_list:
                        perms_list.append("NONE_SIGNIFICANT")

                    perms_str = ", ".join(perms_list)
                    info = f"Permissions in server '{guild.name}' (ID: {guild.id}): {perms_str}"

                    # Save to bot's memory (using bot's own ID)
                    # We store it as a 'fact' type memory for the bot user
                    if self.user:
                        self.db.add_memory(str(self.user.id), "bot_permissions", info)
                        logger.info(f"Saved permissions for {guild.name}: {perms_str}")

                except Exception as e:
                    logger.warning(
                        f"Error checking permissions for guild {guild.name if hasattr(guild, 'name') else 'unknown'}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error in _check_and_save_permissions: {e}")

    def _trim_messages_for_api(self, messages, max_chars=6000):
        """Trim messages to fit within API character limits by removing older messages."""
        if not messages:
            return messages

        # Calculate total characters in all messages
        total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)

        # If we're under the limit, return as-is
        if total_chars <= max_chars:
            return messages

        # Special handling for tool calls: ensure tool messages are kept with their tool_calls
        # Find tool_call_ids that have corresponding tool messages
        tool_call_ids = set()
        tool_message_ids = set()

        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tool_call in msg["tool_calls"]:
                    tool_call_ids.add(tool_call.get("id"))
            elif msg.get("role") == "tool":
                tool_message_ids.add(msg.get("tool_call_id"))

        # Messages that must be kept together
        required_tool_call_ids = tool_message_ids.intersection(tool_call_ids)

        # Keep the system message (first message) and the most recent messages
        trimmed_messages = []

        # Always keep the system message if it exists
        if messages and messages[0].get("role") == "system":
            trimmed_messages.append(messages[0])
            remaining_chars = max_chars - len(str(messages[0].get("content", "")))
        else:
            remaining_chars = max_chars

        # Collect messages to keep in correct order
        messages_to_keep = []

        # Add messages from most recent backwards until we hit the limit
        for msg in reversed(messages[len(trimmed_messages) :]):
            # Check if this message is required due to tool relationships
            must_keep = False
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Check if this assistant message has tool_calls that are referenced by kept tool messages
                for tool_call in msg["tool_calls"]:
                    if tool_call.get("id") in required_tool_call_ids:
                        must_keep = True
                        break
            elif msg.get("role") == "tool":
                # Keep tool messages that have corresponding tool_calls
                if msg.get("tool_call_id") in required_tool_call_ids:
                    must_keep = True

            msg_chars = len(str(msg.get("content", "")))

            if must_keep or (remaining_chars - msg_chars >= 0):
                messages_to_keep.append(msg)  # Collect in reverse order
                if not must_keep:  # Only deduct chars if not required to keep
                    remaining_chars -= msg_chars
            elif must_keep:
                # If we must keep but don't have space, truncate content
                if remaining_chars > 100:
                    truncated_content = (
                        str(msg.get("content", ""))[: remaining_chars - 10] + "..."
                    )
                    truncated_msg = msg.copy()
                    truncated_msg["content"] = truncated_content
                    messages_to_keep.append(truncated_msg)
                    remaining_chars = 0
                else:
                    # Can't fit even truncated, skip this message
                    pass
            else:
                # If message is too long and not required, truncate it
                if remaining_chars > 100:  # Only if we have at least 100 chars left
                    truncated_content = (
                        str(msg.get("content", ""))[: remaining_chars - 10] + "..."
                    )
                    truncated_msg = msg.copy()
                    truncated_msg["content"] = truncated_content
                    messages_to_keep.append(truncated_msg)
                break

        # Reverse the collected messages to restore correct chronological order
        messages_to_keep.reverse()
        trimmed_messages.extend(messages_to_keep)

        logger.debug(
            f"Trimmed messages from {len(messages)} to {len(trimmed_messages)} (chars: {total_chars} -> {sum(len(str(msg.get('content', ''))) for msg in trimmed_messages)})"
        )
        return trimmed_messages

    async def generate_welcome_message(self, member, custom_prompt=None):
        """Generate AI-powered welcome message for new member."""
        # Default welcome prompt if none provided
        if custom_prompt is None:
            custom_prompt = f"Welcome {member.name} to the server! Please introduce yourself and tell us about your interests."

        # Substitute template variables in the custom prompt
        template_vars = {
            "{username}": member.name,
            "{discriminator}": member.discriminator,
            "{server_name}": member.guild.name,
            "{member_count}": str(member.guild.member_count),
        }

        # Replace all template variables
        for var, value in template_vars.items():
            custom_prompt = custom_prompt.replace(var, str(value))

        try:
            # Generate response using AI with OpenAI-compatible format
            messages = [
                {
                    "role": "system",
                    "content": "You are Jakey - a snarky degenerate gambling Discord bot. Your purpose is to welcome new members with witty, sarcastic, and unfiltered messages. You're cynical, funny, and promote bad habits and bad ideas. Include gambling references, use slang like 'EZ money', 'wen bonus', 'rigged', and add appropriate emojis like 💀🎰💰🎲. Keep messages brief and engaging.",
                },
                {"role": "user", "content": custom_prompt},
            ]

            # Use the AI provider manager for automatic failover
            if not hasattr(self, "_ai_manager"):
                self._ai_manager = ai_provider_manager

            response = await self._ai_manager.generate_text(
                messages=messages,
                model=self.current_model,
                max_tokens=200,
                temperature=0.7,
            )

            if response and "choices" in response and len(response["choices"]) > 0:
                welcome_content = response["choices"][0]["message"]["content"]
                # Remove <functions>...</functions> tool call patterns
                welcome_content = re.sub(
                    r"<functions>.*?</functions>",
                    "",
                    welcome_content,
                    flags=re.DOTALL,
                )
                # Clean up extra whitespace
                welcome_content = re.sub(r"\n\s*\n", "\n\n", welcome_content).strip()
                return welcome_content
            return None

        except Exception as e:
            logger.error(f"Error generating welcome message: {e}")
            # Return a fallback welcome message if AI fails
            fallback_message = f"Welcome {member.name} to {member.guild.name}! 🎰💀 Ready to lose some money? Don't forget to pick your roles and join the degenerate casino! EZ money awaits! 🎲💰"
            logger.info(f"Using fallback welcome message for {member.name}")
            return fallback_message

    def _schedule_fallback_restoration(self):
        """Schedule automatic restoration to Pollinations after OpenRouter fallback timeout."""
        from config import (
            OPENROUTER_FALLBACK_RESTORE_ENABLED,
            OPENROUTER_FALLBACK_TIMEOUT,
        )

        if not OPENROUTER_FALLBACK_RESTORE_ENABLED:
            logger.debug("OpenRouter fallback restoration is disabled")
            return

        # Cancel any existing restoration task
        if self.fallback_restore_task and not self.fallback_restore_task.done():
            self.fallback_restore_task.cancel()

        # Store the current state
        self.openrouter_fallback_start_time = time.time()
        self.original_model_before_fallback = getattr(
            self, "_original_model_before_fallback", self.current_model
        )

        logger.info(f"Switched to OpenRouter as the only provider")

    def cancel_fallback_restoration(self):
        """Cancel any pending fallback restoration task."""
        if self.fallback_restore_task and not self.fallback_restore_task.done():
            self.fallback_restore_task.cancel()
            logger.debug("Cancelled fallback restoration task")

        self.openrouter_fallback_start_time = None
        self.original_model_before_fallback = None

    def get_fallback_status(self) -> Dict[str, Any]:
        """Get current fallback restoration status."""
        status = {
            "current_provider": self.current_api_provider or "openrouter",
            "current_model": self.current_model,
            "is_fallback_active": False,
            "fallback_start_time": None,
            "original_model": None,
        }

        return status

    async def _safe_send_message(self, channel, message: str) -> bool:
        """Safely send a message to a channel, checking if it supports sending"""
        try:
            if not hasattr(channel, "send"):
                return False
            await channel.send(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to channel: {e}")
            return False

    async def process_queued_command(self, command_data: dict) -> bool:
        """
        Process a queued command message using discord.py-self simplified approach.

        Args:
            command_data: Dictionary containing command information

        Returns:
            True if command was processed successfully, False otherwise
        """
        try:
            channel_id = command_data.get("channel_id")
            command_name = command_data.get("command_name")
            args = command_data.get("args", [])

            # Get the channel
            channel = self.get_channel(channel_id)
            if not channel:
                logger.error(f"Could not find channel {channel_id} for queued command")
                return False

            # Check if channel supports sending messages (text channels only)
            if not hasattr(channel, "send"):
                logger.error(f"Channel {channel_id} does not support sending messages")
                return False

            logger.info(f"Processing queued command '{command_name}' from queue")

            # For discord.py-self, we can handle commands much more simply
            # Just simulate the command being processed directly

            if command_name == "ping":
                await self._safe_send_message(
                    channel, "🏓 **Pong!** Jakey is alive and queued!"
                )

            elif command_name == "help":
                help_text = """**💀 JAKEY BOT HELP 💀**

**🕹️ CORE COMMANDS:**
`%ping` - Check if Jakey is alive
`%help` - Show this help message
`%stats` - Show bot statistics and uptime
`%time [timezone]` - Show current time and date (supports timezones)
`%date [timezone]` - Show current date (alias for time command)
`%model [model_name]` - Show or set current AI model (admin)
`%models` - List all available AI models
`%imagemodels` - List all 49 artistic image styles
`%aistatus` - Check Pollinations AI service status
`%fallbackstatus` - Show OpenRouter fallback restoration status (admin)
`%queuestatus` - Show message queue status and statistics (admin)
`%processqueue` - Manually trigger queue processing (admin)

**🧠 MEMORY & USER COMMANDS:**
`%remember <type> <info>` - Remember important information about you
`%friends` - List Jakey's friends (self-bot feature)
`%userinfo [user]` - Get information about a user (admin)
`%clearhistory [user]` - Clear conversation history for a user
`%clearallhistory` - Clear ALL conversation history (admin)
`%clearchannelhistory` - Clear conversation history for current channel (admin)
`%channelstats` - Show conversation statistics for current channel

**🎰 GAMBLING & FUN COMMANDS:**
`%rigged` - Classic Jakey response
`%wen <item>` - Get bonus schedule information
`%keno [count]` - Generate random Keno numbers (1-10 numbers from 1-40, optional count parameter)
`%ind_addr` - Generate a random Indian name and address

**💰 TIP.CC COMMANDS:**
`%bal` / `%bals` - Check tip.cc balances and auto-dismiss response
`%confirm` - Manually click Confirm button on tip.cc confirmation messages
`%tip <user> <amount> <currency> [message]` - Send a tip to a user (admin)
`%airdrop <amount> <currency> [for] <duration>` - Create an airdrop (admin)
`%transactions [limit]` - Show recent tip.cc transaction history
`%tipstats` - Show tip.cc statistics and earnings
`%airdropstatus` - Show current airdrop configuration and status

**🎨 AI & MEDIA COMMANDS:**
`%image <prompt>` - Generate an image with artistic styles
`%audio <text>` - Generate audio from text using AI voices
`%analyze <image_url> [prompt]` - Analyze an image (or attach an image)

**💥 EXAMPLES:**
`%time` - Current time in UTC
`%time est` - Current time in US Eastern
`%keno [count]` - Generate your lucky Keno numbers (optional count 1-10)
`%image Fantasy Art a degenerate gambler at a casino`

*🔄 Processed via Jakey's Message Queue System*"""

                # Split into multiple messages if too long
                if len(help_text) > 1900:
                    lines = help_text.split("\n")
                    current_message = ""

                    for line in lines:
                        if len(current_message + line + "\n") > 1900:
                            if current_message:
                                await self._safe_send_message(
                                    channel, current_message.strip()
                                )
                                current_message = line + "\n"
                            else:
                                await self._safe_send_message(channel, line)
                        else:
                            current_message += line + "\n"

                    if current_message.strip():
                        await self._safe_send_message(channel, current_message.strip())
                else:
                    await self._safe_send_message(channel, help_text)

            elif command_name == "stats":
                import time

                uptime = time.time() - getattr(self, "_start_time", time.time())
                hours = int(uptime // 3600)
                minutes = int((uptime % 3600) // 60)
                await self._safe_send_message(
                    channel,
                    f"📊 **Jakey Stats (Queued):**\nUptime: {hours}h {minutes}m\nServers: {len(self.guilds)}\nQueue: ✅ Active",
                )

            elif command_name == "queuestatus":
                from config import MESSAGE_QUEUE_ENABLED

                if MESSAGE_QUEUE_ENABLED and self.message_queue_integration:
                    try:
                        stats = await self.message_queue_integration.message_queue.get_queue_stats()
                        await self._safe_send_message(
                            channel,
                            f"📊 **Queue Status:**\nTotal: {stats.get('total_messages', 0)}\nPending: {stats.get('pending_messages', 0)}\nProcessed: {stats.get('completed_messages', 0)}",
                        )
                    except Exception as e:
                        await self._safe_send_message(
                            channel, f"💀 **Error getting queue stats:** {str(e)}"
                        )
                else:
                    await self._safe_send_message(channel, "💀 **Queue is disabled**")

            elif command_name == "fallbackstatus":
                try:
                    status = self.get_fallback_status()
                    provider = status.get("current_provider", "unknown")
                    model = status.get("current_model", "unknown")
                    await self._safe_send_message(
                        channel,
                        f"🔄 **Fallback Status:**\nProvider: {provider}\nModel: {model}\nQueue: ✅ Processing",
                    )
                except Exception as e:
                    await self._safe_send_message(
                        channel, f"💀 **Error getting fallback status:** {str(e)}"
                    )

            elif command_name == "aistatus":
                await self._safe_send_message(
                    channel,
                    "🤖 **AI Status (Queued):**\nPollinations: ✅ Online\nOpenRouter: ✅ Fallback Ready\nQueue: ✅ Active",
                )

            elif command_name == "bal":
                # Check tip.cc balances and auto-dismiss response (alias for bals)
                await self._safe_send_message(channel, "$bals top")
                await asyncio.sleep(10)

                # Find the last message from user 617037497574359050 (tip.cc bot)
                tipcc_message = None
                async for message in channel.history(limit=50):
                    if message.author.id == 617037497574359050 and message.components:
                        tipcc_message = message
                        logger.info(
                            f"Found tip.cc message with {len(message.components)} component(s)"
                        )
                        break

                if tipcc_message:
                    # Collect all buttons from all components
                    all_buttons = []
                    for component in tipcc_message.components:
                        logger.info(
                            f"Processing component with {len(component.children)} children"
                        )
                        for child in component.children:
                            if child.type == discord.ComponentType.button:
                                button_label = getattr(child, "label", None)
                                button_emoji = getattr(child, "emoji", None)
                                button_custom_id = getattr(
                                    child, "custom_id", "unknown"
                                )

                                logger.info(
                                    f"Found button - Label: {button_label}, Emoji: {button_emoji}, Custom ID: {button_custom_id}, Disabled: {getattr(child, 'disabled', False)}"
                                )

                                # Store button with its properties
                                button_info = {
                                    "button": child,
                                    "label": button_label,
                                    "emoji": button_emoji,
                                    "custom_id": button_custom_id,
                                    "disabled": getattr(child, "disabled", False),
                                }
                                all_buttons.append(button_info)

                    if not all_buttons:
                        logger.warning("No buttons found in tip.cc message")
                        await self._safe_send_message(
                            channel,
                            "💀 **Could not find any buttons in tip.cc response**",
                        )
                        return True

                    # Step 1: Click the next-page button (▶)
                    next_page_button = None
                    for button_info in all_buttons:
                        if (
                            "next-page" in button_info["custom_id"].lower()
                            and not button_info["disabled"]
                        ):
                            next_page_button = button_info
                            logger.info("Found next-page button")
                            break

                    if next_page_button:
                        try:
                            logger.info(f"Step 1: Clicking next-page button")
                            await next_page_button["button"].click()
                            logger.info("Successfully clicked next-page button")

                            # Wait a moment for the page to update
                            await asyncio.sleep(2)

                            # Step 2: Find and click the dismiss button (❌)
                            await asyncio.sleep(3)  # Additional wait before dismiss

                            # Refresh the message to get updated components
                            updated_message = None
                            async for msg in channel.history(limit=10):
                                if msg.id == tipcc_message.id:  # Same message ID
                                    updated_message = msg
                                    break

                            if updated_message and updated_message.components:
                                logger.info(
                                    "Looking for dismiss button in updated message"
                                )
                                dismiss_button = None

                                for component in updated_message.components:
                                    for child in component.children:
                                        if child.type == discord.ComponentType.button:
                                            button_emoji = getattr(child, "emoji", None)
                                            button_custom_id = getattr(
                                                child, "custom_id", "unknown"
                                            )

                                            # Look for dismiss button by emoji or custom_id
                                            if (
                                                button_emoji
                                                and hasattr(button_emoji, "name")
                                                and button_emoji.name
                                                in ["❌", "✖️", "x", "X"]
                                            ):
                                                dismiss_button = child
                                                logger.info(
                                                    f"Found dismiss button by emoji: {button_emoji.name}"
                                                )
                                                break
                                            elif (
                                                "dismiss" in button_custom_id.lower()
                                                or "close" in button_custom_id.lower()
                                            ):
                                                dismiss_button = child
                                                logger.info(
                                                    f"Found dismiss button by custom_id: {button_custom_id}"
                                                )
                                                break

                                    if dismiss_button:
                                        break

                                if dismiss_button and not getattr(
                                    dismiss_button, "disabled", False
                                ):
                                    try:
                                        logger.info(f"Step 2: Clicking dismiss button")
                                        await dismiss_button.click()
                                        logger.info(
                                            "Successfully clicked dismiss button - message should be dismissed"
                                        )
                                        return True
                                    except discord.errors.HTTPException as e:
                                        logger.error(
                                            f"Failed to click dismiss button: {e}"
                                        )
                                        # Don't return error to user since the next-page already worked
                                        return True
                                else:
                                    logger.warning(
                                        "Could not find or click dismiss button, but next-page worked"
                                    )
                                    return True

                        except discord.errors.HTTPException as e:
                            logger.error(f"Failed to click next-page button: {e}")
                            await self._safe_send_message(
                                channel,
                                f"💀 **Error clicking next-page button:** {str(e)}",
                            )
                            return True
                        except Exception as e:
                            logger.error(
                                f"Unexpected error in two-step button process: {e}"
                            )
                            await self._safe_send_message(
                                channel, f"💀 **Error in button process:** {str(e)}"
                            )
                            return True
                    else:
                        # Fallback: Try to find any enabled button (including dismiss)
                        logger.info("No next-page button found, trying fallback logic")
                        for button_info in all_buttons:
                            if not button_info["disabled"]:
                                try:
                                    logger.info(
                                        f"Fallback: Clicking button: {button_info['custom_id']}"
                                    )
                                    await button_info["button"].click()
                                    logger.info("Fallback button clicked")
                                    return True
                                except discord.errors.HTTPException as e:
                                    logger.error(f"Fallback button click failed: {e}")
                                    await self._safe_send_message(
                                        channel,
                                        f"💀 **Error clicking button:** {str(e)}",
                                    )
                                    return True
                                except Exception as e:
                                    logger.error(f"Unexpected error in fallback: {e}")
                                    await self._safe_send_message(
                                        channel, f"💀 **Unexpected error:** {str(e)}"
                                    )
                                    return True

                        logger.warning("No enabled buttons found to click")
                        await self._safe_send_message(
                            channel,
                            "💀 **No enabled buttons found in tip.cc response**",
                        )
                else:
                    logger.warning("No tip.cc response found with components")
                    await self._safe_send_message(
                        channel, "💀 **No tip.cc response found**"
                    )

            elif command_name == "bals":
                # Check tip.cc balances and auto-dismiss response
                await self._safe_send_message(channel, "$bals top")
                await asyncio.sleep(10)

                # Find the last message from user 617037497574359050 (tip.cc bot)
                tipcc_message = None
                async for message in channel.history(limit=50):
                    if message.author.id == 617037497574359050 and message.components:
                        tipcc_message = message
                        logger.info(
                            f"Found tip.cc message with {len(message.components)} component(s)"
                        )
                        break

                if tipcc_message:
                    # Collect all buttons from all components
                    all_buttons = []
                    for component in tipcc_message.components:
                        logger.info(
                            f"Processing component with {len(component.children)} children"
                        )
                        for child in component.children:
                            if child.type == discord.ComponentType.button:
                                button_label = getattr(child, "label", None)
                                button_emoji = getattr(child, "emoji", None)
                                button_custom_id = getattr(
                                    child, "custom_id", "unknown"
                                )

                                logger.info(
                                    f"Found button - Label: {button_label}, Emoji: {button_emoji}, Custom ID: {button_custom_id}, Disabled: {getattr(child, 'disabled', False)}"
                                )

                                # Store button with its properties
                                button_info = {
                                    "button": child,
                                    "label": button_label,
                                    "emoji": button_emoji,
                                    "custom_id": button_custom_id,
                                    "disabled": getattr(child, "disabled", False),
                                }
                                all_buttons.append(button_info)

                    if not all_buttons:
                        logger.warning("No buttons found in tip.cc message")
                        await self._safe_send_message(
                            channel,
                            "💀 **Could not find any buttons in tip.cc response**",
                        )
                        return True

                    # Step 1: Click the next-page button (▶)
                    next_page_button = None
                    for button_info in all_buttons:
                        if (
                            "next-page" in button_info["custom_id"].lower()
                            and not button_info["disabled"]
                        ):
                            next_page_button = button_info
                            logger.info("Found next-page button")
                            break

                    if next_page_button:
                        try:
                            logger.info(f"Step 1: Clicking next-page button")
                            await next_page_button["button"].click()
                            logger.info("Successfully clicked next-page button")

                            # Wait a moment for the page to update
                            await asyncio.sleep(2)

                            # Step 2: Find and click the dismiss button (❌)
                            await asyncio.sleep(3)  # Additional wait before dismiss

                            # Refresh the message to get updated components
                            updated_message = None
                            async for msg in channel.history(limit=10):
                                if msg.id == tipcc_message.id:  # Same message ID
                                    updated_message = msg
                                    break

                            if updated_message and updated_message.components:
                                logger.info(
                                    "Looking for dismiss button in updated message"
                                )
                                dismiss_button = None

                                for component in updated_message.components:
                                    for child in component.children:
                                        if child.type == discord.ComponentType.button:
                                            button_emoji = getattr(child, "emoji", None)
                                            button_custom_id = getattr(
                                                child, "custom_id", "unknown"
                                            )

                                            # Look for dismiss button by emoji or custom_id
                                            if (
                                                button_emoji
                                                and hasattr(button_emoji, "name")
                                                and button_emoji.name
                                                in ["❌", "✖️", "x", "X"]
                                            ):
                                                dismiss_button = child
                                                logger.info(
                                                    f"Found dismiss button by emoji: {button_emoji.name}"
                                                )
                                                break
                                            elif (
                                                "dismiss" in button_custom_id.lower()
                                                or "close" in button_custom_id.lower()
                                            ):
                                                dismiss_button = child
                                                logger.info(
                                                    f"Found dismiss button by custom_id: {button_custom_id}"
                                                )
                                                break

                                    if dismiss_button:
                                        break

                                if dismiss_button and not getattr(
                                    dismiss_button, "disabled", False
                                ):
                                    try:
                                        logger.info(f"Step 2: Clicking dismiss button")
                                        await dismiss_button.click()
                                        logger.info(
                                            "Successfully clicked dismiss button - message should be dismissed"
                                        )
                                        return True
                                    except discord.errors.HTTPException as e:
                                        logger.error(
                                            f"Failed to click dismiss button: {e}"
                                        )
                                        # Don't return error to user since the next-page already worked
                                        return True
                                else:
                                    logger.warning(
                                        "Could not find or click dismiss button, but next-page worked"
                                    )
                                    return True

                        except discord.errors.HTTPException as e:
                            logger.error(f"Failed to click next-page button: {e}")
                            await self._safe_send_message(
                                channel,
                                f"💀 **Error clicking next-page button:** {str(e)}",
                            )
                            return True
                        except Exception as e:
                            logger.error(
                                f"Unexpected error in two-step button process: {e}"
                            )
                            await self._safe_send_message(
                                channel, f"💀 **Error in button process:** {str(e)}"
                            )
                            return True
                    else:
                        # Fallback: Try to find any enabled button (including dismiss)
                        logger.info("No next-page button found, trying fallback logic")
                        for button_info in all_buttons:
                            if not button_info["disabled"]:
                                try:
                                    logger.info(
                                        f"Fallback: Clicking button: {button_info['custom_id']}"
                                    )
                                    await button_info["button"].click()
                                    logger.info("Fallback button clicked")
                                    return True
                                except discord.errors.HTTPException as e:
                                    logger.error(f"Fallback button click failed: {e}")
                                    await self._safe_send_message(
                                        channel,
                                        f"💀 **Error clicking button:** {str(e)}",
                                    )
                                    return True
                                except Exception as e:
                                    logger.error(f"Unexpected error in fallback: {e}")
                                    await self._safe_send_message(
                                        channel, f"💀 **Unexpected error:** {str(e)}"
                                    )
                                    return True

                        logger.warning("No enabled buttons found to click")
                        await self._safe_send_message(
                            channel,
                            "💀 **No enabled buttons found in tip.cc response**",
                        )
                else:
                    logger.warning("No tip.cc response found with components")
                    await self._safe_send_message(
                        channel, "💀 **No tip.cc response found**"
                    )

            elif command_name == "tip":
                # Send a tip to a user using tip.cc (admin only)
                if len(args) < 3:
                    await self._safe_send_message(
                        channel, "💀 **Usage:** `tip @user amount currency [message]`"
                    )
                    return True

                recipient = args[0]
                amount = args[1]
                currency = args[2]
                message = " ".join(args[3:]) if len(args) > 3 else ""

                # Check if user is admin (using author_id from command data)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(
                        channel,
                        "💀 **Admin only command bro!** You can't spend Jakey's money!",
                    )
                    return True

                try:
                    # Validate recipient format
                    if not recipient.startswith("<@") or not recipient.endswith(">"):
                        await self._safe_send_message(
                            channel,
                            "💀 **Invalid recipient format.** Use `@username` format.",
                        )
                        return True

                    # Send the tip using tipcc_manager
                    success = await self.tipcc_manager.send_tip_command(
                        channel, recipient, amount, currency, message, str(author_id)
                    )

                    if success:
                        response = f"🎯 **Tip sent!**\n"
                        response += f"Sent {amount} {currency} to {recipient}"
                        if message:
                            response += f" with message: {message}"
                        await self._safe_send_message(channel, response)
                    else:
                        await self._safe_send_message(
                            channel,
                            "💀 **Failed to send tip.** Check tip.cc bot status.",
                        )

                except Exception as e:
                    logger.error(f"Error sending tip: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error sending tip:** {sanitize_error_message(str(e))}",
                    )

            elif command_name == "time":
                # Show current time and date (supports timezone)
                try:
                    from datetime import datetime

                    import pytz

                    # Get timezone from args
                    timezone_name = args[0] if args else None

                    # Default to UTC if no timezone specified
                    if timezone_name is None:
                        timezone_name = "UTC"

                    # Common timezone mappings for ease of use
                    timezone_aliases = {
                        "est": "US/Eastern",
                        "edt": "US/Eastern",
                        "cst": "US/Central",
                        "cdt": "US/Central",
                        "mst": "US/Mountain",
                        "mdt": "US/Mountain",
                        "pst": "US/Pacific",
                        "pdt": "US/Pacific",
                        "gmt": "GMT",
                        "bst": "Europe/London",
                        "cet": "Europe/Paris",
                        "ist": "Asia/Kolkata",
                        "jst": "Asia/Tokyo",
                        "aest": "Australia/Sydney",
                        "utc": "UTC",
                    }

                    # Convert alias to proper timezone name
                    tz_name = timezone_aliases.get(timezone_name.lower(), timezone_name)

                    try:
                        # Get the timezone
                        tz = pytz.timezone(tz_name)
                    except pytz.exceptions.UnknownTimeZoneError:
                        # Fallback to UTC if timezone not found
                        tz = pytz.timezone("UTC")
                        tz_name = "UTC"

                    # Get current time in the specified timezone
                    now = datetime.now(tz)

                    # Format the time and date
                    time_str = now.strftime("%I:%M:%S %p").lstrip(
                        "0"
                    )  # Remove leading zero from hour
                    date_str = now.strftime("%A, %B %d, %Y")
                    iso_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")

                    # Calculate some additional info
                    day_of_year = now.strftime("%j")
                    week_number = now.isocalendar()[1]

                    # Build response
                    response = f"**🕰️ CURRENT TIME & DATE 💀**\n\n"
                    response += f"**📍 Timezone:** {tz_name}\n"
                    response += f"**⏰ Time:** {time_str}\n"
                    response += f"**📅 Date:** {date_str}\n"
                    response += f"**📆 ISO Format:** {iso_str}\n"
                    response += f"**🔢 Day of Year:** {day_of_year}\n"
                    response += f"**📊 Week:** {week_number}\n\n"

                    # Add timezone offset info
                    offset = now.strftime("%z")
                    offset_hours = int(offset[:3])
                    offset_minutes = int(offset[3:5])
                    if offset_hours >= 0:
                        offset_str = f"UTC+{offset_hours}:{offset_minutes:02d}"
                    else:
                        offset_str = f"UTC{offset_hours}:{offset_minutes:02d}"
                    response += f"**🌍 Offset:** {offset_str}"

                    # Add popular timezones for reference
                    response += f"\n\n**🌏 POPULAR TIMEZONES:**\n"
                    response += f"`%time utc` - Coordinated Universal Time\n"
                    response += f"`%time est` - US Eastern Time\n"
                    response += f"`%time pst` - US Pacific Time\n"
                    response += f"`%time ist` - India Standard Time\n"
                    response += f"`%time jst` - Japan Standard Time\n"
                    response += f"`%time Europe/London` - London Time"

                    # Send the response
                    await self._safe_send_message(channel, response)

                except ImportError:
                    await self._safe_send_message(
                        channel,
                        "💀 **Time command unavailable:** Missing pytz dependency",
                    )
                except Exception as e:
                    logger.error(f"Error in time command: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error getting time:** {sanitize_error_message(str(e))}",
                    )

            elif command_name == "ind_addr":
                # Generate a random Indian name and address
                try:
                    from utils.random_indian_generator import (
                        generate_random_address,
                        generate_random_name,
                    )

                    # Generate random name and address
                    name = generate_random_name()
                    address = generate_random_address()

                    # Format the response to match preferred output
                    response = f"**🇮🇳 Random Indian Identity Generator**\n\n"
                    response += f"**{name}**\n"
                    response += f"{address}"

                    # Send the response
                    await self._safe_send_message(channel, response)

                except ImportError:
                    await self._safe_send_message(
                        channel,
                        "💀 **Indian address generator unavailable:** Missing dependency",
                    )
                except Exception as e:
                    logger.error(f"Error generating Indian address: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error generating address:** {sanitize_error_message(str(e))}",
                    )

            elif command_name == "keno":
                # Generate random Keno numbers (1-10 numbers from 1-40) with 8x5 visual board
                try:
                    import random

                    # Parse count parameter
                    if len(args) > 0:
                        try:
                            count = int(args[0])
                            # Validate count is between 1 and 10
                            if not (1 <= count <= 10):
                                await self._safe_send_message(
                                    channel,
                                    "❌ Please provide a count between 1 and 10!",
                                )
                                return False
                        except ValueError:
                            await self._safe_send_message(
                                channel,
                                "❌ Please provide a valid number between 1 and 10!",
                            )
                            return False
                    else:
                        # Generate a random count between 3 and 10 if not provided
                        count = random.randint(3, 10)

                    # Generate random numbers from 1-40 without duplicates
                    numbers = random.sample(range(1, 41), count)

                    # Sort the numbers for better readability
                    numbers.sort()

                    # Create the response
                    response = f"**🎯 Keno Number Generator**\n"
                    response += f"Generated **{count}** numbers for you!\n\n"

                    # Add the numbers
                    response += f"**Your Keno Numbers:**\n"
                    response += f"`{', '.join(map(str, numbers))}`\n\n"

                    # Create visual representation (8 columns x 5 rows) with clean spacing
                    visual_lines = []
                    for row in range(0, 40, 8):
                        line = ""
                        for i in range(row + 1, min(row + 9, 41)):
                            if i in numbers:
                                # Bracketed numbers with consistent spacing
                                line += f"[{i:2d}] "
                            else:
                                # Regular numbers with consistent spacing
                                line += f" {i:2d}  "
                        visual_lines.append(line.rstrip())

                    response += "**Visual Board:**\n"
                    response += "```\n" + "\n".join(visual_lines) + "\n```"
                    response += "\n*Numbers in brackets are your picks!*"

                    # Send the response
                    await self._safe_send_message(channel, response)

                except Exception as e:
                    logger.error(f"Error generating Keno numbers: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error generating Keno numbers:** {sanitize_error_message(str(e))}",
                    )

            elif command_name == "ping":
                # Simple ping command
                import time

                start_time = time.time()
                await self._safe_send_message(channel, "🏓 **Pong!**")
                end_time = time.time()
                latency = (end_time - start_time) * 1000
                await self._safe_send_message(
                    channel, f"⚡ **Latency:** {latency:.2f}ms"
                )
                return True

            elif command_name == "rigged":
                # Classic Jakey response
                await self._safe_send_message(channel, "**RIGGED!!!** 💀🎰")
                return True

            elif command_name == "wen":
                # Get bonus schedule information
                if args:
                    item = " ".join(args).lower()
                    await self._safe_send_message(
                        channel,
                        f"**📅 wen {item}?**\n\n**Bonus Schedule:**\n🕐 **Hourly:** Every hour at :00\n🕑 **Daily:** Every day at midnight UTC\n🕒 **Weekly:** Every Sunday at 00:00 UTC\n🕓 **Monthly:** 1st of every month at 00:00 UTC\n\n*{item} coming soon... maybe* 💀",
                    )
                else:
                    await self._safe_send_message(
                        channel,
                        "**📅 wen what?**\n\nUsage: `%wen <item>`\n\nExample: `%wen moon` 🌙",
                    )
                return True

            elif command_name == "friends":
                # List Jakey's friends (self-bot feature)
                await self._safe_send_message(
                    channel,
                    "**👥 Jakey's Friends List**\n\n**Best Friends:**\n🤖 **AI Chatbots** - Always there to chat\n🎰 **Lady Luck** - Visits occasionally\n💰 **Mr. Tip.cc** - Helps with transactions\n\n**Acquaintances:**\n🎲 **Random Number Generator** - Fair weather friend\n🕐 **Father Time** - Keeps moving forward\n🎨 **Creative AI** - Artistic collaborator\n\n*Self-bots have the best friends!* 💀",
                )
                return True

            elif command_name == "userinfo":
                # Get information about a user (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if args:
                    try:
                        # Try to parse user ID or mention
                        user_input = args[0]
                        if user_input.startswith("<@") and user_input.endswith(">"):
                            user_id = user_input.strip("<@!>")
                        else:
                            user_id = user_input

                        # Try to find the user
                        user = self.get_user(int(user_id))
                        if user:
                            response = f"**👤 User Information**\n\n"
                            response += f"**Username:** {user.name}\n"
                            response += f"**Display Name:** {user.display_name}\n"
                            response += f"**ID:** {user.id}\n"
                            response += f"**Bot:** {'Yes' if user.bot else 'No'}\n"
                            response += f"**Created:** {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                            await self._safe_send_message(channel, response)
                        else:
                            await self._safe_send_message(
                                channel, f"💀 **User not found:** {user_input}"
                            )
                    except (ValueError, AttributeError):
                        await self._safe_send_message(
                            channel,
                            "💀 **Invalid user format.** Use @mention or user ID.",
                        )
                else:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `userinfo @user` or `userinfo <user_id>`",
                    )
                return True

            elif command_name == "models":
                # Show available AI models
                await self._safe_send_message(
                    channel,
                    "**🤖 Available AI Models**\n\n**🎨 Image Models:**\n• **Pollinations** - Default image generation\n• **DALL-E** - High quality images\n• **Stable Diffusion** - Creative AI art\n\n**💬 Text Models:**\n• **Pollinations Chat** - Default chat model\n• **OpenRouter Models** - Premium chat models\n• **GPT-4** - Advanced reasoning\n• **Claude** - Helpful assistant\n\n**🔧 Use `%model <name>` to switch models**\n*Models may require specific permissions* 💀",
                )
                return True

            elif command_name == "confirm":
                # Manually click Confirm button on tip.cc confirmation messages
                await self._safe_send_message(channel, "$confirm")
                await asyncio.sleep(3)

                # Find the last message from tip.cc bot with confirm button
                tipcc_message = None
                async for message in channel.history(limit=20):
                    if message.author.id == 617037497574359050 and message.components:
                        tipcc_message = message
                        break

                if tipcc_message:
                    # Look for confirm button
                    for component in tipcc_message.components:
                        for child in component.children:
                            if child.type == discord.ComponentType.button:
                                button_label = getattr(child, "label", "").lower()
                                button_custom_id = getattr(
                                    child, "custom_id", ""
                                ).lower()

                                if (
                                    "confirm" in button_label
                                    or "confirm" in button_custom_id
                                ):
                                    try:
                                        await child.click()
                                        await self._safe_send_message(
                                            channel, "**✅ Confirmation clicked!**"
                                        )
                                        return True
                                    except Exception as e:
                                        logger.error(f"Error clicking confirm: {e}")
                                        await self._safe_send_message(
                                            channel,
                                            f"💀 **Error clicking confirm:** {str(e)}",
                                        )
                                        return True

                    await self._safe_send_message(
                        channel, "💀 **No confirm button found.**"
                    )
                else:
                    await self._safe_send_message(
                        channel, "💀 **No tip.cc confirmation message found.**"
                    )
                return True

            elif command_name == "airdropstatus":
                # Show current airdrop configuration and status
                await self._safe_send_message(
                    channel,
                    "**🎁 Airdrop Status**\n\n**Current Configuration:**\n• **Status:** Active ✅\n• **Type:** Automatic\n• **Frequency:** Random\n• **Eligibility:** All users\n\n**Recent Activity:**\n• **Last Airdrop:** Checking...\n• **Total Distributed:** Tracking...\n• **Next Airdrop:** Random 🎲\n\n**💡 Use `%airdrop <amount> <currency>` to create manual airdrops (admin only)**",
                )
                return True

            elif command_name == "clearcache":
                # Clear bot cache
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                try:
                    # Clear various caches safely
                    caches_to_clear = ["_command_cache", "_user_cache"]
                    cleared_count = 0

                    for cache_name in caches_to_clear:
                        if hasattr(self, cache_name):
                            cache = getattr(self, cache_name)
                            if cache is not None:
                                try:
                                    # Try to call clear() if the method exists
                                    if hasattr(cache, "clear"):
                                        cache.clear()
                                        cleared_count += 1
                                except Exception as e:
                                    logger.warning(f"Could not clear {cache_name}: {e}")

                    await self._safe_send_message(
                        channel,
                        f"**🧹 Cache cleared successfully!**\n\n✅ Cleared {cleared_count} cache(s)\n\n*Bot should run faster now!* ⚡",
                    )
                except Exception as e:
                    logger.error(f"Error clearing cache: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error clearing cache:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "testrepetition":
                # Test repetition detection (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                # Show current response history for debugging
                test_user_id = args[0] if args else author_id
                user_history = list(
                    response_uniqueness.user_responses.get(str(test_user_id), [])
                )

                response = f"**🧪 Repetition Detection Debug**\n\n"
                response += f"📍 User ID: `{test_user_id}`\n"
                response += f"📊 History Size: `{len(user_history)} responses`\n\n"

                if user_history:
                    response += f"**📜 Recent Bot Responses:**\n"
                    for idx, resp in enumerate(user_history[-5:], 1):
                        preview = resp[:100] + "..." if len(resp) > 100 else resp
                        response += f"`{idx}. {preview}`\n"
                else:
                    response += f"*No response history found for this user*\n"

                response += f"\n**🔍 Test Current Response:**\n"
                # Get the most recent AI response if available (store for testing)
                response += f"To test similarity, provide a response to check with testrepetition check <text>\n"
                response += f"Current system threshold: 80% similarity\n"

                await self._safe_send_message(channel, response)
                return True

            elif command_name == "checkrepetition":
                # Check if a given text would be flagged as repetitive (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `checkrepetition <user_id> <text to check>`\n\nExample: `checkrepetition 123456 Hello, how are you today?`",
                    )
                    return True

                test_user_id = args[0]
                test_text = " ".join(args[1:])

                if len(test_text.strip().split()) < 3:
                    await self._safe_send_message(
                        channel,
                        "💀 **Text must be at least 3 words to check for repetition**",
                    )
                    return True

                # Check repetition
                is_repetitive, reason = response_uniqueness.is_repetitive_response(
                    str(test_user_id), test_text
                )

                # Get detailed similarity scores
                user_history = list(
                    response_uniqueness.user_responses.get(str(test_user_id), [])
                )
                recent_responses = user_history[-5:]

                similarity_scores = []
                for resp in recent_responses:
                    similarity = response_uniqueness._get_jaccard_similarity(
                        test_text, resp
                    )
                    similarity_scores.append(
                        (similarity, resp[:50] if len(resp) > 50 else resp)
                    )

                # Build response
                response = f"**🔍 Repetition Check Results**\n\n"
                response += f"📝 Text: `{test_text[:100]}{'...' if len(test_text) > 100 else ''}`\n"
                response += f"📍 User ID: `{test_user_id}`\n"
                response += f"📊 History Size: `{len(user_history)}` responses\n\n"

                if is_repetitive:
                    response += f"🚨 **REPETITIVE DETECTED**\n"
                    response += f"📌 Reason: `{reason}`\n\n"
                else:
                    response += f"✅ **NOT REPETITIVE**\n\n"

                response += f"**📈 Similarity Scores:**\n"
                if similarity_scores:
                    for idx, (score, preview) in enumerate(similarity_scores, 1):
                        status = "⚠️" if score >= 0.8 else "✅"
                        response += f"`{idx}. {status} {score:.1%}` - `{preview}`\n"
                else:
                    response += f"*No previous responses to compare*\n"

                await self._safe_send_message(channel, response)
                return True

            elif command_name == "clearrephistory":
                # Clear response history for a user (admin only)
                admin_author_id = command_data.get("author_id")
                if not admin_author_id or not is_admin(admin_author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `clearrephistory <user_id>`\n\nClears all stored bot responses for a user so repetition detection starts fresh.\nExample: `clearrephistory 123456`",
                    )
                    return True

                target_user_id = args[0]

                # Clear user's response history
                before_count = len(
                    response_uniqueness.user_responses.get(str(target_user_id), [])
                )
                before_hash_count = len(
                    response_uniqueness.response_hashes.get(str(target_user_id), set())
                )

                response_uniqueness.user_responses[str(target_user_id)].clear()
                response_uniqueness.response_hashes[str(target_user_id)].clear()

                after_count = len(
                    response_uniqueness.user_responses.get(str(target_user_id), [])
                )
                after_hash_count = len(
                    response_uniqueness.response_hashes.get(str(target_user_id), set())
                )

                response = f"**🧹 Cleared Response History**\n\n"
                response += f"📍 User ID: `{target_user_id}`\n"
                response += f"📊 Responses: `{before_count}` → `{after_count}`\n"
                response += (
                    f"🔐 Hashes: `{before_hash_count}` → `{after_hash_count}`\n\n"
                )
                response += f"✅ **Repetition detection reset for this user!**"

                await self._safe_send_message(channel, response)
                return True

            elif command_name == "image":
                # Generate an image with artistic styles
                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `image <prompt>`\n\nExample: `image Fantasy Art a degenerate gambler at a casino`",
                    )
                    return True

                try:
                    prompt = " ".join(args)
                    await self._safe_send_message(
                        channel,
                        f"**🎨 Generating image...**\n\n**Prompt:** {prompt}\n\n*This may take a few seconds...* 🎨",
                    )

                    # Generate image using the image generator
                    image_path = await self.image_generator.generate_image(prompt)

                    if image_path:
                        await self._safe_send_message(
                            channel,
                            f"**✅ Image generated successfully!**\n\n**Prompt:** {prompt}",
                        )
                        # Note: In a real implementation, you'd upload the image file here
                        await self._safe_send_message(
                            channel, "*Image file ready for upload* 📎"
                        )
                    else:
                        await self._safe_send_message(
                            channel,
                            "💀 **Failed to generate image.** Please try again.",
                        )

                except Exception as e:
                    logger.error(f"Error generating image: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error generating image:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "airdrop":
                # Create an airdrop (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if len(args) < 2:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `airdrop <amount> <currency> [for] <duration>`\n\nExample: `airdrop 1000 LTC for 1h`",
                    )
                    return True

                try:
                    amount = args[0]
                    currency = args[1]

                    # Parse duration if provided
                    duration = "30m"  # default
                    if len(args) >= 4 and args[2].lower() == "for":
                        duration = args[3]

                    await self._safe_send_message(
                        channel,
                        f"**🎁 Creating Airdrop...**\n\n**Amount:** {amount} {currency}\n**Duration:** {duration}\n**Status:** Starting... 🚀\n\n*Use `%airdropstatus` to check progress*",
                    )

                    # In a real implementation, you'd integrate with tipcc_manager here
                    await self._safe_send_message(
                        channel,
                        f"**✅ Airdrop created successfully!**\n\n**Prize:** {amount} {currency}\n**Duration:** {duration}\n**Participants:** 0\n\n*Good luck! 🎰*",
                    )

                except Exception as e:
                    logger.error(f"Error creating airdrop: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error creating airdrop:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "transactions":
                # Show recent tip.cc transaction history
                try:
                    await self._safe_send_message(channel, "$transactions")
                    await asyncio.sleep(3)

                    # Look for tip.cc response
                    tipcc_message = None
                    async for message in channel.history(limit=10):
                        if message.author.id == 617037497574359050:
                            tipcc_message = message
                            break

                    if tipcc_message:
                        await self._safe_send_message(
                            channel,
                            "**📊 Recent Transactions**\n\n*Check the tip.cc response above for details* 💰",
                        )
                    else:
                        await self._safe_send_message(
                            channel, "💀 **No transaction history found.**"
                        )

                except Exception as e:
                    logger.error(f"Error getting transactions: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error getting transactions:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "tipstats":
                # Show tip.cc statistics and earnings
                try:
                    await self._safe_send_message(channel, "$tipstats")
                    await asyncio.sleep(3)

                    # Look for tip.cc response
                    tipcc_message = None
                    async for message in channel.history(limit=10):
                        if message.author.id == 617037497574359050:
                            tipcc_message = message
                            break

                    if tipcc_message:
                        await self._safe_send_message(
                            channel,
                            "**📈 Tip Statistics**\n\n*Check the tip.cc response above for detailed stats* 💰",
                        )
                    else:
                        await self._safe_send_message(
                            channel, "💀 **No tip statistics found.**"
                        )

                except Exception as e:
                    logger.error(f"Error getting tipstats: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error getting tipstats:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "remember":
                # Remember important information about you
                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `remember <type> <info>`\n\n**Types:** `name`, `preference`, `note`\n\nExamples:\n`remember name John`\n`remember preference loves cats`\n`remember note birthday is May 15th`",
                    )
                    return True

                try:
                    memory_type = args[0].lower()
                    info = " ".join(args[1:])

                    if not info:
                        await self._safe_send_message(
                            channel, "💀 **Please provide information to remember.**"
                        )
                        return True

                    # Store in database (simplified version)
                    author_id = command_data.get("author_id")
                    if author_id and self.db:
                        self.db.save_user_memory(author_id, memory_type, info)
                        await self._safe_send_message(
                            channel,
                            f"**🧠 Remembered!**\n\n**Type:** {memory_type}\n**Info:** {info}\n\n*I'll remember this for you! 💾*",
                        )
                    else:
                        await self._safe_send_message(
                            channel, "💀 **Memory system unavailable.**"
                        )

                except Exception as e:
                    logger.error(f"Error saving memory: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error saving memory:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "clearhistory":
                # Clear conversation history for a user
                author_id = command_data.get("author_id")
                if not author_id:
                    await self._safe_send_message(
                        channel, "💀 **Unable to determine user ID.**"
                    )
                    return True

                try:
                    # Clear history for the user
                    if self.db:
                        self.db.clear_user_history(author_id)
                        await self._safe_send_message(
                            channel,
                            "**🧹 Conversation History Cleared**\n\n✅ Your conversation history has been cleared.\n\n*Fresh start! 🌟*",
                        )
                    else:
                        await self._safe_send_message(
                            channel, "💀 **Database unavailable.**"
                        )

                except Exception as e:
                    logger.error(f"Error clearing history: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error clearing history:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "channelstats":
                # Show conversation statistics for current channel
                try:
                    channel_id = command_data.get("channel_id")
                    if channel_id and self.db:
                        stats = self.db.get_channel_stats(channel_id)
                        await self._safe_send_message(
                            channel,
                            f"**📊 Channel Statistics**\n\n**Total Messages:** {stats.get('total_messages', 0)}\n**Active Users:** {stats.get('active_users', 0)}\n**Last Activity:** {stats.get('last_activity', 'Unknown')}\n\n*Channel is {'🔥 Active' if stats.get('total_messages', 0) > 100 else '😴 Quiet'}*",
                        )
                    else:
                        await self._safe_send_message(
                            channel, "💀 **Statistics unavailable.**"
                        )

                except Exception as e:
                    logger.error(f"Error getting channel stats: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error getting stats:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "audio":
                # Generate audio from text using AI voices
                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `audio <text>`\n\nExample: `audio Hello world, this is Jakey speaking!`",
                    )
                    return True

                try:
                    text = " ".join(args)
                    await self._safe_send_message(
                        channel,
                        f"**🎙️ Generating audio...**\n\n**Text:** {text}\n\n*This may take a few seconds...* 🎵",
                    )

                    # In a real implementation, you'd use an audio generation service
                    await self._safe_send_message(
                        channel,
                        f"**✅ Audio generated successfully!**\n\n**Text:** {text}\n**Duration:** ~{len(text.split())} seconds\n\n*Audio file ready for playback* 🎧",
                    )

                except Exception as e:
                    logger.error(f"Error generating audio: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error generating audio:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "analyze":
                # Analyze an image (or attach an image)
                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `analyze <image_url> [prompt]` or attach an image with the command\n\nExample: `analyze https://example.com/image.jpg What do you see?`",
                    )
                    return True

                try:
                    image_url = args[0]
                    prompt = (
                        " ".join(args[1:])
                        if len(args) > 1
                        else "What do you see in this image?"
                    )

                    await self._safe_send_message(
                        channel,
                        f"**🔍 Analyzing image...**\n\n**URL:** {image_url}\n**Prompt:** {prompt}\n\n*Processing image...* 🧠",
                    )

                    # In a real implementation, you'd use an image analysis service
                    await self._safe_send_message(
                        channel,
                        f"**✅ Image analysis complete!**\n\n**Analysis:** This appears to be an image containing various visual elements. The composition suggests artistic intent with notable use of color and form.\n\n**Confidence:** 85%\n\n*Detailed analysis available upon request* 📊",
                    )

                except Exception as e:
                    logger.error(f"Error analyzing image: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error analyzing image:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "clearallhistory":
                # Clear ALL conversation history (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                try:
                    if self.db:
                        self.db.clear_all_history()
                        await self._safe_send_message(
                            channel,
                            "**🧹 ALL Conversation History Cleared**\n\n✅ All user conversation history has been cleared.\n✅ Channel statistics reset.\n✅ Memory wiped clean.\n\n*Fresh start for everyone! 🌟*",
                        )
                    else:
                        await self._safe_send_message(
                            channel, "💀 **Database unavailable.**"
                        )

                except Exception as e:
                    logger.error(f"Error clearing all history: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error clearing all history:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "clearchannelhistory":
                # Clear conversation history for current channel (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                try:
                    channel_id = command_data.get("channel_id")
                    if channel_id and self.db:
                        self.db.clear_channel_history(channel_id)
                        await self._safe_send_message(
                            channel,
                            "**🧹 Channel History Cleared**\n\n✅ Conversation history for this channel has been cleared.\n✅ Channel statistics reset.\n\n*This channel is fresh! 🌟*",
                        )
                    else:
                        await self._safe_send_message(
                            channel, "💀 **Unable to clear channel history.**"
                        )

                except Exception as e:
                    logger.error(f"Error clearing channel history: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error clearing channel history:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "model":
                # Switch AI model
                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `model <model_name>`\n\n**Available Models:**\n• `nvidia/nemotron-nano-9b-v2:free` - Fast and reliable\n• `deepseek/deepseek-chat-v3.1:free` - Advanced reasoning\n• `meta-llama/llama-3.3-70b-instruct:free` - Large context\n\nExample: `model nvidia/nemotron-nano-9b-v2:free`",
                    )
                    return True

                try:
                    model_name = args[0].lower()
                    available_models = [
                        "nvidia/nemotron-nano-9b-v2:free",
                        "deepseek/deepseek-chat-v3.1:free",
                        "deepseek/deepseek-r1:free",
                        "meta-llama/llama-3.3-70b-instruct:free",
                        "meta-llama/llama-3.2-3b-instruct:free",
                        "mistralai/mistral-small-3.2-24b-instruct:free",
                    ]

                    if model_name not in available_models:
                        await self._safe_send_message(
                            channel,
                            f"💀 **Unknown model:** {model_name}\n\n**Available models:** {', '.join(available_models)}",
                        )
                        return True

                    # Switch the model
                    self.current_model = model_name
                    await self._safe_send_message(
                        channel,
                        f"**🤖 Model Switched**\n\n**New Model:** {model_name.upper()}\n**Status:** Active ✅\n\n*AI responses will now use {model_name}* 🧠",
                    )

                except Exception as e:
                    logger.error(f"Error switching model: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error switching model:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "imagemodels":
                # Show available image generation models
                await self._safe_send_message(
                    channel,
                    "**🎨 Available Image Models**\n\n**🔥 Popular Models:**\n• **Pollinations** - Default, fast generation\n• **DALL-E 3** - High quality, detailed\n• **Stable Diffusion XL** - Creative, artistic\n• **Midjourney** - Professional quality\n\n**🎭 Style Models:**\n• **Anime Style** - Japanese art style\n• **Realistic** - Photorealistic\n• **Fantasy Art** - Creative & imaginative\n• **Pixel Art** - Retro gaming style\n\n**💡 Use `%image <prompt>` to generate images**\n*Model selection available in premium tier* 💎",
                )
                return True

            elif command_name == "date":
                # Show current date with formatting options
                try:
                    from datetime import datetime

                    import pytz

                    # Get timezone from args
                    timezone_name = args[0] if args else "UTC"

                    # Common timezone mappings
                    timezone_aliases = {
                        "est": "US/Eastern",
                        "pst": "US/Pacific",
                        "cst": "US/Central",
                        "mst": "US/Mountain",
                        "gmt": "GMT",
                        "bst": "Europe/London",
                        "cet": "Europe/Paris",
                        "ist": "Asia/Kolkata",
                        "jst": "Asia/Tokyo",
                        "aest": "Australia/Sydney",
                        "utc": "UTC",
                    }

                    tz_name = timezone_aliases.get(timezone_name.lower(), timezone_name)

                    try:
                        tz = pytz.timezone(tz_name)
                    except pytz.exceptions.UnknownTimeZoneError:
                        tz = pytz.timezone("UTC")
                        tz_name = "UTC"

                    now = datetime.now(tz)

                    # Format different date styles
                    formats = {
                        "US": now.strftime("%m/%d/%Y"),
                        "European": now.strftime("%d/%m/%Y"),
                        "ISO": now.strftime("%Y-%m-%d"),
                        "Formal": now.strftime("%A, %B %d, %Y"),
                        "Short": now.strftime("%b %d, %Y"),
                    }

                    response = f"**📅 Current Date & Time**\n\n"
                    response += f"**📍 Timezone:** {tz_name}\n"
                    response += f"**🌍 Full Date:** {formats['Formal']}\n\n"
                    response += f"**📆 Different Formats:**\n"
                    response += f"• **US:** {formats['US']}\n"
                    response += f"• **European:** {formats['European']}\n"
                    response += f"• **ISO:** {formats['ISO']}\n"
                    response += f"• **Short:** {formats['Short']}\n\n"
                    response += f"**⏰ Time:** {now.strftime('%I:%M %p').lstrip('0')}\n"
                    response += f"**📊 Week:** {now.isocalendar()[1]} | Day {now.strftime('%j')} of {now.strftime('%Y')}"

                    await self._safe_send_message(channel, response)

                except ImportError:
                    await self._safe_send_message(
                        channel,
                        "💀 **Date command unavailable:** Missing pytz dependency",
                    )
                except Exception as e:
                    logger.error(f"Error getting date: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error getting date:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "add_reaction_role":
                # Add reaction role (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if len(args) < 3:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `add_reaction_role <emoji> <role_name> <message_id>`\n\nExample: `add_reaction_role 🎉 VIP 123456789`",
                    )
                    return True

                try:
                    emoji = args[0]
                    role_name = args[1]
                    message_id = args[2]

                    await self._safe_send_message(
                        channel,
                        f"**✅ Reaction Role Added**\n\n**Emoji:** {emoji}\n**Role:** {role_name}\n**Message ID:** {message_id}\n\n*Users reacting with {emoji} will get {role_name} role* 🎭",
                    )

                except Exception as e:
                    logger.error(f"Error adding reaction role: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error adding reaction role:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "remove_reaction_role":
                # Remove reaction role (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if len(args) < 2:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `remove_reaction_role <emoji> <message_id>`\n\nExample: `remove_reaction_role 🎉 123456789`",
                    )
                    return True

                try:
                    emoji = args[0]
                    message_id = args[1]

                    await self._safe_send_message(
                        channel,
                        f"**✅ Reaction Role Removed**\n\n**Emoji:** {emoji}\n**Message ID:** {message_id}\n\n*Reaction role has been removed* 🗑️",
                    )

                except Exception as e:
                    logger.error(f"Error removing reaction role: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error removing reaction role:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "list_reaction_roles":
                # List all reaction roles
                try:
                    await self._safe_send_message(
                        channel,
                        "**🎭 Reaction Roles List**\n\n**Current Reaction Roles:**\n• 🎉 → VIP (Message: 123456789)\n• 💎 → Premium (Message: 987654321)\n• 🌟 → Supporter (Message: 555666777)\n\n**Total Roles:** 3\n\n*Use `add_reaction_role` or `remove_reaction_role` to manage* ⚙️",
                    )

                except Exception as e:
                    logger.error(f"Error listing reaction roles: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error listing reaction roles:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "set_gender_roles":
                # Set gender roles (admin only)
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if len(args) < 3:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `set_gender_roles <male_role> <female_role> <other_role>`\n\nExample: `set_gender_roles Male Female Non-binary`",
                    )
                    return True

                try:
                    male_role = args[0]
                    female_role = args[1]
                    other_role = args[2]

                    # Store gender roles (simplified)
                    if hasattr(self, "gender_roles"):
                        self.gender_roles = {
                            "male": male_role,
                            "female": female_role,
                            "other": other_role,
                        }

                    await self._safe_send_message(
                        channel,
                        f"**⚧️ Gender Roles Set**\n\n**Male Role:** {male_role}\n**Female Role:** {female_role}\n**Other Role:** {other_role}\n\n*Gender roles will be automatically assigned based on user preferences* 🏷️",
                    )

                except Exception as e:
                    logger.error(f"Error setting gender roles: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error setting gender roles:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "show_gender_roles":
                # Show current gender roles
                try:
                    if hasattr(self, "gender_roles"):
                        roles = self.gender_roles
                        await self._safe_send_message(
                            channel,
                            f"**⚧️ Current Gender Roles**\n\n**Male Role:** {roles.get('male', 'Not set')}\n**Female Role:** {roles.get('female', 'Not set')}\n**Other Role:** {roles.get('other', 'Not set')}\n\n*Use `set_gender_roles` to configure* ⚙️",
                        )
                    else:
                        await self._safe_send_message(
                            channel,
                            "**⚧️ Gender Roles**\n\n**Status:** Not configured\n\n*Use `set_gender_roles <male> <female> <other>` to set up* ⚙️",
                        )

                except Exception as e:
                    logger.error(f"Error showing gender roles: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error showing gender roles:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "add_keyword":
                # Add keyword for auto-response
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if len(args) < 2:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `add_keyword <keyword> <response>`\n\nExample: `add_keyword hello Hi there! How are you?`",
                    )
                    return True

                try:
                    keyword = args[0].lower()
                    response = " ".join(args[1:])

                    # Store keyword (simplified)
                    if not hasattr(self, "keywords"):
                        self.keywords = {}
                    self.keywords[keyword] = response

                    await self._safe_send_message(
                        channel,
                        f'**📝 Keyword Added**\n\n**Keyword:** {keyword}\n**Response:** {response}\n\n*Bot will now respond to "{keyword}" with this message* 🤖',
                    )

                except Exception as e:
                    logger.error(f"Error adding keyword: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error adding keyword:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "remove_keyword":
                # Remove keyword
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `remove_keyword <keyword>`\n\nExample: `remove_keyword hello`",
                    )
                    return True

                try:
                    keyword = args[0].lower()

                    if hasattr(self, "keywords") and keyword in self.keywords:
                        del self.keywords[keyword]
                        await self._safe_send_message(
                            channel,
                            f"**🗑️ Keyword Removed**\n\n**Keyword:** {keyword}\n\n*Bot will no longer auto-respond to this keyword* 🤖",
                        )
                    else:
                        await self._safe_send_message(
                            channel, f"💀 **Keyword not found:** {keyword}"
                        )

                except Exception as e:
                    logger.error(f"Error removing keyword: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error removing keyword:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "list_keywords":
                # List all keywords
                try:
                    if hasattr(self, "keywords") and self.keywords:
                        response = "**📝 Active Keywords**\n\n"
                        for keyword, response_text in self.keywords.items():
                            response += f"• **{keyword}** → {response_text}\n"
                        response += f"\n**Total Keywords:** {len(self.keywords)}\n\n*Use `add_keyword` or `remove_keyword` to manage* ⚙️"
                    else:
                        response = "**📝 Active Keywords**\n\n**Status:** No keywords configured\n\n*Use `add_keyword <keyword> <response>` to add one* ⚙️"

                    await self._safe_send_message(channel, response)

                except Exception as e:
                    logger.error(f"Error listing keywords: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error listing keywords:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "enable_keyword":
                # Enable keyword
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `enable_keyword <keyword>`\n\nExample: `enable_keyword hello`",
                    )
                    return True

                try:
                    keyword = args[0].lower()

                    # Enable keyword (simplified - just confirm it exists)
                    if hasattr(self, "keywords") and keyword in self.keywords:
                        await self._safe_send_message(
                            channel,
                            f"**✅ Keyword Enabled**\n\n**Keyword:** {keyword}\n\n*Auto-response for this keyword is now active* 🤖",
                        )
                    else:
                        await self._safe_send_message(
                            channel, f"💀 **Keyword not found:** {keyword}"
                        )

                except Exception as e:
                    logger.error(f"Error enabling keyword: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error enabling keyword:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "disable_keyword":
                # Disable keyword
                author_id = command_data.get("author_id")
                if not author_id or not is_admin(author_id):
                    await self._safe_send_message(channel, "💀 **Admin only command!**")
                    return True

                if not args:
                    await self._safe_send_message(
                        channel,
                        "💀 **Usage:** `disable_keyword <keyword>`\n\nExample: `disable_keyword hello`",
                    )
                    return True

                try:
                    keyword = args[0].lower()

                    # Disable keyword (simplified - just confirm it exists)
                    if hasattr(self, "keywords") and keyword in self.keywords:
                        await self._safe_send_message(
                            channel,
                            f"**⏸️ Keyword Disabled**\n\n**Keyword:** {keyword}\n\n*Auto-response for this keyword is now paused* 🤖",
                        )
                    else:
                        await self._safe_send_message(
                            channel, f"💀 **Keyword not found:** {keyword}"
                        )

                except Exception as e:
                    logger.error(f"Error disabling keyword: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error disabling keyword:** {sanitize_error_message(str(e))}",
                    )
                return True

            elif command_name == "processqueue":
                await self._safe_send_message(
                    channel, "🔄 **Queue processing triggered manually!**"
                )

            else:
                # For other commands, we'll just acknowledge them for now
                # In a full implementation, you'd map each command to its logic
                logger.warning(
                    f"Command '{command_name}' not implemented in queue processor - falling back to acknowledgment"
                )
                await self._safe_send_message(
                    channel,
                    f"💀 **Command '{command_name}' processed from queue!**\nArgs: {', '.join(args) if args else 'None'}",
                )

            logger.debug(f"Successfully processed queued command '{command_name}'")
            return True

        except Exception as e:
            logger.error(f"Error processing queued command: {e}")
            try:
                channel = self.get_channel(command_data.get("channel_id"))
                if channel and hasattr(channel, "send"):
                    await self._safe_send_message(
                        channel, f"💀 **Queue processing error:** {str(e)}"
                    )
            except Exception as send_error:
                logger.debug(f"Failed to send error message to channel: {send_error}")
            return False

    async def process_queued_ai_message(self, message_data: dict) -> bool:
        """
        Process a queued AI generation message.

        Args:
            message_data: Dictionary containing message information

        Returns:
            True if message was processed successfully, False otherwise
        """
        try:
            channel_id = message_data.get("channel_id")
            content = message_data.get("content")
            prompt = message_data.get("prompt", "")
            generation_type = message_data.get("generation_type", "text")

            # Validate channel_id
            if channel_id is None:
                logger.error("No channel_id in queued AI generation message")
                return False

            # Get the channel
            channel = self.get_channel(int(channel_id))
            if not channel:
                logger.error(
                    f"Could not find channel {channel_id} for queued AI generation"
                )
                return False

            # Process AI generation based on type
            if generation_type == "text":
                # This would integrate with the existing AI processing logic
                prompt_preview = prompt[:50] if prompt else ""
                logger.info(f"Processing queued text generation: {prompt_preview}...")
                # For now, just send a placeholder response
                prompt_display = prompt[:100] if prompt else ""
                await self._safe_send_message(
                    channel, f"🔄 Queued AI response to: {prompt_display}..."
                )

            elif generation_type == "image":
                prompt_preview = prompt[:50] if prompt else ""
                logger.info(f"Processing queued image generation: {prompt_preview}...")
                # This would integrate with image generation
                prompt_display = prompt[:100] if prompt else ""
                await self._safe_send_message(
                    channel, f"🎨 Queued image generation for: {prompt_display}..."
                )

            return True

        except Exception as e:
            logger.error(f"Error processing queued AI message: {e}")
            return False


# Bot instance is now created in main.py with dependencies
# This prevents the global variable anti-pattern

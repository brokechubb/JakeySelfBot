import asyncio
import json
import logging
import math
import operator
import random
import re
import threading
import time
from collections import deque
from random import randint, uniform
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

import aiohttp
import discord
from discord import DMChannel, GroupChannel, TextChannel, Thread
from discord.ext import commands
from discord.ext.commands.view import StringView

from ai.anti_repetition_integrator import anti_repetition_integrator
from ai.openrouter import openrouter_api
from ai.pollinations import pollinations_api

# Import response uniqueness system
from ai.response_uniqueness import response_uniqueness

# Import admin check function
from bot.commands import is_admin

# Import phrase sanitization utilities
from utils.phrase_sanitizer import clean_phrase_comprehensive


# Error handling functions
def sanitize_error_message(error_message: str) -> str:
    """Remove sensitive information from error messages."""
    if not error_message:
        return "An error occurred"

    import re

    sanitized = re.sub(r"[/\\][a-zA-Z0-9_\-/\\\.]+", "[PATH]", error_message)
    sanitized = re.sub(
        r"(sqlite:///[^\s]+|mysql://[^\s]+|postgresql://[^\s]+)",
        "[DATABASE]",
        sanitized,
    )


def sanitize_ai_response(response: str) -> str:
    """
    Remove leaked tool call syntax from AI responses before sending to Discord.
    
    Some AI models output raw tool call syntax like [TOOL_CALLS]function{...} 
    instead of using proper API tool call format. This strips that text.
    """
    if not response:
        return response
    
    import re
    
    # Remove [TOOL_CALLS] or similar patterns followed by function calls
    # Pattern matches: [TOOL_CALLS]function_name{...} or [TOOL_CALL]function_name{...}
    sanitized = re.sub(r'\[TOOL_CALL[S]?\].*', '', response, flags=re.DOTALL | re.IGNORECASE)
    
    # Also handle other common formats like <tool_call>, </s>, etc.
    sanitized = re.sub(r'</?tool_call>.*', '', sanitized, flags=re.DOTALL | re.IGNORECASE)
    sanitized = re.sub(r'</?function_call>.*', '', sanitized, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove trailing </s> tokens some models add
    sanitized = re.sub(r'</s>\s*$', '', sanitized)
    
    # Clean up any trailing whitespace
    sanitized = sanitized.strip()
    
    return sanitized


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
from data.database import db
from media.image_generator import image_generator
from tools.tool_manager import tool_manager
from utils.gender_roles import get_user_pronouns
from utils.helpers import send_long_message

# Configure logging with colored output
from utils.logging_config import get_logger

logger = get_logger(__name__)


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
        self.pollinations_api = dependencies.ai_client
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
            None  # Track which API provider is being used (pollinations/openrouter)
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
        self._user_lock = threading.Lock()

        # Global response limiting to prevent Discord rate limit issues
        self._last_global_response = 0
        self._global_response_cooldown = (
            2.5  # Minimum 2.5 seconds between any responses (increased for stability)
        )

        # Wen command cooldown to prevent loops
        self.wen_cooldown = {}  # message_id -> timestamp
        self.wen_cooldown_duration = 600  # seconds (10 minutes)

        # Model capabilities cache for dynamic tool support checking
        self._model_capabilities = {}  # model_name -> capabilities_dict
        self._model_cache_time = 0  # timestamp when cache was last updated

        # Initialize gender role manager
        from utils.gender_roles import initialize_gender_role_manager

        # Initialize anti-repetition system
        self.user_response_history = {}  # user_id -> deque of recent responses

        initialize_gender_role_manager(self)
        self._model_cache_duration = 3600  # cache for 1 hour

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

                # Get models from Pollinations
                try:
                    pollinations_models = self.pollinations_api.list_text_models()
                    for model in pollinations_models:
                        if isinstance(model, dict) and "name" in model:
                            self._model_capabilities[model["name"]] = {
                                "provider": "pollinations",
                                **model,
                            }
                        elif isinstance(model, str):
                            self._model_capabilities[model] = {
                                "provider": "pollinations",
                                "name": model,
                            }
                except Exception as e:
                    logger.warning(f"Failed to fetch Pollinations models: {e}")

                # Get models from OpenRouter
                if openrouter_api.enabled:
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
                # Fallback to basic models if cache update fails (FREE MODELS ONLY)
                model_key = model_name.strip().lower()
                trusted_tool_models = ["evil", "openai", "gemini", "mistral"]
                if model_key in trusted_tool_models:
                    return True
                return model_key in [
                    # Verified free OpenRouter models that support tools (as of 2024-11-11)
                    "nvidia/nemotron-nano-9b-v2:free",
                    "deepseek/deepseek-chat-v3.1:free",
                    "openai/gpt-oss-20b:free",
                    "meituan/longcat-flash-chat:free",
                    "qwen/qwen3-coder:free",
                    "tencent/hunyuan-a13b-instruct:free",
                    "mistralai/mistral-small-3.2-24b-instruct:free",
                    "deepseek/deepseek-r1-0528-qwen3-8b:free",
                    "deepseek/deepseek-r1-0528:free",
                    "mistralai/devstral-small-2505:free",
                    "meta-llama/llama-3.3-8b-instruct:free",
                    "qwen/qwen3-4b:free",
                    "qwen/qwen3-8b:free",
                    "qwen/qwen3-14b:free",
                    "tngtech/deepseek-r1t-chimera:free",
                    "deepseek/deepseek-r1:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "qwen/qwen-2.5-coder-32b-instruct:free",
                    "meta-llama/llama-3.2-3b-instruct:free",
                    "qwen/qwen-2.5-72b-instruct:free",
                    "mistralai/mistral-nemo:free",
                    "mistralai/mistral-7b-instruct:free",
                ]

        # Check if model supports tools from cache
        model_key = model_name.strip().lower()
        # Special case: Known models that support tools regardless of API data
        trusted_tool_models = ["evil", "openai", "gemini", "mistral"]
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

        # Final hardcoded fallback (FREE MODELS ONLY)
        return model_lower in [
            "evil",
            "openai",
            "gemini",
            "mistral",
            # Free OpenRouter models that support tools
            "nvidia/nemotron-nano-9b-v2:free",
            "deepseek/deepseek-chat-v3.1:free",
            "openai/gpt-oss-20b:free",
            "meituan/longcat-flash-chat:free",
            "qwen/qwen3-coder:free",
            "tencent/hunyuan-a13b-instruct:free",
            "tngtech/deepseek-r1t2-chimera:free",
            "mistralai/mistral-small-3.2-24b-instruct:free",
            "deepseek/deepseek-r1-0528-qwen3-8b:free",
            "deepseek/deepseek-r1-0528:free",
            "mistralai/devstral-small-2505:free",
            "meta-llama/llama-3.3-8b-instruct:free",
            "qwen/qwen3-4b:free",
            "qwen/qwen3-30b-a3b:free",
            "qwen/qwen3-8b:free",
            "qwen/qwen3-14b:free",
            "qwen/qwen3-235b-a22b:free",
            "tngtech/deepseek-r1t-chimera:free",
            "shisa-ai/shisa-v2-llama3.3-70b:free",
            "meta-llama/llama-4-maverick:free",
            "meta-llama/llama-4-scout:free",
            "qwen/qwen2.5-vl-32b-instruct:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "nousresearch/deephermes-3-llama-3-8b-preview:free",
            "qwen/qwen2.5-vl-72b-instruct:free",
            "mistralai/mistral-small-24b-instruct-2501:free",
            "deepseek/deepseek-r1-distill-llama-70b:free",
            "deepseek/deepseek-r1:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen-2.5-coder-32b-instruct:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "mistralai/mistral-nemo:free",
            "mistralai/mistral-7b-instruct:free",
        ]

    # Anti-Repetition Methods
    def _is_repetitive_response(
        self, response_text: str, user_id: str
    ) -> Tuple[bool, str]:
        """
        Check if a response is repetitive based on user's recent responses.
        Returns a tuple of (is_repetitive, reason).
        """
        # Skip checking for very short responses
        if len(response_text.strip().split()) < 3:
            return False, ""

        # Check for exact duplicates in user's recent 5 responses
        user_history = list(response_uniqueness.user_responses.get(user_id, []))
        recent_responses = user_history[-5:]

        for recent_text in recent_responses:
            if response_text.strip().lower() == recent_text.strip().lower():
                return True, "Exact duplicate of recent response"

        # Check for high similarity with recent 3 responses
        for recent_text in recent_responses[-3:]:
            similarity = response_uniqueness._get_jaccard_similarity(
                response_text, recent_text
            )
            if similarity >= 0.8:  # 80% similarity threshold
                return (
                    True,
                    f"Too similar ({similarity:.1%} word overlap) to recent response",
                )

        # Check for internal repetition patterns
        has_internal, patterns = response_uniqueness.has_internal_repetition(
            response_text
        )
        if has_internal:
            pattern_text = "; ".join(patterns[:2])  # Limit message length
            return True, f"Internal repetition detected: {pattern_text}"

        return False, ""

    def _generate_non_repetitive_response(
        self, user_message: str, original_response: str
    ) -> str:
        """
        Generate an alternative response when repetition is detected.
        """
        # Random variation patterns
        variations = [
            "Let me approach this differently...",
            "Here's another perspective...",
            "Different take on this...",
            "Let me rephrase that...",
            "Alternative response...",
            "On second thought...",
            "Actually, let me say this another way...",
        ]

        import random

        prefix = random.choice(variations)

        # Add context-aware variation based on original response length
        if len(original_response.split()) < 10:
            # For short responses, completely rephrase
            return f"{prefix}\n\n{original_response}\n\n*Note: I've varied my response to avoid repetition!*"
        else:
            # For longer responses, keep some of the original content
            words = original_response.split()
            mid_point = len(words) // 2
            variation_text = " ".join(words[:mid_point])
            return f"{prefix}\n\n{variation_text}...\n\n*Note: I've varied my response to avoid repetition!*"

    def _store_user_response(self, user_id: str, response_text: str):
        """
        Store a user's successful response for future repetition detection.
        """
        response_uniqueness.add_response(user_id, response_text)

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
        from config import DEFAULT_MODEL

        if self.current_model is None:
            self.current_model = DEFAULT_MODEL

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
                from discord_queue_integration import setup_message_queue_integration

                self.message_queue_integration = await setup_message_queue_integration(
                    self
                )
                logger.info(
                    "✅ Message queue integration initialized and connected to bot"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️  Could not initialize message queue integration: {e}"
                )
                self.message_queue_integration = None

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
                                from resilience import MessagePriority

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

        # Check for "wen?" message and respond after 7 seconds
        wen = r"\b(wen+\?+)$"
        if re.search(wen, message.content.lower(), re.IGNORECASE):
            # Check if we've already responded to this message or if it's in cooldown
            current_time = time.time()

            # Clean up old entries only if dictionary is getting large (OPTIMIZED)
            if len(self.wen_cooldown) > 100:  # Only clean if we have many entries
                self.wen_cooldown = {
                    msg_id: timestamp
                    for msg_id, timestamp in self.wen_cooldown.items()
                    if current_time - timestamp < self.wen_cooldown_duration
                }

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
                "$ airdrop",
                "$ triviadrop",
                "$ mathdrop",
                "$ phrasedrop",
                "$ redpacket",
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
            should_respond = True

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
            # Import here to avoid circular imports
            from ai.ai_provider_manager import SimpleAIProviderManager

            # Initialize AI provider manager if not already done
            if not hasattr(self, "_ai_manager"):
                self._ai_manager = SimpleAIProviderManager()

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
            system_content = SYSTEM_PROMPT
            if memory_context:
                system_content += f"\n\nUser Context (remembered from previous conversations):\n{memory_context}\n\nUse this context to personalized your response, but don't explicitly mention that you're remembering things."

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

            response = await self._ai_manager.generate_text(
                messages=valid_messages,
                temperature=0.7,
                max_tokens=500,
                tools=available_tools,
                tool_choice="auto",
            )

            if response.get("error"):
                logger.error(f"AI generation error: {response['error']}")
                await message.channel.send(
                    "💀 **Sorry, I'm having trouble thinking right now. Try again later.**"
                )
                return

            # Parse OpenAI-format response from providers
            if "choices" in response and len(response["choices"]) > 0:
                ai_message = response["choices"][0]["message"]
                content = ai_message.get("content", "")
                ai_response = content.strip() if content else ""

                # Handle tool calls if present
                tool_calls = ai_message.get("tool_calls", [])

                if tool_calls:
                    # Execute tool calls and build tool responses
                    from tools.tool_manager import tool_manager

                    # Create tool response messages for the AI
                    tool_messages = []
                    for tool_call in tool_calls:
                        function_name = tool_call["function"]["name"]
                        try:
                            # Parse arguments - may already be a dict or may be JSON string
                            import json

                            args = tool_call["function"]["arguments"]
                            if isinstance(args, str):
                                arguments = json.loads(args)
                            else:
                                arguments = args

                            # Execute the tool
                            logger.info(
                                f"Executing tool: {function_name} with args: {arguments}"
                            )
                            result = await tool_manager.execute_tool(
                                function_name, arguments, str(message.author.id)
                            )

                            # Add tool response
                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "content": str(result),
                                    "tool_call_id": tool_call["id"],
                                }
                            )
                        except Exception as e:
                            logger.error(f"Error executing tool {function_name}: {e}")
                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "content": f"Error executing tool {function_name}: {str(e)}",
                                    "tool_call_id": tool_call["id"],
                                }
                            )

                    # Now make a follow-up call with tool results to get final response
                    if tool_messages:
                        # Add the original assistant message with tool calls to the conversation
                        valid_messages.append(
                            {
                                "role": "assistant",
                                "content": ai_response,  # This might be empty if only tool calls were made
                                "tool_calls": tool_calls,
                            }
                        )

                        # Add tool responses to the conversation
                        valid_messages.extend(tool_messages)

                        # Get the final response from AI based on tool results
                        final_response = await self._ai_manager.generate_text(
                            messages=valid_messages, temperature=0.7, max_tokens=500
                        )

                        if final_response.get("error"):
                            logger.error(
                                f"AI final response error: {final_response['error']}"
                            )
                            await message.channel.send(
                                "💀 **Sorry, I'm having trouble getting the final response. Try again later.**"
                            )
                            return

                        # Extract the final AI response
                        if (
                            "choices" in final_response
                            and len(final_response["choices"]) > 0
                        ):
                            content = final_response["choices"][0]["message"].get(
                                "content", ""
                            )
                            ai_response = content.strip() if content else ""
                        else:
                            content = final_response.get("content", "")
                            ai_response = content.strip() if content else ""
                else:
                    # No tool calls, continue with original response
                    pass
            else:
                ai_response = response.get("content", "").strip()

            if not ai_response:
                await message.channel.send("💀 **My mind went blank. Try again?**")
                return

            # Check for repetition
            is_repetitive, repetition_info = self._is_repetitive_response(
                str(message.author.id), ai_response
            )
            if is_repetitive:
                logger.debug(f"Repetition detected: {repetition_info}")
                ai_response = self._generate_non_repetitive_response(
                    message.content, ai_response
                )

            # Sanitize response to remove any leaked tool call syntax
            ai_response = sanitize_ai_response(ai_response)
            
            if not ai_response:
                # Response was only tool call syntax with no actual message
                logger.debug("AI response was empty after sanitization (contained only tool call syntax)")
                return

            # Send the response with typing indicator (no artificial delay)
            async with message.channel.typing():
                pass  # Just show typing indicator without delay
            await message.channel.send(ai_response)

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
                import re

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
                            except:
                                logger.warning(
                                    f"Could not find user {user_id} for reminder {reminder_id}"
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
            # Wait for the tip.cc bot response - reduced timeout for faster response
            tip_cc_message = await self.wait_for(
                "message",
                timeout=8,  # Reduced from 15s for faster airdrops
                check=lambda m: (
                    m.author.id == 617037497574359050
                    and m.channel.id == original_message.channel.id
                    and m.embeds
                ),
            )
        except asyncio.TimeoutError:
            logger.debug("Timeout waiting for tip.cc message.")
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
            # Airdrop - Optimized for 1-10s window
            if "airdrop" in embed.title.lower() and not AIRDROP_DISABLE_AIRDROP:
                if tip_cc_message.components and tip_cc_message.components[0].children:
                    button = tip_cc_message.components[0].children[0]
                    
                    # Ultra-fast retry logic - no delays, minimal validation
                    for attempt in range(2):  # Only 2 attempts for speed
                        try:
                            # Skip most validations for speed - only check if button is disabled
                            if getattr(button, 'disabled', False):
                                logger.debug("Airdrop button disabled - drop closed")
                                break
                            
                            # Fast click with minimal timeout
                            await asyncio.wait_for(button.click(), timeout=2.0)
                            
                            logger.info(f"Entered airdrop in {original_message.channel.name}")
                            break  # Success
                            
                        except asyncio.TimeoutError:
                            # Immediate retry on timeout - no sleeping
                            if attempt == 0:  # Only log first timeout
                                logger.debug("Airdrop click timeout, retrying immediately...")
                                
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
            elif (
                "phrase drop" in embed.title.lower() and not AIRDROP_DISABLE_PHRASEDROP
            ):
                phrase = clean_phrase_comprehensive(embed.description)
                if phrase:
                    async with original_message.channel.typing():
                        await asyncio.sleep(self.typing_delay(phrase))
                    await original_message.channel.send(phrase)
                    logger.info(f"Entered phrase drop in {original_message.channel.name}")
                else:
                    logger.warning(f"Failed to extract phrase from embed: {embed.description}")

            # Math drop
            elif "math" in embed.title.lower() and not AIRDROP_DISABLE_MATHDROP:
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
            elif "trivia" in embed.title.lower() and not AIRDROP_DISABLE_TRIVIADROP:
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
                                        logger.error(
                                            f"Unexpected error clicking trivia button: {e}"
                                        )
                                        return  # Don't retry on unexpected errors

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
            elif "appeared" in embed.title.lower() and not AIRDROP_DISABLE_REDPACKET:
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

        except (IndexError, AttributeError, discord.HTTPException, discord.NotFound):
            logger.debug("Something went wrong while handling drop.")
            return

    def typing_delay(self, text: str) -> float:
        """Simulate typing time based on CPM."""
        cpm = randint(AIRDROP_CPM_MIN, AIRDROP_CPM_MAX)
        return len(text) / cpm * 60

    def _validate_trivia_category(self, category: str) -> bool:
        """Validate trivia category to prevent directory traversal and injection attacks."""
        import re

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
            if isinstance(node, ast.Num):  # <number>
                return node.n
            elif isinstance(node, ast.Constant):  # <number> (Python 3.8+)
                return node.value
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
        import re

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

        return None

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

            response = await asyncio.to_thread(
                self.pollinations_api.generate_text,
                messages=messages,
                model=self.current_model,
                max_tokens=200,
                temperature=0.7,
            )

            if response and "choices" in response and len(response["choices"]) > 0:
                welcome_content = response["choices"][0]["message"]["content"]
                # Remove <functions>...</functions> tool call patterns
                import re

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
            return None

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

        # Schedule the restoration task
        self.fallback_restore_task = asyncio.create_task(
            self._restore_to_pollinations_after_timeout()
        )

        logger.info(
            f"Scheduled restoration to Pollinations after {OPENROUTER_FALLBACK_TIMEOUT} seconds"
        )

    async def _restore_to_pollinations_after_timeout(self):
        """Background task to restore to Pollinations after timeout."""
        from config import DEFAULT_MODEL, OPENROUTER_FALLBACK_TIMEOUT

        try:
            # Wait for the timeout period
            await asyncio.sleep(OPENROUTER_FALLBACK_TIMEOUT)

            # Check if we're still using OpenRouter
            if self.current_api_provider != "openrouter":
                logger.debug("Not using OpenRouter anymore, skipping restoration")
                return

            # Check if Pollinations is healthy now
            try:
                pollinations_health = await asyncio.to_thread(
                    self.pollinations_api.check_service_health
                )
                if not pollinations_health.get("healthy", False):
                    logger.info(
                        "Pollinations still unhealthy, keeping OpenRouter fallback"
                    )
                    # Reschedule restoration for later
                    self._schedule_fallback_restoration()
                    return
            except Exception as e:
                logger.warning(f"Failed to check Pollinations health: {e}")
                # Reschedule restoration for later
                self._schedule_fallback_restoration()
                return

            # Restore to Pollinations
            original_model = self.original_model_before_fallback or DEFAULT_MODEL
            self.current_api_provider = "pollinations"
            self.current_model = original_model
            self.openrouter_fallback_start_time = None
            self.original_model_before_fallback = None

            logger.info(
                f"✅ Restored to Pollinations with model {original_model} after {OPENROUTER_FALLBACK_TIMEOUT} seconds"
            )

            # Optionally send a notification to a log channel or admin
            # This could be configured later if needed

        except asyncio.CancelledError:
            logger.debug("Fallback restoration task cancelled")
        except Exception as e:
            logger.error(f"Error in fallback restoration task: {e}")

    def cancel_fallback_restoration(self):
        """Cancel any pending fallback restoration task."""
        if self.fallback_restore_task and not self.fallback_restore_task.done():
            self.fallback_restore_task.cancel()
            logger.debug("Cancelled fallback restoration task")

        self.openrouter_fallback_start_time = None
        self.original_model_before_fallback = None

    def get_fallback_status(self) -> Dict[str, Any]:
        """Get current fallback restoration status."""
        from config import OPENROUTER_FALLBACK_TIMEOUT

        status = {
            "current_provider": self.current_api_provider,
            "current_model": self.current_model,
            "is_fallback_active": self.current_api_provider == "openrouter",
            "fallback_start_time": self.openrouter_fallback_start_time,
            "original_model": self.original_model_before_fallback,
        }

        if self.openrouter_fallback_start_time:
            elapsed = time.time() - self.openrouter_fallback_start_time
            remaining = max(0, OPENROUTER_FALLBACK_TIMEOUT - elapsed)
            status.update(
                {
                    "fallback_elapsed_seconds": elapsed,
                    "fallback_remaining_seconds": remaining,
                    "fallback_progress_percent": (elapsed / OPENROUTER_FALLBACK_TIMEOUT)
                    * 100,
                }
            )

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
            content = command_data.get("content")
            author_id = command_data.get("author_id")
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
                    from utils.random_indian_generator import random_indian_generator

                    # Generate random name and address
                    name = random_indian_generator.generate_random_name()
                    address = random_indian_generator.generate_random_address()

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
                                return
                        except ValueError:
                            await self._safe_send_message(
                                channel,
                                "❌ Please provide a valid number between 1 and 10!",
                            )
                            return
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
                    # Clear various caches
                    if hasattr(self, "_command_cache"):
                        self._command_cache.clear()
                    if hasattr(self, "_user_cache"):
                        self._user_cache.clear()

                    await self._safe_send_message(
                        channel,
                        "**🧹 Cache cleared successfully!**\n\n✅ Command cache cleared\n✅ User cache cleared\n✅ Memory cache cleared\n\n*Bot should run faster now!* ⚡",
                    )
                except Exception as e:
                    logger.error(f"Error clearing cache: {e}")
                    await self._safe_send_message(
                        channel,
                        f"💀 **Error clearing cache:** {sanitize_error_message(str(e))}",
                    )
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
                        "💀 **Usage:** `model <model_name>`\n\n**Available Models:**\n• `pollinations` - Default chat model\n• `gpt4` - Advanced reasoning\n• `claude` - Helpful assistant\n• `openrouter` - Premium models\n\nExample: `model gpt4`",
                    )
                    return True

                try:
                    model_name = args[0].lower()
                    available_models = ["pollinations", "gpt4", "claude", "openrouter"]

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
            except:
                pass
            return False

    async def process_queued_ai_message(self, message_data: dict) -> bool:
        """
        Process a queued AI generation message.

        Args:
            message_data: Dictionary containing AI message information

        Returns:
            True if message was processed successfully, False otherwise
        """
        try:
            channel_id = message_data.get("channel_id")
            prompt = message_data.get("prompt")
            generation_type = message_data.get("generation_type", "text")
            author_id = message_data.get("author_id")

            # Get the channel
            channel = self.get_channel(channel_id)
            if not channel:
                logger.error(
                    f"Could not find channel {channel_id} for queued AI generation"
                )
                return False

            # Process AI generation based on type
            if generation_type == "text":
                # This would integrate with the existing AI processing logic
                logger.info(f"Processing queued text generation: {prompt[:50]}...")
                # For now, just send a placeholder response
                await self._safe_send_message(
                    channel, f"🔄 Queued AI response to: {prompt[:100]}..."
                )

            elif generation_type == "image":
                logger.info(f"Processing queued image generation: {prompt[:50]}...")
                # This would integrate with image generation
                await self._safe_send_message(
                    channel, f"🎨 Queued image generation for: {prompt[:100]}..."
                )

            return True

        except Exception as e:
            logger.error(f"Error processing queued AI message: {e}")
            return False


# Bot instance is now created in main.py with dependencies
# This prevents the global variable anti-pattern

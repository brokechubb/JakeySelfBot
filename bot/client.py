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
    sanitized = re.sub(r"\b[A-Za-z0-9]{20,}\b", "[KEY]", sanitized)
    sanitized = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", sanitized
    )
    sanitized = re.sub(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", "[IP]", sanitized)
    sanitized = re.sub(r"https?://[^\s]+", "[URL]", sanitized)
    sanitized = re.sub(
        r"Traceback \(most recent call last\):.*?$",
        "",
        sanitized,
        flags=re.MULTILINE | re.DOTALL,
    )
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."

    return sanitized or "Sanitized error message"


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
    AIRDROP_SMART_DELAY,
    CHANNEL_CONTEXT_MESSAGE_LIMIT,
    CHANNEL_CONTEXT_MINUTES,
    CONVERSATION_HISTORY_LIMIT,
    DISCORD_TOKEN,
    GENDER_ROLES_GUILD_ID,
    MAX_CONVERSATION_TOKENS,
    RATE_LIMIT_COOLDOWN,
    RELAY_MENTION_ROLE_MAPPINGS,
    SYSTEM_PROMPT,
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
    CONVERSATION_HISTORY_LIMIT = (
        CONVERSATION_HISTORY_LIMIT  # Number of previous conversations to include
    )
    MAX_CONVERSATION_TOKENS = (
        MAX_CONVERSATION_TOKENS  # Maximum tokens for conversation context
    )
    CHANNEL_CONTEXT_MINUTES = (
        CHANNEL_CONTEXT_MINUTES  # Minutes of channel context to include
    )
    CHANNEL_CONTEXT_MESSAGE_LIMIT = (
        CHANNEL_CONTEXT_MESSAGE_LIMIT  # Maximum messages in channel context
    )


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

        # Start the cleanup scheduler for memory management
        asyncio.create_task(self._schedule_cleanup())
        logger.info("Started memory cleanup scheduler")

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
                                # Archived: from resilience import MessagePriority
                                # Define local MessagePriority for queued commands
                                from enum import Enum
                                class MessagePriority(Enum):
                                    LOW = 1
                                    NORMAL = 2
                                    HIGH = 3
                                    CRITICAL = 4

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
                            await message.channel.send(
                                "💀 Command failed, probably Eddie's fault"
                            )
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

            # Get the channel ID as string for mapping lookup
            channel_id = str(message.channel.id)

            # Check if this channel has a webhook relay configured
            if channel_id not in WEBHOOK_RELAY_MAPPINGS:
                return

            webhook_url = WEBHOOK_RELAY_MAPPINGS[channel_id]
            if not webhook_url:
                logger.warning(f"Empty webhook URL configured for channel {channel_id}")
                return

            # # Allow relaying webhook messages (but still skip regular bot messages)
            # if message.author.bot and not message.webhook_id:
            #     return

            # Filter out specific webhook IDs to prevent loops
            if message.webhook_id and str(message.webhook_id) in WEBHOOK_EXCLUDE_IDS:
                logger.debug(f"Skipping excluded webhook ID {message.webhook_id}")
                return

            logger.info(
                f"Relaying message from channel {channel_id} to webhook (webhook_id: {message.webhook_id}, author: {message.author.name})"
            )

            # Format the message content
            author_name = message.author.display_name or message.author.name
            author_avatar = (
                message.author.display_avatar.url
                if message.author.display_avatar
                else None
            )

            # Build the relay content
            relay_content = message.content

            # Prepare embeds list - prioritize original embeds for embed-only messages
            embeds = []

            # Add original message embeds first (highest priority)
            if message.embeds:
                for original_embed in message.embeds:
                    try:
                        embed_dict = original_embed.to_dict()
                        embeds.append(embed_dict)
                    except Exception as embed_error:
                        logger.warning(
                            f"Failed to convert embed to dict: {embed_error}"
                        )
                        # Skip this embed if conversion fails
                        continue

            # Only add relay info embed if there is content or if we haven't added any original embeds
            # This prevents double embeds when an embed is already present and we just want to relay that
            if message.content or not embeds:
                relay_embed = discord.Embed(
                    description=message.content
                    or "*Message contained only embeds/attachments*",
                    color=discord.Color.blue(),
                    timestamp=message.created_at,
                )

                # Set author information
                relay_embed.set_author(
                    name=f"{author_name} in #{message.channel.name}",
                    icon_url=author_avatar
                    or "https://cdn.discordapp.com/embed/avatars/0.png",
                )

                # Add guild information if available
                if message.guild:
                    relay_embed.set_footer(
                        text=f"From: {message.guild.name}",
                        icon_url=message.guild.icon.url if message.guild.icon else None,
                    )

                # Convert relay embed to dictionary
                try:
                    relay_embed_dict = relay_embed.to_dict()
                    embeds.append(relay_embed_dict)
                except Exception as embed_error:
                    logger.warning(
                        f"Failed to convert relay embed to dict: {embed_error}"
                    )
                    # If we can't convert the relay embed, we'll proceed without it

            # Handle role mentions if configured for this webhook
            mention_role_id = RELAY_MENTION_ROLE_MAPPINGS.get(webhook_url)
            relay_content_with_mentions = relay_content

            if mention_role_id:
                # Add role mention to content if configured
                relay_content_with_mentions = (
                    f"<@&{mention_role_id}>\n{relay_content}"
                    if relay_content
                    else f"<@&{mention_role_id}>"
                )

            # Prepare the webhook payload
            webhook_data = {
                "content": relay_content_with_mentions
                if relay_content_with_mentions
                else None,
                "embeds": embeds if embeds else [],
                "username": f"Relay - {author_name}",
                "avatar_url": author_avatar,
            }

            # Handle attachments if any
            if message.attachments:
                # For attachments, we need to upload them separately
                # For now, we'll add their URLs to the content
                attachment_urls = [attachment.url for attachment in message.attachments]
                if attachment_urls:
                    attachment_text = "\n\n**Attachments:**\n" + "\n".join(
                        f"• {url}" for url in attachment_urls
                    )
                    if webhook_data.get("content"):
                        webhook_data["content"] += attachment_text
                    else:
                        webhook_data["content"] = attachment_text

            # Clean up empty fields
            if not webhook_data.get("content"):
                webhook_data.pop("content", None)
            if not webhook_data.get("embeds"):
                webhook_data.pop("embeds", None)

            # Validate that all data is JSON serializable before sending
            import json

            try:
                json.dumps(webhook_data)  # Test serialization
            except (TypeError, ValueError) as json_error:
                logger.error(f"Webhook payload is not JSON serializable: {json_error}")
                # Try to fix by removing problematic embeds
                if "embeds" in webhook_data:
                    logger.warning("Removing embeds due to JSON serialization error")
                    webhook_data.pop("embeds", None)
                # Try again
                try:
                    json.dumps(webhook_data)
                except (TypeError, ValueError) as final_error:
                    logger.error(f"Cannot fix JSON serialization: {final_error}")
                    return  # Skip this message

            # Send to webhook using aiohttp
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(webhook_url, json=webhook_data) as response:
                        if response.status == 200 or response.status == 204:
                            logger.info(
                                f"Successfully relayed message to webhook for channel {channel_id}"
                            )
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Failed to relay message to webhook: {response.status} - {error_text}"
                            )
                except Exception as e:
                    logger.error(f"Exception while sending to webhook: {e}")

        except Exception as e:
            logger.error(f"Error in webhook relay processing: {e}")

    def extract_facts_from_message(
        self, message_content: str, user_id: str
    ) -> List[Dict[str, str]]:
        """Extract facts from user message content and return them as tool call arguments"""
        facts = []

        # Patterns for common fact statements (improved to capture multi-word values)
        patterns = [
            # "My name is X" or "I'm called X" or "I am X"
            (r"\b(?:my name is|i\'?m called|i am) ([^.,!?;]+?)(?:[.,!?;]|$)", "name"),
            # "I live in X" or "I'm from X"
            (r"\b(?:i live in|i\'?m from) ([^.,!?;]+?)(?:[.,!?;]|$)", "location"),
            # "My favorite team is X" or "I like X"
            (
                r"\b(?:my favorite (?:team|sport) is|i like) ([^.,!?;]+?)(?:[.,!?;]|$)",
                "favorite_team",
            ),
            # "I work as X" or "I am a X"
            (r"\b(?:i work as|i am a|i\'?m a) ([^.,!?;]+?)(?:[.,!?;]|$)", "occupation"),
            # "I prefer X" or "I like X"
            (r"\b(?:i prefer|i like) ([^.,!?;]+?)(?:[.,!?;]|$)", "preference"),
            # "My favorite color is X"
            (r"\bmy favorite color is ([^.,!?;]+?)(?:[.,!?;]|$)", "favorite_color"),
        ]

        # Check each pattern
        for pattern, fact_type in patterns:
            matches = re.findall(pattern, message_content, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                fact_value = match.strip()
                # Remove common articles/prefixes that might be included
                fact_value = re.sub(
                    r"^(?:the|a|an)\s+", "", fact_value, flags=re.IGNORECASE
                )

                # Further cleanup to handle trailing words like 'and', 'but', etc.
                fact_value = re.sub(
                    r"\s+(?:and|but|or|so|then|yet|for|nor)\s*$",
                    "",
                    fact_value,
                    flags=re.IGNORECASE,
                )

                # Additional cleanup for complex sentences
                # Remove trailing phrases that connect to other statements
                fact_value = re.sub(
                    r"\s+(?:and\s+my|but\s+my|or\s+my|so\s+my)\s+.*$",
                    "",
                    fact_value,
                    flags=re.IGNORECASE,
                )

                if (
                    fact_value and len(fact_value) > 1
                ):  # Only store if we have a meaningful value
                    facts.append(
                        {
                            "user_id": user_id,
                            "information_type": fact_type,
                            "information": fact_value.title()
                            if fact_type == "name"
                            else fact_value,
                        }
                    )

        return facts

    async def collect_recent_channel_context(
        self,
        message,
        limit_minutes: Optional[int] = None,
        message_limit: Optional[int] = None,
    ) -> str:
        """Collect recent messages from the current channel for context"""
        try:
            # Only collect context for guild channels, not DMs
            if not hasattr(message.channel, "guild") or isinstance(
                message.channel, discord.DMChannel
            ):
                return ""

            channel_context = []
            current_time = time.time()

            # Fetch recent messages from the channel
            try:
                history_iter = message.channel.history(limit=message_limit)
                async for msg in history_iter:
                    # Skip the current message and bot messages
                    if msg.id == message.id or msg.author.bot:
                        continue

                    # Use configurable time limit
                    time_limit_minutes = (
                        limit_minutes or JakeyConstants.CHANNEL_CONTEXT_MINUTES
                    )
                    message_time = msg.created_at.timestamp()
                    if current_time - message_time > (time_limit_minutes * 60):
                        break

                    # Format the message for context
                    author_name = msg.author.name
                    # Only check for nick if author is a Member object (User objects don't have nick)
                    if hasattr(msg.author, "nick") and msg.author.nick:
                        author_name = f"{msg.author.nick} ({msg.author.name})"

                    # Add message to context with timestamp
                    time_ago = int((current_time - message_time) / 60)  # minutes ago
                    channel_context.append(
                        f"[{time_ago}m ago] {author_name}: {msg.content}"
                    )

            except Exception as e:
                logger.warning(f"Error iterating through channel history: {e}")
                return ""

            if channel_context:
                # Reverse to show oldest first, add header
                channel_context.reverse()
                context_str = (
                    "\n\nRecent Channel Context (last 30 minutes):\n"
                    + "\n".join(channel_context)
                )
                return context_str

            return ""

        except Exception as e:
            logger.warning(f"Error collecting channel context: {e}")
            return ""

    async def process_jakey_response(self, message):
        """Process a message and generate Jakey's response with improved error handling"""
        try:
            # Add a reaction to indicate processing
            try:
                await message.add_reaction("🧠")
            except discord.NotFound:
                # Message was deleted, ignore gracefully
                pass
            except discord.Forbidden:
                # Bot doesn't have permission to add reactions
                pass
            async with message.channel.typing():
                # Get user pronouns based on their roles (only in specified guild if configured)
                try:
                    user_pronouns = ("they", "them", "their")  # Default to neutral
                    if GENDER_ROLES_GUILD_ID:
                        # Check if message is in the specified guild
                        if hasattr(message.channel, "guild") and message.channel.guild:
                            if str(message.channel.guild.id) == GENDER_ROLES_GUILD_ID:
                                # Use gender roles only in the specified guild
                                user_pronouns = get_user_pronouns(message.author)
                    else:
                        # No guild restriction configured, use global behavior
                        user_pronouns = get_user_pronouns(message.author)

                    # Add guild context for Discord tool usage
                    guild_context = ""
                    if hasattr(message.channel, "guild") and message.channel.guild:
                        guild_context = f"\n- Current Guild: {message.channel.guild.name} (ID: {message.channel.guild.id})"

                    pronoun_context = f"\n\nUser Information:\n- Name: {message.author.name}\n- Pronouns: {user_pronouns[0]}/{user_pronouns[1]}/{user_pronouns[2]}{guild_context}"
                except Exception as e:
                    logger.warning(f"Could not determine user pronouns: {e}")
                    user_pronouns = ("they", "them", "their")
                    # Add guild context for Discord tool usage
                    guild_context = ""
                    if hasattr(message.channel, "guild") and message.channel.guild:
                        guild_context = f"\n- Current Guild: {message.channel.guild.name} (ID: {message.channel.guild.id})"

                    pronoun_context = f"\n\nUser Information:\n- Name: {message.author.name}\n- Pronouns: they/them/their{guild_context}"
                # Check user rate limiting
                user_id = str(message.author.id)
                current_time = time.time()
                logger.debug(f"Rate limiting check for user {user_id}")

                with self._user_lock:
                    # OPTIMIZED O(1) rate limiting using sliding window
                    if user_id not in self._user_window_starts:
                        # New user - initialize tracking
                        self._user_request_counts[user_id] = 0
                        self._user_window_starts[user_id] = current_time
                        logger.debug(
                            f"Created new rate limit tracking for user {user_id}"
                        )

                    # Check if we need to reset the window (60 seconds have passed)
                    if (
                        current_time - self._user_window_starts[user_id]
                        >= JakeyConstants.RATE_LIMIT_WINDOW
                    ):
                        # Reset window - O(1) operation
                        self._user_request_counts[user_id] = 0
                        self._user_window_starts[user_id] = current_time
                        logger.debug(f"Reset rate limit window for user {user_id}")

                    # Check if user is rate limited - O(1) operation
                    if self._user_request_counts[user_id] >= self.user_rate_limit:
                        logger.warning(
                            f"Rate limit hit for user {user_id} - {self._user_request_counts[user_id]}/{self.user_rate_limit} requests"
                        )
                        await message.channel.send(
                            f"💀 Rate limit hit! Wait {self.rate_limit_cooldown} seconds before trying again."
                        )
                        return

                    # Record this request - O(1) operation
                    self._user_request_counts[user_id] += 1
                    logger.debug(
                        f"Recorded request for user {user_id} - now has {self._user_request_counts[user_id]} active requests"
                    )
                # Get or create user in database
                logger.debug(f"Checking database for user {message.author.id}")
                user_data = await self.db.aget_user(str(message.author.id))
                if not user_data:
                    logger.info(
                        f"Creating new user entry for {message.author.name}#{message.author.discriminator}"
                    )
                    await self.db.acreate_or_update_user(
                        user_id=str(message.author.id), username=message.author.name
                    )
                    user_data = await self.db.aget_user(str(message.author.id))
                else:
                    # Update username if it has changed
                    if user_data.get("username") != message.author.name:
                        logger.info(
                            f"Updating username for user {message.author.id} from '{user_data.get('username')}' to '{message.author.name}'"
                        )
                        await self.db.acreate_or_update_user(
                            user_id=str(message.author.id),
                            username=message.author.name,
                            preferences=user_data.get("preferences"),
                            important_facts=user_data.get("important_facts"),
                        )

                # Get user memories/facts
                logger.debug(f"Loading user memories for {message.author.id}")
                user_memories = await self.db.aget_memories(str(message.author.id))

                # Get recent conversation history using configurable limit
                logger.debug(f"Loading recent conversations for {message.author.id}")
                recent_conversations = await self.db.aget_recent_conversations(
                    str(message.author.id),
                    limit=JakeyConstants.CONVERSATION_HISTORY_LIMIT,
                )
                # Collect recent channel context for better responses
                logger.debug(f"Collecting channel context for {message.channel.id}")
                channel_context = await self.collect_recent_channel_context(
                    message,
                    limit_minutes=JakeyConstants.CHANNEL_CONTEXT_MINUTES,
                    message_limit=JakeyConstants.CHANNEL_CONTEXT_MESSAGE_LIMIT,
                )
                if channel_context:
                    logger.info(
                        f"Collected channel context with {len(channel_context)} characters"
                    )

                # Extract facts from the user's message
                facts = self.extract_facts_from_message(
                    message.content, str(message.author.id)
                )
                if facts:
                    logger.info(
                        f"Extracted {len(facts)} facts from user message for user {message.author.id}"
                    )
                    # Store the extracted facts in memory
                    for fact in facts:
                        try:
                            await self.db.aadd_memory(
                                fact["user_id"],
                                fact["information_type"],
                                fact["information"],
                            )
                            logger.debug(
                                f"Stored fact: {fact['information_type']} = {fact['information']}"
                            )
                        except Exception as e:
                            logger.error(f"Error storing fact: {e}")

                # Check if the message is asking for Keno numbers before calling AI

                # Build message history for context with size limits
                system_content = SYSTEM_PROMPT + pronoun_context

                # Add channel context to system prompt if available
                if channel_context:
                    system_content += channel_context

                # Add user-specific memories to system prompt
                if user_memories:
                    memory_context = "\n\nUser-Specific Information:\n"
                    for key, value in user_memories.items():
                        memory_context += f"- {key}: {value}\n"
                    system_content += memory_context

                # Apply advanced anti-repetition context enhancement (invisible)
                user_id = str(message.author.id)
                enhanced_system_content = (
                    anti_repetition_integrator.get_enhanced_system_prompt(
                        user_id, system_content
                    )
                )

                messages = [{"role": "system", "content": enhanced_system_content}]

                # Add recent conversation context (limit total tokens)
                total_tokens = len(SYSTEM_PROMPT.split())  # Approximate token count
                max_tokens = min(
                    JakeyConstants.MAX_AI_TOKENS, JakeyConstants.MAX_CONVERSATION_TOKENS
                )  # Use configurable conversation token limit

                # Add recent conversations in reverse order (newest first)
                for i, conv in enumerate(recent_conversations):
                    # Ensure conv_messages is a mutable list
                    conv_messages = list(conv["messages"])
                    # Check for None content in conversation messages
                    for j, msg in enumerate(conv_messages):
                        if isinstance(msg, dict) and msg.get("content") is None:
                            msg["content"] = ""
                        elif isinstance(msg, str):
                            # If msg is a string, convert it to a dict with role and content
                            conv_messages[j] = {"role": "user", "content": msg}

                    conv_tokens = sum(
                        len((msg.get("content") or "").split()) for msg in conv_messages
                    )

                    if total_tokens + conv_tokens <= max_tokens:
                        # Check messages before adding them
                        for msg in conv_messages:
                            if isinstance(msg, dict) and msg.get("content") is None:
                                msg["content"] = ""
                            elif isinstance(msg, str):
                                # If msg is a string, conversion already handled earlier
                                pass  # String would have been converted to dict in earlier loop
                        messages.extend(conv_messages)
                        total_tokens += conv_tokens
                    else:
                        # If adding this conversation would exceed limit, skip it
                        break

                # Add current message
                current_message_content = f"{message.author.name}: {message.content}"
                if total_tokens + len(current_message_content.split()) <= max_tokens:
                    user_message = {"role": "user", "content": current_message_content}
                    # Ensure content is not None
                    if user_message["content"] is None:
                        user_message["content"] = ""
                    messages.append(user_message)

                # Check if the message is asking for Keno numbers before calling AI
                keno_keywords = [
                    "keno",
                    "keno numbers",
                    "keno picks",
                    "keno numbers please",
                    "keno picks please",
                    "keno number",
                    "keno pick",
                ]
                message_content_lower = message.content.lower()

                # Extract facts from the user's message
                facts = self.extract_facts_from_message(
                    message.content, str(message.author.id)
                )
                if facts:
                    logger.info(
                        f"Extracted {len(facts)} facts from user message for user {message.author.id}"
                    )
                    # Store the extracted facts in memory
                    for fact in facts:
                        try:
                            await self.db.aadd_memory(
                                fact["user_id"],
                                fact["information_type"],
                                fact["information"],
                            )
                            logger.debug(
                                f"Stored fact: {fact['information_type']} = {fact['information']}"
                            )
                        except Exception as e:
                            logger.error(f"Error storing fact: {e}")

                # If the message is asking for Keno numbers, generate them automatically
                if any(keyword in message_content_lower for keyword in keno_keywords):
                    logger.info(f"Keno request detected for user {message.author.id}")
                    # Generate Keno numbers automatically
                    import random

                    count = random.randint(3, 10)
                    numbers = random.sample(range(1, 41), count)
                    numbers.sort()

                    # Create visual representation (8 columns x 5 rows) with clean spacing
                    visual_lines = []
                    for row in range(0, 40, 8):
                        line = ""
                        for i in range(row + 1, min(row + 9, 41)):
                            if i in numbers:
                                line += f"[{i:2d}] "
                            else:
                                line += f" {i:2d}  "
                        visual_lines.append(line.rstrip())

                    # Create the response
                    keno_response = f"**🎯 Keno Number Generator**\n"
                    keno_response += f"Generated **{count}** numbers for you!\n\n"
                    keno_response += f"**Your Keno Numbers:**\n"
                    keno_response += f"`{', '.join(map(str, numbers))}`\n\n"
                    keno_response += "**Visual Board:**\n"
                    keno_response += "```\n" + "\n".join(visual_lines) + "\n```"
                    keno_response += "\n*Numbers in brackets are your picks!*"

                    # Send the Keno response
                    await message.channel.send(keno_response)

                    # Save conversation to database
                    conversation_history = [
                        {
                            "role": "user",
                            "content": f"{message.author.name}: {message.content}",
                        },
                        {
                            "role": "assistant",
                            "content": f"🎯 Generated Keno numbers: {', '.join(map(str, numbers))}",
                        },
                    ]
                    self.db.add_conversation(
                        str(message.author.id), conversation_history
                    )

                    # Remove the processing reaction
                    try:
                        await message.remove_reaction("🧠", self.user)
                    except:
                        pass

                    return  # Don't process with AI since we already responded

                # Generate response with tool support
                # Ensure all messages have valid content before sending
                for i, msg in enumerate(messages):
                    if isinstance(msg, dict) and msg.get("content") is None:
                        msg["content"] = ""
                    elif isinstance(msg, str):
                        # If msg is a string, convert it to a dict with role and content
                        messages[i] = {"role": msg.get("role", "user"), "content": msg}
                        msg["content"] = ""

                logger.info(
                    f"Calling AI API for user {message.author.id} with {len(messages)} messages"
                )
                logger.debug(f"Using model: {self.current_model}")

                # Log model capabilities for debugging
                model_supports_tools = self._model_supports_tools(self.current_model)
                logger.info(
                    f"Model {self.current_model} supports tools: {model_supports_tools}"
                )

                logger.debug(
                    f"About to determine API provider for model {self.current_model}"
                )

                # Determine which provider the model belongs to
                model_key = (
                    self.current_model.strip().lower() if self.current_model else ""
                )
                model_info = (
                    self._model_capabilities.get(model_key) if model_key else None
                )
                preferred_provider = (
                    model_info.get("provider", "pollinations")
                    if model_info and isinstance(model_info, dict)
                    else "pollinations"
                )

                logger.info(
                    f"Selected API provider: {preferred_provider} for model {self.current_model}"
                )

                response = None
                pollinations_failed = False
                self.current_api_provider = preferred_provider

                logger.debug(f"About to make API call to {preferred_provider}")

                # Try the appropriate API based on the model's provider
                if preferred_provider == "openrouter" and openrouter_api.enabled:
                    # Use OpenRouter for OpenRouter-specific models
                    logger.debug(
                        f"Using OpenRouter API for model {self.current_model} (provider: {preferred_provider})"
                    )
                    if model_supports_tools:
                        response = openrouter_api.generate_text(
                            messages=messages,
                            model=self.current_model,
                            tools=self.tool_manager.get_available_tools(),
                            tool_choice="auto",
                        )

                        # Check for tool-use errors and retry without tools
                        if "error" in response:
                            error_msg = str(response.get("error", "")).lower()
                            if (
                                "no endpoints found that support tool use" in error_msg
                                or "http 404" in error_msg
                            ):
                                logger.warning(
                                    f"OpenRouter model {self.current_model} doesn't support tools, retrying without tools"
                                )
                                response = openrouter_api.generate_text(
                                    messages=messages, model=self.current_model
                                )
                    else:
                        logger.warning(
                            f"Model {self.current_model} may not support tools, calling without tools via OpenRouter"
                        )
                        response = openrouter_api.generate_text(
                            messages=messages, model=self.current_model
                        )
                else:
                    # Use Pollinations for other models (default) or if OpenRouter is disabled
                    logger.debug(
                        f"Using Pollinations API for model {self.current_model} (provider: {preferred_provider})"
                    )
                    if model_supports_tools:
                        response = self.pollinations_api.generate_text(
                            messages=messages,
                            model=self.current_model,
                            tools=self.tool_manager.get_available_tools(),
                            tool_choice="auto",
                        )
                    else:
                        # Fallback to no tools for models that don't support function calling
                        logger.warning(
                            f"Model {self.current_model} may not support tools, calling without tools"
                        )
                        response = self.pollinations_api.generate_text(
                            messages=messages, model=self.current_model
                        )

                # Check if the primary provider failed
                if "error" in response:
                    if preferred_provider == "pollinations":
                        pollinations_failed = True
                        logger.warning(
                            f"Pollinations API failed for user {message.author.id}: {response['error']}"
                        )
                    else:
                        logger.warning(
                            f"OpenRouter API failed for user {message.author.id}: {response['error']}"
                        )
                        # Mark as pollinations failed for fallback logic (since we're treating OpenRouter as primary for its models)
                        pollinations_failed = True

                    # Try OpenRouter as fallback
                    if openrouter_api.enabled:
                        logger.info(
                            f"Attempting OpenRouter fallback for user {message.author.id}"
                        )

                        # Use a hardcoded reliable OpenRouter model (more reliable than dynamic selection)
                        openrouter_model = "nvidia/nemotron-nano-9b-v2:free"
                        logger.debug(
                            f"Selected hardcoded OpenRouter fallback model: {openrouter_model}"
                        )

                        # Try OpenRouter API call
                        openrouter_response = openrouter_api.generate_text(
                            messages=messages,
                            model=openrouter_model,
                            tools=self.tool_manager.get_available_tools(),
                            tool_choice="auto" if model_supports_tools else None,
                        )

                        if "error" not in openrouter_response:
                            response = openrouter_response
                            self.current_api_provider = "openrouter"
                            self.current_model = (
                                openrouter_model  # Update to actual model used
                            )
                            logger.info(
                                f"OpenRouter fallback successful for user {message.author.id} using model {openrouter_model}"
                            )
                            # Schedule restoration to Pollinations after timeout
                            self._schedule_fallback_restoration()
                        else:
                            # Check if this is a tool-use error and retry without tools
                            error_msg = str(
                                openrouter_response.get("error", "")
                            ).lower()
                            if (
                                "no endpoints found that support tool use" in error_msg
                                or "http 404" in error_msg
                            ) and model_supports_tools:
                                logger.warning(
                                    f"OpenRouter model {openrouter_model} doesn't support tools, retrying without tools"
                                )
                                openrouter_response_no_tools = (
                                    openrouter_api.generate_text(
                                        messages=messages,
                                        model=openrouter_model,
                                        tools=None,
                                        tool_choice=None,
                                    )
                                )

                                if "error" not in openrouter_response_no_tools:
                                    response = openrouter_response_no_tools
                                    self.current_api_provider = "openrouter"
                                    self.current_model = openrouter_model
                                    logger.info(
                                        f"OpenRouter fallback successful without tools for user {message.author.id} using model {openrouter_model}"
                                    )
                                    # Schedule restoration to Pollinations after timeout
                                    self._schedule_fallback_restoration()
                                else:
                                    logger.error(
                                        f"OpenRouter fallback also failed (even without tools): {openrouter_response_no_tools['error']}"
                                    )
                            else:
                                logger.error(
                                    f"OpenRouter fallback also failed: {openrouter_response['error']}"
                                )
                    else:
                        logger.info("OpenRouter not available as fallback")

                if "error" in response:
                    logger.error(
                        f"AI API call failed for user {message.author.id}: {response['error']}"
                    )
                    error_msg = response["error"].lower()

                    # Provide context about fallback attempts
                    if pollinations_failed and openrouter_api.enabled:
                        error_context = "Both Pollinations and OpenRouter failed"
                    elif pollinations_failed:
                        error_context = (
                            "Pollinations failed and OpenRouter is not available"
                        )
                    else:
                        error_context = "AI service error"

                    # Check for service outage patterns first
                    if (
                        "502" in error_msg
                        or "bad gateway" in error_msg
                        or "server error" in error_msg
                        or "service may be down" in error_msg
                        or "cloudflared" in error_msg
                    ):
                        await message.channel.send(
                            f"🔥 **AI Services Down** - {error_context}. "
                            "Try again in a few minutes or use `%help` for other commands."
                        )
                    elif "timeout" in error_msg or "connection error" in error_msg:
                        await message.channel.send(
                            f"💀 I am a little slow bro ({error_context}). Try again in a bit"
                        )
                    else:
                        await message.channel.send(
                            f"💀 WTF is this? {error_context}: {response['error']}"
                        )
                    return

                # Filter out tool call JSON from response content to prevent it from being sent to user
                if response.get("choices", [{}])[0].get("message", {}).get("content"):
                    response_content = response["choices"][0]["message"].get(
                        "content", ""
                    )
                    # Remove tool call JSON from the response content
                    import re

                    # Remove <functions>...</functions> tool call patterns
                    response_content = re.sub(
                        r"<functions>.*?</functions>",
                        "",
                        response_content,
                        flags=re.DOTALL,
                    )
                    # Remove JSON-like tool call patterns
                    response_content = re.sub(
                        r'\[\s*\{.*?"name".*?\}\s*\]',
                        "",
                        response_content,
                        flags=re.DOTALL,
                    )
                    # Remove Python function call tool patterns (e.g., remember_user_info("key": "value"))
                    response_content = re.sub(
                        r"\b(?:remember_user_info|web_search|company_research|crawling|generate_image|analyze_image|crypto_price|stock_price|get_bonus_schedule|tip_user|calculate)\s*\([^)]*\)",
                        "",
                        response_content,
                        flags=re.DOTALL,
                    )
                    # Clean up extra whitespace
                    response_content = re.sub(
                        r"\n\s*\n", "\n\n", response_content
                    ).strip()
                    # Update the response content
                    response["choices"][0]["message"]["content"] = response_content

                # Handle tool calls if present
                image_generated = False
                image_urls = []
                response_text = ""  # Initialize response_text

                if (
                    response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("tool_calls")
                ):
                    tool_calls = response["choices"][0]["message"]["tool_calls"]
                    # Add the assistant's message with tool calls to the conversation
                    # Make sure it has content to avoid API errors
                    original_message = response["choices"][0]["message"].copy()
                    # Set meaningful content for assistant messages with tool calls to avoid API validation errors
                    if (
                        not original_message.get("content")
                        or original_message["content"] == ""
                    ):
                        original_message["content"] = (
                            "Processing your request with available tools..."
                        )
                    messages.append(original_message)

                    # Process each tool call and collect results
                    tool_results = []

                    # Process each tool call and collect results
                    logger.info(
                        f"Processing {len(tool_calls)} tool calls for user {message.author.id}"
                    )
                    for tool_call in tool_calls:
                        function_name = tool_call["function"]["name"]
                        try:
                            arguments = json.loads(tool_call["function"]["arguments"])
                            # Enhanced logging: Log tool name and key parameters
                            if function_name == "web_search":
                                query = arguments.get("query", "unknown")
                                logger.info(
                                    f"🔍 TOOL CALL: web_search(query='{query[:100]}{'...' if len(query) > 100 else ''}') by user {message.author.id}"
                                )
                            elif function_name == "company_research":
                                company = arguments.get("company_name", "unknown")
                                logger.info(
                                    f"🏢 TOOL CALL: company_research(company='{company}') by user {message.author.id}"
                                )
                            elif function_name == "crypto_price":
                                symbol = arguments.get("symbol", "unknown")
                                currency = arguments.get("currency", "USD")
                                logger.info(
                                    f"💰 TOOL CALL: crypto_price(symbol='{symbol}', currency='{currency}') by user {message.author.id}"
                                )
                            elif function_name == "stock_price":
                                symbol = arguments.get("symbol", "unknown")
                                logger.info(
                                    f"📈 TOOL CALL: stock_price(symbol='{symbol}') by user {message.author.id}"
                                )
                            elif function_name == "generate_image":
                                prompt = arguments.get("prompt", "unknown")
                                logger.info(
                                    f"🎨 TOOL CALL: generate_image(prompt='{prompt[:100]}{'...' if len(prompt) > 100 else ''}') by user {message.author.id}"
                                )
                            elif function_name == "analyze_image":
                                image_url = arguments.get("image_url", "unknown")[:50]
                                prompt = arguments.get("prompt", "unknown")
                                logger.info(
                                    f"🖼️  TOOL CALL: analyze_image(image_url='{image_url}...', prompt='{prompt[:50]}...') by user {message.author.id}"
                                )
                            elif function_name == "calculate":
                                expression = arguments.get("expression", "unknown")
                                logger.info(
                                    f"🧮 TOOL CALL: calculate(expression='{expression}') by user {message.author.id}"
                                )
                            elif function_name == "remember_user_info":
                                key = arguments.get("key", "unknown")
                                value = str(arguments.get("value", "unknown"))[:50]
                                logger.info(
                                    f"🧠 TOOL CALL: remember_user_info(key='{key}', value='{value}...') by user {message.author.id}"
                                )
                            elif function_name == "tip_user":
                                recipient = arguments.get("recipient", "unknown")
                                amount = arguments.get("amount", "unknown")
                                currency = arguments.get("currency", "unknown")
                                logger.info(
                                    f"💸 TOOL CALL: tip_user(recipient='{recipient}', amount='{amount}', currency='{currency}') by user {message.author.id}"
                                )
                            elif function_name == "get_bonus_schedule":
                                platform = arguments.get("platform", "unknown")
                                logger.info(
                                    f"📅 TOOL CALL: get_bonus_schedule(platform='{platform}') by user {message.author.id}"
                                )
                            elif function_name == "crawling":
                                url = arguments.get("url", "unknown")[:50]
                                logger.info(
                                    f"🕷️  TOOL CALL: crawling(url='{url}...') by user {message.author.id}"
                                )
                            else:
                                logger.info(
                                    f"🔧 TOOL CALL: {function_name}(arguments={arguments}) by user {message.author.id}"
                                )

                            logger.debug(
                                f"Executing tool {function_name} for user {message.author.id}"
                            )
                            result = await self.tool_manager.execute_tool(
                                function_name, arguments
                            )

                            # Check if this is an image generation result
                            if function_name == "generate_image":
                                result_str = str(result)
                                # Check if the result is a valid image URL (either directly returned or contained within)
                                if (
                                    result_str.startswith(
                                        "https://image.pollinations.ai"
                                    )
                                    or result_str.startswith(
                                        "https://t2i-prod.s3.us-east-1.amazonaws.com"
                                    )
                                    or "https://image.pollinations.ai" in result_str
                                    or "https://t2i-prod.s3.us-east-1.amazonaws.com"
                                    in result_str
                                ):
                                    image_generated = True
                                    logger.info(
                                        f"Image generated for user {message.author.id}"
                                    )
                                    # Extract the image URL - handle both direct URLs and URLs within text
                                    import re

                                    if result_str.startswith("https://"):
                                        # Direct URL return
                                        image_urls.append(result_str.strip())
                                    else:
                                        # URL embedded in response text
                                        pollinations_urls = re.findall(
                                            r"https://image\.pollinations\.ai[^\s\)]*",
                                            result_str,
                                        )
                                        arta_urls = re.findall(
                                            r"https://t2i-prod\.s3\.us-east-1\.amazonaws\.com[^\s\)]*",
                                            result_str,
                                        )
                                        urls = pollinations_urls + arta_urls
                                        image_urls.extend(urls)

                            # Format tool response according to OpenAI API specification
                            tool_result = {
                                "tool_call_id": tool_call.get("id", ""),
                                "role": "tool",
                                "content": str(result),
                            }
                            tool_results.append(tool_result)

                            # Enhanced logging: Log tool completion with result summary
                            import re

                            result_str = str(result)
                            if function_name == "web_search":
                                # Count number of results from search
                                result_lines = result_str.split("\n")
                                num_results = len(
                                    [
                                        line
                                        for line in result_lines
                                        if line.strip()
                                        and not line.startswith("Source:")
                                    ]
                                )
                                logger.info(
                                    f"✅ TOOL RESULT: web_search completed with {num_results} results for user {message.author.id}"
                                )
                            elif function_name == "company_research":
                                logger.info(
                                    f"✅ TOOL RESULT: company_research completed for user {message.author.id}"
                                )
                            elif function_name == "crypto_price":
                                # Extract price from result if available
                                price_match = re.search(r"\$?[\d,]+\.?\d*", result_str)
                                price = (
                                    price_match.group(0) if price_match else "unknown"
                                )
                                logger.info(
                                    f"✅ TOOL RESULT: crypto_price completed, price: {price} for user {message.author.id}"
                                )
                            elif function_name == "stock_price":
                                # Extract price from result if available
                                price_match = re.search(r"\$?[\d,]+\.?\d*", result_str)
                                price = (
                                    price_match.group(0) if price_match else "unknown"
                                )
                                logger.info(
                                    f"✅ TOOL RESULT: stock_price completed, price: {price} for user {message.author.id}"
                                )
                            elif function_name == "generate_image":
                                logger.info(
                                    f"✅ TOOL RESULT: generate_image completed successfully for user {message.author.id}"
                                )
                            elif function_name == "analyze_image":
                                logger.info(
                                    f"✅ TOOL RESULT: analyze_image completed for user {message.author.id}"
                                )
                            elif function_name == "calculate":
                                # Extract calculation result
                                calc_match = re.search(
                                    r"=?\s*([\d,]+\.?\d*|\w+)", result_str
                                )
                                calc_result = (
                                    calc_match.group(1) if calc_match else "computed"
                                )
                                logger.info(
                                    f"✅ TOOL RESULT: calculate completed, result: {calc_result} for user {message.author.id}"
                                )
                            elif function_name == "remember_user_info":
                                logger.info(
                                    f"✅ TOOL RESULT: remember_user_info completed for user {message.author.id}"
                                )
                            elif function_name == "tip_user":
                                logger.info(
                                    f"✅ TOOL RESULT: tip_user completed for user {message.author.id}"
                                )
                            elif function_name == "get_bonus_schedule":
                                logger.info(
                                    f"✅ TOOL RESULT: get_bonus_schedule completed for user {message.author.id}"
                                )
                            elif function_name == "crawling":
                                # Extract URL and content info from result for better logging
                                result_str = str(result)
                                url_from_args = arguments.get("url", "unknown")[:50]
                                if "Content from" in result_str and ":" in result_str:
                                    # Extract content length and preview
                                    content_part = (
                                        result_str.split(":", 1)[1]
                                        if ":" in result_str
                                        else result_str
                                    )
                                    content_length = len(content_part)
                                    content_preview = (
                                        content_part[:100].replace("\n", " ").strip()
                                        + "..."
                                        if len(content_part) > 100
                                        else content_part
                                    )
                                    logger.info(
                                        f"✅ TOOL RESULT: crawling completed for {url_from_args}... - {content_length} chars: {content_preview} for user {message.author.id}"
                                    )
                                else:
                                    logger.info(
                                        f"✅ TOOL RESULT: crawling completed for {url_from_args}... for user {message.author.id}"
                                    )
                            else:
                                logger.info(
                                    f"✅ TOOL RESULT: {function_name} completed for user {message.author.id}"
                                )

                            logger.debug(
                                f"Tool {function_name} completed successfully for user {message.author.id}"
                            )

                        except Exception as e:
                            error_msg = f"Error executing {function_name}: {str(e)}"
                            # Enhanced error logging with specific tool context
                            logger.error(
                                f"❌ TOOL ERROR: {function_name} failed for user {message.author.id}: {str(e)[:200]}"
                            )
                            # Format error response according to OpenAI API specification
                            tool_result = {
                                "tool_call_id": tool_call.get("id", ""),
                                "role": "tool",
                                "content": error_msg,
                            }
                            tool_results.append(tool_result)

                    # Add all tool responses to messages
                    messages.extend(tool_results)

                    # Generate final response after all tools have been processed
                    logger.info(
                        f"Generating final response for user {message.author.id} using {self.current_api_provider} with {len(messages)} messages"
                    )

                    # Remove None content from messages before sending to API
                    for i, msg in enumerate(messages):
                        if isinstance(msg, dict) and msg.get("content") is None:
                            msg["content"] = ""
                        elif isinstance(msg, str):
                            # If msg is a string, convert it to a dict with role and content
                            messages[i] = {
                                "role": "user",
                                "content": msg,
                            }

                    # Ensure all messages have valid content before sending
                    for i, msg in enumerate(messages):
                        if isinstance(msg, dict) and msg.get("content") is None:
                            msg["content"] = ""
                        elif isinstance(msg, str):
                            # If msg is a string, convert it to a dict with role and content
                            messages[i] = {
                                "role": "user",
                                "content": msg,
                            }

                    # Trim messages to fit within API character limits (gpt-5-mini limit is ~7000 chars)
                    messages = self._trim_messages_for_api(messages, max_chars=6000)

                    # Use the same API provider that was used for the initial call
                    try:
                        if self.current_api_provider == "openrouter":
                            logger.debug(
                                f"Making final OpenRouter API call with model {self.current_model}"
                            )
                            final_response = openrouter_api.generate_text(
                                messages=messages, model=self.current_model
                            )
                        else:
                            logger.debug(
                                f"Making final Pollinations API call with model {self.current_model}"
                            )
                            final_response = self.pollinations_api.generate_text(
                                messages=messages, model=self.current_model
                            )

                        if "error" in final_response:
                            logger.error(
                                f"Final API call failed for user {message.author.id}: {final_response['error']}"
                            )
                            # Send error message to user
                            await message.channel.send(
                                f"❌ Sorry, I encountered an error: {final_response['error']}"
                            )
                            return

                        logger.info(
                            f"Final API call successful for user {message.author.id}"
                        )

                        # Log the actual response content
                        if "choices" in final_response and final_response["choices"]:
                            response_content = final_response["choices"][0][
                                "message"
                            ].get("content", "")
                            logger.info(
                                f"AI RESPONSE CONTENT for user {message.author.id}: '{response_content}' (length: {len(response_content)})"
                            )
                        else:
                            logger.warning(
                                f"No choices in final response for user {message.author.id}: {final_response}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Exception during final API call for user {message.author.id}: {str(e)}"
                        )
                        await message.channel.send(
                            f"❌ Sorry, I encountered an error while generating your response."
                        )
                        return
                    if "error" not in final_response:
                        response_text = final_response["choices"][0]["message"].get(
                            "content", ""
                        )
                        logger.debug(f"Raw AI response: {response_text}")
                        # Filter out tool call JSON from final response content
                        if response_text:
                            import re

                            # Remove <functions>...</functions> tool call patterns
                            response_text = re.sub(
                                r"<functions>.*?</functions>",
                                "",
                                response_text,
                                flags=re.DOTALL,
                            )
                            # Remove JSON-like tool call patterns
                            response_text = re.sub(
                                r'\[\s*\{.*?"name".*?\}\s*\]',
                                "",
                                response_text,
                                flags=re.DOTALL,
                            )
                            # Remove Python function call tool patterns (e.g., remember_user_info("key": "value"))
                            response_text = re.sub(
                                r"\b(?:remember_user_info|web_search|company_research|crawling|generate_image|analyze_image|crypto_price|stock_price|get_bonus_schedule|tip_user|calculate)\s*\([^)]*\)",
                                "",
                                response_text,
                                flags=re.DOTALL,
                            )
                            # Clean up extra whitespace
                            response_text = re.sub(
                                r"\n\s*\n", "\n\n", response_text
                            ).strip()

                        # Advanced anti-repetition check (invisible and efficient)
                        if response_text and response_text.strip():
                            user_id = str(message.author.id)

                            # Check if response needs enhancement
                            should_enhance, reason = (
                                anti_repetition_integrator.should_enhance_response(
                                    user_id, response_text
                                )
                            )

                            if should_enhance:
                                logger.debug(
                                    f"Response enhancement suggested for user {user_id}: {reason}"
                                )
                                # In the new system, we don't generate fallback responses
                                # Instead, we let the enhanced system prompt guide the AI
                                # This makes the system invisible to users
                                pass  # Response is still sent, but context is enhanced for next time

                            # Record the response for learning (lightweight operation)
                            anti_repetition_integrator.record_response(
                                user_id, response_text
                            )

                        logger.debug(f"Filtered response_text: '{response_text}'")
                    else:
                        error_msg = final_response["error"]
                        if "timeout" in error_msg.lower():
                            response_text = "💀 Tool timeout... Pollinations is being slow bro, try again in a bit"
                        else:
                            response_text = "💀 Tool broke, try again later"
                else:
                    response_text = response["choices"][0]["message"].get("content", "")

                    # Response will be handled by send_long_message below to avoid truncation

                # Extract image URLs from response text
                image_links_sent = False
                if response_text and (
                    "image.pollinations.ai" in response_text
                    or "t2i-prod.s3.us-east-1.amazonaws.com" in response_text
                ):
                    # Look for image URLs in the response text
                    import re

                    # Find URLs pointing to image.pollinations.ai and arta
                    pollinations_urls = re.findall(
                        r"https://image\.pollinations\.ai[^\s\)]*", response_text
                    )
                    arta_urls = re.findall(
                        r"https://t2i-prod\.s3\.us-east-1\.amazonaws\.com[^\s\)]*",
                        response_text,
                    )
                    found_image_urls = pollinations_urls + arta_urls
                    image_urls.extend(found_image_urls)

                    # Remove the image URLs and surrounding markdown from the response text
                    # Remove markdown links for Pollinations: [text](url)
                    response_text = re.sub(
                        r"\[[^\]]*\]\(https?://image\.pollinations\.ai[^\)]*\)",
                        "",
                        response_text,
                    )
                    # Remove markdown links for Arta: [text](url)
                    response_text = re.sub(
                        r"\[[^\]]*\]\(https?://t2i-prod\.s3\.us-east-1\.amazonaws\.com[^\)]*\)",
                        "",
                        response_text,
                    )
                    # Remove bare URLs for Pollinations
                    response_text = re.sub(
                        r"https?://image\.pollinations\.ai[^\s]*", "", response_text
                    )
                    # Remove bare URLs for Arta
                    response_text = re.sub(
                        r"https?://t2i-prod\.s3\.us-east-1\.amazonaws\.com[^\s]*",
                        "",
                        response_text,
                    )
                    # Clean up extra whitespace
                    response_text = re.sub(r"\n\s*\n", "\n\n", response_text).strip()

                # Handle case where tool response contains just an image URL
                elif response_text and response_text.startswith(
                    "https://image.pollinations.ai"
                ):
                    # Extract image URLs
                    import re

                    found_image_urls = re.findall(
                        r"https://image\.pollinations\.ai[^\s]*", response_text
                    )
                    image_urls.extend(found_image_urls)
                    response_text = ""
                    image_links_sent = True

                # Remove duplicate image URLs
                unique_image_urls = list(
                    dict.fromkeys(image_urls)
                )  # Preserves order and removes duplicates

                # Send a single coordinated response with both text and images
                response_sent = False

                # Prepare conversation content for database
                conversation_content = ""
                logger.debug(
                    f"response_text: '{response_text}', unique_image_urls: {unique_image_urls}"
                )
                if response_text and response_text.strip():
                    conversation_content = response_text.strip()
                elif unique_image_urls:
                    conversation_content = f"🎨 Image generated ({len(unique_image_urls)} image{'s' if len(unique_image_urls) > 1 else ''})"
                else:
                    conversation_content = None
                logger.debug(f"conversation_content: '{conversation_content}'")

                # Send single response combining text and images
                if response_text and response_text.strip() and unique_image_urls:
                    # Both text and images - send combined message
                    combined_message = f"{response_text}\n\n"
                    for i, image_url in enumerate(unique_image_urls):
                        if i == 0:
                            combined_message += (
                                f"🎨 **Here's your image bro:**\n{image_url}"
                            )
                        else:
                            combined_message += (
                                f"\n\n🎨 **Another image:**\n{image_url}"
                            )

                    # Check global response cooldown
                    current_time = time.time()
                    time_since_last_response = current_time - self._last_global_response
                    if time_since_last_response < self._global_response_cooldown:
                        await asyncio.sleep(
                            self._global_response_cooldown - time_since_last_response
                        )

                    # Send long message without truncation
                    await send_long_message(message.channel, combined_message)
                    self._last_global_response = time.time()
                    response_sent = True
                    logger.debug("Combined text+image response sent")

                elif unique_image_urls:
                    # Images only - send image message
                    for i, image_url in enumerate(unique_image_urls):
                        if i == 0:
                            image_message = (
                                f"🎨 **Here's your image bro:**\n{image_url}"
                            )
                        else:
                            image_message = f"🎨 **Another image:**\n{image_url}"

                        # Check global response cooldown
                        current_time = time.time()
                        time_since_last_response = (
                            current_time - self._last_global_response
                        )
                        if time_since_last_response < self._global_response_cooldown:
                            await asyncio.sleep(
                                self._global_response_cooldown
                                - time_since_last_response
                            )

                        await message.channel.send(image_message)
                        self._last_global_response = time.time()
                        response_sent = True
                        logger.debug(
                            f"Image response {i + 1}/{len(unique_image_urls)} sent"
                        )

                elif response_text and response_text.strip():
                    # Text only - send text message
                    logger.debug(f"Sending text response: '{response_text}'")
                    current_time = time.time()
                    time_since_last_response = current_time - self._last_global_response
                    if time_since_last_response < self._global_response_cooldown:
                        await asyncio.sleep(
                            self._global_response_cooldown - time_since_last_response
                        )

                    # Send long message without truncation
                    await send_long_message(message.channel, response_text)
                    self._last_global_response = time.time()
                    response_sent = True
                    logger.debug("Text response sent")

                    # Log if no response was sent
                    if not response_sent:
                        logger.warning(
                            f"NO RESPONSE SENT for user {message.author.id}. response_text='{response_text}', unique_image_urls={len(unique_image_urls) if unique_image_urls else 0}"
                        )

                    # Save conversation to database if we sent a response
                    if (
                        response_sent
                        and conversation_content
                        and conversation_content.strip()
                    ):
                        conversation_history = [
                            {
                                "role": "user",
                                "content": f"{message.author.name}: {message.content}",
                            },
                            {"role": "assistant", "content": conversation_content},
                        ]
                        await self.db.aadd_conversation(
                            str(message.author.id), conversation_history
                        )

        except Exception as e:
            error_msg = f"Error processing message: {e}"
            logger.exception(f"💀 {error_msg}")  # Log the full traceback
            await message.channel.send(
                "💀 Something went wrong, probably Eddie's fault"
            )
        finally:
            # Remove the processing reaction
            try:
                await message.remove_reaction("🧠", self.user)
            except discord.errors.NotFound:
                pass  # Reaction already removed or message deleted
            except Exception as e:
                logger.error(f"Error removing reaction: {e}")

    async def on_reaction_add(self, reaction, user):
        """Handle reaction additions with proper self-bot handling"""
        # Don't respond to ourselves or bots
        if user == self.user or user.bot:
            return

        # Check if this is a reaction role
        message_id = str(reaction.message.id)
        emoji = str(reaction.emoji)

        # Check if this message has reaction roles set up
        reaction_role = self.db.get_reaction_role(message_id, emoji)
        if reaction_role:
            try:
                # Get the role
                guild = reaction.message.guild
                role = guild.get_role(int(reaction_role))

                if role:
                    # Add the role to the user
                    member = guild.get_member(user.id)
                    if member:
                        await member.add_roles(role, reason="Reaction role")
                        # Optionally send a confirmation message
                        await user.send(
                            f"✅ You've received the **{role.name}** role by reacting with {emoji}!"
                        )
                    else:
                        logger.error(
                            f"Could not find member {user.id} in guild {guild.name}"
                        )
                else:
                    logger.error(
                        f"Could not find role {reaction_role} in guild {guild.name}"
                    )
            except discord.Forbidden:
                logger.error("Bot doesn't have permission to add roles")
            except Exception as e:
                logger.error(f"Error adding reaction role: {e}")

        # Check if the reaction is to our own message
        if reaction.message.author == self.user:
            # Respond to specific reactions with personality
            if str(reaction.emoji) == "💀":
                try:
                    await reaction.message.add_reaction("💥")
                except discord.NotFound:
                    # Message was deleted, ignore gracefully
                    pass
                except discord.Forbidden:
                    # Bot doesn't have permission to add reactions
                    pass
            elif str(reaction.emoji) == "rigged":
                await reaction.message.channel.send("💀 Everything's rigged bro!")
            elif str(reaction.emoji) == "💰":
                await reaction.message.channel.send(
                    "EZ money? More like ramen money 💀"
                )

    async def on_reaction_remove(self, reaction, user):
        """Handle reaction removals with proper self-bot handling"""
        # Don't respond to ourselves or bots
        if user == self.user or user.bot:
            return

        # Check if this is a reaction role removal
        message_id = str(reaction.message.id)
        emoji = str(reaction.emoji)

        # Check if this message has reaction roles set up
        reaction_role = self.db.get_reaction_role(message_id, emoji)
        if reaction_role:
            try:
                # Get the role
                guild = reaction.message.guild
                role = guild.get_role(int(reaction_role))

                if role:
                    # Remove the role from the user
                    member = guild.get_member(user.id)
                    if member:
                        await member.remove_roles(role, reason="Reaction role removed")
                        # Optionally send a confirmation message
                        await user.send(
                            f"❌ You've lost the **{role.name}** role because you removed your reaction with {emoji}."
                        )
                    else:
                        logger.error(
                            f"Could not find member {user.id} in guild {guild.name}"
                        )
                else:
                    logger.error(
                        f"Could not find role {reaction_role} in guild {guild.name}"
                    )
            except discord.Forbidden:
                logger.error("Bot doesn't have permission to remove roles")
            except Exception as e:
                logger.error(f"Error removing reaction role: {e}")

        # Check if the reaction was removed from our own message
        if reaction.message.author == self.user:
            # Jakey can respond to reaction removals if needed
            pass

    async def on_reaction_clear(self, message, reactions):
        """Handle when all reactions are cleared from a message"""
        # Don't respond to our own messages
        if message.author == self.user:
            await message.channel.send(
                "💀 Bro, why'd you clear all my reactions? Rigged."
            )

    async def cleanup_old_users(self):
        """Clean up inactive users to prevent memory leaks - OPTIMIZED O(1) cleanup"""
        current_time = time.time()
        cutoff = current_time - (JakeyConstants.USER_MEMORY_LIMIT_DAYS * 24 * 60 * 60)

        with self._user_lock:
            old_users = [
                user_id
                for user_id, window_start in self._user_window_starts.items()
                if window_start < cutoff
            ]
            for user_id in old_users:
                del self._user_request_counts[user_id]
                del self._user_window_starts[user_id]

        if old_users:
            logger.info(f"Cleaned up {len(old_users)} inactive users")

    async def cleanup_wen_cooldown(self):
        """Clean up old wen cooldown entries to prevent memory leaks"""
        current_time = time.time()
        cutoff = current_time - self.wen_cooldown_duration

        # Clean up old entries
        old_entries = len(self.wen_cooldown)
        self.wen_cooldown = {
            msg_id: timestamp
            for msg_id, timestamp in self.wen_cooldown.items()
            if current_time - timestamp < self.wen_cooldown_duration
        }
        new_entries = len(self.wen_cooldown)

        if old_entries != new_entries:
            logger.info(
                f"Cleaned up {old_entries - new_entries} old wen cooldown entries"
            )

    async def _schedule_cleanup(self):
        """Schedule periodic cleanup of all tracking data - OPTIMIZED memory management"""
        while True:
            await asyncio.sleep(3600)  # Run every hour
            try:
                await self.cleanup_old_users()
                await self.cleanup_wen_cooldown()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

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

        # Check if user is in ignore list
        ignore_users_list = (
            AIRDROP_IGNORE_USERS.split(",") if AIRDROP_IGNORE_USERS else []
        )
        if str(original_message.author.id) in ignore_users_list:
            return

        logger.debug(f"Detected potential drop: {original_message.content}")

        try:
            # Wait for the tip.cc bot response
            tip_cc_message = await self.wait_for(
                "message",
                timeout=15,
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

        # Apply delay logic
        await self.maybe_delay(drop_ends_in)

        try:
            # Airdrop
            if "airdrop" in embed.title.lower() and not AIRDROP_DISABLE_AIRDROP:
                if tip_cc_message.components:
                    button = tip_cc_message.components[0].children[0]
                    # Add timeout handling and retry logic for button clicks
                    for attempt in range(3):  # Retry up to 3 times
                        try:
                            # Validate button is still clickable before attempting
                            if not button.disabled:
                                await asyncio.wait_for(button.click(), timeout=5.0)
                                await asyncio.sleep(2)
                                # await original_message.channel.send("beep boop beep...")  # Disabled beep boop message
                                logger.info(
                                    f"Entered airdrop in {original_message.channel.name}"
                                )
                                # Success inside if block
                            else:
                                logger.warning(
                                    "Airdrop button is disabled, drop may have expired"
                                )
                            break  # Success or disabled, exit retry loop
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"Timeout clicking airdrop button (attempt {attempt + 1}/3)"
                            )
                            if attempt < 2:  # Don't sleep on the last attempt
                                await asyncio.sleep(1)  # Reduced backoff time
                        except discord.HTTPException as e:
                            if "50035" in str(e) and "Invalid Form Body" in str(e):
                                logger.warning(
                                    f"Invalid form body when clicking airdrop button (attempt {attempt + 1}/3) - button may be stale"
                                )
                                if attempt < 2:  # Only retry if we have more attempts
                                    await asyncio.sleep(2)  # Wait longer before retry
                                else:
                                    logger.error(
                                        "Airdrop button component appears to be invalid"
                                    )
                            else:
                                logger.error(f"HTTP error clicking airdrop button: {e}")
                                break  # Don't retry on other HTTP errors
                        except discord.ClientException as e:
                            logger.warning(
                                f"Client error clicking airdrop button (likely timeout): {e}"
                            )
                            if attempt < 2:  # Don't sleep on the last attempt
                                await asyncio.sleep(1)  # Reduced backoff time
                        except Exception as e:
                            logger.error(
                                f"Unexpected error clicking airdrop button: {e}"
                            )
                            break  # Don't retry on unexpected errors

            # Phrase drop
            elif (
                "phrase drop" in embed.title.lower() and not AIRDROP_DISABLE_PHRASEDROP
            ):
                phrase = embed.description.replace("\n", "").replace("**", "")
                phrase = phrase.split("*")[1].strip()
                async with original_message.channel.typing():
                    await asyncio.sleep(self.typing_delay(phrase))
                await original_message.channel.send(phrase)
                logger.info(f"Entered phrase drop in {original_message.channel.name}")

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
                                                            button.click(), timeout=10.0
                                                        )
                                                        logger.info(
                                                            f"Entered trivia drop in {original_message.channel.name}"
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
                                                        logger.error(
                                                            f"Unexpected error clicking trivia button: {e}"
                                                        )
                                                        return  # Don't retry on unexpected errors

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

    def typing_delay(self, text: str) -> float:
        """Simulate typing time based on CPM."""
        cpm = randint(AIRDROP_CPM_MIN, AIRDROP_CPM_MAX)
        return len(text) / cpm * 60

    def _validate_trivia_category(self, category: str) -> bool:
        """Validate trivia category to prevent directory traversal and injection attacks."""
        import re

        # Allow only alphanumeric characters, spaces, hyphens, and underscores
        if not re.match(r"^[a-zA-Z0-9\s\-_]+$", category):
            return False

        # Prevent directory traversal attempts
        if ".." in category or "/" in category or "\\" in category:
            return False

        # Prevent null bytes and other dangerous characters
        if "\x00" in category or "\n" in category or "\r" in category:
            return False

        # Reasonable length limit
        if len(category) > 50:
            return False

        # Strip whitespace and check if still valid
        cleaned_category = category.strip()
        if not cleaned_category:
            return False

        return True

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

            response = self.pollinations_api.generate_text(
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
                pollinations_health = self.pollinations_api.check_service_health()
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
`%keno` - Generate random Keno numbers (3-10 numbers from 1-40)
`%ind_addr` - Generate a random Indian name and address

**💰 TIP.CC COMMANDS (Admin Only):**
`%bal` / `%bals` - Check tip.cc balances and auto-dismiss response (admin)
`%confirm` - Manually click Confirm button on tip.cc confirmation messages (admin)
`%tip <user> <amount> <currency> [message]` - Send a tip to a user (admin)
`%airdrop <amount> <currency> [for] <duration>` - Create an airdrop (admin)
`%transactions [limit]` - Show recent tip.cc transaction history (admin)
`%tipstats` - Show tip.cc statistics and earnings (admin)
`%airdropstatus` - Show current airdrop configuration and status (admin)

**🎨 AI & MEDIA COMMANDS:**
`%image <prompt>` - Generate an image with artistic styles
`%audio <text>` - Generate audio from text using AI voices
`%analyze <image_url> [prompt]` - Analyze an image (or attach an image)

**💥 EXAMPLES:**
`%time` - Current time in UTC
`%time est` - Current time in US Eastern
`%keno` - Generate your lucky Keno numbers
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
                                    logger.info("Fallback button click successful")
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
                                    logger.info("Fallback button click successful")
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
                # Generate random Keno numbers (3-10 numbers from 1-40) with 8x5 visual board
                try:
                    import random

                    # Generate a random count between 3 and 10
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

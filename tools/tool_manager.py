import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import pytz
import requests
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import COINMARKETCAP_API_KEY, MCP_MEMORY_ENABLED, SEARXNG_URL

from .discord_tools import DiscordTools

logger = logging.getLogger(__name__)

# Import rate limiter
try:
    from .rate_limiter import rate_limit_middleware

    RATE_LIMITING_ENABLED = True
except ImportError:
    logger.warning("Rate limiter not available, using fallback rate limiting")
    RATE_LIMITING_ENABLED = False


class ToolManager:
    def __init__(self):
        self.tools = {
            "set_reminder": self.set_reminder,
            "list_reminders": self.list_reminders,
            "cancel_reminder": self.cancel_reminder,
            "check_due_reminders": self.check_due_reminders,
            "remember_user_info": self.remember_user_info,
            "search_user_memory": self.search_user_memory,
            "get_crypto_price": self.get_crypto_price,
            "get_stock_price": self.get_stock_price,
            "tip_user": self.tip_user,
            "check_balance": self.check_balance,
            "get_bonus_schedule": self.get_bonus_schedule,
            "web_search": self.web_search,
            "company_research": self.company_research,
            "crawling": self.crawling,
            "generate_image": self.generate_image,
            "analyze_image": self.analyze_image,
            "calculate": self.calculate,
            "get_current_time": self.get_current_time,
            "remember_user_mcp": self.remember_user_mcp,
            # Discord tools
            "discord_get_user_info": self.discord_get_user_info,
            "discord_list_guilds": self.discord_list_guilds,
            "discord_list_channels": self.discord_list_channels,
            "discord_read_channel": self.discord_read_channel,
            "discord_search_messages": self.discord_search_messages,
            "discord_list_guild_members": self.discord_list_guild_members,
            "discord_send_message": self.discord_send_message,
            "discord_send_dm": self.discord_send_dm,
            "discord_get_user_roles": self.discord_get_user_roles,
            # Rate limiting tools
            "get_user_rate_limit_status": self.get_user_rate_limit_status,
            "get_system_rate_limit_stats": self.get_system_rate_limit_stats,
            "reset_user_rate_limits": self.reset_user_rate_limits,
        }

        # Initialize Discord tools - will be set later by main.py after bot initialization
        self.discord_tools = None

        # Define corrected bonus schedules for different sites
        self.bonus_schedules = {
            "stake_weekly": "Saturday 12:30 PM UTC",
            "stake_monthly": "Around the 15th of each month (varies by VIP)",
            "bitsler_daily": "Every 24 hours after last claim",
            "bitsler_weekly": "Sunday 12:00 AM UTC (approximate, may vary)",
            "bitsler_monthly": "First day of month 12:00 AM UTC",
            "freebitco.in_daily": "12:00 AM UTC",
            "freebitco.in_weekly": "Sunday 12:00 AM UTC",
            "freebitco.in_monthly": "First day of month 12:00 AM UTC",
            "freebitco.in_hourly": "Every hour",
            "fortunejack_daily": "12:00 AM UTC",
            "fortunejack_weekly": "Sunday 12:00 AM UTC",
            "fortunejack_monthly": "First day of month 12:00 AM UTC",
            "bc.game_daily": "Once every 24 hours (local reset varies)",
            "bc.game_weekly": "Sunday 12:00 AM UTC",
            "bc.game_monthly": "End of month 12:00 AM UTC",
            "roobet_daily": "12:00 AM UTC",
            "roobet_weekly": "Weekly raffle (time not fixed)",
            "roobet_monthly": "Monthly cashback (time not fixed)",
            "vave_daily": "12:00 AM UTC",
            "vave_weekly": "Sunday 12:00 AM UTC",
            "vave_monthly": "First day of month 12:00 AM UTC",
            "spinz.io_daily": "12:00 AM UTC",
            "spinz.io_weekly": "Sunday 12:00 AM UTC",
            "spinz.io_monthly": "First day of month 12:00 AM UTC",
            "blazebet_daily": "12:00 AM UTC",
            "blazebet_weekly": "Sunday 12:00 AM UTC",
            "blazebet_monthly": "First day of month 12:00 AM UTC",
            "duelbits_daily": "12:00 AM UTC",
            "duelbits_weekly": "Sunday 12:00 AM UTC",
            "duelbits_monthly": "First day of month 12:00 AM UTC",
            "bets.io_daily": "12:00 AM UTC",
            "bets.io_weekly": "Sunday 12:00 AM UTC",
            "bets.io_monthly": "First day of month 12:00 AM UTC",
            "clash.bet_daily": "12:00 AM UTC",
            "clash.bet_weekly": "Sunday 12:00 AM UTC",
            "clash.bet_monthly": "First day of month 12:00 AM UTC",
            "stake.us_weekly": "Saturday 12:30 PM UTC",
            "stake.us_monthly": "Around the 15th of each month (varies by VIP)",
            "shuffle_weekly": "Thursday 11:00 AM UTC",
            "shuffle_monthly": "First Friday 12:00 AM UTC",
        }

        # Add rate limiting for tools
        self.last_call_time = {}
        self.rate_limits = {
            "crypto_price": 1.0,  # 1 second between calls
            "stock_price": 1.0,  # 1 second between calls
            "tip_user": 1.0,  # 1 second between calls
            "check_balance": 1.0,  # 1 second between calls
            "get_bonus_schedule": 1.0,  # 1 second between calls
            "web_search": 2.0,  # 2 seconds between calls
            "company_research": 2.0,  # 2 seconds between calls
            "crawling": 2.0,  # 2 seconds between calls
            "generate_image": 5.0,  # 5 seconds between calls
            "analyze_image": 5.0,  # 5 seconds between calls
            "calculate": 0.1,  # 0.1 seconds between calls
            "get_current_time": 0.1,  # 0.1 seconds between calls
            "set_reminder": 1.0,  # 1 second between calls
            "list_reminders": 1.0,  # 1 second between calls
            "cancel_reminder": 1.0,  # 1 second between calls
            "check_due_reminders": 5.0,  # 5 seconds between calls (background task)
            "remember_user_info": 1.0,  # 1 second between calls
            "remember_user_mcp": 1.0,  # 1 second between calls
            "search_user_memory": 0.1,  # 0.1 seconds between calls
            # Discord tool rate limits
            "discord_get_user_info": 1.0,
            "discord_list_guilds": 1.0,
            "discord_list_channels": 1.0,
            "discord_read_channel": 1.0,
            "discord_search_messages": 1.0,
            "discord_list_guild_members": 1.0,
            "discord_send_message": 1.0,
            "discord_send_dm": 1.0,
        }

    def _validate_crypto_symbol(self, symbol: str) -> bool:
        """Validate cryptocurrency symbol using security framework."""
        try:
            # Import here to avoid circular imports
            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path(__file__).parent.parent))
            from utils.security_validator import validator

            is_valid, _ = validator.validate_cryptocurrency_symbol(symbol)
            return is_valid
        except ImportError:
            # Fallback to basic validation if security validator not available
            import re

            return bool(re.match(r"^[A-Z0-9]{1,10}$", symbol.upper()))

    def _validate_currency_code(self, currency: str) -> bool:
        """Validate currency code using security framework."""
        try:
            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path(__file__).parent.parent))
            from utils.security_validator import validator

            is_valid, _ = validator.validate_currency_code(currency)
            return is_valid
        except ImportError:
            # Fallback validation
            import re

            return bool(re.match(r"^[A-Z]{3}$", currency.upper()))

    def _validate_search_query(self, query: str) -> bool:
        """Validate search query using security framework."""
        try:
            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path(__file__).parent.parent))
            from utils.security_validator import validator

            is_valid, _ = validator.validate_search_query(query)
            return is_valid
        except ImportError:
            # Fallback validation
            return bool(query and len(query.strip()) <= 1000 and "\x00" not in query)

    def _check_rate_limit(self, tool_name: str, user_id: str = "system") -> bool:
        """Check if tool can be called based on per-user rate limits"""
        # Check per-user rate limits first if available
        if RATE_LIMITING_ENABLED:
            try:
                is_allowed, violation_reason = rate_limit_middleware.check_request(
                    user_id, tool_name
                )
                if not is_allowed:
                    logger.warning(
                        f"Rate limit violation for user {user_id}: {violation_reason}"
                    )
                    return False
            except Exception as e:
                logger.error(f"Error checking per-user rate limit: {e}")
                # Fall back to global rate limiting on error

        # Fall back to global rate limits for backward compatibility
        current_time = time.time()
        if tool_name in self.last_call_time:
            time_since_last_call = current_time - self.last_call_time[tool_name]
            if time_since_last_call < self.rate_limits.get(tool_name, 1.0):
                return False
        self.last_call_time[tool_name] = current_time
        return True

    def get_available_tools(self) -> List[Dict]:
        """Return the list of available tools in OpenAI function calling format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "set_reminder",
                    "description": "Set a reminder, alarm, or timer for a specific time",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID who owns the reminder",
                            },
                            "reminder_type": {
                                "type": "string",
                                "description": "Type of reminder: 'alarm', 'timer', or 'reminder'",
                                "enum": ["alarm", "timer", "reminder"],
                            },
                            "title": {
                                "type": "string",
                                "description": "Title of the reminder",
                            },
                            "description": {
                                "type": "string",
                                "description": "Detailed description of what the reminder is about",
                            },
                            "trigger_time": {
                                "type": "string",
                                "description": "ISO 8601 formatted time when the reminder should trigger (e.g., '2025-10-03T15:00:00Z')",
                            },
                            "channel_id": {
                                "type": "string",
                                "description": "Optional Discord channel ID to send reminder to",
                            },
                            "recurring_pattern": {
                                "type": "string",
                                "description": "Optional recurring pattern (daily, weekly, monthly)",
                            },
                        },
                        "required": [
                            "user_id",
                            "reminder_type",
                            "title",
                            "description",
                            "trigger_time",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_reminders",
                    "description": "List all pending reminders for a user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID whose reminders to list",
                            }
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "cancel_reminder",
                    "description": "Cancel a specific reminder by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID who owns the reminder",
                            },
                            "reminder_id": {
                                "type": "integer",
                                "description": "ID of the reminder to cancel",
                            },
                        },
                        "required": ["user_id", "reminder_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_due_reminders",
                    "description": "Check for any due reminders (used by background tasks)",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remember_user_info",
                    "description": "Remember important information about a user for future reference",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID",
                            },
                            "information_type": {
                                "type": "string",
                                "description": "Type of information to remember (e.g., preference, fact, habit)",
                            },
                            "information": {
                                "type": "string",
                                "description": "The actual information to remember",
                            },
                        },
                        "required": ["user_id", "information_type", "information"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_user_memory",
                    "description": "Search for previously remembered information about a user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID",
                            },
                            "query": {
                                "type": "string",
                                "description": "Search query to find relevant memories",
                            },
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_crypto_price",
                    "description": "Get current price of a cryptocurrency in a specific currency",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Cryptocurrency symbol (e.g., BTC, ETH, DOGE)",
                            },
                            "currency": {
                                "type": "string",
                                "description": "Currency to convert to (e.g., USD, EUR, GBP)",
                                "default": "USD",
                            },
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_stock_price",
                    "description": "Get current price of a stock",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Stock symbol (e.g., AAPL, GOOGL, TSLA)",
                            }
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tip_user",
                    "description": "Tip another user through tip.cc",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID of the recipient",
                            },
                            "amount": {
                                "type": "string",
                                "description": "Amount to tip (e.g., '100' or '5.5')",
                            },
                            "currency": {
                                "type": "string",
                                "description": "Currency to tip in (e.g., 'DOGE', 'BTC', 'USD')",
                                "default": "DOGE",
                            },
                            "message": {
                                "type": "string",
                                "description": "Optional message to include with the tip",
                            },
                        },
                        "required": ["user_id", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_balance",
                    "description": "Check user's tip.cc balance",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID",
                            }
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_bonus_schedule",
                    "description": "Get bonus schedule information for gambling sites",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "description": "Gambling site name (e.g., 'stake', 'bitsler', 'freebitco.in')",
                            },
                            "frequency": {
                                "type": "string",
                                "description": "Bonus frequency (daily, weekly, monthly, hourly)",
                                "enum": ["daily", "weekly", "monthly", "hourly"],
                            },
                        },
                        "required": ["site", "frequency"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Performs real-time web searches using public SearXNG instances with multiple search engines",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "company_research",
                    "description": "Comprehensive company research using public SearXNG instances with multiple search engines",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "company_name": {
                                "type": "string",
                                "description": "Name of the company to research",
                            }
                        },
                        "required": ["company_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "crawling",
                    "description": "Extracts content from specific URLs using direct web scraping",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to crawl"},
                            "max_characters": {
                                "type": "integer",
                                "description": "Maximum number of characters to extract",
                                "default": 3000,
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_image",
                    "description": "Generate an image using Arta API with artistic styles and aspect ratios",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "Image generation prompt",
                            },
                            "model": {
                                "type": "string",
                                "description": "Model to use for generation",
                                "default": "SDXL 1.0",
                            },
                            "width": {
                                "type": "integer",
                                "description": "Image width in pixels (converted to aspect ratio)",
                                "default": 1024,
                            },
                            "height": {
                                "type": "integer",
                                "description": "Image height in pixels (converted to aspect ratio)",
                                "default": 1024,
                            },
                        },
                        "required": ["prompt"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_image",
                    "description": "Analyze an image using Pollinations API vision capabilities",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_url": {
                                "type": "string",
                                "description": "URL of the image to analyze",
                            },
                            "prompt": {
                                "type": "string",
                                "description": "Prompt for image analysis",
                                "default": "Describe this image",
                            },
                        },
                        "required": ["image_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Perform mathematical calculations and comparisons",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Mathematical expression to calculate (supports basic operations +, -, *, / and comparisons >, <, >=, <=, ==, !=)",
                            }
                        },
                        "required": ["expression"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get current time and date information for any timezone worldwide",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timezone": {
                                "type": "string",
                                "description": "Timezone name or alias (e.g., 'UTC', 'EST', 'US/Eastern', 'Europe/London')",
                                "default": "UTC",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remember_user_mcp",
                    "description": "Remember user information using MCP memory server with enhanced capabilities",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID",
                            },
                            "information_type": {
                                "type": "string",
                                "description": "Type of information (e.g. 'preference', 'fact', 'reminder')",
                            },
                            "information": {
                                "type": "string",
                                "description": "The information to remember",
                            },
                        },
                        "required": ["user_id", "information_type", "information"],
                    },
                },
            },
            # Discord tools
            {
                "type": "function",
                "function": {
                    "name": "discord_get_user_info",
                    "description": "Get information about the currently logged-in Discord user",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_list_guilds",
                    "description": "List all Discord servers/guilds the user is in",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_list_channels",
                    "description": "List channels the user has access to, optionally filtered by guild",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {
                                "type": "string",
                                "description": "Optional: Filter channels by guild ID",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_read_channel",
                    "description": "Read messages from a specific Discord channel",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {
                                "type": "string",
                                "description": "The Discord channel ID to read messages from",
                            },
                            "limit": {
                                "type": "number",
                                "description": "Number of messages to fetch (default: 50, max: 100)",
                            },
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_search_messages",
                    "description": "Search for messages in a Discord channel by content, author, or date range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {
                                "type": "string",
                                "description": "The Discord channel ID to search messages in",
                            },
                            "query": {
                                "type": "string",
                                "description": "Text to search for in message content",
                            },
                            "author_id": {
                                "type": "string",
                                "description": "Optional: Filter by author ID",
                            },
                            "limit": {
                                "type": "number",
                                "description": "Number of messages to search through (default: 100, max: 500)",
                            },
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_list_guild_members",
                    "description": "List members of a specific Discord guild/server",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {
                                "type": "string",
                                "description": "The Discord guild ID to list members from",
                            },
                            "limit": {
                                "type": "number",
                                "description": "Number of members to fetch (default: 100, max: 1000)",
                            },
                            "include_roles": {
                                "type": "boolean",
                                "description": "Whether to include role information for each member",
                            },
                        },
                        "required": ["guild_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_send_message",
                    "description": "Send a message to a specific Discord channel",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {
                                "type": "string",
                                "description": "The Discord channel ID to send the message to",
                            },
                            "content": {
                                "type": "string",
                                "description": "The message content to send",
                            },
                            "reply_to_message_id": {
                                "type": "string",
                                "description": "Optional: Message ID to reply to",
                            },
                        },
                        "required": ["channel_id", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_send_dm",
                    "description": "Send a direct message to a specific Discord user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "The Discord user ID to send the DM to",
                            },
                            "content": {
                                "type": "string",
                                "description": "The message content to send",
                            },
                        },
                        "required": ["user_id", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_user_rate_limit_status",
                    "description": "Get rate limiting status and statistics for a specific user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID to check rate limit status for",
                            }
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_system_rate_limit_stats",
                    "description": "Get overall system rate limiting statistics and metrics",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "reset_user_rate_limits",
                    "description": "Reset rate limits and penalties for a specific user (admin function)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Discord user ID to reset rate limits for",
                            }
                        },
                        "required": ["user_id"],
                    },
                },
            },
        ]

    def remember_user_info(
        self, user_id: str, information_type: str, information: str
    ) -> str:
        """Remember important information about a user with rate limiting"""
        if not self._check_rate_limit("remember_user_info", user_id):
            return (
                "Rate limit exceeded. Please wait before remembering more information."
            )

        try:
            # Check if unified memory backend is enabled (migration complete)
            migration_flag = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.memory_migration_complete')
            if os.path.exists(migration_flag):
                try:
                    # Dynamic import to avoid circular dependencies
                    import importlib
                    memory_module = importlib.import_module('memory')
                    memory_backend = memory_module.memory_backend

                    if memory_backend is not None:
                        # Use unified memory backend
                        import asyncio

                        async def _store_memory():
                            success = await memory_backend.store(
                                user_id, information_type, information
                            )
                            return success

                        # Run the async operation
                        try:
                            loop = asyncio.get_running_loop()
                            import concurrent.futures

                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, _store_memory())
                                success = future.result()
                        except RuntimeError:
                            success = asyncio.run(_store_memory())

                        if success:
                            return f"Got it! I'll remember that {information_type}: {information}"
                        else:
                            return "Sorry, I couldn't remember that information right now."
                except (ImportError, AttributeError) as e:
                    # Log but don't fail - fall back to legacy system
                    import logging
                    logging.getLogger(__name__).warning(f"Unified memory backend unavailable: {e}")

            # Fallback to direct database access (legacy system)
            from data.database import db

            key = f"{information_type}"
            db.add_memory(user_id, key, information)

            return f"Got it! I'll remember that {information_type}: {information}"
        except Exception as e:
            return f"Error remembering information: {str(e)}"

        except Exception as e:
            return f"Error remembering information: {str(e)}"

    def remember_user_mcp(
        self, user_id: str, information_type: str, information: str
    ) -> str:
        """Remember user information using MCP memory server with rate limiting and fallback"""
        if not self._check_rate_limit("remember_user_mcp", user_id):
            return (
                "Rate limit exceeded. Please wait before remembering more information."
            )

        if not MCP_MEMORY_ENABLED:
            # Fallback to SQLite when MCP is disabled
            return self.remember_user_info(user_id, information_type, information)

        try:
            # Create the async function to run the operation
            async def _run_with_context():
                async with MCPMemoryClient() as client:
                    if not await client.check_connection():
                        return {"error": "MCP memory server not accessible"}
                    return await client.remember_user_info(
                        user_id, information_type, information
                    )

            # Check if there's already a running event loop
            try:
                loop = asyncio.get_running_loop()
                # If there's a running loop, create a task and wait for it
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _run_with_context())
                    result = future.result()
            except RuntimeError:
                # No running event loop, safe to run directly
                result = asyncio.run(_run_with_context())

            if "error" in result:
                # Fallback to SQLite when MCP fails
                fallback_result = self.remember_user_info(
                    user_id, information_type, information
                )
                return f"MCP memory unavailable, using local storage: {fallback_result}"

            return f"Got it! I'll remember that {information_type}: {information} (stored in MCP memory)"
        except Exception as e:
            # Fallback to SQLite when MCP fails
            try:
                fallback_result = self.remember_user_info(
                    user_id, information_type, information
                )
                return f"MCP memory error ({str(e)}), using local storage: {fallback_result}"
            except Exception as fallback_error:
                return f"Both MCP and local storage failed: MCP: {str(e)}, Local: {str(fallback_error)}"

    def search_user_memory(self, user_id: str, query: str = "") -> str:
        """Search user memories with rate limiting"""
        if not self._check_rate_limit("search_user_memory", user_id):
            return "Rate limit exceeded. Please wait before searching memories."

        # Import asyncio here to avoid issues
        import asyncio
        import concurrent.futures

        # Check if unified memory backend is enabled (migration complete)
        migration_flag = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.memory_migration_complete')
        if os.path.exists(migration_flag):
            try:
                # Dynamic import to avoid circular dependencies
                import importlib
                memory_module = importlib.import_module('memory')
                memory_backend = memory_module.memory_backend

                if memory_backend is not None:
                    # Use unified memory backend
                    async def _search_memory():
                        results = await memory_backend.search(user_id, query or None, limit=5)
                        return results

                    # Run the async operation
                    try:
                        loop = asyncio.get_running_loop()
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, _search_memory())
                            results = future.result()
                    except RuntimeError:
                        results = asyncio.run(_search_memory())

                    if not results:
                        return f"No memories found for user {user_id}."

                    # Format the results
                    formatted_memories = []
                    for entry in results:
                        key = entry.key
                        value = entry.value
                        formatted_memories.append(f"• {key}: {value}")

                    return f"Found memories for user {user_id} (unified):\n" + "\n".join(
                        formatted_memories
                    )
            except (ImportError, AttributeError) as e:
                # Log but don't fail - fall back to legacy system
                import logging
                logging.getLogger(__name__).warning(f"Unified memory backend unavailable for search: {e}")

        # Fallback to legacy MCP system
        if not MCP_MEMORY_ENABLED:
            return "Memory search not available. Use remember_user_info for local storage."

        try:
            # Import MCP memory client
            from tools.mcp_memory_client import MCPMemoryClient

            # Create the async function to run the search
            async def _run_search_with_context():
                async with MCPMemoryClient() as client:
                    if not await client.check_connection():
                        return {"error": "MCP memory server not accessible"}
                    return await client.search_user_memory(
                        user_id, query if query else None
                    )

            # Check if there's already a running event loop
            try:
                loop = asyncio.get_running_loop()
                # If there's a running loop, create a task and wait for it
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _run_search_with_context())
                    result = future.result()
            except RuntimeError:
                # No running event loop, safe to run directly
                result = asyncio.run(_run_search_with_context())

            if "error" in result:
                return f"MCP memory search failed: {result['error']}. Local search not available for this tool."

            # Format the results
            memories = result.get("memories", [])
            if not memories:
                return f"No memories found for user {user_id} in MCP memory server."

            formatted_memories = []
            for memory in memories[:5]:  # Limit to top 5 results
                info_type = memory.get("information_type", "unknown")
                info = memory.get("information", "")
                timestamp = memory.get("timestamp", "")
                formatted_memories.append(f"• {info_type}: {info}")

            return f"Found memories for user {user_id} (MCP):\n" + "\n".join(
                formatted_memories
            )
        except Exception as e:
            return f"Error searching MCP memory: {str(e)}. Local search not available for this tool."

    def get_crypto_price(
        self, symbol: str, currency: str = "USD", user_id: str = "system"
    ) -> str:
        """Get cryptocurrency price from CoinMarketCap API with rate limiting"""
        if not self._check_rate_limit("crypto_price", user_id):
            return "Rate limit exceeded. Please wait before checking another price."

        # Check if API key is available
        if not COINMARKETCAP_API_KEY:
            return "CoinMarketCap API key not configured. Cannot fetch crypto prices."

        # VALIDATE inputs to prevent injection attacks
        if not self._validate_crypto_symbol(symbol):
            return f"Invalid cryptocurrency symbol: {symbol}"

        if not self._validate_currency_code(currency):
            return f"Invalid currency code: {currency}"

        try:
            # Use CoinMarketCap API
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            parameters = {"symbol": symbol.upper(), "convert": currency.upper()}
            headers = {
                "Accepts": "application/json",
                "X-CMC_PRO_API_KEY": COINMARKETCAP_API_KEY,
            }

            response = requests.get(url, headers=headers, params=parameters, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Parse the response
            if data.get("status", {}).get("error_code", 0) == 0:
                crypto_data = data["data"][symbol.upper()]
                price = crypto_data["quote"][currency.upper()]["price"]
                volume_24h = crypto_data["quote"][currency.upper()]["volume_24h"]
                market_cap = crypto_data["quote"][currency.upper()]["market_cap"]

                return f"Current {symbol.upper()} price: ${price:.6f} {currency.upper()}\n24h Volume: ${volume_24h:,.2f}\nMarket Cap: ${market_cap:,.2f}"
            else:
                error_message = data.get("status", {}).get(
                    "error_message", "Unknown error"
                )
                return f"Error getting crypto price: {error_message}"

        except requests.exceptions.RequestException as e:
            return f"Network error getting crypto price: {str(e)}"
        except KeyError as e:
            return f"Data format error: {str(e)}"
        except Exception as e:
            return f"Error getting crypto price: {str(e)}"

    def get_stock_price(self, symbol: str) -> str:
        """Get stock price using yfinance with rate limiting"""
        if not self._check_rate_limit("stock_price"):
            return "Rate limit exceeded. Please wait before checking another stock."

        try:
            stock = yf.Ticker(symbol)
            info = stock.info

            # Try to get current price
            if "currentPrice" in info:
                price = info["currentPrice"]
            elif "regularMarketPrice" in info:
                price = info["regularMarketPrice"]
            else:
                return f"Could not get price for {symbol}"

            return f"Current {symbol} price: ${price:.2f}"
        except Exception as e:
            return f"Error getting stock price for {symbol}: {str(e)}"

    def tip_user(
        self, user_id: str, amount: str, currency: str = "USD", message: str = ""
    ) -> str:
        """Tip a user through tip.cc with rate limiting and validation"""
        if not self._check_rate_limit("tip_user"):
            return "Rate limit exceeded. Please wait before tipping again."

        try:
            # Validate tip parameters using security framework
            try:
                import sys
                from pathlib import Path

                sys.path.insert(0, str(Path(__file__).parent.parent))
                from utils.security_validator import validator

                is_valid, error = validator.validate_tip_command(
                    f"<@{user_id}>", amount, currency, message
                )
                if not is_valid:
                    return f"Validation error: {error}"
            except ImportError:
                # Fallback validation
                if not user_id or not user_id.strip():
                    return "Invalid user ID"
                if not amount or not amount.strip():
                    return "Invalid amount"

            # Format the tip command safely
            recipient = f"<@{user_id.strip()}>"
            amount_safe = amount.strip()
            currency_safe = currency.upper().strip()
            message_safe = message.strip() if message else ""

            tip_command = f"$tip {recipient} {amount_safe} {currency_safe}"
            if message_safe:
                tip_command += f" {message_safe}"
            return f"Tip command prepared: {tip_command}\nPlease use this command in a channel where the tip.cc bot is active."

        except Exception as e:
            return f"Error preparing tip: {str(e)}"

    def check_balance(self, user_id: str) -> str:
        """Check balance through tip.cc with rate limiting"""
        if not self._check_rate_limit("check_balance"):
            return (
                "Rate limit exceeded. Please wait before checking your balance again."
            )

        try:
            # Format the balance command
            balance_command = "$balance"
            return f"Balance command prepared: {balance_command}\nPlease use this command in a channel where the tip.cc bot is active."

        except Exception as e:
            return f"Error preparing balance check: {str(e)}"

    def get_bonus_schedule(self, site: str, frequency: str) -> str:
        """Get bonus schedule information with rate limiting"""
        if not self._check_rate_limit("get_bonus_schedule"):
            return "Rate limit exceeded. Please wait before checking another schedule."

        # Convert to lowercase to ensure case-insensitive matching
        key = f"{site.lower()}_{frequency.lower()}"
        if key in self.bonus_schedules:
            return f"{site.title()} {frequency} bonus: {self.bonus_schedules[key]}"
        else:
            return f"No schedule found for {site} {frequency} bonus"

    def _web_search_html_fallback(self, query: str, instances: List[str]) -> str:
        """Fallback method to parse HTML results from SearXNG when JSON is not available"""
        try:
            import re

            from bs4 import BeautifulSoup

            # Try each instance for HTML parsing
            for instance in instances:
                try:
                    # Use public SearXNG instance for search (HTML format)
                    search_url = urljoin(instance, "search")

                    # Prepare search parameters for SearXNG (HTML format)
                    params = {
                        "q": query,
                        "categories": "general",
                        "engines": "google,bing,duckduckgo,brave",
                        "language": "en-US",
                    }

                    response = requests.get(search_url, params=params, timeout=15)

                    # Check if we got a successful response
                    if response.status_code == 200:
                        # Parse HTML content
                        soup = BeautifulSoup(response.content, "html.parser")

                        # Extract results from search result divs
                        result_divs = soup.find_all("div", class_="result")
                        if not result_divs:
                            # Try alternative class names
                            result_divs = soup.find_all(
                                "div", {"class": lambda x: x and "result" in x}
                            )

                        if result_divs:
                            results = []
                            for result_div in result_divs[:7]:  # Limit to top 7 results
                                try:
                                    # Extract title
                                    title_elem = (
                                        result_div.find("h3")
                                        or result_div.find("h4")
                                        or result_div.find("a")
                                    )
                                    title = (
                                        title_elem.get_text(strip=True)
                                        if title_elem
                                        else "No title"
                                    )

                                    # Extract URL
                                    url_elem = result_div.find("a", href=True)
                                    url = url_elem["href"] if url_elem else ""

                                    # Extract content/description
                                    content_elem = result_div.find(
                                        "p"
                                    ) or result_div.find("span", class_="content")
                                    content = (
                                        content_elem.get_text(strip=True)
                                        if content_elem
                                        else ""
                                    )

                                    # Limit content length
                                    if len(content) > 300:
                                        content = content[:300] + "..."

                                    if title and content:
                                        results.append(f"• {title}: {content} ({url})")
                                except:
                                    # Skip malformed results
                                    continue

                            if results:
                                return "\n".join(results)
                            # Continue to next instance if no valid results
                        # Continue to next instance if no results found
                    # Continue to next instance if HTTP error
                except:
                    # Continue to next instance if any error
                    continue

            # If all instances failed
            return f"No search results found for '{query}' after trying multiple public SearXNG instances."

        except Exception as e:
            return f"Error during HTML parsing fallback: {str(e)}"

    def web_search(self, query: str) -> str:
        """Perform real-time web searches using public SearXNG instances with fallback mechanism"""
        if not self._check_rate_limit("web_search"):
            return "Rate limit exceeded. Please wait before making another search."

        # VALIDATE query to prevent injection attacks
        if not self._validate_search_query(query):
            return "Invalid search query. Please check your input and try again."

        # List of public SearXNG instances (fallback mechanism)
        public_instances = [
            "https://searx.be",
            "https://metacat.online",
            "https://nyc1.sx.ggtyler.dev",
            "https://ooglester.com",
            "https://search.080609.xyz",
            "https://search.canine.tools",
            "https://search.catboy.house",
            "https://search.citw.lgbt",
            "https://search.einfachzocken.eu",
            "https://search.federicociro.com",
            "https://search.hbubli.cc",
            "https://search.im-in.space",
            "https://search.indst.eu",
        ]

        # Shuffle the instances for better distribution
        random.shuffle(public_instances)

        # Try each instance until one works
        for instance in public_instances:
            try:
                # Use public SearXNG instance for search
                search_url = urljoin(instance, "search")

                # Prepare search parameters for SearXNG
                params = {
                    "q": query,
                    "format": "json",
                    "categories": "general",
                    "engines": "google,bing,duckduckgo,brave",
                    "language": "en-US",
                }

                response = requests.get(search_url, params=params, timeout=15)

                # Check if we got a successful response
                if response.status_code == 200:
                    try:
                        data = response.json()

                        # Parse and format results
                        if "results" in data and data["results"]:
                            results = []
                            for result in data["results"][
                                :7
                            ]:  # Limit to top 7 results for better context
                                title = result.get("title", "No title")
                                content = (
                                    result.get("content", "")[:300] + "..."
                                    if len(result.get("content", "")) > 300
                                    else result.get("content", "")
                                )
                                url = result.get("url", "")
                                results.append(f"• {title}: {content} ({url})")

                            return "\n".join(results)
                        else:
                            # Try next instance
                            continue
                    except ValueError:
                        # JSON decode failed, try next instance
                        continue
                else:
                    # HTTP error, try next instance
                    continue

            except requests.exceptions.Timeout:
                # Timeout, try next instance
                continue
            except requests.exceptions.RequestException:
                # Other request error, try next instance
                continue
            except Exception:
                # Any other error, try next instance
                continue

        # If all instances failed, try HTML parsing as fallback
        return self._web_search_html_fallback(query, public_instances)

    def company_research(self, company_name: str) -> str:
        """Comprehensive company research tool using public SearXNG instances with fallback mechanism"""
        if not self._check_rate_limit("company_research"):
            return "Rate limit exceeded. Please wait before making another search."

        # List of public SearXNG instances (fallback mechanism)
        public_instances = [
            "https://searx.be",
            "https://metacat.online",
            "https://nyc1.sx.ggtyler.dev",
            "https://ooglester.com",
            "https://search.080609.xyz",
            "https://search.canine.tools",
            "https://search.catboy.house",
            "https://search.citw.lgbt",
            "https://search.einfachzocken.eu",
            "https://search.federicociro.com",
            "https://search.hbubli.cc",
            "https://search.im-in.space",
            "https://search.indst.eu",
        ]

        # Shuffle the instances for better distribution
        random.shuffle(public_instances)

        # Try each instance until one works
        for instance in public_instances:
            try:
                # Use public SearXNG instance for company research
                search_url = urljoin(instance, "search")

                # Prepare search parameters for company research
                params = {
                    "q": f"company {company_name}",
                    "format": "json",
                    "categories": "general",
                    "engines": "google,bing,duckduckgo,brave",
                    "language": "en-US",
                }

                response = requests.get(search_url, params=params, timeout=15)

                # Check if we got a successful response
                if response.status_code == 200:
                    try:
                        data = response.json()

                        # Parse and format results
                        if "results" in data and data["results"]:
                            results = []
                            for result in data["results"][
                                :7
                            ]:  # Limit to top 7 results for better context
                                title = result.get("title", "No title")
                                content = (
                                    result.get("content", "")[:300] + "..."
                                    if len(result.get("content", "")) > 300
                                    else result.get("content", "")
                                )
                                url = result.get("url", "")
                                results.append(f"• {title}: {content} ({url})")

                            return "\n".join(results)
                        else:
                            # Try next instance
                            continue
                    except ValueError:
                        # JSON decode failed, try next instance
                        continue
                else:
                    # HTTP error, try next instance
                    continue

            except requests.exceptions.Timeout:
                # Timeout, try next instance
                continue
            except requests.exceptions.RequestException:
                # Other request error, try next instance
                continue
            except Exception:
                # Any other error, try next instance
                continue

        # If all instances failed, try HTML parsing as fallback
        return self._web_search_html_fallback(
            f"company {company_name}", public_instances
        )

    def crawling(self, url: str, max_characters: int = 3000) -> str:
        """Extracts content from specific URLs using direct web scraping"""
        if not self._check_rate_limit("crawling"):
            return "Rate limit exceeded. Please wait before crawling another URL."

        try:
            # Use direct requests for content extraction
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # Use BeautifulSoup to parse HTML and extract text
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Limit to max_characters
            if len(text) > max_characters:
                text = text[:max_characters] + "..."

            return f"Content from {url}: {text}"

        except requests.exceptions.Timeout:
            return "URL crawling timed out. Try again later."
        except requests.exceptions.RequestException as e:
            return f"Error crawling URL: {str(e)}"
        except Exception as e:
            return f"Unexpected error during URL crawling: {str(e)}"

    def generate_image(
        self,
        prompt: str,
        model: str = "SDXL 1.0",
        width: int = 1024,
        height: int = 1024,
    ) -> str:
        """Generate an image using Arta API with rate limiting"""
        if not self._check_rate_limit("generate_image"):
            return "Rate limit exceeded. Please wait before generating another image."

        try:
            # Import image generator here to avoid circular imports
            from media.image_generator import image_generator

            # Generate the image
            image_url = image_generator.generate_image(
                prompt=prompt, model=model, width=width, height=height
            )

            return image_url

        except Exception as e:
            return f"Error generating image: {str(e)}"

    def analyze_image(self, image_url: str, prompt: str = "Describe this image") -> str:
        """Analyze an image using Pollinations API vision capabilities with rate limiting"""
        if not self._check_rate_limit("analyze_image"):
            return "Rate limit exceeded. Please wait before analyzing another image."

        try:
            # Import pollinations API here to avoid circular imports
            from ai.pollinations import pollinations_api

            # Analyze the image
            result = pollinations_api.analyze_image(image_url, prompt)

            # Check if there was an error
            if "error" in result:
                return f"Error analyzing image: {result['error']}"

            # Extract the response text
            if "choices" in result and len(result["choices"]) > 0:
                response_text = result["choices"][0]["message"]["content"]
                return response_text
            else:
                return "No response from image analysis"

        except Exception as e:
            return f"Error analyzing image: {str(e)}"

    def calculate(self, expression: str) -> str:
        """Perform mathematical calculations and comparisons with rate limiting"""
        if not self._check_rate_limit("calculate"):
            return "Rate limit exceeded. Please wait before making another calculation."

        try:
            # Safe evaluation - allow basic math operations and comparison operators
            allowed_chars = set("0123456789+-*/().<>=! ")
            if not all(c in allowed_chars for c in expression):
                return "Error: Invalid characters in expression"

            # Use a safer evaluation method instead of eval
            import ast
            import operator

            # Supported operators for math and comparisons
            operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Mod: operator.mod,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }

            # Supported comparison operators
            comparison_operators = {
                ast.Gt: operator.gt,  # >
                ast.Lt: operator.lt,  # <
                ast.GtE: operator.ge,  # >=
                ast.LtE: operator.le,  # <=
                ast.Eq: operator.eq,  # ==
                ast.NotEq: operator.ne,  # !=
            }

            def eval_expr(expr):
                """
                Safe evaluation of mathematical expressions
                """

                def _eval(node):
                    if isinstance(node, ast.Constant):  # For Python 3.8+
                        return node.value
                    elif isinstance(node, ast.Num):  # For Python < 3.8
                        return node.n
                    elif isinstance(node, ast.BinOp):
                        left = _eval(node.left)
                        right = _eval(node.right)
                        return operators[type(node.op)](left, right)
                    elif isinstance(node, ast.Compare):
                        left = _eval(node.left)
                        comparators = [_eval(comp) for comp in node.comparators]
                        ops = [comparison_operators[type(op)] for op in node.ops]

                        # For chained comparisons like 1 < 2 < 3
                        result = True
                        current_left = left
                        for op, current_right in zip(ops, comparators):
                            result = result and op(current_left, current_right)
                            current_left = current_right
                        return result
                    elif isinstance(node, ast.UnaryOp):
                        operand = _eval(node.operand)
                        return operators[type(node.op)](operand)
                    else:
                        raise TypeError(node)

                try:
                    tree = ast.parse(expr, mode="eval")
                    return _eval(tree.body)
                except:
                    raise ValueError("Invalid expression")

            result = eval_expr(expression)
            return f"Result: {result}"
        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            return f"Error calculating expression: {str(e)}"

    def get_current_time(self, timezone: str = "UTC") -> str:
        """Get current time and date information for a specific timezone"""
        if not self._check_rate_limit("get_current_time"):
            return "Rate limit exceeded. Please wait before checking time again."

        try:
            # Common timezone aliases for ease of use
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
                "cet": "CET",
                "cest": "CET",
                "aest": "Australia/Sydney",
                "utc": "UTC",
            }

            # Convert alias to proper timezone name
            tz_name = timezone_aliases.get(timezone.lower(), timezone)

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

            # Get timezone offset info
            offset = now.strftime("%z")
            offset_hours = int(offset[:3])
            offset_minutes = int(offset[3:])
            if offset_hours >= 0:
                offset_str = f"UTC+{offset_hours}:{offset_minutes:02d}"
            else:
                offset_str = f"UTC{offset_hours}:{offset_minutes:02d}"

            # Build response
            response = f"Current time in {tz_name}:\n"
            response += f"Time: {time_str}\n"
            response += f"Date: {date_str}\n"
            response += f"ISO: {iso_str}\n"
            response += f"Day of Year: {day_of_year}\n"
            response += f"Week: {week_number}\n"
            response += f"Offset: {offset_str}"

            return response

        except Exception as e:
            return f"Error getting time: {str(e)}"

    def set_reminder(
        self,
        user_id: str,
        reminder_type: str,
        title: str,
        description: str,
        trigger_time: str,
        channel_id: str = None,
        recurring_pattern: str = None,
    ) -> str:
        """Set a new reminder with rate limiting"""
        if not self._check_rate_limit("set_reminder"):
            return "Rate limit exceeded. Please wait before setting another reminder."

        try:
            # Import db here to avoid circular imports
            from data.database import db

            # Validate trigger_time format (ISO 8601)
            try:
                import datetime

                datetime.datetime.fromisoformat(trigger_time.replace("Z", "+00:00"))
            except ValueError:
                return "Invalid trigger_time format. Please use ISO 8601 format (e.g., '2025-10-03T15:00:00Z')"

            # Create the reminder
            reminder_id = db.add_reminder(
                user_id,
                reminder_type,
                title,
                description,
                trigger_time,
                channel_id,
                recurring_pattern,
            )

            return f"✅ Reminder set successfully!\n• **Title**: {title}\n• **Description**: {description}\n• **Trigger Time**: {trigger_time}\n• **ID**: {reminder_id}"

        except Exception as e:
            return f"Error setting reminder: {str(e)}"

    def list_reminders(self, user_id: str) -> str:
        """List all pending reminders for a user with rate limiting"""
        if not self._check_rate_limit("list_reminders"):
            return "Rate limit exceeded. Please wait before listing reminders again."

        try:
            # Import db here to avoid circular imports
            from data.database import db

            reminders = db.get_user_reminders(user_id)

            if not reminders:
                return "📝 You have no pending reminders."

            response = f"📅 **Your Reminders** ({len(reminders)} total):\n\n"

            for reminder in reminders:
                status_emoji = "⏰" if reminder["status"] == "pending" else "✅"
                response += f"{status_emoji} **{reminder['title']}**\n"
                response += f"   • Description: {reminder['description']}\n"
                response += f"   • Due: {reminder['trigger_time']}\n"
                response += f"   • Type: {reminder['reminder_type']}\n"
                response += f"   • ID: {reminder['id']}\n\n"

            return response

        except Exception as e:
            return f"Error listing reminders: {str(e)}"

    def cancel_reminder(self, reminder_id: str, user_id: str) -> str:
        """Cancel a reminder by ID with rate limiting"""
        if not self._check_rate_limit("cancel_reminder"):
            return "Rate limit exceeded. Please wait before canceling another reminder."

        try:
            # Import db here to avoid circular imports
            from data.database import db

            # First check if the reminder exists and belongs to the user
            reminder = db.get_reminder(int(reminder_id))
            if not reminder:
                return f"❌ Reminder with ID {reminder_id} not found."

            if str(reminder["user_id"]) != user_id:
                return "❌ You can only cancel your own reminders."

            # Cancel the reminder
            db.update_reminder_status(int(reminder_id), "cancelled")

            return f"✅ Reminder '{reminder['title']}' has been cancelled."

        except Exception as e:
            return f"Error canceling reminder: {str(e)}"

    def check_due_reminders(self) -> str:
        """Check for due reminders and return formatted list with rate limiting"""
        if not self._check_rate_limit("check_due_reminders"):
            return (
                "Rate limit exceeded. Please wait before checking due reminders again."
            )

        try:
            # Import db here to avoid circular imports
            from data.database import db

            due_reminders = db.get_due_reminders()

            if not due_reminders:
                return "No reminders are currently due."

            response = f"🔔 **{len(due_reminders)} reminder(s) are due:**\n"

            for reminder in due_reminders:
                response += f"- **{reminder['title']}** (ID: {reminder['id']}, User: {reminder['user_id']})\n"
                response += f"  {reminder['description']}\n"
                response += f"  Due: {reminder['trigger_time']}\n\n"

            return response

        except Exception as e:
            return f"Error checking due reminders: {str(e)}"

    # Discord tool methods
    def discord_get_user_info(self) -> str:
        """Get information about the currently logged-in Discord user"""
        if not self._check_rate_limit("discord_get_user_info"):
            return "Rate limit exceeded for Discord user info request."

        try:
            if self.discord_tools is None:
                return "Discord tools not initialized. Bot may not be connected to Discord."

            result = self.discord_tools.get_user_info()
            if "error" in result:
                return f"Error getting Discord user info: {result['error']}"

            user = result["user"]
            return f"Discord User Info:\n- ID: {user['id']}\n- Username: {user['username']}\n- Display Name: {user['display_name']}\n- Created: {user['created_at']}"
        except Exception as e:
            return f"Error getting Discord user info: {str(e)}"

    def discord_list_guilds(self) -> str:
        """List all Discord servers/guilds the user is in"""
        if not self._check_rate_limit("discord_list_guilds"):
            return "Rate limit exceeded for Discord guilds list request."

        try:
            if self.discord_tools is None:
                return "Discord tools not initialized. Bot may not be connected to Discord."

            result = self.discord_tools.list_guilds()
            if "error" in result:
                return f"Error listing Discord guilds: {result['error']}"

            guilds = result["guilds"]
            response = f"Discord Guilds ({result['count']} total):\n"
            for guild in guilds:
                response += f"- {guild['name']} (ID: {guild['id']}, Members: {guild['member_count']})\n"

            return response
        except Exception as e:
            return f"Error listing Discord guilds: {str(e)}"

    def discord_list_channels(self, guild_id: Optional[str] = None) -> str:
        """List channels the user has access to, optionally filtered by guild"""
        if not self._check_rate_limit("discord_list_channels"):
            return "Rate limit exceeded for Discord channels list request."

        try:
            if self.discord_tools is None:
                return "Discord tools not initialized. Bot may not be connected to Discord."

            result = self.discord_tools.list_channels(guild_id)
            if "error" in result:
                return f"Error listing Discord channels: {result['error']}"

            channels = result["channels"]
            response = f"Discord Channels ({result['count']} total):\n"
            for channel in channels:
                response += f"- #{channel['name']} (ID: {channel['id']}, Guild: {channel['guild_name']})\n"

            return response
        except Exception as e:
            return f"Error listing Discord channels: {str(e)}"

    async def discord_read_channel(self, channel_id: str, limit: int = 50) -> str:
        """Read messages from a specific Discord channel"""
        logger.info(
            f"discord_read_channel called with channel_id={channel_id}, limit={limit}"
        )

        if not self._check_rate_limit("discord_read_channel"):
            logger.warning("Rate limit exceeded for discord_read_channel")
            return "Rate limit exceeded for Discord channel read request."

        try:
            if self.discord_tools is None:
                logger.error(
                    "Discord tools not initialized when discord_read_channel was called"
                )
                return "Discord tools not initialized. Bot may not be connected to Discord."

            logger.info(
                f"Calling discord_tools.read_channel with channel_id={channel_id}, limit={limit}"
            )
            result = await self.discord_tools.read_channel(channel_id, limit)
            logger.info(f"discord_tools.read_channel returned: {result}")
            logger.info(
                f"Result type: {type(result)}, Keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}"
            )

            if "error" in result:
                logger.error(f"Error in discord_read_channel result: {result['error']}")
                return f"Error reading Discord channel: {result['error']}"

            messages = result["messages"]
            channel_info = result["channel"]
            response = f"Channel: #{channel_info['name']} ({channel_info['id']})\n"
            response += f"Guild: {channel_info['guild_name']}\n"
            response += f"Messages ({result['count']} total):\n\n"

            for message in messages:
                timestamp = message["timestamp"].split("T")[0]  # Just the date part
                response += f"[{timestamp}] {message['author']['username']}: {message['content']}\n"
                if message["attachments"]:
                    response += f"  Attachments: {', '.join(message['attachments'])}\n"
                response += "\n"

            logger.info(
                f"Successfully formatted {len(messages)} messages from channel {channel_id}"
            )
            return response
        except Exception as e:
            logger.error(f"Exception in discord_read_channel: {str(e)}", exc_info=True)
            return f"Error reading Discord channel: {str(e)}"

    async def discord_search_messages(
        self,
        channel_id: str,
        query: str = "",
        author_id: Optional[str] = None,
        limit: int = 100,
    ) -> str:
        """Search for messages in a Discord channel by content, author, etc."""
        if not self._check_rate_limit("discord_search_messages"):
            return "Rate limit exceeded for Discord message search request."

        try:
            if self.discord_tools is None:
                return "Discord tools not initialized. Bot may not be connected to Discord."

            result = await self.discord_tools.search_messages(
                channel_id, query, author_id, limit
            )

            if "error" in result:
                return f"Error searching Discord messages: {result['error']}"

            messages = result["messages"]
            channel_info = result["channel"]
            response = f"Search Results in Channel: #{channel_info['name']} ({channel_info['id']})\n"
            response += f"Guild: {channel_info['guild_name']}\n"
            response += f"Query: '{result['query']}'\n"
            response += f"Found {result['count']} matching messages:\n\n"

            for message in messages:
                timestamp = message["timestamp"].split("T")[0]  # Just the date part
                response += f"[{timestamp}] {message['author']['username']}: {message['content']}\n"
                if message["attachments"]:
                    response += f"  Attachments: {', '.join(message['attachments'])}\n"
                response += "\n"

            return response
        except Exception as e:
            return f"Error searching Discord messages: {str(e)}"

    def discord_list_guild_members(
        self, guild_id: str, limit: int = 100, include_roles: bool = False
    ) -> str:
        """List members of a specific Discord guild/server"""
        if not self._check_rate_limit("discord_list_guild_members"):
            return "Rate limit exceeded for Discord guild members list request."

        try:
            if self.discord_tools is None:
                return "Discord tools not initialized. Bot may not be connected to Discord."

            result = self.discord_tools.list_guild_members(
                guild_id, limit, include_roles
            )
            if "error" in result:
                return f"Error listing Discord guild members: {result['error']}"

            members = result["members"]
            guild_info = result["guild"]
            response = f"Members of Guild: {guild_info['name']} ({guild_info['id']})\n"
            response += f"Total Members Listed: {result['count']}\n\n"

            for member in members:
                response += f"- {member['username']}#{member['discriminator']} (ID: {member['id']})\n"
                if include_roles and "roles" in member and member["roles"]:
                    role_names = [role["name"] for role in member["roles"]]
                    response += f"  Roles: {', '.join(role_names)}\n"

            return response
        except Exception as e:
            return f"Error listing Discord guild members: {str(e)}"

    async def discord_send_message(
        self, channel_id: str, content: str, reply_to_message_id: Optional[str] = None
    ) -> str:
        """Send a message to a specific Discord channel"""
        logger.info(
            f"discord_send_message called with channel_id={channel_id}, content='{content[:100]}...', reply_to_message_id={reply_to_message_id}"
        )

        if not self._check_rate_limit("discord_send_message"):
            logger.warning("Rate limit exceeded for Discord send message request.")
            return "Rate limit exceeded for Discord send message request."

        try:
            if self.discord_tools is None:
                logger.error(
                    "Discord tools not initialized when discord_send_message was called"
                )
                return "Discord tools not initialized. Bot may not be connected to Discord."

            logger.info(
                f"Calling discord_tools.send_message with channel_id={channel_id}, content='{content[:100]}...', reply_to_message_id={reply_to_message_id}"
            )
            result = await self.discord_tools.send_message(
                channel_id, content, reply_to_message_id
            )
            logger.info(f"discord_tools.send_message returned: {result}")

            if "error" in result:
                logger.error(f"Error in discord_send_message result: {result['error']}")
                return f"Error sending Discord message: {result['error']}"

            message = result["message"]
            logger.info(
                f"Successfully sent message to channel {message['channel_id']}, message ID: {message['id']}"
            )
            return f"✅ Message sent successfully!\nChannel: {message['channel_id']}\nMessage ID: {message['id']}\nContent: {message['content']}"
        except Exception as e:
            logger.error(f"Exception in discord_send_message: {str(e)}", exc_info=True)
            return f"Error sending Discord message: {str(e)}"

    async def discord_send_dm(self, user_id: str, content: str) -> str:
        """Send a direct message to a specific Discord user"""
        if not self._check_rate_limit("discord_send_dm"):
            return "Rate limit exceeded for Discord send DM request."

        try:
            if self.discord_tools is None:
                return "Discord tools not initialized. Bot may not be connected to Discord."

            result = await self.discord_tools.send_dm(user_id, content)
            if "error" in result:
                return f"Error sending Discord DM: {result['error']}"

            message = result["message"]
            return f"✅ DM sent successfully!\nRecipient ID: {message['recipient_id']}\nMessage ID: {message['id']}\nContent: {message['content']}"
        except Exception as e:
            return f"Error sending Discord DM: {str(e)}"

    def discord_get_user_roles(self, guild_id: Optional[str] = None) -> str:
        """Get roles for the currently logged-in user in a specific guild"""
        if not self._check_rate_limit("discord_get_user_roles"):
            return "Rate limit exceeded for Discord user roles request."

        try:
            if self.discord_tools is None:
                return "Discord tools not initialized. Bot may not be connected to Discord."

            result = self.discord_tools.get_user_roles(guild_id)
            if "error" in result:
                return f"Error getting Discord user roles: {result['error']}"

            user = result["user"]
            guild = result["guild"]
            roles = result["roles"]

            if not roles:
                return f"User {user['display_name']} has no roles in guild '{guild['name']}' (ID: {guild['id']})."

            role_list = "\n".join(
                [f"- {role['name']} (ID: {role['id']})" for role in roles]
            )
            return f"Discord User Roles in '{guild['name']}':\nUser: {user['display_name']} (ID: {user['id']})\nRoles ({result['role_count']}):\n{role_list}"
        except Exception as e:
            return f"Error getting Discord user roles: {str(e)}"

    def set_discord_tools(self, bot_client):
        """Initialize Discord tools with the bot client"""
        from .discord_tools import DiscordTools

        self.discord_tools = DiscordTools(bot_client)

    def get_user_rate_limit_status(self, user_id: str) -> str:
        """Get rate limiting status for a specific user"""
        if not RATE_LIMITING_ENABLED:
            return "Rate limiting is not enabled."

        try:
            stats = rate_limit_middleware.rate_limiter.get_user_stats(user_id)

            response = f"📊 **Rate Limit Status for User {user_id}**\n\n"
            response += f"🔥 Penalty Multiplier: {stats['penalty_multiplier']}x\n"
            response += f"⚠️ Total Violations: {stats['total_violations']}\n"
            response += f"🚨 Recent Violations (1h): {stats['recent_violations']}\n\n"

            if stats["current_usage"]:
                response += "**Current Usage:**\n"
                for operation, usage in stats["current_usage"].items():
                    response += f"• {operation}:\n"
                    for limit_type, data in usage.items():
                        percentage = data["percentage"]
                        emoji = (
                            "🟢"
                            if percentage < 50
                            else "🟡"
                            if percentage < 80
                            else "🔴"
                        )
                        response += f"  {emoji} {limit_type}: {data['current']}/{data['limit']} ({percentage:.1f}%)\n"
                    response += "\n"
            else:
                response += "No recent activity recorded.\n"

            return response
        except Exception as e:
            return f"Error getting rate limit status: {str(e)}"

    def get_system_rate_limit_stats(self) -> str:
        """Get overall system rate limiting statistics"""
        if not RATE_LIMITING_ENABLED:
            return "Rate limiting is not enabled."

        try:
            stats = rate_limit_middleware.rate_limiter.get_system_stats()

            response = f"📈 **System Rate Limit Statistics**\n\n"
            response += f"⏱️ Uptime: {stats['uptime_seconds']:.0f} seconds\n"
            response += f"📊 Total Requests: {stats['total_requests']}\n"
            response += f"⚠️ Total Violations: {stats['total_violations']}\n"
            response += f"🚀 Requests/Second: {stats['requests_per_second']:.2f}\n"
            response += f"👥 Active Users (1h): {stats['active_users_count']}\n"
            response += f"👤 Total Users: {stats['total_users_count']}\n"
            response += (
                f"🚨 Recent Violations (1h): {stats['recent_violations_count']}\n"
            )
            response += f"🔥 Users with Penalties: {stats['users_with_penalties']}\n"
            response += (
                f"⚡ Average Penalty: {stats['average_penalty_multiplier']:.2f}x\n"
            )

            # Calculate violation rate
            if stats["total_requests"] > 0:
                violation_rate = (
                    stats["total_violations"] / stats["total_requests"]
                ) * 100
                response += f"📉 Violation Rate: {violation_rate:.2f}%\n"

            return response
        except Exception as e:
            return f"Error getting system stats: {str(e)}"

    def reset_user_rate_limits(self, user_id: str) -> str:
        """Reset rate limits for a specific user (admin function)"""
        if not RATE_LIMITING_ENABLED:
            return "Rate limiting is not enabled."

        try:
            rate_limit_middleware.rate_limiter.reset_user_limits(user_id)
            return f"✅ Rate limits reset for user {user_id}"
        except Exception as e:
            return f"Error resetting user rate limits: {str(e)}"

    async def execute_tool(
        self, tool_name: str, arguments: Dict, user_id: str = "system"
    ) -> str:
        """Execute a tool by name with given arguments and improved error handling"""
        if tool_name not in self.tools:
            return f"Unknown tool: {tool_name}"

        # Handle parameter mapping for backward compatibility
        mapped_arguments = arguments.copy()
        if tool_name == "remember_user_info":
            if "key" in mapped_arguments and "information_type" not in mapped_arguments:
                mapped_arguments["information_type"] = mapped_arguments.pop("key")
            if "value" in mapped_arguments and "information" not in mapped_arguments:
                mapped_arguments["information"] = mapped_arguments.pop("value")
        elif tool_name == "get_bonus_schedule":
            # Handle case where AI calls with "platform" instead of separate "site" and "frequency"
            if (
                "platform" in mapped_arguments
                and "site" not in mapped_arguments
                and "frequency" not in mapped_arguments
            ):
                platform = mapped_arguments.pop("platform")
                # Parse platform string to extract site and frequency
                # Example: "shuffle weekly" -> site="shuffle", frequency="weekly"
                parts = platform.split()
                if len(parts) >= 2:
                    mapped_arguments["site"] = parts[0]
                    mapped_arguments["frequency"] = parts[1]
                elif len(parts) == 1:
                    # If only one part, assume it's the site and default to "weekly"
                    mapped_arguments["site"] = parts[0]
                    mapped_arguments["frequency"] = "weekly"

        # Add user_id to arguments for methods that support it
        if (
            tool_name in ["get_crypto_price", "get_stock_price"]
            and "user_id" not in mapped_arguments
        ):
            mapped_arguments["user_id"] = user_id

        try:
            tool_func = self.tools[tool_name]
            # Check if the function is a coroutine function
            import asyncio

            if asyncio.iscoroutinefunction(tool_func):
                return await tool_func(**mapped_arguments)
            else:
                return tool_func(**mapped_arguments)
        except TypeError as e:
            return f"Error executing {tool_name}: Parameter mismatch - {str(e)}"
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"


# Async helper functions for MCP operations
import asyncio


async def _run_mcp_with_context(
    user_id: str, information_type: str, information: str
) -> Dict[str, Any]:
    """Run MCP memory operation with proper context management"""
    from tools.mcp_memory_client import MCPMemoryClient

    async with MCPMemoryClient() as client:
        return await client.remember_user_info(user_id, information_type, information)


async def _run_mcp_search_with_context(
    user_id: str, query: Optional[str] = None
) -> Dict[str, Any]:
    """Run MCP memory search with proper context management"""
    from tools.mcp_memory_client import MCPMemoryClient

    async with MCPMemoryClient() as client:
        return await client.search_user_memory(user_id, query)


# Global tool manager instance
tool_manager = ToolManager()

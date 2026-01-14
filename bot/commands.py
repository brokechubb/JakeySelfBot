import asyncio
import logging
import math
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
import pytz
from discord.ext import commands

from ai.openrouter import openrouter_api
from config import ADMIN_USER_IDS
from data.database import db
from media.image_generator import image_generator
from utils import random_indian_generator
from utils.helpers import send_long_message

# Configure logging
from utils.logging_config import get_logger

logger = get_logger(__name__)


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
        f"Command {command_name} error for user {ctx.author.id}: {type(error).__name__}: {str(error)}"
    )

    # Return user-friendly message
    return f"💀 **Command failed:** {sanitized_msg}"


def is_admin(user_id):
    """
    Securely check if a user is an admin with exact matching and validation.

    SECURITY FIXES:
    - Exact string matching instead of substring matching
    - Input validation and sanitization
    - Logging for admin access attempts
    - Type safety checks
    """
    try:
        # Input validation - ensure user_id is a valid integer
        if user_id is None:
            logger.warning(f"ADMIN_CHECK: None user_id provided")
            return False

        # Convert to string and validate it's a proper Discord user ID (17-19 digit number)
        user_id_str = str(user_id).strip()

        # Validate Discord user ID format (should be 17-19 digits)
        if not user_id_str.isdigit() or not (17 <= len(user_id_str) <= 19):
            logger.warning(f"ADMIN_CHECK: Invalid user ID format: {user_id_str}")
            return False

        # Check if ADMIN_USER_IDS is configured
        if not ADMIN_USER_IDS or not ADMIN_USER_IDS.strip():
            logger.warning("ADMIN_CHECK: No admin user IDs configured")
            return False

        # Parse admin IDs with validation
        admin_ids = []
        for admin_id in ADMIN_USER_IDS.split(","):
            admin_id = admin_id.strip()
            if admin_id and admin_id.isdigit() and (17 <= len(admin_id) <= 19):
                admin_ids.append(admin_id)
            elif admin_id:  # Non-empty but invalid
                logger.warning(f"ADMIN_CHECK: Invalid admin ID in config: {admin_id}")

        if not admin_ids:
            logger.warning("ADMIN_CHECK: No valid admin IDs found in configuration")
            return False

        # EXACT MATCHING - This fixes the substring matching vulnerability
        is_admin_result = user_id_str in admin_ids

        # Log admin access attempts (both successful and failed)
        if is_admin_result:
            logger.info(
                f"ADMIN_CHECK: ✅ Admin access granted for user ID: {user_id_str}"
            )
        else:
            logger.warning(
                f"ADMIN_CHECK: ❌ Admin access denied for user ID: {user_id_str}"
            )

        return is_admin_result

    except Exception as e:
        # Log any unexpected errors during admin check
        logger.error(
            f"ADMIN_CHECK: Error during admin verification for user_id {user_id}: {str(e)}"
        )
        return False


def is_admin_with_role_check(ctx):
    """
    Enhanced admin verification that includes Discord role checking.
    Provides additional security layer by checking both user ID and server roles.
    """
    try:
        # First check user ID (primary method)
        if not is_admin(ctx.author.id):
            return False

        # If in a guild, also check for admin roles (additional security)
        if ctx.guild:
            # Get member object with roles
            member = ctx.guild.get_member(ctx.author.id) or ctx.guild.fetch_member(
                ctx.author.id
            )

            if member and member.roles:
                # Check for common admin role names
                admin_role_keywords = [
                    "admin",
                    "administrator",
                    "moderator",
                    "mod",
                    "owner",
                    "staff",
                    "manager",
                    "op",
                    "operator",
                ]

                role_names = [
                    role.name.lower()
                    for role in member.roles
                    if role.name != "@everyone"
                ]
                has_admin_role = any(
                    keyword in role_name
                    for keyword in admin_role_keywords
                    for role_name in role_names
                )

                if has_admin_role:
                    logger.info(
                        f"ADMIN_ROLE_CHECK: ✅ User {ctx.author.id} has admin role in guild {ctx.guild.id}"
                    )
                else:
                    logger.info(
                        f"ADMIN_ROLE_CHECK: ⚠️ User {ctx.author.id} is admin by ID but no admin role in guild {ctx.guild.id}"
                    )

        return True

    except Exception as e:
        logger.error(
            f"ADMIN_ROLE_CHECK: Error during role verification for user {ctx.author.id}: {str(e)}"
        )
        # Fall back to basic admin check if role check fails
        return is_admin(ctx.author.id)


def setup_commands(bot):
    """Register all commands with the bot instance - Complete AGENTS.md Compliance"""

    # ==========================================
    # CORE COMMANDS (8 commands)
    # ==========================================

    @bot.command(name="ping")
    async def ping(ctx):
        """Simple ping command"""
        # Fix for NaN latency issue
        if hasattr(bot, "latency") and bot.latency is not None:
            if not math.isnan(bot.latency):
                latency = round(bot.latency * 1000)
            else:
                latency = 0
        else:
            latency = 0

        await ctx.send(f"🏓 **Pong!** {latency}ms - Jakey's ready to rig some games 💀")

    @bot.command(name="help")
    async def help(ctx):
        """Show help information about Jakey's commands"""
        help_text = """**💀 JAKEY BOT HELP 💀**

 **🕹️ CORE COMMANDS:**
 `%ping` - Check if Jakey is alive
 `%help` - Show this help message
 `%stats` - Show bot statistics and uptime
 `%time [timezone]` - Show current time and date (supports timezones)
 `%date [timezone]` - Show current date (alias for time command)

 **🧠 MEMORY COMMANDS:**
 `%memories [query]` - Search your memories that Jakey has saved from conversations
 `%remember <type> <info>` - Remember important information about you
 `%models` - List all available AI models
 `%imagemodels` - List all 49 artistic image styles
 `%aistatus` - Check Pollinations AI service status

 **🧠 MEMORY & USER COMMANDS:**
 `%friends` - List Jakey's friends (self-bot feature)
 `%clearhistory [user]` - Clear conversation history for a user

 **🎭 REACTION ROLES:**
 `%show_gender_roles` - Show current gender role mappings

 **🎰 GAMBLING & FUN COMMANDS:**
 `%rigged` - Classic Jakey response
 `%wen <item>` - Get bonus schedule information (monthly, stake, shuffle, payout)
 `%keno [count]` - Generate random Keno numbers (1-10 numbers from 1-40, optional count parameter) with visual board
 `%ind_addr` - Generate a random Indian name and address

 **🎨 AI & MEDIA COMMANDS:**
 `%image <prompt>` - Generate an image with artistic styles (supports 49 styles, 9 ratios)
 `%audio <text>` - Generate audio from text using AI voices
 `%analyze <image_url> [prompt]` - Analyze an image (or attach an image)

 **🧠 TRIVIA DATABASE COMMANDS:**
 `%triviacats` - List all available trivia categories
 `%triviasearch <query> [category]` - Search trivia questions

 **💥 EXAMPLES:**
 `%time` - Current time in UTC
 `%time est` - Current time in US Eastern
 `%time Europe/London` - Current time in London
 `%remember favorite_team Dallas Cowboys`
 `%keno [count]` - Generate your lucky Keno numbers (optional count 1-10)
 `%image Fantasy Art a degenerate gambler at a casino`
 `%image 16:9 cinematic a slot machine winning big`
 `%analyze https://example.com/image.jpg What is in this image?`
 `%analyze` (with image attachment) - Analyze attached image

 **⏰ REMINDER EXAMPLES (just ask Jakey):**
 `remind me in 2 hours to take a break`
 `set alarm for 8am tomorrow morning`
 `timer 25 minutes for pomodoro`
 `remind me next Friday at 3pm about the meeting`
 `check my reminders` - List all your pending reminders
 `cancel reminder 123` - Cancel a specific reminder
 """

        # Split into multiple messages if too long
        if len(help_text) > 1900:
            lines = help_text.split("\n")
            current_message = ""

            for line in lines:
                if len(current_message + line + "\n") > 1900:
                    await ctx.send(current_message)
                    current_message = line + "\n"
                else:
                    current_message += line + "\n"

            if current_message:
                await ctx.send(current_message)
        else:
            await ctx.send(help_text)

    @bot.command(name="adminhelp")
    async def adminhelp(ctx):
        """Show help information about admin commands - admin only"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        help_text = """**💀 JAKEY ADMIN HELP 💀**

 **🤖 AI MANAGEMENT COMMANDS:**
 `%model [model_name]` - Show or set current AI model
 `%fallbackstatus` - Show OpenRouter fallback restoration status
 `%queuestatus` - Show message queue status and statistics
 `%processqueue` - Manually trigger queue processing

 **🧠 USER & CHANNEL COMMANDS:**
 `%userinfo [user]` - Get information about a user
 `%clearallhistory` - Clear ALL conversation history
 `%clearchannelhistory` - Clear conversation history for current channel
 `%clearmemories` - Clear all your stored memories (cannot be undone)
 `%memorystatus` - Show your memory statistics and system status
 `%channelstats` - Show conversation statistics for current channel

 **🎭 REACTION ROLES:**
 `%add_reaction_role <message_id> <emoji> <@role>` - Add a reaction role to a message
 `%remove_reaction_role <message_id> <emoji>` - Remove a reaction role from a message
 `%list_reaction_roles` - List all reaction roles in the server

 **🚻 GENDER ROLES:**
 `%set_gender_roles <gender:role_id,...>` - Set gender role mappings (e.g., male:123456789,female:987654321)
 `%show_gender_roles` - Show current gender role mappings

 **🔑 KEYWORD COMMANDS:**
 `%add_keyword <keyword>` - Add a keyword Jakey will respond to
 `%remove_keyword <keyword>` - Remove a keyword
 `%enable_keyword <keyword>` - Enable a disabled keyword
 `%disable_keyword <keyword>` - Disable a keyword without removing it
 `%list_keywords` - List all configured keywords

 **💰 TIP.CC COMMANDS:**
 `%tip <user> <amount> <currency> [message]` - Send a tip to a user
 `%airdrop <amount> <currency> [for] <duration>` - Create an airdrop
 `%bal` / `%bals` - Check tip.cc balances and auto-dismiss response
 `%confirm` - Manually click Confirm button on tip.cc confirmation messages
 `%transactions [limit]` - Show recent tip.cc transaction history
 `%tipstats` - Show tip.cc statistics and earnings
 `%airdropstatus` - Show current airdrop configuration and status

 **🧠 TRIVIA COMMANDS:**
 `%seedtrivia` - Seed trivia database from external sources
 `%addtrivia <category> <question> <answer>` - Add custom trivia question
 `%triviastats` - Show trivia database statistics and health

 **🔧 MISC COMMANDS:**
 `%models` - List all available AI models
 `%imagemodels` - List all 49 artistic image styles
 `%aistatus` - Check Pollinations AI service status
 `%clearcache` - Clear the model capabilities cache
 """

        # Split into multiple messages if too long
        if len(help_text) > 1900:
            lines = help_text.split("\n")
            current_message = ""

            for line in lines:
                if len(current_message + line + "\n") > 1900:
                    await ctx.send(current_message)
                    current_message = line + "\n"
                else:
                    current_message += line + "\n"

            if current_message:
                await ctx.send(current_message)
        else:
            await ctx.send(help_text)

    @bot.command(name="stats")
    async def stats(ctx):
        """Show bot statistics and information"""
        try:
            # Get database stats
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()

            # Count users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]

            # Count conversations
            cursor.execute("SELECT COUNT(*) FROM conversations")
            conversation_count = cursor.fetchone()[0]

            # Count memories
            cursor.execute("SELECT COUNT(*) FROM memories")
            memory_count = cursor.fetchone()[0]

            conn.close()

            # Get latency (fixed for NaN issue)
            if hasattr(bot, "latency") and bot.latency is not None:
                if not math.isnan(bot.latency):
                    latency = round(bot.latency * 1000)
                else:
                    latency = 0
            else:
                latency = 0

            # Get uptime (approximate)
            import time

            if hasattr(bot, "_start_time"):
                uptime_seconds = int(time.time() - bot._start_time)
                hours = uptime_seconds // 3600
                minutes = (uptime_seconds % 3600) // 60
                seconds = uptime_seconds % 60
                uptime_str = f"{hours}h {minutes}m {seconds}s"
            else:
                uptime_str = "Unknown"
                bot._start_time = time.time()

            response = f"**💀 JAKEY BOT STATS 💀**\n"
            response += f"⏱️ **Uptime:** {uptime_str}\n"
            response += f"📡 **Latency:** {latency}ms\n"
            response += f"👥 **Users:** {user_count}\n"
            response += f"💬 **Conversations:** {conversation_count}\n"
            response += f"🧠 **Memories:** {memory_count}\n"
            response += f"🏰 **Servers:** {len(bot.guilds)}\n"

            await ctx.send(response)
        except Exception as e:
            await ctx.send(f"💀 **Failed to get stats:** {str(e)}")

    @bot.command(name="time")
    async def time(ctx, timezone_name: Optional[str] = None):
        """Show current time and date (supports timezone)"""
        try:
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

            # Send long message without truncation
            await send_long_message(ctx.channel, response)

        except Exception as e:
            error_msg = f"💀 Failed to get time: {str(e)}"
            logger.error(error_msg)
            await ctx.send(error_msg)

    @bot.command(name="date")
    async def date(ctx, timezone_name: Optional[str] = None):
        """Show current date (alias for time command)"""
        # Just call the time command
        await time(ctx, timezone_name)

    # ==========================================
    # MEMORY COMMANDS (8 commands)
    # ==========================================

    @bot.command(name="memories")
    async def memories(ctx, *, query: str = ""):
        """Search your memories that Jakey has saved from conversations"""
        try:
            from config import AUTO_MEMORY_EXTRACTION_ENABLED
            from tools.memory_search import memory_search_tool

            if not AUTO_MEMORY_EXTRACTION_ENABLED:
                await ctx.send("💾 **Memory system is currently disabled**")
                return

            # Get memory search results
            result = await memory_search_tool.search_user_memories(
                str(ctx.author.id), query if query.strip() else None, limit=15
            )

            if result.get("error"):
                await ctx.send(f"💀 **Memory search error:** {result['error']}")
                return

            if result.get("success") and result.get("total_memories", 0) > 0:
                memories = result["all_memories"]
                grouped = result["grouped_memories"]

                response = f"**🧠 Found {len(memories)} memories"
                if query:
                    response += f" for: `{query}`"
                response += "**\n\n"

                # Group memories by type for better organization
                for mem_type, memory_list in grouped.items():
                    if memory_list:
                        type_display = mem_type.replace("_", " ").title()
                        response += f"**{type_display}** ({len(memory_list)}):\n"
                        for memory in memory_list[:5]:  # Limit to 5 per type
                            category = memory["category"].replace("_", " ").title()
                            response += f"  • {category}: {memory['information']}\n"
                        if len(memory_list) > 5:
                            response += (
                                f"  • ... and {len(memory_list) - 5} more {mem_type}\n"
                            )
                        response += "\n"

                await ctx.send(response)
            else:
                if query:
                    await ctx.send(
                        f"🔍 **No memories found** matching: `{query}`\n\nI'll remember important things from our conversations!"
                    )
                else:
                    await ctx.send(
                        "🧠 **No memories stored yet**\n\nI'll start remembering things as we chat!"
                    )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "memories"))

    @bot.command(name="clearmemories")
    async def clearmemories(ctx):
        """Clear all your stored memories (cannot be undone)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            from config import AUTO_MEMORY_EXTRACTION_ENABLED
            from memory import memory_backend

            if not AUTO_MEMORY_EXTRACTION_ENABLED:
                await ctx.send("💾 **Memory system is currently disabled**")
                return

            # Count memories before deletion
            if memory_backend is None:
                await ctx.send("💀 **Memory backend not available**")
                return

            memories_before = await memory_backend.get_all(str(ctx.author.id))
            memory_count = len(memories_before)

            if memory_count == 0:
                await ctx.send("🧠 **No memories to clear**")
                return

            # Delete all memories for the user
            import asyncio

            success = await memory_backend.delete(str(ctx.author.id))

            if success:
                await ctx.send(
                    f"🗑️ **Cleared {memory_count} memories**\n\nI'll start learning about you again from our future conversations!"
                )
            else:
                await ctx.send(
                    "💀 **Failed to clear memories**\n\nPlease try again later."
                )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "clearmemories"))

    @bot.command(name="memorystatus")
    async def memorystatus(ctx):
        """Show your memory statistics and system status"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            from config import (
                AUTO_MEMORY_CLEANUP_ENABLED,
                AUTO_MEMORY_EXTRACTION_ENABLED,
                AUTO_MEMORY_MAX_AGE_DAYS,
            )
            from memory import memory_backend

            response = "🧠 **Memory System Status**\n\n"

            # System status
            response += f"**🔧 System Settings:**\n"
            response += f"• Auto-extraction: {'✅ Enabled' if AUTO_MEMORY_EXTRACTION_ENABLED else '❌ Disabled'}\n"
            response += f"• Auto-cleanup: {'✅ Enabled' if AUTO_MEMORY_CLEANUP_ENABLED else '❌ Disabled'}\n"
            response += f"• Max age: {AUTO_MEMORY_MAX_AGE_DAYS} days\n\n"

            if not AUTO_MEMORY_EXTRACTION_ENABLED:
                await ctx.send(
                    response
                    + "💾 **Memory extraction is disabled**\n\nEnable `AUTO_MEMORY_EXTRACTION_ENABLED=true` to activate learning."
                )
                return

            if memory_backend is None:
                await ctx.send(response + "❌ **Memory backend not available**")
                return

            # Get user's memory count
            import asyncio

            memories = await memory_backend.get_all(str(ctx.author.id))
            memory_count = len(memories)

            response += f"**📊 Your Memories:**\n"
            response += f"• Total stored: {memory_count}\n"

            # Memory breakdown by type
            if memory_count > 0:
                type_counts = {}
                for key in memories.keys():
                    mem_type = key.split("_", 1)[0] if "_" in key else "misc"
                    type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

                for mem_type, count in sorted(
                    type_counts.items(), key=lambda x: x[1], reverse=True
                ):
                    type_display = mem_type.replace("_", " ").title()
                    response += f"• {type_display}: {count}\n"
            else:
                response += "• No memories stored yet\n"

            # System health
            try:
                import asyncio

                health = await memory_backend.health_check()
                healthy_backends = sum(health.values())
                total_backends = len(health)

                response += f"\n**🏥 System Health:**\n"
                response += f"• Backends healthy: {healthy_backends}/{total_backends}\n"

                for backend, is_healthy in health.items():
                    status = "✅" if is_healthy else "❌"
                    response += f"• {backend.title()}: {status}\n"

            except Exception as e:
                response += f"\n**🏥 System Health:** Unable to check\n"

            await ctx.send(response)

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "memorystatus"))

    @bot.command(name="model")
    async def model(ctx, model_name: Optional[str] = None):
        """Show or set the current AI model (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        if model_name is None:
            # Show current model and available models
            current_model = (
                bot.current_model if hasattr(bot, "current_model") else "Not set"
            )
            await ctx.send(
                f"🤖 **Current model:** {current_model}\nUse `%model <model_name>` to change it."
            )
            return

        try:
            # Validate the model by checking if it exists in available models
            try:
                available_models = openrouter_api.list_models()
            except:
                available_models = [
                    "nvidia/nemotron-nano-9b-v2:free",
                    "deepseek/deepseek-chat-v3.1:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                ]

            if model_name in available_models:
                bot.current_model = model_name
                logger.info(f"Model changed to: {model_name} (user: {ctx.author.id})")
                await ctx.send(f"💀 **Model updated to:** {model_name}")
            else:
                await ctx.send(
                    f"💀 **Model '{model_name}' not found.** Use `%models` to see available models."
                )

        except Exception as e:
            await ctx.send(f"💀 **Failed to set model:** {str(e)}")

    @bot.command(name="models")
    async def models(ctx):
        """List all available AI models with enhanced information"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            await ctx.message.add_reaction("🧠")
        except discord.NotFound:
            # Message was deleted, ignore gracefully
            pass
        except discord.Forbidden:
            # Bot doesn't have permission to add reactions
            pass

        try:
            # Recommended models for Jakey (best tool calling + conversation)
            # Excluded: nvidia/nemotron-3-nano-30b-a3b (exposes thinking in reasoning field)
            # Excluded: kwaipilot/kat-coder-pro (coding-focused, not ideal for chat)
            recommended_models = [
                ("meta-llama/llama-3.3-70b-instruct:free", "⭐ Jakey's default - reliable, clean responses"),
                ("google/gemma-3-27b-it:free", "Multimodal, 140 languages, solid tool calling"),
                ("mistralai/mistral-small-3.1-24b-instruct:free", "Fast responses, good for conversation"),
                ("xiaomi/mimo-v2-flash:free", "Fast reasoning model with good instruction following"),
                ("nex-agi/deepseek-v3.1-nex-n1:free", "DeepSeek variant optimized for instruction following"),
                ("nvidia/nemotron-nano-12b-v2-vl:free", "NVIDIA's compact multimodal model"),
                ("nvidia/nemotron-nano-9b-v2:free", "NVIDIA's compact 9B instruction model"),
                ("openai/gpt-oss-120b:free", "Large 120B parameter open-source model"),
                ("mistralai/devstral-2512:free", "Mistral's development model, good for coding tasks"),
            ]

            response = "**🤖 RECOMMENDED MODELS FOR JAKEY**\n"
            response += "*Models tested for clean responses and tool calling*\n\n"

            response += "**Recommended:**\n"
            for model, desc in recommended_models:
                response += f"• `{model}`\n  └─ {desc}\n"

            response += "\n**Image Styles (Arta API):**\n"
            response += "• **49 Artistic Styles** - Fantasy Art, Van Gogh, Photographic, Watercolor\n"
            response += "• **9 Aspect Ratios** - 1:1, 16:9, 3:2, etc.\n"
            response += "• Use `%imagemodels` for complete list\n"

            response += "\n**USAGE:**\n"
            response += "• `%model <model_name>` - Switch text model\n"
            response += "• `%image [style] <prompt>` - Generate image\n"

            await send_long_message(ctx.channel, response)

        except Exception as e:
            error_msg = f"💀 Failed to fetch models: {str(e)}"
            logger.error(error_msg)
            await ctx.send(error_msg)

        # Remove thinking reaction
        try:
            await ctx.message.remove_reaction("🧠", bot.user)
        except:
            pass  # Ignore if we can't remove the reaction

    @bot.command(name="imagemodels")
    async def imagemodels(ctx):
        """List all available image AI models (Arta artistic styles)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            # Import image generator
            from media.image_generator import image_generator

            # Get available models (styles)
            styles = image_generator.get_available_models()

            if not styles:
                await ctx.send("❌ No image styles available")
                return

            # Format response with all styles
            response = f"**🎨 Arta Image Styles ({len(styles)} total):**\n"

            # Group styles into columns for better readability
            for i in range(0, len(styles), 3):
                row_styles = styles[i : i + 3]
                row_text = "  ".join([f"`{style}`" for style in row_styles])
                response += row_text + "\n"

            response += "\n**Usage:** `%image [style] [prompt]`\n"
            response += "**Example:** `%image Fantasy Art a mystical castle`"

            # Split into multiple messages if too long
            if len(response) > 1900:
                lines = response.split("\n")
                current_message = ""

                for line in lines:
                    if len(current_message + line + "\n") > 1900:
                        await ctx.send(current_message)
                        current_message = line + "\n"
                    else:
                        current_message += line + "\n"

                if current_message:
                    await ctx.send(current_message)
            else:
                await ctx.send(response)

        except Exception as e:
            logger.error(f"Error listing image styles: {str(e)}")
            await ctx.send(handle_command_error(e, ctx, "list_image_styles"))

    @bot.command(name="aistatus")
    async def aistatus(ctx):
        """Check the status of AI service providers"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            await ctx.message.add_reaction("🔍")
        except discord.NotFound:
            # Message was deleted, ignore gracefully
            pass
        except discord.Forbidden:
            # Bot doesn't have permission to add reactions
            pass

        try:
            # Check service health for OpenRouter
            openrouter_health = openrouter_api.check_service_health()

            response = "**🤖 AI SERVICE STATUS**\n\n"

            # OpenRouter AI Status
            if openrouter_health["healthy"]:
                response += "✅ **OpenRouter AI**: Online and healthy\n"
                response += (
                    f"⚡ Response time: {openrouter_health['response_time']:.2f}s\n"
                )
            else:
                response += f"❌ **OpenRouter AI**: {openrouter_health.get('error', 'Unknown error')}\n"
                response += f"🔍 Status: `{openrouter_health.get('status', 'unknown')}`\n"

            # Check model availability from OpenRouter
            openrouter_models = []
            try:
                if openrouter_api.enabled:
                    openrouter_models = openrouter_api.list_models()
            except Exception as e:
                logger.error(f"Error getting OpenRouter models: {e}")

            response += "\n🤖 **Available Models:**\n"
            if openrouter_models:
                response += "**OpenRouter**: " + ", ".join(
                    openrouter_models[:10]
                )
                if len(openrouter_models) > 10:
                    response += f" (+{len(openrouter_models) - 10} more)"
            else:
                response += "**OpenRouter**: No models available"

            response += f"\n🔧 **Current model**: `{bot.current_model}`\n"
            
            # Add rate limit information
            try:
                rate_status = openrouter_api.check_rate_limits()
                limits = rate_status.get("limits")
                
                response += "\n📊 **Rate Limits:**\n"
                response += f"• Per-minute: {rate_status['requests_per_min']}/{rate_status['rate_limit_per_min']}\n"
                
                if limits:
                    tier = "Free" if limits.get("is_free_tier") else "Paid"
                    response += f"• Tier: {tier}\n"
                    response += f"• Free requests today: {limits.get('free_requests_today', 0)}/{limits.get('free_requests_limit', '?')}\n"
                    response += f"• Remaining: {limits.get('free_requests_remaining', '?')}\n"
                    
                    if limits.get("usage_daily"):
                        response += f"• Credits used today: {limits.get('usage_daily', 0):.4f}\n"
                
                if not rate_status["can_request"]:
                    response += f"\n⚠️ **Rate Limited:** {rate_status['reason']}\n"
                    
            except Exception as e:
                logger.debug(f"Could not get rate limit info: {e}")

            await ctx.send(response)

        except Exception as e:
            logger.error(f"Error checking AI status: {str(e)}")
            await ctx.send(handle_command_error(e, ctx, "ai_status"))

    @bot.command(name="fallbackstatus")
    async def fallbackstatus(ctx):
        """Show current fallback restoration status (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            if hasattr(bot, "get_fallback_status"):
                status = bot.get_fallback_status()

                from config import (
                    OPENROUTER_FALLBACK_RESTORE_ENABLED,
                    OPENROUTER_FALLBACK_TIMEOUT,
                )

                response = f"🔄 **Fallback Restoration Status:**\n\n"
                response += f"**Current Provider:** {status['current_provider']}\n"
                response += f"**Current Model:** {status['current_model']}\n"
                response += f"**Auto-Restore Enabled:** {'✅ Yes' if OPENROUTER_FALLBACK_RESTORE_ENABLED else '❌ No'}\n"
                response += (
                    f"**Restore Timeout:** {OPENROUTER_FALLBACK_TIMEOUT} seconds\n\n"
                )

                if status["is_fallback_active"]:
                    response += "🔴 **Status:** Currently using OpenRouter fallback\n"
                    if status["fallback_start_time"]:
                        import time

                        elapsed = status.get("fallback_elapsed_seconds", 0)
                        remaining = status.get("fallback_remaining_seconds", 0)
                        progress = status.get("fallback_progress_percent", 0)

                        response += f"⏱️ **Fallback Duration:** {elapsed:.0f}s elapsed\n"
                        response += (
                            f"⏳ **Time Until Restore:** {remaining:.0f}s remaining\n"
                        )
                        response += f"📊 **Progress:** {progress:.1f}%\n"
                        response += f"🔄 **Original Model:** {status.get('original_model', 'Unknown')}\n"
                else:
                    response += "✅ **Status:** Using primary provider (Pollinations)\n"

                await ctx.send(response)
            else:
                await ctx.send(
                    "💀 **Fallback status not available** - feature may be disabled"
                )

        except Exception as e:
            await ctx.send(f"💀 **Failed to get fallback status:** {str(e)}")

    @bot.command(name="queuestatus")
    async def queuestatus(ctx):
        """Show message queue status and statistics (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            from config import MESSAGE_QUEUE_ENABLED

            if not MESSAGE_QUEUE_ENABLED:
                await ctx.send("💀 **Message queue is disabled**")
                return

            if (
                not hasattr(bot, "message_queue_integration")
                or not bot.message_queue_integration
            ):
                await ctx.send("💀 **Message queue integration not available**")
                return

            # Get queue statistics
            queue_integration = bot.message_queue_integration

            # Get queue stats
            if (
                hasattr(queue_integration, "message_queue")
                and queue_integration.message_queue
            ):
                stats = await queue_integration.message_queue.get_queue_stats()

                response = f"📊 **Message Queue Status:**\n\n"
                response += f"**Enabled:** ✅ Yes\n"
                response += f"**Total Messages:** {stats.get('total_messages', 0)}\n"
                response += f"**Pending:** {stats.get('pending_messages', 0)}\n"
                response += f"**Processing:** {stats.get('processing_messages', 0)}\n"
                response += f"**Completed:** {stats.get('completed_messages', 0)}\n"
                response += f"**Failed:** {stats.get('failed_messages', 0)}\n"
                response += f"**Dead Letter:** {stats.get('dead_letter_messages', 0)}\n"

                # Add queue age information
                if stats.get("oldest_message_age"):
                    age_seconds = stats["oldest_message_age"]
                    if age_seconds > 60:
                        age_minutes = age_seconds / 60
                        response += (
                            f"**Oldest Message:** {age_minutes:.1f} minutes old\n"
                        )
                    else:
                        response += (
                            f"**Oldest Message:** {age_seconds:.0f} seconds old\n"
                        )

                response += "\n"

                # Processing stats
                if (
                    hasattr(queue_integration, "processor")
                    and queue_integration.processor
                ):
                    proc_stats = queue_integration.processor.get_stats()
                    if isinstance(proc_stats, dict) and "overall" in proc_stats:
                        overall = proc_stats["overall"]
                        response += f"**🔄 Processing Stats:**\n"
                        response += f"Processed: {overall.get('processed_count', 0)}\n"
                        response += f"Success Rate: {overall.get('success_rate', 0) * 100:.1f}%\n"
                        response += f"Avg Time: {overall.get('average_processing_time', 0):.2f}s\n"
                        response += (
                            f"Rate: {overall.get('messages_per_second', 0):.1f} msg/s\n"
                        )

                        # Add recent performance if available
                        if "recent" in proc_stats:
                            recent = proc_stats["recent"]
                            response += f"Recent Success Rate: {recent.get('success_rate', 0) * 100:.1f}%\n"
                        response += "\n"

                # Health status
                if hasattr(queue_integration, "monitor") and queue_integration.monitor:
                    try:
                        health = queue_integration.monitor.get_health_status()
                        if isinstance(health, dict):
                            response += f"**🏥 Health Status:** {health.get('status', 'Unknown')}\n"

                            alerts = health.get("alerts", [])
                            if alerts:
                                response += f"**🚨 Alerts:** {len(alerts)} active\n"
                                # Show top 3 alerts
                                for alert in alerts[:3]:
                                    response += (
                                        f"  • {alert.get('message', 'Unknown alert')}\n"
                                    )
                            else:
                                response += "**🚨 Alerts:** None\n"
                    except Exception as e:
                        logger.warning(f"Failed to get queue health status: {e}")
                        response += "**🏥 Health Status:** Unavailable\n"

                await ctx.send(response)
            else:
                await ctx.send("💀 **Queue statistics not available**")

        except Exception as e:
            await ctx.send(f"💀 **Failed to get queue status:** {str(e)}")

    @bot.command(name="processqueue")
    async def processqueue(ctx):
        """Manually trigger queue processing (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            from config import MESSAGE_QUEUE_ENABLED

            if not MESSAGE_QUEUE_ENABLED:
                await ctx.send("💀 **Message queue is disabled**")
                return

            if (
                not hasattr(bot, "message_queue_integration")
                or not bot.message_queue_integration
            ):
                await ctx.send("💀 **Message queue integration not available**")
                return

            queue_integration = bot.message_queue_integration

            if (
                not hasattr(queue_integration, "processor")
                or not queue_integration.processor
            ):
                await ctx.send("💀 **Queue processor not available**")
                return

            # Manually trigger queue processing
            logger.info(f"Manual queue processing triggered by admin {ctx.author.id}")

            # Process one batch
            processed = await queue_integration.processor.process_batch()

            if processed > 0:
                await ctx.send(f"✅ **Processed {processed} messages from queue**")
            else:
                await ctx.send("ℹ️ **No messages to process in queue**")

        except Exception as e:
            logger.error(f"Manual queue processing failed: {e}")
            await ctx.send(f"💀 **Failed to process queue:** {str(e)}")

    # ==========================================
    # MEMORY & USER COMMANDS (7 commands)
    # ==========================================

    @bot.command(name="remember")
    async def remember(
        ctx, info_type: Optional[str] = None, *, info: Optional[str] = None
    ):
        """Remember important information about the user"""
        if info_type is None or info is None:
            await ctx.send(
                "💀 **Rigged.** Use `%remember <type> <info>` to remember something about you."
            )
            return

        try:
            # Store the information in the database
            user_id = str(ctx.author.id)
            bot.db.add_memory(user_id, info_type, info)
            await ctx.send(
                f"💀 **Got it!** I'll remember that your **{info_type}** is: {info}"
            )
        except Exception as e:
            await ctx.send(f"💀 **Failed to remember that info:** {str(e)}")

    @bot.command(name="friends")
    async def friends(ctx):
        """List Jakey's friends (self-bot specific feature)"""
        try:
            # Check if we have friends attribute (self-bot feature)
            if hasattr(bot, "friends"):
                friends_list = list(bot.friends)
                if friends_list:
                    friend_names = [
                        f"{friend.name}#{friend.discriminator}"
                        for friend in friends_list[:10]
                    ]  # Limit to 10
                    response = (
                        f"💀 Jakey's friends ({len(friends_list)} total):\n"
                        + "\n".join(friend_names)
                    )
                else:
                    response = "💀 Jakey has no friends... just like Eddie"
            else:
                response = "💀 Friends feature not available"
            await ctx.send(response)
        except Exception as e:
            await ctx.send(f"💀 Failed to get friends list: {str(e)}")

    @bot.command(name="userinfo")
    async def userinfo(ctx, user: Optional[discord.User] = None):
        """Get information about a user including their roles (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            target_user = user or ctx.author

            # Try to get member object with roles (works in guild context)
            try:
                if ctx.guild:
                    member = ctx.guild.get_member(
                        target_user.id
                    ) or await ctx.guild.fetch_member(target_user.id)
                    target_display = (
                        member.name if hasattr(member, "name") else target_user.name
                    )
                    response = f"💀 User Info for **{target_display}**:\n"
                    response += f"ID: {target_user.id}\n"
                    response += f"Display Name: {member.display_name if hasattr(member, 'display_name') else target_user.name}\n"
                    response += f"Bot: {'Yes' if target_user.bot else 'No'}\n"

                    # Add roles information
                    if hasattr(member, "roles") and member.roles:
                        # Skip @everyone role (first role by default)
                        role_names = (
                            [role.name for role in member.roles[1:]]
                            if len(member.roles) > 1
                            else []
                        )
                        if role_names:
                            response += (
                                f"Roles ({len(role_names)}): {', '.join(role_names)}\n"
                            )
                        else:
                            response += "Roles: None (excluding @everyone)\n"
                    else:
                        response += "Roles: Could not retrieve roles\n"
                else:
                    # DM context - no roles available
                    response = f"💀 User Info for **{target_user.name}**:\n"
                    response += f"ID: {target_user.id}\n"
                    response += f"Bot: {'Yes' if target_user.bot else 'No'}\n"
                    response += "Roles: Not available in DMs\n"

            except Exception as role_error:
                # Fallback if we can't get member info with roles
                response = f"💀 User Info for **{target_user.name}**:\n"
                response += f"ID: {target_user.id}\n"
                response += f"Bot: {'Yes' if target_user.bot else 'No'}\n"
                response += (
                    "Roles: Could not retrieve (user might not be in this server)\n"
                )

            await ctx.send(response)
        except Exception as e:
            await ctx.send(f"💀 Failed to get user info: {str(e)}")

    @bot.command(name="clearhistory")
    async def clearhistory(ctx, user: Optional[discord.User] = None):
        """Clear conversation history for a user"""
        try:
            # Determine which user's history to clear
            target_user = user or ctx.author
            target_user_id = str(target_user.id)

            # If trying to clear someone else's history, require admin rights
            if user and user != ctx.author:
                # Check if user is admin
                if not is_admin(ctx.author.id):
                    await ctx.send(
                        "💀 Admin only command bro! You can only clear your own history."
                    )
                    return

            # Clear the user's history
            bot.db.clear_user_history(target_user_id)
            await ctx.send(f"💀 History cleared for {target_user.name}. Fresh start!")

        except Exception as e:
            await ctx.send(f"💀 Failed to clear history: {str(e)}")

    @bot.command(name="clearallhistory")
    async def clearallhistory(ctx):
        """Clear ALL conversation history (admin/debug only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            await ctx.send(
                "💀 Clearing ALL history... hope you know what you're doing!"
            )

            # Clear all history
            bot.db.clear_all_history()
            await ctx.send("💀 ALL history cleared. Fresh slate for everyone!")

        except Exception as e:
            await ctx.send(f"💀 Failed to clear all history: {str(e)}")

    @bot.command(name="clearchannelhistory")
    async def clearchannelhistory(ctx):
        """Clear conversation history for the current channel (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            channel_id = str(ctx.channel.id)
            await ctx.send(f"💀 Clearing conversation history for this channel...")

            # Clear channel history
            bot.db.clear_channel_history(channel_id)
            await ctx.send(f"💀 Channel history cleared for {ctx.channel.name}!")

        except Exception as e:
            await ctx.send(f"💀 Failed to clear channel history: {str(e)}")

    @bot.command(name="channelstats")
    async def channelstats(ctx):
        """Show conversation statistics for the current channel"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            channel_id = str(ctx.channel.id)

            # Get channel conversation count
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM conversations WHERE channel_id = ?", (channel_id,)
            )
            channel_conversation_count = cursor.fetchone()[0]

            # Get recent conversations for this channel
            recent_conversations = bot.db.get_recent_channel_conversations(
                channel_id, limit=5
            )

            conn.close()

            response = f"**💬 CHANNEL STATS FOR {ctx.channel.name.upper()} 💀**\n"
            response += f"• **Total Conversations:** {channel_conversation_count}\n"

            if recent_conversations:
                response += f"• **Recent Activity:**\n"
                for i, conv in enumerate(recent_conversations[:3]):
                    # Get the last message from this conversation
                    messages = conv["messages"]
                    if messages:
                        last_msg = messages[-1] if messages else "No messages"
                        if isinstance(last_msg, dict) and "content" in last_msg:
                            content = (
                                last_msg["content"][:50] + "..."
                                if len(last_msg["content"]) > 50
                                else last_msg["content"]
                            )
                            response += f"  {i + 1}. {content}\n"

            # Send long message without truncation
            await send_long_message(ctx.channel, response)

        except Exception as e:
            await ctx.send(f"💀 Failed to get channel stats: {str(e)}")

    # ==========================================
    # REACTION ROLE COMMANDS (3 commands)
    # ==========================================

    @bot.command(name="add_reaction_role")
    async def add_reaction_role(ctx, message_id: str, emoji: str, role: discord.Role):
        """Add a reaction role to a message (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            # Get the message
            channel = ctx.channel
            message = await channel.fetch_message(int(message_id))

            # Add the reaction to the message
            await message.add_reaction(emoji)

            # Store the reaction role in the database
            bot.db.add_reaction_role(
                message_id, str(channel.id), emoji, str(role.id), str(ctx.guild.id)
            )

            await ctx.send(
                f"✅ **Reaction role added!** React with {emoji} to get the **{role.name}** role."
            )

        except discord.NotFound:
            await ctx.send("💀 Message not found. Make sure the message ID is correct.")
        except discord.Forbidden:
            await ctx.send(
                "💀 I don't have permission to add reactions to that message."
            )
        except Exception as e:
            await ctx.send(f"💀 Failed to add reaction role: {str(e)}")

    @bot.command(name="remove_reaction_role")
    async def remove_reaction_role(ctx, message_id: str, emoji: str):
        """Remove a reaction role from a message (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            # Remove the reaction role from the database
            bot.db.remove_reaction_role(message_id, emoji)

            await ctx.send(
                f"✅ **Reaction role removed!** Removed {emoji} reaction from message {message_id}."
            )

        except Exception as e:
            await ctx.send(f"💀 Failed to remove reaction role: {str(e)}")

    @bot.command(name="list_reaction_roles")
    async def list_reaction_roles(ctx):
        """List all reaction roles in the current server (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            # Get all reaction roles for this guild
            reaction_roles = bot.db.get_all_reaction_roles(str(ctx.guild.id))

            if not reaction_roles:
                await ctx.send("💀 No reaction roles set up in this server.")
                return

            response = f"**🎭 REACTION ROLES IN THIS SERVER ({len(reaction_roles)} total):**\n\n"

            for i, rr in enumerate(reaction_roles, 1):
                try:
                    channel = bot.get_channel(int(rr["channel_id"]))
                    channel_name = channel.name if channel else "Unknown Channel"

                    role = ctx.guild.get_role(int(rr["role_id"]))
                    role_name = role.name if role else "Unknown Role"

                    response += f"{i}. **Channel:** #{channel_name} | **Message:** {rr['message_id']} | **Emoji:** {rr['emoji']} | **Role:** @{role_name}\n"
                except Exception:
                    response += f"{i}. **Message:** {rr['message_id']} | **Emoji:** {rr['emoji']} | **Role ID:** {rr['role_id']}\n"

            # Split into multiple messages if too long
            if len(response) > 1900:
                lines = response.split("\n")
                current_message = ""

                for line in lines:
                    if len(current_message + line + "\n") > 1900:
                        await ctx.send(current_message)
                        current_message = line + "\n"
                    else:
                        current_message += line + "\n"

                if current_message:
                    await ctx.send(current_message)
            else:
                await ctx.send(response)

        except Exception as e:
            await ctx.send(f"💀 Failed to list reaction roles: {str(e)}")

    # ==========================================
    # GENDER ROLE COMMANDS (2 commands)
    # ==========================================

    @bot.command(name="set_gender_roles")
    async def set_gender_roles(ctx, *, role_config: str):
        """Set gender role mappings (admin only)"""
        if not is_admin(ctx.author.id):
            await ctx.send("❌ You don't have permission to use this command!")
            return

        try:
            # Example format: male:123456789,female:987654321,neutral:111222333
            # Validate the format
            parts = role_config.split(",")
            validated_config = []

            for part in parts:
                if ":" in part:
                    gender, role_id = part.split(":", 1)  # Split only on first ':'
                    gender = gender.strip().lower()
                    role_id = role_id.strip()

                    if gender not in ["male", "female", "neutral"]:
                        await ctx.send(
                            f"❌ Invalid gender: {gender}. Use male, female, or neutral."
                        )
                        return

                    try:
                        int(role_id)  # Validate that role is numeric
                        validated_config.append(f"{gender}:{role_id}")
                    except ValueError:
                        await ctx.send(
                            f"❌ Invalid role ID: {role_id}. Must be a number."
                        )
                        return
                else:
                    await ctx.send(
                        "❌ Invalid format. Use: gender:role_id,gender:role_id"
                    )
                    return

            # Store in memory (this would ideally persist in database/config in production)
            # For now, just validate and show success
            final_config = ",".join(validated_config)
            await ctx.send(f"✅ Gender role mappings set:\n{final_config}")
            await ctx.send(
                "Note: This configuration won't persist after bot restart until database integration is added."
            )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "set_gender_roles"))

    @bot.command(name="show_gender_roles")
    async def show_gender_roles(ctx):
        """Show current gender role mappings"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        from utils.gender_roles import get_gender_role_config

        mappings = get_gender_role_config()

        if not mappings:
            await ctx.send("❌ No gender role mappings configured.")
            return

        response = "** configured gender role mappings:**\n"
        for gender, config in mappings.items():
            roles = (
                ", ".join([f"<@&{role_id}>" for role_id in config["roles"]])
                if config["roles"]
                else "Not configured"
            )
            pronouns = "/".join(config["pronouns"])
            response += f"• {gender.title()}: {roles} (Pronouns: {pronouns})\n"

        await ctx.send(response)

    # ==========================================
    # KEYWORD COMMANDS (4 commands)
    # ==========================================

    @bot.command(name="add_keyword")
    async def add_keyword(ctx, keyword: str):
        """Add a keyword that Jakey will respond to"""
        try:
            success = await bot.db.aadd_keyword(keyword)
            if success:
                await ctx.send(f"✅ Added keyword: `{keyword}`")
            else:
                await ctx.send(
                    f"❌ Keyword `{keyword}` already exists or failed to add."
                )
        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "add_keyword"))

    @bot.command(name="remove_keyword")
    async def remove_keyword(ctx, keyword: str):
        """Remove a keyword that Jakey responds to"""
        try:
            success = await bot.db.aremove_keyword(keyword)
            if success:
                await ctx.send(f"✅ Removed keyword: `{keyword}`")
            else:
                await ctx.send(f"❌ Keyword `{keyword}` not found.")
        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "remove_keyword"))

    @bot.command(name="list_keywords")
    async def list_keywords(ctx):
        """List all configured keywords"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            keywords = await bot.db.aget_keywords()
            if keywords:
                response = f"**🔑 CONFIGURED KEYWORDS ({len(keywords)} total):**\n\n"
                response += "\n".join([f"• `{keyword}`" for keyword in keywords])
                await ctx.send(response)
            else:
                await ctx.send(
                    "💀 No keywords configured. Jakey only responds to mentions and his name."
                )
        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "list_keywords"))

    @bot.command(name="enable_keyword")
    async def enable_keyword(ctx, keyword: str):
        """Enable a disabled keyword"""
        try:
            success = await bot.db.aenable_keyword(keyword)
            if success:
                await ctx.send(f"✅ Enabled keyword: `{keyword}`")
            else:
                await ctx.send(f"❌ Keyword `{keyword}` not found.")
        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "enable_keyword"))

    @bot.command(name="disable_keyword")
    async def disable_keyword(ctx, keyword: str):
        """Disable a keyword without removing it"""
        try:
            success = await bot.db.adisable_keyword(keyword)
            if success:
                await ctx.send(f"✅ Disabled keyword: `{keyword}`")
            else:
                await ctx.send(f"❌ Keyword `{keyword}` not found.")
        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "disable_keyword"))

    # ==========================================
    # GAMBLING & FUN COMMANDS (4 commands)
    # ==========================================

    @bot.command(name="rigged")
    async def rigged(ctx):
        """Classic Jakey response"""
        await ctx.send("💀 **Everything's rigged bro, especially Eddie's code**")

    @bot.command(name="wen")
    async def wen(ctx, item: str = "monthly"):
        """Wen schedule command"""
        schedules = {
            "monthly": "Wen monthly? Around the 15th bro, but never on Friday/weekend. Probably Eddie's fault if it's late.",
            "stake": "Stake weekly: Saturday 12:30 GMT. Monthly: Around 15th (but rigged obviously).",
            "shuffle": "Shuffle weekly: Thursday 11am UTC. Monthly: First Friday 12:00 AM UTC. Now THIS one's legit.",
            "payout": "Wen payout? When Eddie fixes the code 💀",
        }

        response = schedules.get(item.lower(), f"Wen {item}? No clue bro, ask Eddie 💀")
        await ctx.send(response)

    @bot.command(name="keno")
    async def keno(ctx, count: Optional[int] = None):
        """Generate random Keno numbers (1-10 numbers from 1-40) with 8x5 visual board

        Usage: %keno [count]
        - count: Optional number between 1-10 specifying how many numbers to generate
        - If not provided, generates a random count between 3-10
        """
        import random

        try:
            await ctx.message.add_reaction("🎨")
        except discord.NotFound:
            # Message was deleted, ignore gracefully
            pass
        except discord.Forbidden:
            # Bot doesn't have permission to add reactions
            pass

        try:
            # Validate count parameter
            if count is not None:
                if not (1 <= count <= 10):
                    await ctx.send("❌ Please provide a count between 1 and 10!")
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

            # Send long message without truncation
            await send_long_message(ctx.channel, response)

        except Exception as e:
            error_msg = f"💀 Keno number generation failed: {str(e)}"
            logger.error(error_msg)
            await ctx.send(error_msg)

        # Remove thinking reaction
        try:
            await ctx.message.remove_reaction("🎯", bot.user)
        except:
            pass  # Ignore if we can't remove the reaction

    @bot.command(name="ind_addr")
    async def ind_addr(ctx):
        """Generate a random Indian name and address"""
        try:
            await ctx.message.add_reaction("🇮🇳")
        except discord.NotFound:
            # Message was deleted, ignore gracefully
            pass
        except discord.Forbidden:
            # Bot doesn't have permission to add reactions
            pass

        try:
            # Generate random name and address
            name = random_indian_generator.generate_random_name()
            address = random_indian_generator.generate_random_address()

            # Format the response to match preferred output
            response = f"**🇮🇳 Random Indian Identity Generator**\n\n"
            response += f"**{name}**\n"
            response += f"{address}"

            # Send long message without truncation
            await send_long_message(ctx.channel, response)

        except Exception as e:
            error_msg = f"💀 Failed to generate Indian address: {str(e)}"
            logger.error(error_msg)
            await ctx.send(error_msg)

        # Remove thinking reaction
        try:
            await ctx.message.remove_reaction("🇮🇳", bot.user)
        except discord.NotFound:
            # Message was deleted, ignore gracefully
            pass
        except discord.Forbidden:
            # Bot doesn't have permission to remove reactions
            pass

    # ==========================================
    # TIP.CC COMMANDS (6 commands)
    # ==========================================

    @bot.command(name="bal")
    async def bal(ctx):
        """Check tip.cc balances and click button on response"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        await ctx.send("$bals top")
        await asyncio.sleep(10)

        # Find the last message from user 617037497574359050 (tip.cc bot)
        async for message in ctx.channel.history(limit=50):
            if message.author.id == 617037497574359050 and message.components:
                logger.info(
                    f"Found tip.cc message with {len(message.components)} component(s)"
                )

                # Collect all buttons from all components
                all_buttons = []
                for component in message.components:
                    logger.info(
                        f"Processing component with {len(component.children)} children"
                    )
                    for child in component.children:
                        if child.type == discord.ComponentType.button:
                            button_label = getattr(child, "label", None)
                            button_emoji = getattr(child, "emoji", None)
                            button_custom_id = getattr(child, "custom_id", "unknown")

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
                    await ctx.send(
                        "💀 **Could not find any buttons in tip.cc response**"
                    )
                    return

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
                        async for msg in ctx.channel.history(limit=10):
                            if msg.id == message.id:  # Same message ID
                                updated_message = msg
                                break

                        if updated_message and updated_message.components:
                            logger.info("Looking for dismiss button in updated message")
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

                            if dismiss_button and not getattr(
                                dismiss_button, "disabled", False
                            ):
                                try:
                                    logger.info(f"Step 2: Clicking dismiss button")
                                    await dismiss_button.click()
                                    logger.info(
                                        "Successfully clicked dismiss button - message should be dismissed"
                                    )
                                    return
                                except discord.errors.HTTPException as e:
                                    logger.error(f"Failed to click dismiss button: {e}")
                                    # Don't return error to user since the next-page already worked
                                    return
                            else:
                                logger.warning(
                                    "Could not find or click dismiss button, but next-page worked"
                                )
                                return

                    except discord.errors.HTTPException as e:
                        logger.error(f"Failed to click next-page button: {e}")
                        await ctx.send(handle_command_error(e, ctx, "next_page_button"))
                        return
                    except Exception as e:
                        logger.error(
                            f"Unexpected error in two-step button process: {e}"
                        )
                        await ctx.send(handle_command_error(e, ctx, "two_step_process"))
                        return
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
                                return
                            except Exception as e:
                                logger.error(f"Fallback button click failed: {e}")
                                continue

                    await ctx.send("💀 **No clickable buttons found**")
                    return

            break
        else:
            logger.warning("No message from tip.cc bot found with components")
            await ctx.send("💀 **Could not find tip.cc response message with buttons**")

    @bot.command(name="bals")
    async def bals(ctx):
        """Check tip.cc balances and click button on response (alias for bal)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        await ctx.send("$bals top")
        await asyncio.sleep(10)

        # Find the last message from user 617037497574359050 (tip.cc bot)
        async for message in ctx.channel.history(limit=50):
            if message.author.id == 617037497574359050 and message.components:
                logger.info(
                    f"Found tip.cc message with {len(message.components)} component(s)"
                )

                # Collect all buttons from all components
                all_buttons = []
                for component in message.components:
                    logger.info(
                        f"Processing component with {len(component.children)} children"
                    )
                    for child in component.children:
                        if child.type == discord.ComponentType.button:
                            button_label = getattr(child, "label", None)
                            button_emoji = getattr(child, "emoji", None)
                            button_custom_id = getattr(child, "custom_id", "unknown")

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
                    await ctx.send(
                        "💀 **Could not find any buttons in tip.cc response**"
                    )
                    return

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
                        async for msg in ctx.channel.history(limit=10):
                            if msg.id == message.id:  # Same message ID
                                updated_message = msg
                                break

                        if updated_message and updated_message.components:
                            logger.info("Looking for dismiss button in updated message")
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

                            if dismiss_button and not getattr(
                                dismiss_button, "disabled", False
                            ):
                                try:
                                    logger.info(f"Step 2: Clicking dismiss button")
                                    await dismiss_button.click()
                                    logger.info(
                                        "Successfully clicked dismiss button - message should be dismissed"
                                    )
                                    return
                                except discord.errors.HTTPException as e:
                                    logger.error(f"Failed to click dismiss button: {e}")
                                    # Don't return error to user since the next-page already worked
                                    return
                            else:
                                logger.warning(
                                    "Could not find or click dismiss button, but next-page worked"
                                )
                                return

                    except discord.errors.HTTPException as e:
                        logger.error(f"Failed to click next-page button: {e}")
                        await ctx.send(handle_command_error(e, ctx, "next_page_button"))
                        return
                    except Exception as e:
                        logger.error(
                            f"Unexpected error in two-step button process: {e}"
                        )
                        await ctx.send(handle_command_error(e, ctx, "two_step_process"))
                        return
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
                                return
                            except Exception as e:
                                logger.error(f"Fallback button click failed: {e}")
                                continue

                    await ctx.send("💀 **No clickable buttons found**")
                    return

            break
        else:
            logger.warning("No message from tip.cc bot found with components")
            await ctx.send("💀 **Could not find tip.cc response message with buttons**")

    @bot.command(name="confirm")
    async def confirm(ctx):
        """Manually check for and click Confirm button on tip.cc confirmation messages"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        await ctx.send("🔍 **Looking for tip.cc confirmation messages...**")

        found_confirmation = False
        # Search recent messages for tip.cc confirmation embeds
        async for message in ctx.channel.history(limit=20):
            if (
                message.author.id == 617037497574359050  # tip.cc bot ID
                and message.embeds
                and message.components
            ):
                embed = message.embeds[0]
                if embed.title and "confirm" in embed.title.lower():
                    found_confirmation = True
                    logger.info(f"Found confirmation message: {embed.title}")

                    # Look for Confirm button
                    confirm_button = None
                    for component in message.components:
                        for child in getattr(component, "children", []):
                            if (
                                hasattr(child, "type")
                                and child.type == discord.ComponentType.button
                            ):
                                button_label = getattr(child, "label", "").lower()
                                button_custom_id = getattr(
                                    child, "custom_id", ""
                                ).lower()

                                if (
                                    button_label == "confirm"
                                    or "confirm" in button_custom_id
                                    or "accept" in button_custom_id
                                ):
                                    confirm_button = child
                                    logger.info("Found Confirm button")
                                    break

                    if confirm_button and not getattr(
                        confirm_button, "disabled", False
                    ):
                        try:
                            await confirm_button.click()
                            await ctx.send(
                                "✅ **Successfully clicked Confirm button!**"
                            )
                            logger.info("Manually clicked Confirm button")
                            return
                        except Exception as e:
                            await ctx.send(
                                f"💀 **Failed to click Confirm button:** {str(e)}"
                            )
                            logger.error(f"Failed to click Confirm button: {e}")
                            return
                    else:
                        await ctx.send("💀 **Confirm button not found or disabled**")
                        return

        if not found_confirmation:
            await ctx.send("💀 **No tip.cc confirmation messages found**")

    @bot.command(name="tip")
    async def tip(
        ctx, recipient: str, amount: str, currency: str, *, message: str = ""
    ):
        """Send a tip to a user using tip.cc (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send(
                "💀 **Admin only command bro!** You can't spend Jakey's money!"
            )
            return

        try:
            # Validate recipient format
            if not recipient.startswith("<@") or not recipient.endswith(">"):
                await ctx.send(
                    "💀 **Invalid recipient format.** Use `@username` format."
                )
                return

            # Send the tip
            success = await bot.tipcc_manager.send_tip_command(
                ctx.channel, recipient, amount, currency, message, str(ctx.author.id)
            )

            if success:
                response = f"🎯 **Tip sent!**\n"
                response += f"Sent {amount} {currency} to {recipient}"
                if message:
                    response += f" with message: {message}"
                await ctx.send(response)
            else:
                await ctx.send(
                    "💀 **Failed to send tip.** Make sure tip.cc bot is active in this channel."
                )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "tip"))

    @bot.command(name="airdrop")
    async def airdrop(ctx, amount: str, currency: str, *, duration_and_maybe_for: str):
        """Create an airdrop using tip.cc (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send(
                "💀 **Admin only command bro!** You can't create airdrops with Jakey's money!"
            )
            return

        try:
            # Handle the "for" keyword - users might type "for 5s" or just "5s"
            duration = duration_and_maybe_for
            if duration.lower().startswith("for "):
                duration = duration[4:]  # Remove "for " prefix

            # Send the airdrop
            success = await bot.tipcc_manager.send_airdrop_command(
                ctx.channel, amount, currency, duration
            )

            if success:
                await ctx.send(
                    f"🎁 **Airdrop created!**\nAirdropping {amount} {currency} for {duration}"
                )
            else:
                await ctx.send(
                    "💀 **Failed to create airdrop.** Make sure tip.cc bot is active in this channel."
                )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "airdrop"))

    @bot.command(name="transactions")
    async def transactions(ctx, limit: int = 10):
        """Show recent tip.cc transaction history"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            transaction_history = await bot.tipcc_manager.get_transaction_history(limit)
            await ctx.send(transaction_history)
        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "transactions"))

    @bot.command(name="tipstats")
    async def tipstats(ctx):
        """Show tip.cc statistics and earnings"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            stats = await bot.db.aget_transaction_stats()

            stats_message = f"📊 **Jakey's tip.cc Stats**\n\n"
            stats_message += (
                f"🎯 **Total Airdrops Won**: ${stats['total_airdrops_usd']:.2f}\n"
            )
            stats_message += f"📤 **Total Tips Sent**: ${stats['total_sent_usd']:.2f}\n"
            stats_message += (
                f"📥 **Total Tips Received**: ${stats['total_received_usd']:.2f}\n"
            )

            # Check if the enhanced stats with airdrop spending are available
            if "total_airdrop_spent_usd" in stats:
                stats_message += f"💸 **Total Airdrops Spent**: ${stats['total_airdrop_spent_usd']:.2f}\n"
                stats_message += (
                    f"💰 **Net Profit**: ${stats['net_profit_usd']:.2f}\n\n"
                )
            else:
                stats_message += (
                    f"💰 **Net Profit**: ${stats['net_profit_usd']:.2f}\n\n"
                )

            # Show transaction counts
            stats_message += "**Transaction Counts:**\n"
            for tx_type, count in stats["transaction_counts"].items():
                emoji = bot.tipcc_manager._get_transaction_emoji(tx_type)
                stats_message += (
                    f"{emoji} {tx_type.replace('_', ' ').title()}: {count}\n"
                )

            await ctx.send(stats_message)

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "tipstats"))

    @bot.command(name="clearstats")
    async def clearstats(ctx):
        """Clear all tip.cc transaction history and stats (admin only)"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            # Clear tip.cc transactions
            success = await bot.db.aclear_tipcc_transactions()
            if success:
                # Also clear balances to start completely fresh
                balances_cleared = await bot.db.aclear_balances()

                await ctx.send(
                    "✅ **Tip.cc transaction history cleared!**\n"
                    "📊 All tipstats and transactions have been reset to zero.\n"
                    "💰 Balances have also been cleared for a fresh start."
                )
            else:
                await ctx.send(
                    "💀 **Failed to clear transaction history.** Check logs for details."
                )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "clearstats"))

    @bot.command(name="airdropstatus")
    async def airdropstatus(ctx):
        """Show current airdrop configuration and status"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

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
            AIRDROP_PRESENCE,
            AIRDROP_RANGE_DELAY,
            AIRDROP_SERVER_WHITELIST,
            AIRDROP_SMART_DELAY,
        )

        # Build status response
        response = "**🎯 AIRDROP STATUS 💀**\n\n"
        response += "**Configuration:**\n"
        response += f"• Presence: {AIRDROP_PRESENCE}\n"
        response += (
            f"• Smart Delay: {'Enabled' if AIRDROP_SMART_DELAY else 'Disabled'}\n"
        )
        response += (
            f"• Range Delay: {'Enabled' if AIRDROP_RANGE_DELAY else 'Disabled'}\n"
        )
        response += f"• Delay Range: {AIRDROP_DELAY_MIN}-{AIRDROP_DELAY_MAX}s\n"
        response += f"• CPM: {AIRDROP_CPM_MIN}-{AIRDROP_CPM_MAX}\n"

        # Show ignore thresholds
        if AIRDROP_IGNORE_DROPS_UNDER > 0:
            response += f"• Ignore Drops Under: ${AIRDROP_IGNORE_DROPS_UNDER:.2f}\n"
        if AIRDROP_IGNORE_TIME_UNDER > 0:
            response += f"• Ignore Time Under: {AIRDROP_IGNORE_TIME_UNDER:.1f}s\n"
        if AIRDROP_IGNORE_USERS:
            ignore_count = len(
                [u.strip() for u in AIRDROP_IGNORE_USERS.split(",") if u.strip()]
            )
            response += f"• Ignore Users: {ignore_count} users\n"

        # Show whitelist status
        if AIRDROP_SERVER_WHITELIST:
            whitelist_servers = [
                s.strip() for s in AIRDROP_SERVER_WHITELIST.split(",") if s.strip()
            ]
            response += (
                f"• Server Whitelist: Enabled ({len(whitelist_servers)} servers)\n"
            )
        else:
            response += "• Server Whitelist: Disabled (all servers)\n"
        response += "\n"

        # Show disabled features
        disabled_features = []
        if AIRDROP_DISABLE_AIRDROP:
            disabled_features.append("Airdrop")
        if AIRDROP_DISABLE_TRIVIADROP:
            disabled_features.append("Trivia Drop")
        if AIRDROP_DISABLE_MATHDROP:
            disabled_features.append("Math Drop")
        if AIRDROP_DISABLE_PHRASEDROP:
            disabled_features.append("Phrase Drop")
        if AIRDROP_DISABLE_REDPACKET:
            disabled_features.append("Red Packet")

        if disabled_features:
            response += "**Disabled Features:**\n"
            for feature in disabled_features:
                response += f"• {feature}: Disabled\n"
            response += "\n"
        else:
            response += "**All Features Enabled**\n\n"

        # Show filters
        response += "**Filters:**\n"
        response += f"• Ignore drops under: ${AIRDROP_IGNORE_DROPS_UNDER:.2f}\n"
        response += f"• Ignore time under: {AIRDROP_IGNORE_TIME_UNDER:.1f}s\n"
        response += f"• Ignored users: {AIRDROP_IGNORE_USERS if AIRDROP_IGNORE_USERS else 'None'}\n"

        # Send long message without truncation
        await send_long_message(ctx.channel, response)

    # ==========================================
    # AI & MEDIA COMMANDS (3 commands)
    # ==========================================

    @bot.command(name="image")
    async def image(ctx, *, prompt: str = ""):
        """Generate an image with artistic styles"""
        try:
            # Parse arguments from the prompt
            # Support syntax like: %image [width]x[height] [model] [seed] [prompt]
            # Example: %image 1024x1024 flux 42 a beautiful landscape
            args = prompt.split()
            width = 1024
            height = 1024
            model = "flux"
            seed = None
            nologo = True

            # Parse arguments
            remaining_args = []
            i = 0
            while i < len(args):
                arg = args[i]

                # Check for dimensions (e.g., 1024x1024)
                if "x" in arg and arg.replace("x", "").isdigit():
                    parts = arg.split("x")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        try:
                            w = int(parts[0])
                            h = int(parts[1])
                            # Validate dimensions
                            if 256 <= w <= 2048 and 256 <= h <= 2048:
                                width = w
                                height = h
                                i += 1
                                continue
                        except ValueError:
                            pass  # Not valid dimensions, treat as regular argument

                # Check for model - get available models dynamically
                from media.image_generator import image_generator
                available_models = image_generator.get_available_models()
                model_names = []

                # Handle different model response formats
                if isinstance(available_models, list):
                    for m in available_models:
                        if isinstance(m, dict):
                            model_names.append(
                                str(m.get("id", m.get("name", ""))).lower()
                            )
                        else:
                            model_names.append(str(m).lower())

                # Also include commonly supported models
                common_models = [
                    "flux",
                    "realistic",
                    "anime",
                    "art",
                    "painting",
                    "scenery",
                    "portrait",
                ]

                if arg.lower() in model_names or arg in common_models:
                    model = arg.lower()
                    i += 1
                    continue

                # Check for seed
                if arg.startswith("seed=") and arg[5:].isdigit():
                    seed = int(arg[5:])
                    i += 1
                    continue

                # Rest is the prompt
                remaining_args.append(arg)
                i += 1

            # Reconstruct prompt
            final_prompt = " ".join(remaining_args)

            # Validate dimensions
            if width < 256 or width > 2048 or height < 256 or height > 2048:
                await ctx.send(
                    "💀 Image generation failed: Dimensions must be between 256 and 2048 pixels"
                )
                return

            # Validate prompt
            if not final_prompt or len(final_prompt.strip()) == 0:
                await ctx.send(
                    "💀 **Usage:** `%image <prompt>` or `%image 1024x1024 Fantasy Art a casino scene`\n\n**Examples:**\n• `%image degenerate gambler`\n• `%image 512x512 Fantasy Art poker chips`\n• `%image Photographic seed=42 casino interior`"
                )
                return

            # Notify user we're generating with a brief message
            await ctx.send(
                f"🎨 **Generating Image...**\n**Prompt:** {final_prompt}\n\n*This takes a little bit, go smoke a cigerette or something...*"
            )

            # Add progress indicator with multiple reactions
            try:
                await ctx.message.add_reaction("⚡")  # Lightning bolt for processing
            except discord.NotFound:
                # Message was deleted, ignore gracefully
                pass
            except discord.Forbidden:
                # Bot doesn't have permission to add reactions
                pass

            # Generate image URL with all parameters
            image_url = image_generator.generate_image(
                prompt=final_prompt,
                model=model,
                width=width,
                height=height,
                seed=seed,  # Pass seed as-is (can be None)
                nologo=nologo,
            )

            # Update progress indicators
            try:
                await ctx.message.add_reaction("✅")  # Check mark for success
            except discord.NotFound:
                # Message was deleted, ignore gracefully
                pass
            except discord.Forbidden:
                # Bot doesn't have permission to add reactions
                pass

            # Send the final result
            await ctx.send(
                f"🎨 **Image Generated Successfully!**\n**Prompt:** {final_prompt}\n{image_url}"
            )

        except Exception as e:
            error_msg = f"💀 Image generation failed: {str(e)}"
            logger.error(error_msg)

            # Send plain error message
            await ctx.send(error_msg)

        # Remove thinking reaction
        try:
            await ctx.message.remove_reaction("🖼️", bot.user)
        except:
            pass  # Ignore if we can't remove the reaction

    @bot.command(name="audio")
    async def audio(ctx, *, text: str = ""):
        """Generate audio from text using Pollinations API"""
        if not text:
            await ctx.send(
                "💀 **Usage:** `%audio <text>`\n**Example:** `%audio Welcome to the degenerate courtyard!`"
            )
            return

        try:
            await ctx.message.add_reaction("🔊")
        except discord.NotFound:
            # Message was deleted, ignore gracefully
            pass
        except discord.Forbidden:
            # Bot doesn't have permission to add reactions
            pass

        try:
            # Generate audio URL using OpenRouter text-to-speech
            import urllib.parse
            encoded_text = urllib.parse.quote(text)
            audio_url = f"https://api.openai.com/v1/audio/speech?model=tts-1&voice=nova&input={encoded_text}"

            # Send the result
            response = f"**🔊 Audio Generated!**\n**Text:** {text}\n**Audio URL:** {audio_url}"

            # Send long message without truncation
            await send_long_message(ctx.channel, response)

        except Exception as e:
            error_msg = f"💀 Audio generation failed: {str(e)}"
            logger.error(error_msg)
            await ctx.send(error_msg)

        # Remove thinking reaction
        try:
            await ctx.message.remove_reaction("🔊", bot.user)
        except:
            pass  # Ignore if we can't remove the reaction

    @bot.command(name="analyze")
    async def analyze(ctx, image_url: str = "", *, prompt: str = "Describe this image"):
        """Analyze an image using Pollinations API vision capabilities"""
        # Check if image URL is provided directly or as an attachment
        if not image_url:
            # Check if there's an attachment in the message
            if ctx.message.attachments:
                image_url = ctx.message.attachments[0].url
            else:
                await ctx.send(
                    "💀 **Usage:** `%analyze <image_url> [prompt]` or attach an image\n**Example:** `%analyze https://example.com/image.jpg What is in this image?`"
                )
                return

        try:
            await ctx.message.add_reaction("👁️")
        except discord.NotFound:
            # Message was deleted, ignore gracefully
            pass
        except discord.Forbidden:
            # Bot doesn't have permission to add reactions
            pass

        try:
            # Analyze the image using the tool manager
            from tools.tool_manager import tool_manager

            result = tool_manager.analyze_image(image_url, prompt)

            # Send the result
            response = f"**👁️ Image Analysis Result:**\n**Prompt:** {prompt}\n**Result:** {result}"

            # Send long message without truncation
            await send_long_message(ctx.channel, response)

        except Exception as e:
            error_msg = f"💀 Image analysis failed: {str(e)}"
            logger.error(error_msg)
            await ctx.send(error_msg)

        # Remove thinking reaction
        try:
            await ctx.message.remove_reaction("👁️", bot.user)
        except:
            pass  # Ignore if we can't remove the reaction

    # ==========================================
    # TRIVIA COMMANDS (6 commands)
    # ==========================================

    @bot.command(name="triviastats")
    async def triviastats(ctx):
        """Show trivia database statistics"""
        # Check if user is admin
        if not is_admin(ctx.author.id):
            await ctx.send("💀 Admin only command bro!")
            return

        try:
            from utils.trivia_manager import trivia_manager

            # Get database overview
            overview = await trivia_manager.get_database_overview()

            stats_message = f"""**🧠 TRIVIA DATABASE STATISTICS**

 📊 **Database Health:** {overview.get("health_status", "unknown").title()}
 📈 **Health Score:** {overview.get("health_score", 0)}/100
 📚 **Total Categories:** {overview.get("total_categories", 0)}
 ❓ **Total Questions:** {overview.get("total_questions", 0)}
 🎯 **Total Attempts:** {overview.get("total_attempts", 0)}

 **🏆 Top Categories:**
 """

            top_categories = overview.get("top_categories", [])
            for cat in top_categories[:5]:
                stats_message += f"• {cat['name']}: {cat['count']} questions\n"

            await ctx.send(stats_message)

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "triviastats"))

    @bot.command(name="triviacats")
    async def triviacats(ctx):
        """List all available trivia categories"""
        try:
            from utils.trivia_manager import trivia_manager

            categories = await trivia_manager.list_available_categories()

            if not categories:
                await ctx.send(
                    "❌ No trivia categories found. Try seeding the database first."
                )
                return

            message = "**📚 Available Trivia Categories:**\n\n"

            for cat in categories:
                cache_status = "🟢" if cat.get("cache_status") == "fresh" else "🔴"
                message += f"{cache_status} **{cat['display_name']}** - {cat['question_count']} questions\n"

            message += "\n🟢 = Cached | 🔴 = Not cached"
            message += (
                "\n\nUse `%seedtrivia` to populate the database with more questions."
            )

            await ctx.send(message)

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "triviacats"))

    @bot.command(name="seedtrivia")
    async def seedtrivia(ctx):
        """Seed trivia database with questions from external sources (admin only)"""
        if not is_admin(ctx.author.id):
            await ctx.send("❌ You don't have permission to use this command!")
            return

        try:
            await ctx.send(
                "🌱 Starting trivia database seeding... This may take a moment."
            )

            from utils.trivia_manager import trivia_manager

            # Initialize manager if not already done
            if not trivia_manager.session:
                await trivia_manager.initialize()

            total_imported = 0
            categories = [
                "Entertainment: Music",
                "Entertainment: Japanese Anime & Manga",
                "Entertainment: Video Games",
                "Entertainment: Cartoon & Animations",
                "Entertainment: Film",
                "Entertainment: Television",
                "Entertainment: Books",
                "Science & Nature",
                "Science: Computers",
                "Geography",
                "History",
                "General Knowledge",
                "Art",
                "Animals",
                "Celebrities",
                "Mythology",
                "Politics",
            ]

            for category in categories:
                await ctx.send(f"📥 Seeding {category}...")
                found, imported = await trivia_manager.sync_category_from_external(
                    category
                )
                total_imported += imported

                if imported > 0:
                    await ctx.send(f"✅ Imported {imported} questions for {category}")
                else:
                    await ctx.send(f"⚠️ No questions found for {category}")

            final_message = f"""**🎉 Trivia Seeding Complete!**

📊 **Summary:**
• Categories processed: {len(categories)}
• Total questions imported: {total_imported}
• Database is ready for trivia drops!

💡 Use `%triviastats` to see updated statistics."""

            await ctx.send(final_message)

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "seedtrivia"))

    @bot.command(name="triviatest")
    async def triviatest(ctx):
        """Test trivia system with a sample question"""
        try:
            from utils.trivia_manager import trivia_manager

            # Initialize manager if not already done
            if not trivia_manager.session:
                await trivia_manager.initialize()

            # Test with multiple sample questions to verify system
            test_cases = [
                {
                    "category": "Entertainment: Music",
                    "question": "Which Beatle led the way across the zebra crossing on the Abbey Road album cover?",
                    "expected": "John Lennon",  # This is a real question from our data
                },
                {
                    "category": "Entertainment: Video Games",
                    "question": "What is the best-selling video game console of all time?",
                    "expected": None,  # This might not exist, test fallback
                },
            ]

            results = []
            for i, test_case in enumerate(test_cases, 1):
                answer = await trivia_manager.find_trivia_answer(
                    test_case["category"], test_case["question"]
                )

                status = "✅ Found" if answer else "❌ Not found"
                expected = test_case["expected"]
                result_text = f"{status}: `{test_case['question'][:30]}...`"

                if answer:
                    result_text += f" → `{answer}`"
                    if expected and answer.strip().lower() == expected.lower():
                        result_text += " ✅"
                    elif expected:
                        result_text += f" (expected: `{expected}`) ⚠️"
                else:
                    if expected:
                        result_text += f" (expected: `{expected}`) ⚠️"
                    else:
                        result_text += " ✅"

                results.append(f"Test {i}: {result_text}")

            # Send results
            await ctx.send("**🧪 Trivia System Test Results**\n\n" + "\n".join(results))

            # Overall status
            found_count = sum(1 for r in results if "✅ Found" in r)
            await ctx.send(
                f"\n**Overall Status**: {found_count}/{len(test_cases)} tests passed 🎯"
            )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "triviatest"))

    @bot.command(name="addtrivia")
    async def addtrivia(ctx, category: str, question: str, answer: str):
        """Add a custom trivia question (admin only)"""
        if not is_admin(ctx.author.id):
            await ctx.send("❌ You don't have permission to use this command!")
            return

        try:
            from utils.trivia_manager import trivia_manager

            # Initialize manager if not already done
            if not trivia_manager.session:
                await trivia_manager.initialize()

            # Add the question
            question_id = await trivia_manager.db.add_question(
                category_name=category,
                question_text=question,
                answer_text=answer,
                source="manual",
                difficulty=1,
            )

            if question_id:
                await ctx.send(
                    f"✅ Added trivia question to `{category}`\\n**Q:** {question}\\n**A:** {answer}\\n**ID:** {question_id}"
                )

                # Update cache for this category
                existing_questions = await trivia_manager.db.get_questions_by_category(
                    category, 50
                )
                await trivia_manager.db.cache_category_questions(
                    category, existing_questions, ttl_hours=168
                )

            else:
                await ctx.send(
                    "❌ Failed to add trivia question. Check category name and try again."
                )

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "addtrivia"))

    @bot.command(name="triviasearch")
    async def triviasearch(ctx, *, query: str, category: str = ""):
        """Search for trivia questions"""
        try:
            from utils.trivia_manager import trivia_manager

            # Initialize manager if not already done
            if not trivia_manager.session:
                await trivia_manager.initialize()

            # Search for questions
            results = await trivia_manager.search_questions(query, category, limit=10)

            if not results:
                await ctx.send(f"❌ No trivia questions found for query: `{query}`")
                return

            message = f"**🔍 Trivia Search Results for: `{query}`**\\n\\n"

            for i, q in enumerate(results, 1):
                # Truncate long questions/answers
                q_text = q["question_text"][:60] + (
                    "..." if len(q["question_text"]) > 60 else ""
                )
                a_text = q["answer_text"][:40] + (
                    "..." if len(q["answer_text"]) > 40 else ""
                )

                message += f"**{i}.** {q_text}\\n   📝 `{a_text}`\\n\\n"

            if len(results) >= 10:
                message += f"... and {len(results) - 10} more results."

            await ctx.send(message)

        except Exception as e:
            await ctx.send(handle_command_error(e, ctx, "triviasearch"))

    # ==========================================
    # CLEAR CACHE COMMAND (1 command)
    # ==========================================

    @bot.command(name="clearcache")
    async def clearcache(ctx):
        """Clear the model capabilities cache (admin only)"""
        if not is_admin(ctx.author.id):
            await ctx.send("❌ This command is for admins only.")
            return

        try:
            bot.clear_model_cache()
            await ctx.send("✅ Model capabilities cache cleared successfully.")
        except Exception as e:
            await ctx.send(f"❌ Failed to clear cache: {str(e)}")

    logger.info("All 35 commands registered")

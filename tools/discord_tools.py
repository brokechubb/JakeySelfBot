"""
Discord Tools for JakeySelfBot
Provides native Discord functionality as tools that can be used by the AI
"""

import discord
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class DiscordTools:
    """Native Discord tools implementation for JakeySelfBot"""

    def __init__(self, bot_client: discord.Client):
        """
        Initialize Discord tools with the existing bot client
        Args:
            bot_client: The discord.py-self bot instance from Jakey
        """
        self.bot = bot_client
        self._last_dm_time = 0
        self._dm_cooldown = 30  # 30 seconds between DMs

    def get_user_info(self) -> Dict[str, Any]:
        """Get information about the currently logged-in Discord user"""
        try:
            if not self.bot.user:
                return {"error": "Bot not logged in"}

            user_info = {
                "id": str(self.bot.user.id),
                "username": self.bot.user.name,
                "discriminator": self.bot.user.discriminator,
                "display_name": self.bot.user.display_name,
                "avatar_url": str(self.bot.user.avatar.url) if self.bot.user.avatar else None,
                "is_bot": self.bot.user.bot,
                "created_at": self.bot.user.created_at.isoformat() if self.bot.user.created_at else None
            }

            return {"user": user_info}
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {"error": f"Failed to get user info: {str(e)}"}

    def list_guilds(self) -> Dict[str, Any]:
        """List all Discord servers/guilds the user is in"""
        try:
            guilds = []
            for guild in self.bot.guilds:
                guild_info = {
                    "id": str(guild.id),
                    "name": guild.name,
                    "owner_id": str(guild.owner_id) if guild.owner_id else None,
                    "member_count": guild.member_count,
                    "created_at": guild.created_at.isoformat() if guild.created_at else None,
                    "description": guild.description,
                    "icon_url": str(guild.icon.url) if guild.icon else None
                }
                guilds.append(guild_info)

            return {"guilds": guilds, "count": len(guilds)}
        except Exception as e:
            logger.error(f"Error listing guilds: {e}")
            return {"error": f"Failed to list guilds: {str(e)}"}

    def list_channels(self, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """List channels the user has access to, optionally filtered by guild"""
        try:
            channels = []

            # If guild_id is provided, filter to that guild
            if guild_id:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    return {"error": f"Guild with ID {guild_id} not found"}
                target_channels = guild.channels
            else:
                # Get all channels from all guilds
                target_channels = []
                for guild in self.bot.guilds:
                    target_channels.extend(guild.channels)

            for channel in target_channels:
                # Only include text channels for now
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                    channel_info = {
                        "id": str(channel.id),
                        "name": channel.name,
                        "guild_id": str(channel.guild.id),
                        "guild_name": channel.guild.name,
                        "type": str(channel.type),
                        "position": channel.position,
                        "category_id": str(channel.category_id) if channel.category_id else None
                    }
                    channels.append(channel_info)

            return {"channels": channels, "count": len(channels)}
        except Exception as e:
            logger.error(f"Error listing channels: {e}")
            return {"error": f"Failed to list channels: {str(e)}"}

    async def read_channel(self, channel_id: str, limit: int = 50) -> Dict[str, Any]:
        """Read messages from a specific Discord channel"""
        try:
            # Validate limit
            limit = min(max(1, limit), 100)  # Clamp between 1-100

            # Parse and validate channel ID format (handle Discord mention format <#123456789>)
            channel_id_clean = self._parse_channel_id(channel_id)
            if channel_id_clean is None:
                return {"error": f"Invalid channel ID format: {channel_id}. Must be a numeric ID or Discord channel mention."}

            channel_id_int = channel_id_clean

            # Get the channel - try cache first, then fetch
            channel = self.bot.get_channel(channel_id_int)
            if not channel:
                # Try fetching it if not in cache
                try:
                    channel = await self.bot.fetch_channel(channel_id_int)
                    logger.info(f"Successfully fetched channel {channel_id_int} from Discord API")
                except discord.NotFound:
                    return {"error": f"Channel with ID {channel_id} not found or doesn't exist. Please check:\n1. The channel ID is correct\n2. The channel still exists\n3. You have permission to access this channel"}
                except discord.Forbidden:
                    return {"error": f"Access denied to channel {channel_id}. You don't have permission to read this channel. This could be because:\n1. You're not in the server\n2. The channel is private\n3. Your role doesn't have read permissions"}
                except discord.HTTPException as e:
                    return {"error": f"Discord API error when accessing channel {channel_id}: {str(e)}"}

            # Check if it's a text channel
            if not isinstance(channel, discord.TextChannel):
                channel_type = str(getattr(channel, 'type', 'unknown'))
                return {"error": f"Channel {channel_id} is not a text channel (type: {channel_type}). Only text channels can be read."}

            # Fetch messages
            messages = []
            try:
                async for message in channel.history(limit=limit):
                    messages.append(message)
            except discord.Forbidden:
                return {"error": f"Access denied to read message history in channel {channel_id}. You don't have permission to read message history in this channel. This could be because:\n1. You're not in the server\n2. The channel is private\n3. Your role doesn't have 'Read Message History' permission"}
            except discord.HTTPException as e:
                return {"error": f"Discord API error when reading message history in channel {channel_id}: {str(e)}"}
            except Exception as e:
                logger.error(f"Unexpected error reading message history in channel {channel_id}: {e}")
                return {"error": f"Failed to read message history: {str(e)}"}

            # Format messages
            formatted_messages = []
            for message in reversed(messages):  # Reverse to get chronological order
                message_info = {
                    "id": str(message.id),
                    "content": message.content,
                    "author": {
                        "id": str(message.author.id),
                        "username": message.author.name,
                        "discriminator": message.author.discriminator,
                        "display_name": message.author.display_name,
                        "bot": message.author.bot
                    },
                    "timestamp": message.created_at.isoformat(),
                    "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None,
                    "attachments": [str(att.url) for att in message.attachments],
                    "embeds": len(message.embeds),
                    "mentions": [str(mention.id) for mention in message.mentions],
                    "channel_id": str(message.channel.id),
                    "guild_id": str(message.guild.id) if message.guild else None
                }
                formatted_messages.append(message_info)

            return {
                "messages": formatted_messages,
                "count": len(formatted_messages),
                "channel": {
                    "id": str(channel.id),
                    "name": channel.name,
                    "guild_id": str(channel.guild.id),
                    "guild_name": channel.guild.name
                }
            }
        except Exception as e:
            logger.error(f"Error reading channel {channel_id}: {e}")
            return {"error": f"Failed to read channel: {str(e)}"}

    async def search_messages(self, channel_id: str, query: str = "",
                             author_id: Optional[str] = None,
                             limit: int = 100) -> Dict[str, Any]:
        """Search for messages in a Discord channel by content, author, etc."""
        try:
            # Validate limit
            limit = min(max(1, limit), 500)  # Clamp between 1-500

            # Parse and validate channel ID format (handle Discord mention format <#123456789>)
            channel_id_clean = self._parse_channel_id(channel_id)
            if channel_id_clean is None:
                return {"error": f"Invalid channel ID format: {channel_id}. Must be a numeric ID or Discord channel mention."}

            channel_id_int = channel_id_clean

            # Get the channel
            channel = self.bot.get_channel(channel_id_int)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id_int)
                    logger.info(f"Successfully fetched channel {channel_id_int} from Discord API for search")
                except discord.NotFound:
                    return {"error": f"Channel with ID {channel_id} not found or doesn't exist. Please check:\n1. The channel ID is correct\n2. The channel still exists\n3. You have permission to access this channel"}
                except discord.Forbidden:
                    return {"error": f"Access denied to channel {channel_id}. You don't have permission to read this channel. This could be because:\n1. You're not in the server\n2. The channel is private\n3. Your role doesn't have read permissions"}
                except discord.HTTPException as e:
                    return {"error": f"Discord API error when accessing channel {channel_id}: {str(e)}"}

            # Check if it's a text channel
            if not isinstance(channel, discord.TextChannel):
                return {"error": f"Channel {channel_id} is not a text channel"}

            # Fetch messages
            messages = []
            try:
                async for message in channel.history(limit=limit):
                    messages.append(message)
            except discord.Forbidden:
                return {"error": f"Access denied to read message history in channel {channel_id}. You don't have permission to read message history in this channel. This could be because:\n1. You're not in the server\n2. The channel is private\n3. Your role doesn't have 'Read Message History' permission"}
            except discord.HTTPException as e:
                return {"error": f"Discord API error when reading message history in channel {channel_id}: {str(e)}"}
            except Exception as e:
                logger.error(f"Unexpected error reading message history in channel {channel_id}: {e}")
                return {"error": f"Failed to read message history: {str(e)}"}

            # Filter messages
            filtered_messages = []
            for message in messages:
                # Filter by query if provided
                if query and query.lower() not in message.content.lower():
                    continue

                # Filter by author if provided
                if author_id and str(message.author.id) != author_id:
                    continue

                filtered_messages.append(message)

            # Format messages
            formatted_messages = []
            for message in reversed(filtered_messages):  # Reverse to get chronological order
                message_info = {
                    "id": str(message.id),
                    "content": message.content,
                    "author": {
                        "id": str(message.author.id),
                        "username": message.author.name,
                        "discriminator": message.author.discriminator,
                        "display_name": message.author.display_name,
                        "bot": message.author.bot
                    },
                    "timestamp": message.created_at.isoformat(),
                    "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None,
                    "attachments": [str(att.url) for att in message.attachments],
                    "embeds": len(message.embeds),
                    "mentions": [str(mention.id) for mention in message.mentions],
                    "channel_id": str(message.channel.id),
                    "guild_id": str(message.guild.id) if message.guild else None
                }
                formatted_messages.append(message_info)

            return {
                "messages": formatted_messages,
                "count": len(formatted_messages),
                "query": query,
                "channel": {
                    "id": str(channel.id),
                    "name": channel.name,
                    "guild_id": str(channel.guild.id),
                    "guild_name": channel.guild.name
                }
            }
        except Exception as e:
            logger.error(f"Error searching messages in channel {channel_id}: {e}")
            return {"error": f"Failed to search messages: {str(e)}"}

    def list_guild_members(self, guild_id: str, limit: int = 100,
                          include_roles: bool = False) -> Dict[str, Any]:
        """List members of a specific Discord guild/server"""
        try:
            # Validate limit
            limit = min(max(1, limit), 1000)  # Clamp between 1-1000

            # Get the guild
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return {"error": f"Guild with ID {guild_id} not found"}

            # Get members (note: this might be limited by Discord's caching)
            members = list(guild.members)[:limit]

            # Format members
            formatted_members = []
            for member in members:
                member_info = {
                    "id": str(member.id),
                    "username": member.name,
                    "discriminator": member.discriminator,
                    "display_name": member.display_name,
                    "bot": member.bot,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                    "created_at": member.created_at.isoformat() if member.created_at else None,
                    "avatar_url": str(member.avatar.url) if member.avatar else None,
                    "status": str(member.status),
                    "activity": str(member.activity) if member.activity else None
                }

                if include_roles:
                    member_info["roles"] = [
                        {
                            "id": str(role.id),
                            "name": role.name,
                            "color": str(role.color),
                            "position": role.position
                        }
                        for role in member.roles if role.name != "@everyone"
                    ]

                formatted_members.append(member_info)

            return {
                "members": formatted_members,
                "count": len(formatted_members),
                "guild": {
                    "id": str(guild.id),
                    "name": guild.name
                }
            }
        except Exception as e:
            logger.error(f"Error listing guild members for guild {guild_id}: {e}")
            return {"error": f"Failed to list guild members: {str(e)}"}

    async def send_message(self, channel_id: str, content: str,
                          reply_to_message_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to a specific Discord channel with security validation"""
        logger.info(f"DiscordTools.send_message called with channel_id={channel_id}, content='{content[:100]}...', reply_to_message_id={reply_to_message_id}")
        try:
            # Validate content using security framework
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from utils.security_validator import validator

                is_valid, error = validator.validate_discord_message(content)
                if not is_valid:
                    logger.error(f"Message validation failed: {error}")
                    return {"error": f"Message validation failed: {error}"}
            except ImportError:
                # Fallback validation
                if not content or not content.strip():
                    logger.error("Message content cannot be empty")
                    return {"error": "Message content cannot be empty"}

            # Truncate content to Discord's limit
            content = content[:2000]

            # Parse and validate channel ID format (handle Discord mention format <#123456789>)
            channel_id_clean = self._parse_channel_id(channel_id)
            if channel_id_clean is None:
                logger.error(f"Invalid channel ID format: {channel_id}")
                return {"error": f"Invalid channel ID format: {channel_id}. Must be a numeric ID or Discord channel mention."}

            channel_id_int = channel_id_clean
            logger.info(f"Parsed channel_id: {channel_id_int}")

            # Get the channel
            channel = self.bot.get_channel(channel_id_int)
            if not channel:
                logger.info(f"Channel not in cache, fetching from API: {channel_id_int}")
                try:
                    channel = await self.bot.fetch_channel(channel_id_int)
                    logger.info(f"Successfully fetched channel {channel_id_int} from Discord API")
                except discord.NotFound:
                    logger.error(f"Channel with ID {channel_id} not found")
                    return {"error": f"Channel with ID {channel_id} not found or doesn't exist. Please check:\n1. The channel ID is correct\n2. The channel still exists\n3. You have permission to access this channel"}
                except discord.Forbidden:
                    logger.error(f"Access denied to channel {channel_id}")
                    return {"error": f"Access denied to channel {channel_id}. You don't have permission to send messages to this channel. This could be because:\n1. You're not in the server\n2. The channel is private\n3. Your role doesn't have send permissions"}
                except discord.HTTPException as e:
                    logger.error(f"Discord API error when accessing channel {channel_id}: {e}")
                    return {"error": f"Discord API error when accessing channel {channel_id}: {str(e)}"}

            # Check if it's a text channel
            if not isinstance(channel, discord.TextChannel):
                logger.error(f"Channel {channel_id} is not a text channel, type: {type(channel)}")
                return {"error": f"Channel {channel_id} is not a text channel"}

            logger.info(f"Found text channel: #{channel.name} in guild {channel.guild.name}")

            # Prepare message reference if replying
            reference = None
            if reply_to_message_id:
                try:
                    logger.info(f"Fetching referenced message: {reply_to_message_id}")
                    referenced_message = await channel.fetch_message(int(reply_to_message_id))
                    reference = referenced_message
                    logger.info(f"Found referenced message: {referenced_message.id}")
                except discord.NotFound:
                    logger.warning(f"Referenced message {reply_to_message_id} not found")
                except Exception as e:
                    logger.warning(f"Error fetching referenced message {reply_to_message_id}: {e}")

            # Send the message
            kwargs = {}
            if reference:
                kwargs['reference'] = reference
                logger.info(f"Sending message with reference to {reference.id}")

            logger.info(f"Attempting to send message to channel #{channel.name}")
            sent_message = await channel.send(content, **kwargs)
            logger.info(f"Message sent successfully! ID: {sent_message.id}")

            return {
                "message": {
                    "id": str(sent_message.id),
                    "content": sent_message.content,
                    "timestamp": sent_message.created_at.isoformat(),
                    "channel_id": str(sent_message.channel.id),
                    "guild_id": str(sent_message.guild.id) if sent_message.guild else None
                },
                "status": "sent"
            }
        except discord.Forbidden as e:
            logger.error(f"Permission denied to send message to channel {channel_id}: {e}")
            return {"error": f"Permission denied to send message to channel {channel_id}"}
        except discord.HTTPException as e:
            logger.error(f"HTTP error sending message to channel {channel_id}: {e}")
            return {"error": f"Failed to send message: {str(e)}"}
        except Exception as e:
            logger.error(f"Error sending message to channel {channel_id}: {e}", exc_info=True)
            return {"error": f"Failed to send message: {str(e)}"}

    async def send_dm(self, user_id: str, content: str) -> Dict[str, Any]:
        """Send a direct message to a specific Discord user"""
        try:
            # Check DM cooldown
            import time
            current_time = time.time()
            if current_time - self._last_dm_time < self._dm_cooldown:
                remaining = int(self._dm_cooldown - (current_time - self._last_dm_time))
                return {"error": f"DM cooldown active. Please wait {remaining} seconds before sending another DM."}
            
            # Add delay to avoid captcha
            import asyncio
            await asyncio.sleep(2)  # Wait 2 seconds before sending DM
            
            # Validate content
            if not content or not content.strip():
                return {"error": "Message content cannot be empty"}

            # Truncate content to Discord's limit
            content = content[:2000]

            # Get the user
            user = self.bot.get_user(int(user_id))
            if not user:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                except discord.NotFound:
                    return {"error": f"User with ID {user_id} not found"}
                except discord.Forbidden:
                    return {"error": f"Access denied to user {user_id}"}

            # Create DM channel
            dm_channel = user.dm_channel
            if not dm_channel:
                dm_channel = await user.create_dm()

            # Send the message with retry logic
            logger.info(f"Sending DM to user {user.id} (ID: {user_id}): '{content[:100]}...'")
            
            max_retries = 3
            sent_message = None
            for attempt in range(max_retries):
                try:
                    sent_message = await dm_channel.send(content)
                    logger.info(f"DM sent successfully to user {user.id}, message ID: {sent_message.id}")
                    break
                except discord.HTTPException as e:
                    if "Captcha required" in str(e) and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5  # 5, 10, 15 seconds
                        logger.warning(f"Captcha required, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise e
            
            if sent_message is None:
                return {"error": "Failed to send DM after multiple attempts due to captcha requirements"}

            # Update last DM time
            self._last_dm_time = time.time()

            return {
                "message": {
                    "id": str(sent_message.id),
                    "content": sent_message.content,
                    "timestamp": sent_message.created_at.isoformat(),
                    "channel_id": str(sent_message.channel.id),
                    "recipient_id": str(user.id)
                },
                "status": "sent"
            }
        except discord.Forbidden:
            logger.error(f"Permission denied to send DM to user {user_id}")
            return {"error": f"Permission denied to send DM to user {user_id}"}
        except discord.HTTPException as e:
            logger.error(f"HTTP error sending DM to user {user_id}: {e}")
            return {"error": f"Failed to send DM: {str(e)}"}
        except Exception as e:
            logger.error(f"Error sending DM to user {user_id}: {e}")
            return {"error": f"Failed to send DM: {str(e)}"}

    def get_user_roles(self, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """Get roles for the currently logged-in user in a specific guild or current context"""
        try:
            if not self.bot.user:
                return {"error": "Bot not logged in"}

            # If guild_id is provided, get roles in that specific guild
            if guild_id:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    return {"error": f"Guild with ID {guild_id} not found"}
                
                member = guild.get_member(self.bot.user.id)
                if not member:
                    return {"error": f"User not found in guild {guild_id}"}
            else:
                # Without guild_id, we can't determine context - this should ideally be called with context
                return {"error": "Guild ID is required to get user roles"}

            # Get roles (excluding @everyone)
            roles = [
                {
                    "id": str(role.id),
                    "name": role.name,
                    "color": str(role.color),
                    "position": role.position,
                    "mentionable": role.mentionable
                }
                for role in member.roles if role.name != "@everyone"
            ]

            return {
                "user": {
                    "id": str(member.id),
                    "username": member.name,
                    "display_name": member.display_name
                },
                "guild": {
                    "id": str(guild.id),
                    "name": guild.name
                },
                "roles": roles,
                "role_count": len(roles)
            }
        except Exception as e:
            logger.error(f"Error getting user roles: {e}")
            return {"error": f"Failed to get user roles: {str(e)}"}

    def _parse_channel_id(self, channel_id: str) -> Optional[int]:
        """
        Parse channel ID from various formats with security validation:
        - Raw numeric ID: "123456789"
        - Discord mention format: "<#123456789>"
        Returns int if valid, None if invalid
        """
        try:
            # Import security validator
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from utils.security_validator import validator
            
            # Validate the input first
            is_valid, error = validator.validate_discord_id(channel_id)
            if not is_valid:
                logger.warning(f"Invalid channel ID format: {error}")
                return None
            
            # Handle Discord mention format: <#123456789>
            if channel_id.startswith('<#') and channel_id.endswith('>'):
                numeric_part = channel_id[2:-1]  # Remove <# and >
                return int(numeric_part)
            # Handle raw numeric ID
            else:
                return int(channel_id)
        except (ValueError, TypeError, ImportError):
            return None

# Global Discord tools instance (will be initialized with bot client)
discord_tools = None

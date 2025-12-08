"""
tip.cc Manager for JakeySelfBot
Handles all tip.cc interactions including balance tracking and command sending
"""

import asyncio
import re
import json
import time
import discord
from typing import Optional, Dict, List, Any
from data.database import db
import logging

from utils.logging_config import get_logger
logger = get_logger(__name__)

class TipCCManager:
    """Manager for tip.cc interactions and balance tracking"""

    def __init__(self, bot_instance=None):
        self.bot = bot_instance
        self.tip_cc_bot_id = 617037497574359050  # tip.cc bot ID
        self.balance_cache = {}
        self.last_balance_update = 0
        self.balance_update_interval = 300  # 5 minutes between balance updates

        # Tip thank you tracking
        self.thank_you_cooldown = {}  # user_id -> last_thank_you_timestamp

    async def send_tip_command(self, channel, recipient: str, amount: str, currency: str, message: str = "", sender_id: Optional[str] = None) -> bool:
        """Send a tip command as a separate message with security validation"""
        try:
            # Validate tip parameters using security framework
            try:
                from utils.security_validator import validator
                is_valid, error = validator.validate_tip_command(recipient, amount, currency, message)
                if not is_valid:
                    logger.error(f"Tip validation failed: {error}")
                    return False
            except ImportError:
                # Fallback validation
                if not recipient or not amount or not currency:
                    logger.error("Missing required tip parameters")
                    return False

            # Format the tip command safely
            recipient_safe = recipient.strip()
            amount_safe = amount.strip()
            currency_safe = currency.upper().strip()
            message_safe = message.strip() if message else ""
            
            if message_safe:
                tip_command = f"$tip {recipient_safe} {amount_safe} {currency_safe} {message_safe}"
            else:
                tip_command = f"$tip {recipient_safe} {amount_safe} {currency_safe}"

            # Send the command as a separate message
            await channel.send(tip_command)
            logger.info(f"Sent tip command: {tip_command}")

            # Record the transaction (estimated USD value)
            # Handle "all" amount by recording with 0 amount - will be updated when tip.cc responds
            if amount_safe.lower() == 'all':
                usd_value = 0.0  # Can't estimate USD value for "all"
                record_amount = -1.0  # Use -1 to indicate "all" amount
            else:
                usd_value = await self._estimate_usd_value(amount_safe, currency_safe)
                record_amount = float(amount_safe)
            # Extract user ID from mention if needed
            if recipient_safe.startswith('<@') and recipient_safe.endswith('>'):
                recipient_id = recipient_safe[2:-1]
                # Handle nicknames by removing ! if present
                if recipient_id.startswith('!'):
                    recipient_id = recipient_id[1:]
            else:
                recipient_id = recipient_safe

            await db.aadd_transaction('tip_sent', currency_safe, record_amount, usd_value, recipient_id, message_safe, sender_id)

            return True

        except Exception as e:
            logger.error(f"Error sending tip command: {e}")
            return False

    async def send_airdrop_command(self, channel, amount: str, currency: str, duration: str) -> bool:
        """Send an airdrop command as a separate message"""
        try:
            # Format the airdrop command
            airdrop_command = f"$airdrop {amount} {currency} for {duration}"

            # Send the command as a separate message
            await channel.send(airdrop_command)
            logger.info(f"Sent airdrop command: {airdrop_command}")

            # Record the airdrop as a sent transaction (money spent by Jakey)
            # This is the cost of the airdrop that will be distributed to participants
            currency_safe = currency.upper().strip()
            if amount.lower() == 'all':
                usd_value = 0.0  # Can't estimate USD value for "all"
                record_amount = -1.0  # Use -1 to indicate "all" amount
            else:
                record_amount = float(amount)
                usd_value = await self._estimate_usd_value(record_amount, currency_safe)

            # Record this as a tip_sent transaction (money going out from Jakey)
            sender_id = str(self.bot.user.id) if self.bot and self.bot.user else None
            if sender_id:  # Only record if we have a valid sender ID
                await db.aadd_transaction('airdrop_sent', currency_safe, record_amount, usd_value, 'participants', f'Airdrop for {duration}', sender_id)

            return True

        except Exception as e:
            logger.error(f"Error sending airdrop command: {e}")
            return False

    async def send_balance_command(self, channel) -> bool:
        """Send a balance command as a separate message"""
        try:
            # Send the balance command
            await channel.send("$balances top noembed")
            logger.info("Sent balance command")

            return True

        except Exception as e:
            logger.error(f"Error sending balance command: {e}")
            return False

    async def parse_tip_cc_message(self, message) -> Optional[Dict[str, Any]]:
        """Parse tip.cc messages to extract transaction data"""
        if message.author.id != self.tip_cc_bot_id:
            return None

        try:
            # Handle balance responses
            if message.embeds:
                embed = message.embeds[0]

                # Balance embed parsing
                if embed.title and "balances" in embed.title.lower():
                    return await self._parse_balance_embed(embed)

                # Transaction embed parsing
                elif embed.title and any(keyword in embed.title.lower() for keyword in ["tip", "airdrop", "deposit", "withdraw"]):
                    return await self._parse_transaction_embed(embed)

            # Handle regular messages (like airdrop results)
            elif message.content:
                return await self._parse_transaction_message(message)

        except Exception as e:
            logger.error(f"Error parsing tip.cc message: {e}")

        return None

    async def _parse_balance_embed(self, embed) -> Dict[str, Any]:
        """Parse balance embed and update database"""
        try:
            # Extract balances from embed description or fields
            balances = []
            total_usd = 0.0

            # Check if title contains balance info
            if embed.title and "balances" in embed.title.lower():
                # Parse the description which contains the actual balance info
                if embed.description:
                    content = embed.description
                    # Parse each line for balance info using the actual format
                    lines = content.split('\n')

                    for line in lines:
                        # Handle different currency formats:
                        # "Pepecoin: <:PEPE:1309876764817752065> 1,157.86 PEPE (≈ $0.39)"
                        # "Bitcoin: <:BTC:903867169568325642> 27 satoshi (≈ $0.03)"
                        # "Tether USD (Solana): <:solUSDT:1316078527149244447> 0.1493 solUSDT (≈ $0.14)"

                        # Look for USD values first
                        usd_match = re.search(r'\(≈\s*\$([\d,.]+)\)', line)
                        if not usd_match:
                            continue

                        usd_value = float(usd_match.group(1).replace(',', ''))

                        # Extract currency and amount
                        # Match currency name (may contain spaces, parentheses, special chars)
                        currency_match = re.search(r'^\*\*([^:]+):\*\*', line)
                        if not currency_match:
                            continue

                        currency_name = currency_match.group(1).strip()

                        # Extract amount - this is complex due to various formats
                        amount_patterns = [
                            r'([\d,.]+)\s+([A-Z]{2,10})',  # Regular format: "1,157.86 PEPE"
                            r'([\d,.]+)\s+satoshi',       # Bitcoin format: "27 satoshi"
                        ]

                        amount = 0.0
                        currency_symbol = ''

                        for pattern in amount_patterns:
                            amount_match = re.search(pattern, line)
                            if amount_match:
                                amount = float(amount_match.group(1).replace(',', ''))
                                currency_symbol = amount_match.group(2) if len(amount_match.groups()) > 1 else 'BTC'
                                break

                        # Clean up currency name for database storage
                        clean_currency = currency_name.upper()
                        if '(' in clean_currency:
                            clean_currency = clean_currency.split('(')[0].strip()
                        if 'USD' in clean_currency and clean_currency != 'USD':
                            clean_currency = 'USDT'  # Normalize USD variants

                        # Handle special cases
                        if clean_currency == 'PEPECOIN':
                            clean_currency = 'PEPE'
                        elif clean_currency == 'TETHER USD':
                            clean_currency = 'USDT'
                        elif clean_currency == 'BITCOIN':
                            clean_currency = 'BTC'

                        balances.append({
                            'currency': clean_currency,
                            'amount': amount,
                            'usd_value': usd_value,
                            'display_name': currency_name
                        })

                        total_usd += usd_value

                        # Update database
                        await db.aupdate_balance(clean_currency, amount, usd_value)

            # Update cache
            self.balance_cache = {
                'balances': balances,
                'total_usd': total_usd,
                'timestamp': time.time()
            }
            self.last_balance_update = time.time()
            return {
                'type': 'balance_update',
                'balances': balances,
                'total_usd': total_usd,
                'raw_message': embed.description if embed.description else ''
            }

        except Exception as e:
            logger.error(f"Error parsing balance embed: {e}")
            return {}

    async def _parse_transaction_embed(self, embed) -> Dict[str, Any]:
        """Parse transaction embed and record transaction"""
        try:
            # Extract transaction details from embed
            title = embed.title.lower() if embed.title else ""
            description = embed.description or ""

            # Determine transaction type - more robust detection
            title_lower = title.lower()
            description_lower = description.lower()

            if 'airdrop' in title_lower:
                transaction_type = 'airdrop'
            elif 'deposit' in title_lower:
                transaction_type = 'deposit'
            elif 'withdraw' in title_lower:
                transaction_type = 'withdraw'
            elif 'tip' in title_lower:
                # For tips, check if this is sent or received by looking at description structure
                # Description format: "<@sender> sent <@recipient> amount currency"
                if ' sent ' in description_lower:
                    # Check if bot is the recipient (received tip) or sender (sent tip)
                    bot_mention = f'<@{self.bot.user.id}>' if self.bot and self.bot.user else ''
                    if bot_mention and bot_mention in description_lower:
                        # Find bot's position in description
                        bot_pos = description_lower.find(bot_mention)
                        sent_pos = description_lower.find(' sent ')

                        if bot_pos > sent_pos:
                            # Bot is after "sent" = bot is recipient = received tip
                            transaction_type = 'tip_received'
                        else:
                            # Bot is before "sent" = bot is sender = sent tip
                            transaction_type = 'tip_sent'
                    else:
                        # Default to sent tip if bot not mentioned
                        transaction_type = 'tip_sent'
                else:
                    transaction_type = 'other'
            else:
                transaction_type = 'other'

            # Parse amount and currency from description (handles bold formatting)
            amount_match = re.search(r'\*\*([\d,.]+)\s*([A-Z]{3,4})\*\*', description)
            # Fallback to non-bold format if bold not found
            if not amount_match:
                amount_match = re.search(r'([\d,.]+)\s*([A-Z]{3,4})', description)
            if amount_match:
                amount = float(amount_match.group(1).replace(',', ''))
                currency = amount_match.group(2)

                # Try to extract USD value from tip.cc message first
                usd_match = re.search(r'\(≈\s*\$([\d,.]+)\)', description)
                if usd_match:
                    usd_value = float(usd_match.group(1).replace(',', ''))
                else:
                    # Fallback to estimation if not in message
                    usd_value = await self._estimate_usd_value(amount, currency)

                # Extract recipient and sender from description
                # Handle format: "<:CURRENCY:ID> <@sender> sent <@recipient> amount currency"
                # or format: "<@sender> sent <@recipient> amount currency"

                # Find all user mentions in order
                mention_matches = list(re.finditer(r'<@!?(\d+)>', description))

                # Find where "sent" appears
                sent_pos = description.find(' sent ')

                sender = None
                recipient = None

                if mention_matches and sent_pos != -1:
                    # Find the mention before "sent" (sender)
                    for match in mention_matches:
                        if match.start() < sent_pos:
                            sender = match.group(1)
                            break

                    # Find the mention after "sent" (recipient)
                    for match in mention_matches:
                        if match.start() > sent_pos:
                            recipient = match.group(1)
                            break
                else:
                    # Fallback to old parsing method for backward compatibility
                    sender_match = re.search(r'^<@!?(\d+)>', description)
                    recipient_match = re.search(r'sent <@!?(\d+)>', description)
                    sender = sender_match.group(1) if sender_match else None
                    recipient = recipient_match.group(1) if recipient_match else None

                # Record transaction
                await db.aadd_transaction(transaction_type, currency, amount, usd_value, recipient or '', description, sender)

                # Check if this is a tip received by Jakey and send thank you
                if (transaction_type == 'tip_received' and
                    recipient and
                    sender and
                    self.bot and self.bot.user and
                    str(self.bot.user.id) == recipient):
                    await self._send_tip_thank_you(sender, amount, currency, usd_value)

                return {
                    'type': 'transaction',
                    'transaction_type': transaction_type,
                    'currency': currency,
                    'amount': amount,
                    'usd_value': usd_value,
                    'recipient': recipient,
                    'sender': sender,
                    'description': description
                }

        except Exception as e:
            logger.error(f"Error parsing transaction embed: {e}")

        return {}

    async def _parse_transaction_message(self, message) -> Dict[str, Any]:
        """Parse transaction message and record transaction"""
        try:
            content = message.content.lower() if message.content else ""
            original_content = message.content or ""

            # Airdrop results
            if 'you received' in content and 'from the airdrop' in content:
                # Parse airdrop amount
                amount_match = re.search(r'([\d,.]+)\s*([a-z]{3,4})', content)
                if amount_match:
                    amount = float(amount_match.group(1).replace(',', ''))
                    currency = amount_match.group(2).upper()
                    usd_value = await self._estimate_usd_value(amount, currency)

                    # Record airdrop transaction
                    sender_id = str(self.bot.user.id) if self.bot and self.bot.user else None
                    await db.aadd_transaction('airdrop', currency, amount, usd_value, None, None, sender_id)

                    # Update balance
                    current_balance = await db.aget_balance(currency)
                    if current_balance:
                        new_amount = current_balance['amount'] + amount
                        await db.aupdate_balance(currency, new_amount, current_balance['usd_value'] + usd_value)

                    return {
                        'type': 'airdrop_result',
                        'currency': currency,
                        'amount': amount,
                        'usd_value': usd_value
                    }

            # Tip notifications (plain text format)
            # Format: "@sender sent @recipient amount currency (≈ $usd_value)."
            elif ' sent ' in content:
                # Parse sender, recipient, amount, currency from plain text tip message
                sender_match = re.search(r'^<@!?(\d+)>', original_content)
                recipient_match = re.search(r'sent <@!?(\d+)>', original_content)
                amount_match = re.search(r'([\d,.]+)\s*([A-Z]{3,4})', original_content)

                if sender_match and recipient_match and amount_match:
                    sender = sender_match.group(1)
                    recipient = recipient_match.group(1)
                    amount = float(amount_match.group(1).replace(',', ''))
                    currency = amount_match.group(2)
                    usd_value = await self._estimate_usd_value(amount, currency)

                    # Determine transaction type
                    transaction_type = 'tip_sent'
                    if self.bot and self.bot.user and str(self.bot.user.id) == recipient:
                        transaction_type = 'tip_received'

                    # Record transaction
                    await db.aadd_transaction(transaction_type, currency, amount, usd_value, recipient or '', original_content, sender)

                    # Check if this is a tip received by Jakey and send thank you
                    if (transaction_type == 'tip_received' and
                        recipient and
                        sender and
                        self.bot and self.bot.user and
                        str(self.bot.user.id) == recipient):
                        await self._send_tip_thank_you(sender, amount, currency, usd_value)

                    return {
                        'type': 'transaction',
                        'transaction_type': transaction_type,
                        'currency': currency,
                        'amount': amount,
                        'usd_value': usd_value,
                        'recipient': recipient,
                        'sender': sender,
                        'description': original_content
                    }

        except Exception as e:
            logger.error(f"Error parsing transaction message: {e}")

        return {}

    async def _estimate_usd_value(self, amount, currency: str) -> float:
        """Estimate USD value for a cryptocurrency amount"""
        try:
            # Convert amount to string if it's not already
            amount_str = str(amount)

            # Skip USD estimation for non-numeric amounts like "all"
            if amount_str.lower() in ['all', 'max', 'half']:
                return 0.0

            # Use the tool manager to get price
            amount_float = float(amount_str)
            if currency.upper() == 'USD':
                return amount_float

            # Get price from tool manager
            if self.bot and hasattr(self.bot, 'tool_manager'):
                price_info = self.bot.tool_manager.get_crypto_price(currency.upper())
            else:
                price_info = None
            if isinstance(price_info, str):
                # Parse price from string response
                price_match = re.search(r'\$([\d,.]+)', price_info)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
                    return amount_float * price
            elif isinstance(price_info, (int, float)):
                return amount_float * price_info

        except Exception as e:
            logger.error(f"Error estimating USD value: {e}")

        return 0.0

    async def get_formatted_balances(self) -> str:
        """Get formatted balance string for display"""
        try:
            # First try to get cached data from the most recent tip.cc response
            if (self.balance_cache and
                time.time() - self.balance_cache.get('timestamp', 0) < 300):  # 5 minutes cache

                cached_data = self.balance_cache
                balances = cached_data['balances']
                total_usd = cached_data['total_usd']

                if balances:
                    balance_lines = []
                    for balance in balances:
                        # Use display name if available, otherwise currency code
                        display_name = balance.get('display_name', balance['currency'])
                        balance_lines.append(f"**{display_name}**: {balance['amount']:.8f} (~${balance['usd_value']:.2f})")

                    result = "💰 **Jakey's tip.cc Balances (Live Data):**\n\n"
                    result += "\n".join(balance_lines)
                    result += f"\n\n**Total Value**: ~${total_usd:.2f} USD"
                    return result

            # Fall back to database if no recent cache
            balances = await db.aget_all_balances()
            total_usd = await db.aget_total_usd_balance()

            if not balances:
                return "💀 **No balances found** Use `$balance` to check your tip.cc balances."

            balance_lines = []
            for balance in balances:
                balance_lines.append(f"**{balance['currency']}**: {balance['amount']:.8f} (~${balance['usd_value']:.2f})")

            result = "💰 **Jakey's tip.cc Balances (Cached):**\n\n"
            result += "\n".join(balance_lines)
            result += f"\n\n**Total Value**: ~${total_usd:.2f} USD"

            return result

        except Exception as e:
            logger.error(f"Error formatting balances: {e}")
            return "💀 **Error retrieving balances**"

    async def get_transaction_history(self, limit: int = 10) -> str:
        """Get formatted transaction history"""
        try:
            transactions = await db.aget_recent_transactions(limit)
            stats = await db.aget_transaction_stats()

            if not transactions:
                return "💀 **No transactions found**"

            transaction_lines = []
            for tx in transactions:
                emoji = self._get_transaction_emoji(tx['type'])

                # Handle "all" amounts (stored as -1)
                if tx['amount'] == -1.0:
                    amount_str = "ALL"
                else:
                    amount_str = f"{tx['amount']:.8f}"

                line = f"{emoji} **{tx['type'].replace('_', ' ').title()}**: {amount_str} {tx['currency']} (~${tx['usd_value']:.2f})"
                
                # Show sender and recipient information
                if tx['sender']:
                    line += f" from <@{tx['sender']}>"
                if tx['recipient']:
                    if tx['sender']:
                        line += f" to <@{tx['recipient']}>"
                    else:
                        line += f" to <@{tx['recipient']}>"
                transaction_lines.append(line)

            result = "📊 **Recent tip.cc Transactions:**\n\n"
            result += "\n".join(transaction_lines)

            # Add stats summary
            result += f"\n\n**Stats:**\n"
            result += f"🎯 Total Airdrops: ${stats['total_airdrops_usd']:.2f}\n"
            result += f"📤 Total Sent: ${stats['total_sent_usd']:.2f}\n"
            result += f"📥 Total Received: ${stats['total_received_usd']:.2f}\n"
            result += f"💰 Net Profit: ${stats['net_profit_usd']:.2f}"

            return result

        except Exception as e:
            logger.error(f"Error formatting transaction history: {e}")
            return "💀 **Error retrieving transaction history**"

    def _get_transaction_emoji(self, transaction_type: str) -> str:
        """Get emoji for transaction type"""
        emoji_map = {
            'airdrop': '🎁',
            'tip_sent': '📤',
            'tip_received': '📥',
            'deposit': '💳',
            'withdraw': '💸',
            'other': '💱'
        }
        return emoji_map.get(transaction_type, '💱')

    async def _send_tip_thank_you(self, sender_id: str, amount: float, currency: str, usd_value: float):
        """Send a thank you message when Jakey receives a tip"""
        try:
            from config import TIP_THANK_YOU_ENABLED, TIP_THANK_YOU_MESSAGES, TIP_THANK_YOU_EMOJIS, TIP_THANK_YOU_COOLDOWN

            # Check if thank you messages are enabled
            if not TIP_THANK_YOU_ENABLED:
                return

            # Check cooldown
            current_time = time.time()
            if sender_id in self.thank_you_cooldown:
                if current_time - self.thank_you_cooldown[sender_id] < TIP_THANK_YOU_COOLDOWN:
                    logger.debug(f"Thank you message on cooldown for user {sender_id}")
                    return

            # Update cooldown
            self.thank_you_cooldown[sender_id] = current_time

            # Select random thank you message and emoji
            import random
            thank_you_message = random.choice(TIP_THANK_YOU_MESSAGES)
            thank_you_emoji = random.choice(TIP_THANK_YOU_EMOJIS)

            # Format the thank you message
            response = f"<@{sender_id}> {thank_you_message} {thank_you_emoji}"

            # Find a channel to send the thank you message
            # Look for a channel where both the sender and Jakey are present
            target_channel = None
            if not self.bot:
                return
            for guild in self.bot.guilds:
                # Check if sender is in this guild
                member = guild.get_member(int(sender_id))
                if member and self.bot.user and member != self.bot.user:
                    # Find a text channel where both can see
                    for channel in guild.text_channels:
                        if (channel.permissions_for(guild.me).send_messages and
                            channel.permissions_for(member).view_channel):
                            target_channel = channel
                            break
                    if target_channel:
                        break

            if target_channel:
                await target_channel.send(response)
                logger.info(f"Sent thank you message to user {sender_id} for {amount} {currency} tip")
            else:
                logger.warning(f"Could not find suitable channel to send thank you message to user {sender_id}")

        except Exception as e:
            logger.error(f"Error sending thank you message: {e}")

    async def handle_tip_cc_response(self, message):
        """Handle tip.cc bot responses and update data"""
        try:
            parsed_data = await self.parse_tip_cc_message(message)
            if parsed_data:
                logger.info(f"Processed tip.cc message: {parsed_data.get('type', 'unknown')}")
                # If this is a balance update, auto-dismiss after 8 seconds
                if parsed_data.get('type') == 'balance_update':
                    # Schedule auto-dismiss of the balance message
                    # Don't wait - start the task in the background
                    asyncio.create_task(self._auto_dismiss_balance_message(message))
            
            # Check for confirmation messages and auto-click Confirm button
            await self._handle_confirmation_message(message)

        except Exception as e:
            logger.error(f"Error handling tip.cc response: {e}")

    async def _auto_dismiss_balance_message(self, original_message):
        """Auto-dismiss balance message after delay by clicking X button"""
        try:
            # Wait 8 seconds before dismissing
            await asyncio.sleep(8)

            # Search for the most recent tip.cc bot balance message
            target_message = None
            async for msg in original_message.channel.history(limit=30):
                if (msg.author.id == self.tip_cc_bot_id and
                    msg.embeds and
                    "balance" in msg.embeds[0].title.lower()):
                    target_message = msg
                    break

            if not target_message:
                return

            # Try to click the dismiss button
            dismissed = False

            # Look for X emoji button
            for component in target_message.components:
                for child in getattr(component, 'children', []):
                    try:
                        if hasattr(child, 'emoji') and child.emoji:
                            emoji_name = getattr(child.emoji, 'name', '')
                            if emoji_name in ['❌', '✖', '🗑️', 'x', '❎']:
                                await child.click()
                                dismissed = True
                                return

                        # Check for dismiss/close button
                        if hasattr(child, 'label') and child.label:
                            label = child.label.lower()
                            if any(word in label for word in ['dismiss', 'close', 'delete', 'remove', 'x']):
                                await child.click()
                                dismissed = True
                                return

                        # Try clicking any button as last resort
                        await child.click()
                        dismissed = True
                        return
                    except Exception:
                        continue

            # Try clicking any component
            if not dismissed:
                for component in target_message.components:
                    try:
                        if hasattr(component, 'click'):
                            await component.click()
                            dismissed = True
                            return
                    except Exception:
                        continue

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in auto-dismiss task: {e}")

    async def _handle_confirmation_message(self, message):
        """Handle tip.cc confirmation messages and auto-click Confirm button"""
        try:
            # Check if this is a confirmation message
            if not message.embeds:
                return
                
            embed = message.embeds[0]
            if not embed.title or "confirm" not in embed.title.lower():
                return
                
            logger.info("Detected tip.cc confirmation message")
            
            # Look for Confirm button
            confirm_button = None
            cancel_button = None
            
            for component in message.components:
                for child in getattr(component, 'children', []):
                    if hasattr(child, 'type') and child.type == discord.ComponentType.button:
                        button_label = getattr(child, 'label', '').lower()
                        button_custom_id = getattr(child, 'custom_id', '').lower()
                        
                        # Look for Confirm button (usually on the left)
                        if (button_label == 'confirm' or 
                            'confirm' in button_custom_id or
                            'accept' in button_custom_id):
                            confirm_button = child
                            logger.info("Found Confirm button")
                            
                        # Look for Cancel button (usually on the right)
                        elif (button_label == 'cancel' or 
                              'cancel' in button_custom_id or
                              'decline' in button_custom_id):
                            cancel_button = child
                            logger.info("Found Cancel button")
            
            # Click the Confirm button if found and not disabled - Optimized for speed
            if confirm_button and not getattr(confirm_button, 'disabled', False):
                # Ultra-fast confirmation click - minimal overhead
                try:
                    logger.debug("Attempting instant confirm button click")
                    await asyncio.wait_for(confirm_button.click(), timeout=1.5)
                    logger.info("Successfully clicked Confirm button")
                except asyncio.TimeoutError:
                    logger.debug("Confirm button click timeout")
                except discord.HTTPException as e:
                    if "10008" in str(e):
                        logger.debug("Confirmation message expired")
                    else:
                        logger.debug(f"Confirm HTTP error: {e}")
                except discord.ClientException as e:
                    logger.debug(f"Confirm client error: {e}")
                except Exception as e:
                    logger.debug(f"Confirm unexpected error: {e}")
            else:
                logger.debug("Confirm button not found or disabled")
                
        except Exception as e:
            logger.error(f"Error handling confirmation message: {e}")

# Global tip.cc manager instance
tipcc_manager = None

def init_tipcc_manager(bot_instance):
    """Initialize the global tip.cc manager"""
    global tipcc_manager
    tipcc_manager = TipCCManager(bot_instance)
    return tipcc_manager

def get_tipcc_manager() -> TipCCManager:
    """Get the global tip.cc manager"""
    if tipcc_manager is None:
        raise RuntimeError("TipCCManager not initialized. Call init_tipcc_manager() first.")
    return tipcc_manager

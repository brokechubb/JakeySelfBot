import re
from typing import List, Dict, Any
from datetime import datetime

def extract_user_mentions(message_content: str) -> List[str]:
    """Extract user mentions from message content"""
    mention_pattern = r'<@!?(\d+)>'
    return re.findall(mention_pattern, message_content)

def extract_channel_mentions(message_content: str) -> List[str]:
    """Extract channel mentions from message content"""
    channel_pattern = r'<#(\d+)>'
    return re.findall(channel_pattern, message_content)

def extract_emojis(message_content: str) -> List[str]:
    """Extract emojis from message content"""
    # This is a simple emoji extraction - you might want to use a more robust library
    emoji_pattern = r'<a?:\w+:\d+>'
    return re.findall(emoji_pattern, message_content)

def format_timestamp(timestamp: str) -> str:
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp

def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def split_message_for_discord(text: str, max_length: int = 2000) -> list[str]:
    """
    Split a long message into multiple messages that fit within Discord's character limit.
    
    Args:
        text: The text to split
        max_length: Maximum length per message (default 2000 for Discord)
        
    Returns:
        List of message chunks that each fit within the limit
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by lines first to preserve formatting
    lines = text.split('\n')
    
    for line in lines:
        # If the line itself is too long, split it by words
        if len(line) > max_length:
            # Flush current chunk if it has content
            if current_chunk:
                chunks.append(current_chunk.rstrip())
                current_chunk = ""
            
            # Split the long line by words
            words = line.split(' ')
            word_chunk = ""
            
            for word in words:
                # Add space if needed
                test_word = word if not word_chunk else word_chunk + ' ' + word
                
                if len(test_word) <= max_length:
                    word_chunk = test_word
                else:
                    # Flush current word chunk
                    if word_chunk:
                        chunks.append(word_chunk)
                        word_chunk = word
                    else:
                        # Single word is too long, split it
                        while len(word) > max_length:
                            chunks.append(word[:max_length])
                            word = word[max_length:]
                        word_chunk = word
            
            # Add remaining word chunk
            if word_chunk:
                current_chunk = word_chunk
        
        else:
            # Check if adding this line would exceed the limit
            test_chunk = current_chunk + ('\n' if current_chunk else '') + line
            
            if len(test_chunk) <= max_length:
                current_chunk = test_chunk
            else:
                # Flush current chunk and start new one
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                current_chunk = line
    
    # Add final chunk
    if current_chunk:
        chunks.append(current_chunk.rstrip())
    
    return chunks

async def send_long_message(channel, text: str, max_length: int = 2000):
    """
    Send a long message by splitting it into multiple Discord messages.
    
    Args:
        channel: Discord channel object to send messages to
        text: The text to send
        max_length: Maximum length per message (default 2000 for Discord)
    """
    chunks = split_message_for_discord(text, max_length)
    
    for chunk in chunks:
        await channel.send(chunk)

def sanitize_username(username: str) -> str:
    """Sanitize username for database storage"""
    # Remove any potentially harmful characters
    return re.sub(r'[^\w\-_]', '', username)[:32]  # Limit to 32 characters

def is_valid_discord_id(discord_id: str) -> bool:
    """Check if a string is a valid Discord ID"""
    return discord_id.isdigit() and len(discord_id) in [17, 18, 19]

def format_tool_response(tool_name: str, result: str) -> str:
    """Format tool response for better readability"""
    return f"[{tool_name.upper()}]: {result}"

def detect_tool_request(message_content: str) -> List[str]:
    """Detect if a message is requesting a specific tool"""
    tools = []
    message_lower = message_content.lower()
    
    # Common tool request patterns
    if 'search' in message_lower or 'find' in message_lower or 'look up' in message_lower:
        tools.append('web_search')
    
    if any(keyword in message_lower for keyword in ['price', 'crypto', 'btc', 'eth', 'stock', '$']):
        if any(keyword in message_lower for keyword in ['crypto', 'btc', 'eth', 'coin']):
            tools.append('crypto_price')
        else:
            tools.append('stock_price')
    
    if any(keyword in message_lower for keyword in ['calculate', 'math', 'compute', '+', '-', '*', '/']):
        tools.append('calculate')
    
    if any(keyword in message_lower for keyword in ['wen', 'when', 'bonus', 'schedule']):
        tools.append('get_bonus_schedule')
    
    return tools

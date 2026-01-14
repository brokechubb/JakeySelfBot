"""
Security Validation Framework for JakeySelfBot
Provides centralized input validation and sanitization to prevent injection attacks
"""

import re
import html
import urllib.parse
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SecurityValidator:
    """Centralized security validation and sanitization"""
    
    # Dangerous patterns that should never be allowed
    DANGEROUS_PATTERNS = [
        r'\$\(',           # Command substitution
        r'`',              # Command execution
        r'\|\|',           # Command chaining
        r'&&',             # Command chaining
        r';',              # Command separation
        r'&',              # Background execution
        r'\|',             # Pipe
        r'>>',             # Append redirection
        r'<<',             # Here document
        r'~/',             # Home directory paths
        r'\.\./',          # Directory traversal
        r'\/etc\/',        # System directory access
        r'\/proc\/',       # Process filesystem
        r'\/sys\/',        # System filesystem
        r'\/dev\/',        # Device filesystem
        r'rm\s+-',         # Dangerous file operations
        r'dd\s+if=',       # Disk operations
        r'mkfs\.',         # Filesystem operations
        r'fdisk',          # Disk partitioning
        r'format',         # Disk formatting
        r'del\s+/',        # Windows delete operations
        r'rmdir\s+/',      # Directory removal
        r'chmod\s+[0-7]{3}', # Permission changes
        r'chown\s+',       # Ownership changes
        r'sudo\s+',        # Privilege escalation
        r'su\s+',          # User switching
        r'passwd\s+',      # Password operations
        r'crontab',        # Cron operations
        r'systemctl\s+',   # Service control
        r'service\s+',     # Service management
        r'init\s+',        # Init system
        r'reboot',         # System reboot
        r'shutdown',       # System shutdown
        r'poweroff',       # System poweroff
        r'halt',           # System halt
    ]

    # Shell redirection patterns (separate from general dangerous patterns)
    SHELL_REDIRECTION_PATTERNS = [
        r'<\s*\w+',        # Input redirection with files (but allow Discord mentions)
        r'>>\s*\w+',       # Append redirection to files
        # More specific output redirection pattern - require file-like context
        r'(?:echo|cat|ls|printf|print)\s+[^>]*>\s*\w+',  # Command followed by > and word
        r'(?:>|>>)\s*(?:\/|[a-zA-Z]:\\|tmp|var|home|usr|opt)\S*',  # > followed by path-like patterns
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(\'|(\'\')|(\'\s+;)|(\'\s+--))',
        r'(\-\-|\#)',
        r'(\;|\s+;)',
        r'(\/\*|\*\/)',
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
        r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
        r'(\b(OR|AND)\s+\'\w+\'\s*=\s*\'\w+\')',
        r'(\b(OR|AND)\s+\"\w+\"\s*=\s*\"\w+\")',
        r'(\b(OR|AND)\s+1\s*=\s*1)',
        r'(\b(OR|AND)\s+true\s*=\s*true)',
        r'(\b(OR|AND)\s+false\s*=\s*false)',
        r'(\bWAITFOR\s+DELAY\b)',
        r'(\bSLEEP\s*\()',
        r'(\bBENCHMARK\s*\()',
        r'(\bPG_SLEEP\s*\()',
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r'<\s*script[^>]*>',
        r'<\s*\/script\s*>',
        r'javascript\s*:',
        r'vbscript\s*:',
        r'onload\s*=',
        r'onerror\s*=',
        r'onclick\s*=',
        r'onmouseover\s*=',
        r'onfocus\s*=',
        r'onblur\s*=',
        r'onchange\s*=',
        r'onsubmit\s*=',
        r'<\s*iframe[^>]*>',
        r'<\s*object[^>]*>',
        r'<\s*embed[^>]*>',
        r'<\s*link[^>]*>',
        r'<\s*meta[^>]*>',
        r'<\s*style[^>]*>',
        r'<\s*img[^>]*on\w+\s*=',
        r'<\s*input[^>]*on\w+\s*=',
        r'<\s*form[^>]*on\w+\s*=',
        r'<\s*body[^>]*on\w+\s*=',
        r'<\s*html[^>]*on\w+\s*=',
    ]
    
    # Discord-specific dangerous patterns (updated to allow safe mentions)
    DISCORD_DANGEROUS_PATTERNS = [
        r'@everyone',
        r'@here',
        r'<@&\d+>',      # Role mentions (restrict these)
        r'<@!\d+>',      # Nickname user mentions (allow for now)
        r'<:\w+:\d+>',   # Custom emoji (allow for now)
        r'https?:\/\/discord\.com\/api\/webhooks\/',  # Webhook URLs
        r'https?:\/\/discord\.com\/channels\/\d+\/\d+\/\d+',  # Message links
    ]

    # Safe Discord mention patterns (allowed)
    DISCORD_SAFE_PATTERNS = [
        r'<@\d+>',       # Regular user mentions
        r'<@!\d+>',      # Nickname user mentions
        r'<#\d+>',       # Channel mentions
        r'<:\w+:\d+>',   # Custom emoji
    ]
    
    @classmethod
    def validate_string(cls, input_string: str, max_length: int = 1000, 
                       allow_empty: bool = False, 
                       forbidden_patterns: Optional[List[str]] = None) -> tuple[bool, str]:
        """
        Validate a generic string input
        
        Returns:
            tuple: (is_valid, error_message)
        """
        if not isinstance(input_string, str):
            return False, "Input must be a string"
        
        # Check for null bytes and control characters
        if '\x00' in input_string:
            return False, "Null bytes are not allowed"
        
        # Check for control characters (except common whitespace)
        if any(ord(char) < 32 and char not in ['\t', '\n', '\r'] for char in input_string):
            return False, "Control characters are not allowed"
        
        # Check length
        if len(input_string) > max_length:
            return False, f"Input too long (max {max_length} characters)"
        
        # Check if empty is allowed
        if not allow_empty and not input_string.strip():
            return False, "Input cannot be empty"
        
        # Check for forbidden patterns
        patterns_to_check = cls.DANGEROUS_PATTERNS + (forbidden_patterns or [])
        for pattern in patterns_to_check:
            if re.search(pattern, input_string, re.IGNORECASE):
                return False, f"Input contains dangerous pattern: {pattern}"
        
        return True, ""
    
    @classmethod
    def validate_discord_id(cls, discord_id: str) -> tuple[bool, str]:
        """Validate Discord user ID, channel ID, or guild ID"""
        if not isinstance(discord_id, str):
            return False, "Discord ID must be a string"
        
        # Remove common Discord mention formats
        clean_id = discord_id.strip()
        if clean_id.startswith('<@') and clean_id.endswith('>'):
            clean_id = clean_id[2:-1]
            if clean_id.startswith('!'):
                clean_id = clean_id[1:]
        elif clean_id.startswith('<#') and clean_id.endswith('>'):
            clean_id = clean_id[2:-1]
        
        # Validate numeric format (Discord IDs are 17-19 digit snowflakes)
        if not re.match(r'^\d{17,19}$', clean_id):
            return False, "Invalid Discord ID format"
        
        return True, ""
    
    @classmethod
    def validate_cryptocurrency_symbol(cls, symbol: str) -> tuple[bool, str]:
        """Validate cryptocurrency symbol"""
        is_valid, error = cls.validate_string(symbol, max_length=20)
        if not is_valid:
            return False, error
        
        # Allow only alphanumeric characters (supports longer token names like solUSDC)
        if not re.match(r'^[A-Z0-9]{1,20}$', symbol.upper()):
            return False, "Invalid cryptocurrency symbol format"
        
        return True, ""
    
    @classmethod
    def validate_currency_code(cls, currency: str) -> tuple[bool, str]:
        """Validate currency code (ISO 4217)"""
        is_valid, error = cls.validate_string(currency, max_length=3)
        if not is_valid:
            return False, error
        
        # Allow only 3-letter currency codes
        if not re.match(r'^[A-Z]{3}$', currency.upper()):
            return False, "Invalid currency code format"
        
        return True, ""
    
    @classmethod
    def validate_search_query(cls, query: str) -> tuple[bool, str]:
        """Validate search query to prevent injection"""
        is_valid, error = cls.validate_string(query, max_length=1000)
        if not is_valid:
            return False, error
        
        # Additional search-specific validation
        dangerous_search_patterns = [
            r'file:\/\/\/',
            r'ftp:\/\/',
            r'ssh:\/\/',
            r'telnet:\/\/',
            r'ldap:\/\/',
            r'smb:\/\/',
            r'nfs:\/\/',
            r'git:\/\/',
            r'svn:\/\/',
            r'magnet:\/\/',
        ]
        
        for pattern in dangerous_search_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return False, f"Search query contains dangerous protocol: {pattern}"
        
        return True, ""
    
    @classmethod
    def validate_url(cls, url: str) -> tuple[bool, str]:
        """Validate URL to prevent malicious URLs"""
        is_valid, error = cls.validate_string(url, max_length=2048)
        if not is_valid:
            return False, error
        
        # Check for allowed protocols
        allowed_protocols = ['http://', 'https://']
        if not any(url.lower().startswith(protocol) for protocol in allowed_protocols):
            return False, "Only HTTP and HTTPS URLs are allowed"
        
        # Parse URL to check for dangerous components
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Check for localhost/private IP access
            hostname = parsed.hostname
            if hostname:
                # Block localhost variations
                localhost_patterns = [
                    'localhost', '127.0.0.1', '::1', '0.0.0.0',
                    '0:0:0:0:0:0:0:1', '0:0:0:0:0:0:0:0'
                ]
                if hostname.lower() in localhost_patterns:
                    return False, "Access to localhost is not allowed"
                
                # Block private IP ranges
                if cls._is_private_ip(hostname):
                    return False, "Access to private IP addresses is not allowed"
            
            # Check for dangerous ports
            if parsed.port and parsed.port in [22, 23, 25, 53, 135, 139, 445, 993, 995]:
                return False, f"Access to port {parsed.port} is not allowed"
            
        except Exception as e:
            logger.warning(f"URL parsing error: {e}")
            return False, "Invalid URL format"
        
        return True, ""
    
    @classmethod
    def validate_amount(cls, amount: str) -> tuple[bool, str]:
        """Validate monetary amount"""
        if not isinstance(amount, str):
            return False, "Amount must be a string"
        
        # Allow "all" as special case
        if amount.lower() == 'all':
            return True, ""
        
        # Validate numeric format
        if not re.match(r'^\d+(\.\d{1,8})?$', amount):
            return False, "Invalid amount format"
        
        # Check for reasonable limits
        try:
            amount_float = float(amount)
            if amount_float < 0:
                return False, "Amount cannot be negative"
            if amount_float > 1000000000:  # 1 billion
                return False, "Amount exceeds maximum limit"
        except ValueError:
            return False, "Invalid numeric amount"
        
        return True, ""
    
    @classmethod
    def validate_discord_message(cls, message: str) -> tuple[bool, str]:
        """Validate Discord message content with Discord-specific logic"""
        is_valid, error = cls.validate_string(message, max_length=2000, allow_empty=False)
        if not is_valid:
            return False, error

        # First check if the message contains only safe Discord patterns when using < >
        # This allows Discord mentions but blocks shell redirection
        message_lower = message.lower()

        # Check for shell redirection patterns that use < but aren't Discord mentions
        for pattern in cls.SHELL_REDIRECTION_PATTERNS:
            if re.search(pattern, message):
                return False, f"Message contains shell redirection pattern: {pattern}"

        # Check for Discord-specific dangerous patterns (role mentions, @everyone, @here)
        for pattern in cls.DISCORD_DANGEROUS_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return False, f"Message contains restricted Discord content: {pattern}"

        # Allow the message if it contains safe Discord patterns
        has_safe_discord_patterns = any(re.search(pattern, message) for pattern in cls.DISCORD_SAFE_PATTERNS)

        # If message contains < characters but no safe Discord patterns, be more strict
        if '<' in message and not has_safe_discord_patterns:
            # Check for other potentially dangerous HTML/SSRF patterns
            dangerous_html_patterns = [
                r'<\s*script[^>]*>',
                r'<\s*iframe[^>]*>',
                r'<\s*object[^>]*>',
                r'<\s*embed[^>]*>',
                r'<\s*link[^>]*>',
                r'<\s*meta[^>]*>',
                r'<\s*form[^>]*>',
                r'http[s]?:\/\/[^<\s]*',  # URLs with < around them
            ]

            for pattern in dangerous_html_patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    return False, f"Message contains potentially dangerous HTML pattern: {pattern}"

        return True, ""
    
    @classmethod
    def validate_sql_input(cls, input_string: str) -> tuple[bool, str]:
        """Validate input that will be used in SQL queries"""
        is_valid, error = cls.validate_string(input_string)
        if not is_valid:
            return False, error
        
        # Check for SQL injection patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_string, re.IGNORECASE | re.MULTILINE):
                return False, f"Input contains SQL injection pattern: {pattern}"
        
        return True, ""
    
    @classmethod
    def sanitize_html(cls, input_string: str) -> str:
        """Sanitize HTML input to prevent XSS"""
        if not isinstance(input_string, str):
            return ""
        
        # HTML escape
        sanitized = html.escape(input_string)
        
        # Remove any remaining dangerous patterns
        for pattern in cls.XSS_PATTERNS:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename to prevent directory traversal"""
        if not isinstance(filename, str):
            return ""
        
        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[\/\\:*?"<>|]', '', filename)
        
        # Remove leading dots and spaces
        sanitized = sanitized.lstrip('. ')
        
        # Limit length
        sanitized = sanitized[:255]
        
        # Ensure it's not empty after sanitization
        if not sanitized:
            sanitized = "unnamed"
        
        return sanitized
    
    @classmethod
    def _is_private_ip(cls, hostname: str) -> bool:
        """Check if hostname is a private IP address"""
        try:
            import ipaddress
            ip = ipaddress.ip_address(hostname)
            return ip.is_private
        except ValueError:
            # Not an IP address, check for private hostnames
            private_hostnames = [
                'local', 'localhost', 'internal', 'intranet',
                'dev', 'test', 'staging', 'admin'
            ]
            return any(pattern in hostname.lower() for pattern in private_hostnames)
    
    @classmethod
    def validate_tip_command(cls, recipient: str, amount: str, currency: str, message: str = "") -> tuple[bool, str]:
        """Validate tip.cc command parameters"""
        # Validate recipient (Discord user mention or ID)
        if recipient.startswith('<@') and recipient.endswith('>'):
            # Valid mention format
            pass
        else:
            # Should be a user ID
            is_valid, error = cls.validate_discord_id(recipient)
            if not is_valid:
                return False, f"Invalid recipient: {error}"
        
        # Validate amount
        is_valid, error = cls.validate_amount(amount)
        if not is_valid:
            return False, f"Invalid amount: {error}"
        
        # Validate currency (allow both traditional currency codes and cryptocurrency symbols)
        if len(currency) <= 3:
            # Traditional currency code (USD, EUR, etc.)
            is_valid, error = cls.validate_currency_code(currency)
        else:
            # Cryptocurrency symbol (solUSDC, etc.)
            is_valid, error = cls.validate_cryptocurrency_symbol(currency)
        
        if not is_valid:
            return False, f"Invalid currency: {error}"
        
        # Validate message (optional)
        if message:
            is_valid, error = cls.validate_discord_message(message)
            if not is_valid:
                return False, f"Invalid message: {error}"
        
        return True, ""
    
    @classmethod
    def validate_reminder_data(cls, title: str, description: str, trigger_time: str) -> tuple[bool, str]:
        """Validate reminder data"""
        # Validate title
        is_valid, error = cls.validate_string(title, max_length=200, allow_empty=False)
        if not is_valid:
            return False, f"Invalid title: {error}"
        
        # Validate description
        is_valid, error = cls.validate_string(description, max_length=1000, allow_empty=False)
        if not is_valid:
            return False, f"Invalid description: {error}"
        
        # Validate trigger time (ISO 8601 format)
        try:
            import datetime
            datetime.datetime.fromisoformat(trigger_time.replace('Z', '+00:00'))
        except ValueError:
            return False, "Invalid trigger_time format. Use ISO 8601 format (e.g., '2025-10-03T15:00:00Z')"
        
        return True, ""
    
    @classmethod
    def validate_company_name(cls, company_name: str) -> tuple[bool, str]:
        """Validate company name for research"""
        is_valid, error = cls.validate_string(company_name, max_length=100, allow_empty=False)
        if not is_valid:
            return False, error
        
        # Additional validation for company names
        if not re.match(r'^[a-zA-Z0-9\s\.\-&\']+$', company_name):
            return False, "Company name contains invalid characters"
        
        return True, ""
    
    def is_safe_input(self, input_string: str) -> bool:
        """
        Quick safety check for input strings
        Returns True if input is safe, False if dangerous
        """
        # Check general dangerous patterns
        is_valid, error = self.validate_string(input_string)
        if not is_valid:
            return False
        
        # Check SQL injection patterns
        is_valid, error = self.validate_sql_input(input_string)
        if not is_valid:
            return False
        
        # Check XSS patterns
        if any(re.search(pattern, input_string, re.IGNORECASE) for pattern in self.XSS_PATTERNS):
            return False
        
        return True
    
    @property
    def dangerous_patterns(self) -> list:
        """Get list of dangerous patterns for testing"""
        return self.DANGEROUS_PATTERNS

# Global validator instance
validator = SecurityValidator()
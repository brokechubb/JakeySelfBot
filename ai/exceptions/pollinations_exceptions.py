"""Custom exceptions for Pollinations API"""
from typing import Optional


class PollinationsError(Exception):
    """Base exception for Pollinations API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class APIError(PollinationsError):
    """Exception for API-related errors"""
    pass


class RateLimitError(PollinationsError):
    """Exception for rate limit errors"""
    pass


class ValidationError(PollinationsError):
    """Exception for validation errors"""
    pass
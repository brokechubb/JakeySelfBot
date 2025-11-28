"""Pydantic models for text generation requests and responses"""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represents a message in the conversation"""
    role: str
    content: str


class TextGenerationRequest(BaseModel):
    """Request model for text generation"""
    messages: List[Message] = Field(default_factory=list)
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 500
    tools: Optional[List[Dict]] = None
    tool_choice: str = "auto"


class TextGenerationResponse(BaseModel):
    """Response model for text generation"""
    content: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

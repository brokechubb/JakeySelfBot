"""Pydantic models for image generation requests and responses"""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class ImageGenerationRequest(BaseModel):
    """Request model for image generation"""
    prompt: str
    model: str = "flux"
    width: int = 1024
    height: int = 1024
    seed: Optional[int] = None
    nologo: bool = True
    private: bool = True


class ImageGenerationResponse(BaseModel):
    """Response model for image generation"""
    url: str
    seed: Optional[int] = None
    error: Optional[str] = None

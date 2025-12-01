# Provider Abstraction Enhancement Plan

## Current Issues
- **Direct provider coupling**: AI provider manager directly calls provider methods
- **Inconsistent interfaces**: Each provider has different method signatures
- **No common abstraction**: Hard to add new providers or test provider logic
- **Mixed responsibilities**: Providers handle both API calls and business logic
- **Error handling duplication**: Each provider implements similar error patterns

## Proposed Provider Abstraction Architecture

```python
# ai/providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

class ProviderType(Enum):
    TEXT_GENERATION = "text"
    IMAGE_GENERATION = "image"
    MULTI_MODAL = "multi_modal"

class ProviderCapability(Enum):
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    VISION = "vision"

@dataclass
class ProviderStatus:
    """Standardized provider status information"""
    name: str
    healthy: bool
    response_time: float
    error_message: Optional[str] = None
    last_check: float = 0.0
    capabilities: List[ProviderCapability] = None

@dataclass
class GenerationRequest:
    """Standardized request format"""
    messages: List[Dict[str, Any]]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    tools: Optional[List[Dict]] = None
    tool_choice: str = "auto"
    **kwargs

@dataclass
class GenerationResponse:
    """Standardized response format"""
    content: str
    model_used: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = None

class AIProvider(ABC):
    """Abstract base class for all AI providers"""

    def __init__(self, name: str, provider_type: ProviderType):
        self.name = name
        self.provider_type = provider_type
        self._capabilities: List[ProviderCapability] = []

    @property
    def capabilities(self) -> List[ProviderCapability]:
        """Get provider capabilities"""
        return self._capabilities.copy()

    def supports_capability(self, capability: ProviderCapability) -> bool:
        """Check if provider supports a specific capability"""
        return capability in self._capabilities

    @abstractmethod
    async def check_health(self) -> ProviderStatus:
        """Check provider health and return status"""
        pass

    @abstractmethod
    async def generate_text(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using the provider"""
        pass

    @abstractmethod
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image using the provider (if supported)"""
        pass

    @abstractmethod
    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models from the provider"""
        pass

    @abstractmethod
    def is_rate_limited(self) -> bool:
        """Check if provider is currently rate limited"""
        pass

    @abstractmethod
    async def get_model_capabilities(self, model: str) -> Dict[str, Any]:
        """Get capabilities for a specific model"""
        pass
```

## Concrete Provider Implementations

### Enhanced Pollinations Provider
```python
# ai/providers/pollinations.py
class PollinationsProvider(AIProvider):
    """Pollinations API provider implementation"""

    def __init__(self):
        super().__init__("pollinations", ProviderType.MULTI_MODAL)
        self._capabilities = [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.IMAGE_GENERATION,
            ProviderCapability.FUNCTION_CALLING,
        ]

        # Provider-specific configuration
        self.text_api_url = POLLINATIONS_TEXT_API
        self.image_api_url = POLLINATIONS_IMAGE_API
        self.api_token = POLLINATIONS_API_TOKEN

        # Rate limiting
        self._rate_limiter = RateLimiter(TEXT_API_RATE_LIMIT, IMAGE_API_RATE_LIMIT)

    async def generate_text(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text with standardized interface"""
        if not self.supports_capability(ProviderCapability.TEXT_GENERATION):
            raise ProviderError("Text generation not supported")

        # Check rate limits
        if self.is_rate_limited():
            raise RateLimitError("Rate limit exceeded")

        try:
            # Convert standardized request to provider-specific format
            provider_request = self._convert_request(request)

            # Make API call
            response_data = await self._make_text_request(provider_request)

            # Convert to standardized response
            return self._convert_response(response_data, request.model)

        except Exception as e:
            logger.error(f"Pollinations text generation failed: {e}")
            raise ProviderError(f"Text generation failed: {e}") from e

    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image with standardized interface"""
        if not self.supports_capability(ProviderCapability.IMAGE_GENERATION):
            raise ProviderError("Image generation not supported")

        # Implementation...
        pass

    async def check_health(self) -> ProviderStatus:
        """Standardized health check"""
        start_time = time.time()
        try:
            # Health check implementation
            healthy = await self._perform_health_check()
            response_time = time.time() - start_time

            return ProviderStatus(
                name=self.name,
                healthy=healthy,
                response_time=response_time,
                capabilities=self.capabilities
            )
        except Exception as e:
            return ProviderStatus(
                name=self.name,
                healthy=False,
                response_time=time.time() - start_time,
                error_message=str(e)
            )
```

### Enhanced OpenRouter Provider
```python
# ai/providers/openrouter.py
class OpenRouterProvider(AIProvider):
    """OpenRouter API provider implementation"""

    def __init__(self):
        super().__init__("openrouter", ProviderType.TEXT_GENERATION)
        self._capabilities = [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.FUNCTION_CALLING,
        ]

        # Provider-specific configuration
        self.api_key = OPENROUTER_API_KEY
        self.api_url = OPENROUTER_API_URL
        self._rate_limiter = RateLimiter(60)  # OpenRouter rate limits

    async def generate_text(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text with standardized interface"""
        # Implementation following same pattern as Pollinations
        pass
```

## Enhanced Provider Manager

```python
# ai/provider_manager.py
class ProviderManager:
    """Enhanced provider manager with abstracted providers"""

    def __init__(self):
        self.providers: Dict[str, AIProvider] = {}
        self._register_providers()

    def _register_providers(self):
        """Register all available providers"""
        self.providers["pollinations"] = PollinationsProvider()
        self.providers["openrouter"] = OpenRouterProvider()
        # Future: self.providers["anthropic"] = AnthropicProvider()

    async def get_provider_for_capability(
        self,
        capability: ProviderCapability,
        preferred_provider: Optional[str] = None
    ) -> Optional[AIProvider]:
        """Get best available provider for a capability"""
        if preferred_provider and preferred_provider in self.providers:
            provider = self.providers[preferred_provider]
            if provider.supports_capability(capability):
                health = await provider.check_health()
                if health.healthy:
                    return provider

        # Find any healthy provider that supports the capability
        for provider in self.providers.values():
            if provider.supports_capability(capability):
                health = await provider.check_health()
                if health.healthy:
                    return provider

        return None

    async def generate_text(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs
    ) -> GenerationResponse:
        """Generate text with automatic provider selection"""
        request = GenerationRequest(messages=messages, model=model, **kwargs)

        # Try to find appropriate provider
        provider = await self.get_provider_for_capability(
            ProviderCapability.TEXT_GENERATION
        )

        if not provider:
            raise NoProviderAvailableError("No healthy text generation provider available")

        return await provider.generate_text(request)

    async def get_all_provider_statuses(self) -> Dict[str, ProviderStatus]:
        """Get status of all providers"""
        statuses = {}
        for name, provider in self.providers.items():
            statuses[name] = await provider.check_health()
        return statuses
```

## Migration Strategy

### Phase 1: Create Abstract Base Classes
- Implement `AIProvider` abstract base class
- Define standardized request/response formats
- Create provider capability system

### Phase 2: Refactor Existing Providers
- Update `PollinationsAPI` to inherit from `AIProvider`
- Update `OpenRouterAPI` to inherit from `AIProvider`
- Implement standardized interfaces

### Phase 3: Update Provider Manager
- Refactor `SimpleAIProviderManager` to use new abstractions
- Implement capability-based provider selection
- Add provider health monitoring

### Phase 4: Add Provider Discovery
- Implement automatic provider registration
- Add provider configuration validation
- Create provider testing framework

## Benefits
- **Extensibility**: Easy to add new AI providers
- **Consistency**: All providers follow same interface
- **Testability**: Mock providers for testing
- **Maintainability**: Changes isolated to individual providers
- **Type Safety**: Strong typing for all provider interactions
- **Capability Detection**: Automatic feature detection and routing

## Future Enhancements
- **Provider Marketplace**: Dynamic provider loading
- **Cost Optimization**: Automatic provider selection based on cost
- **A/B Testing**: Compare provider performance
- **Fallback Chains**: Complex provider fallback strategies
- **Provider Analytics**: Detailed usage and performance metrics
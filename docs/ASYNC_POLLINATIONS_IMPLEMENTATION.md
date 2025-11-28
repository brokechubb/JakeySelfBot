# Async Pollinations Implementation

This document describes the new async implementation of the Pollinations API client that incorporates features from the pypollinations package while maintaining backward compatibility with the existing codebase.

## Features Implemented

1. **Async Support**: Full async implementation using `httpx` library
2. **Pydantic Models**: Type-safe request/response models for validation
3. **Backward Compatibility**: Wrapper maintains the same interface as the original sync implementation
4. **Rate Limiting**: Preserved the sophisticated rate limiting from the original implementation
5. **Error Handling**: Enhanced error handling with specific exception types
6. **Retry Logic**: Maintained exponential backoff retry logic for network issues

## File Structure

```
ai/
├── async_pollinations.py          # Backward compatibility wrapper
├── clients/
│   ├── __init__.py
│   └── async_client.py           # Main async client implementation
└── models/
    ├── __init__.py
    ├── text_models.py            # Pydantic models for text generation
    └── image_models.py           # Pydantic models for image generation
```

## Usage

### Async Usage (New)

```python
from ai.async_pollinations import pollinations_async_api

# Text generation
response = await pollinations_async_api.generate_text(
    messages=[{"role": "user", "content": "What is AI?"}],
    model="openai"
)

# Image generation
url = await pollinations_async_api.generate_image(
    "A beautiful sunset",
    model="flux"
)
```

### Sync Usage (Backward Compatible)

The existing code continues to work without changes:

```python
from ai.pollinations import pollinations_api

# Text generation
response = pollinations_api.generate_text(
    messages=[{"role": "user", "content": "What is AI?"}],
    model="openai"
)

# Image generation
url = pollinations_api.generate_image(
    "A beautiful sunset",
    model="flux"
)
```

## Benefits

1. **Performance**: Async implementation provides better performance for handling multiple concurrent requests
2. **Type Safety**: Pydantic models provide automatic validation and type checking
3. **Maintainability**: Modular structure makes the code easier to maintain and extend
4. **Compatibility**: Existing code doesn't need to be changed
5. **Enhanced Features**: Preserves all the sophisticated features of the original implementation

## Dependencies

- `httpx>=0.27.0` - For async HTTP requests
- `pydantic>=2.0.0` - For data validation and serialization

## Testing

Run the async tests with:

```bash
python tests/test_async_pollinations.py
```
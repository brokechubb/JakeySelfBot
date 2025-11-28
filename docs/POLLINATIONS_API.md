# Pollinations.AI API Documentation

## Overview

The Pollinations.AI API provides free, accessible generative AI services including text generation and audio synthesis. Image generation has been replaced with the Arta API for better quality and more features. This documentation covers the API endpoints and demonstrates how to use them in the JakeySelfBot project.

## Available Endpoints

### 1. Text Generation API

**Base URL:** `https://text.pollinations.ai/`

#### Text-to-Text Generation (GET)
```python
# Simple text generation
GET https://text.pollinations.ai/{prompt}

# Example: What are the last Pollinations.AI news?
response = requests.get("https://text.pollinations.ai/What%20are%20the%20last%20Pollinations.AI%20news")
```

#### Advanced Text Generation (POST)
```python
# OpenAI-compatible endpoint
POST https://text.pollinations.ai/openai

payload = {
    "model": "openai",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"}
    ],
    "temperature": 0.7,
    "max_tokens": 500
}
```

#### Text-to-Speech Generation
```python
GET https://text.pollinations.ai/{prompt}?model=openai-audio&voice=nova

# Voices available: alloy, echo, fable, onyx, nova, shimmer
```

#### Speech-to-Text Processing
```python
# POST to https://text.pollinations.ai/openai with base64 audio data
payload = {
    "model": "openai-audio",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Transcribe this:"},
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": "base64_audio_string",
                        "format": "wav"
                    }
                }
            ]
        }
    ]
}
```

#### Vision/Image Analysis
```python
# Include images in message content
payload = {
    "model": "openai",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image:"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpeg;base64,{base64_string}"
                    }
                }
            ]
        }
    ]
}
```

### 2. Image Generation API

**Base URL:** `https://image.pollinations.ai/`

#### Text-to-Image Generation
```python
GET https://image.pollinations.ai/prompt/{prompt}

# Example parameters
params = {
    "model": "flux",           # Available: flux, kontext, etc.
    "width": 1024,
    "height": 1024,
    "seed": 42,
    "nologo": "true",          # Disable logo for registered users
    "enhance": "true"          # Enhance prompt with LLM
}
```

### 3. Real-time Feeds

#### Image Feed (SSE)
```python
# Get real-time image generation feed
GET https://image.pollinations.ai/feed

# Returns Server-Sent Events with new public images
```

#### Text Feed (SSE)
```python
# Get real-time text generation feed
GET https://text.pollinations.ai/feed

# Returns Server-Sent Events with new public text responses
```

## Authentication

### Referrer-Based (Frontend)
- Browsers automatically send `Referer` header
- Register domain at auth.pollinations.ai for higher limits
- Add `?referrer=myapp.com` parameter for explicit identification

### Token-Based (Backend) - RECOMMENDED
```python
# Use Bearer token in headers
headers = {
    "Authorization": "Bearer YOUR_TOKEN",
    "Content-Type": "application/json"
}

# Or as URL parameter
url = f"https://text.pollinations.ai/openai?token=YOUR_TOKEN"
```

## Rate Limits

| Tier       | Rate Limit | Authentication Required |
|------------|------------|------------------------|
| Anonymous | 1 req/5s   | No                    |
| Seed      | 1 req/3s   | Referrer registration  |
| Flower    | 1 req/3s   | Full authentication    |
| Nectar    | Unlimited | Enterprise            |

## Available Models

### Text Models
- `openai` - Primary text generation
- `openai-large` - Enhanced reasoning
- `mistral` - Alternative model
- `claude-hybridspace` - CLIP-based vision
- `openai-audio` - Audio processing

### Image Models
Image generation now uses the Arta API with 49 artistic styles including:
- `SDXL 1.0` - Default high-quality style
- `Fantasy Art` - Fantasy-themed artistic rendering
- `Vincent Van Gogh` - Van Gogh painting style
- `Photographic` - Realistic photographic style
- And 45 more styles

See ARTA_IMAGE_GENERATION.md for a complete list of available styles.

## Current JakeySelfBot Implementation Status

### ✅ Working Features
- **Text Generation**: Full OpenAI-compatible POST endpoint integration
- **Audio Generation**: TTS with multiple voice options
- **Rate Limiting**: Automatic request throttling (1 req/3s for Seed tier = 20 req/min)
- **Authentication**: Bearer token support with "jakeydegenbot" referrer
- **Error Handling**: Optimized retry logic with fast recovery for 502 errors (1, 2, 4, 8s backoff) and standard backoff for other errors
- **Logging**: Detailed request/response logging for debugging

### ⚠️ Image Generation
Image generation has been replaced with the Arta API which provides:
- 49 artistic styles for enhanced creativity
- 9 aspect ratios for flexible image dimensions
- Better quality outputs with professional artistic rendering
- Asynchronous generation with status polling
- See ARTA_IMAGE_GENERATION.md for detailed documentation

### ✅ Enhanced Features
- **TTS/STT Support**: Audio generation with multiple voice options
- **Advanced Parameters**: Fine-grained control over text and image generation
- **Vision/Image Analysis**: Not implemented in current commands
- **Real-time Feeds**: No feed monitoring implemented
- **Function Calling**: Framework exists but unused in current commands
- **Streaming**: Not enabled (could be added for long responses)

### 📋 Configuration
The bot is configured for **Seed tier access** with the following rate limits:
- **Text API**: 20 requests per minute (1 request per 3 seconds)
- **Image API**: 20 requests per minute (1 request per 3 seconds)

**Current Configuration:**
- Uses referrer: "jakeydegenbot" (falls back to anonymous if not registered)
- Optional token authentication via `POLLINATIONS_API_TOKEN` environment variable
- Configurable through `TEXT_API_RATE_LIMIT` and `IMAGE_API_RATE_LIMIT` env vars

**For Production/Higher Limits:**
1. Register application at [auth.pollinations.ai](https://auth.pollinations.ai)
2. Set `POLLINATIONS_API_TOKEN` in environment
3. Consider Flower tier for 1 req/3s + advanced features

### Audio Voices
- `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

## Integration in JakeySelfBot

### Current Implementation

The project currently uses the Pollinations API through `ai/pollinations.py`:

```python
# Text generation
response = pollinations_api.generate_text(messages, model="openai")

# Image generation
image_url = pollinations_api.generate_image(prompt, model="flux")
```

### Configuration

Key configuration parameters in `config.py`:
- `POLLINATIONS_TEXT_API`: Base URL for text API
- `POLLINATIONS_IMAGE_API`: Base URL for image API
- `POLLINATIONS_API_TOKEN`: Authentication token
- `DEFAULT_MODEL`: Default text generation model
- Rate limit configurations

### Usage Examples

#### Generate Text Response
```python
from ai.pollinations import pollinations_api

messages = [
    {"role": "user", "content": "Tell me about artificial intelligence"}
]

# Basic usage
result = pollinations_api.generate_text(messages)

if "error" not in result:
    response_text = result["choices"][0]["message"]["content"]
else:
    print(f"Error: {result['error']}")

# Advanced usage with additional parameters
result = pollinations_api.generate_text(
    messages,
    model="openai",
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.1,
    stop=["END", "THE END"]
)
```

#### Generate Image
```python
from ai.pollinations import pollinations_api

prompt = "A futuristic cityscape at sunset"

# Basic usage
image_url = pollinations_api.generate_image(prompt, model="flux")

# Use the URL to display or download the image

# Advanced usage with additional parameters
image_url = pollinations_api.generate_image(
    prompt, 
    model="flux",
    quality="hd",
    guidance_scale=7.5,
    num_inference_steps=50
)
```

#### Generate Audio
```python
from ai.pollinations import pollinations_api

text = "Welcome to the degenerate courtyard!"
audio_url = pollinations_api.generate_audio(text, model="openai-audio", voice="nova")

# Use the URL to play or download the audio
```

#### Check Rate Limiting
```python
# The API class handles rate limiting automatically
# Current implementation tracks requests per minute
# and blocks requests if rate limit exceeded
```

## Function Calling

The API supports tool/function calling for more advanced interactions:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather information",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    }
]

response = pollinations_api.generate_text(
    messages,
    tools=tools,
    tool_choice="auto"
)
```

## Error Handling

Common error responses:
- **502**: API gateway error (service temporarily down)
- **429**: Rate limit exceeded
- **Timeout**: Connection or processing timeout
- **ConnectionError**: Network connectivity issues

The current implementation includes optimized retry logic:
- **Faster timeouts**: 15-second timeout (down from 30s) for quicker failure detection
- **Differential backoff**: 502 errors use fast retry (1, 2, 4, 8s) while other errors use standard exponential backoff (2, 4, 8, 16s)
- **Maximum 5 retries** for resilience against temporary service issues

## Best Practices

1. **Use Authentication**: Register your application for higher rate limits
2. **Handle Rate Limits**: Implement proper cooldown periods
3. **Error Recovery**: Use the built-in retry mechanisms
4. **Content Safety**: API includes NSFW filtering (set `safe=true` for image generation)
5. **Caching**: Cache frequent requests to reduce API calls
6. **Async Processing**: Use streaming for long responses

## React Hooks Library

For React applications, Pollinations provides `@pollinations/react` with hooks:
- `usePollinationsImage(prompt, options)`
- `usePollinationsText(prompt, options)`
- `usePollinationsChat(initialMessages, options)`

Playground: https://react-hooks.pollinations.ai/

## MCP Server

For AI assistants, Pollinations offers an MCP server with tools for:
- Image generation and serving
- Audio response generation
- Model listing and management

## License

MIT License - Free for commercial and personal use.

## Resources

- **Official Docs**: https://github.com/pollinations/pollinations/blob/master/APIDOCS.md
- **Authentication**: https://auth.pollinations.ai
- **React Hooks**: https://github.com/pollinations/pollinations/blob/master/pollinations-react/README.md
- **Hooks Playground**: https://react-hooks.pollinations.ai/

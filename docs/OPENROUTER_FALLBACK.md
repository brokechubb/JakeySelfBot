# OpenRouter Fallback Integration

## Overview

JakeySelfBot now supports OpenRouter as a fallback AI provider when Pollinations AI is unavailable. This ensures the bot remains functional even during service outages.

## Features

- **Automatic Fallback**: Seamlessly switches to OpenRouter when Pollinations fails
- **Free Model Support**: Prioritizes free OpenRouter models to minimize costs
- **Transparent Operation**: Users are notified when fallback is active
- **Health Monitoring**: Tracks status of both AI providers
- **Rate Limiting**: Respects OpenRouter's rate limits (60 requests/minute for free tier)

## Configuration

Add the following to your `.env` file:

```bash
# OpenRouter API Configuration (Fallback Provider)
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_ENABLED=true
OPENROUTER_DEFAULT_MODEL=microsoft/phi-3-medium-128k-instruct:free
OPENROUTER_SITE_URL=https://github.com/chubbb/JakeySelfBot
OPENROUTER_APP_NAME=JakeySelfBot
```

### Getting an OpenRouter API Key

1. Visit [OpenRouter.ai](https://openrouter.ai/)
2. Sign up for a free account
3. Navigate to [API Keys](https://openrouter.ai/keys)
4. Create a new API key
5. Add the key to your `.env` file

## How It Works

### Fallback Logic

1. **Primary Attempt**: Bot tries Pollinations AI first
2. **Failure Detection**: If Pollinations returns an error, the bot detects the failure
3. **Fallback Activation**: Bot automatically switches to OpenRouter
4. **User Notification**: Users see a message indicating fallback is active
5. **Model Selection**: Bot selects the best available free model

### Error Handling

The bot provides detailed error messages based on failure scenarios:

- **Both providers down**: "Both Pollinations and OpenRouter failed"
- **Pollinations down, OpenRouter unavailable**: "Pollinations failed and OpenRouter is not available"
- **Specific errors**: Timeout, connection issues, rate limits, etc.

### Model Selection

OpenRouter models are selected based on:

1. **Free models first**: Prioritizes models with $0 pricing
2. **Availability**: Checks if models are currently accessible
3. **Capabilities**: Considers tool support for function calling

## Commands

### AI Status Check

Use `%aistatus` to see the status of both AI providers:

```
🤖 AI SERVICE STATUS

✅ Pollinations AI: Online and healthy
⚡ Response time: 0.45s

✅ OpenRouter AI: Online and healthy (Fallback)
⚡ Response time: 0.32s

📊 Available models: 156 models total
  • Pollinations: 12 models
  • OpenRouter: 144 models (23 free)
🔧 Current model: openai
```

## Supported Models

### Recommended Free Models

- `microsoft/phi-3-medium-128k-instruct:free` - Default, good balance
- `microsoft/phi-3-mini-128k-instruct:free` - Faster, smaller context
- `meta-llama/llama-3.2-3b-instruct:free` - Lightweight option
- `google/gemma-2-9b-it:free` - Google's free model

### Premium Models

If you add credits to your OpenRouter account, you can access premium models:
- `anthropic/claude-3.5-sonnet`
- `openai/gpt-4o`
- `meta-llama/llama-3.1-405b-instruct`

## Rate Limits

### Free Tier
- **60 requests per minute**
- **Automatic rate limiting** built into the client
- **Graceful handling** when limits are exceeded

### Paid Tier
- Higher limits based on your plan
- Same fallback logic applies

## Troubleshooting

### OpenRouter Not Working

1. **Check API Key**: Ensure `OPENROUTER_API_KEY` is set correctly
2. **Verify Enabled**: Make sure `OPENROUTER_ENABLED=true`
3. **Check Credits**: Free tier has limits, consider adding credits
4. **Test Manually**: Use the OpenRouter playground to test your key

### Fallback Not Triggering

1. **Pollinations Status**: Check if Pollinations is actually failing
2. **Error Patterns**: Fallback triggers on specific error patterns
3. **Network Issues**: Check internet connectivity
4. **Rate Limits**: Pollinations might be rate-limited

### Performance Issues

1. **Model Selection**: Try different free models for better performance
2. **Response Time**: Monitor response times in `%aistatus`
3. **Tool Support**: Some models don't support function calling

## Monitoring

### Health Checks

The bot continuously monitors both providers:

- **Response Times**: Tracks API latency
- **Error Rates**: Monitors failure patterns
- **Model Availability**: Updates model lists periodically

### Logging

Detailed logging helps with troubleshooting:

```
INFO Pollinations API failed for user 123: 502 Server Error
INFO Attempting OpenRouter fallback for user 123
INFO OpenRouter fallback successful for user 123 using model microsoft/phi-3-medium-128k-instruct:free
```

## Cost Management

### Free Tier Usage

- **No cost** for free models
- **Rate limited** to prevent overuse
- **Automatic fallback** ensures service continuity

### Paid Usage

- **Pay-per-use** for premium models
- **Usage tracking** in OpenRouter dashboard
- **Budget alerts** available in OpenRouter settings

## Security

### API Key Protection

- **Environment variables**: Keys stored in `.env` file
- **No hardcoding**: Keys never committed to repository
- **Access control**: Limit key permissions in OpenRouter

### Data Privacy

- **No training data**: OpenRouter doesn't use conversations for training
- **Privacy policy**: Review OpenRouter's privacy policy
- **Data retention**: Check OpenRouter's data retention policies

## Future Enhancements

### Planned Features

- **Model rotation**: Load balance across multiple models
- **Cost optimization**: Automatic model selection based on cost/quality
- **Custom routing**: Provider selection based on query type
- **Performance metrics**: Detailed analytics and reporting

### Contributing

To contribute to the OpenRouter integration:

1. Test fallback scenarios thoroughly
2. Add support for new models as they become available
3. Improve error handling and user feedback
4. Optimize performance and reduce latency

## Support

### Issues

- **GitHub Issues**: Report bugs and feature requests
- **Discord Community**: Get help from other users
- **OpenRouter Support**: Contact OpenRouter for API issues

### Documentation

- **OpenRouter Docs**: [https://openrouter.ai/docs](https://openrouter.ai/docs)
- **API Reference**: [https://openrouter.ai/docs/quickstart](https://openrouter.ai/docs/quickstart)
- **Model List**: [https://openrouter.ai/models](https://openrouter.ai/models)
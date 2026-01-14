# OpenRouter Model Configuration Guide

## Overview

This bot uses OpenRouter as its AI provider. Not all free models support **function calling** (tool use), which is essential for the bot's advanced features like web search, crypto prices, Discord tools, etc.

## Critical Bug Fix (Jan 2026)

### Issue
The bot was returning empty responses ("My mind went blank") due to:
1. **Duplicate API call bug** in tool call follow-up logic (`bot/client.py:1108-1195`)
2. **Incompatible model** - `meta-llama/llama-3.3-70b-instruct:free` doesn't support function calling

### Resolution
1. **Fixed duplicate API call** - Added proper `break` statement in retry loop
2. **Auto-fallback logic** - Automatically switches to function-calling capable model when tools are needed
3. **Updated default model** - Changed to `openai/gpt-oss-120b:free` which supports function calling

## Free Models with Function Calling Support (Jan 2026)

These models work with the bot's tool system:

### Recommended Models

| Model | Context | Function Calling | Best For |
|-------|---------|------------------|----------|
| `openai/gpt-oss-120b:free` | 131K | ✅ Full support | **DEFAULT - General use, tool calling** |
| `google/gemini-2.0-flash-exp:free` | 1.05M | ✅ Enhanced | Fast responses, large context |
| `google/gemma-3-27b-it:free` | 131K | ✅ Native | Structured outputs |
| `qwen/qwen3-coder:free` | 262K | ✅ Optimized | Coding tasks, agentic workflows |
| `xiaomi/mimo-v2-flash:free` | 262K | ✅ Supported | Agent scenarios, reasoning |

### Good for Coding (with tool support)
- `mistralai/devstral-2512:free` - 262K context, specialized for agentic coding
- `kwaipilot/kat-coder-pro:free` - 256K context, 73.4% SWE-bench solve rate

### Models WITHOUT Function Calling

These models will auto-fallback to `gpt-oss-120b:free` when tools are needed:

- `meta-llama/llama-3.3-70b-instruct:free` - Good for general chat, NO tools
- `deepseek/deepseek-r1-0528:free` - Reasoning model, NO tools
- `nvidia/nemotron-3-nano-30b-a3b:free` - Small efficient model, NO tools
- `allenai/olmo-3.1-32b-think:free` - Deep reasoning, NO tools

## Configuration

### Default Model (with function calling)
```bash
OPENROUTER_DEFAULT_MODEL=openai/gpt-oss-120b:free
```

### Alternative Options
```bash
# Fast with huge context
OPENROUTER_DEFAULT_MODEL=google/gemini-2.0-flash-exp:free

# Best for coding tasks
OPENROUTER_DEFAULT_MODEL=qwen/qwen3-coder:free

# Good balance
OPENROUTER_DEFAULT_MODEL=google/gemma-3-27b-it:free
```

## Auto-Fallback Behavior

The bot automatically handles model compatibility:

```python
# If you set a model without function calling support
OPENROUTER_DEFAULT_MODEL=meta-llama/llama-3.3-70b-instruct:free

# When tools are needed, the bot automatically switches to:
# openai/gpt-oss-120b:free (with warning logged)
```

You'll see this log message:
```
WARNING: Model meta-llama/llama-3.3-70b-instruct:free doesn't support function calling. 
         Switching to openai/gpt-oss-120b:free for tool use.
```

## Testing Function Calling

Test these commands to verify tool support:

```bash
# Web search tool
%web_search latest AI news

# Crypto price tool
%crypto_price BTC

# Discord info tool
%userinfo @username

# Time tool
%time

# Memory tool
%remember I like pizza
```

If you see "My mind went blank" errors, check:
1. Your model supports function calling (see table above)
2. The auto-fallback logic is working (check logs)
3. OpenRouter API key is valid

## Performance Comparison

| Model | Speed | Context | Function Calls | Reasoning |
|-------|-------|---------|---------------|-----------|
| gpt-oss-120b:free | Fast | 131K | ✅ Excellent | Good |
| gemini-2.0-flash-exp:free | **Fastest** | 1.05M | ✅ Enhanced | Good |
| gemma-3-27b-it:free | Fast | 131K | ✅ Native | Good |
| qwen3-coder:free | Medium | 262K | ✅ Optimized | Excellent (coding) |
| mimo-v2-flash:free | Fast | 262K | ✅ Supported | Excellent |

## Troubleshooting

### "Provider returned error"
- Your model doesn't support function calling
- Auto-fallback should handle this automatically
- If persists, manually set `OPENROUTER_DEFAULT_MODEL=openai/gpt-oss-120b:free`

### "My mind went blank"
- Old bug (fixed Jan 2026) - update your code
- Check that follow-up retry loop has proper `break` statement
- Verify response extraction after tool calls

### "Rate limit exceeded"
- Free models have usage quotas
- Wait 60 seconds and try again
- Consider switching to a different free model

## References

- [OpenRouter Free Models](https://openrouter.ai/collections/free-models)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- Code: `ai/openrouter.py` - Auto-fallback logic
- Code: `bot/client.py:1108-1195` - Tool call handling

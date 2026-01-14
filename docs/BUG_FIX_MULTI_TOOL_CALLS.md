# Bug Fix - Silent Failure on Multi-Round Tool Calls

## Issue Report (Jan 4, 2026)

**User Command:** "use his tools to read the channel history"

**Symptom:** Bot executed first tool call but never responded to user

**Logs:**
```
2026-01-04 16:41:26 INFO  Executing tool: discord_get_user_info
2026-01-04 16:41:26 INFO  Tool result: Discord User Info: ...
2026-01-04 16:41:27 INFO  Successfully received follow-up response on attempt 1
2026-01-04 16:41:27 INFO  Sanitized AI response: removed 22 chars of tool call syntax
[NO MESSAGE SENT TO USER]
```

## Root Cause

The bot's tool calling implementation only supports **single-round tool calling**:

1. Initial request → AI makes tool call
2. Tool executes → Result returned
3. Follow-up request → AI tries to make ANOTHER tool call
4. **Bug:** Code doesn't handle follow-up tool calls
5. After sanitization, response is empty
6. **Bug:** Silent `return` with no user feedback

## Two Bugs Fixed

### Bug #1: Silent Return After Sanitization
**Location:** `bot/client.py:1228-1231`

**Before:**
```python
if not ai_response:
    logger.debug("Empty after sanitization")
    return  # SILENT - user gets nothing!
```

**After:**
```python
if not ai_response:
    logger.warning("Empty after sanitization")
    await message.channel.send("💀 **I got the info but forgot what to say. Try rephrasing?**")
    return
```

**Impact:** User now gets feedback instead of silence

### Bug #2: No Multi-Round Tool Call Detection
**Location:** `bot/client.py:1163-1183`

**Before:**
```python
# Extract content from follow-up response
response_message = final_response["choices"][0]["message"]
content = response_message.get("content", "")
ai_response = content.strip() if content else ""
# BUG: Doesn't check for MORE tool_calls!
```

**After:**
```python
# Extract content from follow-up response
response_message = final_response["choices"][0]["message"]
content = response_message.get("content", "")
ai_response = content.strip() if content else ""

# Check if follow-up response ALSO contains tool calls
follow_up_tool_calls = response_message.get("tool_calls", [])
if follow_up_tool_calls:
    logger.warning(f"⚠️ Follow-up response contains {len(follow_up_tool_calls)} MORE tool calls")
    logger.warning(f"Tools requested: {[...tool names...]}")
    ai_response = "🔧 I need to use multiple tools to answer this, but I can only use one at a time right now. Try asking for just one piece of information at a time."
```

**Impact:** User gets clear feedback instead of silent failure

## Why This Happens

When user asks for complex multi-step tasks:
- "read the channel history" requires:
  1. `discord_get_user_info` (to get user ID)
  2. `discord_list_guilds` (to find guilds)
  3. `discord_list_channels` (to find channels)
  4. `discord_read_channel` (to read messages)

Current implementation:
- ✅ Executes first tool (discord_get_user_info)
- ❌ Gets stuck when AI wants to call second tool
- ❌ Returns nothing to user (before fix)
- ✅ Now tells user to simplify request (after fix)

## Workaround for Users

Instead of: **"use your tools to read the channel history"**

Try specific single-tool requests:
- `%userinfo` - Gets Discord user info
- `list the channels in this server` - Should use discord_list_channels
- `show me recent messages` - Should use discord_read_channel

Or chain them manually:
1. First: "what's my user ID?"
2. Then: "list channels in this server"
3. Then: "read channel history from #general"

## Future Enhancement

To properly support this, we'd need to implement **iterative tool calling**:

```python
max_tool_rounds = 5
for round_num in range(max_tool_rounds):
    response = await ai.generate(messages)
    
    if response has tool_calls:
        execute tools
        append results to messages
        continue  # Go to next round
    else:
        # Final response - send to user
        break
```

This would allow:
- Multiple rounds of tool calls
- Complex multi-step tasks
- Agentic behavior

**Complexity:** Medium
**Benefit:** High (enables complex queries)
**Risk:** Could get stuck in loops

## Testing

```bash
# This should now give clear feedback:
"use your tools to read the channel history"
# Expected: "🔧 I need to use multiple tools... Try asking for just one..."

# This should work (single tool):
%userinfo
# Expected: Shows user info

# This should work:
"what channels are in this server"
# Expected: Lists channels (single discord_list_channels call)
```

## Files Modified

1. **`bot/client.py:1163-1183`** - Detect follow-up tool calls
2. **`bot/client.py:1228-1231`** - Send message instead of silent return

## Related Issues

- Empty response bug (fixed Jan 4, 2026)
- Model compatibility (fixed Jan 4, 2026)
- This fix (multi-round tool detection)

All three fixes ensure users always get feedback, even on errors.

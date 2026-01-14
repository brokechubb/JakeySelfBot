# Testing Guide for Jakey Bot

## Quick Test Commands

### Run New Tool Call Tests
```bash
cd /home/chubb/bots/JakeySelfBot
python -m pytest tests/test_tool_call_detection.py -v
```

### Run Core Tests
```bash
python -m pytest tests/test_database.py tests/test_client.py tests/test_commands.py tests/test_tools.py -v
```

### Run All Tests (expect some failures due to missing modules)
```bash
python -m pytest tests/ -v
```

## Manual Testing in Discord

### Test Tool Calling (Web Search)
```
Message: "jakey what's happening in the world right now?"
Expected: Uses web_search tool silently, responds with news
Should NOT see: "Let me search..." or "I'll check..."
Watch for: 🤔 reaction appears and disappears
```

### Test Tool Calling (Crypto Price)
```
Message: "jakey what's the bitcoin price?"
Expected: Uses get_crypto_price tool silently
Should NOT see: Tool call syntax in response
Watch for: Typing indicator for 1-3 seconds
```

### Test Keyword Triggering
```
Message: "rugpull scam exit liquidity" (use configured keywords)
Expected: Jakey responds within 3 seconds
Watch for: Response matches personality (cynical/sarcastic)
```

### Test Personality
```
Message: "jakey are you helpful?"
Expected: Cynical/sarcastic response, NOT friendly assistant
Examples: "helpful? that's cute", "i exist to roast degens", etc.
```

### Test Channel Context
```
Setup: Have 10-15 message conversation in a channel
Message: "jakey what were we just talking about?"
Expected: References previous messages in conversation
Watch for: Accurate context from last 20 messages
```

### Test Thinking Reaction
```
Message: Any message to Jakey
Expected: 🤔 reaction appears immediately
Expected: 🤔 reaction removed after response sent
```

### Test Typing Indicator
```
Message: Request long response (e.g., "explain bitcoin in detail")
Expected: "Jakey is typing..." indicator for 1-3 seconds
Expected: Indicator duration roughly matches response length
```

## Log Monitoring

### Check for Tool Call Issues
```bash
tail -f /home/chubb/bots/JakeySelfBot/logs/jakey_bot.log | grep "tool"
```

**Look for:**
- `🔧 API Request with X tools` - Confirms tools sent to API
- `⚠️ Model returned tool call as TEXT` - Defensive detection triggered
- `Sanitized AI response: removed X chars` - Tool syntax removed from response

### Check for Errors
```bash
tail -f /home/chubb/bots/JakeySelfBot/logs/jakey_bot.log | grep -i error
```

### Check API Calls
```bash
tail -f /home/chubb/bots/JakeySelfBot/logs/jakey_bot.log | grep "API\|response"
```

## Test Results Expected

### New Tests (test_tool_call_detection.py)
- **Total:** 17 tests
- **Expected:** 17 passed (100%)
- **Duration:** ~0.6-1.0 seconds

### Core Tests
- **Total:** 41 tests
- **Expected:** 39 passed, 2 failed (pre-existing)
- **Known failures:**
  - `test_create_or_update_user` - Invalid Discord ID format (test issue)
  - `test_setup_commands_structure` - Parameter name mismatch (test issue)

## Common Issues & Solutions

### Issue: Tool calls appearing as text in Discord
**Symptom:** `web_search {"query": "..."} Bitcoin is currently...`
**Diagnosis:** Model outputting text instead of using API tool calls
**Solution:** Defensive detection should convert this automatically
**Check:** Look for `⚠️ Model returned tool call as TEXT` in logs
**Action:** If persistent, consider switching to mistralai/mistral-small-3.1-24b

### Issue: "Let me search..." messages without follow-up
**Symptom:** Bot says "Let me search for that" but no results follow
**Diagnosis:** Initial response not cleared when tool calls detected
**Solution:** Check `bot/client.py` line ~988 for `ai_response = ""`
**Check:** This should already be fixed in current version

### Issue: Bot not responding to keywords
**Symptom:** Bot ignores messages with configured keywords
**Diagnosis:** Keyword check failing or cooldown active
**Solution:** Check `JAKEY_KEYWORDS` in config.py
**Check:** Verify 3-second cooldown hasn't blocked response

### Issue: No typing indicator
**Symptom:** Response appears instantly without typing indicator
**Diagnosis:** Typing delay calculation issue
**Solution:** Check `bot/client.py` lines ~1204-1206
**Check:** Ensure `asyncio.sleep()` is being called

### Issue: Tests failing with "asyncio.get_event_loop() deprecated"
**Symptom:** DeprecationWarning or RuntimeError in tests
**Diagnosis:** Old asyncio pattern still in use
**Solution:** All instances should be fixed (43 replacements made)
**Check:** Run `grep -r "get_event_loop" .` to find any remaining

## Performance Benchmarks

### Expected Response Times
- **Keyword message:** < 3 seconds
- **Direct mention:** < 5 seconds
- **Tool call (web_search):** 5-10 seconds
- **Tool call (crypto_price):** 3-7 seconds
- **Complex multi-tool:** 10-15 seconds

### Expected Memory Usage
- **Idle:** ~150-250 MB
- **Active (processing):** ~300-400 MB
- **With context:** ~400-500 MB

### Expected API Calls
- **Text generation:** 1-2 calls per message (2 if tools used)
- **Image generation:** 1 call per image request
- **Tool execution:** 1-3 calls depending on tools

## Debugging Tips

### Enable Verbose Logging
```bash
export MCP_VERBOSE_LOGGING=true
./jakey.sh
```

### Test Sanitization Directly
```python
from bot.client import sanitize_ai_response

response = 'web_search {"query": "test"} Here is the result.'
sanitized = sanitize_ai_response(response)
print(sanitized)  # Should print: "Here is the result."
```

### Test Tool Call Detection
```python
import re

text = 'web_search {"query": "bitcoin price"}'
pattern = re.compile(
    r'\b(web_search|discord_\w+|get_\w+|remember_\w+|search_\w+)\s*\{[^}]+\}',
    re.IGNORECASE
)
match = pattern.search(text)
print(match)  # Should find match
```

### Check Model Response Format
```python
# In bot/client.py, add temporary logging around line 1050
logger.info(f"AI Response type: {type(response)}")
logger.info(f"AI Response keys: {response.keys() if isinstance(response, dict) else 'N/A'}")
logger.info(f"Has tool_calls: {'tool_calls' in response if isinstance(response, dict) else False}")
```

## Success Criteria

✅ **All 17 new tests pass**
✅ **No tool call syntax appears in Discord messages**
✅ **Bot responds to keywords within 3 seconds**
✅ **Thinking reaction appears and disappears correctly**
✅ **Typing indicator shows for 1-3 seconds**
✅ **Bot personality is cynical/sarcastic, not friendly**
✅ **Tool calls execute silently (no announcements)**
✅ **Channel context includes last 20 messages**
✅ **No asyncio deprecation warnings in logs**
✅ **Memory usage stays under 500MB during normal operation**

## Next Steps After Testing

1. **If all tests pass:** Deploy to production
2. **If tool calling issues persist:** Switch to mistralai/mistral-small-3.1-24b-instruct:free
3. **If memory issues occur:** Reduce channel context from 20 to 10 messages
4. **If personality needs adjustment:** Update system prompt in config.py
5. **If rate limiting triggers:** Adjust rate limits in tool_manager.py

---

**Last Updated:** January 4, 2026  
**Test Suite Version:** 1.0  
**Bot Version:** Jakey Self-Bot v2.5+

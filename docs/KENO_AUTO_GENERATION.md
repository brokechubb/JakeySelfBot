# Keno Auto-Generation Feature

This document describes the automatic Keno number generation feature that has been integrated into JakeySelfBot's AI response system.

## Feature Overview

Jakey can now automatically generate Keno numbers when users ask for them in natural conversation, without requiring the `%keno` command. This enhancement makes the bot more intuitive and user-friendly.

## Implementation Details

### Automatic Detection
The feature is implemented in the `process_jakey_response` method in `bot/client.py`. When Jakey receives a message, it first checks if the message contains Keno-related keywords before processing it with the AI.

### Keywords Triggering Auto-Generation
The following keywords/phrases will trigger automatic Keno number generation:
- `keno`
- `keno numbers`
- `keno picks`
- `keno numbers please`
- `keno picks please`
- `keno number`
- `keno pick`

### Case Insensitive Matching
Keyword detection is case-insensitive, so all of these will work:
- "Can you give me some keno numbers?"
- "KENO NUMBERS PLEASE"
- "I need Keno picks for tonight"
- "what are some good KENO numbers?"

### Response Generation
When a Keno request is detected, Jakey will:
1. Generate 3-10 random numbers from 1-40 (random count each time)
2. Sort the numbers in ascending order
3. Create a visual 8×5 board representation
4. Format the response with Discord markdown
5. Send the response immediately (bypassing AI processing)
6. Log the conversation in the database

## Response Format

The auto-generated Keno response follows this format:

```
**🎯 Keno Number Generator**
Generated **X** numbers for you!

**Your Keno Numbers:**
`X, X, X, ...`

**Visual Board:**
```
 1   2  [ 3]  4   5   6  [ 7]  8
 9  10   11  12  13  14  [15] 16
17  18   19  20  21 [22]  23  24
25 [26]  27 [28]  29  30  [31] 32
33  34  [35] 36  37  38   39 [40]
```
*Numbers in brackets are your picks!*
```

## Technical Implementation

### Early Return Pattern
The feature uses an early return pattern to prevent unnecessary AI processing when Keno numbers are requested:

```python
# If the message is asking for Keno numbers, generate them automatically
if any(keyword in message_content_lower for keyword in keno_keywords):
    # ... generate and send Keno numbers ...
    return  # Don't process with AI since we already responded
```

### Visual Board Generation
The visual board is generated with clean, consistent spacing:
- 8 columns × 5 rows (numbers 1-40)
- Selected numbers shown in brackets: `[XX]`
- Unselected numbers shown with padding: ` XX `
- Each number slot takes exactly 5 characters
- Proper alignment and readability

### Database Integration
Keno conversations are logged in the database for consistency:
- User message is recorded as the prompt
- Generated numbers are recorded in the response
- Conversation history is maintained

## Usage Examples

### Natural Language Requests
Users can ask for Keno numbers in various ways:
- "Can you give me some keno numbers?"
- "I need keno picks for tonight"
- "keno numbers please"
- "What are some good keno numbers?"
- "Jakey, can you generate keno picks?"
- "I want to play keno, give me some numbers"
- "keno"
- "play some keno"

### Manual Command Alternative
Users can still use the `%keno` command for explicit generation:
```
%keno
```

## Benefits

### User Experience
- **Intuitive**: Users don't need to remember specific commands
- **Natural**: Works with conversational language
- **Immediate**: Fast response without AI processing delay
- **Visual**: Clear, formatted output with visual board

### Technical Advantages
- **Efficient**: Bypasses AI processing for Keno requests
- **Reliable**: No dependency on external AI for number generation
- **Consistent**: Predictable output format
- **Logged**: Conversations maintained in database

## Testing

### Keyword Detection
The feature has been tested with various keyword combinations and edge cases to ensure robust detection.

### Response Generation
Visual board generation and response formatting have been verified for different number combinations.

### Integration
The early return pattern and database logging have been confirmed to work correctly.

## Future Enhancements

### Potential Improvements
- **Custom Count**: Allow users to specify number count (3-10)
- **History Tracking**: Remember user's previously generated numbers
- **Pattern Analysis**: Generate numbers based on "lucky" patterns
- **Multi-Game Support**: Extend to other lottery-style games

### Smart Features
- **Personalized Picks**: Use user's remembered "lucky" numbers
- **Statistical Analysis**: Track frequently generated numbers
- **Advanced Visualization**: Enhanced board formatting options

## Conclusion

The Keno auto-generation feature successfully enhances Jakey's gambling-themed functionality by making Keno number generation more accessible and intuitive. The implementation is robust, efficient, and well-integrated into the existing AI response system.
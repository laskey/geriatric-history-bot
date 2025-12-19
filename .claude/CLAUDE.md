# CLAUDE.md - Instructions for Claude Code

This file provides context and instructions for Claude Code when working on this project.

## Project Context

This is a voice AI system for geriatric patient intake. Read `docs/PROJECT_SPEC.md` for full details.

**Key points:**
- Uses OpenAI Realtime API (NOT regular Chat Completions)
- Conducts pre-appointment phone conversations with elderly patients
- Extracts structured data via tool calls during conversation
- Maps output to a Comprehensive Geriatric Assessment form

## Critical: Realtime API Documentation

The OpenAI Realtime API has evolved significantly and may differ from training data. **Always refer to the local documentation in `docs/realtime-api/` before implementing Realtime API features.**

Key files to consult:
- `docs/realtime-api/realtime-guide.md` - Core API concepts, events, session management
- `docs/realtime-api/realtime-prompting.md` - System prompt structure, conversation flow patterns
- `docs/realtime-api/realtime-costs.md` - Token management, truncation, caching
- `docs/realtime-api/developer-notes.md` - Developer notes with development guidance

If documentation is missing or you need current information, tell the user to update it from:
- https://platform.openai.com/docs/guides/realtime
- https://cookbook.openai.com/examples/realtime_prompting_guide
- https://platform.openai.com/docs/guides/realtime-costs

## Code Style

- Python 3.11
- Use dataclasses for state management
- Type hints everywhere
- Async/await for WebSocket operations
- Keep functions focused and small

## Key Files

| File | Purpose | Edit Carefully |
|------|---------|----------------|
| `src/config/system_prompt.py` | The main prompt - this is where most iteration happens | Yes - changes affect conversation |
| `src/config/tools.py` | Tool definitions for structured extraction | Yes - must match handler code |
| `src/backend/tool_handlers.py` | Executes tools, updates state | Moderate |
| `src/backend/state.py` | CallState dataclass | Moderate |

## Common Tasks

### Modifying the conversation flow
1. Edit the Conversation Flow section in `system_prompt.py`
2. Test with simulated patient input
3. Check that transitions work as expected

### Adding a new tool
1. Add tool definition to `tools.py`
2. Add handler method to `tool_handlers.py`
3. Update state.py if new data fields needed
4. Update coverage tracking if it's a required topic

### Testing a conversation
```bash
python src/main.py --simulate
```
This runs with text input (no audio) for rapid iteration.

### Debugging tool calls
Tool calls are logged to console. Check:
- Is the tool being called at the right time?
- Are arguments being extracted correctly?
- Is state being updated?

## Realtime API Patterns

### Session Configuration
```python
await ws.send(json.dumps({
    "type": "session.update",
    "session": {
        "instructions": SYSTEM_PROMPT,
        "tools": TOOLS,
        "voice": "coral",
        "turn_detection": {
            "type": "semantic_vad",
            "eagerness": "low"
        }
    }
}))
```

### Handling Tool Calls
When you receive `response.function_call_arguments.done`:
1. Parse the arguments
2. Execute the tool handler
3. Send result back:
```python
await ws.send(json.dumps({
    "type": "conversation.item.create",
    "item": {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps(result)
    }
}))
```
4. Trigger continuation:
```python
await ws.send(json.dumps({"type": "response.create"}))
```

### Key Event Types
- `session.created` - Session ready, trigger opening
- `response.function_call_arguments.done` - Tool call ready to execute
- `conversation.item.input_audio_transcription.completed` - Patient speech transcribed
- `response.audio_transcript.done` - AI response transcribed
- `response.done` - Turn complete

## Geriatric-Specific Reminders

When modifying prompts or conversation flow:
- Keep pacing slow and clear
- One question at a time
- Allow for pauses (semantic_vad with low eagerness)
- Handle tangents gracefully
- Never be patronizing
- Always respect patient dignity

## Testing Scenarios

Cover these cases:
1. **Happy path** - Patient answers all questions clearly
2. **Tangential patient** - Goes off on stories, need to redirect
3. **Confused patient** - Needs simpler questions, confirmation
4. **Caregiver on line** - Speaking about patient in third person
5. **Urgent concern** - Patient mentions chest pain, falls, etc.
6. **Incomplete medications** - Patient doesn't know all their meds
7. **Callback requested** - Patient wants to talk to human

## Don't

- Don't use Chat Completions API patterns - this is Realtime API
- Don't assume message history management - Realtime handles it
- Don't add LangGraph or other frameworks without discussion
- Don't skip the documentation check for Realtime API features
- Don't provide medical advice in any prompt text

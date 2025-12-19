# CLAUDE.md - Instructions for Claude Code

This file provides context and instructions for Claude Code when working on this project.

## Documentation Maintenance

**Keep documentation current.** When making significant changes to architecture, adding new patterns, or discovering important information:
- Update this file (CLAUDE.md) with new instructions or patterns
- Update `docs/PROJECT_SPEC.md` if requirements or architecture change
- Update `docs/realtime-api/` if you learn new API behaviors
- Remove outdated information rather than letting it accumulate

## Project Context

This is a voice AI system for geriatric patient intake. Read `docs/PROJECT_SPEC.md` for full details.

**Key points:**
- Uses OpenAI Realtime API GA interface (NOT beta, NOT Chat Completions)
- Model: `gpt-realtime` (not mini for POC)
- Conducts pre-appointment phone conversations with elderly patients
- Extracts structured data via tool calls during conversation
- Maps output to a Comprehensive Geriatric Assessment form

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Browser (TypeScript Agents SDK)                │
│         WebRTC connection to OpenAI Realtime API            │
└─────────────────────────────────────────────────────────────┘
                               │
                    Same Realtime Session
                               │
┌─────────────────────────────────────────────────────────────┐
│            Python Backend (Sideband WebSocket)              │
│  • Connects to same session via WebSocket                   │
│  • Receives and handles all tool calls                      │
│  • Manages CallState                                        │
│  • Coverage tracking                                        │
│  • Structured output generation                             │
└─────────────────────────────────────────────────────────────┘
```

- **Frontend**: OpenAI Agents SDK for TypeScript handles WebRTC audio capture/playback
- **Backend**: Python connects via sideband WebSocket to handle tools (NOT audio relay)
- **Sideband pattern**: Both frontend and backend connect to the same Realtime session
- **Text simulation**: `--simulate` mode for rapid iteration without audio/frontend

### Frontend-Backend Communication Flow
1. Browser establishes WebRTC connection to OpenAI, gets `call_id` from `Location` header
2. Browser sends `call_id` to Python backend via HTTP POST
3. Python backend connects to same session via `wss://api.openai.com/v1/realtime?call_id={call_id}`
4. Python backend sends session.update with tools and instructions
5. Python backend handles all tool calls, updates state
6. Python backend streams state updates to browser via WebSocket for live display

## Critical: Realtime API Documentation

We target the **GA interface** (not beta). The local documentation in `docs/realtime-api/` is authoritative.

Key files to consult:
- `docs/realtime-api/realtime-guide.md` - Core API concepts, events, session management
- `docs/realtime-api/realtime-prompting.md` - System prompt structure, conversation flow patterns
- `docs/realtime-api/realtime-costs.md` - Token management, truncation, caching
- `docs/realtime-api/developer-notes.md` - Developer notes with development guidance
- `docs/realtime-api/realtime-server-controls.md` - Sideband WebSocket connection patterns

If documentation is missing or you need current information, tell the user to update it from:
- https://platform.openai.com/docs/guides/realtime
- https://platform.openai.com/docs/guides/realtime-vad
- https://cookbook.openai.com/examples/realtime_prompting_guide

## Code Style

- Python 3.11
- Use dataclasses for state management
- Type hints everywhere
- Async/await for WebSocket operations
- Keep functions focused and small
- **Maintainability first**: Well-structured, easy to refactor

## Environment

API key is loaded from `.env` file (uses python-dotenv):
```bash
cp .env.example .env
# Edit .env with your API key
```

Or export directly:
```bash
export OPENAI_API_KEY="sk-..."
```

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

### Testing a conversation (text mode)
```bash
python -m src.main --simulate
```
This runs with text input (no audio) for rapid iteration.

### Running the web server (voice mode)
```bash
python -m src.main --server --port 8080
```
Starts the web UI at http://localhost:8080 for browser-based voice testing.
- Serves the frontend UI
- Handles WebRTC sideband connections automatically
- Supports multiple concurrent testers

For deployment on a VM:
```bash
python -m src.main --server --host 0.0.0.0 --port 80
```

### Running with sideband (manual)
```bash
python -m src.main --sideband <call_id>
```
Connects to an existing WebRTC session by call ID (rarely needed - server mode handles this).

### Debugging tool calls
Tool calls are logged to console. Check:
- Is the tool being called at the right time?
- Are arguments being extracted correctly?
- Is state being updated?

## Realtime API Patterns (GA Interface)

### Session Configuration
```python
# GA interface requires session.type and nested audio config
await ws.send(json.dumps({
    "type": "session.update",
    "session": {
        "type": "realtime",
        "model": "gpt-realtime",
        "instructions": SYSTEM_PROMPT,
        "tools": TOOLS,
        "audio": {
            "input": {
                "turn_detection": {
                    "type": "semantic_vad",
                    "eagerness": "low",
                    "create_response": True,
                    "interrupt_response": True
                }
            },
            "output": {
                "voice": "coral"
            }
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

### Key Event Types (GA naming)
- `session.created` - Session ready, trigger opening
- `response.function_call_arguments.done` - Tool call ready to execute
- `conversation.item.input_audio_transcription.completed` - Patient speech transcribed
- `response.output_audio_transcript.delta` - AI response transcript streaming
- `response.output_audio_transcript.done` - AI response transcript complete
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
- Don't use beta interface patterns - we use GA
- Don't assume message history management - Realtime handles it
- Don't add LangGraph or other frameworks without discussion
- Don't skip the documentation check for Realtime API features
- Don't provide medical advice in any prompt text
- Don't relay audio through Python backend - use Agents SDK WebRTC

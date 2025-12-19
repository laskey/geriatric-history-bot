# Geriatric Voice AI Intake System - Project Specification

## Project Overview

This project implements a voice-enabled patient intake system for geriatric medicine. The system conducts pre-appointment phone/web conversations with older adult patients (or their caregivers) to gather medical and social history, producing structured data that maps to a Comprehensive Geriatric Assessment (CGA) form.

### The Problem

Lindy is a geriatrician whose hospital lacks budget for dedicated intake nurses. Pre-appointment history gathering is currently a bottleneck:
- Web-based forms are difficult for older adults
- Traditional robocalls are impersonal and can't handle natural conversation
- Patients often go on tangents or report urgent issues that robocalls can't triage
- Without pre-gathered history, appointments are less efficient

### The Solution

A voice AI system using OpenAI's Realtime API that:
- Conducts natural, patient-paced conversations
- Extracts structured data via tool calls during the conversation
- Handles tangents gracefully while ensuring required topics are covered
- Flags urgent concerns for clinical follow-up
- Produces output that maps directly to the clinic's assessment form

## Clinical Context

### Target Users
- **Primary**: Geriatric patients (typically 65+) awaiting appointments
- **Secondary**: Caregivers/family members accompanying or representing patients
- **End consumer**: Dr. Romanovsky (geriatrician) who reviews the output before appointments

### Clinical Form Being Populated

The system gathers information for a Comprehensive Geriatric Assessment with these sections:

#### Sections Suitable for Voice AI (in scope)
| Section | Priority | Notes |
|---------|----------|-------|
| Reason for Referral | Must cover | Why they're being seen |
| Social History | Must cover | Housing, supports, hobbies, goals of care, substances |
| Functional Status - ADLs | Must cover | Bathing, dressing, eating, ambulation, transfers, toileting |
| Functional Status - IADLs | Must cover | Shopping, meal prep, housework, scheduling, banking, driving |
| Equipment | Should cover | Grab bars, shower chair, walker, etc. |
| Review of Systems | Must cover | Memory, mood, falls, sleep, pain (key geriatric screens) |
| Medications | Best effort | Often incomplete over phone - will verify at appointment |
| Allergies | Should cover | Include reaction type to distinguish true allergies |
| Medical/Surgical History | Best effort | Often incomplete - will verify at appointment |

#### Sections NOT Suitable for Voice AI (out of scope)
- Clinical Frailty Score (requires clinical observation)
- Mental Status Exam (requires in-person assessment)
- Physical Exam (vitals, neuro exam, etc.)
- Labs/Investigations

### Geriatric-Specific Requirements

1. **Pacing**: Speak clearly and slightly slower than normal conversation
2. **One question at a time**: Never stack multiple questions
3. **Patience with tangents**: Older adults often tell stories - extract useful information, gently redirect
4. **Caregiver awareness**: May be speaking with family member, adjust language accordingly
5. **Cognitive accommodation**: If patient seems confused, simplify and confirm understanding
6. **Hearing accommodation**: Be prepared to repeat, speak clearly
7. **Dignity**: Never patronizing, always respectful

## Technical Architecture

### Chosen Approach

**OpenAI Realtime API directly** (no Vapi, no LangGraph for POC)

Rationale:
- Realtime API now handles conversation context automatically
- Well-structured system prompt with tools is sufficient for this use case
- Fewer dependencies = easier debugging and learning
- Can add LangGraph later if needed for production

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Patient Interface                        │
│            (Browser WebRTC for POC, Twilio later)           │
└──────────────────────┬──────────────────────────────────────┘
                       │ Audio stream
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  OpenAI Realtime API                         │
│                                                              │
│  • Receives audio, maintains conversation context           │
│  • Follows system prompt with conversation flow             │
│  • Calls tools to extract structured data                   │
│  • Returns audio responses                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket events (tool calls, transcripts)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Python Backend                             │
│                                                              │
│  • WebSocket connection to Realtime API                     │
│  • Tool handlers update CallState                           │
│  • Coverage tracking (what topics remain)                   │
│  • Transcript storage                                       │
│  • Structured output generation                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Structured JSON Output                          │
│                                                              │
│  • Maps to CGA form fields                                  │
│  • Includes urgent flags                                    │
│  • Full transcript for clinical reference                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. System Prompt (`geriatric_voice_ai_prompt.py`)
Structured per OpenAI's Realtime Prompting Guide:
- Role & Objective
- Personality & Tone (warm, patient, measured pacing)
- Tools (when/how to use each)
- Instructions (geriatric-specific interview guidance)
- Conversation Flow (JSON state machine)
- Safety & Escalation

#### 2. Tools (13 defined)
- `record_referral_reason`
- `record_social_history` (category-based)
- `record_adl_status`, `record_iadl_status`
- `record_gait_aid`, `record_equipment`
- `record_review_of_systems`
- `record_medication`, `record_allergy`, `record_medical_history`
- `flag_urgent_concern`
- `check_coverage_status`, `end_interview`

#### 3. Backend State Management
Simple Python dataclass tracking:
- All extracted clinical data
- Topics covered vs remaining
- Transcript
- Urgent flags

#### 4. Session Configuration
```python
{
    "model": "gpt-realtime",  # or gpt-realtime-mini for lower cost
    "voice": "coral",
    "turn_detection": {
        "type": "semantic_vad",  # Better for elderly speakers
        "eagerness": "low"       # Don't interrupt pauses
    },
    "input_audio_transcription": {
        "model": "gpt-4o-transcribe"
    }
}
```

## Conversation Flow

The system follows this flow, with the model managing transitions:

```
Opening (scripted) → Consent Check → Check Accompaniment
    ↓
Reason for Visit → Social History → Functional Status (ADLs/IADLs)
    ↓
Review of Systems → Medications → Allergies → Medical History
    ↓
Pre-Closing (summary + additions) → Closing (scripted)
```

Special flows:
- `arrange_callback` - if patient can't talk or requests human
- `urgent_escalation` - if patient reports emergency symptoms

## Cost Analysis

Based on December 2025 OpenAI pricing:

| Model | Audio In | Audio Out | Est. per 10-min call |
|-------|----------|-----------|----------------------|
| gpt-realtime | $0.02/min | $0.08/min | $0.50-0.75 |
| gpt-realtime-mini | Lower | Lower | $0.20-0.35 |

At $0.75/call, 20 calls/day = $15/day = ~$4,000/year (vs $60-80K for intake nurse)

## Development Phases

### Phase 1: POC (Current)
- [x] Python backend with state management and tool handlers
- [x] Text-based simulation mode for rapid iteration
- [x] System prompt with conversation flow
- [x] Structured JSON output generation
- [ ] Browser-based WebRTC audio capture (TypeScript frontend)
- [ ] Sideband connection between frontend and backend

### Phase 2: Iteration
- [ ] Test with colleagues roleplaying patients
- [ ] Refine prompt based on failure modes
- [ ] Clinical review of output quality
- [ ] Handle edge cases (confused patients, tangential conversations)

### Phase 3: Production Readiness
- [ ] Add Twilio for phone-based access
- [ ] HIPAA/PHIPA compliance review
- [ ] Integration with clinic systems
- [ ] Institutional approval process

## File Structure

```
geriatric-history-bot/
├── .claude/
│   └── CLAUDE.md                       # Instructions for Claude Code
├── docs/
│   ├── PROJECT_SPEC.md                 # This file
│   └── realtime-api/                   # Downloaded API documentation
│       ├── realtime-guide.md
│       ├── realtime-prompting.md
│       ├── realtime-costs.md
│       ├── developer-notes.md
│       └── realtime-server-controls.md # Sideband WebSocket patterns
├── src/
│   ├── config/
│   │   ├── system_prompt.py            # The main prompt configuration
│   │   └── tools.py                    # Tool definitions
│   ├── backend/
│   │   ├── realtime_connection.py      # WebSocket connection handler
│   │   ├── tool_handlers.py            # Tool execution logic
│   │   ├── state.py                    # CallState dataclass
│   │   └── output.py                   # Structured output generation
│   ├── frontend/                       # Browser-based UI (planned)
│   │   ├── index.html
│   │   └── app.ts
│   └── main.py                         # Entry point (--simulate, --sideband)
├── output/                             # Generated call outputs (gitignored)
├── .env.example                        # Environment template
└── pyproject.toml                      # Python dependencies
```

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Voice API | OpenAI Realtime | Best UX, maintains context, good tool calling |
| Orchestration | None (prompt-based) | Sufficient for POC, adds LangGraph later if needed |
| State management | Python dataclass | Simple, no framework overhead |
| Audio capture (POC) | Browser WebRTC | Easiest for testing |
| Audio capture (prod) | Twilio | Phone accessibility for elderly |
| VAD | semantic_vad, low eagerness | Elderly speakers pause mid-thought |

## Important Constraints

### Clinical Safety
- NEVER provide medical advice or interpret symptoms
- NEVER suggest diagnoses
- ALWAYS flag urgent concerns (chest pain, falls with injury, suicidal ideation)
- For emergencies, direct to 911

### Data Handling
- All data is PHI - handle accordingly
- Transcripts stored securely
- Output reviewed by clinician before use
- Development uses synthetic patients only

### Conversation Quality
- Opening and closing are scripted (consistent disclosure)
- Main interview is guided but natural
- Coverage tracking ensures required topics are addressed
- Time target: 10-15 minutes

## Resources

### OpenAI Documentation (save locally for Claude Code)
- Realtime API Guide: https://platform.openai.com/docs/guides/realtime
- Realtime Prompting Guide: https://cookbook.openai.com/examples/realtime_prompting_guide
- Managing Costs: https://platform.openai.com/docs/guides/realtime-costs
- Developer Notes: https://developers.openai.com/blog/realtime-api/

### Example Code
- Realtime Console: https://github.com/openai/openai-realtime-console
- Twilio Integration: https://github.com/openai/openai-realtime-twilio-demo

## Success Criteria

### POC Success
- [ ] Complete a 10-minute simulated patient conversation
- [ ] Extract structured data for all "must cover" topics
- [ ] Generate output that maps to CGA form
- [ ] Handle at least one "urgent flag" scenario correctly
- [ ] Lindy reviews output and confirms clinical utility

### Production Success
- [ ] Real patients can complete calls via phone
- [ ] Output quality reviewed and approved by clinical team
- [ ] Integration with clinic workflow
- [ ] Cost per call < $1.00
- [ ] Patient satisfaction comparable to nurse intake

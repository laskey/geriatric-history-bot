# OpenAI Realtime Prompting Guide

*Downloaded: December 2025*
*Source: https://cookbook.openai.com/examples/realtime_prompting_guide*

This guide covers prompting techniques for OpenAI's Realtime API speech-to-speech models. These techniques differ from text-based models.

---

## General Tips

* **Iterate relentlessly**: Small wording changes can make or break behavior.
  + Example: For unclear audio instruction, swapping "inaudible" → "unintelligible" improved noisy input handling.
* **Prefer bullets over paragraphs**: Clear, short bullets outperform long paragraphs.
* **Guide with examples**: The model strongly follows sample phrases.
* **Be precise**: Ambiguity or conflicting instructions = degraded performance.
* **Control language**: Pin output to a target language if you see unwanted language switching.
* **Reduce repetition**: Add a Variety rule to reduce robotic phrasing.
* **Use capitalized text for emphasis**: Capitalizing key rules makes them stand out.
* **Convert non-text rules to text**: instead of writing "IF x > 3 THEN ESCALATE", write, "IF MORE THAN THREE FAILURES THEN ESCALATE".

---

## Prompt Structure

Organizing your prompt makes it easier for the model to understand context and stay consistent across turns.

**Recommended sections:**

```
# Role & Objective        — who you are and what "success" means  
# Personality & Tone      — the voice and style to maintain  
# Context                 — retrieved context, relevant info
# Reference Pronunciations — phonetic guides for tricky words  
# Tools                   — names, usage rules, and preambles  
# Instructions / Rules    — do's, don'ts, and approach  
# Conversation Flow       — states, goals, and transitions  
# Safety & Escalation     — fallback and handoff logic
```

Add domain-specific sections as needed (e.g., Compliance, Brand Policy). Remove sections you don't need.

---

## Role and Objective

This section defines who the agent is and what "done" means.

* **When to use**: The model is not taking on the persona, role, or task scope you need.
* **What it does**: Pins identity of the voice agent so that its responses are conditioned to that role description.

**Example:**
```
# Role & Objective
You are a customer service bot for Acme Corp. Your task is to answer the user's questions about their orders.
```

---

## Personality and Tone

The model can follow instructions to imitate a particular personality or tone.

* **When to use**: Responses feel flat, overly verbose, or inconsistent across turns.
* **What it does**: Sets voice, brevity, and pacing so replies sound natural and consistent.

**Example:**
```
# Personality & Tone
## Personality
- Friendly, calm and approachable expert customer service assistant.

## Tone
- Warm, concise, confident, never fawning.

## Length
- 2–3 sentences per turn.
```

### Speed Instructions

The `speed` parameter changes playback rate, not how the model composes speech. To actually sound faster, add instructions:

```
## Pacing
- Deliver your audio response fast, but do not sound rushed.
- Do not modify the content of your response, only increase speaking speed.
```

### Language Constraint

Lock output to prevent accidental language switching:

```
## Language
- The conversation will be only in English.
- Do not respond in any other language even if the user asks.
- If the user speaks another language, politely explain that support is limited to English.
```

### Reduce Repetition

The model may overuse sample phrases. Add a variety constraint:

```
## Variety
- Do not repeat the same sentence twice.
- Vary your responses so it doesn't sound robotic.
```

---

## Reference Pronunciations

For brand names, technical terms, or locations that are often mispronounced:

```
# Reference Pronunciations
When voicing these words, use the respective pronunciations:
- Pronounce "SQL" as "sequel."
- Pronounce "PostgreSQL" as "post-gress."
- Pronounce "Kyiv" as "KEE-iv."
```

### Alphanumeric Pronunciations

For phone numbers, codes, IDs - force character-by-character confirmation:

```
# Instructions/Rules
- When reading numbers or codes, speak each character separately, separated by hyphens (e.g., 4-1-5). 
- Repeat EXACTLY the provided number, do not forget any.
```

---

## Instructions

### Instruction Following

If instructions are conflicting, ambiguous, or unclear, the model will perform worse. Use this meta-prompt with GPT to check your prompt:

```
## Role & Objective  
You are a **Prompt-Critique Expert**.
Examine a user-supplied LLM prompt and surface any weaknesses.

## Instructions
Review the prompt and identify:
- Ambiguity: Could any wording be interpreted in more than one way?
- Lacking Definitions: Are there terms not defined that might be misinterpreted?
- Conflicting, missing, or vague instructions
- Unstated assumptions

## Output Format
# Issues
- Numbered list with brief quote snippets.

# Improvements
- Numbered list with revised lines.

# Revised Prompt
- Revised prompt with surgical edits applied.
```

### No Audio or Unclear Audio

Tell the model how to behave with unclear input:

```
## Unclear audio 
- Always respond in the same language the user is speaking in.
- Only respond to clear audio or text. 
- If the user's audio is not clear (background noise/silent/unintelligible), ask for clarification.
```

---

## Tools

### Tool Selection

Ensure tools mentioned in your prompt match the tools list. Descriptions should not contradict each other.

### Tool Call Preambles

For better UX, have the model speak while calling a tool (masks latency):

```
# Tools
- Before any tool call, say one short line like "I'm checking that now." Then call the tool immediately.
```

### Tool Calls Without Confirmation

For proactive tool calling without asking permission:

```
# Tools
- When calling a tool, do not ask for any user confirmation. Be proactive.
```

### Tool Call Performance

As tools increase, explicitly guide when to use each:

```
## lookup_account(email_or_phone)
Use when: verifying identity or viewing plan/outage flags.
Do NOT use when: the user is clearly anonymous and only asks general questions.

## check_outage(address)
Use when: user reports connectivity issues or slow speeds.
Do NOT use when: question is billing-only.

## escalate_to_human(account_id, reason)
Use when: user seems very frustrated, abuse/harassment, repeated failures, billing disputes >$50, or user requests escalation.
```

### Tool-Level Behavior

Fine-tune behavior per tool:

```
# TOOLS
- For tools marked PROACTIVE: do not ask for confirmation, no preamble.
- For tools marked CONFIRMATION FIRST: always ask for confirmation.
- For tools marked PREAMBLES: say a short line before calling.

## lookup_account(email_or_phone) — PROACTIVE
...

## refund_credit(account_id, minutes) — CONFIRMATION FIRST
Confirmation phrase: "I can issue a credit for this outage—would you like me to go ahead?"

## escalate_to_human(account_id, reason) — PREAMBLES
Preamble: "Let me connect you to a senior agent who can assist further."
```

---

## Conversation Flow

Structure dialogue into clear, goal-driven phases with explicit transitions.

* **When to use**: If conversations feel disorganized or stall before reaching the goal.
* **What it does**: Breaks the interaction into phases with clear goals, instructions, and exit criteria.

**Example:**
```
# Conversation Flow

## 1) Greeting
Goal: Set tone and invite the reason for calling.
How to respond:
- Identify as NorthLoop Internet Support.
- Keep the opener brief and invite the caller's goal.
Exit when: Caller states an initial goal or symptom.

## 2) Discover
Goal: Classify the issue and capture minimal details.
How to respond:
- Determine billing vs connectivity with one targeted question.
- For connectivity: collect the service address.
Exit when: Intent and address (for connectivity) or email/phone (for billing) are known.

## 3) Verify
Goal: Confirm identity and retrieve the account.
How to respond:
- Call lookup_account(email_or_phone).
- If lookup fails, try alternate identifier once.
Exit when: Account ID is returned.

...
```

### Conversation Flow as State Machine

For complex flows, define as JSON:

```json
[
  {
    "id": "1_greeting",
    "description": "Begin with a warm greeting.",
    "instructions": [
      "Use the company name and provide a warm welcome.",
      "Let them know you'll need verification for account help."
    ],
    "examples": [
      "Hello, this is Snowy Peak Boards. How can I help you today?"
    ],
    "transitions": [
      {"next_step": "2_get_first_name", "condition": "Once greeting is complete."},
      {"next_step": "3_get_phone", "condition": "If user provides their name."}
    ]
  },
  ...
]
```

### Dynamic Conversation Flow

For complex scenarios, update the system prompt dynamically using `session.update`:

```python
def build_session_update(state: str) -> dict:
    return {
        "type": "session.update",
        "session": {
            "instructions": INSTRUCTIONS_BY_STATE[state],
            "tools": TOOLS_BY_STATE[state] + [build_state_change_tool(state)]
        }
    }
```

This reduces cognitive load by only providing relevant context for the current phase.

---

## Sample Phrases

Sample phrases act as "anchor examples" for style, brevity, and tone.

```
# Sample Phrases
- Below are examples for inspiration. DO NOT ALWAYS USE THESE, VARY YOUR RESPONSES.

Acknowledgements: "On it." "One moment." "Good question."
Clarifiers: "Do you want A or B?" "What's the deadline?"
Bridges: "Here's the quick plan." "Let's keep it simple."
Empathy (brief): "That's frustrating—let's fix it."
Closers: "Anything else before we wrap?" "Happy to help next time."
```

Add sample phrases to conversation flow states for more control:

```json
{
  "id": "verify",
  "description": "Confirm identity.",
  "instructions": [...],
  "sample_phrases": [
    "Thanks—looking up your account now.",
    "Found your account. I'll take care of this."
  ]
}
```

---

## Safety & Escalation

Define when and how to escalate to humans.

```
# Safety & Escalation
When to escalate (no extra troubleshooting):
- Safety risk (self-harm, threats, harassment)
- User explicitly asks for a human
- Severe dissatisfaction (e.g., "extremely frustrated," repeated complaints)
- 2 failed tool attempts on the same task OR 3 consecutive no-match events
- Out-of-scope or restricted (financial/legal/medical advice)

What to say when escalating:
- "Thanks for your patience—I'm connecting you with a specialist now."
- Then call the tool: escalate_to_human
```

---

## Common Tools

The model is trained effectively on these common tool patterns:

```
# answer(question: string)
Description: Call when customer asks a question you don't have an answer to.

# escalate_to_human()
Description: Call when customer asks for escalation or expresses dissatisfaction.

# finish_session()
Description: Call when customer says they're done. If ambiguous, confirm first.
```

---

## Summary

Key principles for Realtime prompting:

1. **Structure your prompt** with clear sections
2. **Be explicit** about role, tone, and behavior
3. **Use tools** with clear usage rules and preambles
4. **Define conversation flow** with states and transitions
5. **Include sample phrases** for style anchoring
6. **Handle edge cases**: unclear audio, escalation, safety
7. **Iterate relentlessly** - small changes matter

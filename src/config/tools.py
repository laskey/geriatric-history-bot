"""
Tool definitions for the Realtime API.

These tools are called by the model during conversation to extract
structured data and update CallState.

Format follows OpenAI function calling schema.
"""

from typing import Any

# Tool definitions for Realtime API session configuration
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "record_referral_reason",
        "description": "Record why the patient is being seen. Call this after learning the main reason for their referral or visit.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "The primary reason for referral in the patient's own words or summarized"
                },
                "additional_concerns": {
                    "type": "string",
                    "description": "Any additional concerns mentioned beyond the primary reason"
                }
            },
            "required": ["reason"]
        }
    },
    {
        "type": "function",
        "name": "record_social_history",
        "description": "Record social history information. Call this when you learn about living situation, supports, activities, or substance use. Can be called multiple times for different categories.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "living_situation",
                        "support_system",
                        "activities",
                        "goals_of_care",
                        "tobacco",
                        "alcohol",
                        "other_substances"
                    ],
                    "description": "Which aspect of social history this covers"
                },
                "details": {
                    "type": "string",
                    "description": "The information provided about this category"
                }
            },
            "required": ["category", "details"]
        }
    },
    {
        "type": "function",
        "name": "record_adl_status",
        "description": "Record Activities of Daily Living status. Call when you learn about bathing, dressing, eating, walking, transfers, or toileting independence.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity": {
                    "type": "string",
                    "enum": ["bathing", "dressing", "eating", "ambulation", "transfers", "toileting"],
                    "description": "Which ADL activity"
                },
                "level": {
                    "type": "string",
                    "enum": ["independent", "needs_assistance", "dependent"],
                    "description": "Level of independence"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional details about assistance needed or circumstances"
                }
            },
            "required": ["activity", "level"]
        }
    },
    {
        "type": "function",
        "name": "record_iadl_status",
        "description": "Record Instrumental Activities of Daily Living status. Call when you learn about shopping, cooking, housework, appointments, finances, transportation, or medication management.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity": {
                    "type": "string",
                    "enum": [
                        "shopping",
                        "meal_preparation",
                        "housework",
                        "scheduling_appointments",
                        "managing_finances",
                        "driving_transportation",
                        "medication_management",
                        "telephone_use"
                    ],
                    "description": "Which IADL activity"
                },
                "level": {
                    "type": "string",
                    "enum": ["independent", "needs_assistance", "dependent"],
                    "description": "Level of independence"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional details about who helps or how"
                }
            },
            "required": ["activity", "level"]
        }
    },
    {
        "type": "function",
        "name": "record_equipment",
        "description": "Record assistive equipment or home safety items the patient uses.",
        "parameters": {
            "type": "object",
            "properties": {
                "equipment_type": {
                    "type": "string",
                    "enum": [
                        "gait_aid",
                        "hearing_aids",
                        "glasses",
                        "grab_bars",
                        "shower_chair",
                        "raised_toilet_seat",
                        "hospital_bed",
                        "oxygen",
                        "other"
                    ],
                    "description": "Type of equipment"
                },
                "details": {
                    "type": "string",
                    "description": "Specifics (e.g., 'walker with wheels', 'uses oxygen at night')"
                }
            },
            "required": ["equipment_type"]
        }
    },
    {
        "type": "function",
        "name": "record_review_of_systems",
        "description": "Record review of systems findings. Call when you learn about memory, mood, falls, sleep, pain, or sensory changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "system": {
                    "type": "string",
                    "enum": [
                        "memory",
                        "mood",
                        "falls",
                        "sleep",
                        "pain",
                        "vision",
                        "hearing",
                        "urinary",
                        "bowel",
                        "appetite_weight"
                    ],
                    "description": "Which system or symptom area"
                },
                "findings": {
                    "type": "string",
                    "description": "What the patient reported about this system"
                }
            },
            "required": ["system", "findings"]
        }
    },
    {
        "type": "function",
        "name": "record_medication",
        "description": "Record a medication the patient takes. Call once per medication mentioned.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Medication name (brand or generic)"
                },
                "dose": {
                    "type": "string",
                    "description": "Dose if known (e.g., '10mg', 'one pill')"
                },
                "frequency": {
                    "type": "string",
                    "description": "How often taken (e.g., 'once daily', 'twice a day')"
                },
                "purpose": {
                    "type": "string",
                    "description": "What the patient thinks it's for"
                }
            },
            "required": ["name"]
        }
    },
    {
        "type": "function",
        "name": "record_allergy",
        "description": "Record an allergy or adverse reaction. Call once per allergen mentioned.",
        "parameters": {
            "type": "object",
            "properties": {
                "allergen": {
                    "type": "string",
                    "description": "What the patient is allergic to"
                },
                "reaction": {
                    "type": "string",
                    "description": "What happens when exposed (rash, swelling, anaphylaxis, etc.)"
                },
                "severity": {
                    "type": "string",
                    "enum": ["mild", "moderate", "severe", "unknown"],
                    "description": "Severity of the reaction"
                }
            },
            "required": ["allergen"]
        }
    },
    {
        "type": "function",
        "name": "record_medical_history",
        "description": "Record a medical condition or past surgery. Call once per condition mentioned.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {
                    "type": "string",
                    "description": "Name of the condition or surgery"
                },
                "year": {
                    "type": "string",
                    "description": "When diagnosed or when surgery occurred"
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "resolved", "managed", "unknown"],
                    "description": "Current status of the condition"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional details"
                }
            },
            "required": ["condition"]
        }
    },
    {
        "type": "function",
        "name": "flag_urgent_concern",
        "description": "Flag an urgent clinical concern that needs immediate attention. Call for: chest pain, difficulty breathing, fall with injury, suicidal thoughts, abuse concerns, or other emergencies.",
        "parameters": {
            "type": "object",
            "properties": {
                "concern_type": {
                    "type": "string",
                    "enum": [
                        "chest_pain",
                        "breathing_difficulty",
                        "fall_with_injury",
                        "suicidal_ideation",
                        "abuse_concern",
                        "acute_confusion",
                        "other_emergency"
                    ],
                    "description": "Type of urgent concern"
                },
                "description": {
                    "type": "string",
                    "description": "Details about the concern"
                }
            },
            "required": ["concern_type", "description"]
        }
    },
    {
        "type": "function",
        "name": "record_speaker_info",
        "description": "Record who is on the call (patient or caregiver) and their basic info.",
        "parameters": {
            "type": "object",
            "properties": {
                "speaker_type": {
                    "type": "string",
                    "enum": ["patient", "caregiver"],
                    "description": "Whether speaking with the patient directly or a caregiver"
                },
                "patient_name": {
                    "type": "string",
                    "description": "Patient's name if provided"
                },
                "caregiver_name": {
                    "type": "string",
                    "description": "Caregiver's name if applicable"
                },
                "caregiver_relationship": {
                    "type": "string",
                    "description": "Caregiver's relationship to patient (spouse, daughter, etc.)"
                }
            },
            "required": ["speaker_type"]
        }
    },
    {
        "type": "function",
        "name": "check_coverage_status",
        "description": "Check which required topics have been covered and which remain. Call this to determine what to ask about next.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "type": "function",
        "name": "end_interview",
        "description": "Signal that the interview is complete. Call when all required topics are covered or the patient requests to end.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": [
                        "completed",
                        "callback_requested",
                        "patient_declined",
                        "urgent_escalation",
                        "technical_issue"
                    ],
                    "description": "Why the interview is ending"
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what was covered"
                }
            },
            "required": ["reason"]
        }
    }
]


def get_tool_names() -> list[str]:
    """Return list of all tool names."""
    return [tool["name"] for tool in TOOLS]


def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """Look up a tool definition by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None

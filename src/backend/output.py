"""
Output generation for completed calls.

Converts CallState to structured JSON suitable for clinical review.
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.backend.state import CallState, CallStatus, IndependenceLevel, SpeakerType


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON output."""
    if isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, (CallStatus, SpeakerType, IndependenceLevel)):
        return value.value
    elif isinstance(value, set):
        return list(value)
    elif hasattr(value, "__dataclass_fields__"):
        return _serialize_dataclass(value)
    elif isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _serialize_dataclass(obj: Any) -> dict[str, Any]:
    """Recursively serialize a dataclass to a dict."""
    result = {}
    for field_name in obj.__dataclass_fields__:
        value = getattr(obj, field_name)
        result[field_name] = _serialize_value(value)
    return result


def generate_output(state: CallState) -> dict[str, Any]:
    """
    Generate structured output from CallState.

    Returns a dict suitable for JSON serialization and clinical review.
    """
    output = {
        "meta": {
            "call_id": state.call_id,
            "started_at": state.started_at.isoformat(),
            "ended_at": state.ended_at.isoformat() if state.ended_at else None,
            "status": state.status.value,
            "speaker_type": state.speaker_type.value,
            "topics_covered": list(state.topics_covered),
            "topics_not_covered": list(state.get_uncovered_topics()),
            "has_urgent_concerns": state.has_urgent_concerns(),
        },
        "patient": {
            "name": state.patient_name,
            "date_of_birth": state.patient_date_of_birth,
            "caregiver_name": state.caregiver_name,
            "caregiver_relationship": state.caregiver_relationship,
        },
        "referral_reason": state.referral_reason,
        "social_history": _serialize_dataclass(state.social_history),
        "functional_status": {
            "adl": _serialize_dataclass(state.adl_status),
            "iadl": _serialize_dataclass(state.iadl_status),
        },
        "equipment": _serialize_dataclass(state.equipment),
        "review_of_systems": _serialize_dataclass(state.review_of_systems),
        "medications": [_serialize_dataclass(med) for med in state.medications],
        "allergies": [_serialize_dataclass(allergy) for allergy in state.allergies],
        "medical_history": [_serialize_dataclass(item) for item in state.medical_history],
        "urgent_concerns": [_serialize_dataclass(concern) for concern in state.urgent_concerns],
        "transcript": [_serialize_dataclass(entry) for entry in state.transcript],
    }

    return output


def save_output(state: CallState, output_dir: str = "output") -> Path:
    """
    Save call output to a JSON file.

    Args:
        state: The CallState to save
        output_dir: Directory to save output files

    Returns:
        Path to the saved file
    """
    output = generate_output(state)

    # Create output directory if needed
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename from call_id and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"call_{state.call_id}_{timestamp}.json"
    filepath = output_path / filename

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)

    return filepath


def print_summary(state: CallState) -> None:
    """Print a human-readable summary of the call to console."""
    print("\n" + "=" * 60)
    print("CALL SUMMARY")
    print("=" * 60)

    print(f"\nCall ID: {state.call_id}")
    print(f"Status: {state.status.value}")
    print(f"Speaker: {state.speaker_type.value}")

    if state.patient_name:
        print(f"Patient: {state.patient_name}")

    print(f"\nTopics Covered: {', '.join(state.topics_covered) or 'None'}")
    uncovered = state.get_uncovered_topics()
    if uncovered:
        print(f"Topics NOT Covered: {', '.join(uncovered)}")

    if state.has_urgent_concerns():
        print("\n⚠️  URGENT CONCERNS:")
        for concern in state.urgent_concerns:
            print(f"  - {concern.concern_type}: {concern.description}")

    print(f"\nReferral Reason: {state.referral_reason or 'Not recorded'}")

    if state.medications:
        print(f"\nMedications ({len(state.medications)}):")
        for med in state.medications:
            dose_info = f" {med.dose}" if med.dose else ""
            freq_info = f" {med.frequency}" if med.frequency else ""
            print(f"  - {med.name}{dose_info}{freq_info}")

    if state.allergies:
        print(f"\nAllergies ({len(state.allergies)}):")
        for allergy in state.allergies:
            reaction = f" ({allergy.reaction})" if allergy.reaction else ""
            print(f"  - {allergy.allergen}{reaction}")

    print("\n" + "=" * 60)

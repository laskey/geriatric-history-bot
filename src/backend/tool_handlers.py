"""
Tool handlers that execute tool calls and update CallState.

Each handler receives the tool arguments and the current CallState,
performs the update, and returns a result dict to send back to the model.
"""

import json
import logging
from datetime import datetime
from typing import Any, Callable

from src.backend.state import (
    Allergy,
    CallState,
    CallStatus,
    IndependenceLevel,
    MedicalHistoryItem,
    Medication,
    SpeakerType,
    UrgentConcern,
)

logger = logging.getLogger(__name__)


class ToolHandlers:
    """
    Handles tool calls from the Realtime API.

    Each method corresponds to a tool defined in tools.py.
    Methods update the CallState and return a result dict.
    """

    def __init__(self, state: CallState):
        self.state = state

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Route a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments passed to the tool

        Returns:
            Result dict to send back to the model
        """
        handler_map: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "record_referral_reason": self._record_referral_reason,
            "record_social_history": self._record_social_history,
            "record_adl_status": self._record_adl_status,
            "record_iadl_status": self._record_iadl_status,
            "record_equipment": self._record_equipment,
            "record_review_of_systems": self._record_review_of_systems,
            "record_medication": self._record_medication,
            "record_allergy": self._record_allergy,
            "record_medical_history": self._record_medical_history,
            "flag_urgent_concern": self._flag_urgent_concern,
            "record_speaker_info": self._record_speaker_info,
            "check_coverage_status": self._check_coverage_status,
            "end_interview": self._end_interview,
        }

        handler = handler_map.get(tool_name)
        if handler is None:
            logger.warning(f"Unknown tool: {tool_name}")
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        try:
            result = handler(arguments)
            logger.info(f"Tool {tool_name} executed: {result}")
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    def _record_referral_reason(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record the reason for referral."""
        reason = args.get("reason", "")
        additional = args.get("additional_concerns", "")

        self.state.referral_reason = reason
        if additional:
            self.state.referral_reason += f" Additional concerns: {additional}"

        self.state.mark_topic_covered("referral_reason")

        return {
            "success": True,
            "recorded": "referral_reason",
            "message": "Referral reason recorded."
        }

    def _record_social_history(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record social history by category."""
        category = args.get("category", "")
        details = args.get("details", "")

        sh = self.state.social_history

        category_map = {
            "living_situation": "living_situation",
            "support_system": "support_system",
            "activities": "hobbies_activities",
            "goals_of_care": "goals_of_care",
            "tobacco": "tobacco_use",
            "alcohol": "alcohol_use",
            "other_substances": "other_substances",
        }

        attr = category_map.get(category)
        if attr:
            setattr(sh, attr, details)
            self.state.mark_topic_covered("social_history")
            return {
                "success": True,
                "recorded": f"social_history.{category}",
                "message": f"Social history ({category}) recorded."
            }

        return {"success": False, "error": f"Unknown social history category: {category}"}

    def _record_adl_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record ADL status for a specific activity."""
        activity = args.get("activity", "")
        level_str = args.get("level", "")
        notes = args.get("notes", "")

        level_map = {
            "independent": IndependenceLevel.INDEPENDENT,
            "needs_assistance": IndependenceLevel.NEEDS_ASSISTANCE,
            "dependent": IndependenceLevel.DEPENDENT,
        }

        level = level_map.get(level_str)
        if level is None:
            return {"success": False, "error": f"Unknown independence level: {level_str}"}

        adl = self.state.adl_status
        if hasattr(adl, activity):
            setattr(adl, activity, level)
            if notes:
                existing_notes = adl.notes or ""
                separator = "\n" if existing_notes else ""
                adl.notes = f"{existing_notes}{separator}{activity}: {notes}"
            self.state.mark_topic_covered("adl_status")
            return {
                "success": True,
                "recorded": f"adl.{activity}",
                "level": level_str,
                "message": f"ADL status for {activity} recorded as {level_str}."
            }

        return {"success": False, "error": f"Unknown ADL activity: {activity}"}

    def _record_iadl_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record IADL status for a specific activity."""
        activity = args.get("activity", "")
        level_str = args.get("level", "")
        notes = args.get("notes", "")

        level_map = {
            "independent": IndependenceLevel.INDEPENDENT,
            "needs_assistance": IndependenceLevel.NEEDS_ASSISTANCE,
            "dependent": IndependenceLevel.DEPENDENT,
        }

        level = level_map.get(level_str)
        if level is None:
            return {"success": False, "error": f"Unknown independence level: {level_str}"}

        iadl = self.state.iadl_status
        if hasattr(iadl, activity):
            setattr(iadl, activity, level)
            if notes:
                existing_notes = iadl.notes or ""
                separator = "\n" if existing_notes else ""
                iadl.notes = f"{existing_notes}{separator}{activity}: {notes}"
            self.state.mark_topic_covered("iadl_status")
            return {
                "success": True,
                "recorded": f"iadl.{activity}",
                "level": level_str,
                "message": f"IADL status for {activity} recorded as {level_str}."
            }

        return {"success": False, "error": f"Unknown IADL activity: {activity}"}

    def _record_equipment(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record assistive equipment."""
        equipment_type = args.get("equipment_type", "")
        details = args.get("details", "")

        eq = self.state.equipment

        bool_equipment = {
            "hearing_aids", "glasses", "grab_bars", "shower_chair",
            "raised_toilet_seat", "hospital_bed", "oxygen"
        }

        if equipment_type == "gait_aid":
            eq.gait_aid = details or "uses gait aid"
        elif equipment_type in bool_equipment:
            setattr(eq, equipment_type, True)
            if details:
                existing_notes = eq.notes or ""
                separator = "\n" if existing_notes else ""
                eq.notes = f"{existing_notes}{separator}{equipment_type}: {details}"
        elif equipment_type == "other":
            eq.other.append(details)
        else:
            return {"success": False, "error": f"Unknown equipment type: {equipment_type}"}

        self.state.mark_topic_covered("equipment")
        return {
            "success": True,
            "recorded": f"equipment.{equipment_type}",
            "message": f"Equipment ({equipment_type}) recorded."
        }

    def _record_review_of_systems(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record review of systems findings."""
        system = args.get("system", "")
        findings = args.get("findings", "")

        ros = self.state.review_of_systems

        system_map = {
            "memory": "memory_concerns",
            "mood": "mood_depression",
            "falls": "falls_history",
            "sleep": "sleep_issues",
            "pain": "pain",
            "vision": "vision_changes",
            "hearing": "hearing_changes",
            "urinary": "urinary_issues",
            "bowel": "bowel_issues",
            "appetite_weight": "appetite_weight",
        }

        attr = system_map.get(system)
        if attr:
            setattr(ros, attr, findings)
            self.state.mark_topic_covered("review_of_systems")
            return {
                "success": True,
                "recorded": f"review_of_systems.{system}",
                "message": f"Review of systems ({system}) recorded."
            }

        return {"success": False, "error": f"Unknown system: {system}"}

    def _record_medication(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record a medication."""
        med = Medication(
            name=args.get("name", ""),
            dose=args.get("dose"),
            frequency=args.get("frequency"),
            purpose=args.get("purpose"),
        )
        self.state.medications.append(med)
        self.state.mark_topic_covered("medications")

        return {
            "success": True,
            "recorded": "medication",
            "medication": med.name,
            "total_medications": len(self.state.medications),
            "message": f"Medication '{med.name}' recorded."
        }

    def _record_allergy(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record an allergy."""
        allergy = Allergy(
            allergen=args.get("allergen", ""),
            reaction=args.get("reaction"),
            severity=args.get("severity"),
        )
        self.state.allergies.append(allergy)
        self.state.mark_topic_covered("allergies")

        return {
            "success": True,
            "recorded": "allergy",
            "allergen": allergy.allergen,
            "total_allergies": len(self.state.allergies),
            "message": f"Allergy to '{allergy.allergen}' recorded."
        }

    def _record_medical_history(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record a medical history item."""
        item = MedicalHistoryItem(
            condition=args.get("condition", ""),
            year_diagnosed=args.get("year"),
            current_status=args.get("status"),
            notes=args.get("notes"),
        )
        self.state.medical_history.append(item)
        self.state.mark_topic_covered("medical_history")

        return {
            "success": True,
            "recorded": "medical_history",
            "condition": item.condition,
            "total_conditions": len(self.state.medical_history),
            "message": f"Medical history '{item.condition}' recorded."
        }

    def _flag_urgent_concern(self, args: dict[str, Any]) -> dict[str, Any]:
        """Flag an urgent clinical concern."""
        concern = UrgentConcern(
            concern_type=args.get("concern_type", ""),
            description=args.get("description", ""),
            timestamp=datetime.now(),
        )
        self.state.urgent_concerns.append(concern)

        logger.warning(f"URGENT CONCERN FLAGGED: {concern.concern_type} - {concern.description}")

        return {
            "success": True,
            "recorded": "urgent_concern",
            "concern_type": concern.concern_type,
            "message": "URGENT: Concern has been flagged for clinical review. "
                       "If this is a medical emergency, advise the patient to call 911."
        }

    def _record_speaker_info(self, args: dict[str, Any]) -> dict[str, Any]:
        """Record who is on the call."""
        speaker_type_str = args.get("speaker_type", "")

        if speaker_type_str == "patient":
            self.state.speaker_type = SpeakerType.PATIENT
        elif speaker_type_str == "caregiver":
            self.state.speaker_type = SpeakerType.CAREGIVER
        else:
            self.state.speaker_type = SpeakerType.UNKNOWN

        if args.get("patient_name"):
            self.state.patient_name = args["patient_name"]
        if args.get("caregiver_name"):
            self.state.caregiver_name = args["caregiver_name"]
        if args.get("caregiver_relationship"):
            self.state.caregiver_relationship = args["caregiver_relationship"]

        return {
            "success": True,
            "recorded": "speaker_info",
            "speaker_type": speaker_type_str,
            "message": f"Speaking with {speaker_type_str}."
        }

    def _check_coverage_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check which topics have been covered with detailed breakdown."""
        covered = list(self.state.topics_covered)
        uncovered = list(self.state.get_uncovered_topics())

        # Build detailed status for each category
        adl = self.state.adl_status
        adl_assessed = []
        adl_not_assessed = []
        for activity in ["bathing", "dressing", "eating", "ambulation", "transfers", "toileting"]:
            if getattr(adl, activity) != IndependenceLevel.NOT_ASSESSED:
                adl_assessed.append(activity)
            else:
                adl_not_assessed.append(activity)

        iadl = self.state.iadl_status
        iadl_assessed = []
        iadl_not_assessed = []
        for activity in ["shopping", "meal_preparation", "housework", "managing_finances",
                         "driving_transportation", "medication_management"]:
            if getattr(iadl, activity) != IndependenceLevel.NOT_ASSESSED:
                iadl_assessed.append(activity)
            else:
                iadl_not_assessed.append(activity)

        ros = self.state.review_of_systems
        ros_assessed = []
        ros_not_assessed = []
        for system in ["memory_concerns", "mood_depression", "falls_history", "sleep_issues", "pain"]:
            if getattr(ros, system) is not None:
                ros_assessed.append(system.replace("_", " "))
            else:
                ros_not_assessed.append(system.replace("_", " "))

        # Build message with specific guidance
        message_parts = []
        if adl_not_assessed:
            message_parts.append(f"ADLs not yet asked: {', '.join(adl_not_assessed)}")
        if iadl_not_assessed:
            message_parts.append(f"IADLs not yet asked: {', '.join(iadl_not_assessed)}")
        if ros_not_assessed:
            message_parts.append(f"Review of systems not yet asked: {', '.join(ros_not_assessed)}")

        if not message_parts:
            message = "All key items have been assessed. Ready to wrap up."
        else:
            message = "Items still to cover: " + "; ".join(message_parts)

        return {
            "success": True,
            "topics_covered": covered,
            "topics_remaining": uncovered,
            "adl_status": {
                "assessed": adl_assessed,
                "not_assessed": adl_not_assessed,
            },
            "iadl_status": {
                "assessed": iadl_assessed,
                "not_assessed": iadl_not_assessed,
            },
            "review_of_systems": {
                "assessed": ros_assessed,
                "not_assessed": ros_not_assessed,
            },
            "all_required_covered": len(uncovered) == 0,
            "all_items_assessed": not adl_not_assessed and not iadl_not_assessed and not ros_not_assessed,
            "message": message,
        }

    def _end_interview(self, args: dict[str, Any]) -> dict[str, Any]:
        """End the interview."""
        reason = args.get("reason", "completed")
        summary = args.get("summary", "")

        status_map = {
            "completed": CallStatus.COMPLETED,
            "callback_requested": CallStatus.CALLBACK_REQUESTED,
            "patient_declined": CallStatus.ABANDONED,
            "urgent_escalation": CallStatus.URGENT_ESCALATION,
            "technical_issue": CallStatus.ABANDONED,
        }

        self.state.status = status_map.get(reason, CallStatus.COMPLETED)
        self.state.ended_at = datetime.now()

        uncovered = self.state.get_uncovered_topics()

        return {
            "success": True,
            "status": self.state.status.value,
            "topics_not_covered": list(uncovered),
            "has_urgent_concerns": self.state.has_urgent_concerns(),
            "summary": summary,
            "message": f"Interview ended: {reason}."
        }


def parse_tool_arguments(arguments_str: str) -> dict[str, Any]:
    """
    Parse tool arguments from JSON string.

    Args:
        arguments_str: JSON string of arguments

    Returns:
        Parsed arguments dict
    """
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tool arguments: {e}")
        return {}

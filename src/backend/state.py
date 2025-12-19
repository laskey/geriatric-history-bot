"""
CallState dataclass for tracking all data extracted during a patient intake call.

Maps to Comprehensive Geriatric Assessment (CGA) form sections.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class CallStatus(Enum):
    """Current status of the intake call."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CALLBACK_REQUESTED = "callback_requested"
    URGENT_ESCALATION = "urgent_escalation"
    ABANDONED = "abandoned"


class SpeakerType(Enum):
    """Who is on the call."""
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    UNKNOWN = "unknown"


class IndependenceLevel(Enum):
    """Level of independence for ADL/IADL items."""
    INDEPENDENT = "independent"
    NEEDS_ASSISTANCE = "needs_assistance"
    DEPENDENT = "dependent"
    NOT_ASSESSED = "not_assessed"


@dataclass
class ADLStatus:
    """Activities of Daily Living status."""
    bathing: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    dressing: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    eating: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    ambulation: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    transfers: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    toileting: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    notes: Optional[str] = None


@dataclass
class IADLStatus:
    """Instrumental Activities of Daily Living status."""
    shopping: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    meal_preparation: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    housework: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    scheduling_appointments: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    managing_finances: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    driving_transportation: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    medication_management: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    telephone_use: IndependenceLevel = IndependenceLevel.NOT_ASSESSED
    notes: Optional[str] = None


@dataclass
class SocialHistory:
    """Social history information."""
    living_situation: Optional[str] = None  # e.g., "alone", "with spouse", "assisted living"
    home_type: Optional[str] = None  # e.g., "house", "apartment", "senior residence"
    stairs_in_home: Optional[bool] = None
    primary_caregiver: Optional[str] = None
    support_system: Optional[str] = None  # family, friends, community
    hobbies_activities: Optional[str] = None
    goals_of_care: Optional[str] = None
    tobacco_use: Optional[str] = None  # never, former, current + details
    alcohol_use: Optional[str] = None  # frequency, amount
    other_substances: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ReviewOfSystems:
    """Key geriatric review of systems screens."""
    memory_concerns: Optional[str] = None
    mood_depression: Optional[str] = None
    falls_history: Optional[str] = None  # number, circumstances, injuries
    sleep_issues: Optional[str] = None
    pain: Optional[str] = None  # location, severity, duration
    vision_changes: Optional[str] = None
    hearing_changes: Optional[str] = None
    urinary_issues: Optional[str] = None
    bowel_issues: Optional[str] = None
    appetite_weight: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class Medication:
    """Single medication entry."""
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    purpose: Optional[str] = None  # what patient thinks it's for
    notes: Optional[str] = None


@dataclass
class Allergy:
    """Single allergy entry."""
    allergen: str
    reaction: Optional[str] = None  # type of reaction
    severity: Optional[str] = None  # mild, moderate, severe


@dataclass
class MedicalHistoryItem:
    """Single medical/surgical history entry."""
    condition: str
    year_diagnosed: Optional[str] = None
    current_status: Optional[str] = None  # active, resolved, managed
    notes: Optional[str] = None


@dataclass
class Equipment:
    """Assistive equipment and home safety items."""
    gait_aid: Optional[str] = None  # cane, walker, wheelchair, none
    hearing_aids: Optional[bool] = None
    glasses: Optional[bool] = None
    grab_bars: Optional[bool] = None
    shower_chair: Optional[bool] = None
    raised_toilet_seat: Optional[bool] = None
    hospital_bed: Optional[bool] = None
    oxygen: Optional[bool] = None
    other: list[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class UrgentConcern:
    """Urgent clinical concern flagged during call."""
    concern_type: str  # e.g., "chest_pain", "fall_with_injury", "suicidal_ideation"
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    action_taken: Optional[str] = None


@dataclass
class TranscriptEntry:
    """Single turn in the conversation transcript."""
    speaker: str  # "patient", "caregiver", "assistant"
    text: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CallState:
    """
    Complete state for a single patient intake call.

    This is the central data structure that tool handlers update
    and that gets serialized to the final output.
    """
    # Call metadata
    call_id: str
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    status: CallStatus = CallStatus.IN_PROGRESS
    speaker_type: SpeakerType = SpeakerType.UNKNOWN

    # Patient identification (if provided)
    patient_name: Optional[str] = None
    patient_date_of_birth: Optional[str] = None
    caregiver_name: Optional[str] = None
    caregiver_relationship: Optional[str] = None

    # Clinical data sections
    referral_reason: Optional[str] = None
    social_history: SocialHistory = field(default_factory=SocialHistory)
    adl_status: ADLStatus = field(default_factory=ADLStatus)
    iadl_status: IADLStatus = field(default_factory=IADLStatus)
    review_of_systems: ReviewOfSystems = field(default_factory=ReviewOfSystems)
    equipment: Equipment = field(default_factory=Equipment)

    # Lists
    medications: list[Medication] = field(default_factory=list)
    allergies: list[Allergy] = field(default_factory=list)
    medical_history: list[MedicalHistoryItem] = field(default_factory=list)
    urgent_concerns: list[UrgentConcern] = field(default_factory=list)

    # Transcript
    transcript: list[TranscriptEntry] = field(default_factory=list)

    # Coverage tracking - which required topics have been addressed
    topics_covered: set[str] = field(default_factory=set)

    def mark_topic_covered(self, topic: str) -> None:
        """Mark a topic as covered in the interview."""
        self.topics_covered.add(topic)

    def get_uncovered_topics(self) -> set[str]:
        """Return set of required topics not yet covered."""
        required_topics = {
            "referral_reason",
            "social_history",
            "adl_status",
            "iadl_status",
            "review_of_systems",
        }
        return required_topics - self.topics_covered

    def has_urgent_concerns(self) -> bool:
        """Check if any urgent concerns have been flagged."""
        return len(self.urgent_concerns) > 0

    def add_transcript_entry(self, speaker: str, text: str) -> None:
        """Add an entry to the conversation transcript."""
        self.transcript.append(TranscriptEntry(speaker=speaker, text=text))

"""
DocSync Shared Models

Enums and dataclasses shared across all modules.
Extracted from the original app_main.py monolith.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


class ChangeType(Enum):
    """Classification of UI change severity"""
    NO_CHANGE = "no_change"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ValidationStatus(Enum):
    """Validation result status"""
    APPROVED = "approved"
    REVIEW = "review_needed"
    REJECTED = "rejected"


class ProcessingStatus(Enum):
    """Processing pipeline status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MatchResult:
    """Result of image matching between a new screenshot and a PDF image"""
    new_image_path: str
    new_image_name: str
    matched_pdf_image: Optional[Dict] = None
    similarity_score: float = 0.0
    histogram_score: float = 0.0
    edge_score: float = 0.0
    template_score: float = 0.0
    combined_score: float = 0.0
    is_good_match: bool = False
    target_page: Optional[int] = None
    validation_status: ValidationStatus = ValidationStatus.REVIEW
    confidence: float = 0.0
    issues: List[str] = field(default_factory=list)


@dataclass
class TextChange:
    """Represents a detected text change between old and new GUI"""
    old_text: str
    new_text: str
    page: int = 0
    confidence: float = 0.0
    context: str = ""
    approved: bool = False


@dataclass
class ProcessingResult:
    """Complete result of the document update pipeline"""
    success: bool = False
    output_path: str = ""
    images_replaced: int = 0
    text_replaced: int = 0
    matches: List[MatchResult] = field(default_factory=list)
    text_changes: List[TextChange] = field(default_factory=list)
    overall_confidence: float = 0.0
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ChangeLogEntry:
    """Single entry in the change summary log"""
    document: str = ""
    page: int = 0
    change_description: str = ""
    action: str = ""
    timestamp: str = ""
    old_version: str = ""
    new_version: str = ""
    change_type: ChangeType = ChangeType.MINOR
    confidence: float = 0.0

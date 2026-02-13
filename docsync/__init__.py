"""
DocSync - Documentation Synchronization Automation Engine
Schneider Electric Hackathon 2025-2026

A platform-agnostic tool that keeps technical documents updated
with software GUI changes through intelligent image comparison,
OCR text analysis, and automated document updating.
"""

__version__ = "4.0.0"
__author__ = "Schneider Electric Hackathon Team"

from docsync.core.gui_extractor import GUIExtractor
from docsync.core.doc_parser import DocumentParser
from docsync.core.image_comparator import ImageComparator
from docsync.core.change_analyzer import ChangeAnalyzer
from docsync.core.doc_updater import DocumentUpdater
from docsync.core.text_processor import SmartTextProcessor
from docsync.core.report_generator import ReportGenerator
from docsync.core.history_manager import HistoryManager
from docsync.core.validation_engine import ValidationEngine

__all__ = [
    "GUIExtractor",
    "DocumentParser",
    "ImageComparator",
    "ChangeAnalyzer",
    "DocumentUpdater",
    "SmartTextProcessor",
    "ReportGenerator",
    "HistoryManager",
    "ValidationEngine",
]

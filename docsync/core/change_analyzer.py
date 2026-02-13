"""
Change Analyzer Module

Takes image comparison results and localizes / describes changes.
Integrates with the Ollama LLM plugin for semantic descriptions
when available.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from docsync.models import (
    MatchResult, TextChange, ChangeType, ChangeLogEntry, ProcessingResult
)

logger = logging.getLogger("docsync.change_analyzer")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class ChangeAnalyzer:
    """
    Analyzes comparison results to produce localized, described
    change entries suitable for the change summary log.
    """

    def __init__(self, llm_plugin=None):
        """
        Args:
            llm_plugin: Optional OllamaLLMPlugin for semantic descriptions
        """
        self.llm_plugin = llm_plugin

    def classify_change(self, similarity: float) -> ChangeType:
        """Classify change severity based on similarity score"""
        if similarity >= 0.99:
            return ChangeType.NO_CHANGE
        elif similarity >= 0.90:
            return ChangeType.MINOR
        elif similarity >= 0.70:
            return ChangeType.MODERATE
        elif similarity >= 0.50:
            return ChangeType.MAJOR
        else:
            return ChangeType.CRITICAL

    def localize_changes(self, old_path: str, new_path: str) -> List[Dict]:
        """
        Detect and localize changed regions between two images.
        
        Returns a list of bounding boxes with metadata for each
        changed region.
        """
        if not CV2_AVAILABLE:
            return []

        try:
            old_img = cv2.imread(old_path)
            new_img = cv2.imread(new_path)

            if old_img is None or new_img is None:
                return []

            h, w = old_img.shape[:2]
            new_img = cv2.resize(new_img, (w, h))

            diff = cv2.absdiff(old_img, new_img)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            regions = []
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                if area > 100:
                    x, y, cw, ch = cv2.boundingRect(contour)
                    severity = "major" if area > 5000 else "minor"
                    regions.append({
                        "id": i + 1,
                        "x": int(x),
                        "y": int(y),
                        "width": int(cw),
                        "height": int(ch),
                        "area": int(area),
                        "severity": severity,
                        "location": self._describe_location(x, y, w, h),
                    })

            regions.sort(key=lambda r: r["area"], reverse=True)
            return regions

        except Exception as e:
            logger.error(f"Localization error: {e}")
            return []

    def _describe_location(self, x: int, y: int, img_w: int, img_h: int) -> str:
        """Describe the position of a changed region in human terms"""
        horizontal = "left" if x < img_w / 3 else "right" if x > 2 * img_w / 3 else "center"
        vertical = "top" if y < img_h / 3 else "bottom" if y > 2 * img_h / 3 else "middle"
        return f"{vertical}-{horizontal}"

    def describe_change(self, match: MatchResult, text_changes: List[TextChange],
                        regions: List[Dict]) -> str:
        """
        Generate a human-readable description of the change.
        Uses LLM plugin if available, otherwise falls back to
        rule-based description.
        """
        # Try LLM-based description first
        if self.llm_plugin:
            try:
                description = self.llm_plugin.describe_ui_change(
                    match, text_changes, regions
                )
                if description:
                    return description
            except Exception:
                pass

        # Rule-based fallback
        parts = []

        if not match.is_good_match:
            parts.append("No matching image found in document")
        else:
            page = match.matched_pdf_image.get("page", "?") if match.matched_pdf_image else "?"
            parts.append(f"Image on page {page} updated (confidence: {match.confidence:.0%})")

        if text_changes:
            for tc in text_changes[:3]:
                parts.append(f'"{tc.old_text}" → "{tc.new_text}"')

        if regions:
            parts.append(f"{len(regions)} UI region(s) changed")
            for r in regions[:3]:
                parts.append(f"  • {r['severity']} change at {r['location']}")

        return "; ".join(parts)

    def generate_change_log(self, result: ProcessingResult,
                            document_name: str) -> List[ChangeLogEntry]:
        """
        Generate structured change log entries from processing results.
        
        Each entry contains: what changed, where, when, old/new version refs.
        """
        entries = []
        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        for match in result.matches:
            page = match.matched_pdf_image.get("page", 0) if match.matched_pdf_image else 0

            entry = ChangeLogEntry(
                document=document_name,
                page=page,
                change_description=f"Screenshot updated: {match.new_image_name}",
                action="Image replaced" if match.is_good_match else "No match found",
                timestamp=timestamp,
                old_version=f"Page {page} original",
                new_version=match.new_image_name,
                change_type=self.classify_change(match.combined_score),
                confidence=match.confidence,
            )
            entries.append(entry)

        for tc in result.text_changes:
            entry = ChangeLogEntry(
                document=document_name,
                page=tc.page,
                change_description=f'"{tc.old_text}" → "{tc.new_text}"',
                action="Text updated" if tc.approved else "Text change (unapproved)",
                timestamp=timestamp,
                old_version=tc.old_text,
                new_version=tc.new_text,
                change_type=ChangeType.MINOR,
                confidence=tc.confidence,
            )
            entries.append(entry)

        return entries

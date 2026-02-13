"""
Validation Engine Module

Multi-check validation of image matches and text changes.
Extracted from AIValidationEngine in app_main.py.
"""

import logging
from typing import Dict, Optional, List

from docsync.models import MatchResult, TextChange, ValidationStatus

logger = logging.getLogger("docsync.validation_engine")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class ValidationEngine:
    """
    Multi-check validation engine for image matches and text changes.
    
    Performs similarity, dimension, color consistency, structure,
    and content validation to produce an overall confidence score.
    """

    def __init__(self, thresholds: Dict = None):
        default_thresholds = {
            "auto_approve": 0.85,
            "review_needed": 0.60,
            "reject": 0.40,
        }
        self.thresholds = {**default_thresholds, **(thresholds or {})}

    def validate_image_match(self, match: MatchResult, pdf_image_path: str) -> Dict:
        """
        Validate an image match through multiple checks.
        
        Checks:
            1. Similarity threshold
            2. Dimension compatibility
            3. Color consistency
            4. Structure check
            5. Content check
            
        Returns:
            Validation result with status, confidence, and issues
        """
        checks = {
            "similarity": False,
            "dimensions": False,
            "color_consistency": False,
            "structure": False,
            "content": False,
        }
        issues = []
        confidence = 0.0

        # Check 1: Similarity threshold
        if match.combined_score >= self.thresholds["review_needed"]:
            checks["similarity"] = True
        else:
            issues.append(f"Low similarity: {match.combined_score:.1%}")

        # Check 2: Dimension compatibility
        if CV2_AVAILABLE and match.new_image_path and pdf_image_path:
            try:
                new_img = cv2.imread(match.new_image_path)
                pdf_img = cv2.imread(pdf_image_path)
                if new_img is not None and pdf_img is not None:
                    h1, w1 = new_img.shape[:2]
                    h2, w2 = pdf_img.shape[:2]
                    ratio = min(w1, w2) / max(w1, w2) * min(h1, h2) / max(h1, h2)
                    if ratio > 0.3:
                        checks["dimensions"] = True
                    else:
                        issues.append(f"Dimension mismatch: {w1}x{h1} vs {w2}x{h2}")
            except Exception:
                checks["dimensions"] = True  # Skip on error

        # Check 3: Color consistency
        if CV2_AVAILABLE and match.new_image_path and pdf_image_path:
            try:
                new_img = cv2.imread(match.new_image_path)
                pdf_img = cv2.imread(pdf_image_path)
                if new_img is not None and pdf_img is not None:
                    new_mean = np.mean(new_img, axis=(0, 1))
                    pdf_mean = np.mean(pdf_img, axis=(0, 1))
                    color_diff = np.mean(np.abs(new_mean - pdf_mean))
                    if color_diff < 80:
                        checks["color_consistency"] = True
                    else:
                        issues.append(f"Color divergence: {color_diff:.0f}")
            except Exception:
                checks["color_consistency"] = True

        # Check 4: Structure (edge similarity)
        if match.edge_score > 0.3:
            checks["structure"] = True

        # Check 5: Content (histogram similarity)
        if match.histogram_score > 0.3:
            checks["content"] = True

        # Calculate overall confidence
        passed = sum(1 for v in checks.values() if v)
        confidence = (passed / len(checks)) * match.combined_score

        # Boost for high scorers
        if match.combined_score > 0.8:
            confidence = max(confidence, match.combined_score * 0.9)

        # Determine status
        if confidence >= self.thresholds["auto_approve"]:
            status = ValidationStatus.APPROVED
        elif confidence >= self.thresholds["reject"]:
            status = ValidationStatus.REVIEW
        else:
            status = ValidationStatus.REJECTED

        return {
            "status": status,
            "confidence": confidence,
            "checks": checks,
            "issues": issues,
            "recommendation": self._get_recommendation(status, issues),
        }

    def validate_text_change(self, change: TextChange) -> Dict:
        """Validate a text change for safety"""
        issues = []

        if not change.old_text.strip():
            issues.append("Empty old text")
        if not change.new_text.strip():
            issues.append("Empty new text")
        if change.old_text.strip() == change.new_text.strip():
            issues.append("No actual change")

        confidence = change.confidence

        if confidence >= self.thresholds["auto_approve"]:
            status = ValidationStatus.APPROVED
        elif confidence >= self.thresholds["reject"]:
            status = ValidationStatus.REVIEW
        else:
            status = ValidationStatus.REJECTED

        return {
            "status": status,
            "confidence": confidence,
            "issues": issues,
        }

    def _get_recommendation(self, status: ValidationStatus,
                             issues: List[str]) -> str:
        """Generate a recommendation based on validation results"""
        if status == ValidationStatus.APPROVED:
            return "Auto-approved: match is high confidence"
        elif status == ValidationStatus.REVIEW:
            return f"Review recommended: {'; '.join(issues) or 'moderate confidence'}"
        else:
            return f"Rejected: {'; '.join(issues) or 'low confidence'}"

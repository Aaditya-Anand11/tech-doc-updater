"""
Visual Analyzer Module

Creates visual comparison outputs: highlighted differences,
side-by-side comparisons.
Extracted from VisualAnalyzer in app_main.py.
"""

import logging
from typing import Optional

logger = logging.getLogger("docsync.visual_analyzer")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class VisualAnalyzer:
    """Create visual comparisons and difference highlights"""

    def create_highlight_image(self, old_path: str, new_path: str,
                                output_path: str) -> Optional[str]:
        """Create an image with highlighted differences"""
        if not CV2_AVAILABLE:
            return None

        try:
            old_img = cv2.imread(old_path)
            new_img = cv2.imread(new_path)

            if old_img is None or new_img is None:
                return None

            h, w = old_img.shape[:2]
            new_img = cv2.resize(new_img, (w, h))

            diff = cv2.absdiff(old_img, new_img)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            result = new_img.copy()

            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 100:
                    x, y, cw, ch = cv2.boundingRect(contour)
                    color = (0, 0, 255) if area > 5000 else (0, 255, 255)
                    thickness = 3 if area > 5000 else 2
                    cv2.rectangle(result, (x, y), (x + cw, y + ch), color, thickness)

            cv2.imwrite(output_path, result)
            return output_path
        except Exception:
            return None

    def create_side_by_side(self, old_path: str, new_path: str,
                             output_path: str) -> Optional[str]:
        """Create side-by-side comparison image"""
        if not CV2_AVAILABLE:
            return None

        try:
            old_img = cv2.imread(old_path)
            new_img = cv2.imread(new_path)

            if old_img is None or new_img is None:
                return None

            # Resize to same height
            h = max(old_img.shape[0], new_img.shape[0])
            old_img = cv2.resize(
                old_img, (int(old_img.shape[1] * h / old_img.shape[0]), h)
            )
            new_img = cv2.resize(
                new_img, (int(new_img.shape[1] * h / new_img.shape[0]), h)
            )

            # Add labels
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(old_img, "BEFORE", (10, 30), font, 1, (0, 0, 255), 2)
            cv2.putText(new_img, "AFTER", (10, 30), font, 1, (0, 255, 0), 2)

            # Add divider
            divider = np.ones((h, 10, 3), dtype=np.uint8) * 128

            combined = np.hstack([old_img, divider, new_img])
            cv2.imwrite(output_path, combined)
            return output_path
        except Exception:
            return None

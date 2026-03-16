"""
Visual Analyzer Module

Creates visual comparison outputs: highlighted differences,
side-by-side comparisons, and color change detection with RGB/hex.
Extracted from VisualAnalyzer in app_main.py.
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger("docsync.visual_analyzer")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex color string"""
    return f"#{r:02X}{g:02X}{b:02X}"


class VisualAnalyzer:
    """Create visual comparisons, difference highlights, and color analysis"""

    def detect_color_changes(self, old_path: str, new_path: str) -> List[Dict]:
        """
        Detect color changes between two images.
        Returns a list of changed regions with old/new RGB and hex colors.
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

            changes = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 100:
                    continue

                x, y, cw, ch = cv2.boundingRect(contour)

                # Extract mean color of the region in both images (BGR -> RGB)
                old_region = old_img[y:y+ch, x:x+cw]
                new_region = new_img[y:y+ch, x:x+cw]

                old_bgr = np.mean(old_region, axis=(0, 1))
                new_bgr = np.mean(new_region, axis=(0, 1))

                # BGR to RGB
                old_rgb = (int(old_bgr[2]), int(old_bgr[1]), int(old_bgr[0]))
                new_rgb = (int(new_bgr[2]), int(new_bgr[1]), int(new_bgr[0]))

                color_diff = float(np.mean(np.abs(old_bgr - new_bgr)))

                # Determine location on the image
                horizontal = "left" if x < w / 3 else "right" if x > 2 * w / 3 else "center"
                vertical = "top" if y < h / 3 else "bottom" if y > 2 * h / 3 else "middle"
                location = f"{vertical}-{horizontal}"

                severity = "major" if area > 5000 else "minor"

                changes.append({
                    "location": location,
                    "severity": severity,
                    "area": int(area),
                    "bbox": {"x": int(x), "y": int(y), "w": int(cw), "h": int(ch)},
                    "old_color": {
                        "rgb": old_rgb,
                        "hex": _rgb_to_hex(*old_rgb),
                    },
                    "new_color": {
                        "rgb": new_rgb,
                        "hex": _rgb_to_hex(*new_rgb),
                    },
                    "color_difference": round(color_diff, 1),
                })

            # Sort by area (largest changes first)
            changes.sort(key=lambda c: c["area"], reverse=True)
            return changes

        except Exception as e:
            logger.error(f"Color detection error: {e}")
            return []

    def get_overall_color_summary(self, old_path: str, new_path: str) -> Dict:
        """Get overall color statistics between two images"""
        if not CV2_AVAILABLE:
            return {}

        try:
            old_img = cv2.imread(old_path)
            new_img = cv2.imread(new_path)

            if old_img is None or new_img is None:
                return {}

            h, w = old_img.shape[:2]
            new_img = cv2.resize(new_img, (w, h))

            old_mean = np.mean(old_img, axis=(0, 1))  # BGR
            new_mean = np.mean(new_img, axis=(0, 1))

            old_rgb = (int(old_mean[2]), int(old_mean[1]), int(old_mean[0]))
            new_rgb = (int(new_mean[2]), int(new_mean[1]), int(new_mean[0]))

            return {
                "old_dominant_rgb": old_rgb,
                "old_dominant_hex": _rgb_to_hex(*old_rgb),
                "new_dominant_rgb": new_rgb,
                "new_dominant_hex": _rgb_to_hex(*new_rgb),
                "overall_color_shift": round(float(np.mean(np.abs(old_mean - new_mean))), 1),
            }
        except Exception:
            return {}

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

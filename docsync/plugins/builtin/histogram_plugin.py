"""
Histogram Plugin – Color histogram comparison
"""

import logging
from typing import Dict, Any

from docsync.plugins.plugin_base import PluginBase

logger = logging.getLogger("docsync.plugins.histogram")

try:
    import cv2
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


class HistogramPlugin(PluginBase):
    name = "histogram"
    version = "1.0.0"
    description = "Color histogram correlation comparison"

    def initialize(self, config: Dict) -> bool:
        return AVAILABLE

    def execute(self, img1_path: str = "", img2_path: str = "", **kwargs) -> Any:
        if not AVAILABLE:
            return {"score": 0.0, "error": "OpenCV not available"}
        try:
            img1 = cv2.imread(img1_path)
            img2 = cv2.imread(img2_path)
            if img1 is None or img2 is None:
                return {"score": 0.0, "error": "Could not read images"}
            hist1 = cv2.calcHist([img1], [0, 1, 2], None, [8, 8, 8],
                                  [0, 256, 0, 256, 0, 256])
            hist2 = cv2.calcHist([img2], [0, 1, 2], None, [8, 8, 8],
                                  [0, 256, 0, 256, 0, 256])
            cv2.normalize(hist1, hist1)
            cv2.normalize(hist2, hist2)
            score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            return {"score": max(0, float(score))}
        except Exception as e:
            return {"score": 0.0, "error": str(e)}

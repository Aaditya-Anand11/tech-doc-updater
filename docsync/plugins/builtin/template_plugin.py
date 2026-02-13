"""
Template Plugin – OpenCV template matching
"""

import logging
from typing import Dict, Any

from docsync.plugins.plugin_base import PluginBase

logger = logging.getLogger("docsync.plugins.template")

try:
    import cv2
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


class TemplatePlugin(PluginBase):
    name = "template"
    version = "1.0.0"
    description = "Template matching image comparison"

    def initialize(self, config: Dict) -> bool:
        return AVAILABLE

    def execute(self, img1_path: str = "", img2_path: str = "", **kwargs) -> Any:
        if not AVAILABLE:
            return {"score": 0.0, "error": "OpenCV not available"}
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            if img1 is None or img2 is None:
                return {"score": 0.0, "error": "Could not read images"}
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
            result = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return {"score": max(0, float(max_val))}
        except Exception as e:
            return {"score": 0.0, "error": str(e)}

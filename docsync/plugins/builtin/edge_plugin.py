"""
Edge Plugin – Edge structure comparison using Canny + SSIM
"""

import logging
from typing import Dict, Any

from docsync.plugins.plugin_base import PluginBase

logger = logging.getLogger("docsync.plugins.edge")

try:
    import cv2
    from skimage.metrics import structural_similarity as ssim
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


class EdgePlugin(PluginBase):
    name = "edge"
    version = "1.0.0"
    description = "Edge structure comparison using Canny edge detection"

    def initialize(self, config: Dict) -> bool:
        return AVAILABLE

    def execute(self, img1_path: str = "", img2_path: str = "", **kwargs) -> Any:
        if not AVAILABLE:
            return {"score": 0.0, "error": "Dependencies missing"}
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            if img1 is None or img2 is None:
                return {"score": 0.0, "error": "Could not read images"}
            size = (256, 256)
            img1 = cv2.resize(img1, size)
            img2 = cv2.resize(img2, size)
            edges1 = cv2.Canny(img1, 50, 150)
            edges2 = cv2.Canny(img2, 50, 150)
            score, _ = ssim(edges1, edges2, full=True)
            return {"score": max(0, float(score))}
        except Exception as e:
            return {"score": 0.0, "error": str(e)}

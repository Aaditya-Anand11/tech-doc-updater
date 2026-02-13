"""
SSIM Plugin – Structural Similarity comparison
"""

import logging
from typing import Dict, Any

from docsync.plugins.plugin_base import PluginBase

logger = logging.getLogger("docsync.plugins.ssim")

try:
    import cv2
    from skimage.metrics import structural_similarity as ssim
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


class SSIMPlugin(PluginBase):
    name = "ssim"
    version = "1.0.0"
    description = "Structural Similarity Index image comparison"

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
            score, _ = ssim(img1, img2, full=True)
            return {"score": max(0, float(score))}
        except Exception as e:
            return {"score": 0.0, "error": str(e)}

    def health_check(self) -> Dict:
        return {"name": self.name, "status": "ok" if AVAILABLE else "unavailable",
                "version": self.version}

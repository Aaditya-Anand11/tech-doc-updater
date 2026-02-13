"""
Perceptual Hash Plugin – dHash similarity
"""

import logging
from typing import Dict, Any

from docsync.plugins.plugin_base import PluginBase

logger = logging.getLogger("docsync.plugins.phash")

try:
    from PIL import Image
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


class PerceptualHashPlugin(PluginBase):
    name = "phash"
    version = "1.0.0"
    description = "Perceptual hash (dHash) image similarity"

    def initialize(self, config: Dict) -> bool:
        return AVAILABLE

    def execute(self, img1_path: str = "", img2_path: str = "", **kwargs) -> Any:
        if not AVAILABLE:
            return {"score": 0.0, "error": "Pillow not available"}
        try:
            hash_size = kwargs.get("hash_size", 8)

            def dhash(image_path):
                img = Image.open(image_path).convert('L')
                img = img.resize((hash_size + 1, hash_size), Image.LANCZOS)
                pixels = list(img.getdata())
                diff = []
                for row in range(hash_size):
                    for col in range(hash_size):
                        left = pixels[row * (hash_size + 1) + col]
                        right = pixels[row * (hash_size + 1) + col + 1]
                        diff.append(1 if left > right else 0)
                return diff

            hash1 = dhash(img1_path)
            hash2 = dhash(img2_path)
            distance = sum(h1 != h2 for h1, h2 in zip(hash1, hash2))
            score = 1 - (distance / len(hash1))
            return {"score": score}
        except Exception as e:
            return {"score": 0.0, "error": str(e)}

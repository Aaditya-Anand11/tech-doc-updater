"""
GUI Extractor Module

Handles GUI screenshot extraction and validation.
Platform-agnostic: accepts file paths, validates images,
and supports batch extraction.
"""

import os
import logging
from typing import List, Optional, Dict

logger = logging.getLogger("docsync.gui_extractor")

# Optional imports
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class GUIExtractor:
    """
    Extracts and validates GUI screenshots from file paths.
    
    Platform-agnostic design: works with any image file from
    Windows, Linux, Web, or embedded interface screenshots.
    """

    SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}

    def __init__(self):
        self.extracted_images: List[Dict] = []

    def validate_image(self, image_path: str) -> Dict:
        """Validate that a file is a usable GUI screenshot"""
        result = {
            "path": image_path,
            "valid": False,
            "width": 0,
            "height": 0,
            "format": "",
            "size_kb": 0,
            "error": None,
        }

        if not os.path.exists(image_path):
            result["error"] = f"File not found: {image_path}"
            return result

        ext = os.path.splitext(image_path)[1].lower()
        if ext not in self.SUPPORTED_FORMATS:
            result["error"] = f"Unsupported format: {ext}"
            return result

        result["format"] = ext
        result["size_kb"] = round(os.path.getsize(image_path) / 1024, 2)

        if PIL_AVAILABLE:
            try:
                img = Image.open(image_path)
                result["width"] = img.width
                result["height"] = img.height
                result["valid"] = True
                img.close()
            except Exception as e:
                result["error"] = f"Cannot open image: {e}"
        elif CV2_AVAILABLE:
            try:
                img = cv2.imread(image_path)
                if img is not None:
                    result["height"], result["width"] = img.shape[:2]
                    result["valid"] = True
                else:
                    result["error"] = "OpenCV could not read the image"
            except Exception as e:
                result["error"] = f"Cannot open image: {e}"
        else:
            # No image library available, just check file exists
            result["valid"] = True
            result["error"] = "No image library available for full validation"

        return result

    def extract(self, image_paths: List[str]) -> List[Dict]:
        """
        Extract and validate a batch of GUI screenshots.
        
        Args:
            image_paths: List of file paths to GUI screenshots
            
        Returns:
            List of validated image info dictionaries
        """
        self.extracted_images = []

        for path in image_paths:
            if path is None:
                continue

            # Handle Gradio file objects
            actual_path = path if isinstance(path, str) else getattr(path, 'name', str(path))

            info = self.validate_image(actual_path)
            if info["valid"]:
                logger.info(f"Valid screenshot: {os.path.basename(actual_path)} "
                           f"({info['width']}x{info['height']})")
                self.extracted_images.append(info)
            else:
                logger.warning(f"Invalid screenshot: {actual_path} - {info['error']}")

        logger.info(f"Extracted {len(self.extracted_images)} valid GUI screenshots")
        return self.extracted_images

    def get_paths(self) -> List[str]:
        """Get list of validated image file paths"""
        return [img["path"] for img in self.extracted_images]

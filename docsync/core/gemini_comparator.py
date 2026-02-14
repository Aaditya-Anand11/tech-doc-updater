"""
Gemini Image Comparator

Uses Google Gemini's vision capabilities to compare two images
and return a similarity score with explanation.
"""

import os
import base64
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger("docsync.gemini_comparator")

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.info("google-genai not installed. Gemini comparison disabled.")


class GeminiComparator:
    """
    AI-powered image comparison using Google Gemini.

    Sends two images to Gemini and asks it to rate their similarity
    on a 0-100 scale, plus a brief explanation of differences.
    """

    def __init__(self, api_key: str = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("DOCSYNC_GEMINI_KEY", "")
        self.model = model
        self.client = None

        if GENAI_AVAILABLE and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini comparator initialized (model: {self.model})")
            except Exception as e:
                logger.warning(f"Could not init Gemini client: {e}")

    @property
    def is_available(self) -> bool:
        return GENAI_AVAILABLE and self.client is not None

    def _load_image_bytes(self, path: str) -> Optional[bytes]:
        """Load image file as bytes."""
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not read image {path}: {e}")
            return None

    def _guess_mime(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }
        return mime_map.get(ext, "image/png")

    def compare_images(self, img1_path: str, img2_path: str) -> Dict:
        """
        Compare two images using Gemini vision.

        Returns:
            {
                "score": float (0.0 to 1.0),
                "explanation": str,
                "success": bool
            }
        """
        if not self.is_available:
            return {"score": 0.0, "explanation": "Gemini not available", "success": False}

        img1_bytes = self._load_image_bytes(img1_path)
        img2_bytes = self._load_image_bytes(img2_path)

        if not img1_bytes or not img2_bytes:
            return {"score": 0.0, "explanation": "Could not load images", "success": False}

        prompt = (
            "You are comparing two images. Image 1 is a new GUI screenshot. "
            "Image 2 is an image extracted from a PDF document.\n\n"
            "Determine if these two images show the SAME screen/interface/component, "
            "even if there are minor visual differences (colors, text updates, layout tweaks).\n\n"
            "Respond ONLY with valid JSON in this exact format:\n"
            '{"score": <0-100>, "explanation": "<one short sentence>"}\n\n'
            "Score guide:\n"
            "90-100: Same screen, nearly identical\n"
            "70-89: Same screen with noticeable changes\n"
            "40-69: Possibly related but significantly different\n"
            "0-39: Completely different screens\n"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=img1_bytes, mime_type=self._guess_mime(img1_path)),
                    types.Part.from_bytes(data=img2_bytes, mime_type=self._guess_mime(img2_path)),
                ],
            )

            text = response.text.strip()

            # Parse JSON from response (handle markdown code blocks)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            result = json.loads(text)
            score = max(0, min(100, float(result.get("score", 0)))) / 100.0
            explanation = result.get("explanation", "")

            logger.info(f"Gemini score: {score:.2f} — {explanation}")
            return {"score": score, "explanation": explanation, "success": True}

        except json.JSONDecodeError as e:
            logger.warning(f"Gemini returned non-JSON: {e}")
            return {"score": 0.0, "explanation": "Could not parse AI response", "success": False}
        except Exception as e:
            logger.warning(f"Gemini comparison error: {e}")
            return {"score": 0.0, "explanation": str(e), "success": False}

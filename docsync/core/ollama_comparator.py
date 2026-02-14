"""
Ollama Vision Image Comparator

Uses Ollama's vision models (llava, bakllava, etc.) to compare
two images and return a similarity score with explanation.
"""

import os
import base64
import json
import logging
import requests
from typing import Dict

logger = logging.getLogger("docsync.ollama_comparator")


class OllamaComparator:
    """
    AI-powered image comparison using Ollama vision models.

    Sends two images to a local Ollama instance and asks it to rate
    their similarity on a 0-100 scale with a brief explanation.
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llava"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._available = None

    @property
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if r.ok:
                models = [m["name"].split(":")[0] for m in r.json().get("models", [])]
                self._available = self.model.split(":")[0] in models
                if not self._available:
                    logger.warning(f"Ollama model '{self.model}' not found. "
                                   f"Available: {models}. Run: ollama pull {self.model}")
            else:
                self._available = False
        except Exception:
            self._available = False
            logger.info("Ollama not reachable")
        return self._available

    def _encode_image(self, path: str) -> str:
        """Load image and return base64 string."""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def compare_images(self, img1_path: str, img2_path: str) -> Dict:
        """
        Compare two images using Ollama vision model.

        Returns:
            {"score": float (0.0-1.0), "explanation": str, "success": bool}
        """
        if not self.is_available:
            return {"score": 0.0, "explanation": "Ollama not available", "success": False}

        try:
            img1_b64 = self._encode_image(img1_path)
            img2_b64 = self._encode_image(img2_path)
        except Exception as e:
            return {"score": 0.0, "explanation": f"Could not load images: {e}", "success": False}

        prompt = (
            "You are comparing two images. Image 1 is a new GUI screenshot. "
            "Image 2 is an image extracted from a PDF document.\n\n"
            "Determine if these two images show the SAME screen/interface/component, "
            "even if there are minor visual differences.\n\n"
            "Respond ONLY with valid JSON in this exact format:\n"
            '{"score": <0-100>, "explanation": "<one short sentence>"}\n\n'
            "Score guide:\n"
            "90-100: Same screen, nearly identical\n"
            "70-89: Same screen with noticeable changes\n"
            "40-69: Possibly related but significantly different\n"
            "0-39: Completely different screens\n"
            "Respond ONLY with the JSON, nothing else."
        )

        try:
            r = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [img1_b64, img2_b64],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=600,
            )
            r.raise_for_status()
            text = r.json().get("response", "").strip()

            # Parse JSON from response
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            # Try to find JSON in the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            result = json.loads(text)
            score = max(0, min(100, float(result.get("score", 0)))) / 100.0
            explanation = result.get("explanation", "")

            logger.info(f"Ollama score: {score:.2f} — {explanation}")
            return {"score": score, "explanation": explanation, "success": True}

        except json.JSONDecodeError:
            logger.warning(f"Ollama returned non-JSON response")
            return {"score": 0.0, "explanation": "Could not parse AI response", "success": False}
        except requests.Timeout:
            logger.warning("Ollama request timed out")
            return {"score": 0.0, "explanation": "Request timed out", "success": False}
        except Exception as e:
            logger.warning(f"Ollama comparison error: {e}")
            return {"score": 0.0, "explanation": str(e), "success": False}

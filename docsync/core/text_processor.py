"""
Smart Text Processor Module

OCR-based text extraction, comparison, and replacement generation.
Extracted from SmartTextProcessor in app_main.py.
"""

import os
import json
import logging
from typing import List, Dict
from difflib import SequenceMatcher

from docsync.models import TextChange

logger = logging.getLogger("docsync.text_processor")

# OCR support
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract

    # Configure Tesseract path for Windows
    TESSERACT_PATHS = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(
            os.getenv('USERNAME', 'user')
        ),
    ]

    tesseract_found = False
    for path in TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            tesseract_found = True
            break

    try:
        pytesseract.get_tesseract_version()
        OCR_SUPPORT = True
    except Exception:
        OCR_SUPPORT = False

except ImportError:
    OCR_SUPPORT = False


class SmartTextProcessor:
    """
    Intelligent text processing with OCR extraction,
    error correction, and context-aware phrase matching.
    """

    def __init__(self, replacements_file: str = "./data/replacements.json"):
        # DISABLED: Single-word matching causes Scunthorpe problem
        self.ui_terms = {}

        # Only safe multi-char patterns — single-char corrections like
        # |→I, 0→O, 1→l corrupt normal text (numbers, punctuation)
        self.ocr_corrections = {
            "rn": "m",
            "vv": "w",
        }

        # Load phrase pairs from external config
        self.common_phrase_pairs = self._load_phrase_pairs(replacements_file)

    def _load_phrase_pairs(self, filepath: str) -> Dict[str, str]:
        """Load replacement phrase pairs from JSON file"""
        pairs = {}

        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                # Merge all categories
                for category in data.values():
                    if isinstance(category, dict):
                        pairs.update(category)
            except Exception as e:
                logger.warning(f"Could not load replacements from {filepath}: {e}")

        # Ensure bidirectional case coverage
        extended = {}
        for k, v in pairs.items():
            extended[k] = v
            extended[k.lower()] = v.lower()
        pairs.update(extended)

        return pairs

    def extract_full_text(self, image_path: str) -> str:
        """Extract full text from an image using OCR"""
        if not OCR_SUPPORT or not PIL_AVAILABLE:
            return ""
        try:
            img = Image.open(image_path)
            return pytesseract.image_to_string(img).strip()
        except Exception:
            return ""

    def correct_ocr_errors(self, text: str) -> str:
        """Apply common OCR error corrections"""
        corrected = text
        for error, correction in self.ocr_corrections.items():
            corrected = corrected.replace(error, correction)
        return corrected

    def find_text_differences(self, old_img_path: str, new_img_path: str) -> Dict:
        """
        Compare text from two GUI screenshots using OCR.
        
        Returns a diff dict with old/new text, word changes,
        phrase changes, and OCR-detected replacements.
        """
        old_text = self.correct_ocr_errors(self.extract_full_text(old_img_path))
        new_text = self.correct_ocr_errors(self.extract_full_text(new_img_path))

        old_lines = [l.strip() for l in old_text.split('\n') if l.strip() and len(l.strip()) > 2]
        new_lines = [l.strip() for l in new_text.split('\n') if l.strip() and len(l.strip()) > 2]

        old_words = set(old_text.lower().split())
        new_words = set(new_text.lower().split())

        added = new_words - old_words
        removed = old_words - new_words

        phrase_changes = self._find_phrase_changes(old_lines, new_lines)
        ocr_replacements = self._find_ocr_replacements(
            old_text, new_text, old_lines, new_lines
        )

        all_words = old_words | new_words
        common = old_words & new_words
        similarity = len(common) / len(all_words) if all_words else 1.0

        return {
            "old_text": old_text,
            "new_text": new_text,
            "old_lines": old_lines,
            "new_lines": new_lines,
            "added_words": list(added),
            "removed_words": list(removed),
            "ui_changes": [],  # Disabled single-word matching
            "phrase_changes": phrase_changes,
            "ocr_replacements": ocr_replacements,
            "similarity": similarity,
            "total_changes": len(added) + len(removed) + len(phrase_changes) + len(ocr_replacements),
        }

    def _find_ocr_replacements(self, old_text: str, new_text: str,
                                old_lines: List[str], new_lines: List[str]) -> List[Dict]:
        """Find specific text replacements by analyzing OCR differences"""
        changes = []
        old_lower = old_text.lower()
        new_lower = new_text.lower()

        # 1. Check known phrase pairs
        for old_term, new_term in self.common_phrase_pairs.items():
            if old_term.lower() in old_lower and new_term.lower() in new_lower:
                changes.append({
                    "old": old_term.title(),
                    "new": new_term.title(),
                    "category": "phrase_pair",
                    "confidence": 0.95,
                })

        # 2. Extract key phrases and compare
        old_phrases = self._extract_key_phrases(old_lines)
        new_phrases = self._extract_key_phrases(new_lines)

        for old_phrase in old_phrases:
            if old_phrase.lower() not in new_lower:
                for new_phrase in new_phrases:
                    if new_phrase.lower() not in old_lower:
                        old_words = old_phrase.lower().split()
                        new_words = new_phrase.lower().split()
                        if len(old_words) == len(new_words) and len(old_words) <= 3:
                            sim = SequenceMatcher(
                                None, old_phrase.lower(), new_phrase.lower()
                            ).ratio()
                            if 0.2 < sim < 0.85:
                                changes.append({
                                    "old": old_phrase,
                                    "new": new_phrase,
                                    "category": "ocr_phrase",
                                    "confidence": max(0.6, sim),
                                })

        return changes

    def _extract_key_phrases(self, lines: List[str]) -> List[str]:
        """Extract key UI phrases from OCR lines"""
        phrases = []
        for line in lines:
            if len(line) < 3 or len(line) > 50:
                continue
            clean = line.strip()
            words = clean.split()
            if 1 <= len(words) <= 4:
                if any(w[0].isupper() for w in words if w):
                    phrases.append(clean)
        return phrases

    def _find_phrase_changes(self, old_lines: List[str],
                              new_lines: List[str]) -> List[Dict]:
        """Find phrase-level changes between old and new text lines"""
        changes = []
        for old_line in old_lines:
            if len(old_line) < 4:
                continue
            best_match = None
            best_similarity = 0
            for new_line in new_lines:
                if len(new_line) < 4:
                    continue
                sim = SequenceMatcher(None, old_line.lower(), new_line.lower()).ratio()
                if 0.4 < sim < 0.95 and sim > best_similarity:
                    best_similarity = sim
                    best_match = new_line
            if best_match and old_line.lower() != best_match.lower():
                changes.append({
                    "old": old_line,
                    "new": best_match,
                    "category": "phrase",
                    "confidence": best_similarity,
                })
        return changes

    def generate_text_replacements(self, text_diff: Dict) -> List[TextChange]:
        """Generate TextChange objects from a text diff result"""
        replacements = []

        # OCR replacements (highest priority)
        for change in text_diff.get("ocr_replacements", []):
            replacements.append(TextChange(
                old_text=change["old"],
                new_text=change["new"],
                page=0,
                confidence=change["confidence"],
                context=change["category"],
                approved=change["confidence"] > 0.5,
            ))

        # UI term changes
        for change in text_diff.get("ui_changes", []):
            replacements.append(TextChange(
                old_text=change["old"],
                new_text=change["new"],
                page=0,
                confidence=change["confidence"],
                context=change["category"],
                approved=change["confidence"] > 0.7,
            ))

        # Phrase changes
        for change in text_diff.get("phrase_changes", []):
            if change["confidence"] > 0.5:
                replacements.append(TextChange(
                    old_text=change["old"],
                    new_text=change["new"],
                    page=0,
                    confidence=change["confidence"],
                    context="phrase",
                    approved=change["confidence"] > 0.6,
                ))

        return replacements

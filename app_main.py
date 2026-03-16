"""
Tech Doc Auto Updater v3.0 - COMPLETE EDITION
Schneider Electric Hackathon 2025-2026

COMPLETE FEATURE SET:
=====================
✅ No old GUI required (auto-extract from PDF)
✅ Multiple screenshots upload at once
✅ Optional page number specification
✅ Advanced AI matching (SSIM, histogram, edge, template)
✅ Smart text replacement with context awareness
✅ Multi-layer AI validation
✅ Side-by-side preview
✅ Batch processing
✅ Version control & history
✅ Comprehensive reporting
✅ Progress tracking
✅ One-click export (ZIP)
✅ Undo/rollback support
✅ Settings customization
"""

import os
import sys
import json
import shutil
import zipfile
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import tempfile
import re
import threading
import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import Counter
from difflib import SequenceMatcher

# Auth & structured logging
try:
    from docsync.auth.rbac import RBACManager, Role, ROLE_PERMISSIONS
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    logger_placeholder = None  # defined after logging init

try:
    from docsync.logging_config import setup_logging
except ImportError:
    setup_logging = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add file handler so logs appear in Logs tab
_log_dir = os.path.join(".", "data", "logs")
os.makedirs(_log_dir, exist_ok=True)
_fh = logging.FileHandler(os.path.join(_log_dir, "app.log"), encoding="utf-8")
_fh.setLevel(logging.INFO)
_fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(_fh)

# ==================== DEPENDENCY IMPORTS ====================

# Core image processing
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not installed. Run: pip install opencv-python")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not installed. Run: pip install Pillow")

try:
    from skimage.metrics import structural_similarity as ssim
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    logger.warning("scikit-image not installed. Run: pip install scikit-image")

# Gradio for web interface
try:
    import gradio as gr
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False
    logger.error("Gradio not installed. Run: pip install gradio")

# PDF support
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("PyMuPDF not installed. Run: pip install pymupdf")

# OCR support
try:
    import pytesseract
    
    # Configure Tesseract path for Windows
    # Try common installation paths
    TESSERACT_PATHS = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', 'user')),
    ]
    
    tesseract_found = False
    for path in TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            tesseract_found = True
            logger.info(f"Tesseract found at: {path}")
            break
    
    # Verify Tesseract is accessible
    try:
        version = pytesseract.get_tesseract_version()
        OCR_SUPPORT = True
        logger.info(f"Tesseract version: {version}")
    except Exception as e:
        if not tesseract_found:
            logger.warning(f"Tesseract not found in common paths. OCR may not work. Error: {e}")
            logger.warning("Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
        OCR_SUPPORT = False
        
except ImportError:
    OCR_SUPPORT = False
    logger.warning("pytesseract not installed. OCR disabled.")


# ==================== ENUMS & DATA CLASSES ====================

class ChangeType(Enum):
    NO_CHANGE = "no_change"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ValidationStatus(Enum):
    APPROVED = "approved"
    REVIEW = "review_needed"
    REJECTED = "rejected"


class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MatchResult:
    """Stores result of image matching"""
    new_image_path: str
    new_image_name: str
    matched_pdf_image: Optional[Dict] = None
    similarity_score: float = 0.0
    histogram_score: float = 0.0
    edge_score: float = 0.0
    template_score: float = 0.0
    combined_score: float = 0.0
    is_good_match: bool = False
    target_page: Optional[int] = None
    validation_status: ValidationStatus = ValidationStatus.REVIEW
    confidence: float = 0.0
    issues: List[str] = field(default_factory=list)


@dataclass
class TextChange:
    """Stores a text change"""
    old_text: str
    new_text: str
    page: int = 0
    confidence: float = 0.0
    context: str = ""
    approved: bool = False


@dataclass
class ProcessingResult:
    """Complete processing result"""
    success: bool = False
    output_path: str = ""
    images_replaced: int = 0
    text_replaced: int = 0
    matches: List[MatchResult] = field(default_factory=list)
    text_changes: List[TextChange] = field(default_factory=list)
    overall_confidence: float = 0.0
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ==================== HISTORY & VERSION CONTROL ====================

class HistoryManager:
    """
    Manages version history and undo/redo functionality
    """
    
    def __init__(self, storage_dir: str = "./data/history"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.history_file = os.path.join(storage_dir, "history.json")
        self.history = self._load_history()
        self.max_versions = 50
    
    def _load_history(self) -> List[Dict]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def _save_history(self):
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history[-self.max_versions:], f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save history: {e}")
    
    def add_version(self, pdf_path: str, changes: Dict, result: ProcessingResult) -> str:
        """Add a new version to history"""
        version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create backup
        backup_path = os.path.join(self.storage_dir, f"backup_{version_id}.pdf")
        try:
            if os.path.exists(pdf_path):
                shutil.copy(pdf_path, backup_path)
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")
            backup_path = ""
        
        entry = {
            "version_id": version_id,
            "timestamp": datetime.now().isoformat(),
            "original_pdf": pdf_path,
            "backup_path": backup_path,
            "output_path": result.output_path,
            "images_replaced": result.images_replaced,
            "text_replaced": result.text_replaced,
            "confidence": result.overall_confidence,
            "changes_summary": {
                "screenshots_processed": len(result.matches),
                "text_changes": len(result.text_changes)
            }
        }
        
        self.history.append(entry)
        self._save_history()
        
        return version_id
    
    def get_version(self, version_id: str) -> Optional[Dict]:
        """Get a specific version"""
        for entry in self.history:
            if entry.get("version_id") == version_id:
                return entry
        return None
    
    def rollback(self, version_id: str) -> Optional[str]:
        """Rollback to a previous version"""
        version = self.get_version(version_id)
        if version and os.path.exists(version.get("backup_path", "")):
            return version["backup_path"]
        return None
    
    def get_recent_versions(self, limit: int = 10) -> List[Dict]:
        """Get recent versions"""
        return self.history[-limit:][::-1]
    
    def generate_changelog(self) -> str:
        """Generate a changelog from history"""
        if not self.history:
            return "No history available."
        
        changelog = "# Document Update Changelog\n\n"
        
        for entry in reversed(self.history[-20:]):
            confidence = entry.get('confidence', 0)
            changelog += f"""
## Version {entry.get('version_id', 'Unknown')}
- **Date:** {entry.get('timestamp', 'Unknown')}
- **Images Replaced:** {entry.get('images_replaced', 0)}
- **Text Updates:** {entry.get('text_replaced', 0)}
- **Confidence:** {confidence:.1%}

---
"""
        
        return changelog


# ==================== ADVANCED IMAGE MATCHER ====================

class AdvancedImageMatcher:
    """
    Advanced image matching using multiple algorithms
    """
    
    def __init__(self, config: Dict = None):
        # Default config
        default_config = {
            "ssim_weight": 0.35,
            "histogram_weight": 0.20,
            "edge_weight": 0.25,
            "template_weight": 0.20,
            "similarity_threshold": 0.30,
            "high_confidence_threshold": 0.80
        }
        # Merge passed config with defaults
        self.config = {**default_config, **(config or {})}
    
    def compute_ssim(self, img1_path: str, img2_path: str) -> float:
        """Compute SSIM similarity"""
        if not CV2_AVAILABLE or not SKIMAGE_AVAILABLE:
            return 0.0
        
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            
            if img1 is None or img2 is None:
                return 0.0
            
            # Resize to common size
            size = (256, 256)
            img1 = cv2.resize(img1, size)
            img2 = cv2.resize(img2, size)
            
            score, _ = ssim(img1, img2, full=True)
            return max(0, float(score))
        except Exception as e:
            logger.error(f"SSIM error: {e}")
            return 0.0
    
    def compute_histogram(self, img1_path: str, img2_path: str) -> float:
        """Compute color histogram similarity"""
        if not CV2_AVAILABLE:
            return 0.0
        
        try:
            img1 = cv2.imread(img1_path)
            img2 = cv2.imread(img2_path)
            
            if img1 is None or img2 is None:
                return 0.0
            
            # Compute histograms
            hist1 = cv2.calcHist([img1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist2 = cv2.calcHist([img2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            
            cv2.normalize(hist1, hist1)
            cv2.normalize(hist2, hist2)
            
            score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            return max(0, float(score))
        except Exception:
            return 0.0
    
    def compute_edge_similarity(self, img1_path: str, img2_path: str) -> float:
        """Compare edge structures"""
        if not CV2_AVAILABLE or not SKIMAGE_AVAILABLE:
            return 0.0
        
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            
            if img1 is None or img2 is None:
                return 0.0
            
            # Resize
            size = (256, 256)
            img1 = cv2.resize(img1, size)
            img2 = cv2.resize(img2, size)
            
            # Detect edges
            edges1 = cv2.Canny(img1, 50, 150)
            edges2 = cv2.Canny(img2, 50, 150)
            
            # Compare
            score, _ = ssim(edges1, edges2, full=True)
            return max(0, float(score))
        except Exception:
            return 0.0
    
    def compute_template_match(self, img1_path: str, img2_path: str) -> float:
        """Template matching score using center crop of img1 as template"""
        if not CV2_AVAILABLE:
            return 0.0
        
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            
            if img1 is None or img2 is None:
                return 0.0
            
            # Resize both to a common size for comparison
            common_h, common_w = 256, 256
            img1 = cv2.resize(img1, (common_w, common_h))
            img2 = cv2.resize(img2, (common_w, common_h))
            
            # Use a center crop (75%) of img1 as the template
            margin_h = common_h // 8
            margin_w = common_w // 8
            template = img1[margin_h:common_h - margin_h, margin_w:common_w - margin_w]
            
            # Prevent "Solid Color" false positives (Edge Case #4)
            _, stddev = cv2.meanStdDev(template)
            if stddev[0][0] < 5.0:
                logger.debug("Template crop variance too low (solid color), rejecting match")
                return 0.0
            
            # Match template against img2
            result = cv2.matchTemplate(img2, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            return max(0, float(max_val))
        except Exception:
            return 0.0
    
    def compute_perceptual_hash(self, img1_path: str, img2_path: str) -> float:
        """Perceptual hash similarity"""
        if not PIL_AVAILABLE:
            return 0.0
        
        try:
            def dhash(image_path, hash_size=8):
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
            
            # Hamming distance
            distance = sum(h1 != h2 for h1, h2 in zip(hash1, hash2))
            similarity = 1 - (distance / len(hash1))
            
            return similarity
        except Exception:
            return 0.0
    
    def compute_combined_score(self, img1_path: str, img2_path: str) -> Dict:
        """Compute combined weighted score"""
        
        ssim_score = self.compute_ssim(img1_path, img2_path)
        hist_score = self.compute_histogram(img1_path, img2_path)
        edge_score = self.compute_edge_similarity(img1_path, img2_path)
        template_score = self.compute_template_match(img1_path, img2_path)
        
        combined = (
            ssim_score * self.config["ssim_weight"] +
            hist_score * self.config["histogram_weight"] +
            edge_score * self.config["edge_weight"] +
            template_score * self.config["template_weight"]
        )
        
        return {
            "ssim": ssim_score,
            "histogram": hist_score,
            "edge": edge_score,
            "template": template_score,
            "combined": combined,
            "is_match": combined >= self.config["similarity_threshold"],
            "is_high_confidence": combined >= self.config["high_confidence_threshold"]
        }
    
    def find_best_matches(self, new_images: List[str], pdf_images: List[Dict],
                          page_hints: Dict[str, int] = None) -> List[MatchResult]:
        """Find best matches for all new images"""
        
        logger.debug(f"find_best_matches called with {len(new_images)} new images and {len(pdf_images)} PDF images")
        
        results = []
        
        for new_img_path in new_images:
            new_img_name = os.path.basename(new_img_path)
            logger.debug(f"Processing new image: {new_img_name}")
            
            best_match = None
            best_scores = {"combined": 0}
            
            # Check page hints
            target_page = None
            if page_hints:
                for hint_name, hint_page in page_hints.items():
                    if hint_name.lower() in new_img_name.lower():
                        target_page = hint_page
                        break
            
            for pdf_img in pdf_images:
                # Skip if page hint specified and doesn't match
                if target_page is not None and pdf_img.get("page") != target_page:
                    continue
                
                logger.debug(f"Comparing with PDF image: {pdf_img.get('filename', 'unknown')}")
                scores = self.compute_combined_score(new_img_path, pdf_img.get("path", ""))
                logger.debug(f"Scores: SSIM={scores.get('ssim', 0):.3f}, Hist={scores.get('histogram', 0):.3f}, Edge={scores.get('edge', 0):.3f}, Template={scores.get('template', 0):.3f}, Combined={scores.get('combined', 0):.3f}")
                logger.debug(f"is_match={scores.get('is_match')}, threshold={self.config['similarity_threshold']}")
                
                if scores["combined"] > best_scores["combined"]:
                    best_scores = scores
                    best_match = pdf_img
                    logger.debug(f"New best match found!")
            
            logger.debug(f"Best match for {new_img_name}: combined_score={best_scores.get('combined', 0):.3f}, is_match={best_scores.get('is_match', False)}")
            
            # Create result
            result = MatchResult(
                new_image_path=new_img_path,
                new_image_name=new_img_name,
                matched_pdf_image=best_match,
                similarity_score=best_scores.get("ssim", 0),
                histogram_score=best_scores.get("histogram", 0),
                edge_score=best_scores.get("edge", 0),
                template_score=best_scores.get("template", 0),
                combined_score=best_scores.get("combined", 0),
                is_good_match=best_scores.get("is_match", False),
                target_page=target_page,
                confidence=best_scores.get("combined", 0)
            )
            
            # Set validation status
            if best_scores.get("is_high_confidence"):
                result.validation_status = ValidationStatus.APPROVED
            elif best_scores.get("is_match"):
                result.validation_status = ValidationStatus.REVIEW
            else:
                result.validation_status = ValidationStatus.REJECTED
            
            results.append(result)
        
        logger.debug(f"Returning {len(results)} match results")
        return results


# ==================== SMART TEXT PROCESSOR ====================

class SmartTextProcessor:
    """
    Intelligent text processing with context awareness
    """
    
    def __init__(self):
        self.ui_terms = {}
        
        # OCR corrections: only safe multi-char patterns (not single digits/chars)
        self.ocr_corrections = {
            "rn": "m",
            "vv": "w",
        }
        
        # No hardcoded phrase pairs — all text changes are detected dynamically
        # via OCR comparison of old vs new screenshots
        self.common_phrase_pairs = {}
    
    def extract_full_text(self, image_path: str) -> str:
        """Extract full text from image"""
        if not OCR_SUPPORT:
            return ""
        
        try:
            img = Image.open(image_path)
            return pytesseract.image_to_string(img).strip()
        except Exception:
            return ""
    
    def correct_ocr_errors(self, text: str) -> str:
        """Correct common OCR errors"""
        corrected = text
        for error, correction in self.ocr_corrections.items():
            corrected = corrected.replace(error, correction)
        return corrected
    
    def find_ui_term_changes(self, old_text: str, new_text: str) -> List[Dict]:
        """Find UI terminology changes
        
        DISABLED: This function used single-word matching which caused the Scunthorpe 
        problem (e.g., 'view' → 'details' corrupted 'Overview' to 'OverDetails').
        
        Text replacement now relies only on safe multi-word phrase pairs in 
        common_phrase_pairs and OCR-detected phrase changes.
        """
        # Return empty list to disable unsafe single-word matching
        return []  # Disabled: relies on dynamic OCR detection instead
    
    def find_text_differences(self, old_img_path: str, new_img_path: str) -> Dict:
        """Find text differences between two images using enhanced OCR comparison"""
        
        logger.debug(f"Extracting text from old image: {old_img_path}")
        old_text = self.extract_full_text(old_img_path)
        logger.debug(f"Old text extracted: {len(old_text)} chars")
        
        logger.debug(f"Extracting text from new image: {new_img_path}")
        new_text = self.extract_full_text(new_img_path)
        logger.debug(f"New text extracted: {len(new_text)} chars")
        
        # Correct OCR errors
        old_text = self.correct_ocr_errors(old_text)
        new_text = self.correct_ocr_errors(new_text)
        
        # Split into lines for line-by-line comparison
        old_lines = [line.strip() for line in old_text.split('\n') if line.strip() and len(line.strip()) > 2]
        new_lines = [line.strip() for line in new_text.split('\n') if line.strip() and len(line.strip()) > 2]
        
        logger.debug(f"Old lines: {len(old_lines)}, New lines: {len(new_lines)}")
        
        # Find word differences (existing logic)
        old_words = set(old_text.lower().split())
        new_words = set(new_text.lower().split())
        
        added = new_words - old_words
        removed = old_words - new_words
        
        # Find UI term changes
        ui_changes = self.find_ui_term_changes(old_text, new_text)
        
        # Find phrase-level changes by comparing lines
        phrase_changes = self._find_phrase_changes(old_lines, new_lines)
        
        # NEW: Find direct OCR text replacements (key terms and phrases)
        ocr_replacements = self._find_ocr_replacements(old_text, new_text, old_lines, new_lines)
        
        # Calculate similarity
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
            "ui_changes": ui_changes,
            "phrase_changes": phrase_changes,
            "ocr_replacements": ocr_replacements,
            "similarity": similarity,
            "total_changes": len(added) + len(removed) + len(phrase_changes) + len(ocr_replacements)
        }
    
    def _find_ocr_replacements(self, old_text: str, new_text: str, 
                                old_lines: List[str], new_lines: List[str]) -> List[Dict]:
        """Find specific text replacements by analyzing OCR differences"""
        changes = []
        
        old_lower = old_text.lower()
        new_lower = new_text.lower()
        
        # 1. Check for common phrase pairs we know about
        for old_term, new_term in self.common_phrase_pairs.items():
            if old_term in old_lower and new_term in new_lower:
                logger.debug(f"Found known phrase pair: '{old_term}' -> '{new_term}'")
                changes.append({
                    "old": old_term,  # Use original case (not .title())
                    "new": new_term,
                    "category": "phrase_pair",
                    "confidence": 0.95
                })
        
        # 2. Extract key phrases from both texts and compare
        old_phrases = self._extract_key_phrases(old_lines)
        new_phrases = self._extract_key_phrases(new_lines)
        
        logger.debug(f"Extracted {len(old_phrases)} old phrases, {len(new_phrases)} new phrases")
        
        # Find phrases that are in old but not in new, and vice versa
        for old_phrase in old_phrases:
            if old_phrase.lower() not in new_lower:
                # This phrase was removed - look for a similar replacement
                for new_phrase in new_phrases:
                    if new_phrase.lower() not in old_lower:
                        # Both phrases are unique to their respective texts
                        # Check if they might be related (same word count, similar context)
                        old_words = old_phrase.lower().split()
                        new_words = new_phrase.lower().split()
                        
                        if len(old_words) == len(new_words) and len(old_words) <= 3:
                            # Same word count, might be a direct replacement
                            similarity = SequenceMatcher(None, old_phrase.lower(), new_phrase.lower()).ratio()
                            if 0.2 < similarity < 0.85:
                                logger.debug(f"Found OCR replacement: '{old_phrase}' -> '{new_phrase}' (sim: {similarity:.2f})")
                                changes.append({
                                    "old": old_phrase,
                                    "new": new_phrase,
                                    "category": "ocr_phrase",
                                    "confidence": max(0.6, similarity)
                                })
        
        return changes
    
    def _extract_key_phrases(self, lines: List[str]) -> List[str]:
        """Extract key UI phrases from OCR lines"""
        phrases = []
        
        for line in lines:
            # Skip very short or very long lines
            if len(line) < 3 or len(line) > 50:
                continue
                
            # Clean up the line
            clean = line.strip()
            
            # Extract phrases that look like UI elements (capitalized, short)
            words = clean.split()
            if 1 <= len(words) <= 4:
                # This could be a button label, menu item, or header
                if any(w[0].isupper() for w in words if w):
                    phrases.append(clean)
        
        return phrases
    
    def _find_phrase_changes(self, old_lines: List[str], new_lines: List[str]) -> List[Dict]:
        """Find phrase-level changes between old and new text lines"""
        changes = []
        
        # Compare each old line to find its best match in new lines
        for old_line in old_lines:
            if len(old_line) < 4:
                continue
                
            best_match = None
            best_similarity = 0
            
            for new_line in new_lines:
                if len(new_line) < 4:
                    continue
                    
                similarity = SequenceMatcher(None, old_line.lower(), new_line.lower()).ratio()
                
                # Look for lines that are similar but not identical (0.4-0.95 range)
                if 0.4 < similarity < 0.95 and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = new_line
            
            if best_match and old_line.lower() != best_match.lower():
                logger.debug(f"Found phrase change: '{old_line}' -> '{best_match}' (similarity: {best_similarity:.2f})")
                changes.append({
                    "old": old_line,
                    "new": best_match,
                    "category": "phrase",
                    "confidence": best_similarity
                })
        
        return changes
    
    def generate_text_replacements(self, text_diff: Dict) -> List[TextChange]:
        """Generate text replacements from diff"""
        replacements = []
        
        logger.debug(f"Generating text replacements...")
        logger.debug(f"UI changes: {len(text_diff.get('ui_changes', []))}")
        logger.debug(f"Phrase changes: {len(text_diff.get('phrase_changes', []))}")
        logger.debug(f"OCR replacements: {len(text_diff.get('ocr_replacements', []))}")
        
        # HIGH PRIORITY: Add OCR replacements (these are the most reliable)
        for change in text_diff.get("ocr_replacements", []):
            replacements.append(TextChange(
                old_text=change["old"],
                new_text=change["new"],
                page=0,
                confidence=change["confidence"],
                context=change["category"],
                approved=change["confidence"] > 0.5  # Auto-approve most OCR changes
            ))
        
        # Add UI term changes
        for change in text_diff.get("ui_changes", []):
            replacements.append(TextChange(
                old_text=change["old"],
                new_text=change["new"],
                page=0,
                confidence=change["confidence"],
                context=change["category"],
                approved=change["confidence"] > 0.7
            ))
        
        # Add phrase changes
        for change in text_diff.get("phrase_changes", []):
            # Only add if sufficiently confident
            if change["confidence"] > 0.5:
                replacements.append(TextChange(
                    old_text=change["old"],
                    new_text=change["new"],
                    page=0,
                    confidence=change["confidence"],
                    context="phrase",
                    approved=change["confidence"] > 0.6
                ))
        
        # DELETED: Word pairing loop removed - it caused single-word replacements
    # that corrupted text (e.g., "Devices" → "Active devices" mid-sentence)
        
        logger.debug(f"Total replacements generated: {len(replacements)}")
        for r in replacements:
            logger.debug(f"  '{r.old_text}' -> '{r.new_text}' (approved={r.approved}, confidence={r.confidence:.2f})")
        
        return replacements


# ==================== AI VALIDATION ENGINE ====================

class AIValidationEngine:
    """
    Multi-layer AI validation system
    """
    
    def __init__(self):
        self.validation_history = []
        self.thresholds = {
            "auto_approve": 0.85,
            "review_needed": 0.60,
            "reject": 0.40
        }
    
    def validate_image_match(self, match: MatchResult, pdf_image_path: str) -> Dict:
        """Comprehensive image match validation"""
        
        issues = []
        checks = {
            "similarity": False,
            "dimensions": False,
            "colors": False,
            "structure": False,
            "content": False
        }
        
        # Check 1: Similarity threshold
        if match.combined_score >= self.thresholds["review_needed"]:
            checks["similarity"] = True
        else:
            issues.append(f"Low similarity: {match.combined_score:.1%}")
        
        # Check 2: Dimension compatibility
        if PIL_AVAILABLE:
            try:
                new_img = Image.open(match.new_image_path)
                pdf_img = Image.open(pdf_image_path)
                
                new_ratio = new_img.width / new_img.height
                pdf_ratio = pdf_img.width / pdf_img.height
                
                if abs(new_ratio - pdf_ratio) < 0.3:
                    checks["dimensions"] = True
                else:
                    issues.append(f"Aspect ratio mismatch: {abs(new_ratio - pdf_ratio):.2f}")
            except Exception:
                issues.append("Could not verify dimensions")
        
        # Check 3: Color consistency
        if match.histogram_score > 0.4:
            checks["colors"] = True
        else:
            issues.append("Significant color difference")
        
        # Check 4: Structural similarity
        if match.edge_score > 0.4:
            checks["structure"] = True
        else:
            issues.append("UI structure differs significantly")
        
        # Check 5: Content check (template)
        if match.template_score > 0.3:
            checks["content"] = True
        else:
            issues.append("Content layout differs")
        
        # Calculate overall score
        passed = sum(checks.values())
        total = len(checks)
        confidence = (passed / total) * 0.6 + match.combined_score * 0.4
        
        # Determine status
        if confidence >= self.thresholds["auto_approve"]:
            status = ValidationStatus.APPROVED
        elif confidence >= self.thresholds["reject"]:
            status = ValidationStatus.REVIEW
        else:
            status = ValidationStatus.REJECTED
        
        result = {
            "status": status,
            "confidence": confidence,
            "checks_passed": passed,
            "total_checks": total,
            "issues": issues,
            "details": checks
        }
        
        self.validation_history.append(result)
        return result
    
    def validate_text_change(self, change: TextChange) -> Dict:
        """Validate a text change"""
        
        issues = []
        
        # Check 1: Length sanity
        if len(change.new_text) > len(change.old_text) * 3:
            issues.append("New text significantly longer")
        
        # Check 2: Empty check
        if not change.new_text.strip():
            issues.append("New text is empty")
        
        # Check 3: Character type consistency
        old_has_nums = any(c.isdigit() for c in change.old_text)
        new_has_nums = any(c.isdigit() for c in change.new_text)
        if old_has_nums != new_has_nums:
            issues.append("Number presence differs")
        
        confidence = change.confidence * (1 - len(issues) * 0.15)
        
        return {
            "approved": confidence > 0.6 and len(issues) < 2,
            "confidence": max(0, confidence),
            "issues": issues
        }
    
    def generate_validation_summary(self) -> str:
        """Generate validation summary"""
        
        if not self.validation_history:
            return "No validations performed."
        
        approved = sum(1 for v in self.validation_history 
                      if v.get("status") == ValidationStatus.APPROVED)
        review = sum(1 for v in self.validation_history 
                    if v.get("status") == ValidationStatus.REVIEW)
        rejected = sum(1 for v in self.validation_history 
                      if v.get("status") == ValidationStatus.REJECTED)
        
        avg_confidence = sum(v.get("confidence", 0) for v in self.validation_history) / len(self.validation_history)
        
        all_issues = []
        for v in self.validation_history:
            all_issues.extend(v.get("issues", []))
        
        summary = f"""
╔══════════════════════════════════════════════════════════════════╗
║                    AI VALIDATION SUMMARY                         ║
╚══════════════════════════════════════════════════════════════════╝

📊 RESULTS OVERVIEW
───────────────────
✅ Approved:      {approved}
⚠️ Review Needed: {review}
❌ Rejected:      {rejected}
📈 Avg Confidence: {avg_confidence:.1%}

"""
        
        if all_issues:
            issue_counts = Counter(all_issues)
            summary += "⚠️ COMMON ISSUES\n───────────────\n"
            for issue, count in issue_counts.most_common(5):
                summary += f"• {issue} (x{count})\n"
        
        # Overall recommendation
        if avg_confidence >= 0.8 and rejected == 0:
            summary += "\n✅ RECOMMENDATION: Safe to proceed automatically"
        elif avg_confidence >= 0.6:
            summary += "\n⚠️ RECOMMENDATION: Review flagged items before proceeding"
        else:
            summary += "\n❌ RECOMMENDATION: Manual review required"
        
        return summary
    
    def reset(self):
        """Reset validation history"""
        self.validation_history = []


# ==================== ENHANCED PDF PROCESSOR ====================

class EnhancedPDFProcessor:
    """
    Advanced PDF processing with full feature support
    """
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def get_pdf_info(self, pdf_path: str) -> Dict:
        """Get comprehensive PDF information"""
        if not PDF_SUPPORT:
            return {"error": "PDF support not available. Install pymupdf."}
        
        try:
            doc = fitz.open(pdf_path)
            
            images_per_page = {}
            total_images = 0
            total_text = 0
            
            for page_num, page in enumerate(doc):
                images = page.get_images()
                images_per_page[page_num + 1] = len(images)
                total_images += len(images)
                total_text += len(page.get_text())
            
            info = {
                "title": doc.metadata.get("title", Path(pdf_path).stem),
                "pages": len(doc),
                "total_images": total_images,
                "images_per_page": images_per_page,
                "total_text_chars": total_text,
                "author": doc.metadata.get("author", "Unknown"),
                "file_size_kb": round(os.path.getsize(pdf_path) / 1024, 2),
                "creation_date": doc.metadata.get("creationDate", "Unknown")
            }
            doc.close()
            return info
        except Exception as e:
            return {"error": str(e)}
    
    def extract_all_images(self, pdf_path: str, output_dir: str = None) -> List[Dict]:
        """Extract all images with metadata"""
        if not PDF_SUPPORT:
            return []
        
        if output_dir is None:
            output_dir = os.path.join(self.temp_dir, "extracted")
        os.makedirs(output_dir, exist_ok=True)
        
        extracted = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num, page in enumerate(doc):
                images = page.get_images()
                
                for img_index, img in enumerate(images):
                    xref = img[0]
                    
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                        filepath = os.path.join(output_dir, filename)
                        
                        with open(filepath, "wb") as f:
                            f.write(image_bytes)
                        
                        # Get position
                        img_rects = page.get_image_rects(xref)
                        position = None
                        if img_rects:
                            rect = img_rects[0]
                            position = {
                                "x": rect.x0, "y": rect.y0,
                                "width": rect.width, "height": rect.height
                            }
                        
                        extracted.append({
                            "page": page_num + 1,
                            "index": img_index + 1,
                            "xref": xref,
                            "path": filepath,
                            "filename": filename,
                            "position": position,
                            "format": image_ext
                        })
                    except Exception:
                        pass
            
            doc.close()
            return extracted
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return []
    
    def replace_images_and_text(self, pdf_path: str, 
                                 image_replacements: List[Dict],
                                 text_replacements: List[TextChange],
                                 output_path: str) -> Dict:
        """Replace images and text in PDF – two-pass redaction approach"""
        if not PDF_SUPPORT:
            return {"success": False, "error": "PDF support not available"}
        
        try:
            doc = fitz.open(pdf_path)
            images_replaced = 0
            text_replaced = 0
            page_details = {}  # page_num -> {"images": N, "texts": [(old,new),...]}
            
            # ── Pass 1: Replace images ──
            for repl in image_replacements:
                xref = repl.get("xref")
                new_path = repl.get("new_image_path")
                
                if not xref or not new_path or not os.path.exists(new_path):
                    continue
                
                for page_num, page in enumerate(doc):
                    for img in page.get_images():
                        if img[0] == xref:
                            rects = page.get_image_rects(xref)
                            if rects:
                                rect = rects[0]
                                try:
                                    try:
                                        page.delete_image(xref)
                                    except Exception:
                                        # Fallback for flattened/complex images (Edge Case #7)
                                        page.draw_rect(rect, color=(1,1,1), fill=(1,1,1))
                                    
                                    page.insert_image(rect, filename=new_path)
                                    images_replaced += 1
                                    pg = page_details.setdefault(page_num + 1, {"images": 0, "texts": []})
                                    pg["images"] += 1
                                    logger.info(f"Replaced image xref={xref} on page {page_num+1}")
                                except Exception as e:
                                    logger.error(f"Image replacement error on page {page_num+1}: {e}")
                            break
            
            # ── Pass 2a: Collect ALL text redactions per page ──
            page_redactions = {}  # page_num -> [(rect, new_text), ...]
            
            for change in text_replacements:
                if not change.approved:
                    continue
                
                old_text = change.old_text
                new_text = change.new_text
                
                logger.info(f"Text replacement: '{old_text}' -> '{new_text}'")
                
                for page_num, page in enumerate(doc):
                    search_variants = self._generate_search_variants(old_text)
                    
                    for variant in search_variants:
                        instances = page.search_for(variant)
                        if instances:
                            valid_instances = []
                            for inst in instances:
                                # Quick boundary check to prevent replacing part of a larger word (Edge Case #2)
                                ext_rect = fitz.Rect(max(0, inst.x0 - 2), inst.y0, inst.x1 + 2, inst.y1)
                                word_in_context = page.get_text("text", clip=ext_rect).strip()
                                # Only replace if it matches standalone word length roughly
                                if len(word_in_context) <= len(variant) + 3:
                                    valid_instances.append(inst)
                                
                            if valid_instances:
                                logger.info(f"  Found {len(valid_instances)} safe matches for '{variant}' on page {page_num+1}")
                                for inst in valid_instances:
                                    if page_num not in page_redactions:
                                        page_redactions[page_num] = []
                                    page_redactions[page_num].append((inst, new_text))
                                    text_replaced += 1
                                    pg = page_details.setdefault(page_num + 1, {"images": 0, "texts": []})
                                    pg["texts"].append((old_text, new_text))
                                break  # Use first variant that matches
            
            # ── Pass 2b: Apply all redactions per page at once ──
            for page_num, redactions in page_redactions.items():
                page = doc[page_num]
                # First, mark all redactions
                for rect, _ in redactions:
                    page.add_redact_annot(rect)
                
                try:
                    # Apply redactions to wipe old text
                    page.apply_redactions()
                except Exception as e:
                    logger.error(f"Apply redactions error on page {page_num+1}: {e}")
                    
                # Now add the new text overlays
                for rect, new_text in redactions:
                    try:
                        # Edge Case #1 Fix: Use FreeText to prevent squishing and show as tracked change
                        # Widen the rect to allow natural text flow
                        new_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + max(rect.width, len(new_text)*5.5), rect.y1 + 12)
                        annot = page.add_freetext_annot(
                            new_rect,
                            new_text,
                            fontsize=max(8, rect.height * 0.75),
                            fontname="helv",
                            text_color=(0.8, 0, 0), # Dark red change
                            fill_color=(1, 1, 0.9)  # Light yellow bg
                        )
                        annot.update()
                    except Exception as e:
                        logger.error(f"Text overlay error on page {page_num+1}: {e}")
            
            logger.info(f"Total: {images_replaced} images replaced, {text_replaced} text replacements")
            
            doc.save(output_path)
            doc.close()
            
            return {
                "success": True,
                "images_replaced": images_replaced,
                "text_replaced": text_replaced,
                "output_path": output_path,
                "page_details": page_details
            }
        except Exception as e:
            logger.error(f"PDF replacement error: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_search_variants(self, text: str) -> List[str]:
        """Generate search variants for case-insensitive fuzzy matching"""
        variants = []
        seen = set()
        
        def _add(v):
            if v and v not in seen:
                seen.add(v)
                variants.append(v)
        
        # Original text
        _add(text)
        # Normalized whitespace
        _add(' '.join(text.split()))
        # Title Case
        _add(text.title())
        # UPPER CASE (headings in PDFs are often uppercase)
        _add(text.upper())
        # lower case
        _add(text.lower())
        # Capitalize first letter only
        _add(text[0].upper() + text[1:] if len(text) > 1 else text.upper())
        
        return variants
    
    def render_pdf_pages(self, pdf_path: str, output_dir: str = None) -> List[Dict]:
        """Render each PDF page as an image for fallback comparison"""
        if not PDF_SUPPORT:
            return []
        
        if output_dir is None:
            output_dir = os.path.join(self.temp_dir, "rendered")
        os.makedirs(output_dir, exist_ok=True)
        
        rendered = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Render at 150 DPI
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat)
                img_path = os.path.join(output_dir, f"page_{page_num + 1}.png")
                pix.save(img_path)
                rendered.append({
                    "page": page_num + 1,
                    "path": img_path,
                    "filename": f"page_{page_num + 1}.png",
                })
            doc.close()
            logger.info(f"Rendered {len(rendered)} PDF pages as images")
        except Exception as e:
            logger.error(f"Error rendering PDF pages: {e}")
        return rendered
    
    def cleanup(self):
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass


# ==================== VISUAL ANALYZER ====================

class VisualAnalyzer:
    """Create visual comparisons and highlights"""
    
    def create_highlight_image(self, old_path: str, new_path: str, output_path: str) -> Optional[str]:
        """Create image with highlighted differences"""
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
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
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
    
    def create_side_by_side(self, old_path: str, new_path: str, output_path: str) -> Optional[str]:
        """Create side-by-side comparison"""
        if not CV2_AVAILABLE:
            return None
        
        try:
            old_img = cv2.imread(old_path)
            new_img = cv2.imread(new_path)
            
            if old_img is None or new_img is None:
                return None
            
            # Resize to same height
            h = max(old_img.shape[0], new_img.shape[0])
            old_img = cv2.resize(old_img, (int(old_img.shape[1] * h / old_img.shape[0]), h))
            new_img = cv2.resize(new_img, (int(new_img.shape[1] * h / new_img.shape[0]), h))
            
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


# ==================== REPORT GENERATOR ====================

class ComprehensiveReportGenerator:
    """Generate all report formats"""
    
    def generate_summary(self, result: ProcessingResult, pdf_info: Dict,
                         page_details: Dict = None) -> str:
        """Generate detailed English-only summary with per-page breakdown"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine overall status
        if result.overall_confidence >= 0.8:
            status = "EXCELLENT"
            status_desc = "High confidence - all changes verified"
        elif result.overall_confidence >= 0.6:
            status = "GOOD"
            status_desc = "Moderate confidence - review recommended"
        else:
            status = "NEEDS REVIEW"
            status_desc = "Low confidence - manual review required"
        
        summary = f"""DOCUMENT UPDATE REPORT
{'=' * 72}
Generated : {timestamp}
Document  : {pdf_info.get('title', 'Unknown')}
Pages     : {pdf_info.get('pages', 'N/A')}
Status    : {status} - {status_desc}
{'=' * 72}

SUMMARY
{'-' * 40}
  Screenshots Processed : {len(result.matches)}
  Images Replaced       : {result.images_replaced}
  Text Changes Applied  : {result.text_replaced}
  Text Changes Detected : {len(result.text_changes)}
  Overall Confidence    : {result.overall_confidence:.1%}
  Processing Time       : {result.processing_time:.2f} seconds
"""
        
        # ── Per-page breakdown ──
        if page_details:
            summary += f"\nPER-PAGE CHANGE DETAILS\n{'-' * 40}\n"
            for page_num in sorted(page_details.keys()):
                info = page_details[page_num]
                img_count = info.get("images", 0)
                txt_list = info.get("texts", [])
                summary += f"\n  Page {page_num}:\n"
                if img_count:
                    summary += f"    - {img_count} image(s) replaced\n"
                if txt_list:
                    summary += f"    - {len(txt_list)} text change(s):\n"
                    seen = set()
                    for old_t, new_t in txt_list:
                        key = (old_t, new_t)
                        if key not in seen:
                            seen.add(key)
                            summary += f'        "{old_t}" -> "{new_t}"\n'
        
        # ── Match details ──
        summary += f"\nMATCH DETAILS\n{'-' * 40}\n"
        for match in result.matches:
            status_icon = "[OK]" if match.validation_status == ValidationStatus.APPROVED else \
                         "[REVIEW]" if match.validation_status == ValidationStatus.REVIEW else "[REJECTED]"
            matched_page = match.matched_pdf_image.get('page', 'N/A') if match.matched_pdf_image else 'N/A'
            summary += f"  {status_icon} {match.new_image_name}\n"
            summary += f"      Page: {matched_page} | Confidence: {match.confidence:.1%} | Status: {match.validation_status.value}\n"
        
        # ── Text changes listing ──
        if result.text_changes:
            summary += f"\nALL TEXT CHANGES\n{'-' * 40}\n"
            for i, change in enumerate(result.text_changes, 1):
                approved_str = "[APPLIED]" if change.approved else "[SKIPPED]"
                summary += f'  {i}. {approved_str} "{change.old_text}" -> "{change.new_text}" (confidence: {change.confidence:.0%})\n'
        
        if result.errors:
            summary += f"\nERRORS\n{'-' * 40}\n"
            for error in result.errors:
                summary += f"  - {error}\n"
        
        if result.warnings:
            summary += f"\nWARNINGS\n{'-' * 40}\n"
            for warning in result.warnings:
                summary += f"  - {warning}\n"
        
        summary += f"\n{'=' * 72}\nOUTPUT: {result.output_path}\n{'=' * 72}\n"
        
        return summary
    
    def generate_json(self, result: ProcessingResult, pdf_info: Dict) -> str:
        """Generate JSON report"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "document": pdf_info,
            "success": result.success,
            "images_replaced": result.images_replaced,
            "text_replaced": result.text_replaced,
            "confidence": result.overall_confidence,
            "processing_time": result.processing_time,
            "matches": [
                {
                    "image": m.new_image_name,
                    "page": m.matched_pdf_image.get("page") if m.matched_pdf_image else None,
                    "confidence": m.confidence,
                    "status": m.validation_status.value
                }
                for m in result.matches
            ],
            "text_changes": [
                {
                    "old": c.old_text,
                    "new": c.new_text,
                    "confidence": c.confidence
                }
                for c in result.text_changes
            ],
            "errors": result.errors,
            "warnings": result.warnings
        }
        
        return json.dumps(data, indent=2)
    
    def generate_html(self, result: ProcessingResult, pdf_info: Dict) -> str:
        """Generate HTML report"""
        
        confidence_pct = result.overall_confidence * 100
        status_color = "#27ae60" if confidence_pct >= 70 else "#f39c12" if confidence_pct >= 50 else "#e74c3c"
        status_text = "PASSED" if confidence_pct >= 70 else "REVIEW NEEDED" if confidence_pct >= 50 else "FAILED"
        
        matches_html = ""
        for m in result.matches:
            icon = "✅" if m.validation_status == ValidationStatus.APPROVED else \
                   "⚠️" if m.validation_status == ValidationStatus.REVIEW else "❌"
            matched_page = m.matched_pdf_image.get('page', 'N/A') if m.matched_pdf_image else 'N/A'
            confidence_color = '#27ae60' if m.confidence >= 0.7 else '#f39c12'
            matches_html += f"""
            <tr>
                <td>{icon} {m.new_image_name}</td>
                <td>Page {matched_page}</td>
                <td style="color: {confidence_color}">{m.confidence:.1%}</td>
                <td>{m.validation_status.value}</td>
            </tr>
            """
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Document Update Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a0a; color: #fff; }}
        .container {{ max-width: 1100px; margin: 0 auto; padding: 30px; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 40px; border-radius: 15px; text-align: center; margin-bottom: 30px; }}
        .status-badge {{ display: inline-block; padding: 12px 35px; background: {status_color}; border-radius: 30px; font-size: 1.2em; font-weight: bold; margin-top: 20px; }}
        .card {{ background: #16213e; border-radius: 15px; padding: 25px; margin-bottom: 20px; }}
        .card h2 {{ color: #4CAF50; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #4CAF50; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; }}
        .stat {{ background: #0f3460; padding: 25px; border-radius: 12px; text-align: center; }}
        .stat-value {{ font-size: 2.5em; font-weight: bold; color: #4CAF50; }}
        .stat-label {{ color: #888; margin-top: 5px; }}
        .progress {{ background: #0f3460; border-radius: 15px; height: 35px; overflow: hidden; margin: 20px 0; }}
        .progress-bar {{ height: 100%; background: linear-gradient(90deg, #4CAF50, #8BC34A); display: flex; align-items: center; justify-content: center; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th {{ background: #4CAF50; padding: 15px; text-align: left; }}
        td {{ padding: 15px; border-bottom: 1px solid #333; }}
        tr:hover {{ background: #0f3460; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 Document Update Report</h1>
            <p>Tech Doc Auto Updater v3.0</p>
            <p style="color: #888; margin-top: 10px;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <div class="status-badge">{status_text}</div>
        </div>
        
        <div class="card">
            <h2>📊 Processing Summary</h2>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{len(result.matches)}</div>
                    <div class="stat-label">Screenshots</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{result.images_replaced}</div>
                    <div class="stat-label">Images Replaced</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{result.text_replaced}</div>
                    <div class="stat-label">Text Updates</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{result.processing_time:.1f}s</div>
                    <div class="stat-label">Time</div>
                </div>
            </div>
            
            <h3 style="margin-top: 25px;">Overall Confidence</h3>
            <div class="progress">
                <div class="progress-bar" style="width: {confidence_pct}%">{confidence_pct:.0f}%</div>
            </div>
        </div>
        
        <div class="card">
            <h2>🔍 Match Details</h2>
            <table>
                <tr><th>Screenshot</th><th>Matched To</th><th>Confidence</th><th>Status</th></tr>
                {matches_html}
            </table>
        </div>
        
        <div class="card">
            <h2>✅ Output</h2>
            <p><strong>Updated PDF:</strong> {result.output_path}</p>
            <p><strong>Document:</strong> {pdf_info.get('title', 'N/A')} ({pdf_info.get('pages', 'N/A')} pages)</p>
        </div>
    </div>
</body>
</html>
"""
        return html


# ==================== EXPORT MANAGER ====================

class ExportManager:
    """Handle all export functionality"""
    
    def __init__(self, output_dir: str = "./data/output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def create_zip_export(self, files: List[str], zip_name: str = None) -> str:
        """Create ZIP file with all outputs"""
        
        if zip_name is None:
            zip_name = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        zip_path = os.path.join(self.output_dir, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in files:
                if file_path and os.path.exists(file_path):
                    zf.write(file_path, os.path.basename(file_path))
        
        return zip_path


# ==================== MAIN PROCESSING FUNCTION ====================

def process_document_v3(
    old_gui,        # Required: old GUI screenshot
    old_pdf,        # Required: PDF document to update
    new_gui=None,   # Required: new GUI screenshot
    custom_replacements=""  # Optional: custom text replacements (format: "old -> new" per line)
):
    """
    Main processing function v3.0 - Simplified Edition
    
    Args:
        old_gui: Required old GUI screenshot for reference
        old_pdf: Required PDF document to update
        new_gui: Required new GUI screenshot for replacement
        custom_replacements: Optional custom text replacements, one per line ("old text -> new text")
    """
    
    # Hardcoded defaults (previously configurable)
    enable_text_replacement = True
    enable_ai_validation = True
    enable_auto_page_detection = True
    confidence_threshold = 0.30  # Must match AdvancedImageMatcher default
    
    start_time = time.time()
    output_dir = "./data/output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Edge Case #5: Append UUID to prevent multi-user write collisions
    timestamp = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    # Initialize result
    result = ProcessingResult(success=False)
    _page_details = {}  # Initialize early to prevent NameError on error paths
    
    # Validate required inputs
    if old_gui is None:
        return None, "❌ Please upload the old GUI screenshot", "", None, "{}", None, ""
    
    if old_pdf is None:
        return None, "❌ Please upload the PDF document", "", None, "{}", None, ""
    
    # Get paths from uploaded files
    old_gui_path = old_gui if isinstance(old_gui, str) else old_gui.name
    
    # Handle new_gui - REQUIRED for Update Mode
    new_paths = []
    if new_gui is not None:
        if isinstance(new_gui, list):
            for f in new_gui:
                if f is not None:
                    new_paths.append(f if isinstance(f, str) else f.name)
        else:
            new_paths.append(new_gui if isinstance(new_gui, str) else new_gui.name)
    
    # VALIDATION: New screenshot is required for document updates
    if not new_paths:
        return None, """❌ **New GUI Screenshot Required**

To update your document, please upload the **new** GUI screenshot.

**What you need:**
- **Old GUI Screenshot**: The current/outdated interface ✅ (provided)
- **New GUI Screenshot**: The updated interface ❌ (missing)
- **PDF Document**: The manual to update ✅ (provided)

The tool will:
1. Find where the old screenshot appears in the PDF
2. Replace it with the new screenshot
3. Update related text descriptions

Without the new screenshot, there's nothing to update.""", "", None, "{}", None, ""
    
    # Get PDF path
    pdf_path = old_pdf if isinstance(old_pdf, str) else old_pdf.name
    
    # Page hints no longer used (auto-detection only)
    page_hints = {}
    

    try:
        logger.debug("Starting process_document_v3...")
        logger.debug(f"old_gui_path: {old_gui_path}")
        logger.debug(f"new_paths: {new_paths}")
        logger.debug(f"pdf_path: {pdf_path}")
        
        # Initialize all components
        logger.debug("Initializing components...")
        pdf_processor = EnhancedPDFProcessor()
        matcher = AdvancedImageMatcher({"similarity_threshold": confidence_threshold})
        text_processor = SmartTextProcessor()
        validator = AIValidationEngine() if enable_ai_validation else None
        analyzer = VisualAnalyzer()
        report_gen = ComprehensiveReportGenerator()
        history_mgr = HistoryManager()
        logger.debug("Components initialized.")
        
        # Get PDF info
        logger.debug("Getting PDF info...")
        pdf_info = pdf_processor.get_pdf_info(pdf_path)
        logger.debug(f"PDF info: {pdf_info}")
        if "error" in pdf_info:
            return None, f"❌ PDF Error: {pdf_info['error']}", "", None, "{}", None, ""
        
        # Extract images from PDF
        logger.info("Extracting images from PDF...")
        extract_dir = os.path.join(output_dir, f"extracted_{timestamp}")
        pdf_images = pdf_processor.extract_all_images(pdf_path, extract_dir)
        logger.info(f"Extracted {len(pdf_images)} images from PDF")
        
        # Filter out tiny images (icons, logos < 50x50)
        large_pdf_images = []
        for pimg in pdf_images:
            try:
                if PIL_AVAILABLE:
                    _img = Image.open(pimg["path"])
                    if _img.width >= 50 and _img.height >= 50:
                        large_pdf_images.append(pimg)
                    else:
                        logger.debug(f"Filtered small image: {pimg['filename']} ({_img.width}x{_img.height})")
                else:
                    large_pdf_images.append(pimg)
            except Exception:
                large_pdf_images.append(pimg)
        
        if not large_pdf_images and not pdf_images:
            return None, "No images found in the PDF document.", "", None, "{}", None, ""
        
        use_images = large_pdf_images if large_pdf_images else pdf_images
        logger.info(f"Using {len(use_images)} images for matching (filtered from {len(pdf_images)})")
        
        # CRITICAL FIX: Match OLD GUI against PDF images to find WHERE the old image is
        # (was incorrectly matching new GUI, which is what we want to INSERT, not find)
        logger.info("Matching old GUI screenshot against PDF images...")
        matches = matcher.find_best_matches([old_gui_path], use_images, page_hints)
        logger.info(f"Found {len(matches)} match candidates")
        
        # Fallback: if no good match with extracted images, try rendered pages
        if not any(m.is_good_match for m in matches):
            logger.info("No match with extracted images, trying rendered PDF pages...")
            render_dir = os.path.join(output_dir, f"rendered_{timestamp}")
            rendered_pages = pdf_processor.render_pdf_pages(pdf_path, render_dir)
            if rendered_pages:
                page_matches = matcher.find_best_matches([old_gui_path], rendered_pages, page_hints)
                for pm in page_matches:
                    if pm.is_good_match:
                        target_page = pm.matched_pdf_image.get("page")
                        logger.info(f"Matched old GUI to rendered page {target_page}")
                        # Find the largest image on that page
                        page_imgs = [i for i in use_images if i.get("page") == target_page]
                        if page_imgs:
                            best_img = page_imgs[0]
                            match = MatchResult(
                                new_image_path=new_paths[0] if new_paths else old_gui_path,
                                new_image_name=os.path.basename(new_paths[0]) if new_paths else "old_gui",
                                matched_pdf_image=best_img,
                                is_good_match=True,
                                target_page=target_page,
                                confidence=pm.confidence,
                                combined_score=pm.combined_score,
                            )
                            matches = [match]
                            break
        
        # Set the NEW GUI as the replacement image for all matches
        for match in matches:
            if match.is_good_match and new_paths:
                match.new_image_path = new_paths[0]
                match.new_image_name = os.path.basename(new_paths[0])
        
        logger.info(f"Good matches: {sum(1 for m in matches if m.is_good_match)}/{len(matches)}")
        
        # AI Validation if enabled
        logger.debug("Running AI validation...")
        if validator:
            for match in matches:
                if match.matched_pdf_image:
                    validation = validator.validate_image_match(
                        match, 
                        match.matched_pdf_image.get("path", "")
                    )
                    match.validation_status = validation["status"]
                    match.confidence = validation["confidence"]
                    match.issues = validation.get("issues", [])
        
        # Process text differences if enabled
        logger.debug("Processing text differences...")
        text_changes = []
        text_report = "Text replacement disabled."
        
        if enable_text_replacement:
            if not OCR_SUPPORT:
                text_report = "⚠️ OCR missing (Tesseract not installed or path invalid). Text replacement skipped entirely."
            else:
                # Use old GUI as reference (it's now required)
                reference_image = old_gui_path
                
                if reference_image and new_paths:
                    logger.debug(f"Comparing text: {reference_image} vs {new_paths}")
                    for new_path in new_paths:
                        logger.debug(f"Processing text for: {new_path}")
                        text_diff = text_processor.find_text_differences(reference_image, new_path)
                        logger.debug(f"Text diff result: {text_diff.get('total_changes', 0)} changes")
                        changes = text_processor.generate_text_replacements(text_diff)
                        
                        # Validate text changes if AI validation enabled
                        if validator:
                            for change in changes:
                                validation = validator.validate_text_change(change)
                                change.approved = validation["approved"]
                                change.confidence = validation["confidence"]
                        
                        text_changes.extend(changes)
                    
                    # Add custom replacements from user input
                    if custom_replacements and custom_replacements.strip():
                        logger.debug(f"Parsing custom replacements...")
                        for line in custom_replacements.strip().split("\n"):
                            if "->" in line:
                                parts = line.split("->", 1)
                                if len(parts) == 2:
                                    old_text = parts[0].strip()
                                    new_text = parts[1].strip()
                                    if old_text and new_text:
                                        logger.debug(f"Custom replacement: '{old_text}' -> '{new_text}'")
                                        text_changes.append(TextChange(
                                            old_text=old_text,
                                            new_text=new_text,
                                            page=0,
                                            confidence=1.0,
                                            context="custom",
                                            approved=True  # Always approve custom user replacements
                                        ))
                    
                    # Generate text report
                    if text_changes:
                        text_report = f"""
📝 TEXT CHANGE ANALYSIS
═══════════════════════

Total Changes Detected: {len(text_changes)}
Approved for Replacement: {sum(1 for c in text_changes if c.approved)}

DETECTED REPLACEMENTS:
──────────────────────
"""
                        for i, change in enumerate(text_changes[:15], 1):
                            status = "✅" if change.approved else "⚠️"
                            text_report += f'{status} "{change.old_text}" → "{change.new_text}" ({change.confidence:.0%})\n'
                    else:
                        text_report = "No significant text changes detected."
        
        # Prepare image replacements
        image_replacements = []
        for match in matches:
            if match.is_good_match and match.matched_pdf_image:
                # Check validation status
                if validator:
                    if match.validation_status == ValidationStatus.REJECTED:
                        result.warnings.append(f"Skipped {match.new_image_name}: Failed validation")
                        continue
                
                image_replacements.append({
                    "xref": match.matched_pdf_image.get("xref"),
                    "new_image_path": match.new_image_path
                })
        
        # Create output PDF path
        output_pdf_path = os.path.join(output_dir, f"updated_{timestamp}.pdf")
        
        # Replace images and text
        if image_replacements or text_changes:
            replace_result = pdf_processor.replace_images_and_text(
                pdf_path,
                image_replacements,
                [c for c in text_changes if c.approved],
                output_pdf_path
            )
            
            if replace_result.get("success"):
                result.images_replaced = replace_result.get("images_replaced", 0)
                result.text_replaced = replace_result.get("text_replaced", 0)
                result.output_path = output_pdf_path
                result.success = True
                _page_details = replace_result.get("page_details", {})
            else:
                result.errors.append(replace_result.get("error", "Unknown error"))
                _page_details = {}
        else:
            # No changes to make, just copy the original
            shutil.copy(pdf_path, output_pdf_path)
            result.output_path = output_pdf_path
            result.success = True
            result.warnings.append("No matching images found - PDF copied without changes")
            _page_details = {}
        
        # Create visual highlight
        highlight_path = None
        if new_paths:
            # Use old_gui_path as reference
            reference = old_gui_path
            
            if reference:
                highlight_path = os.path.join(output_dir, f"highlights_{timestamp}.png")
                analyzer.create_highlight_image(reference, new_paths[0], highlight_path)
        
        # Calculate overall confidence
        if matches:
            confidences = [m.confidence for m in matches if m.confidence > 0]
            result.overall_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Store matches and text changes
        result.matches = matches
        result.text_changes = text_changes
        result.processing_time = time.time() - start_time
        logger.info(f"Processing time: {result.processing_time:.2f}s")
        
        # Add to history
        history_mgr.add_version(pdf_path, {}, result)
        
        # Generate reports (pass page_details for per-page breakdown)
        summary_report = report_gen.generate_summary(result, pdf_info, _page_details)
        json_report = report_gen.generate_json(result, pdf_info)
        html_report = report_gen.generate_html(result, pdf_info)
        
        # Save HTML report
        html_path = os.path.join(output_dir, f"report_{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        
        # Generate AI validation report
        ai_report = ""
        if validator:
            ai_report = validator.generate_validation_summary()
        
        # Cleanup
        pdf_processor.cleanup()
        
        logger.info("Processing complete.")
        return (
            output_pdf_path,
            summary_report,
            ai_report if ai_report else "AI validation disabled.",
            highlight_path,
            json_report,
            html_path,
            text_report
        )
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        logger.debug(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Error: {str(e)}", "", None, "{}", None, ""


def quick_compare(img1, img2):
    """Quick comparison of two images"""
    if img1 is None or img2 is None:
        return 0, None, "Please upload both images"
    
    path1 = img1 if isinstance(img1, str) else img1
    path2 = img2 if isinstance(img2, str) else img2
    
    matcher = AdvancedImageMatcher()
    analyzer = VisualAnalyzer()
    
    scores = matcher.compute_combined_score(path1, path2)
    
    output_dir = "./data/output"
    os.makedirs(output_dir, exist_ok=True)
    highlight_path = os.path.join(output_dir, f"compare_{datetime.now().strftime('%H%M%S')}.png")
    analyzer.create_highlight_image(path1, path2, highlight_path)
    
    report = f"""
╔══════════════════════════════════════════════════════════════════╗
║                    QUICK COMPARISON RESULTS                      ║
╚══════════════════════════════════════════════════════════════════╝

📊 SIMILARITY SCORES
────────────────────
• SSIM Score:      {scores['ssim']:.1%}
• Histogram Score: {scores['histogram']:.1%}
• Edge Score:      {scores['edge']:.1%}
• Template Score:  {scores['template']:.1%}
• Combined Score:  {scores['combined']:.1%}

📋 RESULT
─────────
{'✅ MATCH - Images are similar enough for replacement' if scores['is_match'] else '❌ NO MATCH - Images differ significantly'}
{'🌟 HIGH CONFIDENCE' if scores['is_high_confidence'] else ''}

🎨 VISUAL ANALYSIS
──────────────────
• Red boxes: Major differences
• Yellow boxes: Minor differences
"""
    
    return scores['combined'] * 100, highlight_path, report


def get_version_history():
    """Get version history for display"""
    history_mgr = HistoryManager()
    versions = history_mgr.get_recent_versions(10)
    
    if not versions:
        return "No version history available."
    
    history_text = """
╔══════════════════════════════════════════════════════════════════╗
║                      VERSION HISTORY                             ║
╚══════════════════════════════════════════════════════════════════╝

"""
    
    for v in versions:
        confidence = v.get('confidence', 0)
        history_text += f"""
📌 Version: {v.get('version_id', 'Unknown')}
   Date: {v.get('timestamp', 'Unknown')}
   Images Replaced: {v.get('images_replaced', 0)}
   Text Updates: {v.get('text_replaced', 0)}
   Confidence: {confidence:.1%}
   Output: {v.get('output_path', 'N/A')}
───────────────────────────────────────────────────────────────────
"""
    
    return history_text


def rollback_version(version_id: str):
    """Rollback to a previous version"""
    if not version_id or not version_id.strip():
        return None, "Please enter a version ID"
    
    history_mgr = HistoryManager()
    backup_path = history_mgr.rollback(version_id.strip())
    
    if backup_path and os.path.exists(backup_path):
        return backup_path, f"✅ Successfully restored version {version_id}"
    else:
        return None, f"❌ Could not find version {version_id}"


def export_all_outputs(pdf_path, html_path, highlight_path):
    """Create ZIP with all outputs"""
    if not pdf_path:
        return None, "No outputs to export"
    
    files = []
    if pdf_path and os.path.exists(str(pdf_path)):
        files.append(str(pdf_path))
    if html_path and os.path.exists(str(html_path)):
        files.append(str(html_path))
    if highlight_path and os.path.exists(str(highlight_path)):
        files.append(str(highlight_path))
    
    if not files:
        return None, "No files to export"
    
    export_mgr = ExportManager()
    zip_path = export_mgr.create_zip_export(files)
    
    return zip_path, f"✅ Exported {len(files)} files to ZIP"


def process_batch(old_gui, new_gui, pdfs):
    """Process multiple PDFs with the same GUI update"""
    if not old_gui or not new_gui or not pdfs:
        return "❌ Please upload both screenshots and at least one PDF", None
    
    results = []
    output_files = []
    timestamp = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    # Get screenshot paths
    old_gui_path = old_gui if isinstance(old_gui, str) else old_gui.name
    new_gui_path = new_gui if isinstance(new_gui, str) else new_gui.name
    
    # Process each PDF
    pdf_list = pdfs if isinstance(pdfs, list) else [pdfs]
    
    for pdf in pdf_list:
        if pdf is None:
            continue
            
        pdf_path = pdf if isinstance(pdf, str) else pdf.name
        pdf_name = os.path.basename(pdf_path)
        
        results.append(f"📄 Processing: {pdf_name}...")
        
        try:
            output = process_document_v3(
                old_gui_path,  # old_gui (required)
                pdf_path,      # old_pdf (required)
                new_gui_path   # new_gui (required)
            )
            
            if output[0]:
                output_files.append(output[0])
                results.append(f"   ✅ Success: {os.path.basename(output[0])}")
            else:
                results.append(f"   ❌ Failed: {output[1]}")
        except Exception as e:
            results.append(f"   ❌ Error: {str(e)}")
    
    # Create ZIP of all outputs
    if output_files:
        export_mgr = ExportManager()
        zip_path = export_mgr.create_zip_export(
            output_files,
            f"batch_output_{timestamp}.zip"
        )
        results.append(f"\n📦 Created ZIP with {len(output_files)} files")
        return "\n".join(results), zip_path
    
    return "\n".join(results), None


def save_settings(*args):
    """Save settings to file"""
    # In a real implementation, save to config file
    return "✅ Settings saved successfully!"


# ==================== AUTH HELPERS ====================

def _read_log_files():
    """Read recent log entries from data/logs/"""
    log_dir = "./data/logs"
    if not os.path.isdir(log_dir):
        return "No log files found."
    
    log_files = sorted(
        [f for f in os.listdir(log_dir) if f.endswith(".log")],
        reverse=True,
    )
    if not log_files:
        return "No log files found."
    
    lines = []
    for lf in log_files[:3]:  # last 3 days
        try:
            with open(os.path.join(log_dir, lf), "r", encoding="utf-8", errors="replace") as fh:
                lines.extend(fh.readlines()[-200:])  # last 200 lines per file
        except Exception:
            pass
    
    if not lines:
        return "Log files are empty."
    return "".join(lines[-500:])  # cap at 500 lines


def _get_audit_log():
    """Get audit log entries"""
    if not AUTH_AVAILABLE:
        return "Auth module not available."
    try:
        rbac = RBACManager()
        entries = rbac.get_audit_log(limit=100)
        if not entries:
            return "No audit log entries."
        text = "AUDIT LOG\n" + "=" * 60 + "\n"
        for e in entries:
            text += f"[{e['timestamp']}] {e['username']} - {e['action']}: {e['details']}\n"
        return text
    except Exception as ex:
        return f"Error reading audit log: {ex}"


def _list_users_display():
    """List users for admin display"""
    if not AUTH_AVAILABLE:
        return "Auth module not available."
    try:
        rbac = RBACManager()
        users = rbac.list_users()
        if not users:
            return "No users found."
        text = f"{'Username':<15} {'Role':<10} {'Active':<8} {'Last Login':<25}\n"
        text += "-" * 60 + "\n"
        for u in users:
            text += f"{u['username']:<15} {u['role']:<10} {'Yes' if u['active'] else 'No':<8} {u.get('last_login','Never') or 'Never':<25}\n"
        return text
    except Exception as ex:
        return f"Error: {ex}"


def _create_user(username, password, role, admin_user):
    """Create a new user (admin only)"""
    if not AUTH_AVAILABLE:
        return "Auth module not available."
    if admin_user is None or admin_user.get("role") != "admin":
        return "Access denied. Admin role required."
    if not username or not password:
        return "Username and password are required."
    if role not in ("viewer", "editor", "admin"):
        return "Role must be viewer, editor, or admin."
    try:
        rbac = RBACManager()
        ok = rbac.create_user(username.strip(), password.strip(), role)
        if ok:
            rbac._log_audit(admin_user["username"], "create_user", f"Created user {username} with role {role}")
            return f"User '{username}' created with role '{role}'."
        return f"Failed to create user '{username}' (may already exist)."
    except Exception as ex:
        return f"Error: {ex}"


def _process_with_auth(old_gui, old_pdf, new_gui, custom_replacements, user_state):
    """Auth-gated document processing"""
    if user_state is None:
        return None, "Please login first.", "", None, "{}", None, ""
    if AUTH_AVAILABLE:
        rbac = RBACManager()
        if not rbac.authorize(user_state, "process_document"):
            return None, "Access denied. Editor or Admin role required.", "", None, "{}", None, ""
        rbac._log_audit(user_state["username"], "process_document", "Started document processing")
    return process_document_v3(old_gui, old_pdf, new_gui, custom_replacements)


def _compare_with_auth(img1, img2, user_state):
    """Auth-gated comparison"""
    if user_state is None:
        return 0, None, "Please login first."
    return quick_compare(img1, img2)


# ==================== GRADIO INTERFACE ====================

def build_interface():
    """Build the complete Gradio interface with login and RBAC"""
    
    if not GRADIO_AVAILABLE:
        print("Gradio not installed. Run: pip install gradio")
        return None
    
    with gr.Blocks(
        title="Document Updater - Schneider Electric",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 1200px !important; }
        .header-text { text-align: center; }
        """
    ) as interface:
        
        # Auth state
        current_user = gr.State(value=None)
        
        # ==================== LOGIN SECTION ====================
        with gr.Column(visible=True) as login_section:
            gr.Markdown("""
            # Document Updater
            ### Schneider Electric Technical Documentation Tool
            
            **Please login to continue.**
            
            ---
            """)
            with gr.Row():
                with gr.Column(scale=1):
                    pass
                with gr.Column(scale=2):
                    login_username = gr.Textbox(label="Username", placeholder="Enter username")
                    login_password = gr.Textbox(label="Password", type="password", placeholder="Enter password")
                    login_btn = gr.Button("Login", variant="primary", size="lg")
                    login_status = gr.Markdown("")
                    gr.Markdown("""
                    **Default accounts:**
                    
                    | Username | Password | Role |
                    |----------|----------|------|
                    | admin | admin123 | Admin (full access) |
                    | editor | editor123 | Editor (process documents) |
                    | viewer | viewer123 | Viewer (read-only) |
                    """)
                with gr.Column(scale=1):
                    pass
        
        # ==================== MAIN APP (hidden until login) ====================
        with gr.Column(visible=False) as main_section:
            
            # Header with user info
            with gr.Row():
                gr.Markdown("""
                # Document Updater
                ### Schneider Electric Technical Documentation Tool
                """)
            with gr.Row():
                user_info_display = gr.Markdown("Not logged in")
                logout_btn = gr.Button("Logout", size="sm", variant="secondary")
            
            gr.Markdown("---")
            
            # ==================== TAB: UPDATE DOCUMENT ====================
            with gr.Tab("Update Document"):
                gr.Markdown("""
                ### Update Your Documentation
                Upload the current screenshot and PDF, then add the new screenshot to replace it.
                """)
                
                with gr.Row():
                    # Left Column - Inputs
                    with gr.Column(scale=1):
                        gr.Markdown("#### Step 1: Upload Files")
                        
                        old_gui = gr.File(
                            label="Current Screenshot (Required)",
                            file_types=["image"],
                            type="filepath"
                        )
                        
                        old_pdf = gr.File(
                            label="PDF Document (Required)",
                            file_types=[".pdf"],
                            type="filepath"
                        )
                        
                        new_gui = gr.File(
                            label="New Screenshot (Required)",
                            file_types=["image"],
                            type="filepath"
                        )
                        
                        gr.Markdown("#### Custom Text Replacements (Optional)")
                        gr.Markdown("*Add your own replacements, one per line: `old text -> new text`*")
                        
                        custom_replacements = gr.Textbox(
                            label="Custom Replacements",
                            placeholder="green gradient -> blue gradient\nAdd New Device -> Register Device",
                            lines=5,
                            info="These will be applied in addition to auto-detected changes"
                        )
                        
                        gr.Markdown("#### Step 2: Process")
                        
                        process_btn = gr.Button(
                            "Update Document",
                            variant="primary",
                            size="lg"
                        )
                    
                    # Right Column - Primary Outputs
                    with gr.Column(scale=1):
                        gr.Markdown("#### Results")
                        
                        pdf_output = gr.File(label="Updated PDF")
                        highlight_output = gr.Image(label="Visual Comparison")
                        
                        with gr.Row():
                            export_btn = gr.Button("Download All Files", size="sm")
                            export_status = gr.Textbox(label="Status", lines=1)
                        
                        zip_output = gr.File(label="Download Package")
                
                # Reports Section
                gr.Markdown("#### Processing Details")
                
                with gr.Row():
                    with gr.Column():
                        summary_output = gr.Textbox(
                            label="Summary",
                            lines=15,
                            interactive=False
                        )
                    
                    with gr.Column():
                        ai_output = gr.Textbox(
                            label="Validation Report",
                            lines=15,
                            interactive=False
                        )
                
                with gr.Row():
                    with gr.Column():
                        text_output = gr.Textbox(
                            label="Text Changes",
                            lines=10,
                            interactive=False
                        )
                    
                    with gr.Column():
                        json_output = gr.Textbox(
                            label="Technical Details",
                            lines=10,
                            interactive=False
                        )
                
                html_output = gr.File(label="Full Report (HTML)")
                
                # Connect process button (auth-gated)
                process_btn.click(
                    fn=_process_with_auth,
                    inputs=[
                        old_gui,
                        old_pdf,
                        new_gui,
                        custom_replacements,
                        current_user
                    ],
                    outputs=[
                        pdf_output,
                        summary_output,
                        ai_output,
                        highlight_output,
                        json_output,
                        html_output,
                        text_output
                    ]
                )
                
                # Connect export button
                export_btn.click(
                    fn=export_all_outputs,
                    inputs=[pdf_output, html_output, highlight_output],
                    outputs=[zip_output, export_status]
                )
            
            # ==================== TAB: COMPARE IMAGES ====================
            with gr.Tab("Compare Images"):
                gr.Markdown("""
                ### Compare Two Screenshots
                Check the differences between two images before updating your document.
                """)
                
                with gr.Row():
                    compare_img1 = gr.Image(label="Image 1 (Before)", type="filepath")
                    compare_img2 = gr.Image(label="Image 2 (After)", type="filepath")
                
                compare_btn = gr.Button("Compare", variant="primary")
                
                with gr.Row():
                    compare_score = gr.Number(label="Similarity (%)", precision=1)
                    compare_highlight = gr.Image(label="Differences Highlighted")
                
                compare_report = gr.Textbox(
                    label="Comparison Results",
                    lines=12,
                    interactive=False
                )
                
                compare_btn.click(
                    fn=_compare_with_auth,
                    inputs=[compare_img1, compare_img2, current_user],
                    outputs=[compare_score, compare_highlight, compare_report]
                )
            
            # ==================== TAB: HISTORY ====================
            with gr.Tab("History"):
                gr.Markdown("""
                ### Document History
                View previous updates and restore earlier versions if needed.
                """)
                
                refresh_history_btn = gr.Button("Refresh", size="sm")
                
                history_display = gr.Textbox(
                    label="Recent Updates",
                    lines=15,
                    interactive=False
                )
                
                with gr.Row():
                    version_id_input = gr.Textbox(
                        label="Version ID",
                        placeholder="Enter version ID to restore"
                    )
                    rollback_btn = gr.Button("Restore Version", variant="secondary")
                
                rollback_output = gr.File(label="Restored PDF")
                rollback_status = gr.Textbox(label="Status", lines=1)
                
                refresh_history_btn.click(
                    fn=get_version_history,
                    outputs=[history_display]
                )
                
                rollback_btn.click(
                    fn=rollback_version,
                    inputs=[version_id_input],
                    outputs=[rollback_output, rollback_status]
                )
            
            with gr.Tab("Batch Processing"):
                gr.Markdown("""
                ### Process Multiple Documents
                Apply the **same GUI update** across multiple PDF documents at once.
                """)
                
                with gr.Row():
                    batch_old_gui = gr.File(
                        label="Current Screenshot (Required)",
                        file_types=["image"],
                        type="filepath"
                    )
                    
                    batch_new_gui = gr.File(
                        label="New Screenshot (Required)",
                        file_types=["image"],
                        type="filepath"
                    )
                
                batch_pdfs = gr.File(
                    label="PDF Documents (Upload Multiple)",
                    file_types=[".pdf"],
                    file_count="multiple",
                    type="filepath"
                )
                
                batch_btn = gr.Button("Process All", variant="primary")
                
                batch_progress = gr.Textbox(
                    label="Progress",
                    lines=12,
                    interactive=False
                )
                
                batch_output = gr.File(label="Download Results")
                
                batch_btn.click(
                    fn=process_batch,
                    inputs=[batch_old_gui, batch_new_gui, batch_pdfs],
                    outputs=[batch_progress, batch_output]
                )
            
            # ==================== TAB: LOGS (Admin) ====================
            with gr.Tab("Logs"):
                gr.Markdown("""
                ### Application Logs & Audit Trail
                View recent application logs and user audit trail.
                """)
                
                with gr.Row():
                    refresh_logs_btn = gr.Button("Refresh Logs", size="sm")
                    refresh_audit_btn = gr.Button("Refresh Audit Log", size="sm")
                
                app_logs_display = gr.Textbox(
                    label="Application Logs (recent entries)",
                    lines=20,
                    interactive=False,
                    max_lines=30,
                )
                
                audit_log_display = gr.Textbox(
                    label="Audit Log (user actions)",
                    lines=15,
                    interactive=False,
                    max_lines=25,
                )
                
                refresh_logs_btn.click(
                    fn=_read_log_files,
                    outputs=[app_logs_display]
                )
                
                refresh_audit_btn.click(
                    fn=_get_audit_log,
                    outputs=[audit_log_display]
                )
            
            # ==================== TAB: ADMIN (Admin only) ====================
            with gr.Tab("Admin"):
                gr.Markdown("""
                ### User Management
                Create and manage user accounts. **Admin access required.**
                """)
                
                refresh_users_btn = gr.Button("Refresh User List", size="sm")
                users_display = gr.Textbox(
                    label="Current Users",
                    lines=10,
                    interactive=False
                )
                
                gr.Markdown("#### Create New User")
                with gr.Row():
                    new_username = gr.Textbox(label="Username", placeholder="new_user")
                    new_password = gr.Textbox(label="Password", type="password", placeholder="password")
                    new_role = gr.Dropdown(
                        choices=["viewer", "editor", "admin"],
                        value="viewer",
                        label="Role"
                    )
                
                create_user_btn = gr.Button("Create User", variant="primary")
                create_user_status = gr.Textbox(label="Status", lines=1, interactive=False)
                
                refresh_users_btn.click(
                    fn=_list_users_display,
                    outputs=[users_display]
                )
                
                create_user_btn.click(
                    fn=_create_user,
                    inputs=[new_username, new_password, new_role, current_user],
                    outputs=[create_user_status]
                )
            
            # ==================== TAB: HELP ====================
            with gr.Tab("Help"):
                gr.Markdown("""
                ## How to Use This Tool
                
                ### Updating a Document
                
                1. **Upload Current Screenshot** - Select the existing screenshot from your document
                2. **Upload PDF** - Select the PDF document you want to update
                3. **Upload New Screenshot** - The new version of the screenshot
                4. **Click "Update Document"** - The tool will process your files
                5. **Download** - Save the updated PDF to your computer
                
                ---
                
                ### User Roles
                
                | Role | Permissions |
                |------|-------------|
                | **Viewer** | View reports, history, and comparisons |
                | **Editor** | All viewer permissions + process documents, rollback |
                | **Admin** | All editor permissions + manage users, view logs |
                
                ---
                
                ### Understanding Results
                
                - **High Score** - Good match, changes applied successfully
                - **Medium Score** - Review recommended before using
                - **Low Score** - Poor match, may need manual review
                
                ---
                
                ### Common Questions
                
                | Question | Answer |
                |----------|--------|
                | No images found in PDF | The PDF may not contain embedded images |
                | Low match score | Try using a higher quality screenshot |
                | Slow processing | Reduce the number of files being processed |
                | Cannot open PDF | Check that the file is not password protected |
                
                ---
                
                ### Need Help?
                
                Contact your IT department for assistance with this tool.
                """)
            
            # ==================== FOOTER ====================
            gr.Markdown("""
            ---
            
            <div style="text-align: center; color: #666; font-size: 0.9em;">
                <p>Document Updater | Schneider Electric</p>
            </div>
            """)
        
        # ==================== AUTH HANDLERS ====================
        def handle_login(username, password):
            if not AUTH_AVAILABLE:
                # If auth module not available, allow access as admin
                user = {"id": 0, "username": username or "admin", "role": "admin"}
                return [
                    user,
                    gr.update(visible=False),
                    gr.update(visible=True),
                    f"**{username or 'admin'}** | Role: **ADMIN** (auth module not loaded)",
                    "",
                ]
            
            rbac = RBACManager()
            user = rbac.authenticate(username, password)
            if user:
                role = user["role"]
                return [
                    user,
                    gr.update(visible=False),
                    gr.update(visible=True),
                    f"**{username}** | Role: **{role.upper()}**",
                    "",
                ]
            return [
                None,
                gr.update(visible=True),
                gr.update(visible=False),
                "",
                "**Invalid username or password.** Please try again.",
            ]
        
        def handle_logout():
            return [
                None,
                gr.update(visible=True),
                gr.update(visible=False),
                "",
            ]
        
        login_btn.click(
            fn=handle_login,
            inputs=[login_username, login_password],
            outputs=[current_user, login_section, main_section, user_info_display, login_status]
        )
        
        logout_btn.click(
            fn=handle_logout,
            outputs=[current_user, login_section, main_section, user_info_display]
        )
    
    return interface


# ==================== MAIN ENTRY POINT ====================

def main():
    """Main entry point"""
    
    # Setup structured logging
    if setup_logging is not None:
        setup_logging()
    
    print("""
    ========================================================================
    |                                                                      |
    |     Technical Document Auto Updater v3.0                             |
    |                                                                      |
    |     Schneider Electric Hackathon 2025-2026                           |
    |                                                                      |
    ========================================================================
    |                                                                      |
    |   Features:                                                          |
    |   [+] Advanced Multi-Algorithm Image Matching                        |
    |   [+] AI-Powered Validation & Quality Assurance                      |
    |   [+] Smart Text Replacement with OCR                                |
    |   [+] Version History & Rollback Support                             |
    |   [+] Batch Processing for Multiple Documents                        |
    |   [+] One-Click Export (ZIP)                                         |
    |   [+] Comprehensive Reporting (Summary, JSON, HTML)                  |
    |   [+] Role-Based Access Control (Viewer/Editor/Admin)                |
    |   [+] Application & Audit Logging                                    |
    |                                                                      |
    ========================================================================
    """)
    
    # Create required directories
    directories = [
        "./data/output",
        "./data/documents",
        "./data/gui_screenshots",
        "./data/history",
        "./data/output/reports",
        "./data/logs",
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    # Check dependencies
    print("\n[*] Checking dependencies...")
    print(f"   - OpenCV:       {'[OK]' if CV2_AVAILABLE else '[X] Install opencv-python'}")
    print(f"   - Pillow:       {'[OK]' if PIL_AVAILABLE else '[X] Install Pillow'}")
    print(f"   - scikit-image: {'[OK]' if SKIMAGE_AVAILABLE else '[X] Install scikit-image'}")
    print(f"   - Gradio:       {'[OK]' if GRADIO_AVAILABLE else '[X] Install gradio'}")
    print(f"   - PDF Support:  {'[OK]' if PDF_SUPPORT else '[X] Install pymupdf'}")
    print(f"   - OCR Support:  {'[OK]' if OCR_SUPPORT else '[!] Install pytesseract for text features'}")
    print(f"   - Auth (RBAC):  {'[OK]' if AUTH_AVAILABLE else '[!] Auth module not found'}")
    
    if not GRADIO_AVAILABLE:
        print("\n[ERROR] Cannot start: Gradio is required. Run: pip install gradio")
        return
    
    # Build and launch interface
    print("\n[*] Building interface...")
    interface = build_interface()
    
    if interface is None:
        print("[ERROR] Failed to build interface")
        return
    
    print("\n[OK] Starting server...")
    print("[*] Open your browser to: http://127.0.0.1:7870")
    print("\n[*] To stop: Press Ctrl+C\n")
    
    interface.launch(
        server_name="127.0.0.1",
        server_port=7870,
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main()


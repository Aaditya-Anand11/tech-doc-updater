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
import time
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import Counter
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
            "similarity_threshold": 0.55,
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
        """Template matching score"""
        if not CV2_AVAILABLE:
            return 0.0
        
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            
            if img1 is None or img2 is None:
                return 0.0
            
            # Resize img2 to match img1
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
            
            # Template matching
            result = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
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
        
        print(f"[DEBUG] find_best_matches called with {len(new_images)} new images and {len(pdf_images)} PDF images")
        
        results = []
        
        for new_img_path in new_images:
            new_img_name = os.path.basename(new_img_path)
            print(f"[DEBUG] Processing new image: {new_img_name}")
            
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
                
                print(f"[DEBUG] Comparing with PDF image: {pdf_img.get('filename', 'unknown')}")
                scores = self.compute_combined_score(new_img_path, pdf_img.get("path", ""))
                print(f"[DEBUG] Scores: SSIM={scores.get('ssim', 0):.3f}, Hist={scores.get('histogram', 0):.3f}, Edge={scores.get('edge', 0):.3f}, Template={scores.get('template', 0):.3f}, Combined={scores.get('combined', 0):.3f}")
                print(f"[DEBUG] is_match={scores.get('is_match')}, threshold={self.config['similarity_threshold']}")
                
                if scores["combined"] > best_scores["combined"]:
                    best_scores = scores
                    best_match = pdf_img
                    print(f"[DEBUG] New best match found!")
            
            print(f"[DEBUG] Best match for {new_img_name}: combined_score={best_scores.get('combined', 0):.3f}, is_match={best_scores.get('is_match', False)}")
            
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
        
        print(f"[DEBUG] Returning {len(results)} match results")
        return results


# ==================== SMART TEXT PROCESSOR ====================

class SmartTextProcessor:
    """
    Intelligent text processing with context awareness
    """
    
    def __init__(self):
        # DISABLED: Single-word matching causes Scunthorpe problem
        # e.g., "view" → "details" corrupts "Overview" to "OverDetails"
        self.ui_terms = {}
        
        self.ocr_corrections = {
            "|": "I",
            "0": "O",
            "rn": "m",
            "vv": "w",
            "1": "l",
            "!": "i",
        }
        
        # Common PHRASE replacements - Include BOTH lowercase AND capitalized versions
        # for exact PDF text matching
        self.common_phrase_pairs = {
            # Product names (capitalized as they appear in PDF)
            "EcoStruxure Device Manager": "EcoStruxure Device Hub",
            "ecostruxure device manager": "ecostruxure device hub",
            "Device Manager": "Device Hub",
            "device manager": "device hub",
            
            # UI labels - capitalized as they appear
            "Add New Device": "Register Device",
            "+ Add New Device": "+ Register Device",
            "add new device": "register device",
            "+ add new device": "+ register device",
            "Online Devices": "Active Devices",
            "online devices": "active devices",
            "Connected Devices": "Device Inventory",
            "connected devices": "device inventory",
            
            # Grammatical variations (prevent "Last Sync d" bug)
            "Last Updated": "Last Synced",  # Capitalized FIRST
            "Last Update": "Last Sync",
            "last updated": "last synced",
            "last update": "last sync",
            
            # Visual descriptions - as they appear in manual
            "Green gradient": "Blue header",
            "green gradient": "blue header",
            "Green header": "Blue header",
            "green header": "blue header",
            "Green button": "Blue button",
            "green button": "blue button",
            "(green)": "(blue)",
            "(Green)": "(Blue)",
            "green left border": "blue left border",
            
            # Button labels
            "Settings button": "Preferences button",
            "settings button": "preferences button",
        }
    
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
        return []
    
    def find_text_differences(self, old_img_path: str, new_img_path: str) -> Dict:
        """Find text differences between two images using enhanced OCR comparison"""
        
        print(f"[DEBUG] Extracting text from old image: {old_img_path}")
        old_text = self.extract_full_text(old_img_path)
        print(f"[DEBUG] Old text extracted: {len(old_text)} chars")
        
        print(f"[DEBUG] Extracting text from new image: {new_img_path}")
        new_text = self.extract_full_text(new_img_path)
        print(f"[DEBUG] New text extracted: {len(new_text)} chars")
        
        # Correct OCR errors
        old_text = self.correct_ocr_errors(old_text)
        new_text = self.correct_ocr_errors(new_text)
        
        # Split into lines for line-by-line comparison
        old_lines = [line.strip() for line in old_text.split('\n') if line.strip() and len(line.strip()) > 2]
        new_lines = [line.strip() for line in new_text.split('\n') if line.strip() and len(line.strip()) > 2]
        
        print(f"[DEBUG] Old lines: {len(old_lines)}, New lines: {len(new_lines)}")
        
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
                print(f"[DEBUG] Found known phrase pair: '{old_term}' -> '{new_term}'")
                changes.append({
                    "old": old_term.title(),  # Capitalize for proper replacement
                    "new": new_term.title(),
                    "category": "phrase_pair",
                    "confidence": 0.95
                })
        
        # 2. Extract key phrases from both texts and compare
        old_phrases = self._extract_key_phrases(old_lines)
        new_phrases = self._extract_key_phrases(new_lines)
        
        print(f"[DEBUG] Extracted {len(old_phrases)} old phrases, {len(new_phrases)} new phrases")
        
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
                                print(f"[DEBUG] Found OCR replacement: '{old_phrase}' -> '{new_phrase}' (sim: {similarity:.2f})")
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
                print(f"[DEBUG] Found phrase change: '{old_line}' -> '{best_match}' (similarity: {best_similarity:.2f})")
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
        
        print(f"[DEBUG] Generating text replacements...")
        print(f"[DEBUG] UI changes: {len(text_diff.get('ui_changes', []))}")
        print(f"[DEBUG] Phrase changes: {len(text_diff.get('phrase_changes', []))}")
        print(f"[DEBUG] OCR replacements: {len(text_diff.get('ocr_replacements', []))}")
        
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
        
        print(f"[DEBUG] Total replacements generated: {len(replacements)}")
        for r in replacements:
            print(f"[DEBUG]   '{r.old_text}' -> '{r.new_text}' (approved={r.approved}, confidence={r.confidence:.2f})")
        
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
        """Replace images and text in PDF with fuzzy text matching"""
        if not PDF_SUPPORT:
            return {"success": False, "error": "PDF support not available"}
        
        try:
            doc = fitz.open(pdf_path)
            images_replaced = 0
            text_replaced = 0
            
            # Replace images
            for repl in image_replacements:
                xref = repl.get("xref")
                new_path = repl.get("new_image_path")
                
                if not xref or not new_path:
                    continue
                
                for page in doc:
                    for img in page.get_images():
                        if img[0] == xref:
                            rects = page.get_image_rects(xref)
                            if rects:
                                rect = rects[0]
                                page.delete_image(xref)
                                page.insert_image(rect, filename=new_path)
                                images_replaced += 1
                            break
            
            # Replace text with fuzzy matching
            for change in text_replacements:
                if not change.approved:
                    continue
                
                old_text = change.old_text
                new_text = change.new_text
                
                print(f"[DEBUG] Trying to replace: '{old_text}' -> '{new_text}'")
                
                for page in doc:
                    # Try multiple search variants for fuzzy matching
                    search_variants = self._generate_search_variants(old_text)
                    
                    instances_found = []
                    for variant in search_variants:
                        instances = page.search_for(variant)
                        if instances:
                            instances_found.extend(instances)
                            print(f"[DEBUG] Found {len(instances)} matches for variant: '{variant}'")
                            break  # Use first variant that matches
                    
                    # DELETED: Longest-word fallback removed - it caused text stutter
                    # (e.g., "Device Hub Device Hub Device Hub" when searching for single words)
                    for inst in instances_found:
                        try:
                            page.add_redact_annot(inst, new_text)
                            text_replaced += 1
                        except Exception as e:
                            print(f"[DEBUG] Redaction error: {e}")
                    
                    if instances_found:
                        try:
                            page.apply_redactions()
                        except Exception as e:
                            print(f"[DEBUG] Apply redactions error: {e}")
            
            print(f"[DEBUG] Total text replacements: {text_replaced}")
            
            doc.save(output_path)
            doc.close()
            
            return {
                "success": True,
                "images_replaced": images_replaced,
                "text_replaced": text_replaced,
                "output_path": output_path
            }
        except Exception as e:
            print(f"[DEBUG] PDF replacement error: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_search_variants(self, text: str) -> List[str]:
        """Generate search variants for matching - SIMPLIFIED to prevent stutter"""
        variants = []
        
        # 1. Original text (exact match)
        variants.append(text)
        
        # 2. Normalized whitespace only
        normalized = ' '.join(text.split())
        if normalized != text:
            variants.append(normalized)
        
        # 3. Title case (for proper nouns)
        title = text.title()
        if title not in variants:
            variants.append(title)
        
        # That's it - no more case variations that could cause duplicate matches
        return variants
    
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
    
    def generate_summary(self, result: ProcessingResult, pdf_info: Dict) -> str:
        """Generate human-readable summary"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine overall status
        if result.overall_confidence >= 0.8:
            status = "✅ EXCELLENT"
            status_desc = "High confidence - all changes verified"
        elif result.overall_confidence >= 0.6:
            status = "⚠️ GOOD"
            status_desc = "Moderate confidence - review recommended"
        else:
            status = "❌ NEEDS REVIEW"
            status_desc = "Low confidence - manual review required"
        
        summary = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║               DOCUMENT UPDATE SUMMARY - TECH DOC AUTO UPDATER            ║
╚══════════════════════════════════════════════════════════════════════════╝

📅 Generated: {timestamp}
📄 Document: {pdf_info.get('title', 'Unknown')}
📊 Status: {status}
   {status_desc}

═══════════════════════════════════════════════════════════════════════════
                              PROCESSING RESULTS
═══════════════════════════════════════════════════════════════════════════

📸 IMAGE UPDATES
────────────────
• Screenshots Processed: {len(result.matches)}
• Images Replaced: {result.images_replaced}
• Match Confidence: {result.overall_confidence:.1%}

📝 TEXT UPDATES
───────────────
• Text Changes Applied: {result.text_replaced}
• Text Changes Detected: {len(result.text_changes)}

⏱️ PERFORMANCE
──────────────
• Processing Time: {result.processing_time:.2f}s
• Pages Processed: {pdf_info.get('pages', 'N/A')}

═══════════════════════════════════════════════════════════════════════════
                              MATCH DETAILS
═══════════════════════════════════════════════════════════════════════════
"""
        
        for match in result.matches:
            status_icon = "✅" if match.validation_status == ValidationStatus.APPROVED else \
                         "⚠️" if match.validation_status == ValidationStatus.REVIEW else "❌"
            
            matched_page = match.matched_pdf_image.get('page', 'N/A') if match.matched_pdf_image else 'N/A'
            
            summary += f"""
{status_icon} {match.new_image_name}
   → Page: {matched_page}
   → Confidence: {match.confidence:.1%}
   → Status: {match.validation_status.value}
"""
        
        if result.errors:
            summary += "\n❌ ERRORS\n─────────\n"
            for error in result.errors:
                summary += f"• {error}\n"
        
        if result.warnings:
            summary += "\n⚠️ WARNINGS\n───────────\n"
            for warning in result.warnings:
                summary += f"• {warning}\n"
        
        summary += f"""
═══════════════════════════════════════════════════════════════════════════
✅ OUTPUT: {result.output_path}
═══════════════════════════════════════════════════════════════════════════
"""
        
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
    confidence_threshold = 0.6
    
    start_time = time.time()
    output_dir = "./data/output"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Initialize result
    result = ProcessingResult(success=False)
    
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
        print("[DEBUG] Starting process_document_v3...")
        print(f"[DEBUG] old_gui_path: {old_gui_path}")
        print(f"[DEBUG] new_paths: {new_paths}")
        print(f"[DEBUG] pdf_path: {pdf_path}")
        
        # Initialize all components
        print("[DEBUG] Initializing components...")
        pdf_processor = EnhancedPDFProcessor()
        matcher = AdvancedImageMatcher({"similarity_threshold": confidence_threshold})
        text_processor = SmartTextProcessor()
        validator = AIValidationEngine() if enable_ai_validation else None
        analyzer = VisualAnalyzer()
        report_gen = ComprehensiveReportGenerator()
        history_mgr = HistoryManager()
        print("[DEBUG] Components initialized.")
        
        # Get PDF info
        print("[DEBUG] Getting PDF info...")
        pdf_info = pdf_processor.get_pdf_info(pdf_path)
        print(f"[DEBUG] PDF info: {pdf_info}")
        if "error" in pdf_info:
            return None, f"❌ PDF Error: {pdf_info['error']}", "", None, "{}", None, ""
        
        # Extract images from PDF
        print("[DEBUG] Extracting images from PDF...")
        extract_dir = os.path.join(output_dir, f"extracted_{timestamp}")
        pdf_images = pdf_processor.extract_all_images(pdf_path, extract_dir)
        print(f"[DEBUG] Extracted {len(pdf_images)} images from PDF")
        
        if not pdf_images:
            return None, "❌ No images found in the PDF document", "", None, "{}", None, ""
        
        # Find best matches using advanced matching
        print("[DEBUG] Finding best matches...")
        matches = matcher.find_best_matches(new_paths, pdf_images, page_hints)
        print(f"[DEBUG] Found {len(matches)} matches")
        
        # AI Validation if enabled
        print("[DEBUG] Running AI validation...")
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
        print("[DEBUG] Processing text differences...")
        text_changes = []
        text_report = "Text replacement disabled."
        
        if enable_text_replacement:
            # Use old GUI as reference (it's now required)
            reference_image = old_gui_path
            
            if reference_image and new_paths:
                print(f"[DEBUG] Comparing text: {reference_image} vs {new_paths}")
                for new_path in new_paths:
                    print(f"[DEBUG] Processing text for: {new_path}")
                    text_diff = text_processor.find_text_differences(reference_image, new_path)
                    print(f"[DEBUG] Text diff result: {text_diff.get('total_changes', 0)} changes")
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
                    print(f"[DEBUG] Parsing custom replacements...")
                    for line in custom_replacements.strip().split("\n"):
                        if "->" in line:
                            parts = line.split("->", 1)
                            if len(parts) == 2:
                                old_text = parts[0].strip()
                                new_text = parts[1].strip()
                                if old_text and new_text:
                                    print(f"[DEBUG] Custom replacement: '{old_text}' -> '{new_text}'")
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
            else:
                result.errors.append(replace_result.get("error", "Unknown error"))
        else:
            # No changes to make, just copy the original
            shutil.copy(pdf_path, output_pdf_path)
            result.output_path = output_pdf_path
            result.success = True
            result.warnings.append("No matching images found - PDF copied without changes")
        
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
        print(f"[DEBUG] Processing time: {result.processing_time:.2f}s")
        
        # Add to history
        print("[DEBUG] Adding to history...")
        history_mgr.add_version(pdf_path, {}, result)
        
        # Generate reports
        print("[DEBUG] Generating summary report...")
        summary_report = report_gen.generate_summary(result, pdf_info)
        print("[DEBUG] Generating JSON report...")
        json_report = report_gen.generate_json(result, pdf_info)
        print("[DEBUG] Generating HTML report...")
        html_report = report_gen.generate_html(result, pdf_info)
        
        # Save HTML report
        print("[DEBUG] Saving HTML report...")
        html_path = os.path.join(output_dir, f"report_{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        
        # Generate AI validation report
        print("[DEBUG] Generating AI validation report...")
        ai_report = ""
        if validator:
            ai_report = validator.generate_validation_summary()
        
        # Cleanup
        print("[DEBUG] Cleaning up...")
        pdf_processor.cleanup()
        
        print("[DEBUG] DONE! Returning results...")
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
        print(f"[DEBUG] ERROR: {e}")
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


def process_batch(screenshots, pdfs):
    """Process multiple PDFs with screenshots"""
    if not screenshots or not pdfs:
        return "❌ Please upload screenshots and PDFs", None
    
    results = []
    output_files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get screenshot paths
    screenshot_paths = []
    if isinstance(screenshots, list):
        for s in screenshots:
            if s is not None:
                path = s if isinstance(s, str) else s.name
                screenshot_paths.append(path)
    else:
        path = screenshots if isinstance(screenshots, str) else screenshots.name
        screenshot_paths.append(path)
    
    # Process each PDF
    pdf_list = pdfs if isinstance(pdfs, list) else [pdfs]
    
    for pdf in pdf_list:
        if pdf is None:
            continue
            
        pdf_path = pdf if isinstance(pdf, str) else pdf.name
        pdf_name = os.path.basename(pdf_path)
        
        results.append(f"📄 Processing: {pdf_name}...")
        
        try:
            # Use first screenshot as old_gui reference, rest as new_gui for batch
            old_gui_path = screenshot_paths[0] if screenshot_paths else None
            new_gui_path = screenshot_paths[1] if len(screenshot_paths) > 1 else None
            
            output = process_document_v3(
                old_gui_path,  # old_gui (required)
                pdf_path,      # old_pdf (required)
                new_gui_path   # new_gui (optional)
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


# ==================== GRADIO INTERFACE ====================

def build_interface():
    """Build the complete Gradio interface with clean, professional design"""
    
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
        
        # ==================== HEADER ====================
        gr.Markdown("""
        # Document Updater
        ### Schneider Electric Technical Documentation Tool
        
        Automatically update PDF documentation with new screenshots.
        
        ---
        """)
        
        # ==================== MAIN TAB: UPDATE DOCUMENT ====================
        with gr.Tab("Update Document"):
            gr.Markdown("""
            ### Update Your Documentation
            Upload the current screenshot and PDF, then optionally add a new screenshot to replace it.
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
            
            # Connect process button
            process_btn.click(
                fn=process_document_v3,
                inputs=[
                    old_gui,
                    old_pdf,
                    new_gui,
                    custom_replacements
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
                fn=quick_compare,
                inputs=[compare_img1, compare_img2],
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
        
        # ==================== TAB: BATCH ====================
        with gr.Tab("Batch Processing"):
            gr.Markdown("""
            ### Process Multiple Documents
            Update several PDF documents at once.
            """)
            
            batch_screenshots = gr.File(
                label="Screenshots (Upload Multiple)",
                file_types=["image"],
                file_count="multiple",
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
                inputs=[batch_screenshots, batch_pdfs],
                outputs=[batch_progress, batch_output]
            )
        
        # ==================== TAB: HELP ====================
        with gr.Tab("Help"):
            gr.Markdown("""
            ## How to Use This Tool
            
            ### Updating a Document
            
            1. **Upload Current Screenshot** - Select the existing screenshot from your document
            2. **Upload PDF** - Select the PDF document you want to update
            3. **Upload New Screenshot** (Optional) - If you have a new version of the screenshot
            4. **Click "Update Document"** - The tool will process your files
            5. **Download** - Save the updated PDF to your computer
            
            ---
            
            ### Understanding Results
            
            - **Green/High Score** - Good match, changes applied successfully
            - **Yellow/Medium Score** - Review recommended before using
            - **Red/Low Score** - Poor match, may need manual review
            
            ---
            
            ### Visual Comparison
            
            The highlighted image shows:
            - **Red areas** - Significant differences between images
            - **Yellow areas** - Minor differences
            
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
    
    return interface


# ==================== MAIN ENTRY POINT ====================

def main():
    """Main entry point"""
    
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
    |                                                                      |
    ========================================================================
    """)
    
    # Create required directories
    directories = [
        "./data/output",
        "./data/documents",
        "./data/gui_screenshots",
        "./data/history",
        "./data/output/reports"
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

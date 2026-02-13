"""
Image Comparator Module

Multi-algorithm image comparison engine.
Extracted from AdvancedImageMatcher in app_main.py.

Supports: SSIM, Histogram, Edge, Template matching, Perceptual hash.
"""

import os
import logging
from typing import List, Dict, Optional

from docsync.models import MatchResult, ValidationStatus

logger = logging.getLogger("docsync.image_comparator")

# Optional dependencies
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from skimage.metrics import structural_similarity as ssim
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False


class ImageComparator:
    """
    Multi-algorithm image comparison engine.
    
    Uses a weighted combination of SSIM, histogram correlation,
    edge structure, and template matching to produce a robust
    similarity score.
    """

    def __init__(self, config: Dict = None):
        default_config = {
            "ssim_weight": 0.35,
            "histogram_weight": 0.20,
            "edge_weight": 0.25,
            "template_weight": 0.20,
            "similarity_threshold": 0.55,
            "high_confidence_threshold": 0.80,
        }
        self.config = {**default_config, **(config or {})}

    # ─── Individual algorithms ──────────────────────────────────

    def compute_ssim(self, img1_path: str, img2_path: str) -> float:
        """Structural Similarity Index Measure"""
        if not CV2_AVAILABLE or not SKIMAGE_AVAILABLE:
            return 0.0
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            if img1 is None or img2 is None:
                return 0.0
            size = (256, 256)
            img1 = cv2.resize(img1, size)
            img2 = cv2.resize(img2, size)
            score, _ = ssim(img1, img2, full=True)
            return max(0, float(score))
        except Exception as e:
            logger.error(f"SSIM error: {e}")
            return 0.0

    def compute_histogram(self, img1_path: str, img2_path: str) -> float:
        """Color histogram correlation"""
        if not CV2_AVAILABLE:
            return 0.0
        try:
            img1 = cv2.imread(img1_path)
            img2 = cv2.imread(img2_path)
            if img1 is None or img2 is None:
                return 0.0
            hist1 = cv2.calcHist([img1], [0, 1, 2], None, [8, 8, 8],
                                  [0, 256, 0, 256, 0, 256])
            hist2 = cv2.calcHist([img2], [0, 1, 2], None, [8, 8, 8],
                                  [0, 256, 0, 256, 0, 256])
            cv2.normalize(hist1, hist1)
            cv2.normalize(hist2, hist2)
            score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            return max(0, float(score))
        except Exception:
            return 0.0

    def compute_edge_similarity(self, img1_path: str, img2_path: str) -> float:
        """Edge structure comparison using Canny + SSIM"""
        if not CV2_AVAILABLE or not SKIMAGE_AVAILABLE:
            return 0.0
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            if img1 is None or img2 is None:
                return 0.0
            size = (256, 256)
            img1 = cv2.resize(img1, size)
            img2 = cv2.resize(img2, size)
            edges1 = cv2.Canny(img1, 50, 150)
            edges2 = cv2.Canny(img2, 50, 150)
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
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
            result = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max(0, float(max_val))
        except Exception:
            return 0.0

    def compute_perceptual_hash(self, img1_path: str, img2_path: str) -> float:
        """Perceptual hash (dHash) similarity"""
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
            distance = sum(h1 != h2 for h1, h2 in zip(hash1, hash2))
            return 1 - (distance / len(hash1))
        except Exception:
            return 0.0

    # ─── Combined scoring ──────────────────────────────────────

    def compute_combined_score(self, img1_path: str, img2_path: str) -> Dict:
        """Compute weighted combined similarity score"""
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
            "is_high_confidence": combined >= self.config["high_confidence_threshold"],
        }

    # ─── Batch matching ──────────────────────────────────────

    def find_best_matches(
        self,
        new_images: List[str],
        pdf_images: List[Dict],
        page_hints: Dict[str, int] = None,
    ) -> List[MatchResult]:
        """
        Find the best PDF image match for each new screenshot.
        
        Args:
            new_images: Paths to new GUI screenshots
            pdf_images: Image metadata dicts extracted from the PDF
            page_hints: Optional mapping of image name patterns to page numbers
            
        Returns:
            List of MatchResult with best matches
        """
        results = []

        for new_img_path in new_images:
            new_img_name = os.path.basename(new_img_path)
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
                if target_page is not None and pdf_img.get("page") != target_page:
                    continue

                scores = self.compute_combined_score(
                    new_img_path, pdf_img.get("path", "")
                )

                if scores["combined"] > best_scores["combined"]:
                    best_scores = scores
                    best_match = pdf_img

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
                confidence=best_scores.get("combined", 0),
            )

            if best_scores.get("is_high_confidence"):
                result.validation_status = ValidationStatus.APPROVED
            elif best_scores.get("is_match"):
                result.validation_status = ValidationStatus.REVIEW
            else:
                result.validation_status = ValidationStatus.REJECTED

            results.append(result)

        logger.info(f"Matched {len(results)} images "
                    f"({sum(1 for r in results if r.is_good_match)} good matches)")
        return results

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

try:
    import pytesseract
    # Configure Tesseract path for Windows
    _TESSERACT_PATHS = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(
            os.getenv('USERNAME', 'user')
        ),
    ]
    _tesseract_found = False
    for _p in _TESSERACT_PATHS:
        if os.path.exists(_p):
            pytesseract.pytesseract.tesseract_cmd = _p
            _tesseract_found = True
            break
    try:
        pytesseract.get_tesseract_version()
        TESSERACT_AVAILABLE = True
    except Exception:
        TESSERACT_AVAILABLE = False
except ImportError:
    TESSERACT_AVAILABLE = False


class ImageComparator:
    """
    Multi-algorithm image comparison engine.
    
    Uses a weighted combination of SSIM, histogram correlation,
    edge structure, and template matching to produce a robust
    similarity score.
    """

    def __init__(self, config: Dict = None, gemini_config: Dict = None, ollama_config: Dict = None):
        default_config = {
            "ssim_weight": 0.25,
            "histogram_weight": 0.15,
            "edge_weight": 0.20,
            "template_weight": 0.15,
            "phash_weight": 0.25,
            "ocr_weight": 0.25,
            "similarity_threshold": 0.55,
            "high_confidence_threshold": 0.80,
            "aspect_ratio_tolerance": 0.4,
            "min_area_ratio": 0.05,
            "ai_top_n": 3,
        }
        self.config = {**default_config, **(config or {})}

        # AI comparator (Gemini or Ollama — first available wins)
        self.ai_comparator = None
        self.ai_weight = 0.0
        self.ai_name = None

        # Try Gemini first
        if gemini_config and gemini_config.get("enabled"):
            try:
                from docsync.core.gemini_comparator import GeminiComparator
                gc = GeminiComparator(
                    api_key=gemini_config.get("api_key", ""),
                    model=gemini_config.get("model", "gemini-2.0-flash"),
                )
                if gc.is_available:
                    self.ai_comparator = gc
                    self.ai_weight = gemini_config.get("weight", 0.25)
                    self.ai_name = "Gemini"
                    logger.info(f"Gemini AI matching enabled (weight={self.ai_weight})")
            except Exception as e:
                logger.warning(f"Could not init Gemini: {e}")

        # Fallback to Ollama vision
        if not self.ai_comparator and ollama_config and ollama_config.get("enabled"):
            try:
                from docsync.core.ollama_comparator import OllamaComparator
                oc = OllamaComparator(
                    base_url=ollama_config.get("base_url", "http://localhost:11434"),
                    model=ollama_config.get("vision_model", "llava"),
                )
                if oc.is_available:
                    self.ai_comparator = oc
                    self.ai_weight = ollama_config.get("weight", 0.25)
                    self.ai_name = "Ollama"
                    logger.info(f"Ollama vision matching enabled (model={oc.model}, weight={self.ai_weight})")
                else:
                    logger.info(f"Ollama vision model not available")
            except Exception as e:
                logger.warning(f"Could not init Ollama comparator: {e}")

    # ─── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _resize_keep_aspect(img, max_dim=256):
        """Resize image keeping aspect ratio, padding to square."""
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return img
        scale = max_dim / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (new_w, new_h))
        # Pad to max_dim x max_dim
        pad_top = (max_dim - new_h) // 2
        pad_bottom = max_dim - new_h - pad_top
        pad_left = (max_dim - new_w) // 2
        pad_right = max_dim - new_w - pad_left
        padded = cv2.copyMakeBorder(resized, pad_top, pad_bottom,
                                    pad_left, pad_right,
                                    cv2.BORDER_CONSTANT, value=0)
        return padded

    @staticmethod
    def _get_image_dimensions(path):
        """Get (width, height) of an image without fully loading it."""
        if not CV2_AVAILABLE:
            return None
        img = cv2.imread(path)
        if img is None:
            return None
        h, w = img.shape[:2]
        return (w, h)

    @staticmethod
    def _aspect_ratio(dims):
        """Return aspect ratio (always >= 1.0)."""
        if dims is None:
            return 1.0
        w, h = dims
        if h == 0 or w == 0:
            return 1.0
        r = w / h
        return r if r >= 1.0 else 1.0 / r

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
            img1 = self._resize_keep_aspect(img1)
            img2 = self._resize_keep_aspect(img2)
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
            img1 = self._resize_keep_aspect(img1)
            img2 = self._resize_keep_aspect(img2)
            edges1 = cv2.Canny(img1, 50, 150)
            edges2 = cv2.Canny(img2, 50, 150)
            score, _ = ssim(edges1, edges2, full=True)
            return max(0, float(score))
        except Exception:
            return 0.0

    def compute_template_match(self, img1_path: str, img2_path: str) -> float:
        """Template matching score (aspect-ratio-preserving)"""
        if not CV2_AVAILABLE:
            return 0.0
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            if img1 is None or img2 is None:
                return 0.0
            # Use aspect-ratio-preserving resize so we don't distort images
            img1 = self._resize_keep_aspect(img1)
            img2 = self._resize_keep_aspect(img2)
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

    # ─── OCR text similarity ─────────────────────────────────

    def _ocr_text(self, img_path: str) -> str:
        """Extract text from a single image, with caching."""
        if not hasattr(self, '_ocr_cache'):
            self._ocr_cache = {}
        if img_path in self._ocr_cache:
            return self._ocr_cache[img_path]
        text = ""
        if TESSERACT_AVAILABLE and PIL_AVAILABLE:
            try:
                text = pytesseract.image_to_string(
                    Image.open(img_path), config="--psm 6"
                ).strip()
            except Exception as e:
                logger.debug(f"OCR extraction error for {img_path}: {e}")
        self._ocr_cache[img_path] = text
        return text

    def compute_ocr_similarity(self, img1_path: str, img2_path: str) -> float:
        """Extract text from both images via Tesseract OCR and compare.

        Returns a 0-1 similarity score using SequenceMatcher.
        If either image yields no text the score is 0.0 (neutral).
        """
        if not TESSERACT_AVAILABLE or not PIL_AVAILABLE:
            return 0.0
        try:
            from difflib import SequenceMatcher

            text1 = self._ocr_text(img1_path)
            text2 = self._ocr_text(img2_path)

            # If neither image has readable text, OCR cannot help
            if not text1 and not text2:
                return 0.0
            # If only one has text, they are clearly different
            if not text1 or not text2:
                return 0.0

            return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        except Exception as e:
            logger.debug(f"OCR similarity error: {e}")
            return 0.0

    # ─── Combined scoring ──────────────────────────────────────

    def compute_fast_score(self, img1_path: str, img2_path: str) -> Dict:
        """Fast scoring using traditional algorithms only (no AI, no OCR).

        OCR is intentionally excluded here because it is too slow to
        run on every candidate pair.  It is applied in a separate
        refinement pass on only the top-N candidates.
        """
        ssim_score = self.compute_ssim(img1_path, img2_path)
        hist_score = self.compute_histogram(img1_path, img2_path)
        edge_score = self.compute_edge_similarity(img1_path, img2_path)
        template_score = self.compute_template_match(img1_path, img2_path)
        phash_score = self.compute_perceptual_hash(img1_path, img2_path)

        combined = (
            ssim_score * self.config["ssim_weight"] +
            hist_score * self.config["histogram_weight"] +
            edge_score * self.config["edge_weight"] +
            template_score * self.config["template_weight"] +
            phash_score * self.config["phash_weight"]
        )

        return {
            "ssim": ssim_score,
            "histogram": hist_score,
            "edge": edge_score,
            "template": template_score,
            "phash": phash_score,
            "ocr": 0.0,
            "ai_score": 0.0,
            "ai_backend": "none",
            "ai_explanation": "",
            "combined": combined,
            "is_match": combined >= self.config["similarity_threshold"],
            "is_high_confidence": combined >= self.config["high_confidence_threshold"],
        }

    def refine_with_ocr(self, img1_path: str, img2_path: str, fast_scores: Dict) -> Dict:
        """Add OCR text-similarity on top of existing fast scores."""
        ocr_score = self.compute_ocr_similarity(img1_path, img2_path)
        if ocr_score <= 0.0:
            # OCR couldn't extract text — keep fast scores unchanged
            return fast_scores

        ocr_w = self.config["ocr_weight"]
        scale = 1.0 - ocr_w
        combined = (
            fast_scores["ssim"] * self.config["ssim_weight"] * scale +
            fast_scores["histogram"] * self.config["histogram_weight"] * scale +
            fast_scores["edge"] * self.config["edge_weight"] * scale +
            fast_scores["template"] * self.config["template_weight"] * scale +
            fast_scores["phash"] * self.config["phash_weight"] * scale +
            ocr_score * ocr_w
        )

        return {
            **fast_scores,
            "ocr": ocr_score,
            "combined": combined,
            "is_match": combined >= self.config["similarity_threshold"],
            "is_high_confidence": combined >= self.config["high_confidence_threshold"],
        }

    def refine_with_ai(self, img1_path: str, img2_path: str, fast_scores: Dict) -> Dict:
        """Add AI score on top of existing fast scores (single call)."""
        if not self.ai_comparator or self.ai_weight <= 0:
            return fast_scores

        result = self.ai_comparator.compare_images(img1_path, img2_path)
        if not result["success"]:
            return {**fast_scores, "ai_backend": self.ai_name or "none"}

        ai_score = result["score"]
        ai_explanation = result.get("explanation", "")

        # Re-compute combined with AI blended in
        scale = 1.0 - self.ai_weight
        combined = (
            fast_scores["ssim"] * self.config["ssim_weight"] * scale +
            fast_scores["histogram"] * self.config["histogram_weight"] * scale +
            fast_scores["edge"] * self.config["edge_weight"] * scale +
            fast_scores["template"] * self.config["template_weight"] * scale +
            fast_scores.get("phash", 0) * self.config["phash_weight"] * scale +
            fast_scores.get("ocr", 0) * self.config["ocr_weight"] * scale +
            ai_score * self.ai_weight
        )

        return {
            **fast_scores,
            "ai_score": ai_score,
            "ai_backend": self.ai_name,
            "ai_explanation": ai_explanation,
            "combined": combined,
            "is_match": combined >= self.config["similarity_threshold"],
            "is_high_confidence": combined >= self.config["high_confidence_threshold"],
        }

    def compute_combined_score(self, img1_path: str, img2_path: str) -> Dict:
        """Compute full score (fast + OCR + AI). Used by /api/compare endpoint."""
        fast = self.compute_fast_score(img1_path, img2_path)
        with_ocr = self.refine_with_ocr(img1_path, img2_path, fast)
        return self.refine_with_ai(img1_path, img2_path, with_ocr)

    # ─── Batch matching ──────────────────────────────────────

    def find_best_matches(
        self,
        new_images: List[str],
        pdf_images: List[Dict],
        page_hints: Dict[str, int] = None,
    ) -> List[MatchResult]:
        """
        Find the best PDF image match for each new screenshot.

        Two-pass approach for speed:
          Pass 1: Fast algorithms (SSIM/histogram/edge/template) on ALL pairs
          Pass 2: AI comparison ONLY on the winning candidate per screenshot
        """
        results = []
        ar_tol = self.config["aspect_ratio_tolerance"]
        min_area = self.config["min_area_ratio"]

        for new_img_path in new_images:
            new_img_name = os.path.basename(new_img_path)

            # Check page hints
            target_page = None
            if page_hints:
                for hint_name, hint_page in page_hints.items():
                    if hint_name.lower() in new_img_name.lower():
                        target_page = hint_page
                        break

            # Pre-compute new image dimensions for pre-filtering
            new_dims = self._get_image_dimensions(new_img_path)
            new_ar = self._aspect_ratio(new_dims)
            new_area = (new_dims[0] * new_dims[1]) if new_dims else 0

            # ── Pass 1: Fast scoring on all candidates ──
            candidates = []   # [(combined, pdf_img, scores), ...]
            skipped = 0

            for pdf_img in pdf_images:
                if target_page is not None and pdf_img.get("page") != target_page:
                    continue

                pdf_path = pdf_img.get("path", "")

                # ── Pre-filter: aspect ratio ──
                pdf_dims = self._get_image_dimensions(pdf_path)
                if pdf_dims and new_dims:
                    pdf_ar = self._aspect_ratio(pdf_dims)
                    ar_diff = abs(new_ar - pdf_ar) / max(new_ar, pdf_ar)
                    if ar_diff > ar_tol:
                        skipped += 1
                        continue

                    # ── Pre-filter: area ratio (skip tiny icons) ──
                    pdf_area = pdf_dims[0] * pdf_dims[1]
                    if new_area > 0 and pdf_area > 0:
                        area_ratio = min(new_area, pdf_area) / max(new_area, pdf_area)
                        if area_ratio < min_area:
                            skipped += 1
                            continue

                scores = self.compute_fast_score(new_img_path, pdf_path)
                candidates.append((scores["combined"], pdf_img, scores))

                # Early exit: if we find a very high confidence match, stop scanning
                if scores["is_high_confidence"] and scores["combined"] >= 0.85:
                    logger.info(f"Early exit: high-confidence match found "
                                f"(score={scores['combined']:.3f}) on page "
                                f"{pdf_img.get('page', '?')}")
                    break

            # Sort candidates by combined score (best first)
            candidates.sort(reverse=True, key=lambda x: x[0])

            if skipped:
                logger.info(f"Skipped {skipped}/{skipped + len(candidates)} "
                            f"candidates for {new_img_name} (aspect/size pre-filter)")

            # Log top candidates for diagnostics
            for rank, (comb, c_img, c_scores) in enumerate(candidates[:5], 1):
                logger.info(
                    f"  #{rank} page {c_img.get('page', '?')}: "
                    f"combined={comb:.3f} "
                    f"(ssim={c_scores['ssim']:.2f} hist={c_scores['histogram']:.2f} "
                    f"edge={c_scores['edge']:.2f} tmpl={c_scores['template']:.2f} "
                    f"phash={c_scores['phash']:.2f} ocr={c_scores.get('ocr', 0):.2f})"
                )

            # Pick initial best from fast scoring
            best_match = candidates[0][1] if candidates else None
            best_scores = candidates[0][2] if candidates else {"combined": 0}

            # ── Pass 1.5: OCR refinement on top-N candidates ──
            # OCR is slow (~1s per image) so we only run it on the
            # top few candidates, not all 400+.
            ocr_top_n = self.config.get("ai_top_n", 3)
            if TESSERACT_AVAILABLE and len(candidates) > 1:
                # Pre-cache OCR for the new screenshot (done once)
                self._ocr_text(new_img_path)

                ocr_candidates = []
                for i, (comb, c_img, c_scores) in enumerate(candidates[:ocr_top_n]):
                    c_path = c_img.get("path", "")
                    refined = self.refine_with_ocr(new_img_path, c_path, c_scores)
                    ocr_candidates.append((refined["combined"], c_img, refined))
                    logger.info(
                        f"  OCR #{i+1} page {c_img.get('page', '?')}: "
                        f"ocr={refined['ocr']:.2f} -> combined={refined['combined']:.3f}")

                # Re-sort OCR-refined candidates
                ocr_candidates.sort(reverse=True, key=lambda x: x[0])
                best_match = ocr_candidates[0][1]
                best_scores = ocr_candidates[0][2]

                # Update main candidates list so AI pass uses OCR-refined scores
                candidates[:ocr_top_n] = ocr_candidates
                candidates.sort(reverse=True, key=lambda x: x[0])

            # ── Minimum threshold gate ──
            if best_match and best_scores["combined"] < self.config["similarity_threshold"]:
                logger.info(f"No good match for {new_img_name}: "
                            f"best score {best_scores['combined']:.3f} "
                            f"< threshold {self.config['similarity_threshold']}")
                best_match = None
                best_scores["is_match"] = False
                best_scores["is_high_confidence"] = False

            # ── Pass 2: AI refinement on top-N candidates ──
            # Compare the top N fast-scoring candidates with AI so
            # a narrow fast-score winner can be overturned.
            ai_top_n = self.config.get("ai_top_n", 3)
            if best_match and self.ai_comparator and candidates:
                ai_best_score = -1.0
                ai_best_match = None
                ai_best_scores = None

                for i, (comb, c_img, c_scores) in enumerate(candidates[:ai_top_n]):
                    if c_scores["combined"] < self.config["similarity_threshold"]:
                        break  # remaining candidates are even worse
                    c_path = c_img.get("path", "")
                    logger.info(f"AI verifying: {new_img_name} -> "
                                f"page {c_img.get('page', '?')} "
                                f"(candidate #{i+1})")
                    refined = self.refine_with_ai(new_img_path, c_path, c_scores)
                    if refined["combined"] > ai_best_score:
                        ai_best_score = refined["combined"]
                        ai_best_match = c_img
                        ai_best_scores = refined

                if ai_best_match and ai_best_scores:
                    if ai_best_match.get("page") != best_match.get("page"):
                        logger.info(
                            f"AI overturned fast-score winner: "
                            f"page {best_match.get('page', '?')} -> "
                            f"page {ai_best_match.get('page', '?')} "
                            f"(score {ai_best_scores['combined']:.3f})")
                    best_match = ai_best_match
                    best_scores = ai_best_scores

                # Re-apply threshold after AI refinement
                if best_scores["combined"] < self.config["similarity_threshold"]:
                    logger.info(f"AI-refined score still below threshold for {new_img_name}")
                    best_match = None
                    best_scores["is_match"] = False
                    best_scores["is_high_confidence"] = False

            result = MatchResult(
                new_image_path=new_img_path,
                new_image_name=new_img_name,
                matched_pdf_image=best_match,
                similarity_score=best_scores.get("ssim", 0),
                histogram_score=best_scores.get("histogram", 0),
                edge_score=best_scores.get("edge", 0),
                template_score=best_scores.get("template", 0),
                ocr_score=best_scores.get("ocr", 0),
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



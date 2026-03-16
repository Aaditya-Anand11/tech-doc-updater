"""
Document Updater Module

Replaces images and text in PDF documents while preserving
formatting, alignment, and numbering.
Extracted from EnhancedPDFProcessor.replace_images_and_text().
"""

import os
import logging
from typing import List, Dict

from docsync.models import TextChange

logger = logging.getLogger("docsync.doc_updater")

try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class DocumentUpdater:
    """
    Updates PDF documents by replacing images and text.
    Preserves original formatting, alignment, and page structure.
    """

    def replace_images_and_text(
        self,
        pdf_path: str,
        image_replacements: List[Dict],
        text_replacements: List[TextChange],
        output_path: str,
    ) -> Dict:
        """
        Replace images and text in a PDF document.
        
        Args:
            pdf_path: Path to the original PDF
            image_replacements: List of dicts with 'xref' and 'new_image_path'
            text_replacements: List of approved TextChange objects
            output_path: Path to write the updated PDF
            
        Returns:
            Result dict with success, counts, and any errors
        """
        if not PDF_SUPPORT:
            return {"success": False, "error": "PDF support not available"}

        try:
            doc = fitz.open(pdf_path)
            images_replaced = 0
            text_replaced = 0

            page_details = {}  # page_num -> {"images": N, "texts": [(old,new),...]}

            # ── Replace images ──────────────────────────────────
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
                                        # Fallback for flattened/complex images
                                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                    page.insert_image(rect, filename=new_path)
                                    images_replaced += 1
                                    pg = page_details.setdefault(page_num + 1, {"images": 0, "texts": []})
                                    pg["images"] += 1
                                    logger.info(f"Replaced image xref={xref} on page {page_num + 1}")
                                except Exception as e:
                                    logger.error(f"Image replacement error on page {page_num + 1}: {e}")
                            break

            # ── Replace text: two-pass redaction approach ─────────
            # Collect all redactions per page first, then apply once
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
                            # Boundary check to prevent replacing part of a larger word
                            valid_instances = []
                            for inst in instances:
                                ext_rect = fitz.Rect(max(0, inst.x0 - 2), inst.y0, inst.x1 + 2, inst.y1)
                                word_in_context = page.get_text("text", clip=ext_rect).strip()
                                if len(word_in_context) <= len(variant) + 3:
                                    valid_instances.append(inst)

                            if valid_instances:
                                for inst in valid_instances:
                                    if page_num not in page_redactions:
                                        page_redactions[page_num] = []
                                    page_redactions[page_num].append((inst, new_text))
                                    text_replaced += 1
                                    pg = page_details.setdefault(page_num + 1, {"images": 0, "texts": []})
                                    pg["texts"].append((old_text, new_text))
                                break  # Use first variant that matches

            # Apply all redactions per page at once
            for page_num, redactions in page_redactions.items():
                page = doc[page_num]
                for rect, _ in redactions:
                    page.add_redact_annot(rect)
                try:
                    page.apply_redactions()
                except Exception as e:
                    logger.error(f"Apply redactions error on page {page_num + 1}: {e}")

                # Add new text overlays with tracked-change styling
                for rect, new_text in redactions:
                    try:
                        new_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + max(rect.width, len(new_text) * 5.5), rect.y1 + 12)
                        annot = page.add_freetext_annot(
                            new_rect, new_text,
                            fontsize=max(8, rect.height * 0.75),
                            fontname="helv",
                            text_color=(0.8, 0, 0),
                            fill_color=(1, 1, 0.9),
                        )
                        annot.update()
                    except Exception as e:
                        logger.error(f"Text overlay error on page {page_num + 1}: {e}")

            doc.save(output_path)
            doc.close()

            logger.info(
                f"Document updated: {images_replaced} images, "
                f"{text_replaced} text replacements → {output_path}"
            )

            return {
                "success": True,
                "images_replaced": images_replaced,
                "text_replaced": text_replaced,
                "output_path": output_path,
                "page_details": page_details,
            }
        except Exception as e:
            logger.error(f"PDF replacement error: {e}")
            return {"success": False, "error": str(e)}

    def _generate_search_variants(self, text: str) -> List[str]:
        """Generate search variants for fuzzy text matching in PDFs"""
        variants = []
        seen = set()

        def _add(v):
            if v and v not in seen:
                seen.add(v)
                variants.append(v)

        _add(text)
        _add(' '.join(text.split()))  # Normalized whitespace
        _add(text.title())
        _add(text.upper())
        _add(text.lower())
        if len(text) > 1:
            _add(text[0].upper() + text[1:])

        return variants

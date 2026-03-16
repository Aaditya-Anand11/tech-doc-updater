"""
Document Updater Module

Replaces images and text in PDF documents while preserving
formatting, alignment, and numbering.
Extracted from EnhancedPDFProcessor.replace_images_and_text().
"""

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

            # ── Replace images ──────────────────────────────────
            for repl in image_replacements:
                xref = repl.get("xref")
                new_path = repl.get("new_image_path")
                if not xref or not new_path or not os.path.exists(new_path):
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

            # ── Replace text with fuzzy matching ─────────────────
            for change in text_replacements:
                if not change.approved:
                    continue

                old_text = change.old_text
                new_text = change.new_text

                for page in doc:
                    search_variants = self._generate_search_variants(old_text)

                    instances_found = []
                    for variant in search_variants:
                        instances = page.search_for(variant)
                        if instances:
                            instances_found.extend(instances)
                            break  # Use first variant that matches

                    for inst in instances_found:
                        try:
                            page.add_redact_annot(inst, new_text)
                            text_replaced += 1
                        except Exception as e:
                            logger.debug(f"Redaction error: {e}")

                    if instances_found:
                        try:
                            page.apply_redactions()
                        except Exception as e:
                            logger.debug(f"Apply redactions error: {e}")

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
            }
        except Exception as e:
            logger.error(f"PDF replacement error: {e}")
            return {"success": False, "error": str(e)}

    def _generate_search_variants(self, text: str) -> List[str]:
        """Generate search variants for fuzzy text matching in PDFs"""
        variants = [text]

        # Normalized whitespace
        normalized = ' '.join(text.split())
        if normalized != text:
            variants.append(normalized)

        # Title case
        title = text.title()
        if title not in variants:
            variants.append(title)

        return variants

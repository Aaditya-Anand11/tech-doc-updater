"""
Document Parser Module

Parses PDF (and future DOCX) documents to extract images, metadata,
and text content. Extracted from EnhancedPDFProcessor in app_main.py.
"""

import os
import tempfile
import shutil
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger("docsync.doc_parser")

# PDF support
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("PyMuPDF not installed. Run: pip install pymupdf")


class DocumentParser:
    """
    Parse documents (PDF, future DOCX) to extract images,
    metadata, and text content for comparison.
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
                "creation_date": doc.metadata.get("creationDate", "Unknown"),
            }
            doc.close()
            return info
        except Exception as e:
            return {"error": str(e)}

    def extract_all_images(self, pdf_path: str, output_dir: str = None) -> List[Dict]:
        """Extract all images from a PDF with metadata (page, position, xref)"""
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

                        # Get position on page
                        img_rects = page.get_image_rects(xref)
                        position = None
                        if img_rects:
                            rect = img_rects[0]
                            position = {
                                "x": rect.x0, "y": rect.y0,
                                "width": rect.width, "height": rect.height,
                            }

                        extracted.append({
                            "page": page_num + 1,
                            "index": img_index + 1,
                            "xref": xref,
                            "path": filepath,
                            "filename": filename,
                            "position": position,
                            "format": image_ext,
                        })
                    except Exception:
                        pass

            doc.close()
            logger.info(f"Extracted {len(extracted)} images from {os.path.basename(pdf_path)}")
            return extracted
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return []

    def extract_text_by_page(self, pdf_path: str) -> Dict[int, str]:
        """Extract text from each page of a PDF"""
        if not PDF_SUPPORT:
            return {}

        text_by_page = {}
        try:
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc):
                text_by_page[page_num + 1] = page.get_text()
            doc.close()
        except Exception as e:
            logger.error(f"Text extraction error: {e}")

        return text_by_page

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
                mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
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
        """Remove temporary files"""
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

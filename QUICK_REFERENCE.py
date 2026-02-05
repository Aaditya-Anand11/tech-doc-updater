"""
QUICK REFERENCE - Advanced Document Analyzer
Schneider Electric Hackathon 2025-2026
"""

# ============================================================
# INSTALLATION
# ============================================================

pip install -r requirements.txt          # Install all dependencies
python app_main.py                       # Run application
# Open: http://127.0.0.1:7861

# ============================================================
# PYTHON API USAGE
# ============================================================

from app_main import AdvancedDocumentAnalyzer

# Initialize
analyzer = AdvancedDocumentAnalyzer()

# Load images
gui_image = analyzer.load_image("gui.png")
doc_image = analyzer.load_image("doc.png")

# Compare images
result = analyzer.compare_images(
    gui_image, 
    doc_image, 
    enable_ocr=True,              # Extract text
    enable_color_analysis=True    # Analyze colors
)

# Generate summary
summary = analyzer.generate_summary_report(
    gui_name="GUI Screenshot",
    doc_name="Documentation Image",
    result=result
)

# Print results
print(f"Similarity: {summary['similarity_score']}%")
print(f"Changed Regions: {summary['changed_regions_count']}")
print(f"Type: {summary['change_type']}")
print(f"Recommendation: {summary['recommendation']}")

# Generate reports
analyzer.generate_html_report(result, summary, gui_image, doc_image, "report.html")
analyzer.generate_json_report(result, summary, "report.json")
analyzer.generate_pdf_report(result, summary, "report.pdf")

# Export changelog
analyzer.export_changelog("changelog.json")

# ============================================================
# CONFIGURATION
# ============================================================

# Adjust sensitivity
analyzer.similarity_threshold = 0.95      # Lower = more sensitive
analyzer.min_region_area = 10             # Smaller regions detected
analyzer.text_similarity_threshold = 0.90 # Text matching sensitivity

# ============================================================
# AVAILABLE METHODS
# ============================================================

# Image Loading
analyzer.load_image(image_path)                 # Load from file/PIL/numpy

# Image Processing
analyzer.preprocess_image(img, target_size)    # Convert to grayscale
analyzer.preprocess_for_ocr(img)               # Prepare for OCR

# Text Operations
analyzer.extract_text(img)                      # OCR text extraction
analyzer.extract_text_with_boxes(img)          # OCR with bounding boxes
analyzer.compare_text(text1, text2)            # Compare two texts

# Color Operations
analyzer.extract_dominant_colors(img)          # Get top 5 colors
analyzer.rgb_to_hex(r, g, b)                   # Convert RGB to HEX

# Analysis
analyzer.compare_images(gui_image, doc_image)  # Main comparison
analyzer.analyze_change_type(result)           # Categorize changes

# Reporting
analyzer.generate_summary_report(...)          # Create summary
analyzer.generate_html_report(...)             # HTML file
analyzer.generate_json_report(...)             # JSON file
analyzer.generate_pdf_report(...)              # PDF file

# Changelog
analyzer.export_changelog(path)                 # Save all comparisons
analyzer.clear_log()                           # Clear data

# ============================================================
# CHANGE TYPES (Returns)
# ============================================================

"NO_CHANGE"              # > 99% similar, no update needed
"MINOR_UPDATES"          # 95-98%, update specific sections
"MULTIPLE_SMALL_CHANGES" # > 5 regions changed
"SIGNIFICANT_CHANGES"    # 70-95%, major revision needed
"MAJOR_REDESIGN"         # < 70%, complete rewrite needed
"TEXT_CONTENT_CHANGED"   # Text differs but layout same

# ============================================================
# RESULT DICTIONARY STRUCTURE
# ============================================================

result = {
    "similarity_score": 0.92,              # Float 0-1
    "is_changed": True,                    # Boolean
    "num_changed_regions": 5,              # Integer
    "changed_regions": [
        {"x": 10, "y": 20, "width": 100, "height": 50, "area": 5000},
        ...
    ],
    "diff_visualization": numpy_array,     # Highlighted image
    "ocr_gui_text": "Extracted text...",   # If OCR enabled
    "ocr_doc_text": "Documentation text...",
    "text_comparison": {
        "text_similarity": 95.2,           # Percentage
        "is_text_changed": False,
        "added_text": ["line1", "line2"],
        "removed_text": ["old_line"],
        "diff_lines": [...]
    },
    "color_analysis": {
        "gui_colors": [
            {"rgb": (255, 87, 51), "hex": "#FF5733", "percentage": 25.3},
            ...
        ],
        "doc_colors": [...]
    }
}

# ============================================================
# SUMMARY REPORT STRUCTURE
# ============================================================

summary = {
    "timestamp": "2026-01-23T12:34:56.789123",
    "gui_source": "gui.png",
    "document_image": "doc.png",
    "similarity_score": 92.35,              # Percentage
    "change_type": "MINOR_UPDATES",
    "requires_update": True,
    "changed_regions_count": 5,
    "recommendation": "Update specific...",
    "changed_areas": [...],
    "text_analysis": {
        "text_similarity": 95.2,
        "text_changed": False,
        "added_text": [...],
        "removed_text": [...]
    },
    "color_analysis": {...}
}

# ============================================================
# COMMON WORKFLOWS
# ============================================================

# Workflow 1: Quick comparison
gui = analyzer.load_image("gui.png")
doc = analyzer.load_image("doc.png")
result = analyzer.compare_images(gui, doc)
print(result["similarity_score"])

# Workflow 2: Full analysis with all reports
gui = analyzer.load_image("gui.png")
doc = analyzer.load_image("doc.png")
result = analyzer.compare_images(gui, doc, enable_ocr=True, enable_color_analysis=True)
summary = analyzer.generate_summary_report("GUI", "Doc", result)
analyzer.generate_html_report(result, summary, gui, doc)
analyzer.generate_json_report(result, summary)
analyzer.generate_pdf_report(result, summary)

# Workflow 3: Batch processing
images = [("gui1.png", "doc1.png"), ("gui2.png", "doc2.png")]
for gui_path, doc_path in images:
    gui = analyzer.load_image(gui_path)
    doc = analyzer.load_image(doc_path)
    result = analyzer.compare_images(gui, doc)
    print(f"{gui_path}: {result['similarity_score']*100:.1f}%")

# Workflow 4: Custom preprocessing
img = analyzer.load_image("gui.png")
processed = analyzer.preprocess_for_ocr(img)
text = analyzer.extract_text(img, preprocess=False)

# ============================================================
# THRESHOLD TUNING
# ============================================================

0.99  → Very strict, only major changes
0.98  → Strict, default (recommended)
0.95  → Moderate, detects small changes
0.90  → Sensitive, detects subtle differences
0.85  → Very sensitive, finds minor variations
< 0.85 → Extremely sensitive, may have false positives

# ============================================================
# IMAGE FORMAT SUPPORT
# ============================================================

Supported: PNG, JPG, JPEG, BMP, GIF, TIFF, WebP
Recommended: PNG (lossless), JPEG (lossy but common)
Size limit: ~50MB (web interface), unlimited (API)
Resolution: 600x400 minimum, 2000x1500 recommended

# ============================================================
# ERROR HANDLING
# ============================================================

try:
    gui = analyzer.load_image("gui.png")
    doc = analyzer.load_image("doc.png")
    result = analyzer.compare_images(gui, doc)
except ValueError as e:
    print(f"Invalid image: {e}")
except Exception as e:
    print(f"Error: {e}")

# ============================================================
# LOGGING & DEBUGGING
# ============================================================

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Or check config.ini for logging settings:
# LOG_LEVEL = DEBUG
# LOG_TO_FILE = true

# ============================================================
# FILE OUTPUTS
# ============================================================

report.html              # Interactive HTML with images
report.json              # Structured JSON data
report.pdf               # Professional PDF document
changelog.json           # All comparison history

# ============================================================
# PERFORMANCE TIPS
# ============================================================

# Fast (< 1 second)
disable_ocr = False
disable_colors = False
threshold = 0.98
resolution = 800x600

# Balanced (2-3 seconds)
enable_ocr = True
disable_colors = False
threshold = 0.95
resolution = 1024x768

# Thorough (5-10 seconds)
enable_ocr = True
enable_colors = True
threshold = 0.85
resolution = 1920x1440

# ============================================================
# COMMON ISSUES & SOLUTIONS
# ============================================================

# OCR not working
# → Install: pip install pytesseract
# → Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki

# PDF export fails
# → Install: pip install reportlab PyPDF2 pdf2image

# Port 7861 in use
# → Change: interface.launch(server_port=7862)

# Memory error on large images
# → Reduce resolution or disable color analysis

# Low accuracy
# → Enable OCR preprocessing
# → Use higher resolution
# → Lower similarity threshold

# ============================================================
# RESOURCE REQUIREMENTS
# ============================================================

Minimum:
- RAM: 2 GB
- Disk: 500 MB
- CPU: 2 cores
- Python: 3.8+

Recommended:
- RAM: 8 GB
- Disk: 2 GB
- CPU: 4 cores
- Python: 3.10+

For batch processing:
- RAM: 16 GB
- Disk: 10 GB
- CPU: 8+ cores

# ============================================================
# USEFUL LINKS
# ============================================================

GitHub: https://github.com/Izpiz06/Schneider_hackathon
Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
OpenCV: https://opencv.org
Gradio: https://gradio.app
ReportLab: https://www.reportlab.com

# ============================================================
# SHORTCUTS & TIPS
# ============================================================

# Get OCR available status
print(analyzer.ocr_available)

# Get PDF support status
print(analyzer.pdf_support)

# Access change log
print(analyzer.change_log)

# Clear all data
analyzer.clear_log()

# Check thresholds
print(analyzer.similarity_threshold)
print(analyzer.min_region_area)
print(analyzer.text_similarity_threshold)

# ============================================================
# VERSION INFO
# ============================================================

Version: 1.0.0
Released: January 23, 2026
For: Schneider Electric Hackathon 2025-2026
License: MIT
Python: 3.8+

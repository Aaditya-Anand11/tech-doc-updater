# 🔄 Automatic Update to Technical Documents - ENHANCED

**Schneider Electric Hackathon 2025-2026** | Idea Card ID: 12

An advanced platform-agnostic tool that compares GUI images from software applications with images in technical documentation, identifies changes, and provides comprehensive update recommendations with professional reports.

## ✨ Features

### Core Functionality
- **Visual Comparison** - Compare GUI screenshots with documentation images
- **Change Detection** - Automatically identify regions that have changed
- **Similarity Scoring** - Get precise similarity percentages
- **Visual Highlighting** - Yellow highlights on changes, red borders for precision
- **Change Classification** - Categorize changes as Minor, Significant, or Major Redesign

### OCR & Text Analysis
- **Text Extraction** - Extract visible text from GUI screenshots using Tesseract OCR
- **Text Comparison** - Automatically compare text content between GUI and documentation
- **Text Diff** - See exactly what text was added, removed, or changed
- **Text Regions** - Green boxes highlight detected text areas
- **Text Similarity Score** - Percentage match of text content

### Color Analysis ✨ NEW
- **Dominant Color Extraction** - Identify top 5 dominant colors in images
- **RGB & HEX Values** - Convert colors to both RGB and HEX formats
- **Color Percentage** - See percentage distribution of colors
- **Comparative Analysis** - Compare color palettes between GUI and documentation

### Reporting System ✨ NEW
- **Summary Report** - Quick, human-readable overview
- **Technical Report** - Detailed metrics in table format
- **JSON Report** - Structured data export for integration
- **PDF Report** - Professional formatted document
- **HTML Report** - Interactive visualization with images
- **HTML Export** - Self-contained HTML file with embedded images

### User Interface
- **Web Interface** - Easy-to-use Gradio UI with multiple tabs
- **Multi-Tab Design** - Organized sections for different tasks
- **Real-time Analysis** - Fast processing (3-5 seconds)
- **File Export** - Download all reports as files

### Advanced Features
- **PDF Support** - Compare PDFs directly
- **Change Log** - Track all comparisons over time
- **Batch Processing** - Compare multiple documents
- **Custom Thresholds** - Adjust sensitivity for detection
- **OCR Configuration** - Optimize for different document types

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Izpiz06/Schneider_hackathon.git
cd Schneider_hackathon

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Install Tesseract OCR

**Windows:**
1. Download installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer
3. Add Tesseract to PATH or set in code:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### Run the Application

```bash
python app_main.py
```

Open browser: **http://127.0.0.1:7861**

## 📖 How to Use

### Tab 1: Compare Images
1. **Upload GUI Screenshot** - Current state of your software's interface
2. **Upload Documentation Image** - Corresponding image from your technical documentation
3. **Enable OCR** - Toggle for text extraction and comparison
4. **Color Analysis** - Toggle to analyze color palettes
5. **Adjust Threshold** - Lower = more sensitive (default: 0.98)
6. **Click Compare** - Analyze and highlight differences
7. **Review Results** - View changes, text, and color analysis
8. **Download Reports** - Export as HTML, JSON, or PDF

### Tab 2: Reports & Export
- **Export Changelog** - Save all comparisons to JSON
- **Clear Analysis** - Reset all data

### Tab 3: About
- Learn about features and technologies

## 📊 Output & Reports

### Visualization
| Output | Description |
|--------|-------------|
| **Diff Visualization** | Red boxes highlight changed regions |
| **Yellow Highlights** | 30% transparency showing exact change areas |
| **Info Bar** | Shows similarity %, change count, text match % |
| **Region Numbers** | Labeled boxes for identifying multiple changes |

### Text Analysis
| Output | Description |
|--------|-------------|
| **GUI Text** | Extracted text from current GUI |
| **Doc Text** | Extracted text from documentation |
| **Similarity Score** | Percentage match (0-100%) |
| **Added Text** | New text in GUI not in documentation |
| **Removed Text** | Text in documentation not in GUI |

### Color Analysis
| Output | Description |
|--------|-------------|
| **Dominant Colors** | Top 5 colors by percentage |
| **RGB Values** | (Red, Green, Blue) format |
| **HEX Values** | #RRGGBB format |
| **Percentages** | % of image covered by color |

### Reports
| Report | Format | Use Case |
|--------|--------|----------|
| **HTML Report** | Interactive web page | Sharing with team |
| **JSON Report** | Structured data | Integration with tools |
| **PDF Report** | Professional document | Printing & documentation |
| **Summary Text** | Human readable | Quick reference |

## 🎨 Change Classification

| Type | Similarity | Action |
|------|------------|--------|
| 🟢 NO_CHANGE | > 99% | No update needed |
| 🟡 MINOR_UPDATES | 95-98% | Update specific sections |
| 🟠 SIGNIFICANT_CHANGES | 70-95% | Major revision recommended |
| 🔴 MAJOR_REDESIGN | < 70% | Complete rewrite may be needed |
| ⚪ TEXT_CONTENT_CHANGED | Text ≠ Visual = | Update text content even if visuals match |

## 🧪 Test Images

Test images are included:
- `test_old_gui.jpg` - Sample "old" documentation image
- `test_new_gui.jpg` - Sample "new" GUI with changes
- `old.jpg` / `new.jpg` - Alternative test images
- `old.html` / `new.html` - HTML comparison examples

## 📁 Project Structure

```
Schneider_hackathon/
├── app_main.py                    # Main application (ENHANCED)
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── test_old_gui.jpg              # Test image (old)
├── test_new_gui.jpg              # Test image (new)
├── old.jpg / new.jpg             # Alternative test images
├── old.html / new.html           # HTML test files
│
# Generated outputs:
├── report.html                    # Interactive HTML report
├── report.json                    # Structured JSON data
├── report.pdf                     # Professional PDF
└── changelog.json                # All comparisons history
```

## 🛠️ Technologies Used

| Technology | Purpose |
|-----------|---------|
| **Python 3.8+** | Core language |
| **OpenCV** | Image processing & region detection |
| **scikit-image** | SSIM similarity comparison |
| **Tesseract OCR** | Text extraction from images |
| **pytesseract** | Python wrapper for Tesseract |
| **Gradio** | Web user interface |
| **NumPy** | Array & matrix operations |
| **Pillow (PIL)** | Image loading & manipulation |
| **ReportLab** | PDF generation |
| **PyPDF2** | PDF processing |
| **pdf2image** | PDF to image conversion |

## 🔧 Configuration

### Adjust Sensitivity

```python
# In app_main.py
analyzer = AdvancedDocumentAnalyzer()
analyzer.similarity_threshold = 0.95  # More sensitive (lower = more changes detected)
analyzer.min_region_area = 10         # Smaller regions detected
```

### Custom OCR Config

```python
# In the extract_text method
custom_config = r'--oem 3 --psm 6'
# --oem: OCR Engine Mode (3 = Default)
# --psm: Page Segmentation Mode (6 = Uniform block of text)
```

## 📈 Performance

- **Fast Processing**: 3-5 seconds per comparison
- **Memory Efficient**: Handles high-resolution images
- **Batch Ready**: Can process multiple images
- **Scalable**: Works with various image sizes

## 🐛 Troubleshooting

### Tesseract Not Found
```bash
# Windows
pip install pytesseract
# Then download tesseract installer

# Linux
sudo apt install tesseract-ocr

# Mac
brew install tesseract
```

### PDF Support Missing
```bash
pip install reportlab PyPDF2 pdf2image
# May need to install poppler on Windows
```

### Low Accuracy on GUI Text
- Use `Enable OCR` checkbox
- Ensure high-resolution screenshots (600+ dpi)
- Try different threshold values

## 📊 API Usage

```python
from app_main import AdvancedDocumentAnalyzer
import cv2

analyzer = AdvancedDocumentAnalyzer()

# Load images
gui_img = analyzer.load_image("gui.png")
doc_img = analyzer.load_image("doc.png")

# Compare
result = analyzer.compare_images(gui_img, doc_img, enable_ocr=True)

# Generate reports
summary = analyzer.generate_summary_report("GUI", "Doc", result)
analyzer.generate_html_report(result, summary, gui_img, doc_img)
analyzer.generate_json_report(result, summary)
analyzer.generate_pdf_report(result, summary)

print(f"Similarity: {summary['similarity_score']}%")
print(f"Changed Regions: {summary['changed_regions_count']}")
print(f"Recommendation: {summary['recommendation']}")
```

## 👥 Target Audience

- Electronics Engineering
- Instrumentation & Control
- Robotics
- Electrical Engineering
- Computer Science
- Technical Documentation Teams
- QA Engineers
- Product Managers

## 🎯 Use Cases

1. **Product Release Documentation** - Update docs when GUI changes
2. **Quality Assurance** - Verify design matches documentation
3. **Localization** - Check text translations in GUI
4. **Branding Updates** - Detect color scheme changes
5. **Version Control** - Track documentation history
6. **Compliance** - Ensure consistent documentation
7. **User Manual Updates** - Automate screenshot validation

## 📄 License

MIT License - Free for commercial and personal use

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📞 Support

For issues or questions:
- Check the README thoroughly
- Review test images
- Verify Tesseract installation
- Check logs for errors

## 🎓 Educational

This tool demonstrates:
- Image processing with OpenCV
- Structural Similarity (SSIM) comparison
- OCR integration
- PDF generation
- Web UI with Gradio
- Color analysis algorithms
- Report generation
- PDF processing

Perfect for learning about:
- Computer Vision
- Machine Learning
- Technical Documentation
- Software Quality
- Automation

---

**Made with ❤️ for Schneider Electric Hackathon 2025-2026**

*Last Updated: January 23, 2026*

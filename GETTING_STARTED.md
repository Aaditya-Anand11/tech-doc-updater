# 🚀 Getting Started Guide
## Advanced Document Analyzer - Schneider Electric Hackathon 2025-2026

---

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Running the Application](#running-the-application)
4. [Using the Interface](#using-the-interface)
5. [Interpreting Results](#interpreting-results)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Minimum Requirements
- Python 3.8 or higher
- 2GB RAM
- 500MB disk space
- Tesseract OCR (optional but recommended)

### In 3 Steps

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Tesseract (Optional but recommended)
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt install tesseract-ocr
# Mac: brew install tesseract

# 3. Run the application
python app_main.py
```

Then open: **http://127.0.0.1:7861**

---

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/Izpiz06/Schneider_hackathon.git
cd Schneider_hackathon
```

### Step 2: Create Virtual Environment

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate.bat
```

**On Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Install Tesseract OCR (Optional)

**Windows:**
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run installer and note installation path
3. Add to your code (if needed):
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### Step 5: Install Poppler (For PDF support)

**Windows:**
- Download: https://github.com/oschwartz10612/poppler-windows/releases
- Extract to a folder
- Add to PATH or specify path in code

**Linux:**
```bash
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

---

## Running the Application

### Option 1: Direct Run

```bash
python app_main.py
```

Output:
```
Running on local URL:  http://127.0.0.1:7861
```

### Option 2: Using Installation Scripts

**Linux/Mac:**
```bash
chmod +x install.sh
./install.sh
```

**Windows:**
```bash
install.bat
```

### Accessing the Interface

Open your web browser and navigate to:
```
http://127.0.0.1:7861
```

---

## Using the Interface

### Tab 1: Compare Images 🔍

#### Step-by-Step

1. **Upload GUI Screenshot**
   - Click "GUI Screenshot" upload area
   - Select your current GUI image (JPG, PNG, etc.)
   - File size: Up to 50MB

2. **Upload Documentation Image**
   - Click "Documentation Image" upload area
   - Select your documentation screenshot
   - Should be similar size to GUI screenshot

3. **Enable OCR** (Optional)
   - Check "Enable OCR" to extract and compare text
   - Requires Tesseract installed
   - Takes additional 1-2 seconds

4. **Enable Color Analysis** (Optional)
   - Check "Color Analysis" to extract dominant colors
   - Shows RGB and HEX values
   - Takes additional 1-2 seconds

5. **Adjust Similarity Threshold**
   - Default: 0.98 (strict)
   - Lower values (0.85) = more changes detected
   - Higher values (0.99) = only major changes
   - Good range: 0.85 - 0.98

6. **Click "🔍 Compare"**
   - Analysis starts (takes 2-5 seconds)
   - Results appear below

#### Understanding Results

**Status & Metrics (Top Right)**
```
✅ Analysis Complete
- Similarity: 92.35%
- Changed Regions: 5
- Change Type: MINOR_UPDATES
- Recommendation: Update specific sections where changes are highlighted.
```

**Highlighted Changes (Center)**
- **Yellow areas** = Exact change location
- **Red boxes** = Region boundaries
- **Numbers** = Multiple changes identified

**GUI Text (OCR)**
- Text extracted from your current GUI
- Copy/paste for review

**Doc Text (OCR)**
- Text extracted from documentation
- Compare manually if needed

**Color Analysis**
```
GUI Colors:
- #FF5733 RGB(255, 87, 51) - 25.3%
- #3498DB RGB(52, 152, 219) - 18.7%
- #2ECC71 RGB(46, 204, 113) - 15.2%
```

**Text Comparison**
```
Text Similarity: 94.50%
Added: Button clicked
Removed: Previous button
```

### Tab 2: Reports & Export 📥

#### Export Changelog
- Saves all comparison history to JSON
- Click "📥 Export Changelog"
- Downloads as `changelog.json`

#### Clear Analysis
- Resets all data
- Click "🗑️ Clear Analysis"
- Useful before new batch

### Tab 3: About 📖
- Feature overview
- Technology stack
- Team information

---

## Interpreting Results

### Similarity Score

| Score | Meaning | Action |
|-------|---------|--------|
| > 99% | No changes | No documentation update needed |
| 95-99% | Minor changes | Update specific UI elements |
| 85-95% | Some changes | Revise sections with changes |
| 70-85% | Significant changes | Major revision needed |
| < 70% | Major redesign | Complete rewrite recommended |

### Change Types

**NO_CHANGE** ✅
- GUI and documentation are identical
- No update required

**MINOR_UPDATES** 🟡
- 1-5 small regions changed
- Update button text, icons, positions
- Documentation text stays same

**MULTIPLE_SMALL_CHANGES** 🟠
- More than 5 small regions
- Review all highlighted areas
- Update multiple sections

**SIGNIFICANT_CHANGES** 🟠
- Large sections different
- 50-70% similarity
- Major documentation revision needed
- Consider updating screenshots

**MAJOR_REDESIGN** 🔴
- Fundamental UI changes
- < 50% similarity
- Complete rewrite may be necessary
- Redesign entire documentation section

**TEXT_CONTENT_CHANGED** ⚪
- Text differs but visual layout same
- Only text content needs updating
- No screenshot changes needed

### Color Analysis

When color analysis is enabled:

**Meaning of Changes:**
- Same dominant colors = No rebranding
- Different color palette = Brand/theme change
- Missing colors = Simplified design

**Example Interpretation:**
```
Old: #3498DB (Blue) 40% → New: #E74C3C (Red) 35%
→ Brand color changed from Blue to Red
→ Update all branded images and graphics
```

---

## Advanced Features

### Custom Threshold Configuration

Edit `config.ini`:
```ini
[ANALYSIS]
SIMILARITY_THRESHOLD = 0.90  # Lower = more sensitive
MIN_REGION_AREA = 10         # Smaller regions detected
```

Then restart application.

### Using API Directly

```python
from app_main import AdvancedDocumentAnalyzer
import cv2

# Initialize
analyzer = AdvancedDocumentAnalyzer()

# Load images
gui = analyzer.load_image("gui.png")
doc = analyzer.load_image("doc.png")

# Compare
result = analyzer.compare_images(gui, doc, enable_ocr=True, enable_color_analysis=True)

# Generate all reports
summary = analyzer.generate_summary_report("GUI", "Documentation", result)
analyzer.generate_html_report(result, summary, gui, doc, "report.html")
analyzer.generate_json_report(result, summary, "report.json")
analyzer.generate_pdf_report(result, summary, "report.pdf")

# Export changelog
analyzer.export_changelog("all_comparisons.json")
```

### Batch Processing

```python
from pathlib import Path
import glob

image_pairs = [
    ("gui_v1.png", "doc_v1.png"),
    ("gui_v2.png", "doc_v2.png"),
    ("gui_v3.png", "doc_v3.png"),
]

results = []
for gui_path, doc_path in image_pairs:
    gui = analyzer.load_image(gui_path)
    doc = analyzer.load_image(doc_path)
    result = analyzer.compare_images(gui, doc)
    summary = analyzer.generate_summary_report(gui_path, doc_path, result)
    results.append(summary)
    print(f"✓ Processed {gui_path}")

# Save all results
import json
with open("batch_results.json", "w") as f:
    json.dump(results, f, indent=2)
```

### Custom Image Preprocessing

```python
import cv2
from app_main import AdvancedDocumentAnalyzer

analyzer = AdvancedDocumentAnalyzer()

# Load and preprocess
img = analyzer.load_image("gui.png")

# Apply custom preprocessing
gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
_, binary = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

# Now compare
gui_processed = analyzer.preprocess_image(img)
doc_processed = analyzer.preprocess_image(analyzer.load_image("doc.png"))

# Continue with analysis...
```

---

## Troubleshooting

### Issue: "Tesseract OCR not found"

**Solution:**
1. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
2. Verify installation path
3. Add to PATH environment variable
4. Or set in code:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Issue: "PDF export not available"

**Solution:**
```bash
pip install reportlab PyPDF2 pdf2image
```

On Windows, also install poppler.

### Issue: "Image size too large"

**Solution:**
- Resize image before uploading
- Use smaller resolution screenshots
- Or adjust in code:
```python
analyzer.max_image_size = 1500  # pixels
```

### Issue: "Out of memory"

**Solution:**
- Close other applications
- Reduce image resolution
- Process one image at a time
- Increase virtual memory/swap

### Issue: "Very slow processing"

**Solution:**
- Disable OCR if not needed
- Disable color analysis
- Reduce image resolution
- Increase similarity threshold (fewer calculations)
- Use faster computer

### Issue: "Low OCR accuracy"

**Solution:**
- Ensure high-resolution screenshots (150+ dpi)
- Increase image contrast
- Enable OCR preprocessing
- Try different PSM modes:
  - 3 = Default (single column)
  - 6 = Uniform block (recommended for GUI)
  - 11 = Sparse text

### Issue: "Port 7861 already in use"

**Solution:**
Option 1: Kill existing process
```bash
# Windows
netstat -ano | findstr :7861
taskkill /PID [PID] /F

# Linux/Mac
lsof -i :7861
kill -9 [PID]
```

Option 2: Use different port
```python
interface.launch(server_port=7862)
```

### Issue: "Report not generating"

**Solution:**
1. Check file permissions
2. Ensure `reports/` directory exists
```bash
mkdir reports
```
3. Check disk space
4. Verify report settings in `config.ini`

---

## Performance Tips

### For Fast Processing
1. **Reduce Image Size**: Scale to 1000x800 max
2. **Disable Unnecessary Features**: OCR and color analysis add 1-2 seconds each
3. **Adjust Threshold**: Higher threshold = faster (fewer regions to process)
4. **Preprocess Externally**: Use Photoshop/GIMP before uploading

### For Accuracy
1. **Enable OCR**: Better text detection
2. **Enable Color Analysis**: Catch branding changes
3. **Lower Threshold**: Detect subtle changes
4. **High Resolution**: 300 dpi recommended
5. **Same Image Type**: Consistent formats (PNG vs JPG)

### For Large Batches
1. Use API directly instead of web interface
2. Process sequentially to avoid memory issues
3. Save results incrementally
4. Run on high-spec machine (8GB+ RAM)

---

## Best Practices

### Before Comparison
✓ Use same image format (all PNG or all JPG)
✓ Ensure similar resolution
✓ Take screenshots at same zoom level
✓ Use lossless formats (PNG) for precision
✓ Document the image source (feature/version)

### During Comparison
✓ Enable OCR for text-heavy UIs
✓ Enable color analysis for branded designs
✓ Use default threshold first (0.98)
✓ Lower threshold if too few changes detected
✓ Disable features if processing is slow

### After Comparison
✓ Save HTML report for team review
✓ Export JSON for integration
✓ Export changelog for history
✓ Document findings in team system
✓ Use recommendations for doc updates

---

## Common Workflows

### Workflow 1: Simple Change Detection

```
1. Upload current GUI
2. Upload documentation image
3. Enable OCR (optional)
4. Use default threshold (0.98)
5. Click Compare
6. Review highlighted changes
7. Download HTML report
```

### Workflow 2: Comprehensive Analysis

```
1. Upload screenshots
2. Enable OCR ✓
3. Enable Color Analysis ✓
4. Lower threshold to 0.90
5. Click Compare
6. Review all results:
   - Visual changes
   - Text analysis
   - Color palette changes
7. Generate PDF for stakeholders
```

### Workflow 3: Batch Documentation Update

```
1. Prepare all GUI screenshots
2. Use API for batch processing
3. Generate reports for each comparison
4. Review all JSON reports
5. Consolidated findings
6. Create comprehensive update document
7. Distribute to documentation team
```

---

## Getting Help

### Documentation
- Check README.md for feature overview
- Review this guide for detailed instructions
- Check config.ini for all settings

### Testing
- Use provided test images (old.jpg, new.jpg)
- Try with sample screenshots first
- Verify Tesseract with `pytesseract.get_tesseract_version()`

### Debugging
- Enable logging: Set `LOG_LEVEL = DEBUG` in config.ini
- Check console output for errors
- Verify file permissions
- Test with smaller images first

### Issues
1. Check this troubleshooting section
2. Review application logs
3. Verify all dependencies installed
4. Try with test images
5. Check GitHub issues

---

**Version:** 1.0.0  
**Last Updated:** January 23, 2026  
**For:** Schneider Electric Hackathon 2025-2026

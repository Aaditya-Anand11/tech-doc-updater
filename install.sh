#!/bin/bash
# Installation script for Schneider Electric Hackathon Tool

echo "🔄 Setting up Automatic Document Updater..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "📥 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Install Tesseract OCR
echo "🔤 Installing Tesseract OCR..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt install tesseract-ocr
elif [[ "$OSTYPE" == "darwin"* ]]; then
    brew install tesseract
else
    echo "⚠️ Please install Tesseract manually from: https://github.com/UB-Mannheim/tesseract/wiki"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "To run the application:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Run: python app_main.py"
echo "3. Open browser: http://127.0.0.1:7861"

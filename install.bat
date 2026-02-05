@echo off
REM Installation script for Schneider Electric Hackathon Tool (Windows)

echo 🔄 Setting up Automatic Document Updater...

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python 3.8+
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✓ Python version: %PYTHON_VERSION%

REM Create virtual environment
echo 📦 Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

REM Upgrade pip
echo 📥 Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📚 Installing dependencies...
pip install -r requirements.txt

REM Install Tesseract OCR
echo 🔤 Installing Tesseract OCR...
echo ⚠️ Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
echo After installation, run:
echo set PYTESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

echo.
echo ✅ Installation complete!
echo.
echo To run the application:
echo 1. Activate virtual environment: venv\Scripts\activate.bat
echo 2. Run: python app_main.py
echo 3. Open browser: http://127.0.0.1:7861

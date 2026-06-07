@echo off
chcp 65001 >nul

echo ============================================
echo   File Desensitizer - GUI Launcher
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check and install dependencies
echo [INFO] Checking dependencies...
python -c "from file_desensitizer.gui import main" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First run, installing dependencies...
    pip install git+https://github.com/Yongsgithub/file-desensitizer.git
    if %errorlevel% neq 0 (
        echo [WARN] Online install failed, trying local install...
        pip install -e .
    )
)

:: Check Tesseract
where tesseract >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Tesseract OCR not installed. Image desensitization will not work.
    echo Download: https://github.com/UB-Mannheim/tesseract/wiki
    echo.
)

:: Launch GUI
echo [INFO] Launching GUI...
python -c "from file_desensitizer.gui import main; main()"

pause

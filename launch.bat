@echo off
chcp 65001 >nul

echo ============================================
echo   File Desensitizer - GUI Launcher
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    cls
    echo ============================================
    echo        Python Not Found
    echo ============================================
    echo.
    echo Python 3.10 or higher is required to run this program.
    echo.
    echo Steps to install:
    echo.
    echo   1. Download Python from the page that will open
    echo   2. [IMPORTANT] Check "Add Python to PATH" during install
    echo   3. Click "Install Now"
    echo   4. Re-run this script (launch.bat) after installation
    echo.
    echo Opening Python download page...
    start "" "https://www.python.org/downloads/"
    echo.
    pause
    exit /b 1
)

:: Check and install dependencies
echo [INFO] Checking dependencies...
python -c "from file_desensitizer.gui import main" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First run, installing dependencies...
    python -m pip install git+https://github.com/Yongsgithub/file-desensitizer.git
    if %errorlevel% neq 0 (
        echo [WARN] Online install failed, trying local install...
        python -m pip install -e .
    )
    if %errorlevel% neq 0 (
        echo [ERROR] Dependency installation failed. Please check your network or run manually: python -m pip install -e .
        pause
        exit /b 1
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

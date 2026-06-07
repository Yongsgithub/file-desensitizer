@echo off
chcp 65001 >nul

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 检查并安装依赖
echo [信息] 检查依赖...
python -c "from file_desensitizer.gui import main" >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 首次运行，正在安装依赖...
    pip install git+https://github.com/Yongsgithub/file-desensitizer.git
    if %errorlevel% neq 0 (
        echo [警告] 在线安装失败，尝试本地安装...
        pip install -e .
    )
)

:: 检查 Tesseract
where tesseract >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] Tesseract OCR 未安装，图片脱敏功能不可用
    echo 下载: https://github.com/UB-Mannheim/tesseract/wiki
    echo 安装时请勾选 Chinese (Simplified) 语言包
    echo.
)

:: 启动 GUI
echo [信息] 启动图形界面...
start "" python -m file_desensitizer.gui

exit /b 0

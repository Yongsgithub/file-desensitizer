@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================
echo   文件信息脱敏工具 - 启动程序
echo ============================================
echo.

:: 1. 检查 Python
echo [1/4] 检查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

:: 2. 安装依赖
echo [2/4] 安装依赖...
pip install git+https://github.com/Yongsgithub/file-desensitizer.git 2>&1
echo.

:: 3. 检查环境
echo [3/4] 检查环境...
python -c "from file_desensitizer.gui import main; print('OK')" 2>&1
if %errorlevel% neq 0 (
    echo [错误] 模块加载失败，尝试修复...
    pip install --upgrade git+https://github.com/Yongsgithub/file-desensitizer.git 2>&1
    echo.
    python -c "from file_desensitizer.gui import main; print('OK')" 2>&1
    if %errorlevel% neq 0 (
        echo [错误] 仍然失败，请检查 Python 环境
        pause
        exit /b 1
    )
)
echo.

:: 4. 启动 GUI
echo [4/4] 启动图形界面...
echo.
python -m file_desensitizer.gui
pause

@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
::  File Desensitizer - 健壮启动脚本
::  所有步骤均有错误处理，不依赖外部 pip 命令
:: ============================================================

title File Desensitizer 启动器
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: 日志文件（用于调试）
set "LOG=%SCRIPT_DIR%\startup.log"
echo [%date% %time%] 启动脚本开始执行 > "%LOG%"

goto :main

:: ============================================================
::  工具函数：安全执行命令并记录日志
::  用法：call :safe_exec "描述" command args...
:: ============================================================
:safe_exec
set "DESC=%~1"
shift
echo [%date% %time%] [EXEC] !DESC! >> "%LOG%"
echo !DESC!...
goto :eof

:: ============================================================
::  工具函数：检查 Python 是否可用
::  返回：errorlevel 0=可用，1=不可用
:: ============================================================
:check_python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python -c "import pip" >nul 2>&1
    if !errorlevel! equ 0 exit /b 0
)
exit /b 1

:: ============================================================
::  MAIN
:: ============================================================
:main

:: -------- 步骤1：检测 Python --------
echo ============================================
echo   File Desensitizer - 启动检查
echo ============================================
echo.

call :safe_exec "检测 Python..."

python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python 已安装
    echo [%date% %time%] [OK] Python detected >> "%LOG%"
    goto :python_ready
)

echo [信息] 未检测到 Python，即将自动安装...
echo [%date% %time%] [INFO] Python not found, starting auto-install >> "%LOG%"
goto :install_python

:: -------- 步骤2：自动安装 Python --------
:install_python
echo.
echo ============================================
echo        自动安装 Python 3.12
echo ============================================
echo.
echo 即将执行：
echo   1. 下载 Python 3.12.5 安装包（约 25MB）
echo   2. 静默安装到当前用户目录，自动配置 PATH
echo   3. 预计耗时 1~3 分钟
echo.
echo 注意：安装过程中请勿关闭此窗口。
echo.
pause

:: 创建临时目录
set "DL_DIR=%TEMP%\file_desensitizer"
if not exist "%DL_DIR%" (
    mkdir "%DL_DIR%" 2>nul
    if not exist "%DL_DIR%" (
        echo [错误] 无法创建临时目录：%DL_DIR%
        echo [%date% %time%] [ERROR] Cannot create temp dir >> "%LOG%"
        pause
        exit /b 1
    )
)

set "PYTHON_INSTALLER=%DL_DIR%\python-3.12.5-amd64.exe"

:: 下载 Python 安装包
echo.
echo [1/3] 正在下载 Python 安装包...
echo [%date% %time%] [INFO] Downloading Python... >> "%LOG%"
echo          URL: https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe
echo          保存到: %PYTHON_INSTALLER%
echo.

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe' -OutFile '%PYTHON_INSTALLER%' -ErrorAction Stop; Write-Host 'Download OK' } catch { Write-Host 'Download FAILED:' $_.Exception.Message; exit 1 }"

if not exist "%PYTHON_INSTALLER%" (
    echo.
    echo [错误] 下载失败！
    echo.
    echo 可能原因：
    echo   1. 网络连接异常或无法访问 python.org
    echo   2. 防火墙/代理阻止了下载
    echo.
    echo 解决方案：
    echo   1. 检查网络连接后重新运行本脚本
    echo   2. 或手动下载安装 Python：https://www.python.org/downloads/
    echo      【务必勾选】"Add Python to PATH"
    echo.
    echo [%date% %time%] [ERROR] Python download failed >> "%LOG%"
    pause
    exit /b 1
)

:: 获取文件大小
for %%F in ("%PYTHON_INSTALLER%") do set "FILE_SIZE=%%~zF"
set /a FILE_SIZE_MB=%FILE_SIZE%/1024/1024
echo [OK] 下载完成（%FILE_SIZE_MB% MB）
echo [%date% %time%] [OK] Python installer downloaded: %FILE_SIZE_MB% MB >> "%LOG%"

:: 静默安装 Python
echo.
echo [2/3] 正在静默安装 Python（请稍候 1~3 分钟）...
echo [%date% %time%] [INFO] Installing Python silently... >> "%LOG%"

start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 ^
    Shortcuts=0 Include_doc=0 Include_launcher=1

set "PY_INSTALL_ERROR=%errorlevel%"

:: 删除安装包
del "%PYTHON_INSTALLER%" >nul 2>&1
echo [%date% %time%] [INFO] Installer exit code: %PY_INSTALL_ERROR% >> "%LOG%"

if %PY_INSTALL_ERROR% neq 0 (
    echo.
    echo [错误] Python 安装失败（退出码：%PY_INSTALL_ERROR%）
    echo.
    echo 解决方案：
    echo   1. 以管理员身份运行本脚本
    echo   2. 或手动下载安装：https://www.python.org/downloads/
    echo.
    echo [%date% %time%] [ERROR] Python install failed: %PY_INSTALL_ERROR% >> "%LOG%"
    pause
    exit /b 1
)

echo [OK] Python 安装完成
echo [%date% %time%] [OK] Python installed >> "%LOG%"

:: 刷新 PATH（从注册表读取最新值）
echo.
echo [3/3] 正在刷新环境变量...
echo [%date% %time%] [INFO] Refreshing PATH... >> "%LOG%"

set "NEW_PATH=%PATH%"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "NEW_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "NEW_PATH=!NEW_PATH!;%%B"
set "PATH=%NEW_PATH%"

echo [OK] 环境变量已刷新
echo [%date% %time%] [OK] PATH refreshed >> "%LOG%"

:: 重新验证 Python 是否可用
echo.
echo 正在验证 Python 安装...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [警告] 当前会话中 Python 命令暂时不可用。
    echo         这是正常的，重启电脑后生效。
    echo.
    echo 请选择：
    echo   [R] 重启电脑后重新运行本脚本
    echo   [C] 继续尝试（可能失败）
    echo.
    set /p "RESTART_CHOICE=请选择 (R/C，回车默认R): "
    if "!RESTART_CHOICE!"=="" set "RESTART_CHOICE=R"
    if /i "!RESTART_CHOICE!"=="R" (
        echo [%date% %time%] [INFO] User chose to restart >> "%LOG%"
        shutdown /r /t 5 /c "重启后请重新运行启动.bat"
        exit /b 0
    )
    echo [%date% %time%] [INFO] User chose to continue anyway >> "%LOG%"
) else (
    echo [OK] Python 验证通过
)

echo.
echo 安装完成，正在重新启动脚本...
echo [%date% %time%] [INFO] Relaunching script... >> "%LOG%"
timeout /t 2 >nul
call "%~f0" %*
exit /b

:: -------- 步骤3：Python 就绪，确保 pip 可用 --------
:python_ready
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PYVER=%%i"
echo ============================================
echo  %PYVER% 已就绪
echo ============================================
echo.

:: 确保 pip 可用（始终用 python -m pip，不依赖 PATH 中的 pip 命令）
echo [信息] 检查 pip 是否可用...
python -m pip --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] pip 已可用
    echo [%date% %time%] [OK] pip available >> "%LOG%"
    goto :deps_check
)

echo [信息] pip 不可用，尝试修复（python -m ensurepip）...
echo [%date% %time%] [INFO] pip not found, running ensurepip... >> "%LOG%"

python -m ensurepip --upgrade --default-pip >nul 2>&1

python -m pip --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] pip 修复成功
    echo [%date% %time%] [OK] pip fixed via ensurepip >> "%LOG%"
    goto :deps_check
)

:: ensurepip 失败，尝试 get-pip.py
echo [警告] ensurepip 失败，尝试下载 get-pip.py...
echo [%date% %time%] [WARN] ensurepip failed, trying get-pip.py >> "%LOG%"

set "GET_PIP=%TEMP%\file_desensitizer\get-pip.py"
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GET_PIP%' -ErrorAction Stop; Write-Host 'get-pip downloaded' } catch { Write-Host 'get-pip download failed'; exit 1 }"

if exist "%GET_PIP%" (
    python "%GET_PIP%" --quiet
    del "%GET_PIP%" >nul 2>&1
    python -m pip --version >nul 2>&1
    if !errorlevel! equ 0 (
        echo [OK] pip 修复成功（via get-pip.py）
        echo [%date% %time%] [OK] pip fixed via get-pip.py >> "%LOG%"
        goto :deps_check
    )
)

echo.
echo [错误] 无法修复 pip！
echo.
echo 请尝试：
echo   1. 重新安装 Python，并勾选"pip"组件
echo   2. 手动运行：python -m ensurepip
echo.
echo 详细日志：%LOG%
echo [%date% %time%] [ERROR] Cannot fix pip >> "%LOG%"
pause
exit /b 1

:: -------- 步骤4：检查并安装 Python 依赖 --------
:deps_check
echo.
echo [信息] 检查项目依赖包...

:: 先检查 setuptools 和 wheel（构建需要）
python -m pip show setuptools >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 正在安装构建依赖（setuptools wheel）...
    python -m pip install setuptools wheel --quiet 2>&1
)

:: 检查项目是否已安装（可编辑模式：源码修改即时生效）
python -c "from file_desensitizer.gui import main" >nul 2>&1
if %errorlevel% equ 0 (
    :: 验证是否是最新版本（检查 egg-link 或直接强制刷新）
    echo [OK] 项目已安装
    echo [%date% %time%] [OK] Project already installed >> "%LOG%"
    
    :: 可编辑安装强制刷新（确保源码改动即时生效，极快）
    pushd "%SCRIPT_DIR%"
    python -m pip install -e . --quiet 2>nul
    popd
    echo [OK] 源码已同步
    goto :launch_gui
)

echo [信息] 首次运行，正在安装项目依赖（可编辑模式，需要网络连接，约 1~5 分钟）...
echo [%date% %time%] [INFO] Installing project in editable mode... >> "%LOG%"
echo.

:: 进入项目目录后安装（避免路径问题）
pushd "%SCRIPT_DIR%"

python -m pip install -e . 2>"%TEMP%\file_desensitizer\pip_error.log"
set "PIP_EXIT=%errorlevel%"

popd

if %PIP_EXIT% equ 0 (
    echo.
    echo [OK] 项目安装完成（可编辑模式，后续源码修改无需重装）
    echo [%date% %time%] [OK] Project installed in editable mode >> "%LOG%"
    goto :launch_gui
)

:: 安装失败，显示错误信息
echo.
echo [错误] 依赖安装失败（退出码：%PIP_EXIT%）
echo.
echo 详细错误日志：
type "%TEMP%\file_desensitizer\pip_error.log" 2>nul | more
echo.
echo 可能原因：
echo   1. 网络连接异常，无法访问 PyPI（pypi.org）
echo   2. 防火墙/代理阻止了 pip 下载
echo   3. 依赖包版本冲突
echo.
echo 解决方案：
echo   1. 检查网络连接后重新运行本脚本
echo   2. 配置 pip 镜像源后重试，例如：
echo      python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .
echo   3. 手动安装：cd "%SCRIPT_DIR%" ^&^& python -m pip install -e .
echo.
echo 详细日志已保存至：%LOG%
echo [%date% %time%] [ERROR] pip install failed: %PIP_EXIT% >> "%LOG%"
pause
exit /b 1

:: -------- 步骤5：启动 GUI --------
:launch_gui
echo ============================================
echo  正在启动 File Desensitizer...
echo ============================================
echo.
echo [%date% %time%] [INFO] Launching GUI... >> "%LOG%"

python -c "from file_desensitizer.gui import main; main()"
set "GUI_EXIT=%errorlevel%"

echo.
if %GUI_EXIT% equ 0 (
    echo 程序正常退出。
    echo [%date% %time%] [OK] GUI exited normally >> "%LOG%"
) else (
    echo 程序异常退出（退出码：%GUI_EXIT%）
    echo 详细日志：%LOG%
    echo [%date% %time%] [ERROR] GUI exited with code: %GUI_EXIT% >> "%LOG%"
)

echo.
pause

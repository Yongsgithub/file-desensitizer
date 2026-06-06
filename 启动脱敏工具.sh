#!/usr/bin/env bash
# ============================================================
#  文件信息脱敏工具 - 启动脚本 (macOS / Linux)
#  自动检查环境 → 安装依赖 → 启动 GUI
# ============================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        🔒 文件信息脱敏工具 - 本地离线版                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 找 Python ──
PYTHON=""
for py in python3.12 python3.11 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$py" -c "import sys; print(sys.version_info.major)")
        minor=$("$py" -c "import sys; print(sys.version_info.minor)")
        if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
            PYTHON="$py"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo -e "${RED}[ERROR]${NC} 需要 Python >= 3.10"
    echo "macOS: brew install python@3.11"
    echo "Ubuntu: sudo apt install python3.11"
    exit 1
fi
log_ok "Python: $($PYTHON --version)"

# ── 检查/安装 Python 包 ──
if ! "$PYTHON" -c "from file_desensitizer.gui import main" 2>/dev/null; then
    log_info "首次运行，正在安装依赖..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
        "$PYTHON" -m pip install --quiet -e "$SCRIPT_DIR" 2>&1 | tail -1
    else
        "$PYTHON" -m pip install --quiet git+https://github.com/Yongsgithub/file-desensitizer.git 2>&1 | tail -1
    fi
    log_ok "依赖安装完成"
fi

# ── 检查 Tesseract ──
if ! command -v tesseract &>/dev/null; then
    log_warn "Tesseract OCR 未安装，图片脱敏功能不可用"
    log_warn "macOS: brew install tesseract tesseract-lang"
    log_warn "Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
fi

# ── 启动 GUI ──
log_info "启动 GUI..."
"$PYTHON" -m file_desensitizer.gui

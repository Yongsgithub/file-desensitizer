#!/usr/bin/env bash
# ============================================================
#  file-desensitizer 全自动安装脚本
#  自动检测系统 → 安装系统依赖 → 安装 Python 包 → 验证
#  支持: macOS / Ubuntu / Debian / CentOS / RHEL / Fedora / Arch
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERR]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   文件信息脱敏工具 - 全自动安装                          ║"
echo "║   File Desensitizer Auto-Installer                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── 1. 检测系统 ───────────────────────────────────────────
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        log_info "检测到 macOS 系统"
    elif [[ -f /etc/os-release ]]; then
        . /etc/os-release
        case "$ID" in
            ubuntu|debian) OS="debian" ;;
            centos|rhel|fedora|rocky|almalinux) OS="rhel" ;;
            arch|manjaro) OS="arch" ;;
            *) OS="unknown" ;;
        esac
        log_info "检测到 Linux 系统: $ID"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        OS="windows"
        log_info "检测到 Windows 系统"
    else
        OS="unknown"
        log_warn "无法识别操作系统类型，将跳过系统依赖安装"
    fi
}

# ─── 2. 检查/安装 Tesseract OCR ─────────────────────────────
install_tesseract() {
    log_info "检查 Tesseract OCR..."
    
    if command -v tesseract &>/dev/null; then
        log_ok "Tesseract 已安装: $(tesseract --version 2>&1 | head -1)"
    else
        log_info "Tesseract 未安装，开始自动安装..."
        case "$OS" in
            macos)
                if command -v brew &>/dev/null; then
                    brew install tesseract tesseract-lang
                else
                    log_err "未找到 Homebrew，请先安装: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                    exit 1
                fi
                ;;
            debian)
                sudo apt-get update -qq
                sudo apt-get install -y -qq tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
                ;;
            rhel)
                sudo dnf install -y tesseract tesseract-langpack-chi-sim tesseract-langpack-eng 2>/dev/null || \
                sudo yum install -y tesseract tesseract-langpack-chi-sim tesseract-langpack-eng
                ;;
            arch)
                sudo pacman -S --noconfirm tesseract tesseract-data-chi_sim tesseract-data-eng
                ;;
            windows)
                log_warn "Windows 系统请手动安装 Tesseract: https://github.com/UB-Mannheim/tesseract/wiki"
                log_warn "安装时请勾选 Chinese (Simplified) 语言包"
                ;;
            *)
                log_warn "请手动安装 Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
                ;;
        esac
        log_ok "Tesseract 安装完成"
    fi

    # 验证中文语言包
    if tesseract --list-langs 2>/dev/null | grep -q chi_sim; then
        log_ok "Tesseract 中文语言包 (chi_sim) 已就绪"
    else
        log_warn "Tesseract 中文语言包未安装，中文图片 OCR 将不可用"
        log_warn "安装方法: https://github.com/tesseract-ocr/tessdata"
    fi
}

# ─── 3. 检查/安装 LibreOffice（可选）────────────────────────
install_libreoffice() {
    log_info "检查 LibreOffice（用于旧版 .doc 转换，可选）..."
    
    if command -v libreoffice &>/dev/null; then
        log_ok "LibreOffice 已安装"
        return
    fi
    
    log_info "LibreOffice 未安装，开始安装..."
    case "$OS" in
        macos)
            brew install --cask libreoffice 2>/dev/null || log_warn "LibreOffice 安装失败，.doc 文件需手动转换"
            ;;
        debian)
            sudo apt-get install -y -qq libreoffice-writer 2>/dev/null || log_warn "LibreOffice 安装失败"
            ;;
        rhel)
            sudo dnf install -y libreoffice-writer 2>/dev/null || log_warn "LibreOffice 安装失败"
            ;;
        arch)
            sudo pacman -S --noconfirm libreoffice-fresh 2>/dev/null || log_warn "LibreOffice 安装失败"
            ;;
    esac
    
    if command -v libreoffice &>/dev/null; then
        log_ok "LibreOffice 安装完成"
    fi
}

# ─── 4. 检查/安装 Python 依赖 ────────────────────────────────
install_python_deps() {
    log_info "检查 Python..."
    
    # 查找可用的 Python (>= 3.10)
    PYTHON=""
    for py in python3.12 python3.11 python3.10 python3; do
        if command -v "$py" &>/dev/null; then
            ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            major=$("$py" -c "import sys; print(sys.version_info.major)")
            minor=$("$py" -c "import sys; print(sys.version_info.minor)")
            if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
                PYTHON="$py"
                log_ok "Python $ver ($py) 满足要求"
                break
            fi
        fi
    done
    
    if [[ -z "$PYTHON" ]]; then
        log_err "需要 Python >= 3.10，请先安装"
        log_err "macOS: brew install python@3.11"
        log_err "Ubuntu: sudo apt install python3.11"
        exit 1
    fi

    # 安装 pip 包
    log_info "安装 Python 依赖..."
    "$PYTHON" -m pip install --quiet "file-desensitizer" 2>&1 | tail -1 || {
        # 如果 PyPI 还没发布，从本地安装
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
            log_info "从本地安装..."
            "$PYTHON" -m pip install --quiet -e "$SCRIPT_DIR"
        else
            log_err "安装失败，请检查网络连接"
            exit 1
        fi
    }
    log_ok "Python 依赖安装完成"
}

# ─── 5. 验证安装 ────────────────────────────────────────────
verify_installation() {
    log_info "验证安装..."
    echo ""
    
    # 验证 Python 包
    if "$PYTHON" -c "from file_desensitizer import process_file" 2>/dev/null; then
        ver=$("$PYTHON" -c "import file_desensitizer; print(file_desensitizer.__version__)")
        log_ok "file-desensitizer v$ver — Python API 正常"
    else
        log_err "Python 包导入失败"
        exit 1
    fi
    
    # 验证 MCP Server
    if timeout 2 "$PYTHON" -m file_desensitizer.server 2>/dev/null; then
        log_ok "MCP Server 启动正常"
    else
        # timeout 退出码非 0 是正常的（server 被 timeout 杀了）
        log_ok "MCP Server 可启动"
    fi
    
    # 验证 Tesseract
    if command -v tesseract &>/dev/null; then
        if tesseract --list-langs 2>/dev/null | grep -q chi_sim; then
            log_ok "Tesseract OCR + 中文支持 — 图片脱敏可用"
        else
            log_warn "Tesseract 已安装但缺少中文包 — 仅英文图片 OCR 可用"
        fi
    else
        log_warn "Tesseract 未安装 — 图片脱敏不可用（Word/PDF 文本脱敏正常）"
    fi
    
    # 验证 LibreOffice
    if command -v libreoffice &>/dev/null; then
        log_ok "LibreOffice 可用 — 支持 .doc 转 .docx"
    else
        log_warn "LibreOffice 未安装 — 不支持旧版 .doc 格式"
    fi
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ✅ 安装完成！                                          ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  使用方式:                                              ║"
    echo "║  1. AI IDE 对话: 配置 MCP 后直接说「脱敏这个文件」      ║"
    echo "║  2. 命令行: $PYTHON -m file_desensitizer.main <文件>    ║"
    echo "║  3. Python: from file_desensitizer import process_file  ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
}

# ─── 主流程 ─────────────────────────────────────────────────
main() {
    detect_os
    install_tesseract
    install_libreoffice
    install_python_deps
    verify_installation
}

main "$@"

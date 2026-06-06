# 文件信息脱敏工具 (File Desensitizer)

> 自动识别并遮盖图片、Word 文档、PDF 中的敏感信息：姓名、手机号、身份证号、住址、邮箱、银行卡号。生成脱敏副本，原文件不受影响。

---

## 🚀 全自动安装（一条命令）

```bash
bash setup.sh
```

**这个脚本会自动完成一切：**
1. 🔍 检测操作系统（macOS / Ubuntu / Debian / CentOS / Fedora / Arch / Windows）
2. 📦 安装 Tesseract OCR + 中文语言包
3. 📄 安装 LibreOffice（用于 .doc → .docx 转换，可选）
4. 🐍 安装 Python 包及所有依赖
5. ✅ 验证安装是否成功

跑完就能用，**不需要手动处理任何东西**。

> 如果不想用脚本：`pip install file-desensitizer` 即可（但图片 OCR 仍需手动装 Tesseract）。

---

## 🤖 AI IDE 内自动检查

MCP Server 提供两个工具，让 AI 帮用户完成一切：

| MCP 工具 | 功能 |
|----------|------|
| `check_environment` | 自动检查环境，列出缺失依赖和安装命令 |
| `auto_setup` | 一键自动安装缺失依赖（自动识别系统） |

对话中说「检查环境」或「帮我安装」，AI 全自动处理。

---

## 📋 环境要求（参考）

| 依赖 | 版本要求 | 用途 | 是否必须 |
|------|---------|------|:------:|
| Python | >= 3.10 | 运行环境 | ✅ 必须 |
| Tesseract OCR | 任意版本 | 图片文字识别 | ⚠️ 仅图片脱敏需要 |
| Tesseract 中文包 | chi_sim | 中文 OCR | ⚠️ 仅中文图片脱敏需要 |
| LibreOffice | 任意版本 | .doc 转 .docx | ❌ 仅处理旧版 .doc 时需要 |

---

## 📖 手动安装（参考）

> ⚠️ 推荐用上面的 `bash setup.sh`。以下为各系统手动安装命令参考。

### 系统依赖

<details>
<summary><b>macOS</b></summary>

```bash
# Tesseract OCR + 中英文语言包
brew install tesseract tesseract-lang

# 可选：旧版 .doc 转换
brew install --cask libreoffice
```
</details>

<details>
<summary><b>Ubuntu / Debian</b></summary>

```bash
# Tesseract OCR + 中英文语言包
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng

# 可选：旧版 .doc 转换
sudo apt-get install -y libreoffice-writer
```
</details>

<details>
<summary><b>CentOS / RHEL / Fedora</b></summary>

```bash
# Tesseract OCR + 中英文语言包
sudo dnf install -y tesseract tesseract-langpack-chi-sim tesseract-langpack-eng

# 可选：旧版 .doc 转换
sudo dnf install -y libreoffice-writer
```
</details>

<details>
<summary><b>Windows</b></summary>

1. 下载 Tesseract 安装包：https://github.com/UB-Mannheim/tesseract/wiki
2. 安装时勾选 **Chinese (Simplified)** 语言包
3. 将安装目录（如 `C:\Program Files\Tesseract-OCR`）添加到系统 PATH
4. 验证：`tesseract --list-langs`

可选：安装 LibreOffice 用于 .doc 转换
</details>

<details>
<summary><b>Arch Linux</b></summary>

```bash
# Tesseract OCR + 中英文语言包
sudo pacman -S tesseract tesseract-data-chi_sim tesseract-data-eng

# 可选：旧版 .doc 转换
sudo pacman -S libreoffice-fresh
```
</details>

**验证 Tesseract 安装：**
```bash
tesseract --list-langs | grep chi_sim
# 应输出: chi_sim
```

### 第二步：安装 Python 包

```bash
pip install file-desensitizer
```

这会自动安装所有 Python 依赖：
- `pillow>=10.0` — 图像处理
- `pytesseract>=0.3.10` — OCR 接口
- `PyMuPDF>=1.23.0` — PDF 解析
- `python-docx>=1.0.0` — Word 文档读写
- `mcp>=1.0.0` — MCP 协议支持

---

## 📖 三种使用方式

### 🎯 方式一：AI IDE 一键使用（MCP）

在 Trae / Cursor / CodeBuddy 等 AI IDE 中配置 MCP，之后直接在对话中说「脱敏这个文件」即可。

**配置 MCP：** 在 IDE 的 MCP 设置中添加：

```json
{
  "mcpServers": {
    "file-desensitizer": {
      "command": "python",
      "args": ["-m", "file_desensitizer.server"]
    }
  }
}
```

**MCP 提供的工具：**

| 工具名 | 功能 | 必填参数 | 可选参数 |
|--------|------|---------|---------|
| `desensitize_file` | 脱敏单个文件 | `file_path` | `output_dir`, `method`, `pdf_mode` |
| `desensitize_text` | 脱敏纯文本内容 | `text` | — |
| `desensitize_batch` | 批量脱敏多个文件 | `file_paths` | `output_dir`, `method` |

### ⌨️ 方式二：命令行

```bash
# 单文件
file-desensitizer contract.pdf

# 批量
file-desensitizer file1.pdf file2.jpg file3.docx

# 指定输出目录
file-desensitizer document.docx --output-dir ./output

# 图片遮挡方式: black(默认) / blur(模糊) / pixelate(像素化)
file-desensitizer photo.jpg --method blur

# PDF 模式: auto(默认) / text(文本替换) / image(图像遮盖)
file-desensitizer scanned.pdf --pdf-mode image
```

### 🐍 方式三：Python API

```python
from file_desensitizer import process_file, process_files, TextDesensitizer

# 单文件脱敏
result = process_file("contract.pdf", output_dir="./output")
print(result["output_path"])   # 脱敏后文件路径
print(result["records"])        # 脱敏记录列表

# 纯文本脱敏
text, records = TextDesensitizer.desensitize_text("张三 13812345678 北京市朝阳区建国路88号")
# text = "张* 138****5678 北京市朝阳区****"

# 批量脱敏
result = process_files(["a.pdf", "b.docx", "c.jpg"], output_dir="./output")
for r in result["results"]:
    print(f"{r['input_path']} → {r['output_path']}")
```

---

## 🔒 脱敏规则

| 类型 | 规则 | 示例 |
|------|------|------|
| 👤 姓名 | 保留姓，名用*代替 | 张三丰 → 张** |
| 📱 手机号 | 保留前3后4 | 13812345678 → 138****5678 |
| 🆔 身份证号 | 保留前6后4 | 110101199001011234 → 110101********1234 |
| 🏠 住址 | 保留省市区 | 北京市朝阳区建国路88号 → 北京市朝阳区**** |
| 📧 邮箱 | 保留首字符和域名 | lisi@example.com → l\*\*\*@example.com |
| 💳 银行卡号 | 保留后4位 | 622202...0123 → \*\*\*\*0123 |

## 📁 支持的文件类型

| 类型 | 扩展名 | 处理方式 |
|------|--------|---------|
| 🖼️ 图片 | .png .jpg .jpeg .bmp .tiff .webp | OCR识别 → 文字脱敏 → 黑色块/模糊/像素化遮盖 |
| 📝 Word | .docx | 直接修改文档文本，红色标记脱敏内容 |
| 📄 PDF | .pdf | 文本搜索替换 / 渲染为图片+OCR遮盖 |

---

## 📂 项目结构

```
file-desensitizer/
├── SKILL.md                     ← CodeBuddy Skill 配置
├── README.md                    ← 本文件
├── pyproject.toml               ← pip 包配置
├── scripts/                     ← 独立脚本（CodeBuddy Skill 直接调用）
│   ├── main.py                  ← CLI 入口
│   ├── desensitizer.py          ← 核心脱敏引擎
│   ├── image_processor.py       ← 图片处理器
│   ├── docx_processor.py        ← Word 处理器
│   └── pdf_processor.py         ← PDF 处理器
└── src/file_desensitizer/       ← pip 包源码
    ├── __init__.py              ← 包入口
    ├── core.py                  ← 核心脱敏引擎
    ├── main.py                  ← CLI + process_file/process_files
    ├── server.py                ← MCP Server
    ├── image_processor.py
    ├── docx_processor.py
    └── pdf_processor.py
```

---

## ⚠️ 注意事项

1. **原文件不会被修改** — 所有操作在副本上进行
2. **OCR 精度** — 图片脱敏效果取决于 OCR 精度，低分辨率截图和中文手写体识别效果有限
3. **扫描版 PDF** — 建议使用 `--pdf-mode image` 模式
4. **Word 格式** — 仅支持 `.docx`，旧版 `.doc` 需先用 LibreOffice/WPS 转换
5. **脱敏不可逆** — 脱敏后无法恢复，请确保原文件已妥善保存

---

## 📄 License

MIT

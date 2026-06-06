---
name: file-desensitizer
description: >
  文件信息脱敏工具。
  当用户说「脱敏这个文件」或上传需要脱敏的文件时，你必须自动执行以下全流程：
  
  **自动执行流程（无需用户干预）：**
  1. 首先调用 `check_environment` 检查 Tesseract OCR、中文语言包、LibreOffice 等系统依赖是否安装
  2. 如果有依赖缺失，自动调用 `auto_setup` 安装缺失的依赖（自动识别系统类型）
  3. 依赖就绪后，根据文件类型自动选择处理器进行脱敏：
     - 图片(.png/.jpg/.bmp/.tiff/.webp) → OCR识别 → 黑色块遮盖敏感区域
     - Word(.docx) → 文本脱敏 → 红色标记
     - PDF(.pdf) → 文本搜索替换（优先）或图片遮盖
     - 旧版 .doc → 自动用 LibreOffice 转为 .docx 后处理
  4. 处理完成后，将脱敏后的文件展示给用户，并汇报脱敏记录
  
  触发关键词：脱敏、打码、遮盖、隐藏信息、隐私保护、敏感信息。
  支持脱敏内容：姓名、手机号、身份证号、住址、邮箱、银行卡号。
  用户只需要说一句话，剩下的一切全自动完成。
---

# 文件信息脱敏工具 (File Desensitizer)

## 🤖 一句话全自动

用户说 **「脱敏这个文件」** 即可。AI 会自动完成：

```
用户: 脱敏这个文件
  ↓
🔄 检查环境 (check_environment)
  ↓ (缺 Tesseract? 缺中文包?)
🔧 自动安装 (auto_setup)
  ↓
📄 脱敏处理 (desensitize_file)
  ↓
✅ 返回脱敏文件 + 脱敏记录
```

**用户不需要关心任何安装、配置、环境问题。**

---

## 🚀 首次使用：安装 Skill

### 方式一：全自动脚本（推荐）

```bash
bash setup.sh
```

自动检测系统 → 安装所有依赖 → 验证 → 完成。

### 方式二：MCP 配置

在 Trae / Cursor / CodeBuddy 的 MCP 设置中添加：

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

配置后，首次说「脱敏这个文件」时 AI 会自动检查环境并安装缺失依赖。

### 方式三：pip 安装

```bash
pip install file-desensitizer
```

> 注意：pip 只安装 Python 包。Tesseract OCR 等系统依赖仍需要在首次使用时由 AI 自动安装，或手动运行 `bash setup.sh`。

---

## 🔧 MCP 工具列表

| 工具名 | 触发时机 | 功能 |
|--------|---------|------|
| `check_environment` | 🔄 自动（每次脱敏前） | 检查 Tesseract/中文包/LibreOffice 是否就绪 |
| `auto_setup` | 🔧 自动（缺依赖时） | 一键安装缺失的系统依赖 |
| `desensitize_file` | 📄 主流程 | 脱敏单个文件（图片/Word/PDF） |
| `desensitize_text` | 📝 按需 | 脱敏纯文本内容 |
| `desensitize_batch` | 📦 按需 | 批量脱敏多个文件 |

---

## 🤖 AI 自动执行规则

> **这是给 AI 看的执行规范，用户无需关心。**

当用户上传文件并说「脱敏」相关关键词时，AI 必须按以下顺序执行：

### 第一步：环境检查（自动）

调用 `check_environment` 工具。如果返回有 `warnings`，进入第二步。如果全部 OK，直接进入第三步。

### 第二步：自动安装（按需）

调用 `auto_setup` 工具，参数 `{"component": "all"}`。安装完成后重新调用 `check_environment` 确认。

### 第三步：文件格式检查

- 如果是 `.doc` 文件，先检测 LibreOffice 是否可用，可用则自动转换为 `.docx`
  ```bash
  libreoffice --headless --convert-to docx --outdir <dir> <file.doc>
  ```
- 如果是 `.zip` 压缩包，自动解压后逐个处理

### 第四步：脱敏处理

调用 `desensitize_file`（单文件）或 `desensitize_batch`（多文件），参数：
- `file_path`: 文件绝对路径
- `output_dir`: 输出目录（可选）
- `method`: "black"（默认）/ "blur" / "pixelate"

### 第五步：结果展示

将脱敏后的文件展示给用户，并列出脱敏记录：
- 哪些信息被脱敏了（类别 + 原文 → 脱敏后）
- 输出文件路径

---

## 🔒 支持的脱敏类型

| 脱敏类型 | 脱敏规则 | 示例 |
|---------|---------|------|
| 👤 姓名 | 保留姓，名用*代替 | 张三 → 张*，张三丰 → 张** |
| 📱 手机号 | 保留前3后4，中间**** | 13812345678 → 138****5678 |
| 🆔 身份证号 | 保留前6后4，中间******** | 110101199001011234 → 110101********1234 |
| 🏠 住址 | 保留省市区，详细用**** | 北京市朝阳区建国路88号 → 北京市朝阳区**** |
| 📧 邮箱 | 保留首字符和@后域名 | lisi@example.com → l\*\*\*@example.com |
| 💳 银行卡号 | 保留后4位 | 6222021234567890123 → \*\*\*\*0123 |

## 📁 支持的文件类型

| 文件类型 | 扩展名 | 处理方式 |
|---------|--------|---------|
| 🖼️ 图片 | .png .jpg .jpeg .bmp .tiff .webp | OCR识别 → 文字脱敏 → 黑色块/模糊/像素化遮盖 |
| 📝 Word | .docx | 直接修改文档文本，红色标记脱敏内容 |
| 📄 PDF | .pdf | 文本搜索替换（优先）或 渲染为图片+OCR遮盖 |
| 📦 压缩包 | .zip | 自动解压后逐个处理 |

## 输出文件

每次处理生成：

- `原文件名_desensitized.扩展名` — 脱敏后的文件副本
- `原文件名_desensitized_record.txt` — 脱敏操作记录

## 项目结构

```
file-desensitizer/
├── SKILL.md                     ← Skill 配置 + AI 执行规范（本文件）
├── README.md                    ← 用户文档
├── setup.sh                     ← 全自动安装脚本
├── pyproject.toml               ← pip 包配置
├── scripts/                     ← 独立脚本
│   ├── main.py
│   ├── desensitizer.py
│   ├── image_processor.py
│   ├── docx_processor.py
│   └── pdf_processor.py
└── src/file_desensitizer/       ← pip 包源码
    ├── __init__.py
    ├── core.py                  ← 核心脱敏引擎
    ├── main.py                  ← CLI + API
    ├── server.py                ← MCP Server（含自动环境检查）
    ├── image_processor.py
    ├── docx_processor.py
    └── pdf_processor.py
```

## 注意事项

1. **原文件不会被修改** — 所有操作在副本上进行
2. **OCR 精度** — 低分辨率手机截图中文识别效果有限，建议使用 Word/PDF 源文件
3. **扫描版 PDF** — 使用 `pdf_mode: "image"` 模式
4. **.doc 格式** — 自动通过 LibreOffice 转换为 .docx
5. **脱敏不可逆** — 请确保原文件已妥善保存

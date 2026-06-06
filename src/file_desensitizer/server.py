"""
MCP Server for File Desensitizer

提供 MCP 协议接口，让 AI IDE（Trae/Cursor/CodeBuddy 等）通过工具调用实现文件脱敏。

启动方式:
    python -m file_desensitizer.server
    # 或通过 MCP 配置直接启动
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .core import TextDesensitizer
from .main import SUPPORTED_EXTENSIONS, detect_file_type, process_file


# ─── 自动依赖检查 ─────────────────────────────────────────────

def _check_environment() -> dict:
    """启动时自动检测运行环境，返回状态报告"""
    status = {
        "python_ok": True,
        "tesseract_ok": False,
        "tesseract_chinese_ok": False,
        "libreoffice_ok": False,
        "warnings": [],
    }

    # 检查 Tesseract
    tesseract_path = shutil.which("tesseract")
    if tesseract_path:
        status["tesseract_ok"] = True
        try:
            langs = subprocess.check_output(
                [tesseract_path, "--list-langs"],
                stderr=subprocess.STDOUT, text=True, timeout=10
            )
            if "chi_sim" in langs:
                status["tesseract_chinese_ok"] = True
            else:
                status["warnings"].append(
                    "Tesseract 中文语言包 (chi_sim) 未安装，中文图片 OCR 将不可用。"
                    "安装: sudo apt install tesseract-ocr-chi-sim"
                )
        except Exception:
            status["warnings"].append("无法检测 Tesseract 语言包")
    else:
        status["warnings"].append(
            "Tesseract OCR 未安装，图片脱敏功能不可用（Word/PDF 文本脱敏正常）。"
            "安装: 运行 setup.sh 或 sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
        )

    # 检查 LibreOffice
    if shutil.which("libreoffice"):
        status["libreoffice_ok"] = True
    else:
        status["warnings"].append(
            "LibreOffice 未安装，不支持旧版 .doc 格式。安装: sudo apt install libreoffice-writer"
        )

    return status


# 启动时检查
_ENV_STATUS = _check_environment()


# ─── MCP Server 定义 ───────────────────────────────────────────

server = Server("file-desensitizer")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用工具"""
    return [
        Tool(
            name="desensitize_file",
            description=(
                "对文件中的敏感信息进行脱敏处理。"
                "支持图片(.png/.jpg/.jpeg/.bmp/.tiff/.webp)、Word文档(.docx)、PDF(.pdf)。"
                "脱敏内容包括：姓名、手机号、身份证号码、住址、邮箱、银行卡号。"
                "处理后会生成脱敏副本，原文件保持不变。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "需要脱敏的文件路径（绝对路径）",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "输出目录，默认为输入文件所在目录",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["black", "blur", "pixelate"],
                        "description": "图片遮挡方式：black(黑色块，默认)、blur(模糊)、pixelate(像素化)",
                    },
                    "pdf_mode": {
                        "type": "string",
                        "enum": ["auto", "text", "image"],
                        "description": "PDF处理模式：auto(自动，默认)、text(文本替换)、image(图像遮盖)",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="check_environment",
            description=(
                "检查运行环境是否完整。"
                "检测 Tesseract OCR、中文语言包、LibreOffice 等系统依赖是否安装。"
                "如果缺少依赖，会自动提供安装命令。"
                "建议在首次使用前调用此工具。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="auto_setup",
            description=(
                "一键自动安装所有依赖。"
                "会自动检测系统类型（macOS/Ubuntu/CentOS/Arch），"
                "并执行相应的安装命令来安装 Tesseract OCR、LibreOffice 等。"
                "注意：此操作可能需要 sudo 权限。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "enum": ["all", "tesseract", "libreoffice"],
                        "description": "要安装的组件：all(全部)、tesseract(OCR引擎)、libreoffice(旧版doc转换)",
                    },
                },
            },
        ),
        Tool(
            name="desensitize_text",
            description=(
                "对纯文本内容进行脱敏处理。"
                "适用于需要单独脱敏一段文字的场景。"
                "返回脱敏后的文本和脱敏记录。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "需要脱敏的原始文本",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="desensitize_batch",
            description=(
                "批量脱敏多个文件。"
                "支持同时处理多种类型文件。"
                "返回每个文件的处理结果汇总。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "需要脱敏的文件路径列表",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "输出目录，默认为各文件所在目录",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["black", "blur", "pixelate"],
                        "description": "图片遮挡方式",
                    },
                },
                "required": ["file_paths"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """处理工具调用"""
    try:
        # ─── 环境检查 ───────────────────────────────────────
        if name == "check_environment":
            status = _check_environment()
            output = "🔍 **运行环境检查报告**\n\n"
            output += f"Python: ✅\n"
            output += f"Tesseract OCR: {'✅' if status['tesseract_ok'] else '❌ 未安装'}\n"
            output += f"中文 OCR (chi_sim): {'✅' if status['tesseract_chinese_ok'] else '❌ 未安装'}\n"
            output += f"LibreOffice (.doc转换): {'✅' if status['libreoffice_ok'] else '⚠️ 未安装（可选）'}\n"

            if status["warnings"]:
                output += "\n⚠️ **缺少以下依赖：**\n"
                for w in status["warnings"]:
                    output += f"- {w}\n"
                output += "\n💡 **一键修复：** 调用 `auto_setup` 工具自动安装，或运行 `setup.sh`\n"
            else:
                output += "\n✅ 所有依赖已就绪，可以正常使用！\n"

            return [TextContent(type="text", text=output)]

        # ─── 自动安装 ───────────────────────────────────────
        if name == "auto_setup":
            component = arguments.get("component", "all")

            # 找到 setup.sh 路径
            setup_script = None
            search_paths = [
                Path(__file__).parent.parent.parent / "setup.sh",
                Path(__file__).parent.parent / "setup.sh",
                Path.cwd() / "setup.sh",
            ]
            for sp in search_paths:
                if sp.exists():
                    setup_script = str(sp)
                    break

            if setup_script:
                output = f"🔧 **正在自动安装 {component}...**\n\n"
                try:
                    result = subprocess.run(
                        ["bash", setup_script],
                        capture_output=True, text=True, timeout=300
                    )
                    output += result.stdout[-2000:]  # 最后 2000 字符
                    if result.returncode != 0:
                        output += f"\n⚠️ 安装过程有警告: {result.stderr[-500:]}"
                    else:
                        output += "\n✅ 安装完成！"
                except subprocess.TimeoutExpired:
                    output += "\n⚠️ 安装超时，请手动运行 setup.sh"
                except Exception as e:
                    output += f"\n❌ 安装失败: {e}\n请手动运行: bash setup.sh"
            else:
                # 直接执行安装命令
                output = f"🔧 **正在安装 {component}...**\n\n"
                if component in ("all", "tesseract"):
                    output += "安装 Tesseract OCR...\n"
                    try:
                        if shutil.which("apt-get"):
                            subprocess.run(["sudo", "apt-get", "update", "-qq"], timeout=60)
                            subprocess.run(["sudo", "apt-get", "install", "-y", "-qq",
                                "tesseract-ocr", "tesseract-ocr-chi-sim", "tesseract-ocr-eng"], timeout=120)
                            output += "✅ Tesseract 安装完成\n"
                        elif shutil.which("brew"):
                            subprocess.run(["brew", "install", "tesseract", "tesseract-lang"], timeout=180)
                            output += "✅ Tesseract 安装完成\n"
                        elif shutil.which("dnf"):
                            subprocess.run(["sudo", "dnf", "install", "-y",
                                "tesseract", "tesseract-langpack-chi-sim"], timeout=120)
                            output += "✅ Tesseract 安装完成\n"
                        elif shutil.which("pacman"):
                            subprocess.run(["sudo", "pacman", "-S", "--noconfirm",
                                "tesseract", "tesseract-data-chi_sim", "tesseract-data-eng"], timeout=120)
                            output += "✅ Tesseract 安装完成\n"
                        else:
                            output += "⚠️ 未识别的包管理器，请手动安装 Tesseract\n"
                    except Exception as e:
                        output += f"⚠️ Tesseract 安装失败: {e}\n"

                if component in ("all", "libreoffice"):
                    output += "安装 LibreOffice...\n"
                    try:
                        if shutil.which("apt-get"):
                            subprocess.run(["sudo", "apt-get", "install", "-y", "-qq",
                                "libreoffice-writer"], timeout=120)
                            output += "✅ LibreOffice 安装完成\n"
                        elif shutil.which("brew"):
                            subprocess.run(["brew", "install", "--cask", "libreoffice"], timeout=300)
                            output += "✅ LibreOffice 安装完成\n"
                        else:
                            output += "⚠️ 请手动安装 LibreOffice\n"
                    except Exception as e:
                        output += f"⚠️ LibreOffice 安装失败: {e}\n"

                output += "\n💡 建议重新运行 `check_environment` 确认安装状态"

            return [TextContent(type="text", text=output)]

        # ─── 文本脱敏 ───────────────────────────────────────
        if name == "desensitize_text":
            text = arguments.get("text", "")
            if not text:
                return [TextContent(type="text", text="❌ 错误：请提供要脱敏的文本内容")]

            result_text, records = TextDesensitizer.desensitize_text(text)

            output = "📝 **脱敏结果**\n\n"
            output += f"脱敏后文本：\n```\n{result_text}\n```\n\n"
            if records:
                output += "**脱敏记录：**\n"
                for r in records:
                    output += f"- [{r['category']}] {r['original']} → {r['masked']}\n"
            else:
                output += "ℹ️ 未检测到敏感信息\n"

            return [TextContent(type="text", text=output)]

        elif name == "desensitize_file":
            file_path = arguments.get("file_path", "")
            if not file_path:
                return [TextContent(type="text", text="❌ 错误：请提供文件路径")]

            if not os.path.exists(file_path):
                return [TextContent(type="text", text=f"❌ 错误：文件不存在 — {file_path}")]

            output_dir = arguments.get("output_dir")
            method = arguments.get("method", "black")
            pdf_mode = arguments.get("pdf_mode", "auto")

            result = process_file(
                file_path,
                output_dir=output_dir,
                method=method,
                pdf_mode=pdf_mode,
            )

            if not result.get("success"):
                return [TextContent(
                    type="text",
                    text=f"❌ 脱敏失败：{result.get('error', '未知错误')}"
                )]

            output = f"✅ **脱敏完成！**\n\n"
            output += f"📄 输入文件：{result.get('input_path', '')}\n"
            output += f"📁 脱敏文件：{result.get('output_path', '')}\n\n"

            records = result.get("records", [])
            if records:
                output += "**脱敏详情：**\n"
                for r in records:
                    output += f"- [{r['category']}] {r['original']} → {r['masked']}\n"
                output += f"\n共处理 {len(records)} 条敏感信息\n"
            else:
                output += "ℹ️ 未检测到敏感信息\n"

            return [TextContent(type="text", text=output)]

        elif name == "desensitize_batch":
            file_paths = arguments.get("file_paths", [])
            if not file_paths:
                return [TextContent(type="text", text="❌ 错误：请提供文件路径列表")]

            output_dir = arguments.get("output_dir")
            method = arguments.get("method", "black")

            from .main import process_files

            result = process_files(
                file_paths,
                output_dir=output_dir,
                method=method,
            )

            output = f"📊 **批量脱敏结果**\n\n"
            output += f"总数：{result.get('total', 0)} | "
            output += f"成功：{result.get('success_count', 0)} | "
            output += f"失败：{result.get('fail_count', 0)}\n\n"

            for r in result.get("results", []):
                fname = os.path.basename(r.get("input_path", "?"))
                if r.get("success"):
                    records = r.get("records", [])
                    count = len(records)
                    output += f"✅ **{fname}** — {count} 条敏感信息已脱敏\n"
                    for rec in records:
                        output += f"   [{rec['category']}] {rec['original']} → {rec['masked']}\n"
                    output += f"   输出：{r.get('output_path', '')}\n\n"
                else:
                    output += f"❌ **{fname}** — {r.get('error', '失败')}\n\n"

            return [TextContent(type="text", text=output)]

        else:
            return [TextContent(type="text", text=f"❌ 未知工具：{name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"❌ 处理异常：{str(e)}")]


def main():
    """MCP Server 入口"""
    import asyncio
    import sys

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()

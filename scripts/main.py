#!/usr/bin/env python3
"""
文件脱敏 Skill 主入口

支持对以下文件类型进行敏感信息脱敏：
- 图片 (.png, .jpg, .jpeg, .bmp, .tiff, .webp)
- Word 文档 (.docx)
- PDF 文件 (.pdf)

用法:
    python main.py <文件路径> [选项]

选项:
    --output-dir <目录>    输出目录（默认为输入文件同目录）
    --method <方式>         图片遮挡方式: black(默认)/blur/pixelate
    --pdf-mode <模式>       PDF处理模式: auto(默认)/text/image
    --text-only             仅输出脱敏文本（图片处理时）
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# 添加 scripts 目录到 path
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from desensitizer import TextDesensitizer


SUPPORTED_EXTENSIONS = {
    # 图片
    '.png': 'image',
    '.jpg': 'image',
    '.jpeg': 'image',
    '.bmp': 'image',
    '.tiff': 'image',
    '.tif': 'image',
    '.webp': 'image',
    # 文档
    '.docx': 'docx',
    # PDF
    '.pdf': 'pdf',
}


def detect_file_type(file_path: str) -> Optional[str]:
    """检测文件类型"""
    suffix = Path(file_path).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(suffix)


def process_file(
    file_path: str,
    output_dir: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    处理单个文件的脱敏。

    Args:
        file_path: 文件路径
        output_dir: 输出目录
        **kwargs: 传递给具体处理器的参数

    Returns:
        处理结果字典
    """
    file_path = str(Path(file_path).resolve())
    file_type = detect_file_type(file_path)

    if file_type is None:
        suffix = Path(file_path).suffix.lower()
        return {
            "success": False,
            "error": f"不支持的文件类型: {suffix}。支持的类型: {', '.join(SUPPORTED_EXTENSIONS.keys())}",
            "input_path": file_path,
        }

    if file_type == 'image':
        from image_processor import process_image
        return process_image(
            file_path,
            output_dir=output_dir,
            redact_method=kwargs.get('method', 'black'),
            text_only=kwargs.get('text_only', False),
        )
    elif file_type == 'docx':
        from docx_processor import process_docx
        return process_docx(
            file_path,
            output_dir=output_dir,
            mark_color=kwargs.get('mark_color', True),
        )
    elif file_type == 'pdf':
        from pdf_processor import process_pdf
        return process_pdf(
            file_path,
            output_dir=output_dir,
            mode=kwargs.get('pdf_mode', 'auto'),
        )


def process_files(
    file_paths: list,
    output_dir: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    批量处理多个文件。

    Args:
        file_paths: 文件路径列表
        output_dir: 输出目录
        **kwargs: 传递给处理器的参数

    Returns:
        批量处理结果
    """
    results = []
    success_count = 0
    fail_count = 0

    for fp in file_paths:
        result = process_file(fp, output_dir=output_dir, **kwargs)
        results.append(result)
        if result.get('success'):
            success_count += 1
        else:
            fail_count += 1

    return {
        "success": True,
        "total": len(file_paths),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
    }


def print_help():
    """打印帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════╗
║            文件信息脱敏工具  File Desensitizer           ║
╠══════════════════════════════════════════════════════════╣
║  支持类型: 图片(png/jpg/bmp/tiff/webp) | Word(docx) | PDF ║
║  脱敏内容: 姓名 | 手机号 | 身份证号 | 住址 | 邮箱 | 银行卡 ║
╚══════════════════════════════════════════════════════════╝

用法:
    python main.py <文件路径> [选项]
    python main.py <文件1> <文件2> ... [选项]

选项:
    --output-dir <目录>    输出目录（默认为输入文件同目录）
    --method <方式>         图片遮挡方式: black(默认) / blur / pixelate
    --pdf-mode <模式>       PDF处理模式: auto(默认) / text / image
    --text-only             仅输出脱敏文本（图片处理）
    --help                  显示此帮助信息

示例:
    python main.py contract.pdf
    python main.py photo.jpg --method blur
    python main.py resume.docx --output-dir ./output
    python main.py a.jpg b.pdf c.docx --output-dir ./desensitized
""")


def parse_args(args: list) -> tuple:
    """解析命令行参数"""
    files = []
    kwargs = {
        'output_dir': None,
        'method': 'black',
        'pdf_mode': 'auto',
        'text_only': False,
    }

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--help', '-h'):
            print_help()
            sys.exit(0)
        elif arg == '--output-dir':
            if i + 1 < len(args):
                kwargs['output_dir'] = args[i + 1]
                i += 1
        elif arg == '--method':
            if i + 1 < len(args):
                kwargs['method'] = args[i + 1]
                i += 1
        elif arg == '--pdf-mode':
            if i + 1 < len(args):
                kwargs['pdf_mode'] = args[i + 1]
                i += 1
        elif arg == '--text-only':
            kwargs['text_only'] = True
        elif not arg.startswith('--'):
            files.append(arg)
        i += 1

    return files, kwargs


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    files, kwargs = parse_args(sys.argv[1:])

    if not files:
        print("❌ 请指定要处理的文件路径", file=sys.stderr)
        sys.exit(1)

    # 验证文件存在
    missing = [f for f in files if not Path(f).exists()]
    if missing:
        print(f"❌ 以下文件不存在: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    print(f"📋 待处理文件: {len(files)} 个")
    print(f"📂 输出目录: {kwargs.get('output_dir') or '(与输入文件同目录)'}")
    print()

    if len(files) == 1:
        result = process_file(files[0], **kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = process_files(files, **kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))

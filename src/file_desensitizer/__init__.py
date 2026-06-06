"""
文件信息脱敏工具 - File Desensitizer

自动识别并遮盖图片、Word 文档、PDF 中的敏感信息：
- 姓名、手机号、身份证号、住址、邮箱、银行卡号

Usage:
    # CLI
    file-desensitizer document.pdf
    file-desensitizer photo.jpg --method blur

    # Python API
    from file_desensitizer import process_file
    result = process_file("contract.pdf", output_dir="./output")
"""

__version__ = "0.1.0"

from .core import TextDesensitizer
from .main import process_file, process_files

__all__ = [
    "process_file",
    "process_files",
    "TextDesensitizer",
    "launch_gui",
]

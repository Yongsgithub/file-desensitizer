# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec 文件
打包为单个 .exe 文件，Windows/macOS/Linux 均支持
"""

import sys
from pathlib import Path

# PyInstaller spec 中 SPECPATH 是 spec 文件所在目录
SRC_DIR = Path(SPECPATH) / "src" / "file_desensitizer"

a = Analysis(
    [str(SRC_DIR / "gui" / "app.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[
        # 嵌入 SKILL.md 作为 about 信息（可选）
    ],
    hiddenimports=[
        "file_desensitizer",
        "file_desensitizer.core",
        "file_desensitizer.main",
        "file_desensitizer.image_processor",
        "file_desensitizer.docx_processor",
        "file_desensitizer.pdf_processor",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageFilter",
        "pytesseract",
        "fitz",
        "docx",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "notebook",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 单文件打包
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="文件脱敏工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Windows: 不显示命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 可添加 .ico 文件
)

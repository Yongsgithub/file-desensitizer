"""
文件信息脱敏工具 - 本地离线桌面版 (GUI)

完全本地运行，数据不上云。
支持拖拽上传、文件选择、脱敏预览、一键导出。

启动方式:
    python -m file_desensitizer.gui.app
    python app.py
"""

import os
import sys
import json
import shutil
import tempfile
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 将包目录加入 path（兼容直接运行和 pip 安装）
_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

# 父包导入
from file_desensitizer.core import TextDesensitizer
from file_desensitizer.main import process_file, process_files, SUPPORTED_EXTENSIONS, detect_file_type

# ─── GUI 导入 ────────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# 拖放支持（Windows/macOS/Linux）
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False


# ─── 样式常量 ─────────────────────────────────────────────────
COLORS = {
    "bg": "#f0f2f5",
    "card": "#ffffff",
    "primary": "#4f46e5",
    "primary_hover": "#4338ca",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "text": "#1e293b",
    "text_secondary": "#64748b",
    "border": "#e2e8f0",
    "drop_zone": "#eef2ff",
    "drop_zone_border": "#818cf8",
    "drop_zone_active": "#dbeafe",
}

FONTS = {
    "title": ("Microsoft YaHei", 18, "bold"),
    "subtitle": ("Microsoft YaHei", 11),
    "body": ("Microsoft YaHei", 10),
    "small": ("Microsoft YaHei", 9),
    "mono": ("Cascadia Code", 9),
}


# ─── 主应用窗口 ───────────────────────────────────────────────
class DesensitizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🔒 文件信息脱敏工具")
        self.root.geometry("900x700")
        self.root.minsize(700, 550)
        self.root.configure(bg=COLORS["bg"])

        # 状态
        self.files: List[str] = []
        self.results: List[Dict] = []
        self.processing = False
        self.output_dir = None

        # 设置窗口图标和样式
        self._setup_styles()
        self._build_ui()

        # 居中显示
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 900) // 2
        y = (self.root.winfo_screenheight() - 700) // 2
        self.root.geometry(f"+{x}+{y}")

        # 启动时检查环境
        self.root.after(500, self._check_environment_on_startup)

    # ─── 样式 ─────────────────────────────────────────────
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["card"], relief="solid", borderwidth=1)
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["body"])
        style.configure("Card.TLabel", background=COLORS["card"], foreground=COLORS["text"])
        style.configure("Title.TLabel", font=FONTS["title"], foreground=COLORS["primary"])
        style.configure("Subtitle.TLabel", font=FONTS["subtitle"], foreground=COLORS["text_secondary"])
        style.configure("Small.TLabel", font=FONTS["small"], foreground=COLORS["text_secondary"])
        style.configure("Primary.TButton", font=FONTS["body"], padding=(20, 8))
        style.configure("Success.TLabel", font=FONTS["body"], foreground=COLORS["success"])
        style.configure("Danger.TLabel", font=FONTS["body"], foreground=COLORS["danger"])

    # ─── UI 构建 ──────────────────────────────────────────
    def _build_ui(self):
        # 顶部标题栏
        header = ttk.Frame(self.root, style="TFrame")
        header.pack(fill="x", padx=0, pady=0)

        header_inner = ttk.Frame(header, style="TFrame")
        header_inner.pack(fill="x", padx=30, pady=(20, 10))

        ttk.Label(header_inner, text="🔒 文件信息脱敏工具", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header_inner,
            text="完全本地运行 · 数据不上云 · 支持 Word / PDF / 压缩包",
            style="Subtitle.TLabel"
        ).pack(anchor="w", pady=(4, 0))

        # 主体区域
        main = ttk.Frame(self.root, style="TFrame")
        main.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # ── 左侧：拖放区 + 文件列表 ──
        left = ttk.Frame(main, style="TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self._build_drop_zone(left)
        self._build_file_list(left)

        # ── 右侧：操作面板 + 结果预览 ──
        right = ttk.Frame(main, style="TFrame")
        right.pack(side="right", fill="both", expand=True)

        self._build_action_panel(right)
        self._build_result_panel(right)

        # 底部状态栏
        self._build_status_bar()

    def _build_drop_zone(self, parent):
        """拖放上传区域"""
        self.drop_frame = tk.Frame(
            parent,
            bg=COLORS["drop_zone"],
            highlightbackground=COLORS["drop_zone_border"],
            highlightthickness=2,
            cursor="hand2",
        )
        self.drop_frame.pack(fill="x", pady=(0, 10))

        drop_inner = tk.Frame(self.drop_frame, bg=COLORS["drop_zone"])
        drop_inner.pack(padx=20, pady=30)

        tk.Label(
            drop_inner,
            text="📂",
            font=("Microsoft YaHei", 32),
            bg=COLORS["drop_zone"],
        ).pack()

        tk.Label(
            drop_inner,
            text="点击选择文件 或 拖放文件到此处",
            font=FONTS["subtitle"],
            bg=COLORS["drop_zone"],
            fg=COLORS["text"],
        ).pack(pady=(8, 4))

        tk.Label(
            drop_inner,
            text="支持: Word (.docx) ｜ PDF (.pdf) ｜ 压缩包 (.zip)",
            font=FONTS["small"],
            bg=COLORS["drop_zone"],
            fg=COLORS["text_secondary"],
        ).pack()

        # 绑定事件
        self.drop_frame.bind("<Button-1>", lambda e: self._select_files())
        drop_inner.bind("<Button-1>", lambda e: self._select_files())
        for child in drop_inner.winfo_children():
            child.bind("<Button-1>", lambda e: self._select_files())

        # 悬停效果
        self.drop_frame.bind("<Enter>", lambda e: self._on_drop_enter())
        self.drop_frame.bind("<Leave>", lambda e: self._on_drop_leave())

        # 注册拖放目标（tkinterdnd2）
        if TKDND_AVAILABLE:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
            self.drop_frame.dnd_bind('<<DragEnter>>', lambda e: self._on_drop_enter())
            self.drop_frame.dnd_bind('<<DragLeave>>', lambda e: self._on_drop_leave())

    def _on_drop(self, event):
        """处理拖放文件"""
        files = self._parse_dropped_files(event.data)
        if files:
            self._add_files(files)
        self._on_drop_leave()
        return "break"

    def _parse_dropped_files(self, data: str) -> List[str]:
        """解析拖放事件返回的文件路径字符串

        tkinterdnd2 返回格式示例：
            Windows: "C:/file1.txt {C:/path with spaces/file2.txt}"
            多文件用空格分隔，含空格路径用 {} 包裹
        """
        files = []
        i = 0
        while i < len(data):
            if data[i] == '{':
                end = data.find('}', i)
                if end == -1:
                    end = len(data)
                files.append(data[i + 1:end])
                i = end + 1
            elif data[i] == ' ':
                i += 1
            else:
                end = data.find(' ', i)
                if end == -1:
                    end = len(data)
                files.append(data[i:end])
                i = end + 1
        # 统一路径分隔符并过滤空值
        return [f.replace('/', os.sep) for f in files if f.strip()]

    def _on_drop_enter(self):
        self.drop_frame.configure(bg=COLORS["drop_zone_active"])
        for child in self.drop_frame.winfo_children():
            try:
                child.configure(bg=COLORS["drop_zone_active"])
                for sub in child.winfo_children():
                    sub.configure(bg=COLORS["drop_zone_active"])
            except Exception:
                pass

    def _on_drop_leave(self):
        self.drop_frame.configure(bg=COLORS["drop_zone"])
        for child in self.drop_frame.winfo_children():
            try:
                child.configure(bg=COLORS["drop_zone"])
                for sub in child.winfo_children():
                    sub.configure(bg=COLORS["drop_zone"])
            except Exception:
                pass

    def _build_file_list(self, parent):
        """文件列表"""
        list_frame = ttk.Frame(parent, style="Card.TFrame")
        list_frame.pack(fill="both", expand=True)

        # 列表头
        header_frame = tk.Frame(list_frame, bg=COLORS["card"])
        header_frame.pack(fill="x", padx=12, pady=(12, 6))

        tk.Label(
            header_frame, text="📋 待处理文件",
            font=FONTS["subtitle"], bg=COLORS["card"], fg=COLORS["text"]
        ).pack(side="left")

        self.file_count_label = tk.Label(
            header_frame, text="0 个文件",
            font=FONTS["small"], bg=COLORS["card"], fg=COLORS["text_secondary"]
        )
        self.file_count_label.pack(side="right")

        # 文件列表（Canvas + Scrollbar）
        list_container = tk.Frame(list_frame, bg=COLORS["card"])
        list_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.file_canvas = tk.Canvas(list_container, bg=COLORS["card"], highlightthickness=0)
        self.file_scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.file_canvas.yview)
        self.file_list_frame = tk.Frame(self.file_canvas, bg=COLORS["card"])

        self.file_list_frame.bind("<Configure>", lambda e: self.file_canvas.configure(
            scrollregion=self.file_canvas.bbox("all")
        ))

        self.file_canvas.create_window((0, 0), window=self.file_list_frame, anchor="nw")
        self.file_canvas.configure(yscrollcommand=self.file_scrollbar.set)

        self.file_canvas.pack(side="left", fill="both", expand=True)
        self.file_scrollbar.pack(side="right", fill="y")

        # 空状态
        self.empty_label = tk.Label(
            self.file_list_frame,
            text="暂无文件\n点击上方区域或拖放文件添加",
            font=FONTS["small"],
            bg=COLORS["card"],
            fg=COLORS["text_secondary"],
        )
        self.empty_label.pack(pady=40)

    def _build_action_panel(self, parent):
        """操作按钮面板"""
        action_frame = ttk.Frame(parent, style="Card.TFrame")
        action_frame.pack(fill="x", pady=(0, 10))

        action_inner = tk.Frame(action_frame, bg=COLORS["card"])
        action_inner.pack(fill="x", padx=16, pady=16)

        tk.Label(
            action_inner, text="⚙️ 操作",
            font=FONTS["subtitle"], bg=COLORS["card"], fg=COLORS["text"]
        ).pack(anchor="w", pady=(0, 10))

        # 输出目录
        out_frame = tk.Frame(action_inner, bg=COLORS["card"])
        out_frame.pack(fill="x", pady=(0, 12))
        tk.Label(out_frame, text="输出目录:", font=FONTS["body"], bg=COLORS["card"]).pack(side="left")
        self.output_var = tk.StringVar(value="(与源文件同目录)")
        tk.Label(
            out_frame, textvariable=self.output_var,
            font=FONTS["small"], bg=COLORS["card"], fg=COLORS["text_secondary"]
        ).pack(side="left", padx=(6, 0))
        tk.Button(
            out_frame, text="更改", font=FONTS["small"],
            bg=COLORS["primary"], fg="white", borderwidth=0,
            padx=12, pady=2, cursor="hand2",
            command=self._select_output_dir,
        ).pack(side="right")

        # 主按钮
        btn_frame = tk.Frame(action_inner, bg=COLORS["card"])
        btn_frame.pack(fill="x")

        self.process_btn = tk.Button(
            btn_frame, text="🔒 开始脱敏",
            font=("Microsoft YaHei", 12, "bold"),
            bg=COLORS["primary"], fg="white",
            activebackground=COLORS["primary_hover"], activeforeground="white",
            borderwidth=0, padx=24, pady=10, cursor="hand2",
            command=self._start_processing,
        )
        self.process_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.clear_btn = tk.Button(
            btn_frame, text="清空列表",
            font=FONTS["body"],
            bg="#e2e8f0", fg=COLORS["text"],
            activebackground="#cbd5e1", activeforeground=COLORS["text"],
            borderwidth=0, padx=16, pady=10, cursor="hand2",
            command=self._clear_files,
        )
        self.clear_btn.pack(side="right")

        # 进度条
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            action_inner, variable=self.progress_var, maximum=100, mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=(12, 0))

        self.progress_label = tk.Label(
            action_inner, text="", font=FONTS["small"],
            bg=COLORS["card"], fg=COLORS["text_secondary"]
        )
        self.progress_label.pack()

    def _build_result_panel(self, parent):
        """结果预览面板"""
        result_frame = ttk.Frame(parent, style="Card.TFrame")
        result_frame.pack(fill="both", expand=True)

        result_header = tk.Frame(result_frame, bg=COLORS["card"])
        result_header.pack(fill="x", padx=12, pady=(12, 6))

        tk.Label(
            result_header, text="📊 脱敏结果",
            font=FONTS["subtitle"], bg=COLORS["card"], fg=COLORS["text"]
        ).pack(side="left")

        self.result_count_label = tk.Label(
            result_header, text="",
            font=FONTS["small"], bg=COLORS["card"], fg=COLORS["success"]
        )
        self.result_count_label.pack(side="right")

        # 结果文本框
        self.result_text = scrolledtext.ScrolledText(
            result_frame,
            font=FONTS["mono"],
            bg="#f8fafc",
            fg=COLORS["text"],
            wrap="word",
            state="disabled",
            borderwidth=0,
            padx=12, pady=10,
        )
        self.result_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # 初始提示
        self._set_result_text("处理完成后，结果将显示在此处\n\n脱敏类型：姓名 · 手机号 · 身份证号 · 住址 · 邮箱 · 银行卡号 · 学号 · 出生年月 · 户籍地址")

    def _build_status_bar(self):
        """底部状态栏"""
        status_frame = tk.Frame(self.root, bg=COLORS["border"], height=1)
        status_frame.pack(fill="x", side="bottom")

        bar = tk.Frame(self.root, bg=COLORS["card"])
        bar.pack(fill="x", side="bottom")

        self.env_status = tk.Label(
            bar, text="🔍 正在检查环境...",
            font=FONTS["small"], bg=COLORS["card"], fg=COLORS["text_secondary"]
        )
        self.env_status.pack(side="left", padx=16, pady=6)

        self.version_label = tk.Label(
            bar, text="v0.1.0",
            font=FONTS["small"], bg=COLORS["card"], fg=COLORS["text_secondary"]
        )
        self.version_label.pack(side="right", padx=16, pady=6)

    # ─── 文件操作 ─────────────────────────────────────────
    def _select_files(self):
        """选择文件对话框"""
        extensions = [
            ("所有支持的文件", "*.docx *.pdf *.zip"),
            ("Word 文档", "*.docx"),
            ("PDF 文件", "*.pdf"),
            ("压缩包", "*.zip"),
        ]
        files = filedialog.askopenfilenames(
            title="选择需要脱敏的文件",
            filetypes=extensions,
        )
        if files:
            self._add_files(list(files))

    def _add_files(self, files: List[str]):
        """添加文件到列表"""
        added = 0
        for f in files:
            if f not in self.files:
                ext = Path(f).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    self.files.append(f)
                    added += 1

        if added > 0:
            self._refresh_file_list()

    def _refresh_file_list(self):
        """刷新文件列表显示"""
        # 清除现有
        for w in self.file_list_frame.winfo_children():
            w.destroy()

        self.empty_label = None

        if not self.files:
            self.empty_label = tk.Label(
                self.file_list_frame,
                text="暂无文件\n点击上方区域或拖放文件添加",
                font=FONTS["small"],
                bg=COLORS["card"],
                fg=COLORS["text_secondary"],
            )
            self.empty_label.pack(pady=40)
        else:
            for i, f in enumerate(self.files):
                path = Path(f)
                ext = path.suffix.lower()
                icon = {"docx": "📝", "pdf": "📄", "zip": "📦"}.get(ext, "📁")

                row = tk.Frame(self.file_list_frame, bg=COLORS["card"])
                row.pack(fill="x", padx=4, pady=1)

                tk.Label(
                    row, text=icon, font=FONTS["body"], bg=COLORS["card"]
                ).pack(side="left", padx=(8, 4))

                tk.Label(
                    row, text=path.name, font=FONTS["body"],
                    bg=COLORS["card"], fg=COLORS["text"], anchor="w",
                ).pack(side="left", fill="x", expand=True)

                tk.Label(
                    row, text=f"{path.stat().st_size / 1024:.1f} KB",
                    font=FONTS["small"], bg=COLORS["card"], fg=COLORS["text_secondary"]
                ).pack(side="left", padx=8)

                # 删除按钮
                del_btn = tk.Label(
                    row, text="✕", font=FONTS["body"],
                    bg=COLORS["card"], fg=COLORS["danger"], cursor="hand2",
                )
                del_btn.pack(side="right", padx=(0, 8))
                del_btn.bind("<Button-1>", lambda e, idx=i: self._remove_file(idx))

        self.file_count_label.configure(text=f"{len(self.files)} 个文件")

    def _remove_file(self, index: int):
        """移除文件"""
        if 0 <= index < len(self.files):
            self.files.pop(index)
            self._refresh_file_list()

    def _clear_files(self):
        """清空文件列表"""
        self.files.clear()
        self.results.clear()
        self._refresh_file_list()
        self._set_result_text("已清空。添加文件后点击「开始脱敏」")

    def _select_output_dir(self):
        """选择输出目录"""
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir = d
            self.output_var.set(d)

    # ─── 处理流程 ─────────────────────────────────────────
    def _start_processing(self):
        """开始脱敏处理"""
        if not self.files:
            messagebox.showwarning("提示", "请先添加需要脱敏的文件")
            return

        if self.processing:
            return

        self.processing = True
        self.process_btn.configure(text="⏳ 处理中...", state="disabled")
        self.clear_btn.configure(state="disabled")
        self.progress_var.set(0)
        self.progress_label.configure(text="正在准备...")
        self._set_result_text("⏳ 正在处理，请稍候...\n")

        # 后台线程处理
        thread = threading.Thread(target=self._process_files, daemon=True)
        thread.start()

    def _process_files(self):
        """后台处理线程"""
        total = len(self.files)
        self.results = []
        all_records = []

        for i, f in enumerate(self.files):
            # 更新进度
            progress_pct = ((i) / total) * 100
            self.root.after(0, lambda p=progress_pct: self.progress_var.set(p))
            self.root.after(0, lambda n=Path(f).name: self.progress_label.configure(
                text=f"正在处理: {n}"
            ))

            # 检测并转换 .doc
            actual_file = f
            ext = Path(f).suffix.lower()
            if ext == ".doc":
                actual_file = self._convert_doc_to_docx(f)
                if not actual_file:
                    self.results.append({
                        "success": False,
                        "input_path": f,
                        "error": "无法转换 .doc 文件（需要 LibreOffice）",
                    })
                    continue

            try:
                result = process_file(
                    actual_file,
                    output_dir=self.output_dir,
                )
                self.results.append(result)
                if result.get("success"):
                    all_records.extend(result.get("records", []))
            except Exception as e:
                self.results.append({
                    "success": False,
                    "input_path": f,
                    "error": str(e),
                })

        # 完成
        self.root.after(0, lambda: self.progress_var.set(100))
        self.root.after(0, lambda: self.progress_label.configure(text="✅ 处理完成"))
        self.root.after(0, self._on_processing_done)

    def _convert_doc_to_docx(self, doc_path: str) -> Optional[str]:
        """使用 LibreOffice 将 .doc 转换为 .docx"""
        if not shutil.which("libreoffice"):
            return None
        try:
            tmpdir = tempfile.mkdtemp()
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", tmpdir, doc_path],
                timeout=60, capture_output=True,
            )
            docx_name = Path(doc_path).stem + ".docx"
            docx_path = os.path.join(tmpdir, docx_name)
            if os.path.exists(docx_path):
                return docx_path
        except Exception:
            pass
        return None

    def _on_processing_done(self):
        """处理完成回调"""
        self.processing = False
        self.process_btn.configure(text="🔒 开始脱敏", state="normal")
        self.clear_btn.configure(state="normal")

        success_count = sum(1 for r in self.results if r.get("success"))
        fail_count = len(self.results) - success_count
        total_records = sum(len(r.get("records", [])) for r in self.results if r.get("success"))

        self.result_count_label.configure(
            text=f"✅ {success_count} 成功  ❌ {fail_count} 失败"
        )

        # 构建结果文本
        output = f"处理完成: {success_count}/{len(self.results)} 成功\n"
        output += f"检测到 {total_records} 条敏感信息\n"
        output += "─" * 50 + "\n\n"

        for i, result in enumerate(self.results):
            fname = Path(result.get("input_path", "?")).name
            if result.get("success"):
                records = result.get("records", [])
                output += f"✅ {fname}\n"
                if records:
                    for rec in records:
                        output += f"   [{rec['category']}] {rec['original']} → {rec['masked']}\n"
                else:
                    output += "   ℹ️ 未检测到敏感信息\n"
                output += f"   📁 {result.get('output_path', '')}\n\n"
            else:
                output += f"❌ {fname}\n"
                output += f"   错误: {result.get('error', '未知')}\n\n"

        output += "─" * 50 + "\n"
        output += f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += "所有处理均在本地完成，数据未上传。\n"

        self._set_result_text(output)

        # 弹窗
        if total_records > 0:
            messagebox.showinfo(
                "脱敏完成",
                f"成功处理 {success_count} 个文件\n"
                f"检测并脱敏 {total_records} 条敏感信息\n\n"
                f"脱敏后的文件已保存至输出目录。"
            )
        else:
            messagebox.showinfo(
                "脱敏完成",
                f"处理了 {success_count} 个文件，未检测到敏感信息。"
            )

    def _set_result_text(self, text: str):
        """设置结果文本"""
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled")

    # ─── 环境检查 ─────────────────────────────────────────
    def _check_environment_on_startup(self):
        """启动时检查环境"""
        def check():
            import importlib
            status_parts = []

            # LibreOffice（.doc 转 .docx 需要）
            lo_ok = shutil.which("libreoffice") is not None
            status_parts.append("LibreOffice ✅" if lo_ok else "LibreOffice ❌ (.doc支持)")

            # Python 依赖（移除 image/Pillow/pytesseract 相关）
            deps_ok = True
            for mod in ["fitz", "docx"]:
                try:
                    importlib.import_module(mod)
                except ImportError:
                    deps_ok = False
                    break
            status_parts.append("Python依赖 ✅" if deps_ok else "Python依赖 ⚠️")

            self.root.after(0, lambda: self.env_status.configure(
                text="  |  ".join(status_parts)
            ))

        threading.Thread(target=check, daemon=True).start()


# ─── 启动入口 ──────────────────────────────────────────────────
def main():
    if TKDND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = DesensitizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

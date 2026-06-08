#!/usr/bin/env python3
"""
压缩包处理器 - 支持 .zip 上传、解压、逐份脱敏、重新压缩

流程：
1. 解压 zip 到临时目录
2. 遍历临时目录，对每个支持的文档（docx/pdf）进行脱敏
3. 将脱敏后的文件打包为新 zip
4. 返回处理结果
"""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, List

from .main import SUPPORTED_EXTENSIONS, process_file


def process_archive(
    archive_path: str,
    output_dir: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    处理压缩包：解压 → 逐份脱敏 → 重新打包。

    Args:
        archive_path: zip 文件路径
        output_dir: 输出目录
        **kwargs: 传递给内部 process_file 的参数

    Returns:
        处理结果字典
    """
    archive_path = str(Path(archive_path).resolve())
    archive_name = Path(archive_path).stem

    if output_dir is None:
        output_dir = str(Path(archive_path).parent)
    output_dir = str(Path(output_dir).resolve())

    # 创建临时工作目录
    work_dir = tempfile.mkdtemp(prefix="desensitizer_archive_")
    extract_dir = os.path.join(work_dir, "extracted")
    processed_dir = os.path.join(work_dir, "processed")

    os.makedirs(extract_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    try:
        # ── 1. 解压 ──
        extracted_files = _extract_zip(archive_path, extract_dir)

        # 查找所有支持的文件
        supported_files = []
        for f in extracted_files:
            ext = Path(f).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS and SUPPORTED_EXTENSIONS[ext] not in ('archive',):
                supported_files.append(f)

        if not supported_files:
            return {
                "success": False,
                "error": "压缩包内未找到可处理的文件（支持 .docx / .pdf）",
                "input_path": archive_path,
                "records": [],
            }

        # ── 2. 逐份脱敏 ──
        all_records: List[Dict] = []
        processed_files: List[str] = []
        failed_files: List[Dict] = []

        for src_file in supported_files:
            rel_path = os.path.relpath(src_file, extract_dir)
            # 构造输出子目录（保留相对目录结构）
            dst_subdir = os.path.dirname(rel_path)
            dst_full_dir = os.path.join(processed_dir, dst_subdir)
            os.makedirs(dst_full_dir, exist_ok=True)

            try:
                result = process_file(
                    src_file,
                    output_dir=dst_full_dir,
                    **kwargs,
                )

                if result.get("success"):
                    all_records.extend(result.get("records", []))
                    out_path = result.get("output_path", "")
                    if out_path and os.path.exists(out_path):
                        processed_files.append(out_path)
                    # 也复制脱敏记录文件
                    record_path = result.get("record_path", "")
                    if record_path and os.path.exists(record_path):
                        processed_files.append(record_path)
                else:
                    failed_files.append({
                        "file": rel_path,
                        "error": result.get("error", "未知错误"),
                    })
                    # 失败的文件原样保留
                    dst_path = os.path.join(dst_full_dir, Path(src_file).name)
                    shutil.copy2(src_file, dst_path)
                    processed_files.append(dst_path)

            except Exception as e:
                failed_files.append({
                    "file": rel_path,
                    "error": str(e),
                })
                dst_path = os.path.join(dst_full_dir, Path(src_file).name)
                shutil.copy2(src_file, dst_path)
                processed_files.append(dst_path)

        # ── 3. 重新打包 ──
        output_path = os.path.join(output_dir, f"{archive_name}_脱敏.zip")
        _create_zip(processed_files, processed_dir, output_path)

        # ── 4. 构造结果 ──
        success_count = len(supported_files) - len(failed_files)

        output_data: Dict[str, Any] = {
            "success": True,
            "input_path": archive_path,
            "output_path": output_path,
            "records": all_records,
            "total_files": len(supported_files),
            "success_count": success_count,
            "fail_count": len(failed_files),
        }
        if failed_files:
            output_data["failed_details"] = failed_files

        return output_data

    except Exception as e:
        return {
            "success": False,
            "error": f"处理压缩包时出错: {str(e)}",
            "input_path": archive_path,
            "records": [],
        }
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


def _extract_zip(zip_path: str, extract_to: str) -> List[str]:
    """
    解压 zip 文件（自动处理 GBK/UTF-8 编码），返回所有提取文件的路径列表。
    """
    extracted = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # 安全检查：拒绝路径穿越攻击
        safe_members = []
        for info in zf.infolist():
            member_path = os.path.abspath(os.path.join(extract_to, info.filename))
            if not member_path.startswith(os.path.abspath(extract_to)):
                continue
            # 处理中文编码：尝试 cp437 → gbk → utf-8
            try:
                info.filename.encode('cp437')
            except UnicodeEncodeError:
                pass
            try:
                decoded = info.filename.encode('cp437').decode('gbk')
                info.filename = decoded
            except (UnicodeDecodeError, UnicodeEncodeError):
                try:
                    decoded = info.filename.encode('cp437').decode('utf-8')
                    info.filename = decoded
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass
            safe_members.append(info)

        for info in safe_members:
            zf.extract(info, extract_to)

        # 收集所有提取的文件
        for root, dirs, files in os.walk(extract_to):
            for f in files:
                extracted.append(os.path.join(root, f))

    return extracted


def _create_zip(file_paths: List[str], base_dir: str, output_path: str):
    """
    将文件列表打包为新的 zip 文件。

    Args:
        file_paths: 要打包的文件路径列表
        base_dir: 基准目录（用于计算相对路径）
        output_path: 输出 zip 路径
    """
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fp in file_paths:
            arcname = os.path.relpath(fp, base_dir)
            zf.write(fp, arcname)

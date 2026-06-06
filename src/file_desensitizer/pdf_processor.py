#!/usr/bin/env python3
"""
PDF 文件脱敏处理器

支持两种处理模式：
1. 文本替换模式：提取 PDF 文本 → 脱敏 → 生成新 PDF（覆盖原文本）
2. 图像遮盖模式：将 PDF 页转为图片 → OCR → 脱敏遮挡 → 生成新 PDF

默认使用文本替换模式（速度更快），当文本替换效果不佳时回退到图像模式。
"""

import sys
import os
import json
import re
import io
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import fitz  # PyMuPDF
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from .core import TextDesensitizer


def process_pdf_text_replace(
    input_path: str,
    output_dir: Path,
    input_file: Path
) -> Dict[str, Any]:
    """
    文本替换模式：直接替换 PDF 中的文本。
    使用 PyMuPDF 的文本搜索和标注功能。
    """
    result = {
        "success": True,
        "mode": "text_replace",
        "input_path": input_path,
        "records": [],
    }

    try:
        doc = fitz.open(input_path)
    except Exception as e:
        return {"success": False, "error": f"无法打开 PDF: {e}"}

    all_records = []
    total_redactions = 0

    for page_num in range(len(doc)):
        page = doc[page_num]

        # 提取页面文本
        page_text = page.get_text("text")
        if not page_text.strip():
            continue

        # 对文本进行脱敏
        desensitized_text, records = TextDesensitizer.desensitize_text(page_text)

        if not records:
            continue

        all_records.extend(records)

        # 对每个敏感信息进行搜索和遮盖
        for record in records:
            original = record['original']
            # 搜索文本位置
            text_instances = page.search_for(original)

            for inst in text_instances:
                # 添加红色矩形遮盖
                annot = page.add_redact_annot(inst, fill=(0, 0, 0))
                total_redactions += 1

        # 应用遮盖
        if total_redactions > 0:
            page.apply_redactions()

    # 去重
    seen = set()
    unique_records = []
    for r in all_records:
        key = (r['category'], r['original'])
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    result["records"] = unique_records
    result["total_redactions"] = total_redactions

    # 保存脱敏后的 PDF
    output_path = output_dir / f"{input_file.stem}_desensitized.pdf"
    doc.save(str(output_path))
    doc.close()
    result["output_path"] = str(output_path)

    # 保存脱敏记录
    text_output_path = output_dir / f"{input_file.stem}_desensitized_record.txt"
    with open(text_output_path, 'w', encoding='utf-8') as f:
        f.write(f"=== PDF 脱敏记录 ===\n")
        f.write(f"原文件: {input_path}\n")
        f.write(f"脱敏文件: {output_path}\n")
        f.write(f"处理模式: 文本替换\n")
        f.write(f"遮盖数量: {total_redactions}\n\n")
        for r in unique_records:
            f.write(f"[{r['category']}] {r['original']} → {r['masked']}\n")
    result["text_output_path"] = str(text_output_path)

    return result


def process_pdf_image_mode(
    input_path: str,
    output_dir: Path,
    input_file: Path
) -> Dict[str, Any]:
    """
    图像遮盖模式：将 PDF 页渲染为图片 → OCR 识别 → 脱敏 → 在图片上遮盖 → 生成新 PDF
    """
    from image_processor import ocr_image, ocr_with_boxes, find_sensitive_boxes

    result = {
        "success": True,
        "mode": "image",
        "input_path": input_path,
        "records": [],
    }

    try:
        doc = fitz.open(input_path)
    except Exception as e:
        return {"success": False, "error": f"无法打开 PDF: {e}"}

    all_records = []
    new_doc = fitz.open()  # 新 PDF

    for page_num in range(len(doc)):
        page = doc[page_num]

        # 将页面渲染为图片（200 DPI）
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom ≈ 144 DPI
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")

        # 保存为临时图片
        temp_img_path = output_dir / f"_temp_page_{page_num}.png"
        with open(temp_img_path, 'wb') as f:
            f.write(img_data)

        try:
            # OCR 识别
            original_text = ocr_image(str(temp_img_path))
            if original_text.strip():
                # 文本脱敏
                desensitized_text, records = TextDesensitizer.desensitize_text(original_text)
                all_records.extend(records)

                if records:
                    # 获取 OCR 位置
                    boxes = ocr_with_boxes(str(temp_img_path))
                    sensitive_boxes = find_sensitive_boxes(boxes, desensitized_text, records, original_text)

                    # 在图片上遮盖
                    from image_processor import redact_image_pixels
                    redacted_img_path = output_dir / f"_temp_page_{page_num}_redacted.png"
                    redact_image_pixels(str(temp_img_path), str(redacted_img_path), sensitive_boxes, method="black")

                    # 将处理后的图片插入新 PDF
                    redacted_img = fitz.open(str(redacted_img_path))
                    rect = redacted_img[0].rect
                    new_page = new_doc.new_page(width=rect.width, height=rect.height)
                    new_page.insert_image(new_page.rect, filename=str(redacted_img_path))
                    redacted_img.close()

                    # 清理临时遮盖图片
                    redacted_img_path.unlink(missing_ok=True)
                else:
                    # 无敏感信息，直接插入原图
                    img = fitz.open(str(temp_img_path))
                    rect = img[0].rect
                    new_page = new_doc.new_page(width=rect.width, height=rect.height)
                    new_page.insert_image(new_page.rect, filename=str(temp_img_path))
                    img.close()
            else:
                # OCR 无结果，保留原图
                img = fitz.open(str(temp_img_path))
                rect = img[0].rect
                new_page = new_doc.new_page(width=rect.width, height=rect.height)
                new_page.insert_image(new_page.rect, filename=str(temp_img_path))
                img.close()
        finally:
            # 清理临时图片
            temp_img_path.unlink(missing_ok=True)

    doc.close()

    # 去重
    seen = set()
    unique_records = []
    for r in all_records:
        key = (r['category'], r['original'])
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    result["records"] = unique_records

    # 保存
    output_path = output_dir / f"{input_file.stem}_desensitized.pdf"
    new_doc.save(str(output_path))
    new_doc.close()
    result["output_path"] = str(output_path)

    # 保存脱敏记录
    text_output_path = output_dir / f"{input_file.stem}_desensitized_record.txt"
    with open(text_output_path, 'w', encoding='utf-8') as f:
        f.write(f"=== PDF 脱敏记录 ===\n")
        f.write(f"原文件: {input_path}\n")
        f.write(f"脱敏文件: {output_path}\n")
        f.write(f"处理模式: 图像遮盖\n\n")
        for r in unique_records:
            f.write(f"[{r['category']}] {r['original']} → {r['masked']}\n")
    result["text_output_path"] = str(text_output_path)

    return result


def process_pdf(
    input_path: str,
    output_dir: str = None,
    mode: str = "auto"
) -> Dict[str, Any]:
    """
    处理 PDF 文件脱敏。

    Args:
        input_path: 输入 PDF 文件路径
        output_dir: 输出目录
        mode: 处理模式 "auto"(自动)/"text"(文本替换)/"image"(图像遮盖)

    Returns:
        处理结果字典
    """
    input_path = str(Path(input_path).resolve())
    input_file = Path(input_path)

    if not input_file.exists():
        return {"success": False, "error": f"文件不存在: {input_path}"}

    if not input_file.suffix.lower() in ('.pdf',):
        return {"success": False, "error": f"不支持的文件格式: {input_file.suffix}，仅支持 .pdf"}

    if output_dir is None:
        output_dir = input_file.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == "image":
        return process_pdf_image_mode(input_path, output_dir, input_file)
    elif mode == "text":
        return process_pdf_text_replace(input_path, output_dir, input_file)
    else:
        # 自动模式：先尝试文本替换，如果效果不好再用图像模式
        result = process_pdf_text_replace(input_path, output_dir, input_file)

        # 如果文本替换没有找到任何敏感信息，尝试图像模式
        if result.get("success") and not result.get("records"):
            print("文本替换模式未发现敏感信息，切换到图像模式...", file=sys.stderr)
            return process_pdf_image_mode(input_path, output_dir, input_file)

        return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python pdf_processor.py <pdf文件路径> [输出目录] [mode:auto/text/image]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    mode = sys.argv[3] if len(sys.argv) > 3 else "auto"

    result = process_pdf(input_path, output_dir, mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""
Word 文档（.docx）脱敏处理器

支持对 .docx 文件中的段落文本和表格内容进行脱敏处理。
处理方式：
1. 遍历所有段落和表格单元格
2. 对文本内容进行脱敏
3. 生成脱敏后的新 .docx 文件
"""

import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List

from docx import Document
from docx.shared import RGBColor, Pt
from docx.oxml.ns import qn

sys.path.insert(0, str(Path(__file__).parent))
from desensitizer import TextDesensitizer


def process_paragraph(paragraph, records: List[Dict]):
    """
    处理单个段落中的文本。

    对于每个 run（文本片段），进行脱敏替换。
    使用红色高亮标记脱敏后的文本。
    """
    for run in paragraph.runs:
        original_text = run.text
        if not original_text.strip():
            continue

        desensitized, run_records = TextDesensitizer.desensitize_text(original_text)
        if desensitized != original_text:
            run.text = desensitized
            # 标记脱敏文本为红色
            run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
            records.extend(run_records)


def process_table(table, records: List[Dict]):
    """处理表格中的所有单元格"""
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                process_paragraph(paragraph, records)


def process_docx(
    input_path: str,
    output_dir: str = None,
    mark_color: bool = True
) -> Dict[str, Any]:
    """
    处理 Word 文档脱敏。

    Args:
        input_path: 输入 .docx 文件路径
        output_dir: 输出目录（默认为输入文件同目录）
        mark_color: 是否用红色标记脱敏文本

    Returns:
        处理结果字典
    """
    input_path = str(Path(input_path).resolve())
    input_file = Path(input_path)

    if not input_file.exists():
        return {"success": False, "error": f"文件不存在: {input_path}"}

    if not input_file.suffix.lower() in ('.docx',):
        return {"success": False, "error": f"不支持的文件格式: {input_file.suffix}，仅支持 .docx"}

    if output_dir is None:
        output_dir = input_file.parent
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "success": True,
        "input_path": input_path,
        "output_path": None,
        "text_output_path": None,
        "records": [],
    }

    try:
        doc = Document(input_path)
    except Exception as e:
        return {"success": False, "error": f"无法打开文档: {e}"}

    all_records = []

    # 1. 处理所有段落（正文、页眉页脚等）
    for paragraph in doc.paragraphs:
        process_paragraph(paragraph, all_records)

    # 2. 处理表格
    for table in doc.tables:
        process_table(table, all_records)

    # 3. 处理页眉
    for section in doc.sections:
        try:
            header = section.header
            if header:
                for paragraph in header.paragraphs:
                    process_paragraph(paragraph, all_records)
                for table in header.tables:
                    process_table(table, all_records)
        except Exception:
            pass

    # 4. 处理页脚
    for section in doc.sections:
        try:
            footer = section.footer
            if footer:
                for paragraph in footer.paragraphs:
                    process_paragraph(paragraph, all_records)
                for table in footer.tables:
                    process_table(table, all_records)
        except Exception:
            pass

    # 去重记录
    seen = set()
    unique_records = []
    for r in all_records:
        key = (r['category'], r['original'])
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    result["records"] = unique_records

    # 5. 保存脱敏后的文档
    output_path = output_dir / f"{input_file.stem}_desensitized.docx"
    doc.save(str(output_path))
    result["output_path"] = str(output_path)

    # 6. 保存脱敏记录文本
    text_output_path = output_dir / f"{input_file.stem}_desensitized_record.txt"
    with open(text_output_path, 'w', encoding='utf-8') as f:
        f.write(f"=== Word 文档脱敏记录 ===\n")
        f.write(f"原文件: {input_path}\n")
        f.write(f"脱敏文件: {output_path}\n\n")
        for r in unique_records:
            f.write(f"[{r['category']}] {r['original']} → {r['masked']}\n")
    result["text_output_path"] = str(text_output_path)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python docx_processor.py <docx文件路径> [输出目录]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    result = process_docx(input_path, output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))

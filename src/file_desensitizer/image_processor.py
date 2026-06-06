#!/usr/bin/env python3
"""
图片文件脱敏处理器

支持通过 OCR 识别图片中的文字，对敏感信息进行脱敏，
支持两种脱敏方式：
1. 叠加遮挡块（默认）- 在原图上覆盖黑色/模糊块
2. 仅输出文本 - 输出脱敏后的文本内容
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .core import TextDesensitizer


def ocr_image(image_path: str) -> str:
    """
    使用 pytesseract 对图片进行 OCR 识别。

    Args:
        image_path: 图片路径

    Returns:
        识别出的文本内容
    """
    try:
        import pytesseract
        img = Image.open(image_path)
        # 使用中英文混合识别
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        return text
    except Exception as e:
        print(f"OCR 识别失败: {e}", file=sys.stderr)
        return ""


def ocr_with_boxes(image_path: str) -> List[Dict[str, Any]]:
    """
    使用 pytesseract 获取每个识别词的位置信息。

    Args:
        image_path: 图片路径

    Returns:
        [{"text": "文字", "left": x, "top": y, "width": w, "height": h}, ...]
    """
    try:
        import pytesseract
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, lang='chi_sim+eng', output_type=pytesseract.Output.DICT)

        boxes = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if text and data['conf'][i] > 30:  # 置信度过滤
                boxes.append({
                    "text": text,
                    "left": data['left'][i],
                    "top": data['top'][i],
                    "width": data['width'][i],
                    "height": data['height'][i],
                    "conf": data['conf'][i],
                })
        return boxes
    except Exception as e:
        print(f"OCR 位置识别失败: {e}", file=sys.stderr)
        return []


def find_sensitive_boxes(
    boxes: List[Dict],
    desensitized_text: str,
    records: List[Dict],
    original_text: str
) -> List[Tuple[int, int, int, int, str]]:
    """
    找到需要覆盖的敏感信息位置。

    Returns:
        [(left, top, right, bottom, category), ...]
    """
    sensitive_boxes = []

    for record in records:
        original = record['original']
        category = record['category']

        # 在 boxes 中查找包含原始文本的 box
        # 使用滑动窗口匹配
        for i in range(len(boxes)):
            # 尝试从当前位置组合连续 boxes 匹配
            combined_text = ""
            for j in range(i, min(i + 10, len(boxes))):
                combined_text += boxes[j]['text']
                if original in combined_text or combined_text in original:
                    # 找到匹配范围
                    left = min(boxes[k]['left'] for k in range(i, j + 1))
                    top = min(boxes[k]['top'] for k in range(i, j + 1))
                    right = max(boxes[k]['left'] + boxes[k]['width'] for k in range(i, j + 1))
                    bottom = max(boxes[k]['top'] + boxes[k]['height'] for k in range(i, j + 1))
                    sensitive_boxes.append((left, top, right, bottom, category))
                    break
            else:
                continue
            break

        # 如果上述方法没找到，尝试单个 box 模糊匹配
        if not sensitive_boxes or sensitive_boxes[-1][4] != category:
            for box in boxes:
                if original in box['text'] or box['text'] in original:
                    sensitive_boxes.append((
                        box['left'], box['top'],
                        box['left'] + box['width'], box['top'] + box['height'],
                        category
                    ))
                    break

    return sensitive_boxes


def redact_image_pixels(
    image_path: str,
    output_path: str,
    boxes: List[Tuple[int, int, int, int, str]],
    method: str = "black"
) -> str:
    """
    在图片上覆盖遮挡块。

    Args:
        image_path: 原始图片路径
        output_path: 输出图片路径
        boxes: 敏感信息区域列表 [(left, top, right, bottom, category), ...]
        method: 遮挡方式 "black"（黑色块）/ "blur"（模糊）/ "pixelate"（像素化）

    Returns:
        输出图片路径
    """
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    for left, top, right, bottom, category in boxes:
        # 扩展遮挡区域以完全覆盖文字
        padding = 3
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(img.width, right + padding)
        bottom = min(img.height, bottom + padding)

        region = img.crop((left, top, right, bottom))

        if method == "blur":
            # 高斯模糊
            blurred = region.filter(ImageFilter.GaussianBlur(radius=8))
            img.paste(blurred, (left, top))
        elif method == "pixelate":
            # 像素化效果
            small = region.resize((max(1, region.width // 10), max(1, region.height // 10)),
                                   resample=Image.NEAREST)
            pixelated = small.resize(region.size, Image.NEAREST)
            img.paste(pixelated, (left, top))
        else:
            # 黑色块
            draw.rectangle([left, top, right, bottom], fill="black")

        # 在遮挡块上添加脱敏类型标签（如果区域足够大）
        if (right - left) > 40 and (bottom - top) > 15:
            try:
                # 使用小号字体标注脱敏类型
                label_map = {
                    "姓名": "[姓名]",
                    "手机号": "[手机]",
                    "身份证号": "[身份证]",
                    "身份证号(15位)": "[身份证]",
                    "住址": "[住址]",
                    "邮箱": "[邮箱]",
                    "银行卡号": "[银行卡]",
                }
                label = label_map.get(category, "[已脱敏]")
                # 使用默认字体
                font_size = min(12, (bottom - top) // 2)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()

                # 白色文字标注
                text_bbox = draw.textbbox((0, 0), label, font=font)
                tw = text_bbox[2] - text_bbox[0]
                th = text_bbox[3] - text_bbox[1]
                tx = left + (right - left - tw) // 2
                ty = top + (bottom - top - th) // 2
                draw.text((tx, ty), label, fill="white", font=font)
            except Exception:
                pass

    img.save(output_path)
    return output_path


def process_image(
    input_path: str,
    output_dir: str = None,
    redact_method: str = "black",
    text_only: bool = False
) -> Dict[str, Any]:
    """
    处理单张图片的脱敏。

    Args:
        input_path: 输入图片路径
        output_dir: 输出目录（默认为输入文件同目录）
        redact_method: 遮挡方式 "black"/"blur"/"pixelate"
        text_only: 是否仅输出文本（不生成遮挡图片）

    Returns:
        处理结果字典
    """
    input_path = str(Path(input_path).resolve())
    input_file = Path(input_path)

    if not input_file.exists():
        return {"success": False, "error": f"文件不存在: {input_path}"}

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
        "original_text": "",
        "desensitized_text": "",
    }

    # 1. OCR 识别
    original_text = ocr_image(input_path)
    result["original_text"] = original_text

    if not original_text.strip():
        result["error"] = "OCR 未能识别到文字内容"
        # 即使没有文字，也复制一份原图
        output_path = output_dir / f"{input_file.stem}_desensitized{input_file.suffix}"
        Image.open(input_path).save(output_path)
        result["output_path"] = str(output_path)
        return result

    # 2. 文本脱敏
    desensitized_text, records = TextDesensitizer.desensitize_text(original_text)
    result["desensitized_text"] = desensitized_text
    result["records"] = records

    # 3. 保存脱敏文本
    text_output_path = output_dir / f"{input_file.stem}_desensitized.txt"
    with open(text_output_path, 'w', encoding='utf-8') as f:
        f.write(f"=== 原始 OCR 文本 ===\n{original_text}\n\n")
        f.write(f"=== 脱敏后文本 ===\n{desensitized_text}\n\n")
        f.write(f"=== 脱敏记录 ===\n")
        for r in records:
            f.write(f"[{r['category']}] {r['original']} → {r['masked']}\n")
    result["text_output_path"] = str(text_output_path)

    if text_only:
        return result

    # 4. 图片遮挡处理
    if records:
        boxes = ocr_with_boxes(input_path)
        sensitive_boxes = find_sensitive_boxes(boxes, desensitized_text, records, original_text)

        output_path = output_dir / f"{input_file.stem}_desensitized{input_file.suffix}"
        redact_image_pixels(input_path, str(output_path), sensitive_boxes, method=redact_method)
        result["output_path"] = str(output_path)
        result["sensitive_regions"] = len(sensitive_boxes)
    else:
        # 没有敏感信息，直接复制
        output_path = output_dir / f"{input_file.stem}_desensitized{input_file.suffix}"
        Image.open(input_path).save(output_path)
        result["output_path"] = str(output_path)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python image_processor.py <图片路径> [输出目录] [遮挡方式]")
        print("遮挡方式: black(默认) / blur / pixelate")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    redact_method = sys.argv[3] if len(sys.argv) > 3 else "black"

    result = process_image(input_path, output_dir, redact_method)
    print(json.dumps(result, ensure_ascii=False, indent=2))

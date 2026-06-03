"""
批量从详细图提取指甲模具，预先生成用于试戴的模具库
"""
import os
import json
import cv2
import numpy as np
from pathlib import Path

# 路径配置
DESIGNS_JSON = "designs.json"
DETAILED_IMG_DIR = r"d:\指上谈兵\款式图"
CROPS_DIR = "molds"  


def extract_nails_from_preview(preview_img: np.ndarray) -> list:
    """从预览图（5个指甲从左到右排列）中裁剪出单个指甲。

    优先用轮廓检测，如果失败才用等分方法。
    返回: [nail_0, nail_1, nail_2, nail_3, nail_4] (BGRA，带透明背景)
    """
    h, w = preview_img.shape[:2]

    # 转灰度+阈值找指甲区域（比色彩范围更可靠）
    gray = cv2.cvtColor(preview_img, cv2.COLOR_BGR2GRAY)
    # 背景是白色(255)，指甲是深色，所以找小于 200 的区域
    _, nail_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # 找轮廓
    contours, _ = cv2.findContours(nail_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"[Design] Found {len(contours)} contours")

    # 筛选足够大的轮廓（过滤噪声）
    min_area = (h * w) / 200  # 至少占图像 0.5%
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    print(f"[Design] Valid contours: {len(valid_contours)}")

    if len(valid_contours) >= 5:
        # 轮廓方法：按 x 坐标排序，取最大的 5 个
        nail_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[0])[-5:]
        print(f"[Design] Using contour method")
    else:
        print(f"[Design] Using equal division method")
        # 水平等分方法：基于整体指甲区域范围
        y_coords, x_coords = np.where(nail_mask > 0)
        if len(x_coords) == 0:
            print(f"[Design] No nail region found")
            return []

        x_min, x_max = x_coords.min(), x_coords.max()
        y_min, y_max = y_coords.min(), y_coords.max()

        nails = []
        nail_width = (x_max - x_min) / 5.0

        for fi in range(5):
            x_start = int(x_min + fi * nail_width)
            x_end = int(x_min + (fi + 1) * nail_width)

            nail_crop = preview_img[y_min:y_max+1, x_start:x_end+1].copy()

            # 标准化尺寸
            h_crop, w_crop = nail_crop.shape[:2]
            if h_crop > 0 and w_crop > 0:
                max_size = max(h_crop, w_crop)
                scale = 280 / max_size if max_size > 0 else 1.0
                new_h = max(80, int(h_crop * scale))
                new_w = max(50, int(w_crop * scale))
                nail_crop = cv2.resize(nail_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)

                nail_bgra = cv2.cvtColor(nail_crop, cv2.COLOR_BGR2BGRA)
                # 全不透明（等分方法没有 mask，保留整个裁剪区域）
                nail_bgra[:,:,3] = 255
                nails.append(nail_bgra)
                print(f"[Design] Nail {fi}: {nail_bgra.shape}")

        return nails

    nails = []
    for fi, contour in enumerate(nail_contours):
        x, y, w_rect, h_rect = cv2.boundingRect(contour)

        # 加上边距，避免裁剪太紧
        margin = 8
        x = max(0, x - margin)
        y = max(0, y - margin)
        w_rect = min(w_rect + 2*margin, w - x)
        h_rect = min(h_rect + 2*margin, h - y)

        # 裁剪指甲区域
        nail_crop = preview_img[y:y+h_rect, x:x+w_rect].copy()

        # 裁剪对应的轮廓 mask（用于生成 alpha）
        contour_crop = contour.copy()
        contour_crop[:, :, 0] -= x  # 调整坐标到裁剪后的坐标系
        contour_crop[:, :, 1] -= y

        # 标准化指甲尺寸：调整为合适的大小（200x350 比例）便于透视变换
        # 保持原始的长宽比，缩放到约 200x350 左右
        max_size = max(w_rect, h_rect)
        target_size = 280  # 目标最大边长
        scale = target_size / max_size if max_size > 0 else 1.0

        new_w = max(50, int(w_rect * scale))
        new_h = max(80, int(h_rect * scale))

        if scale != 1.0:
            nail_crop = cv2.resize(nail_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)
            # 同时缩放轮廓坐标
            contour_crop = (contour_crop * scale).astype(np.int32)

        # 生成 alpha 通道：基于轮廓 fillPoly（保留所有指甲内容，包括高光）
        # 创建一个空白 alpha 图
        h_crop, w_crop = nail_crop.shape[:2]
        alpha_mask = np.zeros((h_crop, w_crop), dtype=np.uint8)

        # 用轮廓填充：轮廓内部完全不透明，外部完全透明
        # 这样可以保留指甲内部的所有细节，包括高光
        cv2.drawContours(alpha_mask, [contour_crop], 0, 255, -1)

        # 轻微膨胀，填补轮廓边缘的小缝隙
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_CLOSE, kernel)

        # 高斯模糊平滑边缘（但不会删除内部的高光）
        alpha_mask = cv2.GaussianBlur(alpha_mask, (3, 3), 0)

        # 转 BGRA
        nail_bgra = cv2.cvtColor(nail_crop, cv2.COLOR_BGR2BGRA)
        nail_bgra[:,:,3] = alpha_mask
        nails.append(nail_bgra)
        print(f"[Design] Nail {fi}: {nail_bgra.shape}")

    return nails

def load_designs():
    """读取 designs.json"""
    with open(DESIGNS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('designs', []) if isinstance(data, dict) else data

def ensure_crop_dir(design_id):
    """确保 crops/{design_id} 目录存在"""
    crop_dir = os.path.join(CROPS_DIR, design_id)
    os.makedirs(crop_dir, exist_ok=True)
    return crop_dir

def save_nail_molds(design_id, nails):
    """保存 5 个指甲模具"""
    if not nails:
        print(f"  - No nails extracted")
        return False

    crop_dir = ensure_crop_dir(design_id)

    for i, nail_bgra in enumerate(nails):
        if nail_bgra is None or nail_bgra.size == 0:
            continue

        # 保存为 PNG（带透明通道）
        nail_path = os.path.join(crop_dir, f"nail_{i}.png")
        cv2.imwrite(nail_path, nail_bgra)
        print(f"    OK nail_{i}.png: {nail_bgra.shape}")

    return len(nails) == 5

def process_detailed_image(design_id, enhanced_hash):
    """处理单个详细图"""
    print(f"\n[{design_id}] {enhanced_hash}")

    # 详细图路径
    detailed_img_path = os.path.join(DETAILED_IMG_DIR, f"{enhanced_hash}.jpg")

    if not os.path.exists(detailed_img_path):
        print(f"  - Image not found: {detailed_img_path}")
        return False

    # 读取图片（处理中文路径）
    import numpy as np
    with open(detailed_img_path, 'rb') as f:
        img_bytes = np.frombuffer(f.read(), dtype=np.uint8)
    img = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
    if img is None:
        print(f"  - Unable to read image")
        return False

    h, w = img.shape[:2]
    print(f"  Image: {w}x{h}")

    # 提取指甲
    nails = extract_nails_from_preview(img)

    if not nails or len(nails) != 5:
        print(f"  - Extraction failed or invalid nail count: {len(nails) if nails else 0}")
        return False

    # 保存指甲模具
    if save_nail_molds(design_id, nails):
        print(f"  OK 5 nails extracted")
        return True
    else:
        print(f"  - Save failed")
        return False

def main():
    """批量处理"""
    print("=" * 60)
    print("Batch extract nail molds from detailed images")
    print("=" * 60)

    designs = load_designs()

    # 筛选有 enhanced_hash 的设计（即有详细图的）
    designs_with_detailed = [
        d for d in designs
        if d.get('enhanced_hash') and os.path.exists(
            os.path.join(DETAILED_IMG_DIR, f"{d['enhanced_hash']}.jpg")
        )
    ]

    print(f"\nFound {len(designs_with_detailed)} designs with detailed images")

    success_count = 0
    fail_count = 0

    for design in designs_with_detailed:
        design_id = design['id']
        enhanced_hash = design['enhanced_hash']

        if process_detailed_image(design_id, enhanced_hash):
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"Complete: OK {success_count}, FAIL {fail_count}")
    print(f"Molds saved: {os.path.abspath(CROPS_DIR)}/")
    print("=" * 60)

if __name__ == "__main__":
    main()

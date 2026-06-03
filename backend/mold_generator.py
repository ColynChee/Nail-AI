"""从灵感图生成美甲模具：Qwen-VL分析设计 + Z-Image-Turbo生成5甲模板 + 自动切割"""

import os
import json
import time
import base64
import uuid
import requests
import numpy as np
import cv2
from pathlib import Path
from typing import Optional
from openai import OpenAI
import httpx

from design_generator import extract_nails_from_preview

MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_TOKEN", "")
BACKEND_DIR = Path(__file__).resolve().parent
MOLDS_DIR = BACKEND_DIR / "molds"

COMMON_HEADERS = {
    "Authorization": f"Bearer {MODELSCOPE_API_KEY}",
    "Content-Type": "application/json",
}

# Qwen-VL 客户端
if MODELSCOPE_API_KEY:
    _http_client = httpx.Client(timeout=120.0, verify=True)
    _vl_client = OpenAI(
        base_url="https://api-inference.modelscope.cn/v1",
        api_key=MODELSCOPE_API_KEY,
        http_client=_http_client
    )
else:
    _vl_client = None


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _analyze_nail_design(image_path: str) -> Optional[str]:
    """用Qwen-VL分析灵感图中的美甲设计，生成详细描述"""
    if not _vl_client:
        return None

    img_b64 = _image_to_base64(image_path)
    prompt = """请仔细观察这张图片中的美甲设计，然后用中文详细描述：
1. 底色/背景色（具体颜色，如裸粉色、白色、渐变等）
2. 图案元素（花朵、线条、几何形、渐变、亮片等）
3. 颜色搭配（主色+配色）
4. 纹理质感（哑光、亮光、镭射、奶油感等）
5. 装饰细节（贝壳粉、碎钻、金箔等）

直接输出描述，不要其他文字，100字以内。"""

    try:
        resp = _vl_client.chat.completions.create(
            model="Qwen/Qwen3-VL-30B-A3B-Instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }],
            max_tokens=200,
            timeout=120.0
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[MoldGen] Qwen-VL分析失败: {e}")
        return None


def _generate_template_with_doubao(design_description: str) -> Optional[str]:
    """调用Z-Image-Turbo生成5甲横排模板图，返回base64"""
    prompt = f"""白色背景，俯视角，只画一横排共5个美甲，从左到右，不要画第二排。设计风格：{design_description}"""

    try:
        response = requests.post(
            "https://api-inference.modelscope.cn/v1/images/generations",
            headers={**COMMON_HEADERS, "X-ModelScope-Async-Mode": "true"},
            data=json.dumps({
                "model": "Tongyi-MAI/Z-Image-Turbo",
                "prompt": prompt
            }, ensure_ascii=False).encode("utf-8"),
            timeout=30,
            proxies={"https": "", "http": ""}
        )
        if response.status_code != 200:
            print(f"[MoldGen] Z-Image-Turbo提交失败: {response.status_code} {response.text}")
            return None

        task_id = response.json().get("task_id")
        if not task_id:
            return None

        print(f"[MoldGen] 发送给Z-Image-Turbo的prompt:\n{prompt}\n{'='*50}")
        print(f"[MoldGen] Z-Image-Turbo任务已提交: {task_id}")

        # 轮询等待结果
        for _ in range(60):  # 最多5分钟
            time.sleep(5)
            result = requests.get(
                f"https://api-inference.modelscope.cn/v1/tasks/{task_id}",
                headers={**COMMON_HEADERS, "X-ModelScope-Task-Type": "image_generation"},
                timeout=30,
                proxies={"https": "", "http": ""}
            )
            data = result.json()
            status = data.get("task_status")
            print(f"[MoldGen] Z-Image-Turbo状态: {status}")

            if status == "SUCCEED":
                img_url = data["output_images"][0]
                # 下载图片，带重试和SSL容错
                for attempt in range(3):
                    try:
                        print(f"[MoldGen] 下载图片 (第{attempt+1}/3次)...")
                        img_resp = requests.get(img_url, timeout=60, verify=False,
                                                proxies={"https": "", "http": ""})
                        img_resp.raise_for_status()
                        return base64.b64encode(img_resp.content).decode("utf-8")
                    except Exception as e:
                        print(f"[MoldGen] 下载失败: {str(e)[:60]}")
                        if attempt < 2:
                            time.sleep(2)
                print(f"[MoldGen] 多次下载失败")
                return None
            elif status == "FAILED":
                print(f"[MoldGen] Z-Image-Turbo生成失败")
                return None

        print(f"[MoldGen] Z-Image-Turbo超时")
        return None

    except Exception as e:
        print(f"[MoldGen] Z-Image-Turbo调用异常: {e}")
        return None


def _split_5nail_template(img_b64: str) -> list:
    """把5甲横排图切割成5个单指PNG（列扫描法，稳定处理指甲粘连）"""
    img_data = base64.b64decode(img_b64)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        print("[MoldGen] 图片解码失败")
        return []

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 根据四角亮度自适应threshold（背景可能不是纯白）
    corners_mean = np.mean([gray[5,5], gray[5,w-6], gray[h-6,5], gray[h-6,w-6]])
    threshold = int(corners_mean * 0.88)
    print(f"[MoldGen] 背景亮度={corners_mean:.1f}, 使用阈值={threshold}")

    _, nail_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)

    # 找整体nail区域范围
    ys, xs = np.where(nail_mask > 0)
    if len(xs) == 0:
        print("[MoldGen] 未找到指甲区域")
        return []

    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    print(f"[MoldGen] 指甲区域: x={x_min}-{x_max}, y={y_min}-{y_max}")

    # 大核闭运算：填充指甲内部颜色变化（白色高光、设计图案等），避免假谷值
    kernel_fill = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (40, 40))
    nail_mask_filled = cv2.morphologyEx(nail_mask, cv2.MORPH_CLOSE, kernel_fill, iterations=3)

    # 垂直投影找谷值：基于填充后的mask，不受内部设计颜色影响
    projection = nail_mask_filled.sum(axis=0).astype(np.float32)

    # 在nail区域内寻找4个谷值作为切割位置
    region = projection[x_min:x_max]
    region_len = len(region)

    # 用等分点为初始位置，在附近找局部最小值作为谷值
    cuts = [x_min]  # 左边界
    for i in range(1, 5):
        approx = int(x_min + i * (x_max - x_min) / 5)
        search_start = max(x_min, approx - int((x_max - x_min) / 10))
        search_end = min(x_max, approx + int((x_max - x_min) / 10))
        local = projection[search_start:search_end]
        if len(local) > 0:
            valley = search_start + int(local.argmin())
        else:
            valley = approx
        cuts.append(valley)
    cuts.append(x_max)  # 右边界

    print(f"[MoldGen] 切割位置(谷值法): {cuts}")

    # 检查每段宽度是否合理，最小宽度 = 总宽 / 8
    expected_width = (x_max - x_min) / 5.0
    min_width = expected_width * 0.6
    widths = [cuts[i+1] - cuts[i] for i in range(5)]
    print(f"[MoldGen] 各段宽度: {widths}, 最小允许={min_width:.0f}")

    if any(bw < min_width for bw in widths):
        print(f"[MoldGen] 谷值切割不合理，回退等分法")
        cuts = [int(x_min + i * (x_max - x_min) / 5) for i in range(6)]
        print(f"[MoldGen] 切割位置(等分法): {cuts}")

    nails = []
    for col_i in range(5):
        left_bound = max(0, cuts[col_i])
        right_bound = min(w, cuts[col_i + 1])
        top_bound = max(0, y_min - 4)
        bot_bound = min(h, y_max + 4)

        nail_crop = img[top_bound:bot_bound, left_bound:right_bound].copy()
        if nail_crop.size == 0:
            continue

        cw, ch = nail_crop.shape[1], nail_crop.shape[0]

        # 标准化尺寸
        max_side = max(cw, ch)
        scale = 280 / max_side
        new_w = max(50, int(cw * scale))
        new_h = max(80, int(ch * scale))
        nail_crop = cv2.resize(nail_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 轮廓填充生成alpha（保留高光，只去背景）
        crop_gray = cv2.cvtColor(nail_crop, cv2.COLOR_BGR2GRAY)
        crop_corners = np.mean([crop_gray[2,2], crop_gray[2,-3], crop_gray[-3,2], crop_gray[-3,-3]])
        crop_thresh = int(crop_corners * 0.88)
        _, binary = cv2.threshold(crop_gray, crop_thresh, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours_crop, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rh, rw = nail_crop.shape[:2]
        alpha_mask = np.zeros((rh, rw), dtype=np.uint8)
        if contours_crop:
            largest = max(contours_crop, key=cv2.contourArea)
            # 用凸包填充，确保高光等亮色区域不被切除
            hull = cv2.convexHull(largest)
            cv2.drawContours(alpha_mask, [hull], 0, 255, -1)
        else:
            alpha_mask[:] = 255

        alpha_mask = cv2.GaussianBlur(alpha_mask, (3, 3), 0)

        nail_bgra = cv2.cvtColor(nail_crop, cv2.COLOR_BGR2BGRA)
        nail_bgra[:, :, 3] = alpha_mask
        nails.append(nail_bgra)
        print(f"[MoldGen] nail[{col_i}]: {new_w}x{new_h}, bound=({left_bound},{right_bound})")

    print(f"[MoldGen] 切割完成，共{len(nails)}个指甲")
    return nails


def generate_mold_from_inspiration(image_path: str) -> Optional[dict]:
    """主函数：从灵感图生成模具并保存，返回design_id和预览图"""
    print(f"[MoldGen] 开始处理灵感图: {image_path}")

    # Step 1: Qwen-VL 分析设计
    print("[MoldGen] Step1: 分析美甲设计...")
    design_desc = _analyze_nail_design(image_path)
    if not design_desc:
        # fallback：用通用描述
        design_desc = "精致美甲设计，优雅配色，细腻质感"
    print(f"[MoldGen] 设计描述: {design_desc}")

    display_desc = design_desc  # 保留原始描述供前端展示

    # 注入排版要求供生图使用（不展示给用户）
    design_desc = design_desc + "。【排版要求】只画1行共5个指甲横排，不要画第2行，白色背景，指甲间留空隙。"

    # Step 2: Z-Image-Turbo生成5甲模板
    print("[MoldGen] Step2: 生成5甲模板...")
    template_b64 = _generate_template_with_doubao(design_desc)
    if not template_b64:
        return None

    # Step 3: 切割成5个单指
    print("[MoldGen] Step3: 切割模具...")
    nail_images = _split_5nail_template(template_b64)
    if not nail_images:
        return None

    # Step 4: 保存到molds目录
    design_id = f"insp_{uuid.uuid4().hex[:8]}"
    mold_dir = MOLDS_DIR / design_id
    mold_dir.mkdir(parents=True, exist_ok=True)

    for i, nail_img in enumerate(nail_images):
        out_path = mold_dir / f"{i}.png"
        success, buf = cv2.imencode('.png', nail_img)
        if success:
            with open(out_path, 'wb') as f:
                f.write(buf.tobytes())
            print(f"[MoldGen] 保存成功: {out_path} ({len(buf)} bytes)")
        else:
            print(f"[MoldGen] 保存失败: {out_path}")

    # Step 5: 用提取出的5个指甲重新拼成干净的预览图（白底横排）
    print(f"[MoldGen] 开始生成预览图，nail_images数量: {len(nail_images)}")
    for i, n in enumerate(nail_images):
        print(f"[MoldGen] nail[{i}] shape={n.shape} dtype={n.dtype}")
    preview_b64 = _make_preview_from_nails(nail_images)
    print(f"[MoldGen] preview_b64 生成{'成功' if preview_b64 else '失败，回退原图'}")

    print(f"[MoldGen] 完成！design_id={design_id}")
    return {
        "design_id": design_id,
        "template_base64": template_b64,  # 展示原始生成图
        "design_description": display_desc,
        "nail_count": len(nail_images)
    }


def _make_preview_from_nails(nail_images: list) -> Optional[str]:
    """把5个单指BGRA图拼成横排预览图（白底）"""
    if not nail_images:
        print("[MoldGen-Preview] nail_images为空")
        return None
    try:
        # 统一高度
        target_h = 280
        resized = []
        for img in nail_images:
            h, w = img.shape[:2]
            scale = target_h / h
            new_w = int(w * scale)
            resized.append(cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_AREA))

        gap = 20
        total_w = sum(img.shape[1] for img in resized) + gap * (len(resized) + 1)
        canvas = np.ones((target_h + gap * 2, total_w, 3), dtype=np.uint8) * 255

        x = gap
        for img in resized:
            h, w = img.shape[:2]
            if img.shape[2] == 4:
                alpha = img[:, :, 3:4].astype(np.float32) / 255.0
                bgr = img[:, :, :3].astype(np.float32)
                white = np.ones_like(bgr) * 255
                blended = (bgr * alpha + white * (1 - alpha)).astype(np.uint8)
            else:
                blended = img[:, :, :3]
            canvas[gap:gap+h, x:x+w] = blended
            x += w + gap

        success, buf = cv2.imencode('.jpg', canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if success:
            print(f"[MoldGen-Preview] 预览图生成成功，尺寸: {canvas.shape}")
            return base64.b64encode(buf.tobytes()).decode('utf-8')
        return None
    except Exception as e:
        print(f"[MoldGen-Preview] 预览图生成异常: {e}")
        import traceback
        traceback.print_exc()
        return None

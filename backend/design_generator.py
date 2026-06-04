"""AI 生成美甲设计。

流程:
  用户提示词 → DeepSeek 优化 → Qwen-Image 生成纹理 → 贴模具 → 生成扇形缩略图
"""
import os
import json
import time
import cv2
import requests
import numpy as np
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI

BACKEND = Path(__file__).resolve().parent
DESIGNS_GEN_DIR = BACKEND.parent / "designs_generated"
DESIGNS_GEN_DIR.mkdir(exist_ok=True)

# 指甲模具路径
NAIL_TEMPLATE_PATH = BACKEND.parent / "生成指甲模板图片.png"

load_dotenv(BACKEND / ".env")
load_dotenv(BACKEND.parent / ".env")

MODELSCOPE_BASE_URL = "https://api-inference.modelscope.cn/"


def _get_modelscope_token() -> str:
    return os.getenv("MODELSCOPE_TOKEN", "")


def _build_deepseek_client() -> Optional[OpenAI]:
    token = _get_modelscope_token()
    if not token:
        return None
    return OpenAI(
        base_url='https://api-inference.modelscope.cn/v1',
        api_key=token,
    )


def _build_common_headers() -> Dict[str, str]:
    token = _get_modelscope_token()
    return {
        "Authorization": token,
        "Content-Type": "application/json",
    }


def _fallback_prompt(user_prompt: str) -> str:
    """降级方案：用固定中文模板包装用户输入，确保 Qwen 能理解。"""
    template = """美甲设计图（平面2D，不要3D渲染）：
- 5个指甲从左到右排成一行，每个指甲之间有明显的白色空隙（指甲宽度的20-30%）
- 排列顺序：短指甲 → 中指最长 → 其他指甲逐渐变短，就像真实手指的比例
- 每个指甲都正向显示（不要旋转、不要倾斜），竖直朝上
- 用户描述：{description}
- 风格：专业美甲设计图，清晰干净，高质量
- 背景纯白色，指甲之间有白色间距，不要贴在一起
- 只显示指甲设计，不要手部、皮肤或其他元素
- 指甲上有光泽和立体阴影效果
- 高端美甲沙龙级别的设计效果"""
    return template.format(description=user_prompt)


def optimize_prompt(user_prompt: str) -> Dict:
    """用 DeepSeek-V4-Pro 优化用户的提示词。

    输入: "短杏仁形、柔粉紫、铬色微型法式"
    输出: {
        "optimized": "短杏仁形柔粉紫底色，结合铬色镜面质感的微型法式美甲..."
    }
    """
    system_msg = """你是专业的美甲设计师。将用户的美甲描述转化为详细的中文设计提示词。

【重要】生成的必须是【纯指甲设计图】，不能包含任何手部、皮肤、背景、其他人体部分。

【关键布局要求】：
✋ 禁止：扇形排列、旋转、倾斜、不规则摆放、指甲相互贴靠
✅ 要求：5个指甲从左到右正向排成一行，每个指甲竖直，不要任何旋转角度
✅ 【间距】指甲之间必须有清晰的白色空隙，间距约为指甲宽度的 20-30%（确保指甲绝对不贴在一起）
✅ 指甲大小：短指甲 → 中指最长 → 无名指小指逐小（比例像真实手指）

【设计细节】：
- 指甲形状、颜色、纹理、渐变、镜面、光泽等设计细节清晰准确
- 背景纯色（白色或浅灰色）
- 平面 2D 设计，不要 3D 渲染、不要投影、不要立体效果
- 线条精准，高质量专业美甲设计图

【禁止项】：
- ⚠️ 严禁生成手部、手指、皮肤、手腕等任何人体元素
- 禁止扇形排列（不像手掌展开）
- 禁止旋转或倾斜指甲
- 禁止 3D 渲染或阴影投影

直接返回优化后的中文描述（一段话，不需要JSON）"""

    try:
        deepseek_client = _build_deepseek_client()
        if deepseek_client is None:
            print("[DeepSeek] MODELSCOPE_TOKEN missing, using fallback template")
            fallback = _fallback_prompt(user_prompt)
            return {"optimized": fallback, "fallback": True}

        print(f"[DeepSeek] Calling API with model: deepseek-ai/DeepSeek-V4-Pro")
        response = deepseek_client.chat.completions.create(
            model='deepseek-ai/DeepSeek-V4-Pro',
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=300,
        )

        print(f"[DeepSeek] Response received: {response}")

        # 详细的错误检查和日志
        if not response:
            print(f"[DeepSeek] Response is None")
            return {"optimized": user_prompt}

        if not hasattr(response, 'choices') or response.choices is None:
            print(f"[DeepSeek] No choices attribute or choices is None. Using fallback template")
            fallback = _fallback_prompt(user_prompt)
            return {"optimized": fallback, "fallback": True}

        if len(response.choices) == 0:
            print(f"[DeepSeek] Choices list is empty. Using fallback template")
            fallback = _fallback_prompt(user_prompt)
            return {"optimized": fallback, "fallback": True}

        choice = response.choices[0]
        if not choice or not hasattr(choice, 'message') or choice.message is None:
            print(f"[DeepSeek] Invalid choice or message. Using fallback template")
            fallback = _fallback_prompt(user_prompt)
            return {"optimized": fallback, "fallback": True}

        optimized_text = choice.message.content
        if not optimized_text:
            print(f"[DeepSeek] Empty response content, using fallback template")
            fallback = _fallback_prompt(user_prompt)
            return {"optimized": fallback, "fallback": True}

        print(f"[DeepSeek] Optimized: {optimized_text[:80]}...")
        return {"optimized": optimized_text, "fallback": False}

    except Exception as e:
        print(f"[DeepSeek] Exception: {type(e).__name__}: {e}")
        print(f"[DeepSeek] Using fallback template")
        # 降级：用固定模板包装用户输入
        fallback = _fallback_prompt(user_prompt)
        return {"optimized": fallback, "fallback": True}


def generate_image(prompt: str, max_wait: int = 300) -> Optional[np.ndarray]:
    """用 Qwen-Image-2512 生成指甲纹理图（异步）。

    Args:
        prompt: 英文描述（来自 DeepSeek 的 full_description）
        max_wait: 最大等待秒数

    Returns:
        生成的图片 numpy 数组 (BGR)，或 None 如果失败
    """
    token = _get_modelscope_token()
    if not token:
        raise RuntimeError("请设置环境变量 MODELSCOPE_TOKEN 后再使用美甲设计生成功能")

    # 1) 提交任务
    submit_response = requests.post(
        f"{MODELSCOPE_BASE_URL}v1/images/generations",
        headers={**_build_common_headers(), "X-ModelScope-Async-Mode": "true"},
        json={
            "model": "Qwen/Qwen-Image-2512",
            "prompt": prompt,
            "size": "1024x1024",
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        }
    )
    submit_response.raise_for_status()
    task_id = submit_response.json()["task_id"]
    print(f"[Qwen] Image generation task: {task_id}")

    # 2) 轮询等待结果
    start_time = time.time()
    while time.time() - start_time < max_wait:
        result = requests.get(
            f"{MODELSCOPE_BASE_URL}v1/tasks/{task_id}",
            headers={**_build_common_headers(), "X-ModelScope-Task-Type": "image_generation"},
        )
        result.raise_for_status()
        data = result.json()

        if data["task_status"] == "SUCCEED":
            # 下载图片
            img_url = data["output_images"][0]
            img_response = requests.get(img_url)
            img_array = cv2.imdecode(
                np.frombuffer(img_response.content, np.uint8),
                cv2.IMREAD_COLOR
            )
            print(f"[Qwen] Image generated successfully")
            return img_array

        elif data["task_status"] == "FAILED":
            print(f"[Qwen] Image generation failed")
            return None

        time.sleep(5)

    print(f"[Qwen] Timeout waiting for image")
    return None


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
    print(f"[Design] 找到 {len(contours)} 个轮廓")

    # 筛选足够大的轮廓（过滤噪声）
    min_area = (h * w) / 200  # 至少占图像 0.5%
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    print(f"[Design] 有效轮廓: {len(valid_contours)} 个")

    if len(valid_contours) >= 5:
        # 轮廓方法：按 x 坐标排序，取最大的 5 个
        nail_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[0])[-5:]
        print(f"[Design] 使用轮廓方法提取指甲")
    else:
        print(f"[Design] 轮廓不足，使用等分方法")
        # 水平等分方法：基于整体指甲区域范围
        y_coords, x_coords = np.where(nail_mask > 0)
        if len(x_coords) == 0:
            print(f"[Design] 未找到指甲区域")
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
                print(f"[Design] 指甲 {fi}: {nail_bgra.shape} (等分法)")

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

        # 用颜色检测的 alpha：白色背景变透明
        nail_bgra[:,:,3] = alpha_mask

        nails.append(nail_bgra)
        print(f"[Design] Extracted nail {fi}: {nail_bgra.shape} (scaled from {w_rect}x{h_rect})")

    return nails


def apply_texture_to_nail(texture_img: np.ndarray, nail_mask_path: Optional[str] = None) -> np.ndarray:
    """把生成的纹理贴到指甲模具上。

    Args:
        texture_img: 生成的纹理图 (BGR)
        nail_mask_path: 指甲模具 PNG 路径（灰度），默认使用全局 NAIL_TEMPLATE_PATH

    Returns:
        贴好的指甲图 (BGRA)，透明部分为 alpha=0
    """
    # 读取模具（用 numpy.fromfile 避免中文路径问题）
    if nail_mask_path is None:
        nail_mask_path = str(NAIL_TEMPLATE_PATH)

    try:
        data = np.fromfile(nail_mask_path, dtype=np.uint8)
        mask = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    except Exception as e:
        print(f"[Error] Failed to read nail template: {e}")
        raise FileNotFoundError(f"Nail template not found: {nail_mask_path}")

    if mask is None:
        raise FileNotFoundError(f"Nail template not found: {nail_mask_path}")

    h, w = mask.shape
    # 缩放纹理到模具大小
    texture_resized = cv2.resize(texture_img, (w, h), interpolation=cv2.INTER_AREA)

    # 创建 BGRA 输出
    result = cv2.cvtColor(texture_resized, cv2.COLOR_BGR2BGRA)

    # 用模具作为 alpha 通道
    result[:, :, 3] = (mask * (mask / 255.0)).astype(np.uint8)

    return result


def generate_fan_thumbnail(nail_images: list, output_path: str) -> bool:
    """生成扇形缩略图（5个指甲排成扇形）。

    Args:
        nail_images: 5 个指甲的 BGRA 图像列表 [(200,350,4), ...]
        output_path: 输出 PNG 路径

    Returns:
        成功则 True
    """
    # 画布尺寸
    W, H = 420, 300

    # 扇形布局 (finger_idx, 旋转度, x中心比例, 指甲高度比例)
    LAYOUT = [
        (4, +22, 0.10, 0.42),
        (3, +11, 0.28, 0.54),
        (2,   0, 0.50, 0.65),
        (1, -11, 0.72, 0.57),
        (0, -20, 0.90, 0.46),
    ]

    BASE_Y = {4: int(H*0.94), 3: int(H*0.90), 2: int(H*0.87), 1: int(H*0.90), 0: int(H*0.94)}
    DRAW_ORDER = [2, 3, 1, 4, 0]

    # 白底画布 BGRA
    canvas = np.full((H, W, 4), 255, dtype=np.uint8)

    # 合成指甲
    layout_by_fi = {fi: (angle, cx_frac, h_frac) for fi, angle, cx_frac, h_frac in LAYOUT}

    for fi in DRAW_ORDER:
        if fi >= len(nail_images):
            continue
        nail = nail_images[fi]
        angle, cx_frac, h_frac = layout_by_fi[fi]
        target_h = int(H * h_frac)
        cx = int(W * cx_frac)
        cy_base = BASE_Y[fi]

        # 缩放指甲
        nh, nw = nail.shape[:2]
        scale = target_h / nh
        new_h = max(4, int(nh * scale))
        new_w = max(4, int(nw * scale))
        nail_resized = cv2.resize(nail, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 旋转
        M = cv2.getRotationMatrix2D((new_w / 2, new_h / 2), angle, 1.0)
        cos_a = abs(M[0, 0]); sin_a = abs(M[0, 1])
        rot_w = int(new_h * sin_a + new_w * cos_a) + 4
        rot_h = int(new_h * cos_a + new_w * sin_a) + 4
        M[0, 2] += (rot_w - new_w) / 2
        M[1, 2] += (rot_h - new_h) / 2
        rotated = cv2.warpAffine(nail_resized, M, (rot_w, rot_h),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=(255, 255, 255, 0))

        # 合成到画布
        x0 = int(cx - rot_w / 2)
        y0 = int(cy_base - rot_h)

        CH, CW = canvas.shape[:2]
        sx0 = max(0, -x0); sx1 = min(rot_w, CW - x0)
        sy0 = max(0, -y0); sy1 = min(rot_h, CH - y0)
        if sx0 >= sx1 or sy0 >= sy1:
            continue

        src = rotated[sy0:sy1, sx0:sx1].astype(np.float32)
        dx0, dy0 = x0 + sx0, y0 + sy0
        dst = canvas[dy0:dy0+(sy1-sy0), dx0:dx0+(sx1-sx0)].astype(np.float32)
        a = src[:, :, 3:4] / 255.0
        canvas[dy0:dy0+(sy1-sy0), dx0:dx0+(sx1-sx0)] = np.clip(
            src * a + dst * (1 - a), 0, 255).astype(np.uint8)

    # 保存
    Path(output_path).parent.mkdir(exist_ok=True)
    ok, buf = cv2.imencode(".png", canvas, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if ok:
        buf.tofile(output_path)
        return True
    return False


def generate_design_preview(user_prompt: str, design_id: Optional[str] = None) -> Dict:
    """第一步：生成设计预览图（平面 2D 设计）。

    返回原始的设计图片给前端展示，用户确认后再处理。
    """
    if not design_id:
        import uuid
        design_id = f"gen_{int(time.time())}_{str(uuid.uuid4())[:8]}"

    print(f"\n[Design] Generating preview: {design_id}")
    print(f"[Design] User prompt: {user_prompt}")

    try:
        token = _get_modelscope_token()
        if not token:
            return {
                "success": False,
                "design_id": design_id,
                "error": "MODELSCOPE_TOKEN 未配置，无法调用美甲设计生成接口",
            }

        # 1) 优化提示词
        optimized = optimize_prompt(user_prompt)
        optimized_text = optimized.get('optimized', user_prompt)
        print(f"[Design] Optimized: {optimized_text[:80]}...")

        # 2) 生成平面设计图
        design_img = generate_image(optimized_text)
        if design_img is None:
            return {
                "success": False,
                "design_id": design_id,
                "error": "Failed to generate image"
            }
        print(f"[Design] Design image shape: {design_img.shape}")

        # 3) 保存原始设计图供预览
        preview_path = str(DESIGNS_GEN_DIR / f"{design_id}_preview.jpg")
        ok, buf = cv2.imencode(".jpg", design_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            buf.tofile(preview_path)
            print(f"[Design] Preview saved: {preview_path}")

        return {
            "success": True,
            "design_id": design_id,
            "preview_url": f"/designs_generated/{design_id}_preview.jpg",
            "prompt": user_prompt,
            "optimized": optimized,
        }

    except Exception as e:
        print(f"[Design] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "design_id": design_id,
            "error": f"Preview generation failed: {str(e)}"
        }


def confirm_design(design_id: str) -> Dict:
    """第二步：用户确认设计后，抠图 + 贴模具 + 生成试戴用的模具。"""
    print(f"\n[Design] Confirming design: {design_id}")

    try:
        # 读取原始预览图
        print(f"[Design] Reading preview image...")
        preview_path = DESIGNS_GEN_DIR / f"{design_id}_preview.jpg"
        print(f"[Design] Preview path: {preview_path}")

        data = np.fromfile(str(preview_path), dtype=np.uint8)
        design_img = cv2.imdecode(data, cv2.IMREAD_COLOR)

        if design_img is None:
            print(f"[Design] Failed to read image from {preview_path}")
            return {
                "success": False,
                "error": "Preview image not found"
            }

        print(f"[Design] Design image shape: {design_img.shape}")

        # 3) 从预览图中裁剪出 5 个指甲
        print(f"[Design] Extracting nails from preview image...")
        nails = extract_nails_from_preview(design_img)

        # 4) 保存单个指甲模具到 molds/ 目录（供试戴使用）
        print(f"[Design] Saving nail molds for try-on...")
        from pathlib import Path as PathlibPath
        molds_dir = PathlibPath(BACKEND) / "molds" / design_id
        molds_dir.mkdir(parents=True, exist_ok=True)
        for fi, nail in enumerate(nails):
            nail_path = str(molds_dir / f"{fi}.png")
            ok, buf = cv2.imencode(".png", nail)
            if ok:
                buf.tofile(nail_path)
                print(f"[Design] Nail mold saved: {nail_path}")

        print(f"[Design] Confirmed: {design_id}")
        return {
            "success": True,
            "design_id": design_id,
        }

    except Exception as e:
        print(f"[Design] Confirm error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Design confirmation failed: {str(e)}"
        }


def create_design(user_prompt: str, design_id: Optional[str] = None) -> Dict:
    """从用户提示词生成完整的美甲设计。

    Returns:
        {
            "success": bool,
            "design_id": str,
            "thumbnail_url": str,
            "prompt": str,
            "optimized": {...},
            "error": str (if failed)
        }
    """
    if not design_id:
        import uuid
        design_id = f"gen_{int(time.time())}_{str(uuid.uuid4())[:8]}"

    print(f"\n[Design] Creating design: {design_id}")
    print(f"[Design] User prompt: {user_prompt}")

    try:
        # 1) 优化提示词
        optimized = optimize_prompt(user_prompt)
        optimized_text = optimized.get('optimized', user_prompt)
        print(f"[Design] Optimized: {optimized_text[:100]}...")

        # 2) 生成纹理图
        texture_img = generate_image(optimized_text)
        if texture_img is None:
            return {
                "success": False,
                "design_id": design_id,
                "error": "Failed to generate image"
            }
        print(f"[Design] Texture image shape: {texture_img.shape}")

        # 3) 应用到指甲模具（生成 5 个指甲）
        nails = []
        for fi in range(5):
            try:
                nail = apply_texture_to_nail(texture_img)  # 使用全局模具路径
                nails.append(nail)
                print(f"[Design] Nail {fi} created: {nail.shape}")
            except Exception as e:
                print(f"[Design] Error creating nail {fi}: {e}")
                import traceback
                traceback.print_exc()
                raise

        # 4) 生成扇形缩略图
        print(f"[Design] Generating thumbnail with {len(nails)} nails...")
        thumbnail_path = str(DESIGNS_GEN_DIR / f"{design_id}.png")
        success = generate_fan_thumbnail(nails, thumbnail_path)
        if not success:
            return {
                "success": False,
                "design_id": design_id,
                "error": "Failed to create thumbnail"
            }
        print(f"[Design] Thumbnail saved: {thumbnail_path}")

        # 5) 保存元数据
        metadata = {
            "id": design_id,
            "user_prompt": user_prompt,
            "optimized": optimized,
            "thumbnail": f"{design_id}.png",
            "created_at": time.time(),
            "nails": [f"{design_id}_nail_{i}.png" for i in range(5)],
        }
        metadata_path = DESIGNS_GEN_DIR / "metadata.json"
        try:
            metadata_list = json.loads(metadata_path.read_text(encoding="utf-8"))
        except:
            metadata_list = []
        metadata_list.append(metadata)
        metadata_path.write_text(json.dumps(metadata_list, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"[Design] Created: {design_id}")
        return {
            "success": True,
            "design_id": design_id,
            "thumbnail_url": f"/designs_generated/{design_id}.png",
            "prompt": user_prompt,
            "optimized": optimized,
        }

    except Exception as e:
        print(f"[Design] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "design_id": design_id,
            "error": f"Design creation failed: {str(e)}"
        }

"""美甲 AI 试戴后端服务。

试戴走 nail_tryon_v2(路线A: YOLO分割+标准甲形+模具/纯色合成)。
- design_id 或 design_image 定位款式
- color 给定 → 纯色合成模式(可任意换色)；否则 → 模具贴图模式
"""
import base64
import os

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import json
import cv2
import numpy as np
from pathlib import Path
from openai import OpenAI

from hand_detector import get_detector
from analytics import log_try_on, log_analyze_hand, get_analytics, get_design_analytics
import nail_tryon_v2
from design_generator import generate_design_preview, confirm_design

app = FastAPI(title="美甲AI试戴后端服务", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SKIN_PALETTE = [
    {"code": "#FFE6D1", "label": "暖白色"},
    {"code": "#F5C6A0", "label": "自然色"},
    {"code": "#D4956A", "label": "小麦色"},
    {"code": "#A0724A", "label": "健康棕"},
]


class ProfileUpsertRequest(BaseModel):
    client_id: str
    name: Optional[str] = None
    avatar: Optional[str] = None
    age: Optional[int] = None
    bio: Optional[str] = None
    skin_color_code: Optional[str] = None
    skin_tone_label: Optional[str] = None
    skin_tone_source: Optional[str] = None
    recommended_style_ids: Optional[List[str]] = None


def _normalize_hex_color(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace('#', '')
    if len(text) == 3 and all(ch in '0123456789abcdefABCDEF' for ch in text):
        text = ''.join(ch * 2 for ch in text)
    if len(text) != 6 or not all(ch in '0123456789abcdefABCDEF' for ch in text):
        return None
    return f"#{text.upper()}"


def _hex_to_rgb(value: str) -> Optional[tuple[int, int, int]]:
    normalized = _normalize_hex_color(value)
    if not normalized:
        return None
    raw = normalized[1:]
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _color_distance(left: str, right: str) -> float:
    rgb_left = _hex_to_rgb(left)
    rgb_right = _hex_to_rgb(right)
    if not rgb_left or not rgb_right:
        return float('inf')
    return sum((a - b) ** 2 for a, b in zip(rgb_left, rgb_right)) ** 0.5


def _snap_skin_code(code: Optional[str], label: Optional[str] = None) -> str:
    normalized = _normalize_hex_color(code)
    if label:
        matched = next((item for item in SKIN_PALETTE if item["label"] == label), None)
        if matched:
            return matched["code"]
    if not normalized:
        return SKIN_PALETTE[1]["code"]
    return min(SKIN_PALETTE, key=lambda item: _color_distance(normalized, item["code"]))["code"]


def _profile_row_to_payload(row) -> Dict:
    if row is None:
        return {}
    return {
        "client_id": row["client_id"],
        "name": row["name"],
        "avatar": row["avatar"],
        "age": row["age"],
        "bio": row["bio"],
        "skinColorCode": row["skin_color_code"],
        "skinToneLabel": row["skin_tone_label"],
        "skinToneSource": row["skin_tone_source"],
        "recommendedStyleIds": row["recommended_style_ids"] or [],
    }


def _recommendation_ids_from_profile(skin_color_code: Optional[str]) -> List[str]:
    if not skin_color_code:
        return []
    try:
        skin_hex = _normalize_hex_color(skin_color_code)
        if not skin_hex:
            return []
        # 与前端一致的简单推荐逻辑：根据肤色把当前 3 个最匹配款式保存下来
        palette_names = {
            "#FFE6D1": ["裸", "奶", "雾", "粉", "法式", "冰", "透"],
            "#F5C6A0": ["奶", "咖", "玫瑰", "豆沙", "香槟", "法式", "果冻"],
            "#D4956A": ["亮", "钻", "银", "金", "果冻", "宝石", "镜面", "闪"],
            "#A0724A": ["黑", "深", "豹", "星", "亮", "钻", "银", "金"],
        }
        matched = min(SKIN_PALETTE, key=lambda item: _color_distance(skin_hex, item["code"]))
        keywords = palette_names.get(matched["code"], [])
        scored = []
        for design in DESIGNS:
            score = 0
            text = f"{design.get('name', '')} {' '.join(design.get('tags', []) or [])} {design.get('bg', '')}"
            for word in keywords:
                if word and word in text:
                    score += 5
            scored.append((score, design.get('id')))
        scored.sort(key=lambda item: (-item[0], item[1] or ''))
        return [design_id for score, design_id in scored[:3] if design_id]
    except Exception:
        return []


async def _fetch_profile_row(client_id: str):
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT client_id, name, avatar, age, bio, skin_color_code, skin_tone_label, skin_tone_source, recommended_style_ids
            FROM user_profiles
            WHERE client_id = $1
            """,
            client_id,
        )


async def _upsert_profile_row(payload: ProfileUpsertRequest):
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")

    skin_color_code = _snap_skin_code(payload.skin_color_code, payload.skin_tone_label)
    recommended_style_ids = payload.recommended_style_ids or _recommendation_ids_from_profile(skin_color_code)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_profiles (
              client_id, name, avatar, age, bio,
              skin_color_code, skin_tone_label, skin_tone_source,
              recommended_style_ids, updated_at
            ) VALUES (
              $1, $2, $3, $4, $5,
              $6, $7, $8,
              $9::jsonb, now()
            )
            ON CONFLICT (client_id) DO UPDATE SET
              name = EXCLUDED.name,
              avatar = EXCLUDED.avatar,
              age = EXCLUDED.age,
              bio = EXCLUDED.bio,
              skin_color_code = EXCLUDED.skin_color_code,
              skin_tone_label = EXCLUDED.skin_tone_label,
              skin_tone_source = EXCLUDED.skin_tone_source,
              recommended_style_ids = EXCLUDED.recommended_style_ids,
              updated_at = now()
            RETURNING client_id, name, avatar, age, bio, skin_color_code, skin_tone_label, skin_tone_source, recommended_style_ids
            """,
            payload.client_id,
            payload.name,
            payload.avatar,
            payload.age,
            payload.bio,
            skin_color_code,
            payload.skin_tone_label,
            payload.skin_tone_source,
            json.dumps(recommended_style_ids),
        )
    return row


def _build_skin_analysis_client() -> Optional[OpenAI]:
    token = os.getenv("MODELSCOPE_TOKEN", "").strip()
    if not token:
        return None
    return OpenAI(
        base_url="https://api-inference.modelscope.cn/v1",
        api_key=token,
    )


def _skin_analysis_model_name() -> str:
    return os.getenv("SKIN_ANALYSIS_MODEL", "Qwen/Qwen2.5-VL-72B-Instruct").strip() or "Qwen/Qwen2.5-VL-72B-Instruct"


def _image_to_data_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


@app.on_event("startup")
async def _startup_db_pool():
    try:
        from db.pool import create_pool

        app.state.db_pool = await create_pool()
        print("[DB] connection pool created")
    except Exception as e:
        print(f"[DB] pool creation failed: {e}")


@app.on_event("shutdown")
async def _shutdown_db_pool():
    try:
        pool = getattr(app.state, "db_pool", None)
        if pool is not None:
            await pool.close()
            print("[DB] connection pool closed")
    except Exception as e:
        print(f"[DB] pool close failed: {e}")

# 设计文件目录
DESIGNS_GEN_DIR = Path(__file__).resolve().parent.parent / "designs_generated"
DESIGNS_GEN_DIR.mkdir(exist_ok=True)

with open("designs.json", "r", encoding="utf-8") as f:
    DESIGNS = json.load(f)["designs"]


def _find_design(design_id: Optional[str], design_image: Optional[str]) -> Dict:
    """按 id 优先、再按 image 路径定位款式。支持 AI 生成的设计（design_id 以 gen_ 开头）。"""
    if design_id:
        # 检查是否是 AI 生成的设计
        if design_id.startswith("gen_"):
            molds_path = Path(__file__).resolve().parent / "molds" / design_id
            if molds_path.exists():
                return {
                    "id": design_id,
                    "name": "AI 生成款式",
                    "image": "",
                    "emoji": "✨",
                    "bg": "#FFF9E6",
                    "price": "AI",
                }
            else:
                raise HTTPException(status_code=404, detail=f"AI 生成设计不存在: {design_id}")

        # 查找静态款式
        d = next((x for x in DESIGNS if x["id"] == design_id), None)
        if not d:
            raise HTTPException(status_code=404, detail=f"design_id 不存在: {design_id}")
        return d
    if design_image:
        d = next((x for x in DESIGNS if x["image"] == design_image), None)
        if not d:
            raise HTTPException(status_code=404, detail=f"design_image 不匹配: {design_image}")
        return d
    if DESIGNS:
        return DESIGNS[0]
    raise HTTPException(status_code=404, detail="设计库为空")


class DesignResponse(BaseModel):
    designs: List[Dict]


@app.get("/", tags=["健康检查"])
async def health_check():
    return {"status": "ok", "service": "美甲AI试戴后端服务", "version": "2.0.0"}


@app.get("/designs_generated/{filename}", tags=["设计文件"])
async def get_design_file(filename: str):
    """提供生成的美甲设计图片文件。"""
    file_path = DESIGNS_GEN_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@app.get("/api/designs", response_model=DesignResponse, tags=["设计库"])
async def get_designs():
    # 为每个设计添加 detailed_image 字段
    designs_with_images = []
    for d in DESIGNS:
        design = d.copy()
        if 'enhanced_hash' in design:
            design['detailed_image'] = f"款式图/{design['enhanced_hash']}.jpg"
        designs_with_images.append(design)
    return {"designs": designs_with_images}


@app.get("/api/designs/{design_id}", tags=["设计库"])
async def get_design(design_id: str):
    d = next((x for x in DESIGNS if x["id"] == design_id), None)
    if not d:
        raise HTTPException(status_code=404, detail="设计不存在")
    return d


@app.get("/api/design-color/{design_id}", tags=["设计库"])
async def get_design_color(design_id: str):
    """返回该款式的主色(hex)，供前端颜色切换色板默认值。"""
    color = nail_tryon_v2.dominant_color(design_id)
    return {"design_id": design_id, "color": color}


@app.post("/api/analyze-skin-tone", tags=["肤色分析"])
async def analyze_skin_tone(image: UploadFile = File(...), source: Optional[str] = Form(None)):
    """使用视觉模型分析肤色，返回可保存的颜色代码。"""
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="图片不能为空")

    client = _build_skin_analysis_client()
    if client is None:
        raise HTTPException(status_code=503, detail="MODELSCOPE_TOKEN 未配置，无法调用肤色分析模型")

    model_name = _skin_analysis_model_name()
    data_url = _image_to_data_url(contents, image.content_type or "image/jpeg")

    system_msg = """你是美妆/美甲场景下的肤色分析专家。请根据用户上传的自拍、手部照片或手臂照片，识别最有代表性的肤色。

要求：
- 只能输出 JSON，不要额外文字
- code 必须是代表肤色的十六进制颜色代码，格式为 #RRGGBB
- code 只能从以下 4 个颜色里选一个最接近的：#FFE6D1, #F5C6A0, #D4956A, #A0724A
- 颜色代码要尽量贴近皮肤本身，不要受背景、阴影、指甲油、饰品、口红影响
- 如果是自拍，优先参考脸颊或下颌；如果是手部照，优先参考手背或手腕
- 如果光线偏暗，要根据可见肤色做合理校正，不要输出过黑或过白的极端值
- label 只能是：暖白色 / 自然色 / 小麦色 / 健康棕
- undertone 只能是：冷色调 / 暖色调 / 中性色调
- confidence 为 0 到 1 的小数

输出格式：
{"code":"#F5C6A0","label":"自然色","undertone":"中性色调","confidence":0.86,"description":"..."}
"""

    user_msg = f"请分析这张图片的肤色并返回 JSON。来源：{source or 'upload'}"

    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_msg},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            raise HTTPException(status_code=502, detail="肤色分析模型未返回内容")

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', content, re.S)
            if not match:
                raise HTTPException(status_code=502, detail="肤色分析模型返回的不是 JSON")
            result = json.loads(match.group(0))
        code = str(result.get("code", "")).strip().upper()
        if not code.startswith("#"):
            code = f"#{code.lstrip('#')}"

        label = str(result.get("label", "自然色")).strip() or "自然色"
        undertone = str(result.get("undertone", "中性色调")).strip() or "中性色调"
        description = str(result.get("description", "")).strip()
        confidence = result.get("confidence", 0.0)
        code = _snap_skin_code(code, label)
        matched = next((item for item in SKIN_PALETTE if item["code"] == code), None)
        if matched:
            label = matched["label"]

        return {
            "success": True,
            "code": code,
            "label": label,
            "undertone": undertone,
            "confidence": confidence,
            "description": description,
            "model_used": model_name,
            "source": source or "upload",
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SkinAnalysis] Error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"肤色分析失败: {e}")


@app.get("/api/profile", tags=["用户资料"])
async def get_profile(client_id: str):
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    try:
        row = await _fetch_profile_row(client_id)
        if row is None:
            return {"success": True, "profile": {"client_id": client_id}}
        return {"success": True, "profile": _profile_row_to_payload(row)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Profile] fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profile", tags=["用户资料"])
async def upsert_profile(payload: ProfileUpsertRequest):
    if not payload.client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    try:
        row = await _upsert_profile_row(payload)
        return {"success": True, "profile": _profile_row_to_payload(row)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Profile] upsert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detect-hands", tags=["手部检测"])
async def detect_hands(image: UploadFile = File(...)):
    try:
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        result = get_detector().detect(img)
        return {
            "success": result["success"],
            "message": "检测成功" if result["success"] else "未检测到手部",
            "num_hands": result["num_hands"],
            "hands": result["hands"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/try-on", tags=["AI试戴"])
async def try_on(
    image: UploadFile = File(...),
    design_id: Optional[str] = None,
    design_image: Optional[str] = None,
    color: Optional[str] = None,
    shape: str = "oval",
    length: float = 1.0,
    width: float = 1.0,
):
    """AI 试戴。
    - color 给定(hex 如 %23A8B04D / #A8B04D) → 纯色合成；否则用款式模具贴图。
    - shape: "oval"(椭圆) / "almond"(尖形) / "square"(方形)
    - length / width: 0.5-1.5 的长宽系数
    """
    try:
        design = _find_design(design_id, design_image)
        did = design["id"]

        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "message": "图片读取失败", "design": design}

        # 约束参数范围
        shape = shape.lower() if shape in ["oval", "almond", "square"] else "oval"
        length = max(0.5, min(1.5, float(length)))
        width = max(0.5, min(1.5, float(width)))

        print(f"[TryOn] 接收参数: color={color}, shape={shape}, length={length}, width={width}")

        result = nail_tryon_v2.try_on(img, did, color=color,
                                      shape_type=shape, length_ratio=length, width_ratio=width)

        # Analytics logging (existing)
        if not result["success"]:
            log_try_on(did, design.get("name", ""), None, False)
            # DB logging: try_on_logs
            pool = getattr(app.state, "db_pool", None)
            if pool is not None:
                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "INSERT INTO try_on_logs (design_id, success, message) VALUES ($1, $2, $3)",
                            did,
                            False,
                            result.get("error", "试戴失败"),
                        )
                except Exception as e:
                    print(f"[DB] failed to insert try_on_logs (failure): {e}")

            return {"success": False, "message": result.get("error", "试戴失败"), "design": design}

        b64 = cv2.imencode(".jpg", result["image"], [cv2.IMWRITE_JPEG_QUALITY, 88])[1]
        import base64
        image_base64 = base64.b64encode(b64).decode("utf-8")

        log_try_on(did, design.get("name", ""), None, True)

        # DB logging: success
        pool = getattr(app.state, "db_pool", None)
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO try_on_logs (design_id, success, message) VALUES ($1, $2, $3)",
                        did,
                        True,
                        "试戴成功",
                    )
            except Exception as e:
                print(f"[DB] failed to insert try_on_logs (success): {e}")

        return {
            "success": True,
            "message": "试戴成功",
            "image_base64": image_base64,
            "design": design,
            "mode": result.get("mode"),
            "n_applied": result.get("n_applied"),
            "color": color,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-nail-design", tags=["AI设计生成"])
async def generate_nail_design_endpoint(prompt: str):
    """第一步：从提示词生成美甲设计预览图。

    Args:
        prompt: 美甲描述，例如 "短杏仁形、柔粉紫、铬色微型法式"

    Returns:
        {
            "success": bool,
            "design_id": str,
            "preview_url": str,
            "prompt": str,
            "optimized": {...}
        }
    """
    try:
        result = generate_design_preview(prompt)
        if result["success"]:
            return result
        else:
            error_message = result.get("error", "设计预览失败")
            status_code = 503 if "MODELSCOPE_TOKEN" in error_message else 500
            raise HTTPException(status_code=status_code, detail=error_message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/try-on-logs", tags=["后端日志"])
async def get_try_on_logs(limit: int = 50):
    """返回最近的 try_on 日志，按时间倒序。"""
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, design_id, success, message, created_at FROM try_on_logs ORDER BY created_at DESC LIMIT $1", limit)
            results = [dict(r) for r in rows]
        return {"success": True, "logs": results}
    except Exception as e:
        print(f"[DB] failed to fetch try_on_logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/confirm-nail-design", tags=["AI设计生成"])
async def confirm_nail_design_endpoint(design_id: str):
    """第二步：用户确认设计后，处理图片（抠图+贴模具）供试戴。

    Args:
        design_id: 设计 ID

    Returns:
        {
            "success": bool,
            "design_id": str,
            "thumbnail_url": str
        }
    """
    try:
        result = confirm_design(design_id)
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "设计确认失败"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detect-nails-preview", tags=["美甲检测"])
async def detect_nails_preview_endpoint(image: UploadFile = File(...)):
    """预检测：返回原图和检测到的指甲位置（用于编辑器）。

    Args:
        image: 用户上传的指甲图片

    Returns:
        {
            "success": bool,
            "image_data": "base64编码的图片",
            "nails_bounds": [{"id": 0, "top": 0.1, "left": 0.1, "bottom": 0.8, "right": 0.4}],
            "message": str
        }
    """
    try:
        import base64

        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"success": False, "message": "图片读取失败"}

        h, w = img.shape[:2]

        # 简化策略：多阈值尝试，找最好的结果
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        best_contours = []
        best_threshold = 200

        # 尝试不同的亮度阈值
        for threshold_val in range(200, 250, 10):
            _, bright_mask = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY)

            # 反转得到指甲掩码
            nail_mask = cv2.bitwise_not(bright_mask)

            # 形态学清理
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            nail_mask = cv2.morphologyEx(nail_mask, cv2.MORPH_CLOSE, kernel)
            nail_mask = cv2.morphologyEx(nail_mask, cv2.MORPH_OPEN, kernel)

            # 找轮廓
            contours, _ = cv2.findContours(nail_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 筛选轮廓
            min_area = (h * w) / 1500
            valid = []

            for c in contours:
                area = cv2.contourArea(c)
                if area < min_area:
                    continue

                x, y, w_rect, h_rect = cv2.boundingRect(c)
                aspect_ratio = h_rect / w_rect if w_rect > 0 else 0

                # 宽高比范围：0.7 - 5.0
                if 0.7 < aspect_ratio < 5.0:
                    valid.append(c)

            print(f"[PreDetect] 阈值 {threshold_val}: 找到 {len(valid)} 个轮廓")

            # 如果找到接近 5 个的，优先选择
            if len(valid) >= 4 and len(valid) <= 6:
                best_contours = valid
                best_threshold = threshold_val
                break
            elif len(valid) > len(best_contours):
                best_contours = valid
                best_threshold = threshold_val

        # 按 x 坐标排序
        valid_contours = sorted(best_contours, key=lambda c: cv2.boundingRect(c)[0])

        # 取最多 5 个
        if len(valid_contours) > 5:
            valid_contours = sorted(valid_contours, key=lambda c: cv2.contourArea(c), reverse=True)[:5]
            valid_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[0])

        print(f"[PreDetect] 用阈值 {best_threshold} 检测到 {len(valid_contours)} 个指甲")

        # 生成指甲框位置（用旋转矩形贴合指甲方向）
        nails_bounds = []
        for idx, contour in enumerate(valid_contours):
            # 计算最小外接旋转矩形
            rect = cv2.minAreaRect(contour)
            center, (width, height), angle = rect

            # 转换为相对坐标（0-1）
            cx, cy = center[0] / w, center[1] / h
            rw, rh = width / w, height / h

            nails_bounds.append({
                "id": idx,
                "cx": cx,
                "cy": cy,
                "width": rw,
                "height": rh,
                "angle": angle  # 旋转角度（度数）
            })

        # 编码图片为 base64
        _, buf = cv2.imencode(".jpg", img)
        img_base64 = base64.b64encode(buf).decode("utf-8")
        img_data_url = f"data:image/jpeg;base64,{img_base64}"

        return {
            "success": True,
            "image_data": img_data_url,
            "nails_bounds": nails_bounds,
            "message": f"检测到 {len(nails_bounds)} 个指甲"
        }

    except Exception as e:
        print(f"[DetectNailsPreview] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"检测失败: {str(e)}"}


@app.post("/api/confirm-crop", tags=["美甲检测"])
async def confirm_crop_endpoint(image: UploadFile = File(...), crops: str = Form(None)):
    """根据用户调整的参数进行最终裁剪。

    Args:
        image: 用户上传的指甲图片
        crops: JSON 字符串，包含每个指甲的裁剪参数

    Returns:
        {
            "success": bool,
            "nails": [base64图片数组],
            "message": str
        }
    """
    try:
        import base64
        import json

        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"success": False, "message": "图片读取失败"}

        h, w = img.shape[:2]

        # 解析裁剪参数（旋转矩形格式）
        print(f"[ConfirmCrop] 接收 crops 参数: {crops}")

        crops_list = []
        if crops:
            try:
                crops_list = json.loads(crops)
                print(f"[ConfirmCrop] 解析得到 {len(crops_list)} 个裁剪参数")
            except Exception as e:
                print(f"[ConfirmCrop] JSON 解析失败: {e}")
                return {"success": False, "message": f"参数解析失败: {e}"}
        else:
            print(f"[ConfirmCrop] 没有裁剪参数")
            return {"success": False, "message": "没有裁剪参数"}

        nail_images = []

        for idx, crop in enumerate(crops_list):
            print(f"[ConfirmCrop] 处理第 {idx+1} 个裁剪")
            # 获取参数（前端已转换为像素坐标）
            cx = crop.get("cx", w / 2)
            cy = crop.get("cy", h / 2)
            rect_w = crop.get("width", w * 0.2)
            rect_h = crop.get("height", h * 0.3)
            angle = crop.get("angle", 0)

            print(f"[ConfirmCrop] 处理矩形: cx={cx:.1f}, cy={cy:.1f}, w={rect_w:.1f}, h={rect_h:.1f}, angle={angle:.1f}")

            # 用旋转矩形裁剪（处理旋转角度）
            center = (cx, cy)
            size = (rect_w, rect_h)
            angle_rad = angle

            # 获取旋转矩形的四个角
            box = cv2.boxPoints((center, size, angle_rad))
            box = np.float32(box)

            # 获取外接矩形边界
            x_min = max(0, int(np.floor(box[:, 0].min())))
            x_max = min(w, int(np.ceil(box[:, 0].max())))
            y_min = max(0, int(np.floor(box[:, 1].min())))
            y_max = min(h, int(np.ceil(box[:, 1].max())))

            if x_max <= x_min + 5 or y_max <= y_min + 5:
                print(f"[ConfirmCrop] 矩形过小: {x_max-x_min}x{y_max-y_min}")
                continue

            # 裁剪外接矩形
            nail_crop = img[y_min:y_max, x_min:x_max].copy()

            if nail_crop.size == 0:
                print(f"[ConfirmCrop] 裁剪为空")
                continue

            h_crop, w_crop = nail_crop.shape[:2]

            # 创建旋转矩形掩码
            mask = np.zeros((h_crop, w_crop), dtype=np.uint8)
            box_local = box.copy().astype(np.int32)
            box_local[:, 0] -= x_min
            box_local[:, 1] -= y_min
            cv2.fillPoly(mask, [box_local], 255)

            # 应用掩码
            nail_crop = cv2.bitwise_and(nail_crop, nail_crop, mask=mask)

            print(f"[ConfirmCrop] 裁剪得到: {nail_crop.shape}")

            if nail_crop.size == 0:
                print(f"[ConfirmCrop] 裁剪图片为空")
                continue

            h_crop, w_crop = nail_crop.shape[:2]
            print(f"[ConfirmCrop] 裁剪得到: {w_crop}x{h_crop}")

            if h_crop < 5 or w_crop < 5:
                print(f"[ConfirmCrop] 尺寸过小，跳过")
                continue

            # 标准化尺寸
            max_size = max(h_crop, w_crop)
            scale = 280 / max_size if max_size > 0 else 1.0
            new_h = max(80, int(h_crop * scale))
            new_w = max(50, int(w_crop * scale))

            nail_crop_resized = cv2.resize(nail_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)
            print(f"[ConfirmCrop] 缩放到: {new_w}x{new_h}")

            # 简单方式：直接用白色作为背景，转 BGRA
            nail_bgra = cv2.cvtColor(nail_crop_resized, cv2.COLOR_BGR2BGRA)

            # 生成 alpha：简单的灰度阈值
            gray = cv2.cvtColor(nail_crop_resized, cv2.COLOR_BGR2GRAY)

            # 用较低的阈值，保留更多细节
            _, alpha_mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)

            # 确保至少有一些前景像素
            if alpha_mask.sum() == 0:
                # 如果完全白色，用更低的阈值
                _, alpha_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

            if alpha_mask.sum() == 0:
                # 最后的保障：全部保留
                alpha_mask = np.full_like(gray, 255)

            print(f"[ConfirmCrop] Alpha 掩码: {(alpha_mask > 0).sum()} 个前景像素")

            nail_bgra[:, :, 3] = alpha_mask

            try:
                # 转 base64
                _, buf = cv2.imencode(".png", nail_bgra)
                b64 = base64.b64encode(buf).decode("utf-8")
                nail_images.append(f"data:image/png;base64,{b64}")
                print(f"[ConfirmCrop] ✅ 成功添加第 {len(nail_images)} 个指甲 ({len(b64)} 字节)")
            except Exception as e:
                print(f"[ConfirmCrop] ❌ 编码失败: {e}")
                continue

        if not nail_images:
            return {"success": False, "message": "裁剪失败，未找到有效区域"}

        return {
            "success": True,
            "message": f"成功裁剪 {len(nail_images)} 个指甲",
            "nails": nail_images
        }

    except Exception as e:
        print(f"[ConfirmCrop] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"裁剪失败: {str(e)}"}


@app.post("/api/extract-nails-from-marking", tags=["美甲检测"])
async def extract_nails_from_marking_endpoint(image: UploadFile = File(...), mask: str = Form(None)):
    """基于用户标记的掩码，用 GrabCut 分割并提取指甲。

    Args:
        image: 用户上传的指甲图片
        mask: 用户标记掩码（base64 编码的 PNG，绿色=保留，红色=删除）

    Returns:
        {
            "success": bool,
            "nails": [base64图片数组],
            "message": str
        }
    """
    try:
        import base64

        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"success": False, "message": "图片读取失败"}

        h, w = img.shape[:2]

        # 解析标记掩码
        if not mask:
            return {"success": False, "message": "没有标记信息"}

        # 从 data URL 解析 base64
        mask_data = mask.split(',')[1] if ',' in mask else mask
        mask_bytes = base64.b64decode(mask_data)
        mask_nparr = np.frombuffer(mask_bytes, np.uint8)
        mask_img = cv2.imdecode(mask_nparr, cv2.IMREAD_COLOR)

        if mask_img is None:
            return {"success": False, "message": "标记掩码解析失败"}

        # 缩放掩码到原图大小
        mask_img = cv2.resize(mask_img, (w, h), interpolation=cv2.INTER_NEAREST)

        # 提取标记（canvas 是 RGB，但 OpenCV 读取的是 BGR）
        # 绿色标记：#00FF00 = RGB，读取后变成 [0, 255, 0] = BGR
        # 红色标记：#FF0000 = RGB，读取后变成 [0, 0, 255] = BGR

        green_mask = (mask_img[:, :, 1] > 200) & (mask_img[:, :, 0] < 50) & (mask_img[:, :, 2] < 50)
        red_mask = (mask_img[:, :, 2] > 200) & (mask_img[:, :, 0] < 50) & (mask_img[:, :, 1] < 50)

        print(f"[ExtractNails] 绿色像素: {green_mask.sum()}, 红色像素: {red_mask.sum()}")

        # 简单方式：不用 GrabCut，直接用绿色标记作为前景
        foreground_mask = green_mask.astype(np.uint8) * 255

        # 如果用户没有标记，用自动检测
        if foreground_mask.sum() < (h * w) * 0.001:  # 前景少于 0.1%
            print(f"[ExtractNails] 标记过少，使用自动背景移除")
            # 用之前的自动检测方法
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, foreground_mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)

        # 形态学清理

        # 形态学清理
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        foreground_mask = cv2.morphologyEx(foreground_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)

        # 找轮廓（5 个指甲）
        contours, _ = cv2.findContours(foreground_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 筛选轮廓（面积、宽高比）
        min_area = (h * w) / 500
        valid_contours = []

        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue

            x, y, w_rect, h_rect = cv2.boundingRect(c)
            aspect_ratio = h_rect / w_rect if w_rect > 0 else 0

            # 指甲通常是竖长的
            if 1.0 < aspect_ratio < 4.0:
                valid_contours.append(c)

        # 按 x 坐标排序
        valid_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[0])

        # 取最多 5 个
        if len(valid_contours) > 5:
            valid_contours = sorted(valid_contours, key=lambda c: cv2.contourArea(c), reverse=True)[:5]
            valid_contours = sorted(valid_contours, key=lambda c: cv2.boundingRect(c)[0])

        print(f"[ExtractNails] 分割得到 {len(valid_contours)} 个指甲")

        # 裁剪每个指甲
        nail_images = []
        for contour in valid_contours:
            # 计算最小外接旋转矩形
            rect = cv2.minAreaRect(contour)
            cx, cy = rect[0]
            w_nail, h_nail = rect[1]
            angle = rect[2]

            # 裁剪
            box = cv2.boxPoints(rect)
            box = np.int32(np.round(box))

            x_min = max(0, int(box[:, 0].min()))
            x_max = min(w, int(box[:, 0].max()) + 1)
            y_min = max(0, int(box[:, 1].min()))
            y_max = min(h, int(box[:, 1].max()) + 1)

            nail_crop = img[y_min:y_max, x_min:x_max].copy()

            if nail_crop.size == 0:
                continue

            # 生成掩码（只保留指甲部分）
            h_crop, w_crop = nail_crop.shape[:2]
            mask_local = np.zeros((h_crop, w_crop), dtype=np.uint8)
            box_local = box.copy()
            box_local[:, 0] -= x_min
            box_local[:, 1] -= y_min
            cv2.fillPoly(mask_local, [box_local], 255)

            nail_crop = cv2.bitwise_and(nail_crop, nail_crop, mask=mask_local)

            # 旋转校正
            if angle != 0:
                center_crop = (w_nail / 2, h_nail / 2)
                rot_mat = cv2.getRotationMatrix2D(center_crop, angle, 1.0)

                cos = np.abs(rot_mat[0, 0])
                sin = np.abs(rot_mat[0, 1])
                new_w = int(h_nail * sin + w_nail * cos)
                new_h = int(h_nail * cos + w_nail * sin)

                rot_mat[0, 2] += (new_w / 2) - center_crop[0]
                rot_mat[1, 2] += (new_h / 2) - center_crop[1]

                nail_crop = cv2.warpAffine(nail_crop, rot_mat, (new_w, new_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

                h_crop, w_crop = nail_crop.shape[:2]
                target_h = int(h_nail)
                target_w = int(w_nail)
                x_crop = (w_crop - target_w) // 2
                y_crop = (h_crop - target_h) // 2
                nail_crop = nail_crop[y_crop:y_crop+target_h, x_crop:x_crop+target_w].copy()

            if nail_crop.size == 0:
                continue

            # 标准化尺寸
            h_crop, w_crop = nail_crop.shape[:2]
            max_size = max(h_crop, w_crop)
            scale = 280 / max_size if max_size > 0 else 1.0
            new_h = max(80, int(h_crop * scale))
            new_w = max(50, int(w_crop * scale))
            nail_crop = cv2.resize(nail_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # 生成 alpha 掩码
            max_channel = np.maximum(np.maximum(nail_crop[:, :, 0], nail_crop[:, :, 1]), nail_crop[:, :, 2])
            alpha_mask = np.where(max_channel > 200, 0, 255).astype(np.uint8)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_CLOSE, kernel)
            kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            alpha_mask = cv2.erode(alpha_mask, kernel_small, iterations=1)

            nail_bgra = cv2.cvtColor(nail_crop, cv2.COLOR_BGR2BGRA)
            nail_bgra[:, :, 3] = alpha_mask

            # 转 base64
            _, buf = cv2.imencode(".png", nail_bgra)
            b64 = base64.b64encode(buf).decode("utf-8")
            nail_images.append(f"data:image/png;base64,{b64}")

        if not nail_images:
            return {"success": False, "message": "抠图失败，未找到有效区域"}

        return {
            "success": True,
            "message": f"成功抠图 {len(nail_images)} 个指甲",
            "nails": nail_images
        }

    except Exception as e:
        print(f"[ExtractNails] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"抠图失败: {str(e)}"}


@app.post("/api/detect-nails", tags=["美甲检测"])
async def detect_nails_endpoint(image: UploadFile = File(...)):
    """检测并裁剪上传图片中的指甲。

    Args:
        image: 用户上传的指甲图片

    Returns:
        {
            "success": bool,
            "nails": [base64图片数组],
            "message": str
        }
    """
    try:
        from design_generator import extract_nails_from_preview

        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"success": False, "message": "图片读取失败"}

        # 裁剪指甲
        nails = extract_nails_from_preview(img)

        if not nails:
            return {"success": False, "message": "未检测到指甲"}

        # 转 base64
        import base64
        nail_images = []
        for nail in nails:
            _, buf = cv2.imencode(".png", nail)
            b64 = base64.b64encode(buf).decode("utf-8")
            nail_images.append(f"data:image/png;base64,{b64}")

        return {
            "success": True,
            "message": f"成功检测到 {len(nails)} 个指甲",
            "nails": nail_images
        }
    except Exception as e:
        print(f"[DetectNails] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detect-nails-vision", tags=["美甲检测"])
async def detect_nails_vision_endpoint(image: UploadFile = File(...)):
    """使用 Claude Vision API 进行精准美甲裁剪。

    Args:
        image: 用户上传的指甲图片

    Returns:
        {
            "success": bool,
            "nails": [base64图片数组],
            "message": str
        }
    """
    try:
        import base64
        import json
        from anthropic import Anthropic

        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"success": False, "message": "图片读取失败"}

        # 编码图片为 base64
        _, buf = cv2.imencode(".jpg", img)
        img_base64 = base64.b64encode(buf).decode("utf-8")

        # 调用 Claude Vision API
        client = Anthropic()
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "分析这张图片中的指甲。请识别出所有指甲，并为每个指甲提供位置（相对坐标0-1）。返回 JSON 格式：{\"nails\":[{\"id\":0,\"top\":0.1,\"left\":0.1,\"bottom\":0.8,\"right\":0.4}]} 只返回 JSON"
                        }
                    ],
                }
            ],
        )

        # 解析响应
        response_text = message.content[0].text
        nail_info = json.loads(response_text)

        # 根据识别结果裁剪指甲
        nail_images = []
        h, w = img.shape[:2]

        for nail_data in nail_info.get("nails", []):
            top = int(nail_data.get("top", 0) * h)
            left = int(nail_data.get("left", 0) * w)
            bottom = int(nail_data.get("bottom", 1) * h)
            right = int(nail_data.get("right", 1) * w)

            # 裁剪区域
            nail_crop = img[top:bottom, left:right].copy()

            if nail_crop.size == 0:
                continue

            # 标准化尺寸
            h_crop, w_crop = nail_crop.shape[:2]
            max_size = max(h_crop, w_crop)
            scale = 280 / max_size if max_size > 0 else 1.0
            new_h = max(80, int(h_crop * scale))
            new_w = max(50, int(w_crop * scale))

            nail_crop = cv2.resize(nail_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # 转 BGRA，用亮度检测生成 alpha
            max_channel = np.maximum(
                np.maximum(nail_crop[:, :, 0], nail_crop[:, :, 1]), nail_crop[:, :, 2]
            )
            alpha_mask = np.where(max_channel > 200, 0, 255).astype(np.uint8)

            # 形态学操作平滑
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_CLOSE, kernel)
            kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            alpha_mask = cv2.erode(alpha_mask, kernel_small, iterations=1)

            nail_bgra = cv2.cvtColor(nail_crop, cv2.COLOR_BGR2BGRA)
            nail_bgra[:, :, 3] = alpha_mask

            # 转 base64
            _, buf = cv2.imencode(".png", nail_bgra)
            b64 = base64.b64encode(buf).decode("utf-8")
            nail_images.append(f"data:image/png;base64,{b64}")

        if not nail_images:
            return {"success": False, "message": "Vision 识别失败"}

        return {
            "success": True,
            "message": f"AI 精准裁剪完成，共识别 {len(nail_images)} 个指甲",
            "nails": nail_images
        }

    except Exception as e:
        print(f"[DetectNailsVision] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"AI 裁剪失败: {str(e)}"}


@app.get("/api/analytics", tags=["数据分析"])
async def get_analytics_endpoint():
    return get_analytics()


@app.get("/api/analytics/design/{design_id}", tags=["数据分析"])
async def get_design_analytics_endpoint(design_id: str):
    return get_design_analytics(design_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

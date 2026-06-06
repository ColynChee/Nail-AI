"""美甲 AI 试戴后端服务。

试戴走 nail_tryon_v2(路线A: YOLO分割+标准甲形+模具/纯色合成)。
- design_id 或 design_image 定位款式
- color 给定 → 纯色合成模式(可任意换色)；否则 → 模具贴图模式
"""
import base64
import os
import hashlib
import secrets

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Callable
import json
import cv2
import numpy as np
from pathlib import Path
import sys
from dotenv import load_dotenv
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from hand_detector import get_detector
from analytics import log_try_on, log_analyze_hand, get_analytics, get_design_analytics
# [Phase 2 测试] 临时切换到极端点对齐版本
import nail_tryon_v2_extreme as nail_tryon_v2
import nail_seg
from design_generator import generate_design_preview, confirm_design
from ai_analysis import analyze_with_vision
from image_enhancer import enhance_nail_tryon
from mold_generator import generate_mold_from_inspiration
from bilibili_stats import BilibiliStatsError, get_bilibili_trending
from douyin_stats import DouyinStatsError, get_douyin_trending, inspect_public_douyin_url
from rednote_stats import RedNoteStatsError, get_rednote_trending, inspect_public_rednote_url
from ops_assistant import generate_ops_assistant, get_modelscope_config_status

app = FastAPI(title="美甲AI试戴后端服务", version="2.0.0")

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"[422错误] URL: {request.url}")
    print(f"[422错误] 详情: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

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


class UserDesignCreateRequest(BaseModel):
    client_id: str
    name: Optional[str] = "我的设计"
    source: str = "upload"               # upload | ai | gallery
    image_data: Optional[str] = None     # base64 data URL（上传/AI生成）
    image_url: Optional[str] = None      # 已托管的相对URL（ai/gallery复用）
    style: Optional[str] = None
    scenes: Optional[List[str]] = None
    recommended_colors: Optional[List[str]] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    design_id: Optional[str] = None      # 后端款式ID（gen_/insp_，用于重新试戴）


class UserDesignUpdateRequest(BaseModel):
    name: Optional[str] = None
    style: Optional[str] = None
    scenes: Optional[List[str]] = None
    recommended_colors: Optional[List[str]] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class AuthRequest(BaseModel):
    username: str
    password: str


class WishlistItemRequest(BaseModel):
    client_id: str
    name: str
    emoji: Optional[str] = None
    price: Optional[str] = None
    bg: Optional[str] = None
    image: Optional[str] = None
    design_id: Optional[str] = None


def _new_salt() -> str:
    return secrets.token_hex(16)


def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200_000).hex()


def _verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    try:
        return secrets.compare_digest(_hash_password(password, salt_hex), expected_hash)
    except Exception:
        return False


def _new_client_key() -> str:
    return "acct_" + secrets.token_urlsafe(16)


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


def _jsonb_to_list(value):
    """asyncpg 默认把 JSONB 返回成字符串，这里兼容解析成 list。"""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return []
    return value


def _user_design_row_to_payload(row) -> Dict:
    if row is None:
        return {}
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "name": row["name"],
        "image_url": row["image_url"],
        "source": row["source"],
        "design_id": row["design_id"] if "design_id" in row else None,
        "style": row["style"],
        "scenes": _jsonb_to_list(row["scenes"]),
        "recommended_colors": _jsonb_to_list(row["recommended_colors"]),
        "description": row["description"],
        "tags": _jsonb_to_list(row["tags"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
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
    return os.getenv("SKIN_ANALYSIS_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct").strip() or "Qwen/Qwen3-VL-30B-A3B-Instruct"


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

# 临时图片目录（用于API调用）
TEMP_IMAGE_DIR = Path(__file__).resolve().parent / ".temp_images"
TEMP_IMAGE_DIR.mkdir(exist_ok=True)

# 挂载临时图片目录为静态文件服务
app.mount("/temp_images", StaticFiles(directory=TEMP_IMAGE_DIR), name="temp_images")

# 用户上传/保存的款式图片目录
USER_DESIGNS_DIR = Path(__file__).resolve().parent.parent / "user_designs"
USER_DESIGNS_DIR.mkdir(exist_ok=True)
app.mount("/user_designs", StaticFiles(directory=USER_DESIGNS_DIR), name="user_designs")

with open("designs.json", "r", encoding="utf-8") as f:
    DESIGNS = json.load(f)["designs"]


def _preprocess_image(file_bytes: bytes, filename: str = "") -> np.ndarray:
    """预处理上传的图片，确保是高质量的格式。

    - 如果是 WebP、TIFF 等低质量格式，转换为高质量 JPG
    - 如果是 PNG，保留原样
    - 如果是 JPG，检查质量，必要时重新编码为高质量

    Args:
        file_bytes: 上传的文件二进制内容
        filename: 文件名（用于检测格式）

    Returns:
        处理后的 numpy 数组 (BGR)
    """
    # 读取图片
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    # 检测源文件格式
    ext = filename.lower().split('.')[-1] if filename else ""

    # 对于 WebP、TIFF、BMP 等压缩格式，强制转换为高质量 JPG
    if ext.lower() in ['webp', 'tiff', 'tif', 'bmp', 'gif']:
        print(f"[ImagePreprocess] 检测到 {ext.upper()} 格式，转换为高质量 JPG")
        # 编码为高质量 JPG（质量 95）
        success, jpeg_data = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if success:
            # 再次解码为 numpy 数组，这样可以确保质量
            img = cv2.imdecode(jpeg_data, cv2.IMREAD_COLOR)
            print(f"[ImagePreprocess] 转换完成，图片大小: {img.shape[1]}x{img.shape[0]}")
    elif ext.lower() in ['jpg', 'jpeg']:
        # JPG 文件，检查是否需要重新编码为更高质量
        # 通过重新编码为 95 质量的 JPG 来提升质量
        success, jpeg_data = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if success:
            img = cv2.imdecode(jpeg_data, cv2.IMREAD_COLOR)
            print(f"[ImagePreprocess] JPG 质量优化完成")

    return img


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

        # 检查是否是灵感图生成的设计
        if design_id.startswith("insp_"):
            molds_path = Path(__file__).resolve().parent / "molds" / design_id
            if molds_path.exists():
                return {
                    "id": design_id,
                    "name": "灵感试戴款式",
                    "image": "",
                    "emoji": "🌟",
                    "bg": "#FFF4F0",
                    "price": "AI",
                }
            else:
                raise HTTPException(status_code=404, detail=f"灵感设计不存在: {design_id}")

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


class OpsAssistantRequest(BaseModel):
    items: List[Dict] = []
    summary: Dict = {}
    trendBuckets: List[Dict] = []


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
        img = _preprocess_image(contents, image.filename)
        if img is None:
            return {"success": False, "message": "图片读取失败"}
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
    nail_angles: Optional[str] = None,
    nails_bounds: Optional[str] = None,
    opacity: float = 0.85,
    skip_analysis: Optional[str] = None,
):
    """AI 试戴。
    - color 给定(hex 如 %23A8B04D / #A8B04D) → 纯色合成；否则用款式模具贴图。
    - shape: "oval"(椭圆) / "almond"(尖形) / "square"(方形)
    - length / width: 0.5-1.5 的长宽系数
    - nail_angles: JSON 字符串，格式 {"0": 90.5, "2": 120.0, ...} 用户调整的指甲角度（可选）
    - nails_bounds: JSON 字符串，从前端检测结果获取的指甲边界信息（可选，优先使用）
    """
    try:

        design = _find_design(design_id, design_image)
        did = design["id"]

        contents = await image.read()
        img = _preprocess_image(contents, image.filename)
        if img is None:
            return {"success": False, "message": "图片读取失败", "design": design}

        # 约束参数范围
        shape = shape.lower() if shape in ["oval", "almond", "square"] else "oval"
        length = max(0.5, min(1.5, float(length)))
        width = max(0.5, min(1.5, float(width)))

        # 解析用户调整的指甲角度（过滤掉null/NaN值）
        custom_angles = {}
        if nail_angles:
            try:
                import json
                raw_angles = json.loads(nail_angles)
                custom_angles = {
                    k: v for k, v in raw_angles.items()
                    if v is not None and v == v  # v==v 过滤NaN
                }
                if custom_angles:
                    print(f"[TryOn] 用户自定义指甲角度: {custom_angles}")
            except Exception as e:
                print(f"[TryOn] 解析 nail_angles 失败: {e}")

        # 解析前端检测结果的指甲边界
        preset_bounds = None
        if nails_bounds:
            try:
                import json
                preset_bounds = json.loads(nails_bounds)
                print(f"[TryOn] 接收前端检测的指甲边界: {len(preset_bounds)} 个")
            except Exception as e:
                print(f"[TryOn] 解析 nails_bounds 失败: {e}")

        print(f"[TryOn] 接收参数: color={color}, shape={shape}, length={length}, width={width}, 有预置边界={preset_bounds is not None}")

        # 优先使用前端检测的指甲边界，如果没有才自己检测
        pre_nails = None
        if preset_bounds:
            print(f"[TryOn] 使用前端检测的指甲边界: {len(preset_bounds)} 个")
            # 注：preset_bounds是前端检测的结果，包含cx, cy, width, height, angle等
            # 后端会在try_on中使用这些信息，无需额外处理
            pre_nails = preset_bounds
        elif custom_angles:
            # 如果没有前端检测结果但有自定义角度，则自己分割并应用角度
            from nail_seg import segment_nails as seg_nails
            _detected = seg_nails(img)
            pre_nails = _detected if _detected else None
            # 应用用户自定义的角度
            for nail in (pre_nails or []):
                finger_idx = str(nail.get("finger_idx", -1))
                if finger_idx in custom_angles:
                    nail["tip_angle"] = float(custom_angles[finger_idx])
                    print(f"[TryOn] 应用自定义角度: 指甲{finger_idx} -> {nail['tip_angle']:.1f}°")

        # 调用试戴（如果有pre_nails则使用前端检测，否则后端自动检测）
        result = nail_tryon_v2.try_on(img, did, color=color,
                                      shape_type=shape, length_ratio=length, width_ratio=width,
                                      pre_nails=pre_nails, opacity=opacity)
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

        # 生成 AI 分析（使用 Qwen VL 进行多模态分析）
        design_image_path = None
        try:
            # 获取美甲款式的详细图路径
            if "image" in design and design["image"]:
                # 如果是相对路径，转换为绝对路径
                if not os.path.isabs(design["image"]):
                    design_image_path = os.path.join(
                        Path(__file__).resolve().parent.parent,
                        design["image"]
                    )
                else:
                    design_image_path = design["image"]

                if not os.path.exists(design_image_path):
                    print(f"[TryOn] 款式图不存在: {design_image_path}")
                    design_image_path = None
        except Exception as e:
            print(f"[TryOn] 获取款式图路径失败: {e}")

        if skip_analysis:
            print(f"[TryOn] 跳过 AI 分析（参数调整）")
            analysis = None
        else:
            print(f"[TryOn] 调用 Qwen VL 进行 AI 分析...")
            analysis = analyze_with_vision(
                hand_image=img,
                design_image_path=design_image_path,
                design_name=design.get("name", "当前款式")
            )
        if analysis:
            print(f"[TryOn] AI 分析完成: 匹配度 {analysis.get('confidence', 0):.0%}")

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
            "analysis": analysis,
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


# ===== 我的设计（用户款式）=====
@app.post("/api/analyze-design", tags=["我的设计"])
async def analyze_design(image: UploadFile = File(...)):
    """用视觉模型分析一张美甲款式图，返回风格/场景/配色建议（不保存）。"""
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="图片不能为空")

    client = _build_skin_analysis_client()
    if client is None:
        raise HTTPException(status_code=503, detail="MODELSCOPE_TOKEN 未配置，无法调用款式分析模型")

    model_name = _skin_analysis_model_name()
    data_url = _image_to_data_url(contents, image.content_type or "image/jpeg")

    system_msg = """你是专业的美甲设计分析师。请根据用户上传的美甲款式图片，分析它的特征。

要求：
- 只能输出 JSON，不要任何额外文字
- name: 给这款美甲起一个简短好记的中文名称（不超过6个字）
- style: 一个词概括风格，如「法式」「韩系」「日系」「酷感」「甜美」「复古」「简约」「奢华」
- scenes: 2-4个适合的场景，从「约会」「通勤」「派对」「日常」「婚礼」「面试」「度假」里选
- recommended_colors: 2-4个该款式的主要颜色，用十六进制色码 #RRGGBB
- description: 一句话专业描述这款美甲的特点和搭配建议
- tags: 2-4个风格标签，如「闪耀」「裸色」「花系」「镜面」「钻饰」

输出格式：
{"name":"粉钻渐变","style":"韩系","scenes":["约会","派对"],"recommended_colors":["#F4A0B4","#C0C0C0"],"description":"...","tags":["闪耀","渐变"]}
"""

    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请分析这张美甲款式图片并返回 JSON。"},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )
        content = response.choices[0].message.content if response.choices else ""
        if not content:
            raise HTTPException(status_code=502, detail="款式分析模型未返回内容")
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', content, re.S)
            if not match:
                raise HTTPException(status_code=502, detail="款式分析模型返回的不是 JSON")
            result = json.loads(match.group(0))

        return {
            "success": True,
            "name": str(result.get("name", "") or "").strip(),
            "style": str(result.get("style", "") or "").strip(),
            "scenes": result.get("scenes") or [],
            "recommended_colors": result.get("recommended_colors") or [],
            "description": str(result.get("description", "") or "").strip(),
            "tags": result.get("tags") or [],
            "model_used": model_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DesignAnalysis] Error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"款式分析失败: {e}")


@app.post("/api/user-designs", tags=["我的设计"])
async def create_user_design(payload: UserDesignCreateRequest):
    """保存一个用户款式（上传/AI生成/图库）。"""
    if not payload.client_id:
        raise HTTPException(status_code=400, detail="缺少 client_id")

    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")

    # 解析图片：data URL 落盘，或复用已有 url
    image_url = None
    if payload.image_data:
        try:
            raw = payload.image_data
            if "," in raw and raw.strip().startswith("data:"):
                raw = raw.split(",", 1)[1]
            img_bytes = base64.b64decode(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="image_data 不是有效的 base64")
        import uuid
        fname = f"{uuid.uuid4().hex}.jpg"
        (USER_DESIGNS_DIR / fname).write_bytes(img_bytes)
        image_url = f"/user_designs/{fname}"
    elif payload.image_url:
        image_url = payload.image_url
    else:
        raise HTTPException(status_code=400, detail="缺少图片（image_data 或 image_url）")

    source = payload.source if payload.source in ("upload", "ai", "gallery") else "upload"

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_designs (
                  client_id, name, image_url, source,
                  style, scenes, recommended_colors, description, tags, design_id, updated_at
                ) VALUES (
                  $1, $2, $3, $4,
                  $5, $6::jsonb, $7::jsonb, $8, $9::jsonb, $10, now()
                )
                RETURNING *
                """,
                payload.client_id,
                (payload.name or "我的设计").strip() or "我的设计",
                image_url,
                source,
                payload.style,
                json.dumps(payload.scenes or []),
                json.dumps(payload.recommended_colors or []),
                payload.description,
                json.dumps(payload.tags or []),
                payload.design_id,
            )
        return {"success": True, "design": _user_design_row_to_payload(row)}
    except Exception as e:
        print(f"[UserDesign] create failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user-designs", tags=["我的设计"])
async def list_user_designs(client_id: str):
    """获取某用户的全部款式。"""
    if not client_id:
        raise HTTPException(status_code=400, detail="缺少 client_id")
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM user_designs WHERE client_id = $1 ORDER BY created_at DESC",
                client_id,
            )
        return {"success": True, "designs": [_user_design_row_to_payload(r) for r in rows]}
    except Exception as e:
        print(f"[UserDesign] list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/user-designs/{design_id}", tags=["我的设计"])
async def update_user_design(design_id: int, payload: UserDesignUpdateRequest, client_id: str):
    """编辑用户款式（仅更新传入的字段）。"""
    if not client_id:
        raise HTTPException(status_code=400, detail="缺少 client_id")
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")

    sets = []
    values = []
    idx = 1
    simple_fields = {"name": payload.name, "style": payload.style, "description": payload.description}
    for col, val in simple_fields.items():
        if val is not None:
            sets.append(f"{col} = ${idx}")
            values.append(val)
            idx += 1
    jsonb_fields = {
        "scenes": payload.scenes,
        "recommended_colors": payload.recommended_colors,
        "tags": payload.tags,
    }
    for col, val in jsonb_fields.items():
        if val is not None:
            sets.append(f"{col} = ${idx}::jsonb")
            values.append(json.dumps(val))
            idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    sets.append("updated_at = now()")
    values.append(design_id)
    id_pos = idx
    idx += 1
    values.append(client_id)
    cid_pos = idx

    query = f"UPDATE user_designs SET {', '.join(sets)} WHERE id = ${id_pos} AND client_id = ${cid_pos} RETURNING *"
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
        if row is None:
            raise HTTPException(status_code=404, detail="款式不存在或无权限")
        return {"success": True, "design": _user_design_row_to_payload(row)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[UserDesign] update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/user-designs/{design_id}", tags=["我的设计"])
async def delete_user_design(design_id: int, client_id: str):
    """删除用户款式（并尽力清理本地图片文件）。"""
    if not client_id:
        raise HTTPException(status_code=400, detail="缺少 client_id")
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM user_designs WHERE id = $1 AND client_id = $2 RETURNING image_url",
                design_id, client_id,
            )
        if row is None:
            raise HTTPException(status_code=404, detail="款式不存在或无权限")
        image_url = row["image_url"]
        if image_url and image_url.startswith("/user_designs/"):
            try:
                (USER_DESIGNS_DIR / image_url.split("/user_designs/", 1)[1]).unlink(missing_ok=True)
            except Exception:
                pass
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[UserDesign] delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 账号系统 =====
@app.post("/api/auth/register", tags=["账号"])
async def auth_register(payload: AuthRequest):
    username = (payload.username or "").strip()
    password = payload.password or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 位")

    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")

    import asyncpg
    salt = _new_salt()
    pwhash = _hash_password(password, salt)
    client_key = _new_client_key()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO accounts (username, password_hash, salt, client_key)
                VALUES ($1, $2, $3, $4)
                RETURNING client_key, username
                """,
                username, pwhash, salt, client_key,
            )
        return {"success": True, "client_id": row["client_key"], "username": row["username"]}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="用户名已存在")
    except Exception as e:
        print(f"[Auth] register failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/login", tags=["账号"])
async def auth_login(payload: AuthRequest):
    username = (payload.username or "").strip()
    password = payload.password or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT password_hash, salt, client_key, username FROM accounts WHERE username = $1",
                username,
            )
        if row is None or not _verify_password(password, row["salt"], row["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {"success": True, "client_id": row["client_key"], "username": row["username"]}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] login failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 收藏（服务端）=====
@app.get("/api/wishlist", tags=["收藏"])
async def list_wishlist(client_id: str):
    if not client_id:
        raise HTTPException(status_code=400, detail="缺少 client_id")
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, emoji, price, bg, image, design_id FROM user_wishlist WHERE client_id = $1 ORDER BY created_at DESC",
                client_id,
            )
        return {"success": True, "items": [dict(r) for r in rows]}
    except Exception as e:
        print(f"[Wishlist] list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/wishlist", tags=["收藏"])
async def add_wishlist(payload: WishlistItemRequest):
    if not payload.client_id or not payload.name:
        raise HTTPException(status_code=400, detail="缺少 client_id 或 name")
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_wishlist (client_id, name, emoji, price, bg, image, design_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (client_id, name) DO UPDATE SET
                  emoji = EXCLUDED.emoji, price = EXCLUDED.price,
                  bg = EXCLUDED.bg, image = EXCLUDED.image, design_id = EXCLUDED.design_id
                RETURNING name, emoji, price, bg, image, design_id
                """,
                payload.client_id, payload.name, payload.emoji,
                payload.price, payload.bg, payload.image, payload.design_id,
            )
        return {"success": True, "item": dict(row)}
    except Exception as e:
        print(f"[Wishlist] add failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/wishlist", tags=["收藏"])
async def delete_wishlist(client_id: str, name: str):
    if not client_id or not name:
        raise HTTPException(status_code=400, detail="缺少 client_id 或 name")
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接未就绪")
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_wishlist WHERE client_id = $1 AND name = $2",
                client_id, name,
            )
        return {"success": True}
    except Exception as e:
        print(f"[Wishlist] delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 检测流程辅助函数（支持进度回调）=====
def _encode_img_to_base64(img_cv2) -> str:
    """将 OpenCV 图片编码为 base64 data URL。"""
    _, buf = cv2.imencode(".jpg", img_cv2)
    img_base64 = base64.b64encode(buf).decode("utf-8")
    return f"data:image/jpeg;base64,{img_base64}"


async def detect_nails_with_progress(
    img_bytes: bytes,
    progress_callback: Optional[Callable[[str, Optional[str]], None]] = None
) -> Dict:
    """执行指甲检测，支持进度回调与中间图片推送。

    Args:
        img_bytes: 图片二进制数据
        progress_callback: 进度回调函数 (message: str, image_data: Optional[str]) -> None

    Returns:
        检测结果字典
    """
    try:
        # 解码图片
        if progress_callback:
            progress_callback("加载图片...")
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return {"success": False, "message": "图片读取失败"}

        h, w = img.shape[:2]

        # 步骤 1: YOLO 分割
        nails = nail_seg.segment_nails(img)
        nails = [n for n in nails if n["finger_idx"] >= 0]

        if not nails:
            return {"success": False, "message": "未检测到指甲"}

        print(f"[DetectNails] 使用 YOLO 检测到 {len(nails)} 个指甲")

        # 推送分割完成消息（不包含图片）
        if progress_callback:
            progress_callback("✓ 指甲分割完成", None)

        # 步骤 2: 计算指甲方向（PCA）
        nails_bounds = []
        for idx, nail in enumerate(nails):
            mask = nail["mask"]
            ys, xs = np.where(mask)
            if len(xs) == 0:
                continue

            # 计算掩码的中心
            cx, cy = xs.mean(), ys.mean()

            # 用 PCA 找掩码的主轴方向
            pts = np.column_stack([xs, ys]).astype(np.float32)
            pts_centered = pts - np.array([cx, cy])

            if len(pts) > 1:
                cov = np.cov(pts_centered.T)
                eigenvalues, eigenvectors = np.linalg.eig(cov)
                main_axis = eigenvectors[:, np.argmax(eigenvalues)]
                perp_axis = eigenvectors[:, np.argmin(eigenvalues)]
            else:
                main_axis = np.array([0, 1])
                perp_axis = np.array([1, 0])

            # 投影计算
            proj_main = pts_centered @ main_axis
            proj_perp = pts_centered @ perp_axis

            # 计算长宽
            length = np.max(proj_main) - np.min(proj_main)
            width = np.max(proj_perp) - np.min(proj_perp)

            if width > length:
                length, width = width, length
                main_axis, perp_axis = perp_axis, main_axis

            # 角度计算
            angle = np.degrees(np.arctan2(main_axis[1], main_axis[0]))

            # 转换为相对坐标
            cx_rel = cx / w
            cy_rel = cy / h
            width_rel = width / w
            height_rel = length / h

            nails_bounds.append({
                "id": nail["finger_idx"],
                "cx": cx_rel,
                "cy": cy_rel,
                "width": width_rel,
                "height": height_rel,
                "angle": angle
            })

        # 推送方向识别完成消息（不包含图片）
        if progress_callback:
            progress_callback("✓ 方向识别完成", None)

        # 步骤 3: 绘制彩色掩码覆盖
        img_with_masks = img.copy()
        colors = [
            (0, 0, 255),      # 红色 (BGR)
            (0, 165, 255),    # 橙色 (BGR)
            (0, 255, 255),    # 青色 (BGR)
            (255, 0, 255),    # 洋红色 (BGR)
            (0, 255, 0),      # 绿色 (BGR)
        ]

        for idx, nail in enumerate(nails):
            mask = nail["mask"]
            color = colors[idx % len(colors)]
            mask_count = int(np.sum(mask))

            if mask_count > 0:
                for i in range(3):
                    img_with_masks[mask, i] = color[i]

        # 编码最终图片
        final_img_data = _encode_img_to_base64(img_with_masks)
        if progress_callback:
            progress_callback("✓ 预览生成完成", None)

        return {
            "success": True,
            "image_data": final_img_data,
            "nails_bounds": nails_bounds,
            "message": f"检测到 {len(nails_bounds)} 个指甲"
        }

    except Exception as e:
        print(f"[DetectNails] 错误: {e}")
        return {"success": False, "message": f"检测失败: {str(e)}"}


@app.post("/api/detect-nails-preview", tags=["美甲检测"])
async def detect_nails_preview_endpoint(image: UploadFile = File(...)):
    """预检测：返回检测结果和进度消息。"""
    try:
        import base64

        contents = await image.read()
        img = _preprocess_image(contents, image.filename)

        if img is None:
            return {"success": False, "message": "图片读取失败", "progress": []}

        h, w = img.shape[:2]
        progress = []

        # 使用 YOLO 分割
        progress.append("✓ 指甲分割完成")
        nails = nail_seg.segment_nails(img)
        nails = [n for n in nails if n["finger_idx"] >= 0]

        if not nails:
            return {"success": False, "message": "未检测到指甲", "progress": progress}

        # 计算指甲边界（方向识别）
        progress.append("✓ 方向识别完成")
        nails_bounds = []
        for nail in nails:
            mask = nail["mask"]
            ys, xs = np.where(mask)
            if len(xs) == 0:
                continue

            cx, cy = xs.mean(), ys.mean()
            pts = np.column_stack([xs, ys]).astype(np.float32)
            pts_centered = pts - np.array([cx, cy])

            if len(pts) > 1:
                cov = np.cov(pts_centered.T)
                eigenvalues, eigenvectors = np.linalg.eig(cov)
                main_axis = eigenvectors[:, np.argmax(eigenvalues)]
                perp_axis = eigenvectors[:, np.argmin(eigenvalues)]
            else:
                main_axis = np.array([0, 1])
                perp_axis = np.array([1, 0])

            proj_main = pts_centered @ main_axis
            proj_perp = pts_centered @ perp_axis

            length = np.max(proj_main) - np.min(proj_main)
            width = np.max(proj_perp) - np.min(proj_perp)

            if width > length:
                length, width = width, length
                main_axis, perp_axis = perp_axis, main_axis

            angle = np.degrees(np.arctan2(main_axis[1], main_axis[0]))

            nails_bounds.append({
                "id": nail["finger_idx"],
                "cx": cx / w,
                "cy": cy / h,
                "width": width / w,
                "height": length / h,
                "angle": angle
            })

        # 生成预览图片（带彩色掩码）
        progress.append("✓ 预览生成完成")
        img_with_masks = img.copy()
        colors = [
            (0, 0, 255),      # 红色
            (0, 165, 255),    # 橙色
            (0, 255, 255),    # 青色
            (255, 0, 255),    # 洋红色
            (0, 255, 0),      # 绿色
        ]

        for idx, nail in enumerate(nails):
            mask = nail["mask"]
            color = colors[idx % len(colors)]
            mask_count = int(np.sum(mask))

            if mask_count > 0:
                for i in range(3):
                    img_with_masks[mask, i] = color[i]

        _, buf = cv2.imencode(".jpg", img_with_masks)
        img_base64 = base64.b64encode(buf).decode("utf-8")
        img_data_url = f"data:image/jpeg;base64,{img_base64}"

        return {
            "success": True,
            "image_data": img_data_url,
            "nails_bounds": nails_bounds,
            "message": f"检测到 {len(nails_bounds)} 个指甲",
            "progress": progress
        }

    except Exception as e:
        print(f"[DetectNailsPreview] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": "检测失败"}


@app.post("/api/detect-nails-stream", tags=["美甲检测"])
async def detect_nails_stream_endpoint(image: UploadFile = File(...)):
    """实时检测流：使用 SSE 推送进度文字。"""

    async def event_generator():
        try:
            contents = await image.read()
            img = _preprocess_image(contents, image.filename)
            messages = []

            def progress_callback(msg: str, img_data: Optional[str] = None):
                messages.append(msg)

            # 将预处理后的图片重新编码为高质量 JPG 字节
            if img is not None:
                success, preprocessed_bytes = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                contents = preprocessed_bytes.tobytes() if success else contents

            result = await detect_nails_with_progress(contents, progress_callback)

            # 推送所有进度消息
            for msg in messages:
                yield f"data: {json.dumps({'message': msg})}\n\n"

            # 推送最终结果
            yield f"data: {json.dumps({'result': result})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            print(f"[DetectNailsStream] 错误: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


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
        img = _preprocess_image(contents, image.filename)

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
        img = _preprocess_image(contents, image.filename)

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
        img = _preprocess_image(contents, image.filename)

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
        try:
            nail_info = json.loads(response_text)
        except json.JSONDecodeError:
            import re as _re
            m = _re.search(r'\{.*\}', response_text, _re.DOTALL)
            if m:
                nail_info = json.loads(m.group(0))
            else:
                nail_info = {"nails": []}

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


@app.get("/api/ops/modelscope-status", tags=["智能运营"])
async def get_ops_modelscope_status():
    return get_modelscope_config_status()


@app.post("/api/ops/assistant", tags=["智能运营"])
async def generate_ops_assistant_endpoint(payload: OpsAssistantRequest):
    return generate_ops_assistant(payload.model_dump())


@app.get("/api/design-image/{design_id}", tags=["款式库"])
async def get_design_image(design_id: str):
    """获取款式详细设计图（去除手部背景的高清图）"""
    try:
        design = _find_design(design_id, None)

        # 优先使用detailed_image（详细设计图），回退到image
        image_field = "detailed_image" if "detailed_image" in design else "image"
        image_path = design.get(image_field)

        if not image_path:
            print(f"[GetDesignImage] {design_id} 没有{image_field}")
            return {"success": False, "message": "款式图不存在"}

        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(image_path):
            image_path = os.path.join(
                Path(__file__).resolve().parent.parent,
                image_path
            )

        print(f"[GetDesignImage] 获取{image_field}: {image_path}")

        if os.path.exists(image_path):
            return FileResponse(image_path, media_type="image/jpeg")
        else:
            print(f"[GetDesignImage] 文件不存在: {image_path}")
            return {"success": False, "message": f"文件不存在: {image_path}"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[GetDesignImage] 错误: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


@app.post("/api/enhance-nail-tryon", tags=["AI试戴增强"])
async def enhance_nail_tryon_endpoint(
    hand_image: UploadFile = File(...),
    design_image: UploadFile = File(...),
    design_name: str = "美甲款式"
):
    """使用Qwen-Image-Edit增强美甲试戴效果

    Args:
        hand_image: 用户手部照片
        design_image: 美甲款式详细图
        design_name: 美甲款式名称
    """
    try:
        import tempfile

        # 保存上传的文件到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as hand_tmp:
            hand_contents = await hand_image.read()
            hand_tmp.write(hand_contents)
            hand_tmp_path = hand_tmp.name

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as design_tmp:
            design_contents = await design_image.read()
            design_tmp.write(design_contents)
            design_tmp_path = design_tmp.name

        try:
            # 调用增强器
            print(f"[TryOnEnhance] 开始增强美甲效果: {design_name}")
            result = await enhance_nail_tryon(
                hand_image_path=hand_tmp_path,
                design_image_path=design_tmp_path,
                design_name=design_name
            )

            if result and isinstance(result, dict):
                # 直接返回后端的响应
                return result
            else:
                return {
                    "success": False,
                    "message": "美甲增强失败"
                }
        finally:
            # 清理临时文件
            import os
            try:
                os.unlink(hand_tmp_path)
                os.unlink(design_tmp_path)
            except:
                pass

    except Exception as e:
        print(f"[TryOnEnhance] 异常: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"增强失败: {str(e)}"}


@app.post("/api/generate-mold-from-inspiration", tags=["灵感试戴"])
async def generate_mold_endpoint(image: UploadFile = File(...)):
    """从灵感图生成美甲模具，返回design_id供试戴使用"""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(await image.read())
            tmp_path = tmp.name

        print(f"[InspTryOn] 收到灵感图，开始生成模具...")
        result = generate_mold_from_inspiration(tmp_path)

        try:
            os.unlink(tmp_path)
        except:
            pass

        if not result:
            return {"success": False, "message": "模具生成失败，请重试"}

        return {
            "success": True,
            "design_id": result["design_id"],
            "template_base64": result["template_base64"],
            "design_description": result["design_description"],
            "nail_count": result["nail_count"],
            "message": f"模具生成成功，识别到{result['nail_count']}个指甲"
        }

    except Exception as e:
        print(f"[InspTryOn] 异常: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}


@app.post("/api/analyze-tryon", tags=["AI分析"])
async def analyze_tryon_endpoint(
    image: UploadFile = File(...),
    design_id: Optional[str] = None,
    design_image: Optional[str] = None,
):
    """独立的AI分析接口，供试戴完成后异步调用"""
    try:
        design = _find_design(design_id, design_image)

        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "message": "图片读取失败"}

        # 获取款式图路径
        design_image_path = None
        try:
            if "image" in design and design["image"]:
                p = design["image"]
                if not os.path.isabs(p):
                    p = os.path.join(Path(__file__).resolve().parent.parent, p)
                if os.path.exists(p):
                    design_image_path = p
        except Exception:
            pass

        print(f"[AnalyzeTryOn] 开始AI分析: {design.get('name', '当前款式')}")
        analysis = analyze_with_vision(
            hand_image=img,
            design_image_path=design_image_path,
            design_name=design.get("name", "当前款式")
        )
        if analysis is None:
            return {"success": False, "message": "AI分析服务暂时不可用"}
        print(f"[AnalyzeTryOn] AI分析完成: 匹配度 {analysis.get('confidence', 0):.0%}")
        return {"success": True, "analysis": analysis}

    except Exception as e:
        print(f"[AnalyzeTryOn] 异常: {e}")
        return {"success": False, "message": str(e)}


@app.get("/api/douyin/trending-nails", tags=["Douyin"])
def get_douyin_trending_endpoint():
    try:
        return get_douyin_trending(DESIGNS)
    except DouyinStatsError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/bilibili/trending-nails", tags=["Bilibili"])
def get_bilibili_trending_endpoint():
    try:
        return get_bilibili_trending(DESIGNS)
    except BilibiliStatsError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/douyin/test-url", tags=["Douyin"])
def test_douyin_public_url(url: str):
    try:
        return inspect_public_douyin_url(url)
    except DouyinStatsError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/rednote/trending-nails", tags=["RedNote"])
def get_rednote_trending_endpoint():
    try:
        return get_rednote_trending(DESIGNS)
    except RedNoteStatsError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/xhs/trending-nails", tags=["RedNote"])
async def get_xhs_trending_endpoint():
    return get_rednote_trending_endpoint()


@app.get("/api/rednote/test-url", tags=["RedNote"])
def test_rednote_public_url(url: str):
    try:
        return inspect_public_rednote_url(url)
    except RedNoteStatsError as e:
        raise HTTPException(status_code=503, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

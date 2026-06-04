"""ModelScope-powered operations assistant for the intelligent ops dashboard."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency is listed in requirements
    OpenAI = None


load_dotenv()

MODELSCOPE_API_KEY = (
    os.getenv("MODELSCOPE_TOKEN", "").strip()
    or os.getenv("MODELSCOPE_API_KEY", "").strip()
)
MODELSCOPE_BASE_URL = os.getenv(
    "MODELSCOPE_BASE_URL",
    "https://api-inference.modelscope.cn/v1",
).strip()
MODELSCOPE_OPS_MODEL = os.getenv(
    "MODELSCOPE_OPS_MODEL",
    os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen3.5-35B-A3B"),
).strip()


def get_modelscope_config_status() -> Dict[str, Any]:
    return {
        "configured": bool(MODELSCOPE_API_KEY and OpenAI),
        "base_url": MODELSCOPE_BASE_URL,
        "model": MODELSCOPE_OPS_MODEL,
    }


def _client() -> Any:
    if not MODELSCOPE_API_KEY or OpenAI is None:
        return None
    return OpenAI(base_url=MODELSCOPE_BASE_URL, api_key=MODELSCOPE_API_KEY)


def _compact_items(items: List[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    compact = []
    for item in items[:limit]:
        stats = item.get("stats") or item.get("rawStats") or {}
        compact.append({
            "rank": item.get("rank"),
            "id": item.get("id"),
            "name": item.get("name"),
            "tags": item.get("tags", []),
            "platform": item.get("platformName"),
            "trendSource": item.get("trendSource"),
            "heatScore": item.get("heatScore"),
            "view": stats.get("view") or stats.get("viewCount"),
            "like": stats.get("like") or stats.get("likeCount"),
            "collect": stats.get("collect") or stats.get("collectCount"),
            "comment": stats.get("comment") or stats.get("commentCount"),
            "share": stats.get("share") or stats.get("shareCount"),
            "engagementRate": stats.get("engagementRate"),
            "collectRate": stats.get("collectRate"),
        })
    return compact


def _extract_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
    raise ValueError("Model response did not contain JSON")


def _fallback(payload: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    items = payload.get("items") or []
    summary = payload.get("summary") or {}
    top = (summary.get("top") or (items[0] if items else {})) or {}
    second = items[1] if len(items) > 1 else top
    risk = next((item for item in items if item.get("trendSource") == "local-fallback"), None)
    risk = risk or (items[-1] if items else {})
    top_name = top.get("name", "当前热度最高款")
    second_name = second.get("name", top_name)
    risk_name = risk.get("name", "数据不足款式")

    return {
        "success": False,
        "source": "local-fallback",
        "model": MODELSCOPE_OPS_MODEL,
        "reason": reason,
        "headline": "OpenClaw-ready 运营助手",
        "status": "LOCAL",
        "lines": [
            {
                "label": "实时监控",
                "text": f"当前监控 {summary.get('liveCount', len(items))}/{summary.get('styleTotal', len(items))} 款，优先补齐缺少公开视频或授权数据的款式。",
            },
            {
                "label": "趋势分析",
                "text": f"今日主推建议锁定「{top_name}」，并用「{second_name}」做同风格组合推荐。",
            },
            {
                "label": "策略生成",
                "text": f"首页热门位、详情页视频入口和 AI 试戴默认款都先承接「{top_name}」。",
            },
            {
                "label": "效率提升",
                "text": f"优先复盘「{risk_name}」的数据缺口、封面卖点和前三秒内容表达。",
            },
        ],
        "actions": [
            {"type": "promote", "target": top.get("id"), "title": f"主推「{top_name}」"},
            {"type": "content", "target": top.get("id"), "title": "生成小红书/抖音文案"},
            {"type": "audit", "target": risk.get("id"), "title": f"复盘「{risk_name}」"},
        ],
    }


def generate_ops_assistant(payload: Dict[str, Any]) -> Dict[str, Any]:
    client = _client()
    if client is None:
        return _fallback(payload, "ModelScope API key or OpenAI client is unavailable.")

    compact_payload = {
        "items": _compact_items(payload.get("items") or []),
        "summary": payload.get("summary") or {},
        "trendBuckets": payload.get("trendBuckets") or [],
    }
    system_prompt = (
        "你是美甲品牌的智能运营总监，也是 OpenClaw 风格的工具编排助手。"
        "你只输出 JSON，不要输出 Markdown。你的建议要能直接用于运营看板。"
    )
    user_prompt = {
        "task": "基于款式热度、平台互动和风险信号，生成今日智能运营建议。",
        "requirements": [
            "使用简体中文",
            "给出实时监控、趋势分析、策略生成、效率提升四行建议",
            "给出 3-5 个可执行动作",
            "动作类型只能是 promote, copywriting, content, audit, data, tryon",
            "不要编造不存在的平台数据",
        ],
        "output_schema": {
            "success": True,
            "source": "modelscope",
            "headline": "ModelScope 智能运营助手",
            "status": "AI",
            "lines": [
                {"label": "实时监控", "text": "一句话"},
                {"label": "趋势分析", "text": "一句话"},
                {"label": "策略生成", "text": "一句话"},
                {"label": "效率提升", "text": "一句话"},
            ],
            "actions": [
                {"type": "promote", "target": "design_id", "title": "动作标题"}
            ],
        },
        "data": compact_payload,
    }

    try:
        response = client.chat.completions.create(
            model=MODELSCOPE_OPS_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
            ],
            temperature=0.35,
            max_tokens=900,
        )
        text = response.choices[0].message.content or ""
        data = _extract_json(text)
        data["success"] = True
        data["source"] = data.get("source") or "modelscope"
        data["model"] = MODELSCOPE_OPS_MODEL
        return data
    except Exception as exc:
        return _fallback(payload, str(exc))

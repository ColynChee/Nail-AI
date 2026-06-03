"""Bilibili public video stats provider.

This uses seeded public Bilibili videos and refreshes their public stats from
the official web-interface view endpoint. It avoids Bilibili search pages,
which often require captcha, but the video stats endpoint is public for a known
BVID/AID.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BACKEND = Path(__file__).resolve().parent
DEFAULT_SOURCES_FILE = BACKEND / "bilibili_sources.json"

_CACHE: Dict[str, Any] = {
    "expires_at": 0.0,
    "payload": None,
}


class BilibiliStatsError(RuntimeError):
    """Raised when Bilibili public data cannot be read."""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _to_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return 0.0
    text = str(value).strip().lower()
    if not text:
        return 0.0
    multiplier = 1.0
    if "万" in text or "w" in text:
        multiplier = 10000.0
    elif "k" in text:
        multiplier = 1000.0
    numeric = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    try:
        return float(numeric) * multiplier
    except ValueError:
        return 0.0


def _first(item: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return default


def _format_heat(score: float) -> str:
    if score >= 10000:
        return f"{score / 10000:.1f}w 实时"
    if score >= 1000:
        return f"{score / 1000:.1f}k 实时"
    return f"{round(score)} 实时"


def _fallback_heat_from_local_design(local: Dict[str, Any]) -> float:
    heat = _to_number(local.get("heat"))
    if heat:
        return heat
    rank = _to_number(local.get("rank"))
    if rank:
        return max(1000.0, 30000.0 - rank * 1000.0)
    return 0.0


def _extract_video_id(source: Dict[str, Any]) -> Tuple[str, str]:
    explicit_bvid = str(source.get("bvid") or source.get("BVID") or "").strip()
    explicit_aid = str(source.get("aid") or source.get("AID") or "").strip()
    if explicit_bvid:
        return "bvid", explicit_bvid
    if explicit_aid:
        return "aid", explicit_aid

    url = str(source.get("url") or source.get("bilibiliUrl") or "").strip()
    bvid_match = re.search(r"(BV[0-9A-Za-z]{10})", url)
    if bvid_match:
        return "bvid", bvid_match.group(1)
    aid_match = re.search(r"/video/av([0-9]+)", url)
    if aid_match:
        return "aid", aid_match.group(1)
    if url.isdigit():
        return "aid", url
    raise BilibiliStatsError(f"Could not find Bilibili video id in source: {url or source}")


def _fetch_video_detail(source: Dict[str, Any]) -> Dict[str, Any]:
    kind, video_id = _extract_video_id(source)
    timeout = _env_int("BILIBILI_TIMEOUT_SECONDS", 6)
    api = "https://api.bilibili.com/x/web-interface/view?" + urllib.parse.urlencode({kind: video_id})
    request = urllib.request.Request(
        api,
        headers={
            "User-Agent": "Mozilla/5.0 NailAIStudentProject/1.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.bilibili.com/",
        },
        method="GET",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(response.read().decode(charset, errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BilibiliStatsError(f"Could not fetch Bilibili video stats: {exc}") from exc

    if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        raise BilibiliStatsError(f"Bilibili API returned {payload.get('code')}: {payload.get('message')}")
    return payload["data"]


def _heat_score(stats: Dict[str, Any]) -> float:
    views = _to_number(stats.get("view"))
    likes = _to_number(stats.get("like"))
    favorites = _to_number(stats.get("favorite"))
    replies = _to_number(stats.get("reply"))
    danmaku = _to_number(stats.get("danmaku"))
    coins = _to_number(stats.get("coin"))
    shares = _to_number(stats.get("share"))
    return views + likes * 6 + favorites * 8 + replies * 10 + danmaku * 3 + coins * 6 + shares * 12


def _read_sources() -> List[Dict[str, Any]]:
    source_file = Path(os.getenv("BILIBILI_SOURCES_FILE", str(DEFAULT_SOURCES_FILE))).expanduser()
    if not source_file.exists():
        return []
    try:
        payload = json.loads(source_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BilibiliStatsError(f"Could not read BILIBILI_SOURCES_FILE: {exc}") from exc
    rows = payload.get("sources", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise BilibiliStatsError("BILIBILI_SOURCES_FILE must be an array or an object with sources[].")
    return [row for row in rows if isinstance(row, dict)]


def _find_local_design(item: Dict[str, Any], designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    design_id = _first(item, ["design_id", "designId", "id"], "")
    if design_id:
        match = next((d for d in designs if d.get("id") == design_id), None)
        if match:
            return match
    name = str(_first(item, ["localName", "name", "keyword"], "")).strip()
    if name:
        return next(
            (
                d for d in designs
                if d.get("name") == name or name in str(d.get("name", "")) or str(d.get("name", "")) in name
            ),
            {},
        )
    return {}


def _normalize_source(source: Dict[str, Any], index: int, designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    local = _find_local_design(source, designs)
    try:
        detail = _fetch_video_detail(source)
        stat = detail.get("stat") or {}
        score = _heat_score(stat)
        bvid = detail.get("bvid") or source.get("bvid") or ""
        url = f"https://www.bilibili.com/video/{bvid}" if bvid else str(source.get("url") or "")
        return {
            "rank": index + 1,
            "id": local.get("id") or _first(source, ["design_id", "designId", "id"], ""),
            "name": local.get("name") or source.get("name") or detail.get("title") or "B站美甲视频",
            "sub": source.get("sub") or detail.get("title") or "B站公开视频实时统计",
            "price": source.get("price") or local.get("price", "到店咨询"),
            "heat": _format_heat(score),
            "heatScore": score,
            "emoji": source.get("emoji") or local.get("emoji", ""),
            "bg": source.get("bg") or local.get("bg", "#FFF0F5"),
            "image": local.get("image") or detail.get("pic") or "",
            "detailed_image": local.get("detailed_image", ""),
            "platformName": "B站",
            "platformUrl": url,
            "bilibili": url,
            "douyin": url,
            "xhs": url,
            "rawStats": {
                "viewCount": int(_to_number(stat.get("view"))),
                "likeCount": int(_to_number(stat.get("like"))),
                "collectCount": int(_to_number(stat.get("favorite"))),
                "commentCount": int(_to_number(stat.get("reply"))),
                "shareCount": int(_to_number(stat.get("share"))),
                "danmakuCount": int(_to_number(stat.get("danmaku"))),
                "coinCount": int(_to_number(stat.get("coin"))),
            },
            "crawlerStatus": "ok",
            "trendSource": "bilibili-public",
            "sourceKind": "seeded-video",
        }
    except BilibiliStatsError as exc:
        score = _fallback_heat_from_local_design(local)
        return {
            "rank": index + 1,
            "id": local.get("id") or _first(source, ["design_id", "designId", "id"], ""),
            "name": local.get("name") or source.get("name") or "B站美甲视频",
            "sub": "B站公开视频暂不可读",
            "price": source.get("price") or local.get("price", "到店咨询"),
            "heat": f"{local.get('heat', '0')} 参考",
            "heatScore": score,
            "emoji": source.get("emoji") or local.get("emoji", ""),
            "bg": source.get("bg") or local.get("bg", "#FFF0F5"),
            "image": local.get("image", ""),
            "detailed_image": local.get("detailed_image", ""),
            "platformName": "B站",
            "platformUrl": str(source.get("url") or ""),
            "bilibili": str(source.get("url") or ""),
            "rawStats": {},
            "crawlerStatus": "error",
            "crawlError": str(exc),
            "trendSource": "local-fallback",
            "sourceKind": "seeded-video",
        }


def _local_fallback_row(design: Dict[str, Any], index: int) -> Dict[str, Any]:
    score = _fallback_heat_from_local_design(design)
    return {
        "rank": index + 1,
        "id": design.get("id", ""),
        "name": design.get("name", "本地款式"),
        "sub": "暂无关联 B站公开视频",
        "price": design.get("price", "到店咨询"),
        "heat": f"{design.get('heat', '0')} 参考",
        "heatScore": score,
        "emoji": design.get("emoji", ""),
        "bg": design.get("bg", "#FFF0F5"),
        "image": design.get("image", ""),
        "detailed_image": design.get("detailed_image", ""),
        "platformName": "B站",
        "platformUrl": "",
        "rawStats": {},
        "crawlerStatus": "unconfigured",
        "trendSource": "local-fallback",
        "sourceKind": "local",
    }


def get_bilibili_trending(designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    cache_seconds = _env_int("BILIBILI_STATS_CACHE_SECONDS", 300)
    now = time.time()
    if _CACHE["payload"] is not None and now < _CACHE["expires_at"]:
        return _CACHE["payload"]

    sources = _read_sources()
    max_workers = max(1, min(_env_int("BILIBILI_MAX_WORKERS", 10), 10))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        items = list(executor.map(lambda pair: _normalize_source(pair[1], pair[0], designs), enumerate(sources)))

    seen_ids = {item.get("id") for item in items if item.get("id")}
    for design in designs:
        if design.get("id") not in seen_ids:
            items.append(_local_fallback_row(design, len(items)))

    items = sorted(items, key=lambda row: row.get("heatScore", 0), reverse=True)
    items = [{**item, "rank": index + 1} for index, item in enumerate(items)]
    result = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "bilibili-live",
        "message": "Bilibili public seeded videos refreshed from live public video stats.",
        "items": items,
    }
    _CACHE["payload"] = result
    _CACHE["expires_at"] = now + max(cache_seconds, 0)
    return result

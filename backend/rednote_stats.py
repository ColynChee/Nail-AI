"""RedNote/Xiaohongshu trending stats provider.

This module deliberately does not scrape RedNote pages. For accurate stats,
point REDNOTE_STATS_API_URL at an authorized data endpoint, or place an exported
JSON payload at REDNOTE_STATS_FILE.
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
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BACKEND = Path(__file__).resolve().parent
DEFAULT_STATS_FILE = BACKEND / "rednote_stats.json"
DEFAULT_SOURCES_FILE = BACKEND / "rednote_sources.json"

_CACHE: Dict[str, Any] = {
    "expires_at": 0.0,
    "payload": None,
}


class RedNoteStatsError(RuntimeError):
    """Raised when no accurate RedNote data source can be read."""


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
    if "w" in text or "万" in text:
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


def _heat_score(item: Dict[str, Any]) -> float:
    explicit = _first(item, ["heatScore", "heat_score"])
    if explicit is not None:
        return _to_number(explicit)

    views = _to_number(_first(item, ["viewCount", "views", "readCount", "view_count", "read_count"]))
    likes = _to_number(_first(item, ["likeCount", "likes", "like_count"]))
    collects = _to_number(_first(item, ["collectCount", "collects", "favorites", "collect_count"]))
    comments = _to_number(_first(item, ["commentCount", "comments", "comment_count"]))
    notes = _to_number(_first(item, ["noteCount", "notes", "note_count"]))
    return views + likes * 6 + collects * 8 + comments * 10 + notes * 12


def _format_heat(score: float) -> str:
    if score >= 10000:
        return f"{score / 10000:.1f}w 实时"
    if score >= 1000:
        return f"{score / 1000:.1f}k 实时"
    return f"{round(score)} 实时"


def _normalize_image_url(url: Any) -> str:
    text = str(url or "").strip()
    if text.startswith("//"):
        return f"https:{text}"
    return text


def _fallback_heat_from_local_design(local: Dict[str, Any]) -> float:
    heat = _to_number(local.get("heat"))
    if heat:
        return heat
    rank = _to_number(local.get("rank"))
    if rank:
        return max(1000.0, 30000.0 - rank * 1000.0)
    return 0.0


def _is_allowed_public_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    allowed = [
        value.strip().lower()
        for value in os.getenv(
            "REDNOTE_ALLOWED_HOSTS",
            "xiaohongshu.com,www.xiaohongshu.com,xhslink.com,www.xhslink.com",
        ).split(",")
        if value.strip()
    ]
    host = host.lower()
    return any(host == item or host.endswith(f".{item}") for item in allowed)


def _fetch_public_html(url: str) -> str:
    if not _is_allowed_public_url(url):
        raise RedNoteStatsError(f"Public crawler URL is not allowed: {url}")

    timeout = _env_int("REDNOTE_PUBLIC_TIMEOUT_SECONDS", 3)
    max_bytes = _env_int("REDNOTE_PUBLIC_MAX_BYTES", 2_000_000)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NailAIStudentProject/1.0 public-url-fetcher",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        method="GET",
    )
    try:
        if os.getenv("REDNOTE_USE_SYSTEM_PROXY", "").strip().lower() in {"1", "true", "yes"}:
            opener = urllib.request.build_opener()
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise RedNoteStatsError(f"Public crawler response is larger than {max_bytes} bytes.")
            return body.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RedNoteStatsError(f"Could not fetch public RedNote URL: {exc}") from exc


def _meta_content(html: str, names: List[str]) -> str:
    for name in names:
        pattern = (
            r"<meta\s+[^>]*(?:property|name)=[\"']"
            + re.escape(name)
            + r"[\"'][^>]*content=[\"']([^\"']+)[\"'][^>]*>"
        )
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return unescape(match.group(1)).strip()

        reversed_pattern = (
            r"<meta\s+[^>]*content=[\"']([^\"']+)[\"'][^>]*(?:property|name)=[\"']"
            + re.escape(name)
            + r"[\"'][^>]*>"
        )
        match = re.search(reversed_pattern, html, flags=re.IGNORECASE)
        if match:
            return unescape(match.group(1)).strip()
    return ""


def _page_title(html: str) -> str:
    title = _meta_content(html, ["og:title", "twitter:title"])
    if title:
        return title
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return ""


def _jsonish_stat(text: str, keys: List[str]) -> float:
    escaped_quote = r'\\?"'
    key_pattern = "|".join(re.escape(key) for key in keys)
    pattern = (
        escaped_quote
        + rf"(?:{key_pattern})"
        + escaped_quote
        + r"\s*:\s*"
        + escaped_quote
        + r"?([0-9][0-9,.\s]*(?:万|w|W|k|K)?)"
    )
    values = [_to_number(match.group(1)) for match in re.finditer(pattern, text, flags=re.IGNORECASE)]
    return max(values) if values else 0.0


def _unescape_js_text(text: str) -> str:
    """Decode the layers commonly found in SPA-embedded JSON snippets."""
    previous = text
    for _ in range(2):
        current = unescape(previous)
        current = current.replace("\\u002F", "/").replace("\\/", "/").replace("\\n", " ")
        if "\\u" in current:
            try:
                current = bytes(current, "utf-8").decode("unicode_escape")
            except UnicodeDecodeError:
                pass
        if current == previous:
            break
        previous = current
    return previous


def _extract_note_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    for part in reversed(parts):
        if re.fullmatch(r"[0-9a-fA-F]{16,32}", part) or re.fullmatch(r"[A-Za-z0-9]{16,32}", part):
            return part
    return ""


def _contains_public_note_marker(html: str, url: str) -> bool:
    note_id = _extract_note_id(url)
    if note_id and note_id in html:
        return True
    markers = ["interactInfo", "likedCount", "collectedCount", "noteDetail", "noteData"]
    return any(marker in html for marker in markers)


def _label_stat(text: str, labels: List[str]) -> float:
    label_pattern = "|".join(re.escape(label) for label in labels)
    patterns = [
        rf"([0-9][0-9,.\s]*(?:万|w|W|k|K)?)\s*(?:{label_pattern})",
        rf"(?:{label_pattern})\s*[:：]?\s*([0-9][0-9,.\s]*(?:万|w|W|k|K)?)",
    ]
    values: List[float] = []
    for pattern in patterns:
        values.extend(_to_number(match.group(1)) for match in re.finditer(pattern, text, flags=re.IGNORECASE))
    return max(values) if values else 0.0


def _extract_public_stats(html: str) -> Dict[str, int]:
    text = _unescape_js_text(html)

    view_count = _jsonish_stat(text, [
        "viewCount", "view_count", "readCount", "read_count", "views", "viewNum", "readNum"
    ])
    like_count = _jsonish_stat(text, [
        "likeCount", "likedCount", "liked_count", "like_count", "likes", "likedNum", "likeNum"
    ])
    collect_count = _jsonish_stat(text, [
        "collectCount", "collectedCount", "collected_count", "collect_count",
        "collects", "favorites", "collectedNum", "collectNum"
    ])
    comment_count = _jsonish_stat(text, [
        "commentCount", "comment_count", "comments", "commentNum", "commentsCount"
    ])
    note_count = _jsonish_stat(text, [
        "noteCount", "note_count", "notes", "total", "totalCount"
    ])

    view_count = view_count or _label_stat(text, ["浏览", "阅读", "观看", "views"])
    like_count = like_count or _label_stat(text, ["赞", "点赞", "likes"])
    collect_count = collect_count or _label_stat(text, ["收藏", "collects", "favorites"])
    comment_count = comment_count or _label_stat(text, ["评论", "comments"])
    note_count = note_count or _label_stat(text, ["笔记", "notes"])

    return {
        "viewCount": int(view_count),
        "likeCount": int(like_count),
        "collectCount": int(collect_count),
        "commentCount": int(comment_count),
        "noteCount": int(note_count),
    }


def _read_public_sources() -> List[Dict[str, Any]]:
    raw_urls = os.getenv("REDNOTE_PUBLIC_URLS", "").strip()
    sources: List[Dict[str, Any]] = []
    if raw_urls:
        for url in re.split(r"[\n;,]+", raw_urls):
            url = url.strip()
            if url:
                sources.append({"url": url})

    source_file = Path(os.getenv("REDNOTE_PUBLIC_URLS_FILE", str(DEFAULT_SOURCES_FILE))).expanduser()
    if source_file.exists():
        try:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RedNoteStatsError(f"Could not read REDNOTE_PUBLIC_URLS_FILE: {exc}") from exc
        rows = payload.get("sources", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise RedNoteStatsError("REDNOTE_PUBLIC_URLS_FILE must be an array or an object with sources[].")
        sources.extend(row for row in rows if isinstance(row, dict) and row.get("url"))

    return sources


def _read_public_urls_payload() -> Optional[Dict[str, Any]]:
    sources = _read_public_sources()
    if not sources:
        return None

    def crawl_source(source: Dict[str, Any]) -> Dict[str, Any]:
        url = str(source.get("url", "")).strip()
        source_kind = str(source.get("kind") or source.get("type") or "").strip().lower()
        if not source_kind:
            source_kind = "note" if "/explore/" in url or "/discovery/item/" in url else "search"
        item = dict(source)
        item["xhsUrl"] = url
        item["sourceKind"] = source_kind
        try:
            html = _fetch_public_html(url)
            stats = _extract_public_stats(html)
            title = _page_title(html)
            image = _meta_content(html, ["og:image", "twitter:image"])
            description = _meta_content(html, ["description", "og:description", "twitter:description"])

            item.update(stats)
            item.setdefault("name", title or source.get("keyword") or "RedNote public URL")
            item.setdefault("sub", description[:80] if description else "Public RedNote page")
            if image:
                item.setdefault("image", image)
            if any(stats.values()):
                item["crawlerStatus"] = "ok"
            elif "登录后查看" in html or "login" in html.lower() and "小红书" in html:
                item["crawlerStatus"] = "login_required"
            elif source_kind == "note" and not _contains_public_note_marker(html, url):
                item["crawlerStatus"] = "note_not_public"
            else:
                item["crawlerStatus"] = "no_public_stats_found"
        except RedNoteStatsError as exc:
            item.setdefault("name", source.get("keyword") or source.get("name") or "RedNote public URL")
            item.setdefault("sub", "Public page could not be read")
            item["crawlerStatus"] = "error"
            item["crawlError"] = str(exc)
        return item

    max_workers = max(1, min(_env_int("REDNOTE_PUBLIC_MAX_WORKERS", 8), 10))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        items = list(executor.map(crawl_source, sources))

    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "public-crawler",
        "items": items,
    }


def inspect_public_rednote_url(url: str) -> Dict[str, Any]:
    """Inspect one public RedNote URL and report what the crawler can read."""
    html = _fetch_public_html(url)
    stats = _extract_public_stats(html)
    source_kind = "note" if "/explore/" in url or "/discovery/item/" in url else "search"
    if any(stats.values()):
        status = "ok"
    elif "登录后查看" in html or "login" in html.lower() and "小红书" in html:
        status = "login_required"
    elif source_kind == "note" and not _contains_public_note_marker(html, url):
        status = "note_not_public"
    else:
        status = "no_public_stats_found"

    return {
        "url": url,
        "sourceKind": source_kind,
        "crawlerStatus": status,
        "title": _page_title(html),
        "image": _normalize_image_url(_meta_content(html, ["og:image", "twitter:image"])),
        "description": _meta_content(html, ["description", "og:description", "twitter:description"]),
        "rawStats": stats,
        "heatScore": _heat_score(stats),
        "htmlLength": len(html),
        "hasNoteMarkers": _contains_public_note_marker(html, url),
    }


def _find_local_design(item: Dict[str, Any], designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    design_id = _first(item, ["design_id", "designId", "localDesignId", "local_design_id", "id"])
    if design_id:
        match = next((d for d in designs if d.get("id") == design_id), None)
        if match:
            return match

    name = str(_first(item, ["localName", "local_name", "name", "title", "keyword"], "")).strip()
    if not name:
        return {}

    return next(
        (
            d for d in designs
            if d.get("name") == name or name in str(d.get("name", "")) or str(d.get("name", "")) in name
        ),
        {},
    )


def _normalize_rows(payload: Any) -> Tuple[List[Dict[str, Any]], str]:
    if isinstance(payload, list):
        return payload, ""
    if not isinstance(payload, dict):
        raise RedNoteStatsError("RedNote payload must be a JSON object or array.")

    rows = payload.get("items") or payload.get("data") or payload.get("rows") or []
    if not isinstance(rows, list):
        raise RedNoteStatsError("RedNote payload items/data/rows must be an array.")
    updated_at = payload.get("updatedAt") or payload.get("updated_at") or ""
    return rows, updated_at


def _normalize_item(item: Dict[str, Any], index: int, designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    local = _find_local_design(item, designs)
    score = _heat_score(item)

    view_count = _to_number(_first(item, ["viewCount", "views", "readCount", "view_count", "read_count"]))
    like_count = _to_number(_first(item, ["likeCount", "likes", "like_count"]))
    collect_count = _to_number(_first(item, ["collectCount", "collects", "favorites", "collect_count"]))
    comment_count = _to_number(_first(item, ["commentCount", "comments", "comment_count"]))
    note_count = _to_number(_first(item, ["noteCount", "notes", "note_count"]))

    name = _first(item, ["name", "title", "keyword"], local.get("name", "RedNote trending nail"))
    sub = _first(item, ["sub", "category", "reason"], "RedNote live metrics")
    image = _normalize_image_url(_first(item, ["image", "imageUrl", "cover", "coverUrl"], local.get("image", "")))
    trend_source = "rednote-public"
    if score <= 0:
        fallback_score = _fallback_heat_from_local_design(local)
        if fallback_score > 0:
            score = fallback_score
            trend_source = "local-fallback"
            image = _normalize_image_url(local.get("image", image))
        elif item.get("crawlerStatus") in {"error", "no_public_stats_found"}:
            trend_source = item.get("crawlerStatus")
            image = _normalize_image_url(local.get("image", image))

    heat = _first(item, ["heat"], None)
    if heat is None:
        heat = f"{local.get('heat')} 参考" if trend_source == "local-fallback" and local.get("heat") else _format_heat(score)

    return {
        "rank": index + 1,
        "id": local.get("id") or _first(item, ["design_id", "designId", "id"], ""),
        "name": name,
        "sub": sub,
        "price": _first(item, ["price"], local.get("price", "Ask in store")),
        "heat": heat,
        "heatScore": score,
        "emoji": _first(item, ["emoji"], local.get("emoji", "\U0001F485")),
        "bg": _first(item, ["bg"], local.get("bg", "#FFF0F5")),
        "image": image,
        "detailed_image": _first(item, ["detailed_image", "detailedImage"], local.get("detailed_image", "")),
        "xhs": _first(
            item,
            ["xhs", "xhsUrl", "rednoteUrl", "url"],
            "https://www.xiaohongshu.com/search_result?keyword=%E7%BE%8E%E7%94%B2",
        ),
        "rawStats": {
            "viewCount": int(view_count),
            "likeCount": int(like_count),
            "collectCount": int(collect_count),
            "commentCount": int(comment_count),
            "noteCount": int(note_count),
        },
        "crawlerStatus": item.get("crawlerStatus"),
        "crawlError": item.get("crawlError"),
        "trendSource": trend_source,
        "sourceKind": item.get("sourceKind"),
    }


def _read_api_payload() -> Optional[Dict[str, Any]]:
    api_url = os.getenv("REDNOTE_STATS_API_URL", "").strip()
    if not api_url:
        return None

    timeout = _env_int("REDNOTE_STATS_TIMEOUT_SECONDS", 10)
    headers = {"Accept": "application/json"}
    api_key = os.getenv("REDNOTE_STATS_API_KEY", "").strip()
    if api_key:
        header_name = os.getenv("REDNOTE_STATS_AUTH_HEADER", "Authorization").strip() or "Authorization"
        if header_name.lower() == "authorization" and not api_key.lower().startswith(("bearer ", "basic ")):
            api_key = f"Bearer {api_key}"
        headers[header_name] = api_key

    request = urllib.request.Request(api_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RedNoteStatsError(f"Could not read REDNOTE_STATS_API_URL: {exc}") from exc


def _read_file_payload() -> Optional[Dict[str, Any]]:
    stats_file = Path(os.getenv("REDNOTE_STATS_FILE", str(DEFAULT_STATS_FILE))).expanduser()
    if not stats_file.exists():
        return None
    try:
        return json.loads(stats_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RedNoteStatsError(f"Could not read REDNOTE_STATS_FILE: {exc}") from exc


def get_rednote_trending(designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return normalized RedNote trending stats for the frontend."""
    cache_seconds = _env_int("REDNOTE_STATS_CACHE_SECONDS", 300)
    now = time.time()
    if _CACHE["payload"] is not None and now < _CACHE["expires_at"]:
        return _CACHE["payload"]

    payload = _read_api_payload() or _read_public_urls_payload() or _read_file_payload()
    if payload is None:
        raise RedNoteStatsError(
            "No accurate RedNote data source configured. Set REDNOTE_STATS_API_URL "
            "to an authorized API endpoint, or provide backend/rednote_stats.json."
        )

    rows, updated_at = _normalize_rows(payload)
    items = [_normalize_item(row, i, designs) for i, row in enumerate(rows) if isinstance(row, dict)]
    items = sorted(items, key=lambda row: row.get("heatScore", 0), reverse=True)
    items = [{**item, "rank": index + 1} for index, item in enumerate(items)]

    result = {
        "updatedAt": updated_at or datetime.now(timezone.utc).isoformat(),
        "source": payload.get("source") if isinstance(payload, dict) and payload.get("source")
        else ("api" if os.getenv("REDNOTE_STATS_API_URL", "").strip() else "file"),
        "items": items,
    }
    _CACHE["payload"] = result
    _CACHE["expires_at"] = now + max(cache_seconds, 0)
    return result

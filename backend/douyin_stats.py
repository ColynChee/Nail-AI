"""Douyin trending stats provider for the nail app.

This module only reads:
- an authorized JSON API configured with DOUYIN_STATS_API_URL,
- an exported JSON file configured with DOUYIN_STATS_FILE, or
- public Douyin video/share URLs configured with DOUYIN_PUBLIC_URLS_FILE.

It does not bypass login, captcha, signatures, or private APIs. If public pages
do not expose metrics, the returned item is clearly marked as local fallback.
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
DEFAULT_STATS_FILE = BACKEND / "douyin_stats.json"
DEFAULT_SOURCES_FILE = BACKEND / "douyin_sources.json"

_CACHE: Dict[str, Any] = {
    "expires_at": 0.0,
    "payload": None,
}


class DouyinStatsError(RuntimeError):
    """Raised when configured Douyin data cannot be read."""


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


def _combined_item(item: Dict[str, Any]) -> Dict[str, Any]:
    raw = item.get("rawStats") if isinstance(item.get("rawStats"), dict) else {}
    combined = dict(raw)
    combined.update(item)
    return combined


def _heat_score(item: Dict[str, Any]) -> float:
    explicit = _first(item, ["heatScore", "heat_score"])
    if explicit is not None:
        return _to_number(explicit)

    views = _to_number(_first(item, ["viewCount", "views", "playCount", "play_count", "playCnt", "play_cnt"]))
    likes = _to_number(_first(item, ["likeCount", "likes", "diggCount", "digg_count", "like_count"]))
    collects = _to_number(_first(item, ["collectCount", "collects", "favoriteCount", "favorite_count", "collect_count"]))
    comments = _to_number(_first(item, ["commentCount", "comments", "comment_count"]))
    shares = _to_number(_first(item, ["shareCount", "shares", "share_count"]))
    return views + likes * 6 + collects * 8 + comments * 10 + shares * 12


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

    allowed = [
        value.strip().lower()
        for value in os.getenv(
            "DOUYIN_ALLOWED_HOSTS",
            "douyin.com,www.douyin.com,v.douyin.com,iesdouyin.com,www.iesdouyin.com",
        ).split(",")
        if value.strip()
    ]
    host = (parsed.hostname or "").lower()
    return any(host == item or host.endswith(f".{item}") for item in allowed)


def _open_request(request: urllib.request.Request, timeout: int):
    if os.getenv("DOUYIN_USE_SYSTEM_PROXY", "").strip().lower() in {"1", "true", "yes"}:
        opener = urllib.request.build_opener()
    else:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request, timeout=timeout)


def _fetch_public_html(url: str) -> str:
    if not _is_allowed_public_url(url):
        raise DouyinStatsError(f"Public crawler URL is not allowed: {url}")

    timeout = _env_int("DOUYIN_PUBLIC_TIMEOUT_SECONDS", 5)
    max_bytes = _env_int("DOUYIN_PUBLIC_MAX_BYTES", 2_500_000)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NailAIStudentProject/1.0 public-douyin-url-fetcher",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        method="GET",
    )
    try:
        with _open_request(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise DouyinStatsError(f"Public crawler response is larger than {max_bytes} bytes.")
            return body.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DouyinStatsError(f"Could not fetch public Douyin URL: {exc}") from exc


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


def _unescape_js_text(text: str) -> str:
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
        "viewCount", "view_count", "views", "playCount", "play_count", "playCnt", "play_cnt"
    ])
    like_count = _jsonish_stat(text, [
        "likeCount", "like_count", "likes", "diggCount", "digg_count", "diggCnt", "digg_cnt"
    ])
    collect_count = _jsonish_stat(text, [
        "collectCount", "collect_count", "collects", "favoriteCount", "favorite_count", "favCount"
    ])
    comment_count = _jsonish_stat(text, [
        "commentCount", "comment_count", "comments", "commentCnt", "comment_cnt"
    ])
    share_count = _jsonish_stat(text, [
        "shareCount", "share_count", "shares", "shareCnt", "share_cnt"
    ])

    view_count = view_count or _label_stat(text, ["播放", "观看", "浏览", "views", "plays"])
    like_count = like_count or _label_stat(text, ["赞", "点赞", "likes"])
    collect_count = collect_count or _label_stat(text, ["收藏", "collects", "favorites"])
    comment_count = comment_count or _label_stat(text, ["评论", "comments"])
    share_count = share_count or _label_stat(text, ["分享", "shares"])

    return {
        "viewCount": int(view_count),
        "likeCount": int(like_count),
        "collectCount": int(collect_count),
        "commentCount": int(comment_count),
        "shareCount": int(share_count),
    }


def _contains_public_video_marker(html: str) -> bool:
    markers = [
        "aweme_id",
        "awemeId",
        "aweme_detail",
        "digg_count",
        "play_count",
        "share_count",
        "Douyin",
        "抖音",
    ]
    return any(marker in html for marker in markers)


def _read_public_sources() -> List[Dict[str, Any]]:
    raw_urls = os.getenv("DOUYIN_PUBLIC_URLS", "").strip()
    sources: List[Dict[str, Any]] = []
    if raw_urls:
        for url in re.split(r"[\n;,]+", raw_urls):
            url = url.strip()
            if url:
                sources.append({"url": url})

    source_file = Path(os.getenv("DOUYIN_PUBLIC_URLS_FILE", str(DEFAULT_SOURCES_FILE))).expanduser()
    if source_file.exists():
        try:
            payload = json.loads(source_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DouyinStatsError(f"Could not read DOUYIN_PUBLIC_URLS_FILE: {exc}") from exc
        rows = payload.get("sources", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise DouyinStatsError("DOUYIN_PUBLIC_URLS_FILE must be an array or an object with sources[].")
        sources.extend(row for row in rows if isinstance(row, dict) and row.get("url"))

    return sources


def _discovery_enabled() -> bool:
    return os.getenv("DOUYIN_DISCOVERY_ENABLED", "true").strip().lower() not in {"0", "false", "no"}


def _discovery_search_url_templates() -> List[str]:
    raw = os.getenv("DOUYIN_DISCOVERY_SEARCH_URLS", "").strip()
    if not raw:
        single = os.getenv("DOUYIN_DISCOVERY_SEARCH_URL", "").strip()
        raw = single or "https://duckduckgo.com/html/?q={query}|https://www.bing.com/search?q={query}"
    return [part.strip() for part in raw.split("|") if part.strip()]


def _fetch_discovery_html(query: str, search_url_template: str) -> str:
    timeout = _env_int("DOUYIN_DISCOVERY_TIMEOUT_SECONDS", 4)
    max_bytes = _env_int("DOUYIN_DISCOVERY_MAX_BYTES", 1_500_000)
    url = search_url_template.replace("{query}", urllib.parse.quote_plus(query))
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NailAIStudentProject/1.0 public-video-discovery",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        method="GET",
    )
    try:
        with _open_request(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise DouyinStatsError(f"Discovery response is larger than {max_bytes} bytes.")
            return body.decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DouyinStatsError(f"Could not discover Douyin videos: {exc}") from exc


def _clean_discovered_url(url: str) -> str:
    current = unescape(url).strip()
    for _ in range(2):
        decoded = urllib.parse.unquote(current)
        if decoded == current:
            break
        current = decoded

    if "uddg=" in current:
        parsed = urllib.parse.urlparse(current)
        params = urllib.parse.parse_qs(parsed.query)
        if params.get("uddg"):
            current = params["uddg"][0]

    current = current.replace("\\/", "/").replace("\\u002F", "/")
    current = re.split(r"[\s\"'<>]", current, maxsplit=1)[0]
    current = current.rstrip(").,;")
    return current


def _extract_douyin_urls_from_search_html(html: str) -> List[str]:
    text = _unescape_js_text(html)
    candidates: List[str] = []
    candidates.extend(match.group(1) for match in re.finditer(r"uddg=([^&\"'<>]+)", text))
    candidates.extend(
        match.group(1)
        for match in re.finditer(
            r"(https?://(?:www\.)?(?:douyin\.com|v\.douyin\.com|iesdouyin\.com)[^\"'<>\\\s]+)",
            text,
            flags=re.IGNORECASE,
        )
    )

    seen = set()
    urls: List[str] = []
    for candidate in candidates:
        url = _clean_discovered_url(candidate)
        if not _is_allowed_public_url(url):
            continue
        if "/search/" in urllib.parse.urlparse(url).path:
            continue
        key = url.split("#", 1)[0]
        if key not in seen:
            seen.add(key)
            urls.append(key)
    return urls


def _design_discovery_keyword(design: Dict[str, Any]) -> str:
    name = str(design.get("name") or "").strip()
    tags = [str(tag).strip() for tag in design.get("tags", []) if str(tag).strip()]
    parts = [name, *tags[:2], "美甲"]
    return " ".join(part for part in parts if part)


def _discover_public_sources(designs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not _discovery_enabled():
        return []

    max_designs = max(1, min(_env_int("DOUYIN_DISCOVERY_MAX_DESIGNS", len(designs)), len(designs)))
    per_design = max(1, min(_env_int("DOUYIN_DISCOVERY_RESULTS_PER_DESIGN", 1), 3))
    templates_env = os.getenv("DOUYIN_DISCOVERY_QUERY_TEMPLATES", "").strip()
    templates = [part.strip() for part in templates_env.split("|") if part.strip()] or [
        "site:douyin.com/video {keyword}",
        "site:v.douyin.com {keyword}",
    ]

    def discover_for_design(design: Dict[str, Any]) -> List[Dict[str, Any]]:
        keyword = _design_discovery_keyword(design)
        if not keyword:
            return []
        found_urls: List[str] = []
        for template in templates:
            query = template.replace("{keyword}", keyword)
            for search_template in _discovery_search_url_templates():
                try:
                    html = _fetch_discovery_html(query, search_template)
                    found_urls.extend(_extract_douyin_urls_from_search_html(html))
                except DouyinStatsError:
                    continue
                if len(found_urls) >= per_design:
                    break
            if len(found_urls) >= per_design:
                break

        unique_urls: List[str] = []
        seen = set()
        for url in found_urls:
            if url in seen:
                continue
            seen.add(url)
            unique_urls.append(url)
            if len(unique_urls) >= per_design:
                break

        return [
            {
                "design_id": design.get("id", ""),
                "keyword": keyword,
                "url": url,
                "sub": "自动发现的抖音公开视频",
                "kind": "discovered-video",
                "discovered": True,
                "discoveryQuery": keyword,
            }
            for url in unique_urls
        ]

    max_workers = max(1, min(_env_int("DOUYIN_DISCOVERY_MAX_WORKERS", 6), 10))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        discovered_lists = list(executor.map(discover_for_design, designs[:max_designs]))

    sources: List[Dict[str, Any]] = []
    seen_urls = set()
    for rows in discovered_lists:
        for row in rows:
            url = row["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append(row)

    return sources


def _read_public_urls_payload(
    sources: Optional[List[Dict[str, Any]]] = None,
    source_name: str = "public-crawler",
) -> Optional[Dict[str, Any]]:
    if sources is None:
        sources = _read_public_sources()
    if not sources:
        return None

    def crawl_source(source: Dict[str, Any]) -> Dict[str, Any]:
        url = str(source.get("url", "")).strip()
        item = dict(source)
        item["douyinUrl"] = url
        item["sourceKind"] = str(source.get("kind") or source.get("type") or "video").strip().lower()
        try:
            html = _fetch_public_html(url)
            stats = _extract_public_stats(html)
            title = _page_title(html)
            image = _normalize_image_url(_meta_content(html, ["og:image", "twitter:image"]))
            description = _meta_content(html, ["description", "og:description", "twitter:description"])

            item.update(stats)
            item.setdefault("name", title or source.get("keyword") or "Douyin public video")
            item.setdefault("sub", description[:80] if description else "Douyin public video")
            if image:
                item.setdefault("image", image)
            if any(stats.values()):
                item["crawlerStatus"] = "ok"
            elif any(token in html.lower() for token in ["login", "captcha", "verify"]) or "登录" in html or "验证码" in html:
                item["crawlerStatus"] = "login_required"
            elif not _contains_public_video_marker(html):
                item["crawlerStatus"] = "video_not_public"
            else:
                item["crawlerStatus"] = "no_public_stats_found"
        except DouyinStatsError as exc:
            item.setdefault("name", source.get("keyword") or source.get("name") or "Douyin public video")
            item.setdefault("sub", "Public Douyin page could not be read")
            item["crawlerStatus"] = "error"
            item["crawlError"] = str(exc)
        return item

    max_workers = max(1, min(_env_int("DOUYIN_PUBLIC_MAX_WORKERS", 8), 10))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        items = list(executor.map(crawl_source, sources))

    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": source_name,
        "items": items,
    }


def _read_discovered_public_urls_payload(designs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    sources = _discover_public_sources(designs)
    if not sources:
        return None
    payload = _read_public_urls_payload(sources, "public-discovery")
    if payload is not None:
        payload["message"] = f"Auto-discovered {len(sources)} public Douyin video URL(s)."
    return payload


def inspect_public_douyin_url(url: str) -> Dict[str, Any]:
    """Inspect one public Douyin URL and report what the crawler can read."""
    html = _fetch_public_html(url)
    stats = _extract_public_stats(html)
    if any(stats.values()):
        status = "ok"
    elif any(token in html.lower() for token in ["login", "captcha", "verify"]) or "登录" in html or "验证码" in html:
        status = "login_required"
    elif not _contains_public_video_marker(html):
        status = "video_not_public"
    else:
        status = "no_public_stats_found"

    return {
        "url": url,
        "sourceKind": "video",
        "crawlerStatus": status,
        "title": _page_title(html),
        "image": _normalize_image_url(_meta_content(html, ["og:image", "twitter:image"])),
        "description": _meta_content(html, ["description", "og:description", "twitter:description"]),
        "rawStats": stats,
        "heatScore": _heat_score(stats),
        "htmlLength": len(html),
        "hasVideoMarkers": _contains_public_video_marker(html),
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
        raise DouyinStatsError("Douyin payload must be a JSON object or array.")

    rows = payload.get("items") or payload.get("data") or payload.get("rows") or []
    if not isinstance(rows, list):
        raise DouyinStatsError("Douyin payload items/data/rows must be an array.")
    updated_at = payload.get("updatedAt") or payload.get("updated_at") or ""
    return rows, updated_at


def _normalize_item(item: Dict[str, Any], index: int, designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    combined = _combined_item(item)
    local = _find_local_design(combined, designs)
    score = _heat_score(combined)

    view_count = _to_number(_first(combined, ["viewCount", "views", "playCount", "play_count", "playCnt", "play_cnt"]))
    like_count = _to_number(_first(combined, ["likeCount", "likes", "diggCount", "digg_count", "like_count"]))
    collect_count = _to_number(_first(combined, ["collectCount", "collects", "favoriteCount", "favorite_count", "collect_count"]))
    comment_count = _to_number(_first(combined, ["commentCount", "comments", "comment_count"]))
    share_count = _to_number(_first(combined, ["shareCount", "shares", "share_count"]))

    name = _first(combined, ["name", "title", "keyword"], local.get("name", "Douyin trending nail"))
    sub = _first(combined, ["sub", "category", "reason"], "Douyin live metrics")
    image = _normalize_image_url(_first(combined, ["image", "imageUrl", "cover", "coverUrl"], local.get("image", "")))

    explicit_trend = _first(combined, ["trendSource", "trend_source"], "")
    trend_source = explicit_trend or "douyin-public"
    if not explicit_trend and score <= 0:
        fallback_score = _fallback_heat_from_local_design(local)
        if fallback_score > 0:
            score = fallback_score
            trend_source = "local-fallback"
            image = _normalize_image_url(local.get("image", image))
        elif combined.get("crawlerStatus") in {"error", "no_public_stats_found", "login_required", "video_not_public"}:
            trend_source = combined.get("crawlerStatus")
            image = _normalize_image_url(local.get("image", image))

    heat = _first(combined, ["heat"], None)
    if heat is None:
        heat = f"{local.get('heat')} 参考" if trend_source == "local-fallback" and local.get("heat") else _format_heat(score)

    url = _first(combined, ["douyin", "douyinUrl", "awemeUrl", "url"], "")
    return {
        "rank": index + 1,
        "id": local.get("id") or _first(combined, ["design_id", "designId", "id"], ""),
        "name": name,
        "sub": sub,
        "price": _first(combined, ["price"], local.get("price", "到店咨询")),
        "heat": heat,
        "heatScore": score,
        "emoji": _first(combined, ["emoji"], local.get("emoji", "")),
        "bg": _first(combined, ["bg"], local.get("bg", "#FFF0F5")),
        "image": image,
        "detailed_image": _first(combined, ["detailed_image", "detailedImage"], local.get("detailed_image", "")),
        "douyin": url,
        "douyinUrl": url,
        "xhs": url,
        "rawStats": {
            "viewCount": int(view_count),
            "likeCount": int(like_count),
            "collectCount": int(collect_count),
            "commentCount": int(comment_count),
            "shareCount": int(share_count),
        },
        "crawlerStatus": combined.get("crawlerStatus"),
        "crawlError": combined.get("crawlError"),
        "trendSource": trend_source,
        "sourceKind": combined.get("sourceKind"),
    }


def _read_api_payload() -> Optional[Dict[str, Any]]:
    api_url = os.getenv("DOUYIN_STATS_API_URL", "").strip()
    if not api_url:
        return None

    timeout = _env_int("DOUYIN_STATS_TIMEOUT_SECONDS", 10)
    headers = {"Accept": "application/json"}
    api_key = os.getenv("DOUYIN_STATS_API_KEY", "").strip()
    if api_key:
        header_name = os.getenv("DOUYIN_STATS_AUTH_HEADER", "Authorization").strip() or "Authorization"
        if header_name.lower() == "authorization" and not api_key.lower().startswith(("bearer ", "basic ")):
            api_key = f"Bearer {api_key}"
        headers[header_name] = api_key

    request = urllib.request.Request(api_url, headers=headers, method="GET")
    try:
        with _open_request(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DouyinStatsError(f"Could not read DOUYIN_STATS_API_URL: {exc}") from exc


def _read_file_payload() -> Optional[Dict[str, Any]]:
    stats_file = Path(os.getenv("DOUYIN_STATS_FILE", str(DEFAULT_STATS_FILE))).expanduser()
    if not stats_file.exists():
        return None
    try:
        return json.loads(stats_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DouyinStatsError(f"Could not read DOUYIN_STATS_FILE: {exc}") from exc


def _local_fallback_row(design: Dict[str, Any], crawler_status: str = "unconfigured") -> Dict[str, Any]:
    score = _fallback_heat_from_local_design(design)
    sub = "已自动搜索 · 暂无公开视频统计" if crawler_status == "not_discovered" else "未接入抖音公开视频"
    return {
            "design_id": design.get("id", ""),
            "name": design.get("name", "本地款式"),
            "sub": sub,
            "price": design.get("price", "到店咨询"),
            "heat": f"{design.get('heat', '0')} 参考",
            "heatScore": score,
            "emoji": design.get("emoji", ""),
            "bg": design.get("bg", "#FFF0F5"),
            "image": design.get("image", ""),
            "detailed_image": design.get("detailed_image", ""),
            "trendSource": "local-fallback",
            "crawlerStatus": crawler_status,
            "sourceKind": "local",
    }


def _build_local_fallback_payload(
    designs: List[Dict[str, Any]],
    crawler_status: str = "unconfigured",
    message: str = "",
    source: str = "local-fallback",
) -> Dict[str, Any]:
    rows = [_local_fallback_row(design, crawler_status) for design in designs]
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "message": message or "No Douyin public video URLs configured yet. Add public video/share URLs to backend/douyin_sources.json for live metrics.",
        "items": rows,
    }


def _append_missing_local_fallbacks(
    rows: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
    designs: List[Dict[str, Any]],
    source: str,
) -> List[Dict[str, Any]]:
    if source not in {"public-crawler", "public-discovery"}:
        return items
    seen_ids = {str(item.get("id") or "") for item in items if item.get("id")}
    fallback_rows = [
        _local_fallback_row(design, "not_discovered")
        for design in designs
        if str(design.get("id") or "") not in seen_ids
    ]
    start = len(rows)
    fallback_items = [
        _normalize_item(row, start + index, designs)
        for index, row in enumerate(fallback_rows)
    ]
    return [*items, *fallback_items]


def get_douyin_trending(designs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return normalized Douyin trending stats for the frontend."""
    cache_seconds = _env_int("DOUYIN_STATS_CACHE_SECONDS", 300)
    now = time.time()
    if _CACHE["payload"] is not None and now < _CACHE["expires_at"]:
        return _CACHE["payload"]

    payload = (
        _read_api_payload()
        or _read_public_urls_payload()
        or _read_file_payload()
        or _read_discovered_public_urls_payload(designs)
    )
    if payload is None:
        if _discovery_enabled():
            payload = _build_local_fallback_payload(
                designs,
                "not_discovered",
                "Auto discovery did not find readable public Douyin video URLs yet; using local reference heat.",
                "public-discovery",
            )
        else:
            payload = _build_local_fallback_payload(designs)

    rows, updated_at = _normalize_rows(payload)
    source = payload.get("source") if isinstance(payload, dict) and payload.get("source") else (
        "api" if os.getenv("DOUYIN_STATS_API_URL", "").strip() else "file"
    )
    items = [_normalize_item(row, i, designs) for i, row in enumerate(rows) if isinstance(row, dict)]
    items = _append_missing_local_fallbacks(rows, items, designs, source)
    items = sorted(items, key=lambda row: row.get("heatScore", 0), reverse=True)
    items = [{**item, "rank": index + 1} for index, item in enumerate(items)]

    result = {
        "updatedAt": updated_at or datetime.now(timezone.utc).isoformat(),
        "source": source,
        "message": payload.get("message", "") if isinstance(payload, dict) else "",
        "items": items,
    }
    _CACHE["payload"] = result
    _CACHE["expires_at"] = now + max(cache_seconds, 0)
    return result

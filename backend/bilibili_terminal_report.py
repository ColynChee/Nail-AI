"""Terminal report for the Bilibili trend integration.

Run this before a demo to show where the platform data comes from and how the
trend score is calculated.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from bilibili_stats import get_bilibili_trending


BACKEND = Path(__file__).resolve().parent
DESIGNS_FILE = BACKEND / "designs.json"
SOURCES_FILE = BACKEND / "bilibili_sources.json"


def _setup_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


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


def _fmt(value: Any) -> str:
    num = _to_number(value)
    if num >= 10000:
        return f"{num / 10000:.1f}w"
    if num >= 1000:
        return f"{num / 1000:.1f}k"
    return str(int(round(num)))


def _fmt_raw(value: Any) -> str:
    return f"{int(round(_to_number(value))):,}"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _video_id(url: str) -> str:
    match = re.search(r"(BV[0-9A-Za-z]{10}|av[0-9]+)", url or "")
    return match.group(1) if match else "-"


def _heat_parts(stats: Dict[str, Any]) -> Dict[str, float]:
    views = _to_number(stats.get("viewCount"))
    likes = _to_number(stats.get("likeCount"))
    favorites = _to_number(stats.get("collectCount"))
    comments = _to_number(stats.get("commentCount"))
    danmaku = _to_number(stats.get("danmakuCount"))
    coins = _to_number(stats.get("coinCount"))
    shares = _to_number(stats.get("shareCount"))
    return {
        "views": views,
        "likes_x6": likes * 6,
        "favorites_x8": favorites * 8,
        "comments_x10": comments * 10,
        "danmaku_x3": danmaku * 3,
        "coins_x6": coins * 6,
        "shares_x12": shares * 12,
    }


def _heat_score(stats: Dict[str, Any]) -> float:
    return sum(_heat_parts(stats).values())


def _intent_score(stats: Dict[str, Any]) -> float:
    likes = _to_number(stats.get("likeCount"))
    favorites = _to_number(stats.get("collectCount"))
    comments = _to_number(stats.get("commentCount"))
    danmaku = _to_number(stats.get("danmakuCount"))
    coins = _to_number(stats.get("coinCount"))
    shares = _to_number(stats.get("shareCount"))
    return likes + favorites * 1.4 + comments * 1.8 + shares * 2 + danmaku * 0.5 + coins * 0.7


def _total(items: Iterable[Dict[str, Any]], key: str) -> float:
    return sum(_to_number((item.get("rawStats") or {}).get(key)) for item in items)


def _print_formula() -> None:
    print("=" * 88)
    print("Bilibili Trend Evidence Report / B站热度数据证明")
    print("=" * 88)
    print("Data source:")
    print("  backend/bilibili_sources.json stores public Bilibili video IDs.")
    print("  backend/bilibili_stats.py calls Bilibili public endpoint:")
    print("  https://api.bilibili.com/x/web-interface/view?bvid=...")
    print()
    print("Trend ranking formula used by backend and frontend:")
    print("  heat = views")
    print("       + likes * 6")
    print("       + favorites * 8")
    print("       + comments * 10")
    print("       + danmaku * 3")
    print("       + coins * 6")
    print("       + shares * 12")
    print()
    print("Operations dashboard high-intent formula:")
    print("  intent = likes + favorites*1.4 + comments*1.8 + shares*2 + danmaku*0.5 + coins*0.7")
    print("=" * 88)


def _print_summary(payload: Dict[str, Any], designs_count: int, sources_count: int) -> None:
    items = payload.get("items", [])
    live_count = sum(1 for item in items if item.get("trendSource") == "bilibili-public")
    fallback_count = sum(1 for item in items if item.get("trendSource") == "local-fallback")
    total_views = _total(items, "viewCount")
    total_likes = _total(items, "likeCount")
    total_favorites = _total(items, "collectCount")
    total_comments = _total(items, "commentCount")
    total_danmaku = _total(items, "danmakuCount")
    total_coins = _total(items, "coinCount")
    total_shares = _total(items, "shareCount")
    total_intent = sum(_intent_score(item.get("rawStats") or {}) for item in items)

    print()
    print("Dataset summary")
    print("-" * 88)
    print(f"Designs in local catalog      : {designs_count}")
    print(f"Bilibili sources configured   : {sources_count}")
    print(f"Live Bilibili rows returned   : {live_count}")
    print(f"Local fallback rows           : {fallback_count}")
    print(f"Updated at                    : {payload.get('updatedAt', '-')}")
    print()
    print("Aggregated public stats")
    print(f"  total views                 : {_fmt_raw(total_views)}")
    print(f"  total likes                 : {_fmt_raw(total_likes)}")
    print(f"  total favorites             : {_fmt_raw(total_favorites)}")
    print(f"  total comments              : {_fmt_raw(total_comments)}")
    print(f"  total danmaku               : {_fmt_raw(total_danmaku)}")
    print(f"  total coins                 : {_fmt_raw(total_coins)}")
    print(f"  total shares                : {_fmt_raw(total_shares)}")
    print(f"  high-intent score           : {_fmt_raw(total_intent)}")


def _print_ranking(items: List[Dict[str, Any]], top: int) -> None:
    print()
    print(f"Top {min(top, len(items))} ranked nail styles by calculated heat")
    print("-" * 88)
    for item in items[:top]:
        stats = item.get("rawStats") or {}
        status = item.get("crawlerStatus") or "-"
        heat = _heat_score(stats) or _to_number(item.get("heatScore"))
        url = item.get("platformUrl") or item.get("bilibili") or ""
        print(
            f"#{item.get('rank', '-'):>2} "
            f"{str(item.get('id', '-')):<10} "
            f"{str(item.get('name', '-'))[:18]:<18} "
            f"{_video_id(url):<12} "
            f"views={_fmt(stats.get('viewCount')):<7} "
            f"likes={_fmt(stats.get('likeCount')):<6} "
            f"fav={_fmt(stats.get('collectCount')):<6} "
            f"comments={_fmt(stats.get('commentCount')):<5} "
            f"heat={_fmt(heat):<8} "
            f"status={status}"
        )


def _print_breakdown(items: List[Dict[str, Any]], count: int) -> None:
    print()
    print(f"Heat formula breakdown for top {min(count, len(items))}")
    print("-" * 88)
    for item in items[:count]:
        stats = item.get("rawStats") or {}
        parts = _heat_parts(stats)
        heat = _heat_score(stats) or _to_number(item.get("heatScore"))
        print(f"#{item.get('rank', '-')} {item.get('name', '-')}")
        print(f"  URL: {item.get('platformUrl') or item.get('bilibili') or '-'}")
        print(f"  views       : {_fmt_raw(stats.get('viewCount'))}")
        print(f"  likes       : {_fmt_raw(stats.get('likeCount'))}  -> likes*6       = {_fmt_raw(parts['likes_x6'])}")
        print(f"  favorites   : {_fmt_raw(stats.get('collectCount'))}  -> favorites*8   = {_fmt_raw(parts['favorites_x8'])}")
        print(f"  comments    : {_fmt_raw(stats.get('commentCount'))}  -> comments*10   = {_fmt_raw(parts['comments_x10'])}")
        print(f"  danmaku     : {_fmt_raw(stats.get('danmakuCount'))}  -> danmaku*3     = {_fmt_raw(parts['danmaku_x3'])}")
        print(f"  coins       : {_fmt_raw(stats.get('coinCount'))}  -> coins*6       = {_fmt_raw(parts['coins_x6'])}")
        print(f"  shares      : {_fmt_raw(stats.get('shareCount'))}  -> shares*12     = {_fmt_raw(parts['shares_x12'])}")
        print(f"  final heat  : {_fmt_raw(heat)}")
        print(f"  intent score: {_fmt_raw(_intent_score(stats))}")
        print()


def main() -> int:
    _setup_stdout()
    parser = argparse.ArgumentParser(description="Show Bilibili stats and heat-score calculation for demo recording.")
    parser.add_argument("--top", type=int, default=25, help="How many ranked styles to print.")
    parser.add_argument("--breakdown", type=int, default=5, help="How many top styles to explain line by line.")
    args = parser.parse_args()

    designs_payload = _read_json(DESIGNS_FILE)
    sources_payload = _read_json(SOURCES_FILE)
    designs = designs_payload.get("designs", [])
    sources = sources_payload.get("sources", [])

    _print_formula()
    payload = get_bilibili_trending(designs)
    items = payload.get("items", [])
    _print_summary(payload, len(designs), len(sources))
    _print_ranking(items, max(args.top, 0))
    _print_breakdown(items, max(args.breakdown, 0))

    print("Demo line you can say:")
    print("  The dashboard does not use a fake number. It reads public Bilibili video stats,")
    print("  applies the weighted heat formula above, ranks the nail styles, then generates")
    print("  operation actions such as main recommendation, conversion focus, and content fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

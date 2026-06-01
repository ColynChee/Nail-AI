"""Generate designs.json from the competition Excel dataset.

Reads `命题三美甲评测数据（对外版）.xlsx` (sheet 款式图) and produces a 25-entry
designs.json pointing at the locally cached 款式图/*.webp files.

Heat / rank / price are placeholders to be backfilled later (smart-ops module).
"""
import json
import re
import os
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EXCEL = ROOT / "命题三美甲评测数据（对外版）.xlsx"
STYLE_DIR = ROOT / "款式图"
OUT = Path(__file__).resolve().parent / "designs.json"

PLACEHOLDER_NAMES = [
    "裸色奶油", "雾感橄榄", "白底波点", "暖棕琥珀", "莓果红",
    "蜜桃珊瑚", "薄荷青", "玫瑰渐变", "雾紫晚霞", "象牙白",
    "深邃黑金", "焦糖咖啡", "粉雾少女", "镜面银", "墨绿丝绒",
    "晨曦杏", "海岛蓝", "黄昏橘", "巧克力棕", "葡萄紫",
    "樱花粉", "燕麦奶咖", "墨黑漆", "极光闪片", "正红丝绒",
]

def hash_from_url(url: str) -> str:
    m = re.search(r"/([0-9a-f]+)\.(png|webp|jpg)", str(url))
    return m.group(1) if m else ""

def main():
    if not EXCEL.exists():
        print(f"Excel not found: {EXCEL}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_excel(EXCEL, sheet_name="款式图")
    local_files = {p.stem: p.name for p in STYLE_DIR.glob("*.webp")}

    designs = []
    missing = []
    for _, row in df.iterrows():
        idx = int(row["序号"])
        enh_hash = hash_from_url(row["增强后款式图URL"])
        orig_hash = hash_from_url(row["原始款式图URL"])

        if enh_hash not in local_files:
            missing.append((idx, enh_hash))
            continue

        designs.append({
            "id": f"design_{idx:03d}",
            "name": PLACEHOLDER_NAMES[(idx - 1) % len(PLACEHOLDER_NAMES)],
            "image": f"款式图/{local_files[enh_hash]}",
            "original_url": row["原始款式图URL"],
            "enhanced_url": row["增强后款式图URL"],
            "original_hash": orig_hash,
            "enhanced_hash": enh_hash,
            # Operations placeholders — to be filled by 智能运营 module
            "price": None,
            "heat": 0,
            "rank": idx,
            "tags": [],
        })

    if missing:
        print(f"⚠️ {len(missing)} designs missing local image:", missing)

    out_obj = {"designs": designs}
    OUT.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Wrote {len(designs)} designs to {OUT}")

if __name__ == "__main__":
    main()

"""
添加新款式工具
==============
使用方法：
1. 把新的美甲图片放进 新款式图/ 文件夹（支持 .jpg .png .webp）
2. 运行：python3 add_designs.py
3. 脚本会自动把图片复制到 款式图/ 并更新 designs.json
4. 重启后端即可看到新款式

可用标签：春夏 秋冬 约会 通勤 法式 韩系 日系 甜美 酷感 闪耀 裸色 复古 花系 温柔
"""

import json
import os
import shutil
import hashlib
from pathlib import Path

ROOT = Path(__file__).parent
DESIGNS_JSON = ROOT / "backend" / "designs.json"
IMG_DIR = ROOT / "款式图"
NEW_IMG_DIR = ROOT / "新款式图"

EMOJIS = ["🌸","🌺","✨","💅","🌿","💎","⭐","🤍","🌙","🦋","🌼","🍓","🫐","🌹","💐"]
BG_COLORS = ["#FFF0F5","#FFF4F0","#F0FDF4","#FFF9E6","#EFF6FF","#F5F0FF","#FFF5F5","#F7F3F0","#FFFBEB"]

def hash_file(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()[:20]

def main():
    NEW_IMG_DIR.mkdir(exist_ok=True)
    IMG_DIR.mkdir(exist_ok=True)

    new_images = list(NEW_IMG_DIR.glob("*.jpg")) + \
                 list(NEW_IMG_DIR.glob("*.png")) + \
                 list(NEW_IMG_DIR.glob("*.webp"))

    if not new_images:
        print(f"⚠️  新款式图/ 文件夹里没有图片")
        print(f"   请把美甲图片放进: {NEW_IMG_DIR}")
        return

    data = json.load(open(DESIGNS_JSON, encoding="utf-8"))
    designs = data["designs"]
    next_id = max((int(d["id"].replace("design_","")) for d in designs if d["id"].startswith("design_")), default=0) + 1

    added = []
    for img_path in sorted(new_images):
        ext = img_path.suffix.lower()
        file_hash = hash_file(img_path)
        new_filename = f"{file_hash}{ext}"
        dest = IMG_DIR / new_filename
        rel_path = f"款式图/{new_filename}"

        # 跳过已存在的
        if any(d.get("image") == rel_path for d in designs):
            print(f"⏭️  已存在，跳过: {img_path.name}")
            continue

        shutil.copy2(img_path, dest)

        # 交互式填写信息
        print(f"\n📸 图片: {img_path.name}")
        name = input("   款式名称 (必填): ").strip()
        if not name:
            name = f"新款式{next_id:03d}"

        print("   可用标签: 春夏 秋冬 约会 通勤 法式 韩系 日系 甜美 酷感 闪耀 裸色 复古 花系 温柔")
        tags_input = input("   标签 (空格分隔，如: 春夏 约会): ").strip()
        tags = tags_input.split() if tags_input else ["日常", "百搭"]

        price = input("   价格 (如 ¥199，直接回车默认 ¥199): ").strip() or "¥199"
        heat = input("   热度 (如 1.5w，直接回车默认 1.0w): ").strip() or "1.0w"

        emoji_idx = (next_id - 1) % len(EMOJIS)
        bg_idx = (next_id - 1) % len(BG_COLORS)

        entry = {
            "id": f"design_{next_id:03d}",
            "name": name,
            "image": rel_path,
            "detailed_image": rel_path,
            "price": price,
            "heat": heat,
            "rank": next_id,
            "tags": tags,
            "emoji": EMOJIS[emoji_idx],
            "bg": BG_COLORS[bg_idx]
        }

        designs.append(entry)
        added.append(name)
        next_id += 1
        print(f"   ✅ 已添加: {name} (ID: {entry['id']})")

    if added:
        # 更新 rank
        for i, d in enumerate(sorted(designs, key=lambda x: x.get("rank", 999))):
            d["rank"] = i + 1

        with open(DESIGNS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n🎉 完成！共添加 {len(added)} 个新款式:")
        for name in added:
            print(f"   • {name}")
        print(f"\n请重启后端服务器查看新款式：")
        print(f"   kill $(lsof -ti:8000) && cd backend && python3 -m uvicorn main:app --reload")
    else:
        print("\n没有新款式被添加。")

if __name__ == "__main__":
    main()

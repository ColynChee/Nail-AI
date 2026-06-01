import os
from PIL import Image
import glob

img_dir = r"d:\指上谈兵\款式图"
target_ratio = 16 / 9

jpg_files = glob.glob(os.path.join(img_dir, "*.jpg"))
print(f"找到 {len(jpg_files)} 张 JPG 图片")

for img_path in jpg_files:
    try:
        img = Image.open(img_path)
        w, h = img.size
        current_ratio = w / h

        if abs(current_ratio - target_ratio) < 0.01:
            print(f"✓ {os.path.basename(img_path)} 已是 16:9")
            continue

        new_h = int(w / target_ratio)

        if new_h > h:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img_crop = img.crop((left, 0, left + new_w, h))
        else:
            top = (h - new_h) // 2
            img_crop = img.crop((0, top, w, top + new_h))

        img_crop.save(img_path, quality=95)
        print(f"✓ {os.path.basename(img_path)}: {w}x{h} → {img_crop.width}x{img_crop.height}")

    except Exception as e:
        print(f"✗ {os.path.basename(img_path)}: {e}")

print("\n完成！所有详细设计图已裁剪为 16:9 比例")

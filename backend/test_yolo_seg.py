"""阶段 1-3/1-4: 验证 YOLOv8-seg 指甲分割效果。

独立测试脚本，不依赖也不修改现有后端代码。
跑两张图：
  1) 用户手图（正常正面手背）
  2) 款式图 牛油果奶咖（MediaPipe 检测不到的侧拍手）

对每张图输出：
  - 检测到几个指甲
  - 每个指甲的置信度
  - 一张叠加可视化图（彩色 mask + 边框）存到 seg_out/
"""
import sys
import os
from pathlib import Path
import numpy as np
import cv2

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(__file__).resolve().parent / "models" / "nails_seg_yolov8.pt"
OUT_DIR = Path(__file__).resolve().parent / "seg_out"
OUT_DIR.mkdir(exist_ok=True)

# 中文路径安全读图
def imread_unicode(path):
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

TEST_IMAGES = [
    ("user_hand", ROOT / "手图" / "b9632e3a699fdb63a1a6139bbfd6bf0d2159483.webp"),
    ("style_avocado", ROOT / "款式图" / "162afb52255bd908ba3ec418fd61824a2254875.webp"),
]

def main():
    from ultralytics import YOLO
    print(f"加载模型: {MODEL_PATH}")
    model = YOLO(str(MODEL_PATH))
    # RTX 5060 (sm_120) 当前 torch cu124 不支持，先用 CPU 验证分割效果
    DEVICE = "cpu"

    for label, img_path in TEST_IMAGES:
        print("\n" + "=" * 60)
        print(f"测试图: {label}  ({img_path.name})")
        img = imread_unicode(img_path)
        if img is None:
            print("  ❌ 图片读取失败")
            continue
        h, w = img.shape[:2]
        print(f"  尺寸: {w}x{h}")

        # 推理（conf 设低一点，先看模型最大能检出多少）
        results = model.predict(img, conf=0.25, verbose=False, device=DEVICE)
        r = results[0]

        if r.masks is None or len(r.masks) == 0:
            print("  ⚠️ 没有检测到任何指甲")
            cv2.imwrite(str(OUT_DIR / f"{label}_none.jpg"), img)
            continue

        n = len(r.masks)
        confs = r.boxes.conf.cpu().numpy() if r.boxes is not None else []
        print(f"  ✅ 检测到 {n} 个指甲")
        for i, c in enumerate(confs):
            print(f"     指甲 {i+1}: 置信度 {c:.2f}")

        # 可视化：每个 mask 叠一个半透明彩色
        overlay = img.copy()
        masks = r.masks.data.cpu().numpy()  # (n, H, W) 0/1
        rng = np.random.default_rng(42)
        for i in range(n):
            m = cv2.resize(masks[i], (w, h), interpolation=cv2.INTER_NEAREST) > 0.5
            color = rng.integers(60, 255, size=3).tolist()
            overlay[m] = (0.5 * np.array(color) + 0.5 * overlay[m]).astype(np.uint8)
            # 画轮廓
            cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, cnts, -1, color, 2)

        out_path = OUT_DIR / f"{label}_seg.jpg"
        cv2.imwrite(str(out_path), overlay)
        print(f"  💾 可视化已存: {out_path}")

    print("\n" + "=" * 60)
    print(f"完成。打开 {OUT_DIR} 看可视化结果。")

if __name__ == "__main__":
    main()

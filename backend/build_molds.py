"""阶段 2A: 款式图分割 + 编号 + 生成可人工纠正的标注骨架。

对每个款式图:
  1) YOLO 分割每个指甲（按质心稳定排序得到编号 0,1,2,...）
  2) 编号预览图 molds_preview/<did>.jpg —— 每个甲面画上大数字
  3) 编号原料 molds_raw/<did>/<idx>.png —— 每个指甲的纹理+alpha
  4) 自动猜测对应写入 molds_labels.auto.json（每次覆盖）
     首次运行时复制成 molds_labels.json（你手动编辑这一份，重跑不会被覆盖）

用法:
  python build_molds.py        # 全部 25 个
  python build_molds.py 3      # 只前 3 个
"""
import sys
import os
import json
import shutil
from pathlib import Path
import numpy as np
import cv2

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path(__file__).resolve().parent
DESIGNS = json.load(open(BACKEND / "designs.json", encoding="utf-8"))["designs"]
PREVIEW_DIR = BACKEND / "molds_preview"
RAW_DIR = BACKEND / "molds_raw"
AUTO_LABELS = BACKEND / "molds_labels.auto.json"
USER_LABELS = BACKEND / "molds_labels.json"

PREVIEW_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]


def imread_unicode(path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite_unicode(path, img):
    ext = os.path.splitext(str(path))[1]
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(str(path))
    return ok


def stable_order(nails):
    """按质心 (x 主, y 次) 排序，得到稳定编号。"""
    return sorted(nails, key=lambda n: (round(n["centroid"][0] / 40), n["centroid"][1]))


def _extract_upright_mold(img, nail):
    """把单个指甲抠出并旋转成"指尖朝上"标准姿态，返回 BGRA。
    tip_angle 是图像中指尖朝向角度(度)；旋转使指尖指向 -y(上)。"""
    mask = nail["mask"]
    cx, cy = nail["centroid"]
    tip_angle = nail.get("tip_angle", -90.0)

    # 旋转量：把 tip_angle 转到 -90°(朝上)
    rot = tip_angle - (-90.0)
    M = cv2.getRotationMatrix2D((cx, cy), rot, 1.0)

    h, w = img.shape[:2]
    bgr_rot = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR)
    mask_rot = cv2.warpAffine(mask.astype(np.uint8) * 255, M, (w, h), flags=cv2.INTER_NEAREST)

    ys, xs = np.where(mask_rot > 127)
    if len(xs) == 0:
        # 兜底：不旋转
        ys, xs = np.where(mask)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = img[y0:y1, x0:x1]
        alpha = (mask[y0:y1, x0:x1] * 255).astype(np.uint8)
        bgra = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
        bgra[:, :, 3] = alpha
        return bgra

    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop = bgr_rot[y0:y1, x0:x1]
    alpha = mask_rot[y0:y1, x0:x1]
    bgra = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra


def draw_numbered(image, nails):
    """画编号预览：每个甲面半透明上色 + 大数字 + 自动猜测的手指名。"""
    vis = image.copy()
    rng = np.random.default_rng(7)
    for idx, n in enumerate(nails):
        color = rng.integers(60, 255, size=3).tolist()
        vis[n["mask"]] = (0.45 * np.array(color) + 0.55 * vis[n["mask"]]).astype(np.uint8)
        if n["contour"] is not None:
            cv2.drawContours(vis, [n["contour"]], -1, color, 2)
        cx, cy = int(n["centroid"][0]), int(n["centroid"][1])
        fi = n["finger_idx"]
        guess = FINGER_NAMES[fi] if 0 <= fi < 5 else "?"
        # 大编号
        cv2.putText(vis, str(idx), (cx - 18, cy + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 7)
        cv2.putText(vis, str(idx), (cx - 18, cy + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.4, color, 3)
        # 小字：自动猜测
        cv2.putText(vis, guess, (cx - 30, cy + 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(vis, guess, (cx - 30, cy + 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
    return vis


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(DESIGNS)
    import nail_seg

    auto_labels = {}
    for d in DESIGNS[:limit]:
        did = d["id"]
        img = imread_unicode(ROOT / d["image"])
        if img is None:
            print(f"{did}: ❌ 读取失败")
            continue

        nails = nail_seg.segment_nails(img)
        nails = stable_order(nails)

        # 编号预览
        imwrite_unicode(PREVIEW_DIR / f"{did}.jpg", draw_numbered(img, nails))

        # 编号原料 —— 旋转校正成"指尖朝上"的标准姿态后存储
        out_dir = RAW_DIR / did
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
        for idx, n in enumerate(nails):
            bgra = _extract_upright_mold(img, n)
            imwrite_unicode(out_dir / f"{idx}.png", bgra)

        # 自动猜测标注
        entry = {"_name": d["name"]}
        for idx, n in enumerate(nails):
            fi = n["finger_idx"]
            entry[str(idx)] = FINGER_NAMES[fi] if 0 <= fi < 5 else "?"
        auto_labels[did] = entry

        guesses = " ".join(f"{i}={entry[str(i)]}" for i in range(len(nails)))
        print(f"{did} ({d['name']}): {len(nails)} 个指甲 | {guesses}")

    # 写自动标注（每次覆盖）
    AUTO_LABELS.write_text(json.dumps(auto_labels, ensure_ascii=False, indent=2), encoding="utf-8")

    # 首次：复制成用户可编辑版；已存在则保留用户编辑
    if not USER_LABELS.exists():
        shutil.copy(AUTO_LABELS, USER_LABELS)
        note = "（已创建，请编辑此文件）"
    else:
        note = "（已存在，保留你的编辑，未覆盖）"

    print("\n" + "=" * 60)
    print(f"编号预览: {PREVIEW_DIR}")
    print(f"自动猜测: {AUTO_LABELS.name}")
    print(f"你要编辑: {USER_LABELS.name} {note}")
    print("\n下一步：对照预览图编辑 molds_labels.json，把每个数字标成正确手指")
    print("（thumb/index/middle/ring/pinky，误检或多余的填 skip），")
    print("然后运行 python apply_labels.py 生成最终模具库。")


if __name__ == "__main__":
    main()

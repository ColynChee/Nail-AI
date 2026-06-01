"""从款式图裁出指甲区域，生成款式缩略图。

对每个款式图:
  1) 跑 YOLO 检测所有指甲 bounding-box
  2) 合并所有 bbox → 加适量 padding → 裁剪
  3) 缩放到 420×300，保持比例，四周补白
  4) 保存到 ../缩略图/<design_id>.png

用法:
  python build_thumbnails.py        # 全部 25 个
  python build_thumbnails.py 3      # 只前 3 个
"""
import sys, json, cv2
from pathlib import Path
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

BACKEND  = Path(__file__).resolve().parent
ROOT     = BACKEND.parent
THUMB_DIR = ROOT / "缩略图"
THUMB_DIR.mkdir(exist_ok=True)

DESIGNS = json.loads((BACKEND / "designs.json").read_text(encoding="utf-8"))["designs"]

# 缩略图目标尺寸
TW, TH = 420, 300
PAD_FRAC = 0.12        # bbox 外扩比例


def imread_unicode(path):
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def get_nail_crop(img: np.ndarray):
    """用 YOLO 找指甲区域，返回裁剪后的 BGR 图。失败则返回居中缩放的原图。"""
    from nail_seg import get_seg_model
    h, w = img.shape[:2]
    model = get_seg_model()
    results = model.predict(img, conf=0.20, verbose=False, device="cpu")
    r = results[0]

    boxes = []
    if r.masks is not None and len(r.masks) > 0:
        masks = r.masks.data.cpu().numpy()
        for m in masks:
            m_full = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST) > 0.5
            ys, xs = np.where(m_full)
            if len(xs) < 20:
                continue
            boxes.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))

    if not boxes:
        return img  # 兜底：返回原图

    # 合并所有 bbox
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)

    # 外扩 padding
    bw, bh = x1 - x0, y1 - y0
    pad_x = int(bw * PAD_FRAC)
    pad_y = int(bh * PAD_FRAC)
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(w - 1, x1 + pad_x)
    y1 = min(h - 1, y1 + pad_y)

    return img[y0:y1+1, x0:x1+1]


def fit_to_canvas(img: np.ndarray, tw: int, th: int) -> np.ndarray:
    """把图缩放进 (tw, th) 的白底画布，保持纵横比，居中放置。"""
    h, w = img.shape[:2]
    scale = min(tw / w, th / h)
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

    canvas = np.full((th, tw, 3), 255, dtype=np.uint8)
    x_off = (tw - nw) // 2
    y_off = (th - nh) // 2
    canvas[y_off:y_off+nh, x_off:x_off+nw] = resized
    return canvas


def build_thumbnail(design: dict) -> bool:
    img_path = ROOT / design["image"]
    img = imread_unicode(str(img_path))
    if img is None:
        return False

    cropped = get_nail_crop(img)
    thumb = fit_to_canvas(cropped, TW, TH)

    out = THUMB_DIR / f"{design['id']}.png"
    ok, buf = cv2.imencode(".png", thumb, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if ok:
        buf.tofile(str(out))
    return ok


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(DESIGNS)
    ok = 0
    for d in DESIGNS[:limit]:
        success = build_thumbnail(d)
        print(f"{d['id']} ({d['name']}): {'✅' if success else '❌'}")
        if success:
            ok += 1
    print(f"\n完成: {ok}/{limit} 个缩略图 → {THUMB_DIR}")


if __name__ == "__main__":
    main()

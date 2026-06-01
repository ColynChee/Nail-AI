"""阶段 3: 路线 A 试戴合成器（模具贴图版）。

流程:
  用户手图 → YOLO 分割每个指甲 + finger_idx (nail_seg)
          → 取款式模具 molds/<design_id>/<finger_idx>.png
          → 透视变换把模具贴到用户该指甲的精确 mask
          → LAB 光影融合(保留用户手明暗) + 边缘羽化
          → 缺指模具用对称补全
          → 输出 BGR 结果

与旧 nail_overlay.py 并存，不互相影响。
"""
import os
from typing import Dict, List, Optional, Tuple
import numpy as np
import cv2

import nail_seg

BACKEND = os.path.dirname(os.path.abspath(__file__))
MOLDS_DIR = os.path.join(BACKEND, "molds")

# 缺指时的补全来源：缺某指 → 优先用哪个相邻指的模具(镜像)
_FALLBACK_ORDER = {
    0: [1, 2],      # thumb 缺 → 用 index/middle
    1: [2, 0],      # index 缺 → 用 middle/thumb
    2: [1, 3],      # middle 缺 → 用 index/ring
    3: [2, 4],      # ring 缺 → 用 middle/pinky
    4: [3, 2],      # pinky 缺 → 用 ring/middle
}


def _imread_unicode(path, flags=cv2.IMREAD_COLOR):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, flags)


def load_molds(design_id: str) -> Dict[int, np.ndarray]:
    """加载某款式的所有指甲模具 {finger_idx: BGRA}，并对缺指做镜像补全。"""
    d = os.path.join(MOLDS_DIR, design_id)
    molds: Dict[int, np.ndarray] = {}
    if os.path.isdir(d):
        for fi in range(5):
            p = os.path.join(d, f"{fi}.png")
            if os.path.exists(p):
                molds[fi] = _imread_unicode(p, cv2.IMREAD_UNCHANGED)

    # 缺指补全：用相邻指的模具水平镜像
    for fi in range(5):
        if fi in molds:
            continue
        for src in _FALLBACK_ORDER[fi]:
            if src in molds:
                molds[fi] = cv2.flip(molds[src], 1)  # 水平镜像
                break
    return molds


def _nail_geometry(mask: np.ndarray, tip_angle: float) -> Tuple[Tuple[float, float], float, float]:
    """按"实际贴图角度 tip_angle"测量指甲几何，保证 L/W/center 与放置角度严格一致。

    把 mask 像素投影到 (指尖方向 u, 垂直方向 v)，量两个方向的跨度：
      - L = u 方向跨度（指甲长）
      - W = v 方向跨度（指甲宽）
      - center = 两方向跨度中点（比质心更贴合外接，定位更稳）
    用 5~95 百分位剔除 YOLO mask 边缘毛刺/锯齿的影响。
    """
    ys, xs = np.where(mask)
    if len(xs) < 5:
        return (float(xs.mean()) if len(xs) else 0.0,
                float(ys.mean()) if len(ys) else 0.0), 4.0, 3.0

    a = np.radians(tip_angle)
    ux, uy = np.cos(a), np.sin(a)        # 指尖方向
    vx, vy = -np.sin(a), np.cos(a)       # 垂直方向

    pu = xs * ux + ys * uy               # 沿指尖方向的投影
    pv = xs * vx + ys * vy               # 沿垂直方向的投影

    # 5~95 百分位，抗毛刺
    u_lo, u_hi = np.percentile(pu, 3), np.percentile(pu, 97)
    v_lo, v_hi = np.percentile(pv, 3), np.percentile(pv, 97)
    L = float(u_hi - u_lo)
    W = float(v_hi - v_lo)
    u_mid = (u_lo + u_hi) / 2.0
    v_mid = (v_lo + v_hi) / 2.0
    # 由 (u_mid, v_mid) 反算回图像坐标 (u,v 正交基)
    cx = u_mid * ux + v_mid * vx
    cy = u_mid * uy + v_mid * vy
    return (float(cx), float(cy)), max(L, 4.0), max(W, 3.0)


def _standard_nail_shape(h: int, w: int, shape_type: str = "oval",
                         length_ratio: float = 1.0, width_ratio: float = 1.0,
                         margin_frac: float = 0.07) -> np.ndarray:
    """生成参数化甲形灰度 mask。

    Args:
        shape_type: "oval"(椭圆) / "almond"(尖形) / "square"(方形)
        length_ratio: 长度系数 0.5-1.5（1.0=标准）
        width_ratio: 宽度系数 0.5-1.5（1.0=标准）
    """
    m = np.zeros((h, w), np.uint8)
    mx = int(round(w * margin_frac))
    my = int(round(h * margin_frac))
    x0, y0, x1, y1 = mx, my, w - mx, h - my
    bw, bh = x1 - x0, y1 - y0
    if bw <= 2 or bh <= 2:
        m[:] = 255
        return m

    # 应用长宽系数
    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    adj_bw = bw * width_ratio
    adj_bh = bh * length_ratio
    adj_x0 = center_x - adj_bw / 2.0
    adj_x1 = center_x + adj_bw / 2.0
    adj_y0 = center_y - adj_bh / 2.0
    adj_y1 = center_y + adj_bh / 2.0

    if shape_type == "almond":
        # 尖形：指尖极度尖锐，用完整椭圆实现
        cx = (adj_x0 + adj_x1) / 2.0
        cy = (adj_y0 + adj_y1) / 2.0

        # 用椭圆表示整个指甲：宽度=指甲宽，高度=指甲长
        # 这样可以自然形成尖形（指尖尖，指根圆）
        axes_w = int(adj_bw / 2.0)
        axes_h = int(adj_bh / 2.0)

        # 绘制完整椭圆（0-360度）
        cv2.ellipse(m, (int(cx), int(cy)), (axes_w, axes_h), 0, 0, 360, 255, -1)

    elif shape_type == "square":
        # 方形：指尖和指根都方
        rt = max(1, int(min(adj_bw, adj_bh) * 0.15))  # 指尖端方
        rb = max(1, int(min(adj_bw, adj_bh) * 0.15))  # 指根端方

        # 中间主体矩形
        cv2.rectangle(m, (int(adj_x0), int(adj_y0 + rt)), (int(adj_x1), int(adj_y1 - rb)), 255, -1)
        cv2.rectangle(m, (int(adj_x0 + rt), int(adj_y0)), (int(adj_x1 - rt), int(adj_y1)), 255, -1)
        # 指尖端两角(顶部)
        cv2.circle(m, (int(adj_x0 + rt), int(adj_y0 + rt)), rt, 255, -1)
        cv2.circle(m, (int(adj_x1 - rt), int(adj_y0 + rt)), rt, 255, -1)
        # 指根端两角(底部)
        cv2.circle(m, (int(adj_x0 + rb), int(adj_y1 - rb)), rb, 255, -1)
        cv2.circle(m, (int(adj_x1 - rb), int(adj_y1 - rb)), rb, 255, -1)

    else:  # "oval" 默认
        # 椭圆形：均衡
        rt = max(1, int(min(adj_bw, adj_bh) * 0.45))  # 指尖端圆
        rb = max(1, int(min(adj_bw, adj_bh) * 0.30))  # 指根端略方

        # 中间主体矩形
        cv2.rectangle(m, (int(adj_x0), int(adj_y0 + rt)), (int(adj_x1), int(adj_y1 - rb)), 255, -1)
        cv2.rectangle(m, (int(adj_x0 + rt), int(adj_y0)), (int(adj_x1 - rt), int(adj_y1)), 255, -1)
        # 指尖端两角(顶部)
        cv2.circle(m, (int(adj_x0 + rt), int(adj_y0 + rt)), rt, 255, -1)
        cv2.circle(m, (int(adj_x1 - rt), int(adj_y0 + rt)), rt, 255, -1)
        # 指根端两角(底部)
        cv2.circle(m, (int(adj_x0 + rb), int(adj_y1 - rb)), rb, 255, -1)
        cv2.circle(m, (int(adj_x1 - rb), int(adj_y1 - rb)), rb, 255, -1)
    return m


def _warp_mold_to_nail(mold_bgra: np.ndarray, dst_mask: np.ndarray,
                        centroid: Tuple[float, float], tip_angle: float,
                        out_h: int, out_w: int, shape_type: str = "oval",
                        length_ratio: float = 1.0, width_ratio: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """把"指尖朝上"的标准模具按用户手指真实角度(tip_angle)对齐贴上。

    改进：保留设计指甲的长宽比，优先适应用户指甲的长度而不是简单裁剪。
    """
    mh, mw = mold_bgra.shape[:2]
    (cx, cy), L, W = _nail_geometry(dst_mask, tip_angle)

    # 计算设计指甲的长宽比（长/宽）
    design_aspect = mh / mw if mw > 0 else 1.0

    # 完全保留设计的长宽比，按用户指甲宽度来缩放
    # 这样可以展示完整的设计效果，即使超过用户指甲长度也没关系
    W_target = W  # 用户指甲的宽度
    L_target = W * design_aspect  # 按设计比例计算长度

    a = np.radians(tip_angle)
    tip_dir = np.array([np.cos(a), np.sin(a)], dtype=np.float32)
    perp_dir = np.array([-np.sin(a), np.cos(a)], dtype=np.float32)

    src = np.array([
        [mw / 2.0, mh / 2.0],
        [mw / 2.0, 0.0],
        [mw, mh / 2.0],
    ], dtype=np.float32)
    cover = 1.15
    half_L = L_target / 2.0 * cover
    half_W = W_target / 2.0 * cover
    center = np.array([cx, cy], dtype=np.float32)
    dst = np.array([
        center,
        center - tip_dir * half_L,
        center + perp_dir * half_W,
    ], dtype=np.float32)

    M = cv2.getAffineTransform(src, dst)

    # 预乘 alpha 再 warp，防止模具透明边缘的暗像素在插值时渗入纹理
    mold_a = mold_bgra[:, :, 3:4].astype(np.float32) / 255.0
    premult = (mold_bgra[:, :, :3].astype(np.float32) * mold_a).astype(np.uint8)
    warped_premult = cv2.warpAffine(premult, M, (out_w, out_h),
                                    flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    warped_mold_a = cv2.warpAffine(mold_bgra[:, :, 3], M, (out_w, out_h),
                                   flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    # 反预乘恢复 straight-alpha BGR（低 alpha 区域用 REFLECT 纹理填充避免黑块）
    wa = warped_mold_a.astype(np.float32) / 255.0
    warped_bgr_f = np.where(wa[:, :, None] > 0.05,
                            warped_premult.astype(np.float32) / (wa[:, :, None] + 1e-6),
                            warped_premult.astype(np.float32))
    # 低 alpha 区域改用 REFLECT 直接 warp BGR（保证纹理连续不出黑块）
    warped_bgr_reflect = cv2.warpAffine(mold_bgra[:, :, :3], M, (out_w, out_h),
                                        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    low_a = wa < 0.05
    warped_bgr_f[low_a] = warped_bgr_reflect.astype(np.float32)[low_a]
    warped_bgr = np.clip(warped_bgr_f, 0, 255).astype(np.uint8)

    # 用参数化的甲形来约束位置，同时保留设计纹理
    # 这样既能确保位置准确，又能展示设计效果
    shape = _standard_nail_shape(mh, mw, shape_type=shape_type,
                                 length_ratio=length_ratio, width_ratio=width_ratio)
    shape_w = cv2.warpAffine(shape, M, (out_w, out_h),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    # 加强腐蚀和羽化，让边界更柔和透明
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    shape_w = cv2.erode(shape_w, kernel, iterations=2)
    # 用更大的高斯模糊来柔化边缘，减少模板的明显感
    warped_alpha = cv2.GaussianBlur(shape_w.astype(np.float32) / 255.0, (11, 11), 3.0)
    return warped_bgr, warped_alpha


def _hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    hx = hex_color.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return (b, g, r)


def dominant_color(design_id: str) -> Optional[str]:
    """从款式模具提取主色(中指优先)，返回 hex。供前端色板默认值。"""
    molds = load_molds(design_id)
    if not molds:
        return None
    mold = molds.get(2) or next(iter(molds.values()))
    bgr = mold[:, :, :3]
    alpha = mold[:, :, 3] > 127
    if alpha.sum() < 10:
        return None
    px = bgr[alpha].reshape(-1, 3)
    # 取中位数(抗高光/暗边),再转 hex
    b, g, r = [int(np.median(px[:, i])) for i in range(3)]
    return f"#{r:02X}{g:02X}{b:02X}"


def _solid_color_alpha(dst_mask: np.ndarray, tip_angle: float,
                       out_h: int, out_w: int) -> np.ndarray:
    """生成纯色款的标准甲形 alpha(不取模具，纯几何)，位置/角度/尺寸对齐用户指甲。"""
    (cx, cy), L, W = _nail_geometry(dst_mask, tip_angle)
    a = np.radians(tip_angle)
    tip_dir = np.array([np.cos(a), np.sin(a)], dtype=np.float32)
    perp_dir = np.array([-np.sin(a), np.cos(a)], dtype=np.float32)

    canvas = 200
    shape = _standard_nail_shape(canvas, canvas)
    src = np.array([
        [canvas / 2.0, canvas / 2.0],
        [canvas / 2.0, 0.0],
        [canvas, canvas / 2.0],
    ], dtype=np.float32)
    cover = 1.12
    center = np.array([cx, cy], dtype=np.float32)
    dst = np.array([
        center,
        center - tip_dir * (L / 2.0 * cover),
        center + perp_dir * (W / 2.0 * cover),
    ], dtype=np.float32)
    M = cv2.getAffineTransform(src, dst)
    shape_w = cv2.warpAffine(shape, M, (out_w, out_h), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT)
    alpha = cv2.GaussianBlur(shape_w.astype(np.float32) / 255.0, (5, 5), 1.5)
    return alpha


def _draw_glossy_highlight(alpha: np.ndarray, tip_angle: float) -> np.ndarray:
    """在甲形内画一道竖直高光条(沿手指方向)，返回 0~1 加光强度图。"""
    h, w = alpha.shape
    ys, xs = np.where(alpha > 0.5)
    if len(xs) < 10:
        return np.zeros_like(alpha)
    cx, cy = xs.mean(), ys.mean()
    a = np.radians(tip_angle)
    perp = np.array([-np.sin(a), np.cos(a)])
    # 高光位于甲面偏一侧
    hx = cx + perp[0] * (xs.std() * 0.5)
    hy = cy + perp[1] * (xs.std() * 0.5)
    gloss = np.zeros_like(alpha)
    cv2.circle(gloss, (int(hx), int(hy)), max(3, int(xs.std() * 0.35)), 1.0, -1)
    gloss = cv2.GaussianBlur(gloss, (0, 0), xs.std() * 0.3 + 2)
    gloss = gloss / (gloss.max() + 1e-6) * (alpha > 0.5)
    return gloss


def _blend_lab(base_bgr: np.ndarray, tex_bgr: np.ndarray, alpha: np.ndarray,
               shading_strength: float = 0.20) -> np.ndarray:
    """LAB 融合：用模具的颜色(A,B)+模具明度被用户手相对光影调制。
    保留真实感的同时贴合用户手的光照。"""
    base_lab = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    tex_lab = cv2.cvtColor(tex_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    mask_bool = alpha > 0.05
    if np.any(mask_bool):
        user_L_mean = float(np.mean(base_lab[:, :, 0][mask_bool]))
        user_L_mean = max(user_L_mean, 1.0)
        rel = np.clip(base_lab[:, :, 0] / user_L_mean - 1.0, -0.25, 0.25)
        shading = 1.0 + rel * shading_strength
    else:
        shading = np.ones_like(base_lab[:, :, 0])

    new_L = np.clip(tex_lab[:, :, 0] * shading, 0, 255)
    a = alpha
    out = base_lab.copy()
    out[:, :, 0] = base_lab[:, :, 0] * (1 - a) + new_L * a
    out[:, :, 1] = base_lab[:, :, 1] * (1 - a) + tex_lab[:, :, 1] * a
    out[:, :, 2] = base_lab[:, :, 2] * (1 - a) + tex_lab[:, :, 2] * a
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def try_on(user_bgr: np.ndarray, design_id: str, color: Optional[str] = None,
           shape_type: str = "oval", length_ratio: float = 1.0, width_ratio: float = 1.0) -> Dict:
    """试戴主入口。
    - color 给定(hex,如'#A8B04D') → 纯色合成模式：干净甲形+纯色+高光，可任意换色
    - color 为 None → 模具贴图模式(图案款)
    - shape_type: "oval"(椭圆) / "almond"(尖形) / "square"(方形)
    - length_ratio / width_ratio: 0.5-1.5 的长宽系数
    返回 {success, image(BGR), n_applied, mode, ...}
    """
    nails = nail_seg.segment_nails(user_bgr)
    nails = [n for n in nails if n["finger_idx"] >= 0]
    if not nails:
        return {"success": False, "error": "未检测到指甲", "image": user_bgr}

    h, w = user_bgr.shape[:2]
    acc_tex = np.zeros((h, w, 3), dtype=np.float32)
    acc_alpha = np.zeros((h, w), dtype=np.float32)
    acc_gloss = np.zeros((h, w), dtype=np.float32)

    # 优先用模具贴图，如果模具缺失且有颜色就用纯色模式
    molds = load_molds(design_id)
    has_molds = molds and len(molds) > 0

    if has_molds:
        # ── 模具贴图模式(图案款) ──
        print(f"[TryOn] 模具贴图模式, shape_type={shape_type}, length_ratio={length_ratio}, width_ratio={width_ratio}")
        n_applied = 0
        for n in nails:
            mold = molds.get(n["finger_idx"])
            if mold is None:
                continue
            ta = n.get("tip_angle", -90.0)
            print(f"[TryOn] 贴模具到指甲 {n['finger_idx']}, 甲形参数: shape={shape_type}, len={length_ratio}, w={width_ratio}")
            warped_bgr, warped_alpha = _warp_mold_to_nail(
                mold, n["mask"], n["centroid"], ta, h, w,
                shape_type=shape_type, length_ratio=length_ratio, width_ratio=width_ratio)
            m3 = warped_alpha[:, :, None]
            acc_tex = acc_tex * (1 - m3) + warped_bgr.astype(np.float32) * m3
            acc_alpha = np.maximum(acc_alpha, warped_alpha)
            acc_gloss = np.maximum(acc_gloss, _draw_glossy_highlight(warped_alpha, ta))
            n_applied += 1
        mode = "pattern"
    elif color is not None:
        # ── 纯色模式（模具缺失时用颜色）──
        print(f"[TryOn] 纯色模式, color={color}, shape_type={shape_type}, length_ratio={length_ratio}, width_ratio={width_ratio}")
        bgr = np.array(_hex_to_bgr(color), dtype=np.float32)
        for n in nails:
            ta = n.get("tip_angle", -90.0)
            alpha = _solid_color_alpha(n["mask"], ta, h, w)
            m3 = alpha[:, :, None]
            acc_tex = acc_tex * (1 - m3) + bgr * m3
            acc_alpha = np.maximum(acc_alpha, alpha)
            acc_gloss = np.maximum(acc_gloss, _draw_glossy_highlight(alpha, ta))
        n_applied = len(nails)
        mode = "solid"
    else:
        return {"success": False, "error": f"款式 {design_id} 无模具且未指定颜色", "image": user_bgr}

    result = _blend_lab(user_bgr, acc_tex.astype(np.uint8), acc_alpha, shading_strength=0.30)
    # 模具贴图模式叠加高光
    if acc_gloss.max() > 0:
        gloss_strength = 45  # 模具贴图模式
        g = (acc_gloss * gloss_strength)[:, :, None]
        result = np.clip(result.astype(np.float32) + g, 0, 255).astype(np.uint8)

    return {
        "success": True,
        "image": result,
        "n_applied": n_applied,
        "n_nails": len(nails),
        "mode": mode,
    }

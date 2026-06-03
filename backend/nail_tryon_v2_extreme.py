"""Phase 2实验版本：极端点对齐试戴合成器。

核心改进：使用指甲极端点(指尖、指根)精确对齐，而非仅基于角度和尺寸。
创建于：2026-06-02  目的：测试极端点对齐是否比角度对齐更好
对比对象：nail_tryon_v2.py (原版角度对齐)

两个入口函数：
  try_on_extreme() - Phase 2 极端点对齐版
  try_on_original() - 原版角度对齐(用于对比)
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


def _get_nail_extremes(mask: np.ndarray, tip_angle: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """优化版 v2：多点采样宽度检测（更稳健）。

    原理：
    1. 沿长轴多点采样，测量每个位置的宽度
    2. 找出宽度递减的方向（从指根→指尖）
    3. 选择宽度和变化趋势最符合的方向

    返回 (tip_point, root_point) - 指尖和指根的坐标。
    """
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return (0.0, 0.0), (0.0, 0.0)

    pts = np.column_stack([xs, ys]).astype(np.float32)
    h, w = mask.shape

    # 用 PCA 找指甲的主轴方向（长轴）
    center = np.mean(pts, axis=0)
    pts_centered = pts - center
    cov = np.cov(pts_centered.T)
    eigenvalues, eigenvectors = np.linalg.eig(cov)
    main_axis = eigenvectors[:, np.argmax(eigenvalues)]
    perp_axis = eigenvectors[:, np.argmin(eigenvalues)]  # 垂直轴

    # 沿长轴投影找两个极端点
    projections = pts_centered @ main_axis
    extreme_idx1 = np.argmax(projections)
    extreme_idx2 = np.argmin(projections)

    point1 = pts[extreme_idx1]
    point2 = pts[extreme_idx2]

    # 用 tip_angle 来指导指根/指尖识别（不再依赖宽度检测）
    # 计算两个极端点相对于掌心的方向角度
    center = pts[extreme_idx1] + pts[extreme_idx2]
    center = center / 2.0  # 两点的中点作为参考

    # 向量：从掌心指向两个极端点
    vec1 = point1 - center
    vec2 = point2 - center

    # 计算这两个向量的角度
    angle1 = float(np.degrees(np.arctan2(vec1[1], vec1[0])))
    angle2 = float(np.degrees(np.arctan2(vec2[1], vec2[0])))

    # 角度差值（标准化到 [-180, 180]）
    def angle_diff(a1, a2):
        diff = a1 - a2
        while diff > 180: diff -= 360
        while diff < -180: diff += 360
        return abs(diff)

    diff1 = angle_diff(angle1, tip_angle)
    diff2 = angle_diff(angle2, tip_angle)

    # 选择方向更接近 tip_angle 的点作为指尖
    if diff1 < diff2:
        tip_point = tuple(point1.astype(float))
        root_point = tuple(point2.astype(float))
    else:
        tip_point = tuple(point2.astype(float))
        root_point = tuple(point1.astype(float))

    print(f"[_get_nail_extremes] tip_angle={tip_angle:.1f}°, angle1={angle1:.1f}° (diff={diff1:.1f}), angle2={angle2:.1f}° (diff={diff2:.1f})")
    print(f"[_get_nail_extremes] 选择: tip={tip_point}, root={root_point}")

    return tip_point, root_point


def _get_mold_extremes(mold_bgra: np.ndarray) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """计算模具的指尖和指根位置。

    约定：指根在上(Y=0)，指尖在下(Y=height)
    返回 (tip_point, root_point)。
    """
    h, w = mold_bgra.shape[:2]
    # 模具的顶部中心（指根）
    root_point = (w / 2.0, 0.0)
    # 模具的底部中心（指尖）
    tip_point = (w / 2.0, float(h))

    return tip_point, root_point


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


def _evaluate_warp_quality(warped_alpha: np.ndarray, dst_mask: np.ndarray) -> float:
    """评估贴图质量：计算 alpha 覆盖 mask 的比例（0-1）。
    越高越好，说明模具很好地覆盖了指甲区域。"""
    if warped_alpha.max() < 0.01 or dst_mask.sum() == 0:
        return 0.0
    # 计算 warped_alpha 和 dst_mask 的重叠部分
    overlap = (warped_alpha > 0.5).astype(np.uint8) * dst_mask.astype(np.uint8)
    coverage = float(overlap.sum()) / max(dst_mask.sum(), 1)
    return coverage


def _warp_mold_to_nail_multiangle(mold_bgra: np.ndarray, dst_mask: np.ndarray,
                                   centroid: Tuple[float, float], tip_angle: float,
                                   out_h: int, out_w: int, shape_type: str = "oval",
                                   length_ratio: float = 1.0, width_ratio: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """多角度匹配版本：尝试多个旋转角度，选择最佳匹配。

    这会提高质量但降低速度（尝试 7 个角度）。"""
    angles_to_try = np.linspace(-30, 30, 7)  # -30, -20, -10, 0, 10, 20, 30 度

    best_result = None
    best_score = -1.0
    best_angle = tip_angle

    for angle_offset in angles_to_try:
        test_angle = tip_angle + angle_offset
        warped_bgr, warped_alpha = _warp_mold_to_nail(
            mold_bgra, dst_mask, centroid, test_angle,
            out_h, out_w, shape_type, length_ratio, width_ratio
        )

        # 评估质量
        score = _evaluate_warp_quality(warped_alpha, dst_mask)

        if score > best_score:
            best_score = score
            best_result = (warped_bgr, warped_alpha)
            best_angle = test_angle

    if best_result is None:
        # 降级：使用原始角度
        best_result = _warp_mold_to_nail(
            mold_bgra, dst_mask, centroid, tip_angle,
            out_h, out_w, shape_type, length_ratio, width_ratio
        )

    return best_result


def _warp_mold_to_nail_extreme(mold_bgra: np.ndarray, dst_mask: np.ndarray,
                               tip_angle: float, out_h: int, out_w: int,
                               shape_type: str = "oval",
                               length_ratio: float = 1.0, width_ratio: float = 1.0,
                               standard_width: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray]:
    """极端点对齐版本（约束方向）。

    使用指甲的指尖和指根两个极端点进行精确对齐，而不是基于角度和中心点。

    约定约束：
    - 所有指甲：指根在上(Y=0)，指尖在下(Y=height)
    - 所有模具：指根在上(Y=0)，指尖在下(Y=height)
    - 通过 _get_nail_extremes() 自动检测用户指甲的方向
    - 通过 _get_mold_extremes() 定义模具的标准方向

    Args:
        standard_width: 所有指甲的统一宽度。如果为None，使用该指甲的实际宽度。
    """
    mh, mw = mold_bgra.shape[:2]

    # 获取极端点
    user_tip, user_root = _get_nail_extremes(dst_mask, tip_angle)
    mold_tip, mold_root = _get_mold_extremes(mold_bgra)

    print(f"[_warp_mold_to_nail_extreme] tip_angle={tip_angle:.1f}°")
    print(f"[_warp_mold_to_nail_extreme] user_tip={user_tip}, user_root={user_root}")
    print(f"[_warp_mold_to_nail_extreme] mold_tip={mold_tip}, mold_root={mold_root}")

    # 直接对齐（无需双向尝试，因为方向已被约束）
    return _warp_mold_extreme_direction(
        mold_bgra, dst_mask, user_tip, user_root,
        mold_tip, mold_root, tip_angle, out_h, out_w,
        shape_type, length_ratio, width_ratio, standard_width,
        flip=False)


def _warp_mold_extreme_direction(mold_bgra: np.ndarray, dst_mask: np.ndarray,
                                  user_tip: Tuple[float, float], user_root: Tuple[float, float],
                                  mold_tip: Tuple[float, float], mold_root: Tuple[float, float],
                                  tip_angle: float, out_h: int, out_w: int,
                                  shape_type: str = "oval",
                                  length_ratio: float = 1.0, width_ratio: float = 1.0,
                                  standard_width: Optional[float] = None,
                                  flip: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """执行极端点对齐变换。

    将模具按照用户指甲的指尖/指根位置进行透视变换贴图。
    """
    mh, mw = mold_bgra.shape[:2]

    (cx, cy), L, W = _nail_geometry(dst_mask, tip_angle)
    # 缩小宽度以适配真实指甲大小（YOLO mask 通常过大）
    W_adjusted = W * 0.75  # 宽度缩小到 75%
    W_target = standard_width if standard_width is not None else W_adjusted

    # 计算指甲方向向量（从指根到指尖）
    user_dir = np.array(user_tip) - np.array(user_root)
    user_dir_len = np.linalg.norm(user_dir)
    if user_dir_len < 1e-6:
        user_dir = np.array([0.0, -1.0])
    else:
        user_dir = user_dir / user_dir_len

    user_perp = np.array([-user_dir[1], user_dir[0]])

    half_W = W_target / 2.0
    user_tip_arr = np.array(user_tip, dtype=np.float32)
    user_root_arr = np.array(user_root, dtype=np.float32)

    dst = np.array([
        user_tip_arr - user_perp * half_W,
        user_tip_arr + user_perp * half_W,
        user_root_arr - user_perp * half_W,
        user_root_arr + user_perp * half_W,
    ], dtype=np.float32)

    # 质心对齐：把4个角点整体平移，使中心对准YOLO检测到的质心(cx,cy)
    current_center = (user_tip_arr + user_root_arr) / 2.0
    target_center = np.array([cx, cy], dtype=np.float32)
    offset = target_center - current_center
    dst += offset

    mold_tip_arr = np.array(mold_tip, dtype=np.float32)
    mold_root_arr = np.array(mold_root, dtype=np.float32)
    half_mold_w = mw / 2.0

    src = np.array([
        mold_tip_arr - np.array([half_mold_w, 0.0], dtype=np.float32),
        mold_tip_arr + np.array([half_mold_w, 0.0], dtype=np.float32),
        mold_root_arr - np.array([half_mold_w, 0.0], dtype=np.float32),
        mold_root_arr + np.array([half_mold_w, 0.0], dtype=np.float32),
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src, dst)

    mold_a = mold_bgra[:, :, 3:4].astype(np.float32) / 255.0
    premult = (mold_bgra[:, :, :3].astype(np.float32) * mold_a).astype(np.uint8)
    warped_premult = cv2.warpPerspective(premult, M, (out_w, out_h),
                                         flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    warped_mold_a = cv2.warpPerspective(mold_bgra[:, :, 3], M, (out_w, out_h),
                                        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    wa = warped_mold_a.astype(np.float32) / 255.0
    warped_bgr_f = np.where(wa[:, :, None] > 0.05,
                            warped_premult.astype(np.float32) / (wa[:, :, None] + 1e-6),
                            warped_premult.astype(np.float32))
    warped_bgr_reflect = cv2.warpPerspective(mold_bgra[:, :, :3], M, (out_w, out_h),
                                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    low_a = wa < 0.05
    warped_bgr_f[low_a] = warped_bgr_reflect.astype(np.float32)[low_a]
    warped_bgr = np.clip(warped_bgr_f, 0, 255).astype(np.uint8)

    shape = _standard_nail_shape(mh, mw, shape_type=shape_type,
                                 length_ratio=length_ratio, width_ratio=width_ratio)
    shape_w = cv2.warpPerspective(shape, M, (out_w, out_h),
                                  flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    shape_w = cv2.erode(shape_w, kernel, iterations=1)
    warped_alpha = cv2.GaussianBlur(shape_w.astype(np.float32) / 255.0, (7, 7), 1.5)
    return warped_bgr, warped_alpha


def _warp_mold_to_nail(mold_bgra: np.ndarray, dst_mask: np.ndarray,
                        centroid: Tuple[float, float], tip_angle: float,
                        out_h: int, out_w: int, shape_type: str = "oval",
                        length_ratio: float = 1.0, width_ratio: float = 1.0,
                        use_extreme_alignment: bool = False,
                        standard_width: Optional[float] = None) -> Tuple[np.ndarray, np.ndarray]:
    """把"指尖朝上"的标准模具按用户手指真实角度(tip_angle)对齐贴上。

    改进：
    - 如果 use_extreme_alignment=True，使用指甲极端点对齐（更精准）
    - 否则使用原有的角度对齐方法（备选）
    - 如果提供 standard_width，用于指甲大小归一化
    """
    if use_extreme_alignment:
        return _warp_mold_to_nail_extreme(mold_bgra, dst_mask, tip_angle, out_h, out_w,
                                         shape_type, length_ratio, width_ratio, standard_width)

    mh, mw = mold_bgra.shape[:2]
    (cx, cy), L, W = _nail_geometry(dst_mask, tip_angle)

    # 方案 C：归一化长度 - 所有指甲使用统一长度，只保留宽度差异
    UNIFIED_ASPECT = 1.6  # 统一的长宽比
    W_target = W  # 用户指甲的宽度
    L_target = W * UNIFIED_ASPECT  # 所有指甲使用相同的长宽比

    a = np.radians(tip_angle)
    tip_dir = np.array([np.cos(a), np.sin(a)], dtype=np.float32)
    perp_dir = np.array([-np.sin(a), np.cos(a)], dtype=np.float32)

    # 改进：使用 4 点透视变换而不是 3 点仿射变换，提高贴合精度
    # 模具的 4 个角点（标准位置：指尖向上，中心对齐）
    src = np.array([
        [0.0, 0.0],                    # 左上
        [mw, 0.0],                     # 右上
        [0.0, mh],                     # 左下
        [mw, mh],                      # 右下
    ], dtype=np.float32)

    cover = 1.0  # 精确贴合用户指甲大小（移除过度覆盖）
    half_L = L_target / 2.0 * cover
    half_W = W_target / 2.0 * cover
    center = np.array([cx, cy], dtype=np.float32)

    # 用户指甲的 4 个角点（基于指尖方向和垂直方向）
    dst = np.array([
        center - tip_dir * half_L - perp_dir * half_W,  # 左上（指尖左）
        center - tip_dir * half_L + perp_dir * half_W,  # 右上（指尖右）
        center + tip_dir * half_L - perp_dir * half_W,  # 左下（指根左）
        center + tip_dir * half_L + perp_dir * half_W,  # 右下（指根右）
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src, dst)

    # 预乘 alpha 再 warp，防止模具透明边缘的暗像素在插值时渗入纹理
    mold_a = mold_bgra[:, :, 3:4].astype(np.float32) / 255.0
    premult = (mold_bgra[:, :, :3].astype(np.float32) * mold_a).astype(np.uint8)
    warped_premult = cv2.warpPerspective(premult, M, (out_w, out_h),
                                         flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    warped_mold_a = cv2.warpPerspective(mold_bgra[:, :, 3], M, (out_w, out_h),
                                        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    # 反预乘恢复 straight-alpha BGR（低 alpha 区域用 REFLECT 纹理填充避免黑块）
    wa = warped_mold_a.astype(np.float32) / 255.0
    warped_bgr_f = np.where(wa[:, :, None] > 0.05,
                            warped_premult.astype(np.float32) / (wa[:, :, None] + 1e-6),
                            warped_premult.astype(np.float32))
    # 低 alpha 区域改用 REFLECT 直接 warp BGR（保证纹理连续不出黑块）
    warped_bgr_reflect = cv2.warpPerspective(mold_bgra[:, :, :3], M, (out_w, out_h),
                                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    low_a = wa < 0.05
    warped_bgr_f[low_a] = warped_bgr_reflect.astype(np.float32)[low_a]
    warped_bgr = np.clip(warped_bgr_f, 0, 255).astype(np.uint8)

    # 用参数化的甲形来约束位置，同时保留设计纹理
    # 这样既能确保位置准确，又能展示设计效果
    shape = _standard_nail_shape(mh, mw, shape_type=shape_type,
                                 length_ratio=length_ratio, width_ratio=width_ratio)
    shape_w = cv2.warpPerspective(shape, M, (out_w, out_h),
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
    # 改进：使用 4 点透视变换提高精度
    src = np.array([
        [0.0, 0.0],
        [canvas, 0.0],
        [0.0, canvas],
        [canvas, canvas],
    ], dtype=np.float32)
    cover = 1.12
    center = np.array([cx, cy], dtype=np.float32)
    dst = np.array([
        center - tip_dir * (L / 2.0 * cover) - perp_dir * (W / 2.0 * cover),
        center - tip_dir * (L / 2.0 * cover) + perp_dir * (W / 2.0 * cover),
        center + tip_dir * (L / 2.0 * cover) - perp_dir * (W / 2.0 * cover),
        center + tip_dir * (L / 2.0 * cover) + perp_dir * (W / 2.0 * cover),
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    shape_w = cv2.warpPerspective(shape, M, (out_w, out_h), flags=cv2.INTER_LINEAR,
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


def _feather_alpha(alpha: np.ndarray, radius: int = 3) -> np.ndarray:
    """对alpha边缘做高斯羽化，消除硬边。"""
    if radius <= 0:
        return alpha
    k = radius * 2 + 1
    blurred = cv2.GaussianBlur(alpha, (k, k), sigmaX=radius * 0.5)
    # 只在边缘区域混合：内部保持原值，仅边缘渐变
    edge_mask = (alpha > 0.05) & (alpha < 0.95)
    result = alpha.copy()
    result[edge_mask] = blurred[edge_mask]
    return result


def _blend_lab(base_bgr: np.ndarray, tex_bgr: np.ndarray, alpha: np.ndarray,
               shading_strength: float = 0.20) -> np.ndarray:
    """LAB 融合：边缘羽化 + 局部光影适配。"""
    # 边缘羽化：消除硬边
    alpha = _feather_alpha(alpha, radius=4)

    base_lab = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    tex_lab = cv2.cvtColor(tex_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    mask_bool = alpha > 0.05
    if np.any(mask_bool):
        # 局部光影：用模糊后的手部亮度图做局部相对值，而非全局均值
        # 这样能适应不均匀光照（一侧亮一侧暗）
        base_L = base_lab[:, :, 0]
        blur_radius = max(31, (base_L.shape[0] // 8) | 1)  # 奇数
        local_mean_L = cv2.GaussianBlur(base_L, (blur_radius, blur_radius), 0)
        local_mean_L = np.maximum(local_mean_L, 1.0)
        rel = np.clip(base_L / local_mean_L - 1.0, -0.35, 0.35)
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
           shape_type: str = "oval", length_ratio: float = 1.0, width_ratio: float = 1.0,
           use_extreme_alignment: bool = True, pre_nails: Optional[List[Dict]] = None,
           opacity: float = 0.85) -> Dict:
    """试戴主入口。
    - color 给定(hex,如'#A8B04D') → 纯色合成模式：干净甲形+纯色+高光，可任意换色
    - color 为 None → 模具贴图模式(图案款)
    - shape_type: "oval"(椭圆) / "almond"(尖形) / "square"(方形)
    - length_ratio / width_ratio: 0.5-1.5 的长宽系数
    - use_extreme_alignment: True使用极端点对齐(Phase 2), False使用角度对齐(原版)
    - pre_nails: 可选，预先处理的指甲数据（包含用户调整的角度）
    - opacity: 美甲不透明度 (0.0-1.0，默认 0.85；降低使透明度增加)
    返回 {success, image(BGR), n_applied, mode, ...}
    """
    # 如果提供了预处理的指甲数据，使用它；否则自动分割
    if pre_nails is not None:
        nails = pre_nails
        print(f"[TryOn] 使用预处理的指甲数据，共 {len(nails)} 个")
    else:
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
        align_mode = "极端点对齐" if use_extreme_alignment else "角度对齐"
        print(f"[TryOn] 模具贴图模式({align_mode}), shape_type={shape_type}, length_ratio={length_ratio}, width_ratio={width_ratio}")

        # 如果使用极端点对齐，先计算所有指甲的宽度中位数以实现大小归一化
        standard_width = None
        if use_extreme_alignment:
            widths = []
            for n in nails:
                mold = molds.get(n["finger_idx"])
                if mold is None:
                    continue
                ta = n.get("tip_angle", -90.0)
                (cx, cy), L, W = _nail_geometry(n["mask"], ta)
                # 应用相同的宽度缩放系数
                W_adjusted = W * 0.75
                widths.append(W_adjusted)

            if widths:
                standard_width = float(np.median(widths))
                print(f"[TryOn] 指甲宽度中位数(已缩放): {standard_width:.1f}px (用于大小归一化)")

        n_applied = 0
        for n in nails:
            mold = molds.get(n["finger_idx"])
            if mold is None:
                # 模具缺失时，用灰色代替（防止指甲被跳过）
                print(f"[TryOn] 警告: 指甲 {n['finger_idx']} 的模具缺失，用灰色代替")
                ta = n.get("tip_angle", -90.0)
                alpha = _solid_color_alpha(n["mask"], ta, h, w)
                m3 = alpha[:, :, None]
                gray_bgr = np.array([128, 128, 128], dtype=np.float32)
                acc_tex = acc_tex * (1 - m3) + gray_bgr * m3
                acc_alpha = np.maximum(acc_alpha, alpha)
                n_applied += 1
                continue
            ta = n.get("tip_angle", -90.0)

            # 握拳时反转 tip_angle
            if n.get("_is_fist", False):
                ta_orig = ta
                ta = (ta + 180) % 360
                print(f"[TryOn] 握拳反转: {ta_orig:.1f}° -> {ta:.1f}°")

            print(f"[TryOn] 贴模具到指甲 {n['finger_idx']}({align_mode}), tip_angle={ta:.1f}°, 甲形参数: shape={shape_type}, len={length_ratio}, w={width_ratio}, opacity={opacity:.2f}")
            warped_bgr, warped_alpha = _warp_mold_to_nail(
                mold, n["mask"], n["centroid"], ta, h, w,
                shape_type=shape_type, length_ratio=length_ratio, width_ratio=width_ratio,
                use_extreme_alignment=use_extreme_alignment, standard_width=standard_width)
            m3 = warped_alpha[:, :, None] * opacity
            acc_tex = acc_tex * (1 - m3) + warped_bgr.astype(np.float32) * m3
            acc_alpha = np.maximum(acc_alpha, warped_alpha)
            acc_gloss = np.maximum(acc_gloss, _draw_glossy_highlight(warped_alpha, ta))
            n_applied += 1
        mode = "pattern_extreme" if use_extreme_alignment else "pattern"
    elif color is not None:
        # ── 纯色模式（模具缺失时用颜色）──
        print(f"[TryOn] 纯色模式, color={color}, shape_type={shape_type}, length_ratio={length_ratio}, width_ratio={width_ratio}, opacity={opacity:.2f}")
        bgr = np.array(_hex_to_bgr(color), dtype=np.float32)
        for n in nails:
            ta = n.get("tip_angle", -90.0)
            alpha = _solid_color_alpha(n["mask"], ta, h, w)
            m3 = alpha[:, :, None] * opacity
            acc_tex = acc_tex * (1 - m3) + bgr * m3
            acc_alpha = np.maximum(acc_alpha, alpha)
            acc_gloss = np.maximum(acc_gloss, _draw_glossy_highlight(alpha, ta))
        n_applied = len(nails)
        mode = "solid"
    else:
        return {"success": False, "error": f"款式 {design_id} 无模具且未指定颜色", "image": user_bgr}

    # 优化 C: 加强 LAB 光影融合，与肤色融合更自然
    result = _blend_lab(user_bgr, acc_tex.astype(np.uint8), acc_alpha, shading_strength=0.50)  # 改大: 0.30→0.50
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

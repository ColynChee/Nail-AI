"""YOLOv8-seg 指甲分割 + 手指身份(finger_idx)标注。

用户图和款式图共用本模块。

核心函数 segment_nails(image):
  返回每个指甲的 dict 列表，含:
    - mask: (H,W) bool 精确甲面
    - finger_idx: 0=拇指 1=食指 2=中指 3=无名指 4=小指；-1 表示未能标注
    - conf: YOLO 置信度
    - centroid: (cx, cy) 质心
    - contour: 最大外轮廓点

手指身份标注策略:
  方案 B(主): MediaPipe 指尖点落在哪个 YOLO mask 内 → 标该 finger_idx
  方案 A(兜底): MediaPipe 失败时，按质心位置排序近似赋值
"""
import os
from typing import List, Dict, Optional
import numpy as np
import cv2

os.environ.setdefault(
    "YOLO_CONFIG_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ultralytics"),
)

_MODEL = None
_MODEL_FIST = None
_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "nails_seg_yolov8.pt")
_MODEL_FIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "nails_seg_fist.pt")
# RTX 5060 (sm_120) 当前 torch cu124 不支持，先用 CPU。升级 cu128 后改 "cuda:0"。
_DEVICE = "cpu"

FINGER_NAMES = ["拇指", "食指", "中指", "无名指", "小指"]
_FINGERTIP_LM = [4, 8, 12, 16, 20]   # MediaPipe 指尖关键点编号
_FINGERBASE_LM = [2, 5, 9, 13, 17]   # 对应指根(MCP)关键点，用于算指尖朝向


def _minarea_tip_angle(mask: np.ndarray) -> float:
    """用 mask 的极端点计算指尖角度(度) —— 更精准的方法。

    算法：找出指甲 mask 上沿各个方向最远的点，计算从指根到指尖的实际方向。
    这避免了依赖 MediaPipe 关键点或标准化假设，直接基于指甲形状。"""
    ys, xs = np.where(mask)
    if len(xs) < 10:  # 点太少，降级使用原有方法
        cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return -90.0
        (cx, cy), (w, h), ang = cv2.minAreaRect(max(cnts, key=cv2.contourArea))
        if w >= h:
            return float(ang)
        else:
            return float(ang + 90)

    pts = np.column_stack([xs, ys]).astype(np.float32)
    center = np.mean(pts, axis=0)

    # 方法：在多个方向上找最远点，选择跨度最大的作为主轴
    angles_to_try = np.linspace(0, 180, 36)  # 尝试 36 个方向
    max_span = 0
    best_angle = -90.0

    for test_angle in angles_to_try:
        a = np.radians(test_angle)
        dir_vec = np.array([np.cos(a), np.sin(a)])
        projections = (pts - center) @ dir_vec
        span = np.max(projections) - np.min(projections)

        if span > max_span:
            max_span = span
            # 找出该方向上最远的两个点
            tip_idx = np.argmax(projections)
            root_idx = np.argmin(projections)
            tip_pt = pts[tip_idx]
            root_pt = pts[root_idx]

            # 计算实际方向
            actual_dir = tip_pt - root_pt
            if np.linalg.norm(actual_dir) > 0.1:
                actual_dir = actual_dir / np.linalg.norm(actual_dir)
                actual_angle = float(np.degrees(np.arctan2(actual_dir[1], actual_dir[0])))
                # 转换为"指向上方"的约定
                best_angle = actual_angle - 90

    return float(best_angle)


def get_seg_model():
    """获取张开手模型"""
    global _MODEL
    if _MODEL is None:
        from ultralytics import YOLO
        _MODEL = YOLO(_MODEL_PATH)
    return _MODEL


def get_seg_model_fist():
    """获取握拳手模型"""
    global _MODEL_FIST
    if _MODEL_FIST is None:
        from ultralytics import YOLO
        _MODEL_FIST = YOLO(_MODEL_FIST_PATH)
    return _MODEL_FIST


def _yolo_nails(image: np.ndarray, conf: float = 0.25, model_type: str = "open") -> List[Dict]:
    """跑 YOLO，返回每个指甲的 mask/conf/centroid/contour（未标 finger_idx）。
    model_type: "open"(张开手) / "fist"(握拳)"""
    h, w = image.shape[:2]
    if model_type == "fist":
        model = get_seg_model_fist()
    else:
        model = get_seg_model()
    results = model.predict(image, conf=conf, verbose=False, device=_DEVICE)
    r = results[0]
    out = []
    if r.masks is None or len(r.masks) == 0:
        return out
    masks = r.masks.data.cpu().numpy()  # (n, mh, mw) 0~1
    confs = r.boxes.conf.cpu().numpy() if r.boxes is not None else [1.0] * len(masks)
    for i in range(len(masks)):
        m = cv2.resize(masks[i], (w, h), interpolation=cv2.INTER_NEAREST) > 0.5
        if int(m.sum()) < 20:
            continue
        ys, xs = np.where(m)
        cx, cy = float(xs.mean()), float(ys.mean())
        cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(cnts, key=cv2.contourArea) if cnts else None
        out.append({
            "mask": m,
            "conf": float(confs[i]),
            "centroid": (cx, cy),
            "contour": contour,
            "finger_idx": -1,
        })
    return out


def _select_main_hand(image: np.ndarray):
    """返回主手(关键点跨度最大那只)的指尖像素坐标列表 [(idx, x, y)]，
    以及该手所有关键点的像素坐标(用于过滤别的手)。检测失败返回 (None, None)。"""
    try:
        from hand_detector import get_detector
        result = get_detector().detect(image)
    except Exception:
        return None, None, None
    if not result.get("success") or not result.get("hands"):
        return None, None, None

    h, w = image.shape[:2]
    best_hand, best_area = None, -1.0
    for hand in result["hands"]:
        lms = hand["landmarks"]
        xs = [lm["x"] for lm in lms]
        ys = [lm["y"] for lm in lms]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best_area, best_hand = area, hand
    lms = best_hand["landmarks"]

    tips = [(fi, lms[lm_id]["x"] * w, lms[lm_id]["y"] * h)
            for fi, lm_id in enumerate(_FINGERTIP_LM)]
    # 每指的"指尖朝向角度"(度): 从指根指向指尖的向量
    tip_angles = {}
    for fi in range(5):
        tx, ty = lms[_FINGERTIP_LM[fi]]["x"] * w, lms[_FINGERTIP_LM[fi]]["y"] * h
        bx, by = lms[_FINGERBASE_LM[fi]]["x"] * w, lms[_FINGERBASE_LM[fi]]["y"] * h
        tip_angles[fi] = float(np.degrees(np.arctan2(ty - by, tx - bx)))
    all_pts = [(lm["x"] * w, lm["y"] * h) for lm in lms]
    return tips, all_pts, tip_angles


def _filter_to_main_hand(nails: List[Dict], all_pts) -> List[Dict]:
    """双手/多检时，只保留靠近主手关键点的指甲。
    判据：mask 质心到最近的主手关键点距离 < 手的尺度 * 0.6。"""
    if not all_pts or len(nails) <= 5:
        return nails
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    hand_scale = max(max(xs) - min(xs), max(ys) - min(ys))
    thresh = hand_scale * 0.6
    kept = []
    for n in nails:
        cx, cy = n["centroid"]
        dmin = min(((cx - px) ** 2 + (cy - py) ** 2) ** 0.5 for px, py in all_pts)
        if dmin <= thresh:
            kept.append(n)
    # 过滤后若反而 <3 个，说明判据不靠谱，退回原始
    return kept if len(kept) >= 3 else nails


def _assign_via_mediapipe(nails: List[Dict], image: np.ndarray, tips) -> None:
    """方案 B 改进版：双向最近匹配 + 距离阈值。
    每根指尖找最近的未占用 mask；距离太远(>typical 指甲间距)则不强配，留 -1。"""
    h, w = image.shape[:2]
    # 典型指甲尺寸作为距离阈值参考
    sizes = [float(n["mask"].sum()) ** 0.5 for n in nails]
    typ = float(np.median(sizes)) if sizes else 30.0
    max_dist = typ * 3.0  # 指尖到甲心允许的最大距离

    used = set()
    # 按"指尖落在 mask 内"优先匹配，再按距离匹配
    for finger_idx, tx, ty in tips:
        # 1) 指尖直接落在某个 mask 内
        hit = None
        for k, n in enumerate(nails):
            if k in used:
                continue
            iy, ix = int(ty), int(tx)
            if 0 <= iy < h and 0 <= ix < w and n["mask"][iy, ix]:
                hit, hit_k = n, k
                break
        # 2) 否则取最近且在阈值内的
        if hit is None:
            best_k, best_d = -1, 1e18
            for k, n in enumerate(nails):
                if k in used:
                    continue
                cx, cy = n["centroid"]
                d = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
                if d < best_d:
                    best_d, best_k = d, k
            if best_k >= 0 and best_d <= max_dist:
                hit, hit_k = nails[best_k], best_k
        if hit is not None:
            hit["finger_idx"] = finger_idx
            used.add(hit_k)


def _assign_via_position(nails: List[Dict]) -> None:
    """方案 A 兜底：按质心 x 排序近似赋 0..4。仅适用张开手，结果可能需人工纠正。"""
    ordered = sorted(nails, key=lambda n: n["centroid"][0])
    for i, n in enumerate(ordered):
        n["finger_idx"] = i if i < 5 else -1


def detect_hand_pose(image: np.ndarray) -> Optional[str]:
    """检测手部姿态：张开手或握拳。
    基于 MediaPipe 关键点：
      - 开放手：指尖之间的距离大，掌心到指尖距离差异大
      - 握拳手：指尖之间距离小，指尖都靠近掌心
    返回 "open" / "fist" / None(检测失败)"""
    try:
        from hand_detector import get_detector
        result = get_detector().detect(image)
    except Exception:
        return None
    if not result.get("success") or not result.get("hands"):
        return None

    h, w = image.shape[:2]
    # 选择跨度最大的手
    best_hand = None
    best_area = -1.0
    for hand in result["hands"]:
        lms = hand["landmarks"]
        xs = [lm["x"] for lm in lms]
        ys = [lm["y"] for lm in lms]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best_area, best_hand = area, hand

    lms = best_hand["landmarks"]

    # 方法：比较指尖到掌心的距离
    # 掌心是 lm 9 (PalmCenter or middle of 5, 17)
    palm_x = (lms[5]["x"] + lms[9]["x"] + lms[13]["x"] + lms[17]["x"]) / 4.0
    palm_y = (lms[5]["y"] + lms[9]["y"] + lms[13]["y"] + lms[17]["y"]) / 4.0
    palm_x *= w
    palm_y *= h

    # 计算每个手指指尖到掌心的距离
    tip_distances = []
    for fi in range(5):
        tip_lm = _FINGERTIP_LM[fi]  # 指尖关键点
        tx, ty = lms[tip_lm]["x"] * w, lms[tip_lm]["y"] * h
        dist = ((tx - palm_x) ** 2 + (ty - palm_y) ** 2) ** 0.5
        tip_distances.append(dist)

    # 判断姿态：基于指尖到掌心的最小距离
    # - 握拳：指尖都靠近掌心 → min_distance 很小
    # - 张开手：指尖远离掌心 → min_distance 很大
    avg_distance = np.mean(tip_distances)
    min_distance = np.min(tip_distances)
    max_distance = np.max(tip_distances)

    print(f"[detect_hand_pose] avg_dist={avg_distance:.1f}, min_dist={min_distance:.1f}, max_dist={max_distance:.1f}")
    print(f"[detect_hand_pose] 握拳判定: {min_distance:.1f} < {avg_distance * 0.4:.1f}? {min_distance < avg_distance * 0.4}")
    print(f"[detect_hand_pose] 张开判定: {min_distance:.1f} > {avg_distance * 0.6:.1f}? {min_distance > avg_distance * 0.6}")

    if min_distance < avg_distance * 0.4:
        print(f"[detect_hand_pose] -> 识别为 FIST (握拳)")
        return "fist"
    elif min_distance > avg_distance * 0.6:
        print(f"[detect_hand_pose] -> 识别为 OPEN (张开手)")
        return "open"
    else:
        # 无法确定（半握等中间状态）
        print(f"[detect_hand_pose] -> 无法确定 (返回 None)")
        return None


def segment_nails(image: np.ndarray, conf: float = 0.25) -> List[Dict]:
    """分割 + 标注 finger_idx + tip_angle(指尖朝向角度,度)。
    自动检测手部姿态（张开/握拳），选择对应模型。
    返回指甲 dict 列表（已过滤到主手）。

    Notes:
      - 第一步检测手部姿态（open/fist/None）
      - 如果检测成功，用对应模型分割；如果失败，尝试两个模型并选择结果更好的
      - 返回的 dict 中 _pose 字段标记检测到的姿态，_model_used 标记使用的模型
    """
    # 第一步：检测手部姿态
    pose = detect_hand_pose(image)

    if pose is None:
        # 姿态检测失败 → 尝试两个模型，选择结果更好的
        nails_open = _yolo_nails(image, conf=conf, model_type="open")
        nails_fist = _yolo_nails(image, conf=conf, model_type="fist")

        # 比较两个结果：选择检测到更多指甲且置信度更高的
        score_open = sum(n["conf"] for n in nails_open) if nails_open else 0
        score_fist = sum(n["conf"] for n in nails_fist) if nails_fist else 0

        if score_open > score_fist:
            nails = nails_open
            model_type = "open"
            pose = "open_fallback"
        elif score_fist > score_open:
            nails = nails_fist
            model_type = "fist"
            pose = "fist_fallback"
        else:
            # 两个都一样，倾向于用 open 模型（通常更稳定）
            nails = nails_open
            model_type = "open"
            pose = "open_default"
    else:
        # 姿态检测成功 → 用对应的模型
        model_type = "fist" if pose == "fist" else "open"
        nails = _yolo_nails(image, conf=conf, model_type=model_type)

    if not nails:
        return []

    # 将检测到的手部姿态添加到每个指甲的返回数据中（用于调试）
    for n in nails:
        n["_pose"] = pose
        n["_model_used"] = model_type

    tips, all_pts, tip_angles = _select_main_hand(image)
    if tips is not None:
        nails = _filter_to_main_hand(nails, all_pts)
        _assign_via_mediapipe(nails, image, tips)
        # 用 MediaPipe 角度；该指无角度则用 minAreaRect 兜底
        for n in nails:
            fi = n["finger_idx"]
            if fi in tip_angles:
                n["tip_angle"] = tip_angles[fi]
            else:
                n["tip_angle"] = _minarea_tip_angle(n["mask"])
    else:
        # MediaPipe 检测失败 → 位置排序兜底（仅取置信度最高的5个）
        nails = sorted(nails, key=lambda n: n["conf"], reverse=True)[:5]
        _assign_via_position(nails)
        for n in nails:
            n["tip_angle"] = _minarea_tip_angle(n["mask"])

    # 为所有指甲添加姿态标记
    is_fist = (pose == "fist")
    for n in nails:
        n["_is_fist"] = is_fist
    print(f"[segment_nails] 最终 pose={pose}, is_fist={is_fist}")

    return nails


def draw_annotation(image: np.ndarray, nails: List[Dict]) -> np.ndarray:
    """生成标注预览图：彩色 mask + 手指名称文字，供人工检查。"""
    vis = image.copy()
    rng = np.random.default_rng(7)
    for n in nails:
        color = rng.integers(60, 255, size=3).tolist()
        vis[n["mask"]] = (0.45 * np.array(color) + 0.55 * vis[n["mask"]]).astype(np.uint8)
        if n["contour"] is not None:
            cv2.drawContours(vis, [n["contour"]], -1, color, 2)
        cx, cy = int(n["centroid"][0]), int(n["centroid"][1])
        fi = n["finger_idx"]
        label = FINGER_NAMES[fi] if 0 <= fi < 5 else "?"
        # 文字用英文缩写避免 OpenCV 中文乱码
        en = ["thumb", "index", "middle", "ring", "pinky"][fi] if 0 <= fi < 5 else "?"
        cv2.putText(vis, f"{en} {n['conf']:.2f}", (cx - 30, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(vis, f"{en} {n['conf']:.2f}", (cx - 30, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return vis

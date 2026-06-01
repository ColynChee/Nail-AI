import sys, numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
import nail_tryon_v2

def ir(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)

ROOT = r"D:\指上谈兵"
hand = ir(ROOT + r"\手图\b9632e3a699fdb63a1a6139bbfd6bf0d2159483.webp")

# 试几个不同类型的款式
tests = [
    ("design_006", "蜜桃珊瑚-纯色"),
    ("design_003", "白底波点-图案"),
    ("design_023", "墨黑漆-纯黑"),
    ("design_002", "雾感橄榄-多色"),
]
for did, name in tests:
    res = nail_tryon_v2.try_on(hand, did)
    if res["success"]:
        out = f"v2_out_{did}.jpg"
        cv2.imencode(".jpg", res["image"])[1].tofile(out)
        print(f"{did} ({name}): OK applied={res['n_applied']}/{res['n_nails']} -> {out}")
    else:
        print(f"{did} ({name}): FAIL {res.get('error')}")

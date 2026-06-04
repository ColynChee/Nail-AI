# 阶段4 进度：接入 FastAPI + 颜色切换

## 背景
美甲试戴赛题。试戴模块走"路线A"(YOLO分割+标准甲形+模具/纯色合成)，核心已完成。
阶段4目标：把 nail_tryon_v2 接入 FastAPI + 前端加颜色切换 + 全链路测试。

## 已完成 ✅
1. **后端 main.py 已重写**（接入 nail_tryon_v2）
   - 验证过：`python -c "import main"` → IMPORT_OK, designs: 25
   - `/api/try-on` 现支持参数：image, design_id, design_image, **color**(可选hex)
     - color 给定 → 纯色合成模式(可换色)；否则 → 模具贴图模式
   - 返回 JSON: success, message, image_base64, design, mode, n_applied, color
   - 新增 `/api/design-color/{design_id}` → 返回款式主色 {color: "#RRGGBB"}，供前端色板默认
   - 保留: /api/designs, /api/designs/{id}, /api/detect-hands, /api/analytics, /api/analytics/design/{id}
   - **删除了 /api/analyze-hand**（肤色LLM分析端点）和 llm_client 依赖
     - ⚠️ 待确认：skin-sheet.js 是否依赖它，如依赖需加回
   - 旧版备份在 `main_v1_backup.py.bak`（我曾误判原文件损坏，实际没坏，但重写是必要的且已验证）

## 待办（剩余阶段4）
2. **前端 try-on.js + HTML 加颜色切换** ← 下一步从这里继续
   - 当前 try-on.js[91-98]：用 `tryonStyleInfo.image` 调 `/api/try-on?design_image=...`（与新后端兼容，基础试戴已能用）
   - 需要：startTryon 里把上传的 file 存到全局变量(如 window._lastTryonFile)，供换色复用
   - 需要：试戴结果区(tryon-result)下方加一排颜色色板(预设色 + 款式主色)
   - 需要：点色板 → 用缓存的 file 重新 POST /api/try-on?design_image=...&color=<hex> → 更新结果图
   - 注意：color 传 hex 时 # 要 encodeURIComponent (%23)
   - HTML 试戴页 id="s-tryon"，结果元素：tryon-result, tryon-result-emoji(放img), tryon-ba-emoji, tryon-result-label, tryon-match-score, tryon-ai-text
     - 上面这些 id 需再次确认(grep 当时被打断/乱码，直接 Read 指上谈兵.html 的 s-tryon 段)

3. **全链路测试**
   - 杀掉旧 8000 端口进程：`Get-NetTCPConnection -LocalPort 8000 | %{ Stop-Process -Id $_.OwningProcess -Force }`
   - 重启后端：`cd D:\指上谈兵\backend; python main.py`
   - 前端服务：`cd D:\指上谈兵; python -m http.server 5500` → http://localhost:5500/指上谈兵.html
   - 测：选款式→上传手图→看试戴(模具模式)→点色板换色(纯色模式)

## 关键技术参考
- nail_tryon_v2.try_on(user_bgr, design_id, color=None) → {success, image(BGR), n_applied, mode}
- nail_tryon_v2.dominant_color(design_id) → "#RRGGBB" or None
- 中文路径读图用 np.fromfile+cv2.imdecode（已在各模块处理）
- YOLO 跑 CPU（RTX5060 sm_120 不兼容当前 torch cu124），单次试戴约1-2秒
- 测试手图：D:\指上谈兵\手图\b9632e3a699fdb63a1a6139bbfd6bf0d2159483.webp
- 纯色款已被颜色切换覆盖；缺指款(001/012/017/020)镜像补全已验证无违和

## 测试输出图（可删）
backend/v2_out_design_*.jpg 是试戴结果样例，非程序依赖

# 部署指南（让手机能装 PWA）

本项目分两部分部署：
- **后端**（FastAPI + Supabase）→ Render（免费）
- **前端**（静态 PWA）→ Vercel（免费 HTTPS）

PWA 必须跑在 HTTPS 上才能「添加到主屏幕」，所以两端都要部署，不能只用本地 localhost。

---

## 前置准备
- 一个 GitHub 账号，且对 `ColynChee/Nail-AI` 仓库有访问权限
  - 仓库在朋友账号下时：让朋友在 **Settings → Collaborators** 把你加为协作者；或 **Fork** 一份到自己账号
- 一个 [Supabase](https://supabase.com) 项目（数据库）
- 一个 [ModelScope](https://modelscope.cn) Token（AI 功能）
- 数据库表已建好（见下方「数据库」一节）

---

## 一、部署后端（Render）

1. 打开 [render.com](https://render.com) 注册并连接 GitHub。
2. **New → Web Service** → 选择 `Nail-AI` 仓库。
3. 填写配置：
   | 项 | 值 |
   |---|---|
   | **Root Directory** | `backend` |
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | **Instance Type** | Free |
4. 展开 **Environment**，添加环境变量（和本地 `backend/.env` 一致）：
   - `MODELSCOPE_TOKEN` = 你的 ModelScope token
   - `DATABASE_URL` = 你的 Supabase 连接串（Session pooler URI，密码里特殊字符要 URL 编码）
5. 点 **Create Web Service**，等待部署。成功后得到后端地址，例如：
   ```
   https://nailai-api.onrender.com
   ```
6. 验证：浏览器打开 `https://你的后端地址/` 应返回 `{"status":"ok",...}`。

> ⚠️ Render 免费实例闲置会休眠，首次访问需等 ~30 秒唤醒，属正常现象。

---

## 二、改前端配置指向云端后端

编辑 `scripts/config.js`，把 `PROD_API_BASE` 改成第一步拿到的后端地址：

```js
const PROD_API_BASE = 'https://nailai-api.onrender.com';  // 改成你的后端地址
```

提交并推送：
```bash
git add scripts/config.js
git commit -m "配置云端后端地址"
git push
```

---

## 三、部署前端（Vercel）

1. 打开 [vercel.com](https://vercel.com) 注册并连接 GitHub。
2. **Add New → Project** → 选择 `Nail-AI` 仓库 → **Import**。
3. 配置：
   - **Framework Preset**: `Other`（纯静态，无需构建）
   - **Root Directory**: `./`（仓库根目录）
   - Build/Output 留空
4. 点 **Deploy**，等待完成。得到前端地址，例如：
   ```
   https://nail-ai.vercel.app
   ```
   （入口是 `index.html`，Vercel 会自动作为首页）

---

## 四、装到手机 📱

1. 手机浏览器（iOS 用 Safari，安卓用 Chrome）打开 Vercel 前端地址。
2. 注册 / 登录账号。
3. 添加到主屏幕：
   - **iOS Safari**：分享按钮 → 「添加到主屏幕」
   - **安卓 Chrome**：右上角菜单 → 「添加到主屏幕 / 安装应用」
4. 桌面会出现「指上谈兵」图标，点开就像原生 App（全屏、有启动图标）。

---

## 数据库（首次部署需执行一次）

在 Supabase 控制台 **SQL Editor** 里执行以下脚本的内容建表：
- `backend/db/schema_accounts.sql` —— 账号表 + 收藏表
- `backend/db/schema_user_designs.sql` —— 我的设计表

若 `user_profiles` / `try_on_logs` 尚未创建，也一并补上。

---

## 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| 前端打开后登录/数据报错 | `scripts/config.js` 的 `PROD_API_BASE` 没改对，或后端在休眠（等 30 秒重试） |
| 后端启动失败 | Render 环境变量 `DATABASE_URL` / `MODELSCOPE_TOKEN` 没配，或密码未 URL 编码 |
| AI 设计/分析不工作 | `MODELSCOPE_TOKEN` 无效或额度不足 |
| 手机上图片裂开 | 后端 `/user_designs`、`/designs_generated` 图片地址需后端可公网访问（Render 已满足） |
| 跨域报错 CORS | 后端已设 `allow_origins=["*"]`，正常不会出现 |
| 改了代码手机没更新 | PWA 有缓存，重新打开或在浏览器里清除站点数据；service-worker 会在下次访问更新 |

---

## 更新流程（部署后改代码）

1. 本地改代码 → `git push`
2. Render（后端）和 Vercel（前端）都会**自动重新部署**最新代码
3. 手机端重新打开 App 即可获取更新

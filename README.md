# 指上谈兵 / Nail AI 🎨

**AI 驱动的美甲设计与虚拟试戴系统**

集成 YOLO 指甲分割、生成式 AI 设计、LLM 提示优化，支持参数化指甲形状、色彩匹配和交互式编辑。

## 🎯 核心功能

### 🌟 灵感试戴（新）
- **设计灵感上传**：上传美甲灵感参考图
- **AI 风格分析**：Qwen-VL 分析设计风格和色彩搭配
- **智能模具生成**：Z-Image-Turbo 生成 5 指模板，自动智能裁剪
- **一键虚拟试戴**：灵感图可立即体验效果

### 🎨 AI 设计生成
- **文生图设计**：使用 Qwen 生成精美美甲设计
- **智能提示词优化**：DeepSeek 大模型优化用户自然语言输入
- **自动指甲提取**：轮廓检测智能分离预览图中的 5 个指甲
- **两步确认工作流**：预览设计 → 确认提取指甲模具

### 💅 虚拟试戴
- **智能指甲分割**：YOLOv8-seg 精确检测用户指甲（支持张开手和握拳）
- **参数化指甲形状**：椭圆形/尖形/方形，可调长宽比和旋转角度
- **两阶段效果显示**：快速试戴结果 + 异步 AI 分析（后台运行）
- **LAB 色彩匹配**：自适应肤色的自然色彩混合

### 🧠 AI 智能分析（新）
- **搭配评分**：Qwen-VL-30B 多维度分析美甲与肤色、手型匹配度
- **个性化推荐**：根据肤色推荐最佳色系和美甲风格
- **场景适配**：智能建议适用场景（日常/约会/职场等）
- **实时通知**：分析完成后 Toast 提示用户

### 🏠 款式库与发现
- **25 款精选设计**：包含原始预览图和高质量详细设计图
- **检测美甲**：上传手部照片，分析肤色、手型、肤质等特征
- **款式试戴**：预定义设计库一键虚拟试戴
- **实时热门榜**：B站/抖音/小红书热度数据集成
- **收藏与追踪**：保存喜爱款式，记录试戴历史

### 📊 智能运营看板（新）
- **多平台实时热度**：B站公开 API 拉取 25 款对应视频的真实播放量、点赞、收藏、弹幕、投币数，5 分钟自动刷新
- **热度综合评分**：加权公式 `播放 + 点赞×6 + 收藏×8 + 评论×10 + 弹幕×3 + 投币×6 + 分享×12`
- **趋势洞察**：自动按裸色/法式/猫眼/春夏/秋冬/闪耀/通勤/甜美/酷感 9 个维度分桶，输出聚合热度、平均互动率和趋势信号（强上升/稳定增长/观察中）
- **KPI 看板**：实时监控款数、平台总曝光、高意向互动（赞藏评转加权）、今日运营动作数
- **优先级执行列表**：前 6 款按热度排序，自动打标（主推 / 联动 / 转化 / 上新 / 优化 / 观察）并附操作建议
- **风险预警**：自动识别低热款、数据缺口款、低互动款，输出具体优化动作
- **今日执行计划**：09:30 主推上首页 → 11:00 接入 AI 试戴默认款 → 15:30 同风格组合推荐 → 20:30 复盘低热款
- **可视化趋势图**：Chart.js 混合图（柱状热度 + 折线互动率），支持 Top 8 款对比

### 🤖 AI 运营助手（新）
- **ModelScope Qwen 驱动**：调用 `Qwen/Qwen3.5-35B-A3B` 大模型，输入 Top 12 款实时热度数据 + 趋势分桶 + 全局汇总
- **四维运营建议**：输出实时监控、趋势分析、策略生成、效率提升四行可落地建议
- **可执行动作**：生成 3-5 个带类型标签的运营动作（promote / copywriting / content / audit / data / tryon），OpenClaw-ready 架构
- **防重复调用**：数据签名未变化时不重复请求 API，节省 token
- **本地兜底**：无 ModelScope Token 时自动切换本地策略模板，不中断展示

---

## 🚀 快速开始

### 前置要求
- Python 3.8+
- Node.js 14+ (HTTP 服务器)
- 一个 [Supabase](https://supabase.com) 项目（免费版即可，用于账号 / 收藏 / 我的设计）
- [ModelScope](https://modelscope.cn) Token（用于 AI 设计与分析）
- GPU 可选（使用 CPU 也可运行）

### ① 配置环境变量
```bash
cd backend
cp .env.example .env
```
然后编辑 `backend/.env`，填入：
- `MODELSCOPE_TOKEN` —— [获取地址](https://modelscope.cn/my/myaccesstoken)
- `DATABASE_URL` —— Supabase 控制台 → Project Settings → Database → Connection string → URI（选 **Session pooler**）。密码含 `+ & $` 等特殊字符要做 URL 编码。

> ⚠️ `.env` 已被 `.gitignore` 忽略、不会上传，**每个人 clone 后都要自己创建**。

### ② 初始化数据库（首次运行一次）
在 Supabase 控制台的 **SQL Editor** 里，依次执行这两个建表脚本的内容：
- `backend/db/schema_accounts.sql` —— 账号表 + 收藏表
- `backend/db/schema_user_designs.sql` —— 我的设计表

（个人资料表 `user_profiles` 和试戴日志 `try_on_logs` 如未创建，也一并补上即可。）

### ③ 后端启动
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# 运行在 http://localhost:8000
# 启动日志出现 [DB] connection pool created 表示数据库连接成功
```

### ④ 前端启动
```bash
# 项目根目录
npx http-server -p 5000 --default-file 指上谈兵.html
# 或用 Python: python -m http.server 5000

# 访问 http://localhost:5000
```

⚠️ **重要**：
- 不要直接用 `file://` 协议打开 HTML，必须用 HTTP 服务器！
- App **需要先注册 / 登录账号**才能进入（账号、收藏、设计都存在 Supabase）。

---

## 📊 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **前端** | HTML/CSS/JavaScript | UI 和交互逻辑 |
| **图像处理** | OpenCV | 图像预处理和轮廓检测 |
| **指甲检测** | YOLOv8-seg (22.8 MB) | 实例分割和指甲定位 |
| **手部检测** | MediaPipe Hand Landmarker | 手指识别和姿态估计 |
| **后端框架** | FastAPI | REST API 服务 |
| **LLM 分析** | Qwen/Qwen3-VL-30B-A3B-Instruct | 美甲搭配分析和推荐 |
| **LLM 优化** | deepseek-ai/DeepSeek-V4-Pro | 提示词优化 |
| **文生图（灵感试戴）** | Tongyi-MAI/Z-Image-Turbo | 从灵感图生成 5 指模具模板 |
| **文生图（AI 设计）** | Qwen/Qwen-Image-2512 | AI 设计生成（异步轮询） |
| **异步生成** | ModelScope API | 异步模具生成和轮询 |
| **色彩空间** | LAB 色彩混合 | 自然色彩适应 |
| **运营 AI** | Qwen/Qwen3.5-35B-A3B | 智能运营策略生成 |
| **热度数据** | B站公开 API | 视频播放/互动实时拉取 |
| **热度数据** | 关键词热度模型 | 抖音/小红书兜底参考 |
| **数据库** | Supabase / asyncpg | 账号、收藏、我的设计、用户档案 |
| **本地分析** | analytics.py | 试戴日志、肤色分布、热门款统计 |

---

## 🔌 关键 API 端点

```
POST /api/generate-nail-design           # AI 生成设计
POST /api/confirm-nail-design            # 确认并提取指甲
POST /api/detect-nails-preview           # 检测用户指甲
POST /api/confirm-crop                   # 裁剪确认
POST /api/try-on                         # 虚拟试戴（支持 skip_analysis 快速返回）
POST /api/analyze-tryon                  # 异步 AI 搭配分析（后台执行）
GET  /api/designs                        # 获取款式库（25+ 款）
POST /api/generate-mold-from-inspiration # 从灵感图生成模具

# 智能运营
GET  /api/bilibili/trending-nails        # B站实时热度（25 款视频数据，5min 缓存）
POST /api/ops/assistant                  # AI 运营助手（Qwen 生成四维建议 + 可执行动作）
GET  /api/analytics                      # 本地试戴日志汇总（总次数/热门款/肤色分布）
GET  /api/analytics/design/{design_id}  # 单款试戴统计

# 账号系统
POST /api/auth/register                  # 注册
POST /api/auth/login                     # 登录
GET  /api/wishlist                       # 收藏列表
POST /api/wishlist                       # 添加收藏
GET  /api/user-designs                   # 我的设计列表
POST /api/user-designs                   # 保存设计
GET  /api/profile                        # 用户档案
POST /api/profile                        # 更新档案
```

---

## 💡 核心算法

### 指甲分割
- **检测方法**：YOLOv8 实例分割 + MediaPipe 手指识别
- **降级方案**：当分割不确定时使用等分法（水平分成 5 列）
- **特殊处理**：握拳姿势的自动检测和适应

### 虚拟试戴变换
- **形状约束**：参数化指甲轮廓（椭圆/尖形/方形）
- **透视变换**：将设计模具映射到用户指甲形状
- **色彩混合**：LAB 色空间自适应用户肤色

### 提示词优化
- **模板机制**：保证结构一致的降级模板
- **LLM 增强**：DeepSeek 优化用户自然语言
- **布局要求**：显式指定 5 个指甲水平排列、适当间距

---

## 📁 项目结构

### Frontend
| 文件 | 说明 |
|------|------|
| `指上谈兵.html` | 主应用文件（所有屏幕） |
| `styles/main.css` | CSS 入口 |
| `scripts/data.js` | 25 款款式数据 + 全局状态 |
| `scripts/detail.js` | 款式详情页逻辑 |
| `scripts/try-on.js` | 虚拟试戴逻辑 |
| `scripts/image-search.js` | 以图搜款 + 检测美甲 |
| `scripts/design-gen.js` | AI 设计生成 |
| `scripts/trending.js` | 热门款式 + B站/抖音/小红书数据集成 |
| `scripts/ops.js` | 智能运营看板（KPI/趋势图/优先级列表/风险预警/执行计划/AI助手） |
| `scripts/xhs-config.js` | 平台热度端点配置（endpoint / refreshMs） |
| `scripts/xhs-keyword-heat.js` | 关键词热度兜底数据（30+ 美甲关键词 + 抖音搜索链接） |
| `scripts/gallery.js` | 款式库渲染和过滤 |
| `scripts/auth.js` | 登录/注册/退出逻辑 |
| `scripts/wishlist.js` | 收藏状态与渲染 |
| `scripts/my-designs.js` | 我的设计页面逻辑 |
| `scripts/profile.js` | 用户档案页面逻辑 |
| `scripts/init.js` | 应用启动初始化 |

### Backend
| 文件 | 说明 |
|------|------|
| `main.py` | FastAPI 服务器 + 路由 |
| `design_generator.py` | AI 设计生成管道 |
| `mold_generator.py` | 灵感图 → 模具生成（Qwen-VL 分析 + Z-Image-Turbo 生成 + 智能裁剪） |
| `ai_analysis.py` | Qwen-VL 搭配分析和推荐（肤色/手型评估） |
| `nail_tryon_v2.py` | 试戴算法（形状变换+色彩混合+两阶段显示） |
| `nail_tryon_v2_extreme.py` | 试戴算法 v2 极端点对齐版（当前使用） |
| `nail_seg.py` | YOLOv8-seg 指甲分割 + 握拳/张开手识别 |
| `hand_detector.py` | MediaPipe 手部检测 |
| `ops_assistant.py` | AI 运营助手（调用 ModelScope Qwen，输出四维建议 + 可执行动作） |
| `bilibili_stats.py` | B站公开 API 数据拉取（真实播放/互动，5min 缓存，并发请求） |
| `douyin_stats.py` | 抖音数据适配器（支持授权 API / 导出 JSON / 本地兜底） |
| `rednote_stats.py` | 小红书数据适配器（支持授权 API / 关键词搜索 / 本地兜底） |
| `analytics.py` | 本地试戴日志（试戴次数/热门款Top5/肤色分布/今日统计） |
| `bilibili_sources.json` | 25 款设计各配一条真实 B站 BVID |
| `rednote_sources.json` | 25 款设计各配关键词 + 小红书搜索链接 |
| `db/schema_accounts.sql` | 账号表 + 收藏表建表脚本 |
| `db/schema_user_designs.sql` | 我的设计表建表脚本 |
| `models/nails_seg_yolov8.pt` | YOLOv8 张开手实例分割模型 |
| `models/nails_seg_fist.pt` | YOLOv8 握拳手实例分割模型 |
| `molds/{design_id}/` | 提取的指甲模具 (PNG，0-4 共 5 个指甲) |

---

## 🎯 工作流程

### 1. 灵感试戴流程
```
用户上传灵感图
    ↓
Qwen-VL 分析设计风格
    ↓
Z-Image-Turbo 生成 5 指模板
    ↓
智能裁剪分割 (垂直投影 + 谷值检测)
    ↓
保存到 molds/insp_{id}/
    ↓
立即加载试戴
    ↓
后台异步 Qwen-VL 分析搭配
    ↓
分析完成 → Toast 通知用户
```

### 2. AI 设计生成流程
```
用户输入 (中文描述)
    ↓
DeepSeek 提示词优化
    ↓
Qwen 文生图 (5 个指甲并排)
    ↓
自动检测和提取指甲 (轮廓检测)
    ↓
保存到 molds/{design_id}/
    ↓
可立即用于虚拟试戴
```

### 3. 虚拟试戴流程
```
用户手部照片
    ↓
YOLO 指甲分割 + 握拳/张开手姿态识别
    ↓
交互式手动调整 (可选: 长宽比、旋转角度)
    ↓
加载设计模具
    ↓
第一阶段（快速）：
  - 参数化形状变换
  - LAB 色彩混合
  - 显示试戴结果 ✓ 用户立即看到效果
    ↓
第二阶段（后台）：
  - 异步调用 Qwen-VL 进行搭配分析
  - 分析完成后 Toast 通知用户 ✓
```

### 4. 智能运营流程
```
前端每 5 分钟自动请求 /api/bilibili/trending-nails
    ↓
后端并发拉取 25 条 B站视频公开统计（播放/点赞/收藏/弹幕/投币）
    ↓
热度公式加权计算 → 按热度排序
    ↓
运营看板渲染（KPI / 趋势图 / 优先级列表 / 风险预警 / 执行计划）
    ↓
签名变化时触发 POST /api/ops/assistant
    ↓
后端把 Top 12 款数据 + 趋势分桶发给 ModelScope Qwen
    ↓
Qwen 输出四维建议（实时监控 / 趋势分析 / 策略生成 / 效率提升）
    + 3-5 个可执行动作（OpenClaw-ready）
    ↓
渲染到 AI 运营助手卡片
```

### 5. 款式库预处理
```
25+ 款设计 (包含详细设计图)
    ↓
批量自动从详细图提取指甲
    ↓
轮廓检测 + 智能裁剪
    ↓
保存 5 个模具/款式 (0.png - 4.png)
    ↓
已准备好虚拟试戴
```

---

## 🔧 配置说明

### 环境变量 (.env)
```
MODELSCOPE_TOKEN=你的_modelscope_token
DEEPSEEK_API_KEY=你的_deepseek_api_key
```

### 关键参数
- **指甲检测**：YOLOv8 置信度 0.5
- **色彩混合**：LAB 色空间 alpha=0.5
- **形状约束**：目标最大边长 280px
- **HTTP 服务器**：前端运行在 5000 端口，后端 8000 端口

---

## 📈 性能指标

| 操作 | 耗时 | 备注 |
|------|------|------|
| 灵感设计生成 | 20-40s | Qwen-VL 分析 + Z-Image-Turbo 生成 |
| 灵感模具裁剪 | 1-2s | 垂直投影 + 谷值检测 |
| 虚拟试戴（第一阶段） | 1-2s | YOLO + 形状变换（同步） |
| AI 搭配分析（第二阶段） | 5-15s | Qwen-VL 多维度分析（异步） |
| AI 设计生成 | 30-60s | 包括提示词优化 |
| 指甲提取 | 1-2s | 轮廓检测 |
| 检测美甲 | 1-3s | YOLO + MediaPipe 手部分析 |

---

## 🔄 开发建议

### 已完成 ✓
- [x] 灵感试戴模块（从灵感图一键生成模具）
- [x] AI 搭配分析（Qwen-VL 多维度评估）
- [x] 两阶段试戴显示（快速结果 + 异步分析）
- [x] YOLO 握拳手模型（nails_seg_fist.pt）
- [x] 25 款设计模具库（含 8 款新设计）
- [x] Toast 实时通知系统
- [x] 智能运营看板（KPI / 趋势图 / 优先级列表 / 风险预警 / 执行计划）
- [x] B站实时热度接入（25 款 BVID，真实 API 拉取）
- [x] AI 运营助手（ModelScope Qwen，四维建议 + 可执行动作）
- [x] 抖音/小红书热度适配器（授权 API / 关键词兜底）
- [x] 账号系统（注册/登录，Supabase 存储）
- [x] 收藏上云（Supabase 持久化）
- [x] 我的设计页（上传/AI 生成设计管理）
- [x] 用户档案（肤色、推荐风格）
- [x] WebP 自动转高质量 JPG（提升试戴效果）
- [x] 少于 3 个指甲时检测质量警告

### 下一步改进
- [ ] 实时视频试戴
- [ ] 多手检测支持
- [ ] AR 集成（真实设备预览）
- [ ] 色彩空间高级优化
- [ ] 边缘融合和光影适配优化

### 数据更新
- 添加新款式：放入 `款式图/` 目录，更新 `designs.json`
- 更新热门榜：修改 `xhs-keyword-heat.js` 的热度分数
- 调整试戴效果：在 `nail_tryon_v2_extreme.py` 中调参

---

## Structure

- `nailai.html` - main page markup and app screens
- `styles/main.css` - stylesheet entry file with imports
- `styles/base/` - design tokens and reset styles
- `styles/layout/` - phone shell, screen layout, top/bottom navigation
- `styles/components/` - shared cards, chips, buttons, toast, sheets
- `styles/screens/` - styles for each app screen
- `scripts/data.js` - style data and shared state
- `scripts/navigation.js` - screen navigation
- `scripts/gallery.js` - gallery rendering and filters
- `scripts/detail.js` - detail screen interactions
- `scripts/try-on.js` - AI try-on simulation
- `scripts/image-search.js` - image search simulation
- `scripts/ops.js` - intelligent operations dashboard
- `scripts/auth.js` - login / register / logout
- `scripts/wishlist.js` - wishlist state and rendering
- `scripts/my-designs.js` - my designs page
- `scripts/profile.js` - profile page
- `scripts/xhs-config.js` - platform trending endpoint config
- `scripts/xhs-keyword-heat.js` - keyword heat fallback data
- `scripts/skin-sheet.js` - skin tone sheet interactions
- `scripts/toast.js` - toast messages
- `scripts/init.js` - startup calls

Open `nailai.html` via an HTTP server to run the app (do not use `file://`).

## 平台热度数据说明

热门榜接入 B站公开 API，端点配置在 `scripts/xhs-config.js`：

```js
const DOUYIN_TRENDING_CONFIG = {
  endpoint: window.API_BASE + '/api/bilibili/trending-nails',
  keywordFallback: false,  // 已关闭关键词兜底，使用真实 B站数据
  refreshMs: 5 * 60 * 1000  // 5 分钟自动刷新
};
```

后端 `/api/bilibili/trending-nails` 返回格式：

```json
{
  "updatedAt": "2026-06-07T12:00:00+08:00",
  "source": "bilibili-public",
  "items": [
    {
      "rank": 1,
      "id": "design_001",
      "name": "裸色奶油",
      "heatScore": 128400,
      "heat": "12.8w 实时",
      "platformName": "B站",
      "platformUrl": "https://www.bilibili.com/video/BV1LvrDY7E1s",
      "trendSource": "bilibili-public",
      "rawStats": {
        "viewCount": 12000,
        "likeCount": 880,
        "collectCount": 360,
        "commentCount": 96,
        "shareCount": 42,
        "danmakuCount": 180,
        "coinCount": 65
      }
    }
  ]
}
```

### 关键词热度兜底

B站接口失败时，前端自动回退到 `scripts/xhs-keyword-heat.js` 里的关键词热度数据（30+ 美甲关键词，链接到抖音搜索）。要更新兜底榜单，调整对应关键词的 `score` 值即可。

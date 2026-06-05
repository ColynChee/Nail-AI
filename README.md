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
- **参数化指甲形状**：圆形/尖形/方形，可调长宽比和旋转角度
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
- **实时热门榜**：小红书热度数据集成
- **收藏与追踪**：保存喜爱款式，记录试戴历史

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
| **LLM 分析** | Qwen-VL-30B-A3B-Instruct | 美甲搭配分析和推荐 |
| **LLM 优化** | DeepSeek-V4-Pro API | 提示词优化 |
| **文生图** | Z-Image-Turbo (豆包) | 快速美甲设计生成 |
| **异步生成** | ModelScope API | 异步模具生成和轮询 |
| **色彩空间** | LAB 色彩混合 | 自然色彩适应 |

---

## 🔌 关键 API 端点

```
POST /api/generate-nail-design         # AI 生成设计
POST /api/confirm-nail-design          # 确认并提取指甲
POST /api/detect-nails-preview         # 检测用户指甲
POST /api/confirm-crop                 # 裁剪确认
POST /api/try-on                       # 虚拟试戴（支持 skip_analysis 快速返回）
POST /api/analyze-tryon                # 异步 AI 搭配分析（后台执行）
GET  /api/designs                      # 获取款式库（25+ 款）
POST /api/generate-mold-from-inspiration # 从灵感图生成模具（新）
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
| `scripts/trending.js` | 热门款式 + 小红书集成 |
| `scripts/gallery.js` | 款式库渲染和过滤 |
| `scripts/init.js` | 应用启动初始化 |

### Backend
| 文件 | 说明 |
|------|------|
| `main.py` | FastAPI 服务器 + 路由 |
| `design_generator.py` | AI 设计生成管道 |
| `mold_generator.py` | 灵感图 → 模具生成（Qwen-VL 分析 + Z-Image-Turbo 生成 + 智能裁剪） |
| `ai_analysis.py` | Qwen-VL 搭配分析和推荐（肤色/手型评估） |
| `nail_tryon_v2.py` | 试戴算法（形状变换+色彩混合+两阶段显示） |
| `nail_seg.py` | YOLOv8-seg 指甲分割 + 握拳/张开手识别 |
| `hand_detector.py` | MediaPipe 手部检测 |
| `models/nails_seg_yolov8.pt` | YOLOv8 张开手实例分割模型 |
| `models/nails_seg_fist.pt` | YOLOv8 握拳手实例分割模型（新） |
| `molds/{design_id}/` | 提取的指甲模具 (PNG，0-4 共 5 个指甲) |

---

## 🎯 工作流程

### 1. 灵感试戴流程（新）
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

### 3. 虚拟试戴流程（改进）
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

### 4. 款式库预处理
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
- [x] 25+ 款设计模具库
- [x] Toast 实时通知系统

### 下一步改进
- [ ] 实时视频试戴
- [ ] 多手检测支持
- [ ] AR 集成（真实设备预览）
- [ ] 色彩空间高级优化
- [ ] 边缘融合和光影适配优化

### 数据更新
- 添加新款式：放入 `款式图/` 目录，更新 `designs.json`
- 更新热门榜：修改 `xhs-keyword-heat.js` 的热度分数
- 调整试戴效果：在 `nail_tryon_v2.py` 中调参

---

## Structure

- `指上谈兵.html` - main page markup and app screens
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
- `scripts/wishlist.js` - wishlist state and rendering
- `scripts/profile.js` - profile counters
- `scripts/skin-sheet.js` - skin tone sheet interactions
- `scripts/toast.js` - toast messages
- `scripts/init.js` - startup calls

Open `指上谈兵.html` in a browser to run the app.

## 小红书实时热门

今日热门榜不再使用假数据。前端会读取 `scripts/xhs-config.js` 里的 `endpoint`，请求你自己的后端接口，然后按小红书流量指标排序。

前端期望接口返回：

```json
{
  "updatedAt": "2026-05-24T12:00:00+08:00",
  "items": [
    {
      "name": "法式星芒裸粉",
      "sub": "裸粉 · 星光钻饰",
      "price": "¥229",
      "image": "款式图/2277d6f9d82264fa6a3c986373e5e44c2292083.webp",
      "xhsUrl": "https://www.xiaohongshu.com/...",
      "viewCount": 12000,
      "likeCount": 880,
      "collectCount": 360,
      "commentCount": 96,
      "noteCount": 42
    }
  ]
}
```

如果接口已经计算好热度，可以直接返回 `heatScore`。否则前端会根据浏览、点赞、收藏、评论、笔记数量计算排序。

### 学生版关键词热度

如果没有小红书开发者账号或后端接口，项目会自动启用学生版关键词热度：

- `scripts/xhs-config.js` 里的 `keywordFallback: true`
- `scripts/xhs-keyword-heat.js` 里维护关键词和 `score`
- `scripts/xhs-keyword-heat.js` 里的 `XHS_STYLE_KEYWORDS` 会把关键词匹配到本地款式图

这不是官方实时数据，但适合课堂原型和作品展示。要更新榜单，只需要把小红书里观察到更热门的关键词分数调高。

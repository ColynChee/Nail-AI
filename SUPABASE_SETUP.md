# Supabase 数据库配置指南

本指南面向第一次配置 Supabase 的开发者，完整覆盖从建项目到后端跑通的全部步骤。

---

## 第一步：注册 / 登录 Supabase

1. 打开 [https://supabase.com](https://supabase.com)
2. 点右上角 **Start your project**，用 GitHub 账号或邮箱注册
3. 登录成功后进入 Dashboard

---

## 第二步：新建项目

1. 点击 **New project**
2. 填写以下信息：
   - **Organization**：选择你的组织（默认会有一个）
   - **Project name**：随意填，例如 `Nail-AI`
   - **Database password**：设一个强密码，**务必记住**，后面要用
   - **Region**：选 **Southeast Asia (Singapore)** 或 **Northeast Asia (Tokyo)**，不要选 Americas（服务器在美国会很慢）
3. 点 **Create new project**
4. 等待 1~2 分钟，状态变为 **Healthy** 即为成功

---

## 第三步：获取数据库连接字符串（DATABASE_URL）

> 注意：必须使用 **Session pooler**，不能用 Direct connection（Direct 是 IPv6，本地网络通常是 IPv4 会连不上）

1. 进入项目后，点顶部绿色的 **Connect** 按钮
2. 在弹出框里，**Connection Method** 选 **Session pooler**
3. **Type** 保持 **URI**
4. 复制 **Connection string** 框里的内容，格式如下：

```
postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
```

5. 把 `[YOUR-PASSWORD]` 替换为第二步设的数据库密码

> 最终格式示例：
> ```
> postgresql://postgres.xgbbmvfuzwsomvuetgwt:MyPassword123@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
> ```

---

## 第四步：配置后端环境变量

**方式 A：写入 .env 文件（推荐，持久生效）**

在 `backend/` 目录下新建 `.env` 文件（参考 `.env.example`），填入：

```env
DATABASE_URL=postgresql://postgres.xxxxxxxxxxxx:你的密码@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
MODELSCOPE_TOKEN=你的ModelScope token
```

> `.env` 文件已在 `.gitignore` 中，不会被上传到 GitHub，密码安全。

**方式 B：在终端临时设置（关闭终端后失效）**

```powershell
$env:DATABASE_URL = "postgresql://postgres.xxxxxxxxxxxx:你的密码@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"
$env:MODELSCOPE_TOKEN = "你的token"
```

然后在**同一个终端窗口**启动后端：

```powershell
cd d:\指上谈兵\backend
python -m uvicorn main:app --reload --port 8000
```

---

## 第五步：安装依赖

如果后端报 `No module named 'asyncpg'`：

```powershell
pip install asyncpg
```

---

## 第六步：在 Supabase 创建数据库表

> 所有 SQL 都在 Supabase 控制台的 **SQL Editor** 里运行（左侧导航栏 → SQL Editor → 点 New query → 粘贴 → Run）

如果提示 "Potential issue detected"（RLS 警告），点 **Run without RLS** 即可。

---

### 6.1 账号系统 + 收藏表

文件路径：`backend/db/schema_accounts.sql`

```sql
CREATE TABLE IF NOT EXISTS accounts (
  id            BIGSERIAL PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  salt          TEXT NOT NULL,
  client_key    TEXT NOT NULL UNIQUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_wishlist (
  id         BIGSERIAL PRIMARY KEY,
  client_id  TEXT NOT NULL,
  name       TEXT NOT NULL,
  emoji      TEXT,
  price      TEXT,
  bg         TEXT,
  image      TEXT,
  design_id  TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (client_id, name)
);

CREATE INDEX IF NOT EXISTS idx_user_wishlist_client ON user_wishlist (client_id);
```

---

### 6.2 核心业务表（款式、模具、试戴日志、用户档案）

文件路径：`backend/supabase/migrations/20260603150004_init_schema.sql`

```sql
create extension if not exists vector;

create table if not exists designs (
  id text primary key,
  name text not null,
  image text,
  emoji text,
  bg text,
  price text,
  enhanced_hash text,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists designs_created_at_idx on designs (created_at desc);
create index if not exists designs_enhanced_hash_idx on designs (enhanced_hash);

create table if not exists molds (
  id bigserial primary key,
  design_id text not null,
  finger_idx smallint not null check (finger_idx between 0 and 4),
  path text not null,
  mime_type text not null default 'image/png',
  created_at timestamptz not null default now(),
  unique (design_id, finger_idx)
);

create index if not exists molds_design_id_idx on molds (design_id);

create table if not exists try_on_logs (
  id bigserial primary key,
  design_id text,
  success boolean not null default false,
  message text,
  mode text,
  n_applied integer,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists try_on_logs_created_at_idx on try_on_logs (created_at desc);
create index if not exists try_on_logs_design_id_idx on try_on_logs (design_id);
create index if not exists try_on_logs_success_idx on try_on_logs (success);

create table if not exists user_profiles (
  client_id text primary key,
  name text,
  avatar text,
  age integer,
  bio text,
  skin_color_code text,
  skin_tone_label text,
  skin_tone_source text,
  recommended_style_ids jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists user_profiles_updated_at_idx on user_profiles (updated_at desc);
create index if not exists user_profiles_skin_color_code_idx on user_profiles (skin_color_code);
```

> 如果运行时报 `extension "vector" does not exist`，删掉第一行 `create extension if not exists vector;` 再运行。

---

### 6.3 我的设计表

文件路径：`backend/db/schema_user_designs.sql`

```sql
CREATE TABLE IF NOT EXISTS user_designs (
  id                  BIGSERIAL PRIMARY KEY,
  client_id           TEXT NOT NULL,
  name                TEXT NOT NULL DEFAULT '我的设计',
  image_url           TEXT NOT NULL,
  source              TEXT NOT NULL DEFAULT 'upload'
                        CHECK (source IN ('upload','ai','gallery')),
  style               TEXT,
  scenes              JSONB NOT NULL DEFAULT '[]'::jsonb,
  recommended_colors  JSONB NOT NULL DEFAULT '[]'::jsonb,
  description         TEXT,
  tags                JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_designs_client
  ON user_designs (client_id, created_at DESC);
```

---

### 6.4 补丁：user_wishlist 补加 design_id 列

如果 6.1 的建表 SQL 里 `user_wishlist` 没有 `design_id` 列，运行：

```sql
ALTER TABLE user_wishlist ADD COLUMN IF NOT EXISTS design_id TEXT;
```

### 6.5 补丁：user_designs 补加 design_id 列

```sql
ALTER TABLE user_designs ADD COLUMN IF NOT EXISTS design_id TEXT;
```

---

## 第七步：验证后端启动正常

重启后端后，终端应出现：

```
[DB] connection pool created
INFO:     Application startup complete.
```

如果出现 `[DB] pool creation failed: DATABASE_URL is not set`，说明 `.env` 文件没有被读取，检查文件是否在 `backend/` 目录下（不是项目根目录）。

---

## 常见问题

| 报错 | 原因 | 解决 |
|------|------|------|
| `DATABASE_URL is not set` | `.env` 文件路径不对或未创建 | 确认 `backend/.env` 存在且格式正确 |
| `No module named 'asyncpg'` | 依赖未安装 | `pip install asyncpg` |
| `relation "accounts" does not exist` | 建表 SQL 未运行 | 在 SQL Editor 运行第六步的 SQL |
| `column "design_id" of relation "user_wishlist" does not exist` | 旧版建表缺少该列 | 运行 6.4 的 ALTER TABLE |
| `column "design_id" of relation "user_designs" does not exist` | 旧版建表缺少该列 | 运行 6.5 的 ALTER TABLE |
| `Not IPv4 compatible` | 使用了 Direct connection | 改用 Session pooler 连接字符串 |
| `extension "vector" does not exist` | 免费版不支持 pgvector | 删掉 `create extension if not exists vector;` 那行 |

---

## 表结构总览

| 表名 | 用途 |
|------|------|
| `accounts` | 用户账号（用户名、密码哈希） |
| `user_wishlist` | 用户收藏的款式 |
| `user_profiles` | 用户档案（肤色、推荐风格等） |
| `user_designs` | 用户上传/AI生成的设计图 |
| `designs` | 平台款式库（从 designs.json 同步） |
| `molds` | 指甲模具文件路径 |
| `try_on_logs` | 试戴操作日志 |

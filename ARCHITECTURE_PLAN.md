# Docx Formatter — 前后端分离架构规划

## 一、整体架构

```
┌─────────────────────────────────────────────┐
│  Frontend (React + Vite + TypeScript)        │
│  独立部署到静态托管 (Nginx / CDN / Vercel)     │
│  端口 5173(dev) → 产物放 dist/(prod)          │
└──────────────────┬──────────────────────────┘
                   │ REST API (JSON)
                   ▼
┌─────────────────────────────────────────────┐
│  Backend (FastAPI + Rust Engine)             │
│  端口 8000                                    │
│  CORS 允许前端域名                              │
│  新增：兑换码中间件、模板 CRUD、批量任务          │
└─────────────────────────────────────────────┘
```

## 二、前端项目结构

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── public/
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/                    # API 调用封装
    │   └── client.ts           # fetch 封装 + 兑换码 header 注入
    ├── hooks/                  # 自定义 hooks
    │   ├── useAuth.ts          # 兑换码管理 (存 localStorage)
    │   └── useTaskPolling.ts   # 任务轮询
    ├── components/             # 通用组件
    │   ├── Layout.tsx
    │   ├── FileUpload.tsx
    │   ├── ProgressBar.tsx
    │   └── ClassificationTable.tsx
    ├── pages/                  # 页面
    │   ├── Home.tsx            # 首页：上传 + 排版
    │   ├── Templates.tsx       # 模板管理
    │   ├── Batch.tsx           # 批量处理
    │   └── History.tsx         # 本地历史记录
    └── types/                  # TypeScript 类型
        └── index.ts
```

## 三、API 设计（新增 + 调整）

所有需要配额的接口，请求头带 `X-Redeem-Code: xxx`，后端中间件统一校验。

### 3.1 兑换码系统

```
POST   /api/redeem/check        # 校验兑换码有效性，返回 { valid, remaining }
POST   /api/redeem/activate     # 首次使用兑换码，绑定到浏览器指纹（可选）
```

### 3.2 模板管理

```
GET    /api/templates                     # 获取所有模板（内置 + 用户自定义）
POST   /api/templates                     # 创建自定义模板 { name, config_json }
PUT    /api/templates/{id}                # 更新模板
DELETE /api/templates/{id}                # 删除模板
GET    /api/templates/{id}/config         # 获取模板配置 JSON
```

模板存储：SQLite（单文件数据库，零运维）。

### 3.3 批量处理

```
POST   /api/batch                         # 提交批量任务 { files: [...], template_id, page_number_config }
GET    /api/batch/{batch_id}              # 查询批量任务进度
GET    /api/batch/{batch_id}/items        # 查询每个子任务状态
GET    /api/batch/{batch_id}/download     # 打包下载所有结果 (zip)
```

### 3.4 原有接口调整

```
POST   /api/format          # 新增 X-Redeem-Code header，扣减配额
GET    /api/tasks/{id}      # 不变
GET    /download/{id}       # 不变
```

## 四、后端数据模型

### 4.1 兑换码表 `redeem_codes`

```sql
CREATE TABLE redeem_codes (
    id          INTEGER PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,       -- 兑换码字符串
    total_quota INTEGER NOT NULL,           -- 总次数
    used_quota  INTEGER NOT NULL DEFAULT 0, -- 已用次数
    is_active   BOOLEAN DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP                   -- 可选过期时间
);
```

### 4.2 模板表 `templates`

```sql
CREATE TABLE templates (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    config_json TEXT NOT NULL,              -- TemplateConfig JSON
    is_builtin  BOOLEAN DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.3 批量任务表 `batch_tasks`

```sql
CREATE TABLE batch_tasks (
    id          TEXT PRIMARY KEY,           -- batch_id
    code        TEXT NOT NULL,              -- 兑换码
    template_id INTEGER,
    status      TEXT DEFAULT 'pending',     -- pending/processing/completed/failed
    total       INTEGER,
    completed   INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 五、兑换码中间件

```
请求进入 → X-Redeem-Code header
  ↓
查表验证码存在 + 未过期 + active + used < total
  ↓
通过 → 继续处理，完成后扣减 used_quota
失败 → 403 { error: "invalid_code" | "expired" | "quota_exhausted" }
```

不需要 session/JWT。每次请求独立校验码。

## 六、客户端本地存储

历史记录存 localStorage，结构：

```typescript
interface HistoryItem {
  id: string;              // task_id
  filename: string;
  template: string;
  status: 'completed' | 'failed';
  timestamp: number;       // Date.now()
}
// key: "docfmt_history"
// value: JSON string of HistoryItem[]
```

前端负责增删读写，后端不参与。

## 七、文件目录变更

```
docx-formatter/
├── engine/                    # 不变
├── python/
│   ├── app/
│   │   ├── api/
│   │   │   ├── main.py        # 添加 CORS，调整路由
│   │   │   ├── templates.py   # 新增：模板 CRUD 路由
│   │   │   ├── batch.py       # 新增：批量处理路由
│   │   │   └── redeem.py      # 新增：兑换码路由
│   │   ├── core/
│   │   │   ├── pipeline.py    # 不变
│   │   │   ├── classifier.py  # 不变
│   │   │   ├── llm_client.py  # 不变
│   │   │   ├── batch.py       # 新增：批量处理逻辑
│   │   │   └── redeem.py      # 新增：兑换码校验逻辑
│   │   ├── db.py              # 新增：SQLite 初始化 + 连接
│   │   ├── middleware.py      # 新增：兑换码中间件
│   │   └── config.py          # 新增配置项
│   └── static/                # 旧前端，可保留或删除
├── frontend/                  # 新增：React + Vite 前端项目
├── CLAUDE.md
├── Dockerfile                 # 多阶段：构建前端 + Rust + Python
├── docker-compose.yml
└── pyproject.toml
```

## 八、Docker 部署调整

Dockerfile 新增前端构建阶段：

```dockerfile
# Stage 0: Build frontend
FROM node:20-alpine AS frontend-builder
COPY frontend/ /build/
WORKDIR /build
RUN npm ci && npm run build

# Stage 1: Build Rust (不变)
FROM rust:1.80-bookworm AS builder
...

# Stage 2: Python runtime (不变，但 COPY 前端产物到 static/)
FROM python:3.12-slim-bookworm
COPY --from=frontend-builder /build/dist/ /app/python/static/
```

## 九、实施顺序

1. **后端基础设施**：SQLite 初始化 + 兑换码 CRUD + 中间件
2. **模板 CRUD API**：从硬编码迁移到数据库
3. **前端脚手架**：React + Vite + TypeScript + 路由 + API 封装
4. **首页重写**：上传 + 排版（复刻现有功能）
5. **模板管理页面**
6. **批量处理后端 + 前端**
7. **历史记录（localStorage）**
8. **Docker 多阶段构建调整**
9. **兑换码管理后台**（可选，后续再做：管理员生成/查看兑换码）

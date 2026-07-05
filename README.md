# AI Study Platform

AI Study Platform 是一个基于 FastAPI、LangGraph、LangChain、Vue、TypeScript、PostgreSQL、Redis、Celery 和 SSE 的 AI 学习教练平台。

用户输入学习目标后，系统会生成阶段化学习路线，调用多个 Agent 完成知识讲解、开源项目分析、作品集任务设计、学习报告生成、测验评分、补弱建议和模拟面试，形成从目标规划到学习反馈的闭环。

## 核心能力

- 多 Agent 编排：Planner、Tutor、OpenSource Mentor、Reporter、Assessment、Interview、Supervisor。
- 学习闭环：目标输入、路线规划、阶段学习、测验、报告、补弱、面试模拟。
- 流式进度：前端通过 SSE 接收 Agent 执行阶段、最终状态和错误事件。
- 用户认证：JWT access token 与 refresh token。
- 异步任务：Celery + Redis 执行学习任务，避免长任务阻塞 API。
- 数据存储：PostgreSQL 保存用户、学习会话、任务状态和学习记录。
- 短期记忆：Redis 保存近期学习事件和任务队列状态。
- 外部依赖降级：LLM 和 GitHub 调用失败时使用确定性 fallback，便于本地开发与测试。
- 工程化环境：后端依赖统一使用 uv，前端依赖统一使用 npm。

## 技术栈

- 后端：Python 3.12、FastAPI、LangGraph、LangChain、SQLAlchemy、Alembic
- 异步任务：Celery、Redis
- 数据库：PostgreSQL
- 前端：Vue 3、Vite、TypeScript、npm
- 质量检查：pytest、ruff、vue-tsc、vite build
- 部署：Docker、Docker Compose
- 包管理：uv、npm

## 项目结构

```text
ai_study_platform/
├── app/
│   ├── api/                 FastAPI 路由
│   ├── agents/              Agent 节点
│   ├── mcp/                 GitHub 与文件系统工具客户端
│   ├── models/              SQLAlchemy 模型
│   ├── schemas/             Pydantic 数据契约
│   ├── services/            LLM、存储、记忆、观测服务
│   ├── tasks/               Celery 后台任务
│   ├── celery_app.py        Celery 应用入口
│   ├── graph.py             LangGraph 工作流
│   └── main.py              FastAPI 应用入口
├── alembic/                 数据库迁移
├── docs/                    架构与工程说明
├── frontend/vue/            Vue 前端源码
│   └── package-lock.json    前端 npm 锁文件
├── tests/                   后端测试
├── Dockerfile               后端镜像
├── docker-compose.yml       本地开发编排
├── docker-compose.prod.yml  生产编排模板
├── pyproject.toml           后端依赖声明
├── uv.lock                  后端依赖锁文件
├── setup-local.ps1          本地环境初始化
├── dev.ps1                  启动后端 API
└── check.ps1                后端 lint/test + 前端 build
```

## 包管理约定

本项目只保留两套包管理方式：

- 后端：`uv` + `pyproject.toml` + `uv.lock`
- 前端：`npm` + `frontend/vue/package-lock.json`

不要再新增或恢复以下文件：

```text
requirements.txt
requirements-dev.txt
pnpm-lock.yaml
pnpm-workspace.yaml
```

本地后端虚拟环境固定使用：

```text
.platform-venv
```

注意：uv 默认会优先使用项目根目录的 `.venv`。如果本机残留坏的 `.venv`，直接执行 `uv sync` 可能报错。请使用项目脚本，或者手动设置：

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".platform-venv"
```

## 本地环境准备

前置要求：

- Python 3.12，由 uv 安装和管理
- uv
- Node.js / npm
- PostgreSQL
- Redis

首次准备：

```powershell
cd E:\my-project\ai_study_platform
Copy-Item .env.example .env
.\setup-local.ps1
```

`setup-local.ps1` 会执行：

- 设置 `UV_CACHE_DIR=.uv-cache`
- 设置 `UV_PROJECT_ENVIRONMENT=.platform-venv`
- 安装 Python 3.12
- 执行 `uv sync --extra dev`
- 在 `frontend/vue` 执行 `npm ci`

## 本地启动

### 1. 启动后端 API

```powershell
cd E:\my-project\ai_study_platform
.\dev.ps1
```

后端默认地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

如果不用脚本，也可以手动执行：

```powershell
cd E:\my-project\ai_study_platform
$env:UV_PROJECT_ENVIRONMENT = ".platform-venv"
$env:UV_CACHE_DIR = ".uv-cache"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 启动 Celery Worker

如果要执行完整学习任务链路，需要单独启动 Worker：

```powershell
cd E:\my-project\ai_study_platform
$env:UV_PROJECT_ENVIRONMENT = ".platform-venv"
$env:UV_CACHE_DIR = ".uv-cache"
uv run celery -A app.celery_app.celery_app worker --loglevel=info
```

### 3. 启动前端

```powershell
cd E:\my-project\ai_study_platform\frontend\vue
npm run dev
```

前端默认地址：

```text
http://127.0.0.1:5173
```

## Docker 开发环境

本地开发可以直接用 Docker Compose 启动完整服务：

```powershell
cd E:\my-project\ai_study_platform
docker compose up --build
```

开发版 Compose 包含：

- backend：FastAPI 后端
- worker：Celery Worker
- frontend：Vue/Vite 开发服务
- postgres：PostgreSQL
- redis：Redis

访问地址：

```text
前端：http://localhost:5173
后端：http://localhost:8000
```

查看配置：

```powershell
docker compose config
```

注意：`docker compose config` 会展开 `.env` 中的真实密钥，不要截图或外发完整输出。

关闭服务：

```powershell
docker compose down
```

## Docker 镜像上传

后端和前端建议分别构建镜像，运行时通过 Docker Compose 组合：

```powershell
cd E:\my-project\ai_study_platform

docker build -t haohao112/learning-coach-backend:dev .
docker push haohao112/learning-coach-backend:dev

docker build -t haohao112/learning-coach-frontend:dev .\frontend\vue
docker push haohao112/learning-coach-frontend:dev
```

后端 API 和 Celery Worker 可以共用同一个后端镜像；前端使用独立镜像；PostgreSQL 和 Redis 使用官方镜像。

## 环境变量

关键变量见 `.env.example`。

开发环境常用变量：

```env
APP_ENV=development
DATABASE_URL=postgresql://postgres:12345@127.0.0.1:5432/ai_study_platform_db
REDIS_URL=redis://localhost:6379/3
CELERY_BROKER_URL=redis://localhost:6379/4
CELERY_RESULT_BACKEND=redis://localhost:6379/5
COACH_LLM_BASE_URL=https://api.deepseek.com
COACH_LLM_MODEL=deepseek-chat
COACH_LLM_API_KEY=
```

开发环境可以不配置 `COACH_LLM_API_KEY`，系统会使用确定性 fallback 数据，便于测试完整流程。

生产环境必须配置：

- `APP_ENV=production`
- `DATABASE_URL`
- `REDIS_PASSWORD`
- `SECRET_KEY`
- `REFRESH_SECRET_KEY`
- `COACH_LLM_API_KEY`

生产密钥建议至少 32 字节，避免 JWT HMAC key 过短警告。

## 数据库迁移

项目使用 Alembic 管理数据库结构。

本地执行：

```powershell
cd E:\my-project\ai_study_platform
$env:UV_PROJECT_ENVIRONMENT = ".platform-venv"
uv run alembic upgrade head
```

Docker 开发和生产 Compose 已在后端启动命令中自动执行：

```text
alembic upgrade head
```

## 测试与质量检查

统一检查入口：

```powershell
cd E:\my-project\ai_study_platform
.\check.ps1
```

单独运行后端 lint：

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".platform-venv"
uv run --extra dev ruff check .
```

单独运行后端测试：

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".platform-venv"
uv run --extra dev pytest
```

单独运行前端构建：

```powershell
cd E:\my-project\ai_study_platform\frontend\vue
npm run build
```

## 常见问题

### uv sync 为什么还找 .venv？

uv 的项目默认环境名是 `.venv`。本项目为了和其他项目区分，统一使用 `.platform-venv`。因此请使用 `setup-local.ps1`、`dev.ps1`、`check.ps1`，或者手动设置：

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".platform-venv"
```

### 后端启动后看到 401 是不是失败？

不是。类似下面的日志表示接口需要登录，但当前请求没有 token：

```text
GET /learning-coach/sessions/latest 401 Unauthorized
```

只要看到 `Application startup complete`，说明后端启动成功。

### InsecureKeyLengthWarning 是什么？

这是开发密钥太短导致的 JWT 警告。开发环境不影响运行；想消除警告，可以在 `.env` 中设置更长的：

```env
SECRET_KEY=dev-secret-key-change-me-please-32bytes
REFRESH_SECRET_KEY=dev-refresh-secret-key-change-me-32bytes
```

### 上传 Docker 镜像时前后端是一个文件还是两个？

是两个镜像：后端镜像和前端镜像。运行时通过 Docker Compose 和 PostgreSQL、Redis 一起组成完整系统。

## 生产部署

生产 Compose 使用生产配置和更严格的环境变量校验：

```powershell
cd E:\my-project\ai_study_platform
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up --build -d
```

生产模式下，如果缺少安全密钥、数据库连接或 LLM Key，应用会启动失败，这是为了避免误用开发配置。

## 工程化路线

下一步建议按优先级推进：

1. 为 SSE 增加短期一次性 stream token，避免长期 access token 出现在 URL 中。
2. 增加登录限流、结构化审计日志和生产错误脱敏。
3. 增加 OpenTelemetry、Sentry 或等价监控能力。
4. 补充更多 API 集成测试和前端端到端测试。
5. 增加 Docker 镜像发布流程和 CI 自动构建。

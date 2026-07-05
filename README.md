# AI Study Platform

AI Study Platform 是一个基于 FastAPI、LangGraph、LangChain、Vue、TypeScript、PostgreSQL、Redis、Celery 和 SSE 的 AI 学习教练平台。

用户输入学习目标后，系统会生成学习路线，并通过多个 Agent 完成知识讲解、开源项目分析、作品集任务设计、学习报告、测验评分、补弱建议和模拟面试，形成从目标规划到学习反馈的闭环。

## 核心能力

- 多 Agent 编排：Planner、Tutor、OpenSource Mentor、Reporter、Assessment、Interview、Supervisor。
- 学习闭环：学习路线、本周内容、开源参考、项目任务、测验、补弱、面试。
- SSE 进度推送：前端实时接收 Agent 阶段、最终状态和错误事件。
- 打字机展示：前端对长内容做渐进式显示，减少等待感。
- JWT 鉴权：access token + refresh token，用户数据按账号隔离。
- 异步任务：Celery + Redis 执行长任务，避免 API 被 Agent 工作流阻塞。
- 持久化：PostgreSQL 保存用户、学习会话、测验、产物和长期记忆。
- 短期记忆：Redis 保存近期学习事件、任务队列和临时状态。
- 降级策略：LLM 或 GitHub 调用失败时使用确定性 fallback，便于本地开发和测试。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 后端 | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Agent | LangGraph, LangChain, OpenAI-compatible LLM |
| 异步任务 | Celery, Redis |
| 数据库 | PostgreSQL |
| 前端 | Vue 3, Vite, TypeScript, npm |
| 质量检查 | pytest, ruff, vue-tsc, vite build |
| 部署 | Docker, Docker Compose |
| 依赖管理 | uv, npm |

## 项目结构

```text
ai_study_platform/
├── app/
│   ├── api/              # FastAPI 路由
│   ├── agents/           # Agent 节点
│   ├── mcp/              # GitHub 和文件系统工具适配层
│   ├── models/           # SQLAlchemy 模型
│   ├── schemas/          # Pydantic 数据契约
│   ├── services/         # LLM、存储、记忆、观测服务
│   ├── celery_app.py     # Celery 应用入口
│   ├── graph.py          # LangGraph 工作流
│   └── main.py           # FastAPI 应用入口
├── alembic/              # 数据库迁移
├── docs/                 # 工程说明和面试设计材料
├── frontend/vue/         # Vue 前端
├── tests/                # 后端测试
├── docker-compose.yml    # 本地 Docker 编排
├── docker-compose.prod.yml
├── pyproject.toml
├── uv.lock
├── dev.ps1               # 本地后端启动脚本
├── check.ps1             # 本地质量检查脚本
└── setup-local.ps1       # 本地环境初始化脚本
```

## 依赖约定

后端只使用 uv：

```text
pyproject.toml + uv.lock
```

前端只使用 npm：

```text
frontend/vue/package.json + frontend/vue/package-lock.json
```

不要恢复或新增这些文件：

```text
requirements.txt
requirements-dev.txt
pnpm-lock.yaml
pnpm-workspace.yaml
```

本地后端虚拟环境统一使用 `.platform-venv`。当前项目根目录的 `.venv` 是指向 `.platform-venv` 的 Junction，用于兼容 uv 默认行为。

## 本地准备

前置要求：

- Python 3.12
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

`setup-local.ps1` 会安装 Python 依赖并在 `frontend/vue` 执行 `npm ci`。

## 本地启动

### 1. 启动后端 API

推荐使用脚本：

```powershell
cd E:\my-project\ai_study_platform
.\dev.ps1
```

或者手动启动：

```powershell
cd E:\my-project\ai_study_platform
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-dir alembic
```

后端地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

### 2. 启动 Celery Worker

完整执行学习任务链路需要单独启动 Worker：

```powershell
cd E:\my-project\ai_study_platform
uv run celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo
```

Windows 本机建议使用 `--pool=solo`，避免 Celery 默认进程池兼容性问题。

### 3. 启动前端

```powershell
cd E:\my-project\ai_study_platform\frontend\vue
npm run dev
```

前端地址：

```text
http://127.0.0.1:5173
```

## Docker 开发环境

```powershell
cd E:\my-project\ai_study_platform
docker compose up --build
```

开发 Compose 包含：

- backend: FastAPI API
- worker: Celery Worker
- frontend: Vue/Vite dev server
- postgres: PostgreSQL
- redis: Redis

访问地址：

```text
frontend: http://localhost:5173
backend:  http://localhost:8000
```

关闭服务：

```powershell
docker compose down
```

查看配置：

```powershell
docker compose config
```

注意：`docker compose config` 会展开 `.env` 里的真实密钥，不要截图或外发完整输出。

## 环境变量

开发环境常用变量见 `.env.example`：

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

开发环境可以不配置 `COACH_LLM_API_KEY`，系统会使用 fallback 数据跑通流程。生产环境必须配置安全密钥、数据库、Redis 和 LLM Key。

## 数据库迁移

```powershell
cd E:\my-project\ai_study_platform
uv run alembic upgrade head
```

Docker Compose 的 backend/worker 启动命令会自动执行 `alembic upgrade head`。

## 测试与质量检查

统一检查：

```powershell
cd E:\my-project\ai_study_platform
.\check.ps1
```

单独运行后端 lint：

```powershell
uv run --extra dev ruff check .
```

单独运行后端测试：

```powershell
uv run --extra dev pytest
```

单独运行前端构建：

```powershell
cd E:\my-project\ai_study_platform\frontend\vue
npm run build
```

## 常见问题

### 后端为什么关不掉？

`uvicorn --reload` 会产生父子进程树：uv -> uvicorn/python reloader -> python server。只关闭窗口或只杀监听端口进程时，父进程可能重新拉起子进程。

可以按项目命令行过滤后停止：

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like '*ai_study_platform*' -and
    ($_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*app.main:app*')
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

### 后端启动后看到 401 是失败吗？

不是。`GET /learning-coach/sessions/latest 401 Unauthorized` 说明接口需要登录但当前请求没有 token。只要看到 `Application startup complete`，后端就是启动成功。

### 完整学习任务一直 queued？

通常是 Celery Worker 没启动。启动 API 只负责接收请求，真正的 Agent 长任务需要 Worker 消费 Redis 队列。

## 生产部署

```powershell
cd E:\my-project\ai_study_platform
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up --build -d
```

生产模式下如果缺少 `SECRET_KEY`、`REFRESH_SECRET_KEY`、`DATABASE_URL` 或 LLM Key，应用会拒绝启动，避免误用开发配置。

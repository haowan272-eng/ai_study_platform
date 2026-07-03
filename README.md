# AI Agent Learning Coach

AI Agent Learning Coach 是一个基于 FastAPI、LangGraph、LangChain、Vue、TypeScript 和 SSE 的多智能体学习教练项目。

用户输入学习目标后，系统会生成学习路线、讲解知识点、搜索并分析 GitHub 项目、设计作品集任务、生成学习报告、出题测验、评分补弱，并进入模拟面试环节。

## 核心能力

- 多 Agent 编排：Planner、Tutor、OpenSource Mentor、Reporter、Assessment、Interview、Supervisor。
- 流式进度：前端通过 SSE 接收 Agent 执行阶段、最终状态和错误事件。
- 用户认证：JWT access token 与 refresh token。
- 数据存储：PostgreSQL 优先，文件归档作为降级方案。
- 短期记忆：Redis 保存近期学习事件。
- 外部依赖降级：LLM 和 GitHub 调用失败时使用确定性 fallback，方便本地开发与测试。

## 项目结构

```text
app/
  api/                 FastAPI 路由
  agents/              Agent 节点
  mcp/                 GitHub 与文件系统工具客户端
  models/              SQLAlchemy 模型
  schemas/             Pydantic 数据契约
  services/            LLM、存储、记忆、观测服务
  graph.py             LangGraph 工作流
  main.py              FastAPI 应用入口
frontend/vue/
  src/                 Vue 前端源码
  Dockerfile           前端生产镜像
  nginx.conf           前端静态服务配置
tests/                 后端测试
docs/                  架构与工程说明
```

## 本地启动

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

使用 Docker 启动开发环境：

```powershell
docker compose up --build
```

后端接口：

```text
http://localhost:8000/docs
```

前端页面：

```text
http://localhost:5173
```

也可以单独启动后端：

```powershell
pip install -r requirements-dev.txt
.\dev.ps1
```

前端单独启动：

```powershell
cd frontend/vue
npm install
npm run dev
```

## 环境变量

关键变量见 `.env.example`。

生产环境必须配置：

- `APP_ENV=production`
- `DATABASE_URL`
- `REDIS_PASSWORD`
- `SECRET_KEY`
- `REFRESH_SECRET_KEY`
- `COACH_LLM_API_KEY`

开发环境可以不配置 `COACH_LLM_API_KEY`，系统会使用确定性 fallback 数据，便于测试完整流程。

## 数据库迁移

项目使用 Alembic 管理数据库结构，不再在应用启动时通过 `ensure_schema()` 自动建表。

首次启动或模型变更后执行：

```powershell
alembic upgrade head
```

Docker 开发和生产 compose 已在后端启动命令中自动执行 `alembic upgrade head`。

## 测试与质量检查

后端测试：

```powershell
python -m pytest
```

后端 lint：

```powershell
python -m ruff check .
```

前端构建：

```powershell
cd frontend/vue
npm run build
```

统一检查入口：

```powershell
.\check.ps1
```

## 生产部署

生产 compose 使用预构建镜像，不在容器启动时安装前端依赖：

```powershell
docker compose -f docker-compose.prod.yml up --build -d
```

生产模式下，如果缺少安全密钥或误用默认 SQLite 数据库，应用会启动失败。

## 工程化路线

当前项目已经具备工程化原型基础。下一步建议按优先级推进：

1. 为 SSE 增加短期一次性 stream token，避免长期 access token 出现在 URL 中。
2. 增加登录限流、结构化审计日志和生产错误脱敏。
3. 增加 OpenTelemetry、Sentry 或等价监控能力。
4. 补充更多 API 集成测试和前端端到端测试。

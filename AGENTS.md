# AGENTS.md

## 项目概览

本仓库是 `agent-engine`,一个面向 Agent Engine AI 产品的 Python Skill 运行时。
它加载本地 Skill 包、执行 Tool 包、路由模型调用、记录 run/trace/artifact,
并通过 SDK、CLI、FastAPI 暴露同一套核心引擎。

主门面(facade)是 `engine/app/engine.py` 中的 `SkillEngine`。

## 架构硬约束（必须遵守）

### 后端 DDD 分层

所有后端服务（`engine/`、`account-service/` 及未来服务）`app/` 下**只允许**这些顶层包：

```text
domain/           领域模型、纯规则、值对象；禁止 I/O / FastAPI / SQLAlchemy Session
application/      用例编排、Ports（Protocol）；禁止 import infrastructure 具体实现
infrastructure/   持久化、外部系统、token/DB 适配器
interfaces/       HTTP / CLI / 脚本入口；只调 application，禁止绕过
```

依赖方向：

```text
interfaces → application → domain
infrastructure → domain   （实现 application 定义的 Port）
禁止：application → infrastructure；domain → 其它层
```

`engine/tests/test_architecture_layers.py` 与 `account-service/tests/test_layers.py` 会强制校验。

### 前端组件复用

- 通用 UI 放 `web/src/components/`，页面只组合不复制样式类堆砌
- 新页面优先复用 `PageShell` / `DataTable` / `EmptyState` / `ErrorBox` / `Pill` 等
- 业务页放 `web/src/pages/`，API 封装放 `web/src/api/`
- 禁止把 engine 内部 Python 模块耦合进前端

## 仓库结构

根目录按“代码 / 账号服务 / 原型 / 文档 / 规范文档”组织:

- `engine/`:后端内核,自成项目根。**构建/运行/测试一律先 `cd engine`。**
  - `engine/app/`:DDD 分层；`engine.py` 为公共门面 `SkillEngine`
  - `engine/tests/`、`engine/resources/`
- `account-service/`:**独立账号权限服务**（登录、用户、账号映射）
  - 同样 DDD：`app/domain|application|infrastructure|interfaces`
- `web/`:前端（Vite+React+TS），对接 engine 与 account-service
- `prototype/`:产品设计稿与 HTML 冻结原型
- `docs/`、`openspec/`

## Skill 与 Tool 包约定

Skill 包包含:

- `SKILL.md`:YAML frontmatter(`name` 和 `description`),后接指令正文。
- `agent.skill.json`:Agent Engine 运行时配置、模型 profile、schema 路径、允许的 tools。
- `schemas/input.schema.json` 与 `schemas/output.schema.json`:JSON Schema 契约。
- `examples/examples.json`:用于文档与测试的示例。

Tool 包包含:

- `tool.yaml`:工具 id/type/entry/schema/运行时配置。
- `input.schema.json` 与 `output.schema.json`:JSON Schema 契约。
- Python 工具的 `main.py`。Python 工具通过 JSON stdin/stdout 通信,
  并通过 `Agent Engine_RUN_ID`、`Agent Engine_TOOL_CALL_ID`、`Agent Engine_ARTIFACT_DIR` 接收 artifact 上下文。

Skill 运行时配置不要写进 `SKILL.md`,应放在 `agent.skill.json`。

## 开发命令

命令统一在 `engine/` 下执行。首次 `uv sync --extra dev`，之后短命令：

```bash
cd engine
uv run pytest
uv run ruff check app tests
uv run mypy app
uv run ae --version
```

账号服务：

```bash
cd account-service
uv sync
uv run python -m app.interfaces.scripts.seed_users
uv run account-service
```

前端：

```bash
cd web
npm run dev
npm run typecheck
```

更多见 [docs/命令速查.md](docs/命令速查.md)。

## 已知基线记录

1.0.1：平台/运行数据 PostgreSQL；账号独立 `account-service`；界面 `web/`。  
`cd engine && uv run pytest` 约 **146 passed**。

## 工作守则

- 不要提交真实密钥。`engine/.env`、`account-service/.env` 已忽略。
- 生成的 artifact 归属 `engine/data/`，已忽略。
- 变更范围保持在当前子系统；新能力加 Port + adapter，不破坏 `SkillEngine` 公开行为。
- 修改运行时/schema/API 时同步测试。
- **禁止** application 直接 import infrastructure；**禁止**在 domain 写 I/O。
- 归位：内核 `engine/`；账号 `account-service/`；前端 `web/`；原型 `prototype/`；文档 `docs/`。
- Git：不自动 add/commit/push；本地 agent 目录不入库。

## 常用验证目标

- Skill loader：`engine/tests/test_skill_loader.py`
- 分层：`engine/tests/test_architecture_layers.py`、`account-service/tests/test_layers.py`
- 隔离：`engine/tests/test_ownership_isolation.py`
- 账号：`account-service/tests/`、`engine/tests/test_auth_*.py`

---

## 变更流程治理

变更由 OpenSpec 驱动:propose → apply → verify → archive。见 `openspec/WORKFLOW.md`。

# AGENTS.md

## 项目概览

本仓库是 `agent-engine`,一个面向 Agent Engine AI 产品的 Python Skill 运行时。
它加载本地 Skill 包、执行 Tool 包、路由模型调用、记录 run/trace/artifact,
并通过 SDK、CLI、FastAPI 暴露同一套核心引擎。

主门面(facade)是 `engine/app/engine.py` 中的 `SkillEngine`。

## 仓库结构

根目录按"代码 / 原型 / 文档 / 规范文档"四类组织:

- `engine/`:后端内核,自成项目根(`pyproject.toml`、`uv.lock`、`agent.yaml`、
  `.env`、`.venv`、`.agent/`、`data/` 都在这里)。**所有构建、运行、测试命令
  一律先 `cd engine` 再执行。**
  - `engine/app/`:核心包,按 DDD 分层 —— `domain/`(领域 schema)、
    `application/`(编排,含 `ports.py`)、`infrastructure/`(加载器、runner、
    持久化、注册表、模型 provider)、`interfaces/`(`cli/`、`http/`);
    `engine.py` 为 SDK、CLI、API 共用的公开门面。
  - `engine/tests/`:pytest 测试套件,按子系统组织。
  - `engine/resources/`:本地 Skill/Tool 资源包与示例输入
    (`skills/`、`tools/`、`inputs/`)。
- `prototype/`:原型与产品设计稿 —— 企业智能体产品设计文档、参考截图
  (`prototype/screenshots/`,不入库)。
- `docs/`:工程与架构文档(含 `diagrams/`)。
- `openspec/`:变更流程规范(OpenSpec,见下文"变更流程治理")。

预留位:未来前端界面放 `web/`(前后端分离方案见 `openspec/changes/`,
内核稳定、界面常改的边界以立项文档为准)。

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

命令统一在 `engine/` 目录下执行(项目根已移入其中):

```bash
cd engine
uv --cache-dir .uv-cache run --extra dev pytest
uv --cache-dir .uv-cache run --extra dev ruff check .
uv --cache-dir .uv-cache run --extra dev mypy app
```

常用的 CLI 冒烟测试:

```bash
cd engine
uv --cache-dir .uv-cache run --extra dev ae --version
uv --cache-dir .uv-cache run --extra dev ae tool test resources/tools/subtitle_generate_srt resources/inputs/subtitle_input.json --output json
uv --cache-dir .uv-cache run --extra dev ae skill run talking-video resources/inputs/talking-video-input.json --skills-dir resources/skills --tools-dir resources/tools --output json
uv --cache-dir .uv-cache run --extra dev ae chat --once "generate a 60 second talking video about eye-friendly desk lamps for programmers" --skills-dir resources/skills --tools-dir resources/tools --output json
```

项目在 `engine/pyproject.toml` 中声明 `requires-python = ">=3.12"`。

## 已知基线记录

2026-09-12 目录重构(engine/ 自成项目根)后,在 `engine/` 下运行
`uv --cache-dir .uv-cache run --extra dev pytest`:

结果 `127 passed, 1 warning`(警告来自 FastAPI TestClient 的 Starlette
弃用提示)。ruff 全部通过;mypy 无问题;CLI 与 catalog 读取正常。

## 工作守则

- 不要提交真实密钥。`engine/.env` 已被忽略,可能包含本地凭证。
- 生成的 artifact 归属 `engine/data/` 目录,该目录已被忽略。
- `engine/.agent/catalog.json` 可能由注册类命令创建;做隔离测试时请使用 `--catalog`。
- 变更范围保持在当前子系统内,并遵循现有的 Pydantic/Typer/FastAPI 风格。
- 修改运行时行为、schema、模型 provider 请求映射、CLI/API 行为或 Skill/Tool
  加载逻辑时,新增或更新对应测试。
- 针对窄范围的示例或 fixture 修复,优先写聚焦的测试,而不是大范围重写端到端用例。
- 除非有意变更 SDK/API 契约,否则保持 `SkillEngine` 的公开行为不变。
- Skill 与 Tool 契约使用结构化的 JSON/schema API,不要做临时性解析。
- 对已存在乱码的文件要谨慎;应有意识地修复编码,避免留下非法 Python 或非法 JSON
  的局部文本编辑。
- 归位规则:内核代码、测试、资源包放 `engine/`;产品原型类内容放 `prototype/`,
  工程文档放 `docs/`;不在根目录新增一级目录。
- Git 操作规则:**不自动执行 `git add` / `git commit` / `git push`**,仅在用户
  明确要求时执行;`.codex/`、`.claude/`、`.serena/`、`.codegraph/` 等本地
  agent/工具目录不入库。

## 常用验证目标

- Skill loader 变更:`engine/tests/test_skill_loader.py`
- Tool loader/runner 变更:`engine/tests/test_tool_loader.py`、`engine/tests/test_python_tool_runner.py`
- Skill 运行时变更:`engine/tests/test_skill_runtime.py`
- Agent 路由变更:`engine/tests/test_agent_runtime.py`
- CLI/API 变更:`engine/tests/test_cli.py`、`engine/tests/test_api_cli.py`
- 模型配置/provider 变更:`engine/tests/test_model_config.py`、`engine/tests/test_model_providers.py`
- Catalog/artifact/trace 存储变更:`engine/tests/test_catalog_store.py`、`engine/tests/test_stores.py`
- 分层规则变更:`engine/tests/test_architecture_layers.py`

---

## 变更流程治理

本仓库装有 OpenSpec(项目级 skills + CLI)与 Superpowers(Claude Code 全局)。变更流程由 OpenSpec 驱动:propose -> apply -> archive。开始任何功能/修复前,先读 `openspec/WORKFLOW.md` 并严格遵守其中分工(尤其"禁止"一节);Superpowers 只用于 brainstorming / TDD / 调试 / 收尾评审,禁止用其 writing-plans / executing-plans 作为并行流程。

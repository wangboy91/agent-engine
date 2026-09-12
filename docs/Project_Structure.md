# BKL Project Structure

本文是当前代码目录导览，用来解释每个目录、文件、主要类的职责，以及哪些模块已经实现、哪些模块只是为后续版本预留边界。

目标架构和未来 DDD 分层见 [BKL Business Agent Base Architecture](BKL_Business_Agent_Base_Architecture.md)。

从当前代码迁移到业务智能体基座的迭代路线见 [BKL Business Agent Base Roadmap](BKL_Business_Agent_Base_Roadmap.md)。

## 1. 为什么有些 Python 文件代码很少

当前项目是 v0.1 的纵向闭环实现，优先把这条主链路跑通：

```text
配置加载
  -> 注册 Tool / Skill
  -> 运行 Skill
  -> 调模型
  -> 调 Tool
  -> 校验输出
  -> 记录 Run / Trace / Artifact
  -> CLI / API / SDK 共用同一个 SkillEngine
```

所以代码量集中在：

```text
engine/app/engine.py
engine/app/interfaces/cli/main.py
engine/app/interfaces/http/main.py
engine/app/application/agent/*
engine/app/application/skill/*
engine/app/application/tool/*
engine/app/application/execution/*
engine/app/domain/agent/*
engine/app/core/schemas.py
engine/app/core/config.py
engine/app/infrastructure/package_loaders/*
engine/app/infrastructure/tool_runners/*
engine/app/infrastructure/repositories/*
engine/app/infrastructure/persistence/*
engine/app/infrastructure/tracing/*
engine/app/models/router.py
engine/app/models/providers/*
```

有些文件只有 1-2 行，是刻意保留的模块边界，后续会拆出去：

```text
interfaces/http/routes_tools.py
interfaces/http/routes_skills.py
interfaces/http/routes_runs.py
interfaces/cli/tool_commands.py
interfaces/cli/skill_commands.py
interfaces/cli/run_commands.py
tools/llm_tool.py
tools/skill_tool.py
policy/policy_engine.py
storage/database.py
storage/models.py
trace/events.py
```

这些不是核心逻辑缺失，而是 P0 还没有展开的后续扩展点。

## 2. 顶层目录

```text
engine/app/
  Core Engine 源码

engine/resources/
  示例 Tool、Skill、输入文件

engine/tests/
  pytest 测试

doc/
  技术规格、开发清单、架构说明、运行请求说明、业务智能体基座架构和路线图

bkl.yaml
  本地模型配置，真实项目中可以由 bkl init 生成

.env
  本地密钥，不提交 git
```

## 3. app 核心目录

```text
engine/app/
  __init__.py
  engine.py
  domain/
  application/
  infrastructure/
  interfaces/
  core/
  cli/
  api/
  agents/
  models/
  skills/
  tools/
  storage/
  trace/
  policy/
```

### 3.1 DDD layer package baseline

当前已开始建立目标 DDD 四层包边界：

```text
domain/
  领域概念和状态枚举。

application/
  应用用例、commands、ports。

infrastructure/
  后续承接数据库、模型 provider、Tool runner、artifact store、secret store、memory adapter。

interfaces/
  后续承接 CLI、HTTP、SDK、本地 UI 等适配层。
```

当前已实现：

```text
domain/agent/schemas.py
  AgentResponse、RouteDecision、InputResolution 等 Agent 领域数据结构。

domain/agent/scene_mapping.py
  scene_id -> skill_id + defaults 的确定性映射。

domain/agent/states.py
  AgentTurnState：Agent turn 显式状态枚举。

domain/execution/states.py
  ExecutionState：Skill / Agent 执行显式状态枚举。

application/ports.py
  SkillRegistryPort、ToolRegistryPort、ModelGatewayPort、ToolRunnerPort、ToolExecutorPort、RunStorePort、TraceStorePort、ArtifactStorePort。

application/skill/
  RunSkillCommand、RunSkillUseCase。

application/agent/
  HandleAgentMessageCommand、HandleAgentMessageUseCase、AgentLoop、SkillRouter、InputResolver、ActionRegistry。

application/tool/
  ToolExecutor，依赖 ToolRunnerPort，不直接创建 Python/API runner。

application/execution/
  SkillRuntime。

infrastructure/package_loaders/
  Skill loader、Tool loader、OpenAPI importer。

infrastructure/tool_runners/
  Python Tool runner、API Tool runner。

infrastructure/repositories/
  InMemorySkillRegistry、InMemoryToolRegistry。

infrastructure/persistence/
  LocalArtifactStore、JsonCatalogStore、InMemoryRunStore。

infrastructure/tracing/
  InMemoryTraceStore。
```

CLI 和 API 已开始通过 application use case 调用核心能力，避免 interface 层直接沉淀业务编排。

`engine/app/agents/`、`engine/app/skills/`、`engine/app/tools/` 目前只作为兼容旧 import path 的 adapter。新实现和新测试应优先使用上面的 DDD canonical path。

### 3.2 `engine.py`

主门面类：`SkillEngine`。

职责：

```text
加载模型配置
创建 Skill Registry
创建 Tool Registry
创建 Model Router
创建 Tool Executor
创建 Trace Store
创建 Artifact Store
创建 Run Store
创建 Catalog Store
对外提供 register_tool / register_skill / run_skill
```

关键类：

```python
class SkillEngine
```

关键方法：

```text
SkillEngine.load(...)
  从 bkl.yaml 和可选 catalog_path 创建 Engine。

SkillEngine.create_for_testing(...)
  创建 mock engine，用于测试和默认 CLI 示例。

register_tool(path)
  加载 Tool 包，注册到 Tool Registry，可选写入 catalog。

register_skill(path)
  加载 Skill 包，注册到 Skill Registry，可选写入 catalog。

run_skill(skill_id, input_data)
  调用 SkillRuntime 执行。

load_catalog()
  从 .bkl/catalog.json 恢复已注册 Tool / Skill。
```

### 3.3 `application/agent/` and `domain/agent/`

Agent 编排层，负责把自然语言或场景请求转成受控的 SkillEngine 调用。领域对象放在 `domain/agent/`，应用状态机和动作编排放在 `application/agent/`。

```text
domain/agent/schemas.py
  AgentResponse、RouteDecision、InputResolution、AgentSession、AgentTurn 等数据结构。

domain/agent/scene_mapping.py
  scene_id -> skill_id + defaults 的确定性映射。

application/agent/router.py
  SkillRouter：根据自然语言从已注册 Skill 中选出候选 skill_id。

application/agent/input_resolver.py
  InputResolver：根据 input.schema.json、scene defaults 和用户文本生成 input draft。

application/agent/actions.py
  ActionRegistry：确定性执行 Agent 动作；当前支持 run Skill、list Skills、list Tools。

application/agent/confirmation.py
  ConfirmationPolicy：写入类动作的确认策略边界。

application/agent/state_machine.py
  AgentLoop：串联 route、resolve、act，作为 bkl chat 和 /chat/messages 的核心。
```

`engine/app/agents/*` 是兼容导出，不再放主实现。

当前 Agent 层已经支持：

```text
自然语言 -> Skill Router -> Input Resolver -> SkillEngine.run_skill
scene_id -> skill_id + defaults -> SkillEngine.run_skill
缺少 required input 字段时返回 needs_input
bkl chat --once
POST /chat/messages
```

尚未实现：

```text
自然语言导入 Tool / Skill
配置模型的管理动作
Agent session 持久化
Agent turn trace 持久化
```

### 3.4 `core/`

共享基础类型和配置。

```text
core/schemas.py
  兼容旧 import path 的 schema re-export；canonical schema 已迁到 domain。

core/config.py
  bkl.yaml + .env 配置加载。

core/errors.py
  结构化错误基类。
```

主要类：

```text
Tool
Skill
SkillLimits
SkillModelConfig
ToolExecutionContext
ToolExecutionResult
RunResult
RunContext
TraceEvent
Artifact
EngineError
UsageSummary
ModelProfileConfig
EngineConfig
BklEngineError
```

Canonical schema 归属：

```text
domain/skill/
  Skill、SkillLimits、SkillModelConfig。

domain/tool/
  Tool、ToolExecutionContext、ToolExecutionResult、ToolPermissions。

domain/execution/
  RunResult、RunContext、Artifact、TraceEvent、EngineError、UsageSummary。

domain/model/
  ModelResponse、ModelUsage、ToolCallRequest。
```

### 3.5 `application/skill/`, `application/execution/`, and `infrastructure/package_loaders/`

Skill 包加载、注册、运行。

```text
infrastructure/package_loaders/skill_loader.py
  读取标准 Skill 包：SKILL.md + bkl.skill.json + schema。

infrastructure/repositories/skill_registry.py
  内存 Skill Registry adapter。

application/execution/skill_runtime.py
  Skill 执行主循环。

skills/prompt.py
  Prompt 渲染扩展点，目前占位。
```

主要类：

```text
SkillLoadError
InMemorySkillRegistry
SkillRuntime
SkillRuntimeError
```

`engine/app/skills/loader.py`、`engine/app/skills/registry.py`、`engine/app/skills/runtime.py` 是兼容导出。新代码应使用 `infrastructure/package_loaders`、`infrastructure/repositories`、`application/skill` 和 `application/execution`。

`SkillRuntime` 当前执行流程：

```text
读取 skill_id
校验 input_schema
读取 allowed_tools
构造 system/user messages
调用模型
如果模型请求 Tool，执行 Tool
把 Tool 结果回填给模型
模型返回 final_output
校验 output_schema
保存 RunResult / Trace
```

### 3.6 `application/tool/`, `infrastructure/package_loaders/`, and `infrastructure/tool_runners/`

Tool 包加载和执行。

```text
infrastructure/package_loaders/tool_loader.py
  读取 tool.yaml + input_schema + output_schema。

infrastructure/repositories/tool_registry.py
  内存 Tool Registry adapter。

application/tool/executor.py
  按 Tool 类型分发执行器，执行前做 policy check，具体 runner 由外层注入。

infrastructure/tool_runners/python_tool.py
  执行 Python Tool，使用 JSON stdin/stdout。

infrastructure/tool_runners/api_tool.py
  执行 API Tool。

infrastructure/package_loaders/openapi_importer.py
  从 OpenAPI operation 生成 API Tool。

tools/llm_tool.py
  LLM Tool 扩展点，目前占位。

tools/skill_tool.py
  Skill-as-Tool 扩展点，目前占位。
```

主要类：

```text
ToolLoadError
InMemoryToolRegistry
ToolExecutor
PythonToolRunner
ToolExecutionError
ApiToolRunner
ApiToolExecutionError
```

`engine/app/tools/loader.py`、`engine/app/tools/registry.py`、`engine/app/tools/executor.py`、`engine/app/tools/python_tool.py`、`engine/app/tools/api_tool.py`、`engine/app/tools/openapi_importer.py` 是兼容导出。新代码应使用 `application/tool` 和 `infrastructure/*`。

### 3.7 `models/`

模型路由和 provider。

```text
models/router.py
  ModelRouter、MockModelProvider、ModelResponse、ToolCallRequest。

models/providers/openai_compatible.py
  OpenAI-compatible chat/completions 协议。

models/providers/anthropic.py
  Anthropic-compatible messages 协议。

models/providers/openrouter.py
  OpenRouter 扩展点，目前占位。

models/providers/volcengine.py
  Volcengine 扩展点，目前占位。
```

主要类：

```text
ModelRouter
MockModelProvider
ModelResponse
ToolCallRequest
ModelUsage
OpenAICompatibleProvider
AnthropicProvider
```

当前模型选择逻辑：

```text
bkl.yaml 里 models.active_profile
  -> ModelRouter 选择对应 provider
  -> Skill 的 model.profile 可覆盖默认 profile
```

### 3.8 `infrastructure/persistence/`

本地存储。

```text
infrastructure/persistence/artifact_store.py
  本地 Artifact 存储。

infrastructure/persistence/catalog_store.py
  .bkl/catalog.json 持久化 Tool / Skill 注册表。

infrastructure/persistence/run_store.py
  内存 Run Store。

storage/database.py
  数据库扩展点，目前占位。

storage/models.py
  数据库模型扩展点，目前占位。
```

主要类：

```text
LocalArtifactStore
JsonCatalogStore
CatalogDocument
CatalogEntry
InMemoryRunStore
```

`engine/app/storage/*` 当前是兼容导出，不再放主实现。

### 3.9 `infrastructure/tracing/`

Trace 事件记录。

```text
infrastructure/tracing/trace_store.py
  内存 trace store。

trace/events.py
  事件类型扩展点，目前占位。
```

主要类：

```text
InMemoryTraceStore
```

`engine/app/trace/trace_store.py` 当前是兼容导出。

### 3.10 `interfaces/http/`

FastAPI 服务。

```text
interfaces/http/main.py
  当前所有 API route 都在这里。

interfaces/http/routes_tools.py
interfaces/http/routes_skills.py
interfaces/http/routes_runs.py
  后续拆分 route 的占位文件。
```

`engine/app/api/main.py` 当前是兼容入口，实际实现已经迁到 `interfaces/http/main.py`。

主要类：

```text
RegisterPathRequest
RunSkillRequest
```

主要函数：

```text
create_app(engine=None)
```

当前 API：

```text
GET  /health
POST /tools/register
GET  /tools
GET  /tools/{tool_id}
POST /skills/register
GET  /skills
GET  /skills/{skill_id}
POST /skills/{skill_id}/runs
GET  /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/trace
GET  /runs/{run_id}/artifacts
GET  /artifacts/{artifact_id}
```

### 3.11 `interfaces/cli/`

Typer CLI。

```text
interfaces/cli/main.py
  当前所有 CLI 命令都在这里。

interfaces/cli/tool_commands.py
interfaces/cli/skill_commands.py
interfaces/cli/run_commands.py
  后续拆分命令的占位文件。
```

`engine/app/cli/main.py` 当前是兼容入口，`pyproject.toml` 的 `bkl` console script 已指向 `interfaces/cli/main.py`。

当前 CLI：

```text
bkl --version
bkl init
bkl serve
bkl tool register
bkl tool list
bkl tool test
bkl skill register
bkl skill list
bkl skill run
bkl run list
bkl trace show
```

为什么 `main.py` 比较大：

```text
P0 先把所有命令集中在一个文件，便于快速验证。
后续稳定后再把 tool/skill/run/trace 命令拆到对应文件。
```

### 3.12 `policy/`

策略和安全控制扩展点。

```text
policy/policy_engine.py
  PolicyDecision、PolicyEngine 和 ToolExecutionPolicy。
```

当前已接入 `ToolExecutor`，默认策略为 allow，方便保持 v0.1 本地行为不变。产品部署和后续迭代可以注入更严格策略，实现 allow / ask / deny。

## 4. resources 目录

```text
engine/resources/
  inputs/
  skills/
  tools/
```

### 4.1 inputs

```text
engine/resources/inputs/talking-video-input.json
engine/resources/inputs/wangbudong-experiment-input.json
engine/resources/inputs/subtitle_input.json
```

用于 CLI/API 测试。

### 4.2 skills

```text
engine/resources/skills/talking-video/
  SKILL.md
  bkl.skill.json
  schemas/input.schema.json
  schemas/output.schema.json
  examples/examples.json

engine/resources/skills/wangbudong-experiment/
  SKILL.md
  bkl.skill.json
  schemas/input.schema.json
  schemas/output.schema.json
  examples/examples.json
```

### 4.3 tools

```text
engine/resources/tools/subtitle_generate_srt/
  tool.yaml
  input.schema.json
  output.schema.json
  main.py

engine/resources/tools/wangbudong_write_prompt_pack/
  tool.yaml
  input.schema.json
  output.schema.json
  main.py
```

## 5. tests 目录

测试按功能拆分：

```text
test_tool_loader.py
  Tool 包加载。

test_python_tool_runner.py
  Python Tool 执行、schema 校验、超时、artifact 目录。

test_skill_loader.py
  Skill 包加载。

test_skill_runtime.py
  Skill Runtime 主循环。

test_model_config.py
  bkl.yaml + .env 模型配置。

test_model_providers.py
  OpenAI-compatible / Anthropic-compatible provider 请求和解析。

test_openapi_importer.py
  OpenAPI operation -> Tool。

test_registries.py
  Tool / Skill Registry。

test_stores.py
  Artifact Store / Trace Store。

test_catalog_store.py
  .bkl/catalog.json 持久化。

test_api_cli.py
  CLI/API 端到端基础链路。

test_cli.py
  CLI init / serve / catalog register。
```

## 6. 当前已实现和占位总结

已实现：

```text
Core schema
config loader
Tool loader
Python Tool runner
API Tool runner
OpenAPI importer skeleton
Tool registry
Skill loader
Skill registry
Skill runtime
Model router
Mock provider
OpenAI-compatible provider
Anthropic provider
Run store
Trace store
Artifact store
Catalog store
CLI
FastAPI
DDD domain/application/infrastructure/interfaces package baseline
Application use cases for direct Skill run and Agent message turn
Tool policy check hook
tool_policy_checked / tool_failed trace events
talking-video example
wangbudong-experiment example
```

占位或待展开：

```text
CLI 命令拆分文件
API route 拆分文件
LLM Tool
Skill-as-Tool
Database persistence
SQLAlchemy models
Trace event type definitions
OpenRouter provider
Volcengine provider
Agent session persistence
Agent turn trace persistence
Agent confirmation resume
Durable run / trace / artifact stores
Memory / RAG ports
Multi-agent task orchestration
Desktop GUI
Server auth / Docker / queue
```

## 7. 推荐后续拆分

下一步如果继续整理代码结构，不建议只做机械拆文件。应先按业务智能体基座目标建立 DDD 边界和 ports，再逐步迁移现有模块。

短期建议按这个顺序拆：

```text
1. 定义 domain / application / infrastructure / interfaces 的目标目录。
2. 继续补齐 RunStore、TraceStore、ArtifactStore、PolicyEngine、SecretStore、AgentSessionStore、MemoryStore、KnowledgeRetriever 等 ports。
3. policy/policy_engine.py 继续承接 Tool 权限、网络权限、文件写权限、secret 权限和确认策略。
4. infrastructure/persistence/run_store.py 和 infrastructure/tracing/trace_store.py 补本地持久化实现，并新增 agent_session_store.py。
5. application/agent/state_machine.py 从过程式编排升级为显式可恢复 Agent state machine。
6. interfaces/http/main.py 拆成 interfaces/http/routes_tools.py、routes_skills.py、routes_runs.py、routes_chat.py。
7. interfaces/cli/main.py 拆成 interfaces/cli/tool_commands.py、skill_commands.py、run_commands.py、server_commands.py、chat_commands.py。
8. skills/prompt.py 承接 Skill prompt 渲染、schema 摘要、tool 摘要、memory context 摘要。
```

拆分时要保持 `SkillEngine` facade 稳定，避免 CLI、API、SDK、未来 UI 各自复制运行逻辑。

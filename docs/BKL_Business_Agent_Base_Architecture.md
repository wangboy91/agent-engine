# BKL Business Agent Base Architecture

Status: proposed target architecture for the next foundation phase. Current code implements a v0.1 vertical slice; this document defines the architecture it should evolve toward.

本文定义 BKL 的长期目标：先打造一个可复用的业务智能体基座，再在 UI 层包装成本地软件、云端 SaaS、私有部署和具体业务产品。

## 1. Positioning

BKL 的目标不是做通用代码编辑 Agent，也不是只做一个单一 Skill Runner。

BKL 应该是：

```text
Business Agent Base
  -> Direct Skill Execution
  -> Agent-Orchestrated Execution
  -> Future Multi-Agent Orchestration
  -> Local / Cloud / Private Product Shells
```

核心定位：

```text
Agent = 面向用户或业务场景的智能体入口和状态机
Skill = 可安装、可复用、可测试的业务能力包
Tool = 最小可执行动作和外部系统连接器
Engine = 运行时、权限、状态、追踪、记忆、产物和模型调用基座
UI/Product = 本地软件、SaaS、私有部署等产品包装
```

BKL 不应该把业务流程硬编码进 Core Engine。业务能力通过 Skill 安装或开发，业务系统通过 Tool / Connector 接入，产品形态通过 HTTP / SDK / CLI / Desktop 调用同一套 Engine。

## 2. Architecture Principles

必须长期坚持这些原则：

1. 只有一套 Core Engine。CLI、API、SDK、本地 GUI、云端 SaaS 都调用同一个运行时能力。
2. 业务流程沉淀在 Skill，不沉淀在 API route、CLI command 或 UI 页面里。
3. Agent 是受控状态机，不是自由行动的脚本执行器。
4. Tool 必须经过 schema 校验、权限校验、沙箱/环境控制、输出校验和 trace 记录。
5. 任何写入、外部发布、付费调用、业务系统变更都必须走确定性 action 和确认策略。
6. 多 Agent 不能直接共享可变内存或随意互相调用；必须通过任务、消息、事件、artifact 和 trace 这些受控通道协作。
7. RAG 和记忆系统是可插拔基础设施，不应该强行绑定到每个 Skill 或 Agent。
8. 所有执行都必须可追踪：用户消息 -> Agent turn -> action -> Skill run -> model turn -> tool call -> artifact。

## 3. Current Implementation Summary

当前代码已经具备的基础：

```text
engine/app/engine.py
  SkillEngine facade，统一 CLI/API/SDK 的运行入口。

engine/app/application/skill/ and engine/app/application/execution/
  Skill registry / runtime，支持 SKILL.md + bkl.skill.json 的执行契约。

engine/app/application/tool/
  Tool registry / executor，支持 python 和 api tool 的受控执行入口。

engine/app/infrastructure/package_loaders/
  Skill loader、Tool loader、OpenAPI importer。

engine/app/infrastructure/tool_runners/
  Python Tool runner、API Tool runner。

engine/app/infrastructure/repositories/
  InMemory Skill / Tool registry adapters。

engine/app/infrastructure/persistence/ and engine/app/infrastructure/tracing/
  Catalog、Run、Artifact、Trace 的本地/内存 adapter。

engine/app/models/
  ModelRouter，支持 mock、OpenAI-compatible、Anthropic-compatible。

engine/app/application/agent/ and engine/app/domain/agent/
  第一版 AgentLoop、SkillRouter、InputResolver、ActionRegistry skeleton，以及 Agent 领域数据结构。

engine/app/domain/
  AgentTurnState、ExecutionState 状态机锚点。

engine/app/application/
  RunSkillUseCase、HandleAgentMessageUseCase，以及 Run/Trace/Artifact ports。

engine/app/infrastructure/ and engine/app/interfaces/
  infrastructure 已承接 loader、runner、registry、persistence、tracing adapter；interfaces 包边界仍待承接 CLI / HTTP。

engine/app/policy/
  默认 PolicyEngine 已接入 ToolExecutor，支持 allow / ask / deny 决策。

engine/app/storage/ and engine/app/trace/
  旧 import path 兼容 adapter，不再承载主流程实现。

engine/app/interfaces/http/ and engine/app/interfaces/cli/
  FastAPI 和 Typer 入口。

engine/app/api/ and engine/app/cli/
  旧 import path / console entry 兼容 adapter，不再承载主流程实现。

engine/app/agents/, engine/app/skills/, engine/app/tools/
  旧 import path 兼容 adapter，不再承载主流程实现。
```

当前最大缺口：

```text
Agent session 和 Agent turn 还未持久化。
Run / Trace / Artifact 索引还未持久化。
ActionRegistry 还没有完整管理动作和确认流。
Agent Router / Input Resolver 仍是规则和正则驱动。
Tool 沙箱、文件权限、网络权限、secret 权限还未强制执行。
PolicyEngine 已有默认 hook，但还缺少生产级规则、确认流、secret scope 和 permission preview。
多 Agent 协作、任务队列、事件流、记忆系统仍未落地。
```

## 4. DDD Bounded Contexts

后续代码结构应按 DDD 组织，而不是继续让技术类型驱动所有目录。

### 4.1 Agent Context

负责智能体定义、会话、状态机、多 Agent 任务和 Agent 间通信。

核心概念：

```text
AgentDefinition
AgentSession
AgentTurn
AgentState
AgentTask
AgentMessage
AgentMailbox
AgentPlan
AgentAction
AgentPolicy
```

职责：

```text
根据用户输入或系统事件推进 Agent 状态机。
决定运行哪个 Skill 或哪个 Action。
管理缺失输入、确认请求、中断、恢复、失败和重试。
协调多 Agent 子任务，但不直接执行 Tool。
```

### 4.2 Skill Context

负责 Skill 包、版本、安装、校验、运行契约和 Skill-as-Tool。

核心概念：

```text
SkillPackage
SkillManifest
SkillVersion
SkillInputSchema
SkillOutputSchema
SkillRunPolicy
SkillInstallation
SkillDependency
```

职责：

```text
加载标准 SKILL.md。
加载 BKL runtime config。
校验 input/output schema。
管理 Skill 的 allowed tools、limits、model profile。
支持安装公开 Skill、禁用、升级、版本锁定和信任策略。
```

### 4.3 Tool Context

负责工具定义、执行、外部系统连接和 Tool 运行结果。

核心概念：

```text
ToolPackage
ToolManifest
ToolInvocation
ToolResult
ToolPermission
ToolRuntime
Connector
SecretRef
SandboxProfile
```

职责：

```text
加载 tool.yaml。
执行 Python/API/LLM/Skill/System Tool。
在执行前做 policy check。
在执行后做 output schema 校验和 artifact 注册。
对接业务系统、OpenAPI、内部 API、文件系统和外部 SaaS。
```

### 4.4 Execution Context

负责通用执行状态机、调用链、重试、中断、并发和任务队列。

核心概念：

```text
Run
RunStep
ExecutionState
ExecutionPlan
ModelTurn
ToolCall
ActionCall
Cancellation
RetryPolicy
TimeoutPolicy
```

职责：

```text
承接 Direct Skill Execution。
承接 Agent-Orchestrated Execution。
记录每个执行 step。
支持同步运行、异步运行、恢复和取消。
```

### 4.5 Policy Context

负责权限、确认、成本、安全和合规策略。

核心概念：

```text
PolicyRule
PolicyDecision
PermissionRequest
ConfirmationRequest
RiskLevel
Budget
WorkspaceScope
NetworkScope
FilesystemScope
SecretScope
```

职责：

```text
判断 action 或 tool 是否 allow / ask / deny。
管理用户确认请求。
控制网络、文件、secret、外部发布、付费动作。
输出可审计的 policy decision。
```

### 4.6 Memory and Knowledge Context

负责短期记忆、长期记忆、业务知识和 RAG。

核心概念：

```text
MemoryScope
MemoryRecord
KnowledgeBase
KnowledgeQuery
KnowledgeResult
ContextSource
ContextSnapshot
```

职责：

```text
为 Agent 和 Skill 提供可插拔记忆能力。
支持 session memory、project memory、user memory、business knowledge。
按 policy 和 agent config 决定是否检索 RAG。
把检索结果作为受控 ContextSource 注入模型上下文。
```

### 4.7 Observability Context

负责 trace、event、artifact、usage、cost 和审计。

核心概念：

```text
TraceEvent
TraceSpan
Artifact
UsageSummary
AuditEvent
EventStream
CorrelationId
```

职责：

```text
记录完整调用链。
支持 UI trace viewer。
支持成本统计和业务审计。
支持 server-sent events 或 websocket 事件流。
```

### 4.8 Product Runtime Context

负责本地软件、云端 SaaS、私有部署的运行环境差异。

核心概念：

```text
Workspace
Project
Tenant
User
CredentialStore
DeploymentMode
RuntimeConfig
```

职责：

```text
隔离本地/云端/私有部署的工作区、租户、认证、凭据和持久化。
保证产品层差异不污染核心业务运行时。
```

## 5. Target Code Layout

当前可以继续保留 `app` 单包，但内部应该逐步向 DDD 分层迁移。

目标结构建议：

```text
engine/app/
  domain/
    agent/
      entities.py
      value_objects.py
      services.py
      events.py
    skill/
    tool/
    execution/
    policy/
    memory/
    observability/

  application/
    agent/
      commands.py
      handlers.py
      state_machine.py
      orchestrator.py
    skill/
      run_skill.py
      install_skill.py
      validate_skill.py
    tool/
      invoke_tool.py
      install_tool.py
      validate_tool.py
    execution/
      run_service.py
      scheduler.py
    memory/
      context_builder.py

  infrastructure/
    persistence/
      sqlite/
      postgres/
      local_json/
    models/
      providers/
    tools/
      python_runner.py
      api_runner.py
      sandbox.py
    memory/
      vector_store.py
      rag_retriever.py
    artifacts/
      local_store.py
      object_store.py
    event_bus/

  interfaces/
    cli/
    http/
    sdk/
```

迁移规则：

```text
domain 不依赖 FastAPI、Typer、httpx、SQLAlchemy、文件系统。
application 编排 domain，并依赖抽象 ports。
infrastructure 实现 ports，例如数据库、模型 provider、tool runner、artifact store。
interfaces 只负责输入输出适配，不写业务流程。
```

短期不用一次性重构到这个结构。先建立 ports 和 state machine，再把现有模块逐步迁入。

## 6. Execution State Machines

### 6.1 Direct Skill Run State Machine

显式调用 `skill_id + input` 时使用这条状态机。

```text
Created
  -> InputValidating
  -> ContextPreparing
  -> ModelTurnRunning
  -> ToolCallRequested
  -> ToolPolicyChecking
  -> WaitingConfirmation
  -> ToolExecuting
  -> ToolResultObserving
  -> OutputValidating
  -> ArtifactRegistering
  -> Succeeded
```

失败和中断路径：

```text
Any state
  -> Failed
  -> Cancelled
  -> TimedOut
  -> RequiresInput
  -> RequiresConfirmation
```

这条状态机必须输出稳定的 RunStep 和 TraceEvent，不能只靠内存里的 for loop。

### 6.2 Agent Turn State Machine

用户通过自然语言或 UI 场景调用 Agent 时使用。

```text
MessageReceived
  -> SessionLoaded
  -> IntentClassified
  -> RouteResolved
  -> InputResolved
  -> PlanBuilt
  -> PolicyChecked
  -> WaitingUserInput
  -> WaitingConfirmation
  -> ActionsDispatching
  -> ResultsObserved
  -> ResponseComposed
  -> TurnPersisted
  -> Completed
```

AgentTurn 可以产生多个 ActionCall，每个 ActionCall 可以产生一个 SkillRun 或 Tool/Management action。

### 6.3 Multi-Agent State Machine

多 Agent 协作不能做成“Agent 互相自由聊天”。应该是任务驱动：

```text
CoordinatorAgent
  -> creates AgentTask
  -> dispatches to WorkerAgent
  -> WorkerAgent runs its own AgentTurn / SkillRun
  -> WorkerAgent returns AgentTaskResult
  -> CoordinatorAgent merges result
```

Agent 之间通信通过：

```text
AgentTask
AgentMessage
Mailbox
SharedArtifact
TraceReference
KnowledgeRecord
```

禁止：

```text
共享可变 Python 对象作为记忆。
绕过 Policy 直接调用其他 Agent 的 Tool。
把所有 Agent 的完整上下文无控制地互相复制。
```

## 7. Tool Execution Contract

所有 Tool 调用必须走同一套执行管线：

```text
1. Resolve tool by id and version.
2. Validate arguments against input_schema.
3. Resolve caller: agent_id, skill_id, run_id, user_id, workspace_id.
4. Evaluate policy: allow / ask / deny.
5. Resolve secrets through SecretStore; never expose raw secret to model or trace.
6. Prepare runtime: sandbox, cwd, env, artifact dir, network scope, filesystem scope.
7. Execute tool.
8. Validate output against output_schema.
9. Register artifacts through ArtifactStore.
10. Persist trace span and usage.
11. Return bounded observation to model.
```

Python Tool 默认不应该继承完整 `os.environ`。它只能拿到白名单环境变量和通过 `SecretRef` 授权的凭据。

API Tool 默认不应该任意访问公网。它必须声明 base_url、method、auth、network scope，并由 PolicyEngine 决定是否允许。

## 8. Memory and RAG Decision

问题：记忆系统是否要挂 RAG？

结论：需要预留 RAG，但不要把 RAG 做成所有 Agent 和 Skill 的强依赖。

推荐分层：

```text
Session Memory
  当前会话短期上下文和用户澄清。

Project Memory
  当前项目或工作区的长期偏好、已安装 Skill、历史运行摘要。

Business Knowledge
  企业文档、产品资料、SOP、素材库、业务知识库。适合 RAG。

Operational Memory
  run history、trace summary、artifact metadata，用于审计和复用。
```

RAG 应该作为 `KnowledgeRetriever` port 或 Tool/ContextSource 接入：

```text
Agent / Skill config
  -> declares memory policy
  -> ContextBuilder asks MemoryService / KnowledgeRetriever
  -> retrieved snippets become ContextSource
  -> Model receives bounded, cited context
```

这样可以支持：

```text
不需要知识库的轻量 Skill 直接运行。
业务知识强相关的 Agent 使用 RAG。
私有部署替换向量库和 embedding provider。
云端 SaaS 按 tenant 隔离知识库。
```

## 9. Trace and Call Chain

调用链需要从第一版就设计成树形或 span 结构。

推荐 ID 关系：

```text
session_id
  turn_id
    action_id
      run_id
        model_turn_id
          tool_call_id
            artifact_id
```

所有事件都应该包含：

```text
trace_id
parent_id
span_id
session_id
turn_id
run_id
skill_id
agent_id
tool_id
workspace_id
timestamp
event_type
status
safe_data
```

Trace 不是只给开发者看的日志，它是未来 UI 调用链、失败诊断、成本解释、业务审计和多 Agent 调试的基础。

## 10. Public Skill Installation

未来支持安装公开 Skill 时，需要把安装过程当成受控业务流程。

安装流程：

```text
Discover
  -> Download / Clone
  -> Verify manifest
  -> Validate SKILL.md and bkl.skill.json
  -> Validate schemas
  -> Resolve Tool dependencies
  -> Show permissions
  -> Require confirmation
  -> Install to catalog
  -> Run smoke validation
  -> Enable
```

必须支持：

```text
version pinning
source URL
checksum or signature
permission preview
dependency lock
enable / disable
upgrade / rollback
```

不要让公开 Skill 自动获得文件、网络、secret 或业务系统写权限。

## 11. UI and Product Forms

UI 层应该是 Engine 的客户，不是第二套 Engine。

本地软件：

```text
Desktop shell
  -> starts local bkl serve
  -> local UI calls HTTP / SDK
  -> local filesystem and user-owned keys
```

云端 SaaS：

```text
Web app
  -> calls hosted BKL server
  -> tenant/user auth
  -> managed model keys or user keys
  -> durable DB and object storage
```

私有部署：

```text
Customer server
  -> deployed BKL server
  -> customer credential store
  -> internal connectors and private knowledge base
```

三种形态共享：

```text
Skill package format
Tool package format
RunResult contract
Trace contract
Artifact contract
Agent session contract
Policy contract
```

## 12. Architecture Priorities

下一阶段优先级：

1. 建立 DDD 目录和 ports，不急着完整迁移全部代码。
2. 把 PolicyEngine 接入 ToolExecutor。
3. 把 Run/Trace/Artifact/AgentSession 持久化抽象出来。
4. 把 AgentLoop 改造成显式状态机。
5. 建立 Tool execution validation pipeline。
6. 建立 trace span 调用链。
7. 增加 Memory / KnowledgeRetriever port，但先不强制实现完整 RAG。
8. 再扩展 multi-agent task / mailbox / event bus。

## 13. Non-Goals for the Foundation Phase

短期不要做：

```text
自由代码编辑 Agent
无限制 shell 执行
复杂可视化工作流编排器
无边界多 Agent 群聊
默认联网抓取
默认 RAG 化所有请求
直接接生产业务系统写操作
```

这些能力可以以后做，但必须建立在 state machine、policy、trace、sandbox 和 persistence 之后。

# BKL Business Agent Base Roadmap

Status: proposed iteration roadmap. This document complements `BKL_Development_Checklist.md`; it focuses on architecture hardening before expanding product features.

## 1. Goal

目标是把当前 v0.1 Skill Engine 演进成业务智能体基座：

```text
Direct Skill Execution
  用户或系统明确传 skill_id 和 input。

Agent-Orchestrated Execution
  用户通过自然语言、scene_id 或 UI 操作触发 Agent 状态机。

Multi-Agent Execution
  一个 Coordinator Agent 能以受控任务方式调度多个 Worker Agent。

Product Shells
  本地软件、云端 SaaS、私有部署只做 UI、认证、租户、支付、部署和业务包装。
```

## 2. Current Baseline

当前已经完成：

```text
SkillEngine facade
Skill loader / registry / runtime under DDD canonical paths
Tool loader / registry / executor under DDD canonical paths
Python Tool and API Tool
ModelRouter with mock / OpenAI-compatible / Anthropic-compatible
Catalog persistence
CLI and FastAPI entrypoints
First AgentLoop slice under application/agent
Scene Mapping
Rule-based SkillRouter
InputResolver
Run / Trace / Artifact basic stores
```

当前不应继续只堆功能。下一阶段先补架构硬度。

## 3. Phase A: DDD Architecture Baseline

Goal: 建立可演进代码结构，不一次性重写业务逻辑。

Tasks:

- [x] 新增 `domain/`、`application/`、`infrastructure/`、`interfaces/` 目标目录。
- [x] 定义第一批 ports：RunStore、TraceStore、ArtifactStore。
- [ ] 继续定义核心 ports：CatalogStore、PolicyEngine、SecretStore、MemoryStore、KnowledgeRetriever、EventBus。
- [x] 保持现有 `SkillEngine` facade 不破坏 CLI/API/SDK。
- [x] 将 Agent、Skill runtime、Tool executor、package loader 的主实现迁到 DDD 分层。
- [x] 保留旧 import path 作为兼容 adapter，不再承载主流程实现。
- [x] 将 registry、persistence、tracing adapter 迁到 infrastructure。
- [ ] 后续新代码优先写到 DDD 分层，逐步迁移 model provider/interface adapter。
- [ ] 为所有 ports 写 Protocol / ABC 和测试用内存实现。
- [ ] 更新贡献规则：interfaces 不写业务流程，infrastructure 不反向依赖 application。

Acceptance:

- [x] 当前测试继续通过。
- [ ] 新增端口有单元测试。
- [x] `SkillEngine` 仍是对外稳定入口。
- [x] 文档里当前结构和目标结构明确区分。

## 4. Phase B: Policy and Tool Execution Pipeline

Goal: 所有工具执行都经过权限、确认、secret、sandbox 和 schema 管线。

Tasks:

- [x] 实现默认 `PolicyEngine.evaluate_tool_execution(...)`，返回 allow / ask / deny。
- [x] 定义 `PolicyDecision`。
- [ ] 定义 `PermissionRequest`、`ConfirmationRequest`。
- [x] ToolExecutor 调用 Python/API Tool 前必须先调用 PolicyEngine。
- [ ] Python Tool 默认不继承完整环境变量，只注入白名单 env。
- [ ] API Tool 校验 base_url、network scope 和 auth secret ref。
- [ ] 引入 `SecretStore`，Tool 只能通过 `SecretRef` 请求凭据。
- [ ] 注册 tool 时生成 permission preview。
- [x] trace 记录 tool policy check 和 tool failure。
- [ ] trace 记录完整 policy decision，但不记录 secret 明文。

Acceptance:

- [ ] 未授权 network tool 被拒绝。
- [ ] 未授权 filesystem write 被拒绝。
- [ ] 缺少 secret 时返回结构化错误。
- [ ] 需要确认的动作返回 `requires_confirmation`，不会直接执行。
- [ ] 所有 Tool 调用 trace 中包含 policy decision。

## 5. Phase C: Durable Execution State

Goal: Run、Trace、Artifact 和 AgentSession 不再只存在内存里。

Tasks:

- [ ] 抽象 `RunStore`，新增 SQLite 本地实现。
- [ ] 抽象 `TraceStore`，新增 span/tree 结构。
- [ ] 抽象 `ArtifactStore`，保存 artifact metadata，文件仍可先落本地。
- [ ] 抽象 `AgentSessionStore`，保存 session、turn、messages、action results。
- [ ] FastAPI 查询 run/trace/artifact 时从持久化 store 读取。
- [ ] CLI `run list`、`trace show` 能看到历史运行。
- [ ] 每个 run 支持 status transition 记录。

Acceptance:

- [ ] 重启 `bkl serve` 后仍能查询 run 和 trace。
- [ ] Artifact 文件和 metadata 可以重新关联。
- [ ] Agent turn 可以关联到 run_id。
- [ ] trace 支持 parent-child 调用链。

## 6. Phase D: Agent State Machine

Goal: AgentLoop 从过程式调用升级为显式状态机。

Tasks:

- [ ] 定义 `AgentTurnState` 和状态迁移表。
- [ ] 将 route、resolve input、confirm、dispatch action、observe result、respond 拆成状态节点。
- [ ] `confirm` 参数真正接入 pending confirmation。
- [ ] ActionRegistry 扩展为 typed command handlers。
- [ ] 支持 actions：run_skill、list_skills、list_tools、register_skill、register_tool、validate_skill、validate_tool、configure_model_profile、explain_trace。
- [ ] 所有写入类 action 必须经过 ConfirmationPolicy。
- [ ] Agent turn trace 持久化。

Acceptance:

- [ ] 缺少 required 字段时停在 `WaitingUserInput`。
- [ ] 写 catalog 前停在 `WaitingConfirmation`。
- [ ] 用户确认后从同一个 pending action 恢复执行。
- [ ] 每个 action 有输入模型、输出模型、风险级别和 trace。

## 7. Phase E: Memory and Knowledge Ports

Goal: 支持记忆和 RAG，但不让 RAG 污染核心运行时。

Tasks:

- [ ] 定义 `MemoryStore`、`KnowledgeRetriever`、`ContextBuilder`。
- [ ] 支持 session memory：用户澄清、当前 turn 摘要、最近 run summary。
- [ ] 支持 project memory：已安装 Skill、常用业务偏好、历史运行摘要。
- [ ] 定义 RAG 接口，不绑定具体向量库。
- [ ] Skill/Agent config 可以声明 memory policy。
- [ ] ContextBuilder 根据 policy 拉取 memory 和 knowledge snippets。
- [ ] trace 记录 memory query，但不记录敏感原文。

Acceptance:

- [ ] 不使用 RAG 的 Skill 不受影响。
- [ ] Agent 可以按配置检索业务知识。
- [ ] 同一接口可替换本地向量库、云端向量库或企业知识库。

## 8. Phase F: Public Skill Installation

Goal: 公开 Skill 能安装，但默认安全、可审计、可回滚。

Tasks:

- [ ] 定义 Skill source：local path、git URL、registry URL。
- [ ] 安装前校验 package、schema、allowed tools、permissions。
- [ ] 生成 permission preview 和 dependency preview。
- [ ] 需要用户确认后写入 catalog。
- [ ] 支持 version pinning、disable、upgrade、rollback。
- [ ] 支持 Skill trust level。

Acceptance:

- [ ] 未确认不能安装公开 Skill。
- [ ] Skill 安装后可通过同一 run contract 执行。
- [ ] 权限变更在升级前必须再次确认。

## 9. Phase G: Multi-Agent Orchestration

Goal: 支持多 Agent，但必须通过任务和消息机制，不做无边界群聊。

Tasks:

- [ ] 定义 `AgentTask`、`AgentTaskResult`、`AgentMailbox`。
- [ ] Coordinator Agent 只能创建任务、等待结果、合并结果。
- [ ] Worker Agent 拥有独立 session/turn/run。
- [ ] 支持 parent-child trace。
- [ ] 支持 task timeout、cancel、retry。
- [ ] Agent 间共享 artifact reference，不共享完整上下文。
- [ ] PolicyEngine 控制哪些 Agent 可以调度哪些 Agent。

Acceptance:

- [ ] 一个 Agent 可以调度两个 Worker Agent 并合并结果。
- [ ] 每个 Worker 的调用链可单独追踪。
- [ ] Worker 失败不会污染 Coordinator 状态。
- [ ] 禁止未授权 Agent 调度。

## 10. Phase H: Server and Product Shells

Goal: 本地软件、云端 SaaS、私有部署都复用同一 Engine。

Tasks:

- [ ] API key auth middleware。
- [ ] request id、structured logs、event stream。
- [ ] async run queue skeleton。
- [ ] workspace root 和 tenant/user scope。
- [ ] Dockerfile。
- [ ] SDK contract 和 OpenAPI schema 稳定化。
- [ ] 本地 GUI 只调用 local HTTP，不嵌入第二套 runtime。
- [ ] 云端 SaaS 增加 tenant isolation、credential store、object storage。

Acceptance:

- [ ] 本地和云端执行同一个 Skill 得到同一类 RunResult。
- [ ] UI 可以显示 session、turn、run、trace、artifact。
- [ ] SaaS 模式下不同 tenant 的 catalog、memory、artifact 隔离。

## 11. Suggested Immediate Order

近期最稳的顺序：

1. DDD ports and target folders.
2. PolicyEngine + ToolExecutor integration.
3. Durable Run/Trace/Artifact/AgentSession.
4. Agent state machine and confirmation resume.
5. Memory/RAG ports.
6. Public Skill installation.
7. Multi-Agent task orchestration.
8. Product shell hardening.

原因：

```text
没有 Policy，多 Agent 会放大风险。
没有持久化，UI 和云端 SaaS 无法解释运行过程。
没有状态机，确认、输入补齐、多 Agent 调度都会变成临时 if/else。
没有 trace span，多 Agent 调试会很快失控。
没有 memory port，RAG 会被硬塞进 SkillRuntime。
```

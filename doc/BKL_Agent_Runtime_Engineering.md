# BKL Agent Runtime Engineering Plan

Status: first implementation slice landed on 2026-06-10; management actions and session persistence remain pending.

本文定义 BKL 下一阶段如何工程化实现 Agent 能力。核心结论是：BKL 需要同时保留“显式指定 Skill 执行”和“自然语言/场景驱动 Agent 执行”两种能力，但它们必须复用同一个 `SkillEngine`，不能做两套运行时。

当前已实现的第一版闭环：

```text
bkl_engine/domain/agent/
  Agent schemas and SceneMapping

bkl_engine/application/agent/
  SkillRouter
  InputResolver
  ActionRegistry skeleton
  AgentLoop

bkl chat --once
POST /chat/messages
```

当前仍未实现：

```text
自然语言导入 Tool / Skill
配置模型等写入类管理动作
Agent session 持久化
Agent turn trace 持久化
```

## 1. Two Execution Modes

BKL 对外应该提供两条入口。

### 1.1 Direct Skill Execution

调用方明确知道要运行哪个 Skill。

```text
caller
  -> skill_id + input JSON
  -> SkillEngine.run_skill(...)
  -> SkillRuntime tool-calling loop
  -> RunResult / Trace / Artifacts
```

适用场景：

- 后端服务调用
- CLI 脚本
- 自动化任务
- 产品页面已经绑定固定 Skill
- 测试和调试

入口示例：

```bash
bkl skill run talking-video input.json --output json
```

```http
POST /skills/talking-video/runs
```

这个模式要求稳定、可预测、易测试。生产 API 默认应该优先使用它。

### 1.2 Agent-Orchestrated Execution

调用方只提供自然语言请求，或者只提供业务场景。Agent 负责选择动作、补齐参数、执行 Skill、返回结果。

```text
user message / scene_id
  -> AgentLoop
  -> SkillRouter / SceneMapping
  -> InputResolver
  -> ConfirmationPolicy
  -> SkillEngine.run_skill(...)
  -> Agent response
```

适用场景：

- `bkl chat`
- 本地 GUI 工作台
- 用户不知道该选哪个 Skill
- 用户通过自然语言导入 Tool / Skill
- 用户通过自然语言运行已注册 Skill

入口示例：

```bash
bkl chat
bkl chat --once "帮我做一个王不懂小实验，主题是鸡蛋为什么会浮起来"
```

```http
POST /chat/messages
```

Agent 模式不应该绕过 Core Engine。它只是 Core Engine 外面的一层编排。

## 2. Layering

目标分层：

```text
CLI / API / Desktop / SaaS Product
  -> Agent Runtime
       AgentLoop
       SkillRouter
       SceneMapping
       InputResolver
       ActionRegistry
       ConfirmationPolicy
       SessionStore
  -> SkillEngine
       SkillRuntime
       ToolExecutor
       ModelRouter
       SkillRegistry
       ToolRegistry
       TraceStore
       ArtifactStore
```

规则：

1. `SkillEngine` 继续负责注册、加载、运行 Skill。
2. `SkillRuntime` 继续负责单个 Skill 内部的 tool-calling loop。
3. `AgentRuntime` 只负责“用户意图 -> 动作计划 -> 调用 SkillEngine”。
4. Agent 不能直接随意执行 shell、改文件或绕过 Tool 权限。
5. 所有写操作必须进入确定性的 action，并经过确认和校验。

## 3. What Makes It an Agent

当前 `SkillRuntime` 已经有内部 loop，但它只解决“某个 Skill 怎么跑完”。

Agent 级 loop 需要解决：

```text
用户到底想做什么？
应该运行哪个 Skill？
需要哪些输入字段？
用户的话里已经包含了哪些字段？
哪些字段缺失，需要追问？
是否涉及写入、导入、配置修改，需要确认？
运行结果是否足够，还是需要继续下一步？
```

因此 BKL Agent 是一个受控状态机，而不是自由行动的代码编辑 Agent。

## 4. Agent Loop

第一版 Agent loop 应该保持简单、可测试、可中断。

```text
1. Observe
   读取用户消息、session 状态、catalog、scene mapping。

2. Classify
   判断是运行 Skill、管理 catalog、配置模型、解释 trace，还是普通问答。

3. Route
   如果是运行 Skill：
   - explicit skill_id 优先
   - scene_id 次之
   - 自然语言 router 最后

4. Resolve Input
   根据目标 Skill 的 input.schema.json 抽取输入。
   缺少 required 字段时追问用户。

5. Confirm
   对导入、配置、写文件、外部发布、可能产生费用的动作要求确认。

6. Act
   通过确定性的 action 调用 SkillEngine 或 catalog/model config API。

7. Observe Result
   读取 RunResult、Trace、Artifacts。

8. Respond
   给用户返回结构化摘要、产物路径、下一步可选动作。
```

第一版 loop 需要硬限制：

```text
max_agent_steps: 6
max_router_candidates: 5
require_confirmation_for_writes: true
allow_direct_tool_call: false
```

## 5. Routing Strategy

路由优先级应该是确定性优先，模型判断兜底。

### 5.1 Explicit Skill ID

用户或调用方已经指定 `skill_id`：

```json
{
  "skill_id": "wangbudong-experiment",
  "input": {
    "topic": "鸡蛋为什么会浮起来"
  }
}
```

Agent 不需要猜测，只需要校验输入并执行。

### 5.2 Scene Mapping

产品页面或工作台提供 `scene_id`：

```yaml
scenes:
  wangbudong_experiment_writer:
    skill_id: wangbudong-experiment
    title: 王不懂小实验内容生成
    defaults:
      platform: xiaohongshu
```

请求链路：

```text
scene_id
  -> skill_id
  -> input_schema
  -> schema-driven form / InputResolver
  -> run skill
```

这适合 GUI 和 SaaS 产品，不需要每次让模型猜 Skill。

### 5.3 Natural Language Skill Router

当没有 `skill_id` 和 `scene_id` 时，Router 从 catalog 中读取候选 Skill 的轻量元数据：

```text
skill_id
name
description
input_schema required fields
output_schema summary
examples summary
```

Router 输出：

```json
{
  "intent": "run_skill",
  "skill_id": "wangbudong-experiment",
  "confidence": 0.91,
  "input_draft": {
    "topic": "鸡蛋为什么会浮起来"
  },
  "missing_fields": [],
  "reason": "用户要求生成王不懂小实验内容，和该 Skill 描述高度匹配。"
}
```

建议阈值：

```text
confidence >= 0.85
  可以自动选择 Skill，但仍要校验 input_schema。

0.60 <= confidence < 0.85
  需要让用户确认候选 Skill。

confidence < 0.60
  不运行，返回候选列表或追问场景。
```

## 6. Input Resolver

Input Resolver 的职责是把自然语言转成目标 Skill 的 JSON 输入。

输入：

```text
user message
target skill input_schema
scene defaults
session memory
```

输出：

```json
{
  "input": {
    "topic": "鸡蛋为什么会浮起来",
    "platform": "xiaohongshu"
  },
  "missing_fields": [
    "duration_seconds"
  ],
  "assumptions": [
    "platform 使用 scene 默认值 xiaohongshu"
  ]
}
```

规则：

1. 只允许填入用户明确说过、schema 默认值、scene 默认值、产品配置默认值。
2. 不能偷偷编造 required 字段。
3. 缺少 required 字段时必须追问。
4. 最终执行前必须通过 `jsonschema` 校验。
5. 追问的问题应该来自 schema 的字段名、description、enum、minimum、maximum。

## 7. Action Registry

Agent 不能自由调用任意代码。第一版只允许这些 action：

```text
run_skill
list_skills
list_tools
register_skill
register_tool
validate_skill
validate_tool
configure_model_profile
test_model_profile
explain_run_trace
```

每个 action 都必须有自己的 Pydantic 输入模型、权限策略、确认策略和 trace 事件。

示例：

```python
class RunSkillActionInput(BaseModel):
    skill_id: str
    input: dict[str, Any]
```

```python
class RegisterSkillActionInput(BaseModel):
    path: str
    persist: bool = True
```

`register_skill`、`register_tool`、`configure_model_profile` 必须要求用户确认。

## 8. Confirmation Policy

确认策略不能交给模型自由判断，应该由代码决定。

必须确认：

```text
写入 catalog
修改 bkl.yaml
导入 Tool / Skill
执行外部发布类 Tool
执行会产生费用的 API Tool
覆盖已有文件
删除或禁用对象
```

可以不确认：

```text
列出 catalog
读取 Skill schema
解释 trace
运行明确指定且无高风险 Tool 的 Skill
```

CLI 里可以提供：

```bash
--yes
```

但 `--yes` 只应该跳过低风险写操作确认，不能跳过删除、覆盖、外部发布、付费动作的确认。

## 9. Session and Trace

Agent session 需要独立于 Skill run，但要能关联 Skill run。

建议数据模型：

```text
AgentSession
  session_id
  created_at
  updated_at
  messages[]
  turns[]

AgentTurn
  turn_id
  user_message
  route_decision
  action_plan
  action_results[]
  run_ids[]
  response
```

第一版本地存储：

```text
.bkl/
  sessions/
    <session_id>.json
```

后续服务端部署可以替换为数据库。

Trace 关系：

```text
Agent turn trace
  -> action trace
  -> Skill run trace
  -> Tool execution trace
```

这样用户在 GUI 里能看到“为什么选择了这个 Skill，以及 Skill 内部调用了哪些 Tool”。

## 10. CLI and API Shape

### 10.1 CLI

```bash
bkl chat
bkl chat --once "帮我做一个王不懂小实验，主题是鸡蛋为什么会浮起来"
bkl chat --scene wangbudong_experiment_writer
bkl chat --session sess_123
```

CLI 行为：

```text
交互模式：持续读取用户输入。
--once：执行一轮后退出，方便脚本测试。
--scene：跳过自然语言 Skill Router，直接用 scene mapping。
--session：恢复已有 session。
```

### 10.2 API

```http
POST /chat/messages
```

请求：

```json
{
  "session_id": null,
  "message": "帮我做一个王不懂小实验，主题是鸡蛋为什么会浮起来",
  "scene_id": null,
  "confirm": false
}
```

响应：

```json
{
  "session_id": "sess_xxx",
  "turn_id": "turn_xxx",
  "status": "completed",
  "message": "已生成王不懂小实验内容。",
  "requires_confirmation": false,
  "confirmation": null,
  "run_ids": [
    "run_xxx"
  ],
  "artifacts": []
}
```

需要确认时：

```json
{
  "status": "requires_confirmation",
  "message": "将导入 Skill resources/skills/foo 并写入 .bkl/catalog.json，是否继续？",
  "requires_confirmation": true,
  "confirmation": {
    "action_id": "act_xxx",
    "risk": "writes_catalog"
  }
}
```

## 11. Current Source Layout

当前 DDD canonical layout：

```text
bkl_engine/domain/agent/
  __init__.py
  schemas.py
  scene_mapping.py
  states.py

bkl_engine/application/agent/
  __init__.py
  commands.py
  handle_message.py
  state_machine.py
  router.py
  input_resolver.py
  actions.py
  confirmation.py

bkl_engine/agents/
  legacy compatibility adapters only
```

后续需要新增：

```text
bkl_engine/application/agent/
  session_store.py
```

历史旧布局如下，已迁移为兼容 adapter：

```text
bkl_engine/agents/
  loop.py
  router.py
  resolver.py
  actions.py
  scene_mapping.py
  confirmation.py
```

职责：

```text
domain/agent/schemas.py
  AgentMessage、AgentSession、AgentTurn、RouteDecision、ActionPlan。

application/agent/state_machine.py
  AgentLoop 主状态机。

application/agent/router.py
  SkillRouter：自然语言请求 -> 候选 Skill / action。

application/agent/input_resolver.py
  InputResolver：自然语言 + schema -> input JSON / missing fields。

application/agent/actions.py
  确定性 action registry，所有写操作走这里。

domain/agent/scene_mapping.py
  scene_id -> skill_id + defaults。

application/agent/session_store.py
  session 持久化接口和本地 JSON 实现。

application/agent/confirmation.py
  代码级确认策略。
```

CLI/API 扩展：

```text
bkl_engine/interfaces/cli/chat_commands.py
bkl_engine/interfaces/http/routes_chat.py
```

## 12. Implementation Order

建议按以下顺序实现，避免一上来做成不可控的聊天机器人。

### Phase 1: Agent Schemas and Scene Mapping

- 新增 `bkl_engine/domain/agent/schemas.py`
- 新增 `SceneMapping`
- 支持从 `bkl.yaml` 或独立 `scenes.yaml` 读取 `scene_id -> skill_id`
- 测试 scene routing

### Phase 2: Skill Router

- 从 catalog 读取 Skill 元数据
- 使用 mock provider 测试自然语言 routing
- 输出 `RouteDecision`
- 实现 confidence threshold
- 低置信度返回候选项，不执行

### Phase 3: Input Resolver

- 根据 `input.schema.json` 抽取字段
- 缺字段时返回追问
- 支持 schema default 和 scene default
- 最终通过 jsonschema 校验

### Phase 4: AgentLoop and `bkl chat --once`

- 串联 router、resolver、confirmation、action
- 第一版只支持 `run_skill`、`list_skills`、`list_tools`
- 支持 mock model 下稳定测试

### Phase 5: Management Actions

- 支持 `register_skill`
- 支持 `register_tool`
- 支持 `validate_skill`
- 支持 `validate_tool`
- 所有写操作必须确认

### Phase 6: Chat API and Session Persistence

- 新增 `POST /chat/messages`
- 新增本地 `.bkl/sessions/*.json`
- Agent turn 关联 Skill run trace

## 13. Testing Strategy

所有 Agent 功能必须默认使用 mock model 测试。

必须覆盖：

```text
明确 skill_id 时不调用 router
scene_id 能映射到 skill_id
自然语言能路由到正确 Skill
低置信度会要求确认或追问
缺少 required input field 会追问
input_schema 校验失败不会运行 Skill
写 catalog 前必须确认
Agent action 会记录 trace
AgentLoop 达到 max_agent_steps 会停止
```

真实模型只做 smoke test，不进入默认测试链路，也不能打印密钥。

## 14. Non-goals for v0.1

第一版不做：

```text
多 Agent 协作
复杂规划器
长期记忆
自动网页操作
任意 shell 执行
自动创建大规模项目代码
可视化 Workflow 编排器
```

这些能力以后可以加，但不能影响 v0.1 的可控性和可测试性。

## 15. Summary

BKL 应该是：

```text
Direct mode:
  explicit skill_id -> SkillEngine.run_skill

Agent mode:
  natural language / scene_id -> AgentRuntime -> SkillEngine.run_skill
```

Agent 是入口层和编排层，不是新的业务运行时。所有业务能力仍然沉淀在 Skill，所有可执行动作仍然沉淀在 Tool，所有运行仍然经过 Core Engine 的 schema、权限、trace、artifact 和模型路由。

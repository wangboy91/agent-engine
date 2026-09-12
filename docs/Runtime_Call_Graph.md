# Agent Engine Runtime Call Graph

本文说明当前代码里 `RunSkillUseCase`、`SkillRuntime`、`SkillEngine`、Agent、Ports 和 Infrastructure 的职责边界与调用关系。

## 文件索引

PlantUML 图放在 `doc/diagrams/`：

- `agent-layered-architecture.puml`：项目分层和依赖方向
- `agent-direct-skill-run-sequence.puml`：CLI / HTTP / SDK 直接运行 Skill 的调用链
- `agent-agent-message-sequence.puml`：自然语言 Agent 入口到 Skill 执行的调用链
- `agent-engine-core-class-relations.puml`：核心类和 ports 的关系

## 核心判断

`application/skill/run_skill.py` 和 `application/execution/skill_runtime.py` 不应该合并。

它们是两层职责：

```text
RunSkillUseCase
  应用用例入口，表达“我要运行一个 Skill”。

SkillRuntime
  执行运行时，负责“怎么把一次 Skill run 真正跑完”。
```

## 职责边界

### RunSkillUseCase

位置：

```text
engine/app/application/skill/run_skill.py
```

职责：

```text
接收 RunSkillCommand
调用 SkillRunnerPort.run_skill(...)
返回 RunResult
```

它不负责模型调用、工具调用、workflow 编排、trace、artifact 或 run 状态。

### SkillRuntime

位置：

```text
engine/app/application/execution/skill_runtime.py
```

职责：

```text
读取 Skill
创建 run_id
保存 run 状态
校验 input_schema / output_schema
执行普通 Skill 的 model/tool loop
执行 Workflow Skill 的 step 编排
记录 trace
保存 artifact
汇总 usage
处理失败状态
```

## 调用入口

### 直接运行 Skill

```text
CLI / HTTP / SDK
  -> RunSkillUseCase
  -> SkillEngine
  -> SkillRuntime
  -> Registry / ModelRouter / ToolExecutor / Stores
```

### Agent 自然语言入口

```text
CLI / HTTP Chat
  -> HandleAgentMessageUseCase
  -> AgentLoop
  -> SkillRouter
  -> InputResolver
  -> ActionRegistry
  -> SkillEngine
  -> SkillRuntime
```

## Ports 的作用

`application/ports.py` 是应用层对外部能力的抽象。

```text
Application 只依赖 Port
Infrastructure 实现 Port
```

这样 `SkillRuntime` 不直接依赖具体的数据库、文件系统、模型 provider 或工具 runner。

当前主要 ports：

```text
SkillRegistryPort
ToolRegistryPort
ModelGatewayPort
ToolExecutorPort
RunStorePort
TraceStorePort
ArtifactStorePort
```

## 设计约束

后续新增能力时建议遵守：

```text
用例入口、权限确认、异步队列、API 命令封装
  放 application/skill 或 application/agent

Skill 执行状态、模型循环、工具调用、workflow 编排
  放 application/execution

外部系统实现、模型 provider、持久化、package loader
  放 infrastructure

纯数据结构和领域对象
  放 domain
```


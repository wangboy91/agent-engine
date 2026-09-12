# ADR：企业智能体 Tenant、Workspace 与 Identity 层级设计

状态：建议采纳（2026-07-29）

## 1. 决策

采用“平台业务模板 + 租户实例”的双层模型：

- `WorkspaceBlueprint` 是平台级、可复用的虚拟业务工作目录，表示一个业务场景。
- `IdentityBlueprint` 位于 Workspace Blueprint 内，表示该业务场景中的某个业务身份智能体；一个 Workspace 可以包含多个 Identity。
- `Tenant` 是权限、配置所有权和运行数据的硬隔离根。
- `TenantWorkspace` 是某个 Tenant 安装指定 Workspace Blueprint 版本后产生的租户实例。
- `TenantIdentity` 是 TenantWorkspace 中可使用的智能体实例，默认引用 Identity Blueprint；开启定制后可以有租户覆盖版本。
- `User` 位于 Tenant 内，通过授权使用 TenantWorkspace 下的 Skill 或 Identity。

不采用“固定一个标准 Tenant，再从标准 Tenant 复制其他 Tenant”的方案。标准能力属于平台模板目录，不属于任何真实 Tenant。

## 2. 为什么不能只用一棵树

这里同时存在两个不同维度：

1. 业务复用维度：同一个 Workspace 业务场景需要复用给多个 Tenant。
2. 安全归属维度：任何可变配置、会话、记忆、Run 和 Artifact 必须归属于一个确定 Tenant。

如果把 Tenant 永久放在 Workspace 下面，业务复用直观，但数据库查询、鉴权和数据删除很容易漏掉 Tenant 条件。如果把所有内容直接复制到 Tenant 下面，安全边界清晰，但标准能力升级会产生大量漂移副本。

双层模型同时保留这两个优点：

```text
平台模板层（只读、版本化、可复用）

PlatformCatalog
└── WorkspaceBlueprint@version
    ├── SkillVersion references
    ├── IdentityBlueprint@version
    │   ├── Skill bindings
    │   ├── Tool bindings
    │   ├── Prompt bindings
    │   └── Knowledge/Component bindings
    └── Workspace default policies

租户实例层（权限和数据硬隔离）

Tenant
└── TenantWorkspace
    ├── base_workspace_blueprint_version
    ├── TenantCustomizationOverlay（可选）
    ├── TenantIdentity instances
    ├── User / Group / Grant
    ├── Session / Memory
    └── Run / Trace / Artifact / Approval
```

`WorkspaceBlueprint` 与 `TenantWorkspace` 是两个不同实体，前者解决复用，后者解决隔离。

## 3. Workspace 的定义

Workspace Blueprint 是一个虚拟业务工作目录，例如：

- 内容生产工作区；
- 招聘业务工作区；
- 员工发展工作区；
- 客户服务工作区。

它可以包含：

- 可直接执行的 Skill；
- 一个或多个 Identity 智能体；
- Tool、Prompt、Knowledge、Component 的引用；
- 默认模型、策略和场景路由；
- 示例、评测集和发布 manifest。

Workspace Blueprint 必须版本化且发布后不可修改。修改标准能力应创建新版本。

## 4. Identity 的定义

Identity 是某个业务身份的智能体，不是最终用户身份。

例如“员工发展”Workspace 可以包含：

- 员工发展顾问；
- 直属主管辅导助手；
- HR 发展运营助手；
- 发展计划审核助手。

Identity 应逐步扩展为：

```text
IdentityDefinition
└── IdentityVersion
    ├── model_profile
    ├── system_prompt
    ├── skill_bindings
    ├── tool_bindings
    ├── knowledge_bindings
    ├── component_bindings
    ├── routing_policy
    └── conversation_policy
```

管理界面可以使用“智能体”作为产品名称，代码领域统一使用 `Identity`。运行态仍使用 `AgentSession/AgentTurn`，避免把配置实体与执行实体混在一起。

## 5. 两种执行入口

### 5.1 Workspace 下直接执行 Skill

适合 API 调用、批处理或明确知道 Skill 的场景：

```text
tenant_id              required
tenant_workspace_id    required
identity_id             null
skill_id                required
user_id                 required for user action
```

运行时只加载 TenantWorkspace 允许的 Skill 版本和租户覆盖配置。

### 5.2 基于 Identity 执行任务

适合自然语言对话、场景路由和智能体任务：

```text
tenant_id              required
tenant_workspace_id    required
identity_id             required
user_id                 required
session_id              required or server-generated
```

Identity 决定可用 Skill、Tool、Prompt、Knowledge、模型和行为策略。

两种入口最终都生成统一的 Run、Trace 和 Artifact。

## 6. Tenant 定制模型

### 6.1 默认租户

默认 Tenant 只安装并引用已发布的 Workspace Blueprint 版本：

- 不能修改平台标准 Skill、Identity、Prompt 或 Tool；
- 可以配置运行期允许项，如用户授权、Secret 和额度；
- 平台升级 Workspace Blueprint 时，可以预览差异后升级 TenantWorkspace。

### 6.2 开启定制的租户

只有功能开关开启时才允许创建租户覆盖：

```text
tenant_features.workspace_customization = true
```

定制采用 Copy-on-Write：

- 不修改平台模板；
- 首次修改时创建 `TenantCustomizationOverlay`；
- 修改 Skill 时创建 tenant-owned Skill fork/version；
- 修改 Identity 时创建 tenant-owned IdentityVersion；
- 通过引用映射覆盖标准资源，不复制无变化的资源；
- 每次定制形成可审计版本。

配置解析顺序：

```text
Platform WorkspaceBlueprint Version
  -> TenantWorkspace pinned base version
  -> TenantCustomizationOverlay
  -> Environment override
  -> Runtime policy and user-private state
```

用户私有状态只能影响本次用户上下文，不能反向修改任何配置层。

## 7. 为什么不推荐“标准 Tenant”

固定一个标准 Tenant，再复制其他 Tenant，存在以下问题：

- Tenant 同时承担模板和真实客户两种语义，权限规则容易出现特殊分支。
- 标准 Tenant 中一旦产生测试会话、Secret 或用户数据，可能被错误复制或引用。
- 全量复制会产生大量重复资源，安全修复和升级难以传播。
- 各 Tenant 修改后出现配置漂移，很难判断哪些来自标准、哪些来自定制。
- 标准 Tenant ID 容易在鉴权代码中成为绕过条件。
- 包版本、引用和审计会退化成目录复制记录。

如果需要演示租户，可以单独创建 Demo Tenant，但它不能成为产品模板来源，也不能被生产 Tenant 继承。

## 8. Tenant 为什么仍是运行时顶层

虽然 Workspace Blueprint 在业务复用关系上位于 Tenant 之前，所有实际请求仍必须先确定 Tenant：

```text
Authenticated Principal
  -> tenant_id
  -> tenant_workspace_id
  -> identity_id or skill_id
  -> user_id
  -> session/run
```

数据库、缓存、对象存储、向量索引和事件订阅都必须以 `tenant_id` 开始构造作用域。不能先按全局 ID 查询数据，再在应用层补 Tenant 判断。

## 9. 记忆隔离

推荐明确区分四种记忆：

| 记忆类型 | 作用域 | 是否跨用户共享 |
| --- | --- | --- |
| 平台标准知识 | Workspace Blueprint Version | 是，只读 |
| 租户业务知识 | Tenant + TenantWorkspace + Identity | 同 Tenant 授权用户可共享 |
| 用户长期记忆 | Tenant + TenantWorkspace + Identity + User | 否 |
| 会话短期记忆 | Tenant + TenantWorkspace + Identity + User + Session | 否 |

用户记忆的完整命名空间：

```text
tenant_id
tenant_workspace_id
identity_id
user_id
memory_type
```

直接执行 Skill 且没有 Identity 时，用 `skill_id` 代替 `identity_id` 作为能力命名空间。

任何缓存、向量检索和 Prompt Context 组装缺少 `tenant_id` 或 `user_id` 时，都应拒绝加载用户记忆，而不是退化为共享查询。

## 10. 本地目录与生产存储

本地开发可以映射为虚拟目录：

```text
engine/resources/
└── workspace-blueprints/
    └── {workspace_key}/{version}/

data/
└── tenants/
    └── {tenant_id}/
        └── workspaces/
            └── {tenant_workspace_id}/
                ├── overrides/
                ├── users/{user_id}/memory/
                ├── sessions/
                ├── runs/
                └── artifacts/
```

目录只是本地 adapter 的存储形式，不是权限边界。生产环境应使用 PostgreSQL、对象存储和向量库，并在 repository 查询中强制 Tenant/User 条件。

## 11. 建议领域对象

```text
WorkspaceBlueprint
WorkspaceBlueprintVersion
IdentityDefinition
IdentityVersion
Tenant
TenantWorkspace
TenantCustomizationOverlay
TenantResourceOverride
TenantIdentity
TenantUser
TenantUserGroup
IdentityGrant
Session
UserMemory
Run
TraceEvent
Artifact
```

关键唯一约束建议：

```text
TenantWorkspace:
  unique(tenant_id, workspace_key)

TenantIdentity:
  unique(tenant_id, tenant_workspace_id, identity_key)

Session:
  unique(tenant_id, tenant_workspace_id, user_id, session_id)

UserMemory:
  unique(tenant_id, tenant_workspace_id, identity_or_skill_key, user_id, memory_key)
```

## 12. 迁移当前项目

当前 `Workspace` 和 `Identity` 可以渐进演进，不需要一次性重写：

1. 为所有运行上下文增加强制 `tenant_id`，保留现有 `workspace_id`。
2. 将现有 Workspace 语义明确为业务场景定义，新增 `TenantWorkspace` 安装关系。
3. 将现有 Identity 扩展为可版本化智能体配置，保留 Identity ID。
4. Skill 直接运行允许 `identity_id=None`；Identity 运行必须校验绑定能力。
5. Session、Memory、Run、Trace、Artifact 增加 tenant/workspace/user 所有权字段。
6. 增加平台模板目录和租户定制覆盖层。
7. 管理 API 区分 Blueprint 管理、Tenant 安装和 Tenant 定制。

## 13. 最终结论

推荐方案可以概括为：

```text
标准能力不放进“标准 Tenant”，而放进 Platform Workspace Blueprint。
Tenant 是所有可变配置和运行数据的安全顶层。
Tenant 安装 Workspace Blueprint 得到 TenantWorkspace。
Identity 是 Workspace 中的业务智能体，一个 Workspace 可以有多个 Identity。
只有开启定制功能的 Tenant 才能通过覆盖层修改资源。
所有用户记忆以 Tenant + Workspace + Identity/Skill + User 强隔离。
```


# 企业智能体 Web 管理端设计

状态：产品与交互设计提案（2026-07-29）

## 1. 产品定位

Web 版由两个相互隔离的入口组成：

- 管理控制台：配置、发布、治理和观测智能体平台。
- 用户工作台：最终用户使用被授权的智能体，管理自己的会话和产物。

两个入口可以属于同一个 Web 应用，但必须采用不同路由、权限和后端 API。管理员进入用户内容必须走显式审计流程，不能因为拥有配置权限就默认读取全部会话正文。

管理界面使用“智能体”名称，后端领域模型使用 `Identity`。平台 Workspace Blueprint 表示可复用业务场景，TenantWorkspace 表示某租户安装后的实例。

## 2. 设计原则

- 企业级、数据密集、低装饰，优先保证信息层级和操作确定性。
- 每个页面只有一个主操作；危险操作与普通操作分离。
- 所有资源详情页可深链，返回后保留筛选和滚动位置。
- 长表格支持筛选、排序、列配置和分页；超过 50 行使用虚拟列表。
- 表单使用可见 label、就地校验、草稿自动保存和未保存离开提醒。
- 状态不能只靠颜色表达，必须同时显示文字或图标。
- 键盘可操作、焦点可见、正文对比度不低于 4.5:1。
- 流式运行、发布和同步操作必须有清晰进度、错误原因和恢复入口。

## 3. 总体信息架构

```text
管理控制台
├── 总览
├── 智能体
├── 资源中心
│   ├── Skill
│   ├── 工具与连接器
│   ├── Prompt
│   ├── UI 组件
│   ├── 知识库
│   └── 模型
├── 运行中心
│   ├── 会话
│   ├── Run
│   ├── 任务与调度
│   └── 产物
├── 治理中心
│   ├── 审批
│   ├── 策略
│   ├── Secret
│   ├── 评测与发布
│   └── 审计日志
└── 设置
    ├── 工作空间
    ├── 成员与角色
    ├── 用户组与智能体授权
    ├── 环境
    └── 配额

用户工作台
├── 我的智能体
├── 会话
├── 我的任务
├── 我的产物
├── 我的记忆
└── 个人设置
```

桌面端使用固定左侧导航；顶部栏始终显示租户、工作空间、环境、全局搜索、待审批数量和当前用户。租户/工作空间切换后，所有列表立即清空旧缓存并重新请求，避免视觉串线。

## 4. 全局页面框架

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Logo  租户 / 工作空间 / 环境      全局搜索      审批  帮助  当前用户     │
├──────────────┬───────────────────────────────────────────────────────────┤
│ 总览         │ 面包屑                                      页面主操作   │
│ 智能体       │ 页面标题、说明、状态摘要                                   │
│ 资源中心     ├───────────────────────────────────────────────────────────┤
│ 运行中心     │ 筛选 / 搜索 / 保存视图                                     │
│ 治理中心     ├───────────────────────────────────────────────────────────┤
│ 设置         │ 主内容：表格、详情、编辑器、时间线或指标                    │
│              │                                                           │
└──────────────┴───────────────────────────────────────────────────────────┘
```

推荐视觉基线：

- 风格：Data-Dense Dashboard，支持完整明暗主题。
- 主色：`#2563EB`，成功/确认色：`#059669`，危险色：`#DC2626`。
- 背景：`#F8FAFC`，正文：`#0F172A`，边框：`#E4ECFC`。
- 使用语义颜色 token，不在组件内散落硬编码颜色。
- 字号等级：12/14/16/18/24/32；正文桌面端 14–16px，移动端不低于 16px。
- 4/8px 间距体系；交互目标至少 44×44px。
- 动效仅用于状态因果，150–300ms，并支持 `prefers-reduced-motion`。
- 图标统一使用同一套 SVG 线性图标，不使用 Emoji 作为结构图标。

## 5. 管理控制台页面设计

### 5.1 总览

展示范围由当前工作空间和环境决定：

- 已发布智能体、近 24 小时 Run、成功率、P95 延迟、成本和待审批。
- 失败趋势、模型/Tool 错误分布和高成本智能体。
- 最近发布、风险告警、队列积压和 provider 健康。
- 快捷入口：创建智能体、导入 Skill、添加工具服务。

指标卡必须可点击进入带相同筛选条件的明细页。

### 5.2 智能体列表

列：名称、状态、当前版本、负责人、已绑定 Skill/Tool、授权用户数、最近运行、成功率、更新时间。

筛选：状态、负责人、标签、环境、模型、更新时间。主操作是“创建智能体”。

行操作：查看、复制草稿、停用、查看引用；删除仅对从未发布且无引用的草稿开放。

### 5.3 智能体详情与编辑

```text
智能体名称  Draft v1.4              [保存草稿] [测试] [提交发布]
概览 | 模型 | 提示词 | 对话 | Skill | 工具 | 知识 | 组件 | 渠道 | 版本
────────────────────────────────────────────────────────────────
左侧：当前配置表单                    右侧：配置目录 / 校验结果
────────────────────────────────────────────────────────────────
底部可折叠调试台：模拟用户、输入、事件、Trace、产物
```

各页签：

| 页签 | 内容 |
| --- | --- |
| 概览 | 名称、头像、描述、标签、负责人、使用范围 |
| 模型 | Profile、温度、预算、fallback、超时 |
| 提示词 | System Prompt、模板引用、变量和渲染预览 |
| 对话 | 欢迎语、输入提示、兜底、FAQ、附件和历史策略 |
| Skill | 已绑定版本、触发场景、输入映射和优先级 |
| 工具 | 已绑定工具、策略、默认参数和审批要求 |
| 知识 | 知识库、召回策略、用户私有记忆策略 |
| 组件 | slot 与组件版本绑定、Mock 预览 |
| 渠道 | Web/API/第三方渠道能力与用户映射 |
| 版本 | Diff、发布说明、评测结果、回滚和引用 |

长表单自动保存草稿；发布前显示统一检查面板：Schema、引用、权限、Secret、评测和兼容性。

### 5.4 Skill 中心

- 列表：名称、编码、最新发布版本、状态、引用数、负责人、更新时间。
- 详情：核心指令、文件、Schema、允许工具、示例、引用、版本和评测。
- 文件查看器只读展示；编辑通过新建草稿或上传新包完成。
- 发布时展示权限与依赖差异。

### 5.5 工具与连接器

第一层是 Tool Service，第二层是 operation。

- Service 列表：类型、Base URL/Server、认证引用、工具数量、同步状态、健康、负责人。
- Service 详情：操作清单、OpenAPI 差异、同步历史、网络策略和调用指标。
- Tool 配置抽屉：别名、描述、默认参数、扩展配置和风险级别。
- “刷新”不能静默覆盖生产版本；生成差异并创建新草稿版本。

### 5.6 Prompt、组件、知识与模型

- Prompt：模板编辑器、变量 Schema、渲染预览、引用、版本和评测。
- UI 组件：Schema、slot、Mock 数据、宿主预览、引用和版本。
- 知识库：数据源、文档、索引状态、同步任务、ACL、召回测试和引用。
- 模型：Provider、Profile、能力、健康、价格、密钥引用、允许范围和用量。

### 5.7 会话、Run 和产物

管理侧列表默认显示脱敏摘要，不默认展示用户完整消息。

- 会话：用户匿名标识、智能体版本、消息数、状态、最近活动。
- Run：状态、发起主体、资源快照、耗时、模型/Tool 用量、错误。
- Run 详情：时间线、步骤树、策略判断、工具调用、产物和安全摘要。
- Artifact：类型、大小、所有者、保留期、下载审计和删除状态。

读取正文或下载用户产物时，必须执行额外权限检查并记录审计理由。

### 5.8 审批、策略与审计

- 审批队列按风险、等待时长、Tool、智能体和发起人筛选。
- 审批详情展示最小必要参数、风险原因、策略来源和影响范围。
- 策略编辑器明确作用域和优先级，并提供“以某用户模拟评估”。
- 审计日志不可修改，支持资源、操作者、最终用户、时间和事件类型筛选。

## 6. 用户工作台设计

用户工作台只展示当前登录用户自己的数据。

### 6.1 我的智能体

- 卡片展示用户已获授权的智能体、说明和最近使用时间。
- 不展示内部 Prompt、Tool 参数、策略或未发布版本。
- 点击进入新会话或恢复本人历史会话。

### 6.2 会话页

```text
┌──────────────┬───────────────────────────────┬─────────────────────┐
│ 我的会话     │ 消息区                         │ 本次任务 / 产物      │
│ + 新建       │                               │                     │
│ 历史会话     │                               │                     │
│              │                               │                     │
│              ├───────────────────────────────┤                     │
│              │ 附件  输入框          发送     │                     │
└──────────────┴───────────────────────────────┴─────────────────────┘
```

- 左侧只加载当前用户的 Session。
- 中间消息区显示安全的执行步骤摘要，不显示模型私有推理。
- 右侧展示当前用户本次会话关联的任务和产物。
- 移动端折叠为“会话列表 / 对话 / 任务产物”三个层级页面，不出现横向滚动。

### 6.3 我的记忆

- 展示智能体为当前用户保存的长期偏好和来源。
- 用户可以纠正、删除或关闭长期记忆。
- 工作空间共享知识不得混入“我的记忆”列表。

## 7. 多用户隔离设计

### 7.1 请求主体

后端从验证后的 Token 构造不可伪造的 `Principal`：

```text
Principal
├── tenant_id
├── principal_id
├── principal_type: user | service_account
├── workspace_roles[]
├── group_ids[]
└── auth_session_id
```

业务请求中的 `user_id` 不能直接决定访问主体。最终用户操作统一使用 `principal_id`；管理员代用户操作需要单独的 impersonation claim、原因和审计事件。

### 7.2 数据作用域

所有用户运行数据至少携带以下字段：

```text
tenant_id
tenant_workspace_id
identity_definition_id
identity_version_id
owner_principal_id
session_id
```

Run、Trace、Artifact 和 Memory 继续携带 `session_id` 或 `run_id` 形成所有权链。

### 7.3 共享与私有边界

| 数据 | 默认边界 |
| --- | --- |
| WorkspaceBlueprint、标准 IdentityVersion | 平台模板层只读复用 |
| TenantWorkspace、TenantIdentity 定制 | Tenant 内共享，按角色管理 |
| Skill/Tool/Prompt/Component/Knowledge 标准配置 | Workspace Blueprint 版本引用 |
| Tenant-owned 资源覆盖 | 仅开启定制功能的 Tenant 可创建 |
| 租户工作空间知识库 | TenantWorkspace 共享，但检索遵守文档 ACL |
| Session、Message | 最终用户私有 |
| UserMemory | 最终用户 + 智能体私有命名空间 |
| Run、Trace、Artifact | 最终用户私有；管理读取需权限和审计 |
| Secret | 工作空间/环境受控，永不下发最终用户 |

### 7.4 强制隔离规则

1. Session 由服务端生成 ID，创建后 `tenant/tenant_workspace/owner/identity` 不可修改。
2. 读取 Session 时使用组合条件，不先按 ID 读取再在应用层过滤：

   ```sql
   SELECT * FROM agent_sessions
   WHERE tenant_id = :tenant
     AND tenant_workspace_id = :tenant_workspace
     AND owner_principal_id = :principal
     AND session_id = :session;
   ```

3. Run、Trace、Artifact 通过相同 owner 字段或受约束的所有权链查询。
4. Memory namespace 必须包含 tenant、tenant workspace、identity（直接 Skill 模式使用 skill）和 principal。
5. 向量库 metadata filter 与关系库授权条件一致；缺少 filter 时拒绝检索。
6. Redis/cache key 必须包含 tenant、tenant workspace 和 principal，切换工作空间时清理客户端缓存。
7. SSE/WS 订阅由服务端根据 Principal 创建 filter，客户端不能任意订阅 user_id。
8. Artifact 下载使用短时签名 URL，并在签发前校验 owner/管理员审计权限。
9. Tool 的用户数据访问凭据不能跨用户缓存；OAuth token 按 principal 隔离。
10. 日志和 Trace 对输入、输出、Token、密钥和个人信息执行分级脱敏。

### 7.5 防串线验收测试

至少覆盖以下双用户场景：

- 用户 A、B 使用同一 IdentityVersion，同时创建和发送消息。
- B 使用 A 的 session_id、run_id、artifact_id 和 event cursor 请求，均返回 404 或 403。
- A 的长期记忆不会出现在 B 的 Prompt Context 或检索结果。
- 管理员没有数据查看权限时只能看到聚合指标和脱敏摘要。
- 管理员授权查看 A 的正文时产生含原因的审计事件，不能顺带读取 B。
- workspace 切换后浏览器旧请求、缓存和 WebSocket 不会继续显示原 workspace 数据。
- 任务重试、审批恢复和回调仍保持原始 owner，不接受新请求覆盖。
- 搜索、导出、批量接口和对象存储下载遵守同样隔离规则。

## 8. API 分层建议

管理 API：

```text
/api/v1/platform/workspace-blueprints
/api/v1/tenants/{tenant_id}/workspaces
/api/v1/tenants/{tenant_id}/workspaces/{tenant_workspace_id}/identities
/api/v1/tenants/{tenant_id}/workspaces/{tenant_workspace_id}/skills
/api/v1/tenants/{tenant_id}/workspaces/{tenant_workspace_id}/tool-services
/api/v1/tenants/{tenant_id}/workspaces/{tenant_workspace_id}/prompts
/api/v1/tenants/{tenant_id}/workspaces/{tenant_workspace_id}/components
/api/v1/tenants/{tenant_id}/workspaces/{tenant_workspace_id}/knowledge-bases
/api/v1/tenants/{tenant_id}/workspaces/{tenant_workspace_id}/policies
/api/v1/tenants/{tenant_id}/audit-events
```

最终用户 API 使用 `/me` 语义，避免客户端传任意用户 ID：

```text
/api/v1/me/identities
/api/v1/me/identities/{identity_id}/sessions
/api/v1/me/sessions/{session_id}/messages
/api/v1/me/runs/{run_id}
/api/v1/me/artifacts/{artifact_id}
/api/v1/me/memories
```

服务端管理 API：

```text
/api/v1/admin/tenants
/api/v1/admin/model-providers
/api/v1/admin/system-health
```

所有租户接口先经过 Authentication → Tenant Membership → TenantWorkspace Grant → Resource Permission → Data Ownership，再进入 application use case。平台 Blueprint 接口使用独立的平台管理权限。

## 9. 前端实现边界

推荐将现有 FastAPI 保持为唯一后端入口，Web 前端只调用公开 application API：

- 管理端可采用 React/Next.js 或 Vue；组件库选择不改变领域 Contract。
- 所有列表请求必须由后端分页和过滤，前端过滤不能作为权限措施。
- query cache key 包含 tenant、tenant workspace 和当前 Principal；登出或切换作用域时清空。
- 路由级权限用于改善体验，真正授权仍由后端执行。
- 运行事件统一消费 SSE/WS contract，页面刷新后通过 cursor 恢复。
- 先保留现有 `/ui` 作为开发调试控制台，新管理端使用独立 `/console`，用户端使用 `/app`。

## 10. Web 版交付顺序

### W0：安全底座

- 登录、Principal、Workspace Membership、RBAC。
- PostgreSQL Store 和用户所有权模型。
- Session/Run/Trace/Artifact/Memory 强隔离。
- 审计事件和双用户越权测试。

### W1：只读管理控制台

- 总览、智能体占位目录、Skill/Tool、Run/Trace/Artifact、审批。
- 先复用现有 API，缺失字段明确展示“尚未支持”，不伪造功能。

### W2：智能体管理闭环

- IdentityDefinition/Version、配置编辑、调试、发布和用户授权。
- Skill 多版本、引用和资源快照。
- 用户工作台“我的智能体”和隔离会话。

### W3：完整资源中心

- Tool Service、Prompt、UI Component、KnowledgeBase、模型 Profile。
- 资源版本、引用、评测和发布检查。

### W4：生产运营

- 队列/任务/调度、对象存储、质量/成本看板、灰度和告警。
- MCP/Channel 和受控多智能体任务。

W0 验收通过之前，可以开发静态页面和 Mock 数据，但不能把真实多用户入口作为可上线能力。

## 11. Web 版完成标准

- 平台能发布 Workspace Blueprint；Tenant 能安装它，开启定制后可创建 Tenant-owned 覆盖版本。
- 管理员能创建并发布一个绑定 Skill、Tool、Prompt 和模型的 Identity 智能体版本。
- 管理员能把该版本授权给两个最终用户。
- 两个用户能独立建立会话、运行 Skill 并查看自己的产物。
- 任一用户无法通过猜测或复用 ID 访问另一用户的数据。
- 管理员能看到聚合运行指标；读取用户正文需要额外授权并留审计。
- Run 可以追溯 Agent、Skill、Tool、Prompt、模型和策略的精确版本。
- 关键页面支持 375/768/1024/1440px，键盘操作、可见焦点和明暗主题。

完整层级、执行入口和 Tenant 定制解析顺序见 [Tenant、Workspace 与 Identity 层级设计 ADR](ADR_企业智能体租户与Workspace层级设计.md)。

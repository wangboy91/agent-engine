# Design: tenant-workspace-identity-registry

状态：1.0.1 后端重构权威设计  
上游：`docs/权限架构设计.md`、`docs/技术实现文档_1.0.1.md`、`docs/ADR_企业智能体租户与Workspace层级设计.md`  
产品目标：`prototype/web` r2

## 1. 目标与边界

在不大爆炸重写 `SkillEngine` 的前提下，为平台化补齐：

1. 租户与工作空间实例模型；
2. 可版本化 Identity；
3. 最终用户所有权字段与查询强制；
4. Artifact 个人目录语义 API；
5. Principal 注入点。

## 2. 架构落点

```text
interfaces/http
  auth dependency: PrincipalProvider（dev header + test override）
  routes /api/v1/... 与兼容旧路由
        │
application
  use cases: identity_registry, grant, artifact_catalog, ownership_scope
  ports: TenantWorkspaceRepo, IdentityRepo, GrantRepo, ArtifactCatalogRepo
        │
domain
  schemas: Tenant, TenantWorkspace, IdentityDefinition/Version, Grant, ArtifactMeta
  rules: lifecycle, owner immutability, path builder
        │
infrastructure
  json adapters + existing stores（扩展字段）
```

依赖规则不变：application 不 import 具体 JSON 实现。

## 3. 领域模型（最小集）

### 3.1 Tenant / Workspace

```text
Tenant
  id, name, status, features{workspace_customization}, created_at

WorkspaceBlueprint
  id, key, name, description

WorkspaceBlueprintVersion
  id, blueprint_id, version, status, manifest_ref?

TenantWorkspace
  id, tenant_id, workspace_key, blueprint_version_id?, environment, status
  unique(tenant_id, workspace_key)
```

### 3.2 Identity

```text
IdentityDefinition
  id, tenant_id, tenant_workspace_id, key, name, description, status

IdentityVersion
  id, definition_id, version, status(draft|review|published|archived),
  model_profile, system_prompt,
  skill_bindings[], tool_bindings[],
  routing_policy?, conversation_policy?,
  resource_snapshot{}, created_at, published_at?
  unique(definition_id, version)

IdentityGrant
  id, tenant_id, tenant_workspace_id,
  identity_version_id, grantee_type(user|group), grantee_id,
  granted_by, created_at, expires_at?
```

约束：

- 仅 `published` 版本可创建 Grant；
- 发布后 `IdentityVersion` 内容不可变（新改动必须新 version）。

### 3.3 所有权字段

以下实体必须携带且查询强制：

```text
tenant_id
tenant_workspace_id
owner_principal_id
identity_id? / skill_id?
session_id? / run_id?
```

涉及：`AgentSession`、`Run`、`TraceEvent`（可继承 Run）、`ArtifactMeta`、`UserMemory`（Memory 可在本 change 只加字段不改行为）。

### 3.4 ArtifactMeta

```text
ArtifactMeta
  artifact_id
  tenant_id, tenant_workspace_id, owner_principal_id
  run_id, session_id?, identity_key?
  logical_path   # 相对 owner 根，如 发展规划助手/2026-07-28/run_9f2a/plan.json
  object_key     # 实际文件路径
  media_type, size_bytes, checksum?
  created_at, expires_at?
```

逻辑路径解析：

```text
tenants/{tenant}/workspaces/{ws}/users/{owner}/{logical_path}
```

## 4. Principal 与鉴权桩

```text
Principal
  tenant_id, principal_id, principal_type, workspace_roles[], scopes[]
```

实现顺序：

1. `PrincipalProvider` Protocol；
2. `DevHeaderPrincipalProvider`：开发环境从可信反代/本机 header 读取（仅 dev）；
3. FastAPI dependency 统一解析；缺失时 401；
4. 测试用 `override_principal` fixture；
5. **不在本 change** 实现完整 OIDC，但禁止业务 handler 自行信任 body.user_id。

## 5. RunContext 扩展

在现有 context 上增加：

```text
tenant_id
tenant_workspace_id
identity_id?
identity_version_id?
owner_principal_id
resource_snapshot?
```

Trace 首条事件记录解析后的资源版本，便于反查。

## 6. API 契约（本 change 必须交付）

### 6.1 管理

```text
POST   /api/v1/tenants
GET    /api/v1/tenants/{tenant_id}
POST   /api/v1/tenants/{tenant_id}/workspaces
GET    /api/v1/tenants/{tenant_id}/workspaces
POST   /api/v1/tenants/{tenant_id}/workspaces/{ws_id}/identities
GET    /api/v1/tenants/{tenant_id}/workspaces/{ws_id}/identities
GET    /api/v1/tenants/{tenant_id}/workspaces/{ws_id}/identities/{identity_id}
POST   /api/v1/tenants/{tenant_id}/workspaces/{ws_id}/identities/{identity_id}/versions
POST   /api/v1/tenants/{tenant_id}/workspaces/{ws_id}/identity-versions/{version_id}/publish
POST   /api/v1/tenants/{tenant_id}/workspaces/{ws_id}/grants
GET    /api/v1/tenants/{tenant_id}/workspaces/{ws_id}/grants
```

### 6.2 最终用户

```text
GET  /api/v1/me/identities
POST /api/v1/me/identities/{identity_id}/sessions
GET  /api/v1/me/sessions
GET  /api/v1/me/sessions/{session_id}
GET  /api/v1/me/sessions/{session_id}/messages
GET  /api/v1/me/runs
GET  /api/v1/me/runs/{run_id}
GET  /api/v1/me/artifacts?path=
GET  /api/v1/me/artifacts/{artifact_id}
GET  /api/v1/me/artifacts/{artifact_id}/download
```

语义要点：

- `/me/*` 主体永远来自 Principal，不接受 `?user_id=`
- 路径查询：`path=/` 列本人根（智能体目录）；子路径列文件夹/文件
- 他人 artifact：404/403（测试固定一种并写断言，建议 404 防枚举）
- download：返回短时 URL 或流式响应；本 change 可先本地文件流 + 到期字段

### 6.3 管理读产物（最小）

```text
GET /api/v1/tenants/{t}/workspaces/{ws}/artifacts?owner=
```

默认仅元数据，无预览正文。完整 elevate API 可在本 change 提供简化版：

```text
POST /api/v1/tenants/{t}/workspaces/{ws}/artifact-elevations
  { owner_principal_id, reason, path_prefix? }
```

成功则写审计事件并返回短时 elevate token（内存实现即可）。

## 7. 存储策略

本 change 使用 JSON/内存 adapter，但必须：

1. 保存时写入完整 ownership 字段；
2. `get/list` 强制过滤参数（缺 tenant/owner 的 list 对 `/me` 直接报错）；
3. 不新增「先按 id 取再应用层判断」的公开方法；
4. 为未来 PostgreSQL 预留同一 Port 接口。

建议文件：

```text
engine/.agent/
  tenants.json
  identities.json
  grants.json
  artifacts.json   # ArtifactMeta only
```

## 8. 与现有 Workspace/Identity 兼容

| 现状 | 策略 |
| --- | --- |
| WorkspaceStore | 保留；新增 TenantWorkspace 为权威模型，旧 workspace 可映射为 `workspace_key` 兼容视图 |
| Identity 记录 | 扩展为 Definition+Version；旧 identity_id 在兼容层解析到 latest published version |
| AgentLoop | 继续可用；若传入 identity_version_id 则按绑定 Skill 解析 |
| Catalog | 不变 |

兼容目标：现有测试与 CLI smoke 不红。

## 9. 安全默认值

- `/me` 无认证 → 401
- 跨 owner → 404
- 发布非 draft → 409
- Grant 非 published version → 400
- 无 reason 的 elevate → 400
- 审计事件至少：elevate_artifact_read、identity_publish、grant_create

## 10. 测试计划

| 文件 | 覆盖 |
| --- | --- |
| `test_tenant_identity_registry.py` | 创建/发布/Grant/仅 published 可 Grant |
| `test_ownership_isolation.py` | A/B session/run/artifact 串线矩阵 |
| `test_me_artifact_api.py` | 目录树、预览、下载、404 |
| `test_principal_dependency.py` | 401、override fixture |
| 既有套件 | 全量回归 |

## 11. 实施切片（与 tasks 对齐）

1. Domain schemas + 校验  
2. Ports + JSON adapters  
3. Principal dependency  
4. Use cases + `/api/v1`  
5. RunContext/存量 store 扩展  
6. Artifact catalog  
7. 测试与文档回写  
8. verify  

## 12. 决策记录

| # | 决策 | 结论 |
| --- | --- | --- |
| A1 | 是否本 change 上 PostgreSQL | 否，JSON adapter + Ports |
| B1 | 跨用户 404 还是 403 | 默认 404 |
| C1 | elevate 形态 | 简化 elevate API + 审计，完整 RBAC 后续 |
| D1 | 旧 API | 保留兼容，新前端只依赖 `/api/v1` |
| E1 | 路径键使用 principal_id | 是，不用展示名 |

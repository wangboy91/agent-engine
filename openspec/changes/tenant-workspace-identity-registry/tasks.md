# Tasks: tenant-workspace-identity-registry

状态：**apply 基本完成**（核心任务已勾选；`141 passed` / ruff / mypy 通过）。  
剩余仅收尾：`openspec verify` → archive，以及可选的 Port 拆分与 OIDC。

## 1. Domain

- [x] 新增 `Tenant`、`WorkspaceBlueprint(Version)`、`TenantWorkspace` Pydantic 模型与状态枚举
- [x] 新增 `IdentityDefinition`、`IdentityVersion`、`IdentityGrant` 模型与生命周期规则（仅 draft 可改、仅 published 可 Grant）
- [x] 新增 `ArtifactMeta` 与逻辑路径 `build_owner_artifact_path()` 工具
- [x] 为 Session/Run（及 Memory）模型补充 `tenant_id`、`tenant_workspace_id`、`owner_principal_id` 等所有权字段（可空兼容旧数据）
- [x] Domain 单元测试：生命周期、路径拼装、Grant 校验（含在 `test_ownership_isolation.py`）

## 2. Ports 与 JSON 适配器

- [x] 平台仓储 Port 语义（`InMemoryPlatformRegistryStore` / `JsonPlatformRegistryStore` / **`PostgresPlatformRegistryStore`** 统一接口）
- [x] 实现 JSON/内存 adapter，落盘 `engine/.agent/platform.json`
- [x] **PostgreSQL adapter**（`platform_registry_pg.py`），库 `agent_engine`，表前缀 `platform_*`
- [x] `SkillEngine.load()` 在 `AGENT_ENGINE_DATABASE_URL` 存在时优先使用 PG
- [x] `list`/`get` 强制带 `tenant_id`；`/me` 资源强制 `owner_principal_id`
- [x] Session `get_for_owner` / `list_for_owner`；禁止跨 owner 返回
- [x] **Session / Run / Trace 迁 PostgreSQL**（`runtime_registry_pg.py`）
- [x] 双库预留：`AGENT_ENGINE_DATABASE_URL`（主）+ `AGENT_ENGINE_RUNTIME_DATABASE_URL`（运行库，未设则复用主库）
- [ ] 补充独立 `TenantWorkspaceRepository` 等拆分 Port（当前合并为 PlatformRegistry，可后续再拆）

## 3. Principal

- [x] 实现 `Principal` 模型（`domain/platform`）
- [x] FastAPI dependency：dev header 解析；缺失 → 401
- [x] `/api/v1` 统一注入 Principal
- [x] 测试：无 Principal 401；A/B 用户切换隔离

## 4. Use Cases 与 API

- [x] `CreateTenant` / `CreateTenantWorkspace`
- [x] `CreateIdentity` / `CreateIdentityVersion` / `PublishIdentityVersion`
- [x] `CreateIdentityGrant` / `ListMyIdentities`
- [x] `StartMySession` / `ListMySessions` / `GetMySession`（owner 强制）
- [x] `ListMyRuns` / `GetMyRun`
- [x] 路由：`/api/v1/tenants...`、`/api/v1/me/identities|sessions|runs`
- [x] 主要管理接口补充 `response_model`（Tenant/Workspace/IdentityVersion/Grant/Artifact/Elevation/Audit）

## 5. 执行链路贯通

- [x] `RunContext` 增加 tenant/workspace/owner/identity_version/snapshot 字段
- [x] HTTP `/skills/{id}/runs` 在带 Principal 头时自动写入 ownership 字段
- [x] Workflow 子 Run 继承 ownership（`_child_context`）
- [x] Run 完成后自动登记 `ArtifactMeta`（`register_run_artifacts_into_platform`）
- [x] Run/Trace 可持久化 ownership（经 RunContext）
- [x] 兼容：无 tenant 的旧 CLI 调用仍可跑（字段可空；全量测试通过）

## 6. Artifact 目录 API

- [x] `ArtifactMeta` 登记 API（`POST .../artifacts`）与逻辑路径
- [x] `GET /api/v1/me/artifacts?path=` 目录列表（文件夹/文件）
- [x] `GET /api/v1/me/artifacts/{id}` owner 校验
- [x] `GET /api/v1/me/artifacts/{id}/download` owner 校验 + 本地 token 占位
- [x] 管理列表：`.../artifacts?owner=` 仅元数据
- [x] 简化 elevate：`POST .../artifact-elevations`（reason 必填）+ 审计事件
- [x] Run 结束自动同步 ArtifactMeta（`SkillEngine.run_skill` 钩子）

## 7. 隔离与回归测试

- [x] `test_ownership_isolation.py`：A/B 同 Identity，session/artifact 互不可见；grant/发布矩阵
- [x] 目录树、他人 404、download 校验（合入上文件）
- [x] 全量 `pytest` 通过（**141 passed**，含 PG 集成 + ownership bridge）
- [x] `ruff` 通过；`mypy app` 通过
- [x] `tests/test_platform_registry_pg.py`：平台注册表 PG 验收
- [x] `tests/test_run_ownership_bridge.py`：Principal 注入 RunContext + ArtifactMeta 自动登记

## 8. 文档与收尾

- [x] 更新 `docs/技术实现文档_1.0.1.md` 中与实现不一致处
- [x] 更新根 `README.md` 的 `/api/v1` 与 Principal 头说明
- [ ] `openspec verify` → 通过后 archive 本 change
- [x] 明确下游：`frontend-backend-separation` 可基于本 change 契约开工

## 已知后续（不阻塞前端联调）

1. Chat `/chat/messages` 与 SSE/WS 路由尚未自动注入 Principal（`/skills/*/runs` 已支持）
2. 独立 repository Ports 拆分
3. 生产 OIDC 替换 dev header PrincipalProvider
4. Artifact 逻辑路径日期/identity 与前端 r2 展示对齐可再打磨

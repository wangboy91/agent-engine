# Proposal: tenant-workspace-identity-registry

## Why

0.1.0 内核已能跑 Skill/Tool/Agent，但缺少企业 SaaS 基座的前置能力：

1. 没有可发布的 `IdentityDefinition/IdentityVersion`，Agent 更像运行时路由器；
2. 没有 `Tenant` / `TenantWorkspace`，无法形成租户硬隔离根；
3. Session/Run/Artifact 查询未按最终用户强制过滤，存在串线与越权风险；
4. Artifact 仅是本地文件，缺少「个人目录树」语义与 `/me` API，无法支撑定稿原型 r2；
5. HTTP 无 Principal 注入点，前端无法在隔离正确性上验收。

1.0.1 原型已定稿。必须**先重构后端服务**，再做前后端分离，否则前端只能堆 Mock。

## What Changes

- 新增平台/租户/Identity 领域模型与 JSON/内存 repository（Ports + adapter）。
- 贯通 `RunContext` 所有权字段与资源版本快照。
- Session owner 创建后不可变；Run/Trace/Artifact 按 `tenant + workspace + owner` 过滤。
- Artifact 逻辑路径 `users/{owner}/…`、元数据、目录列表 API、短时下载策略接口。
- 认证依赖桩：请求可注入 Principal（开发 header/测试依赖；生产 OIDC 后续替换）。
- 新增 `/api/v1` 管理与 `/api/v1/me` 路由骨架。
- 双用户越权与 owner 过滤测试。
- 保持 `SkillEngine` 与现有 CLI 主路径兼容。

## Impact

- 受影响：`engine/app/domain/**`、`application/**`、`infrastructure/persistence/**`、`interfaces/http/**`
- 新增测试：registry、ownership、me API、artifact catalog
- 文档：`docs/技术实现文档_1.0.1.md` 为蓝本；本 change 的 design/tasks 为唯一实施计划
- **不包含**：`web/` 前端实现（见 `frontend-backend-separation`）
- **不包含**：PostgreSQL/OIDC/KMS/队列生产件（预留 Port，不阻塞本 change）

## Non-goals

- 不改 SkillRuntime 模型循环语义
- 不做 Prompt/Component/Knowledge 中心
- 不做真实多副本与对象存储
- 不实现完整 RBAC UI（API 与测试先保证隔离正确）

## Depends On

- 无（本 change 是 1.0.1 第一个实施项）
- 下游：`frontend-backend-separation` 必须在本 change 的 `/api/v1` 契约稳定后联调

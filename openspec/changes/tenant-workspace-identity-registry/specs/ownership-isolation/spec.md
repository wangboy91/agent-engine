# ownership-isolation Specification

## ADDED Requirements

### Requirement: 最终用户数据所有权

Session、Run、Artifact 等用户运行数据必须携带 `tenant_id`、`tenant_workspace_id`、`owner_principal_id`，
读取时由服务端按 Principal 强制过滤。

#### Scenario: 会话所有权创建后不可变

- **WHEN** 创建 AgentSession
- **THEN** owner 与 tenant/workspace 写入后不可被后续请求覆盖

#### Scenario: 双用户会话隔离

- **WHEN** 用户 B 使用用户 A 的 `session_id` 调用 `/api/v1/me/sessions/{id}`
- **THEN** 返回 404，且响应体不包含 A 的会话内容

#### Scenario: 双用户 Run 隔离

- **WHEN** 用户 B 使用用户 A 的 `run_id` 调用 `/api/v1/me/runs/{id}`
- **THEN** 返回 404

#### Scenario: 旧数据兼容路径不破坏隔离

- **WHEN** 存在缺少 tenant 字段的历史 Run 且通过旧 CLI 访问
- **THEN** 旧开发路径仍可用，但 `/api/v1/me` 不得返回无主或跨主数据

### Requirement: Principal 为唯一访问主体

`/api/v1/me/*` 与受保护管理接口的访问主体来自服务端 Principal，不信任请求体中的 `user_id`。

#### Scenario: 缺少认证

- **WHEN** 请求 `/api/v1/me/identities` 且无有效 Principal
- **THEN** 返回 401

#### Scenario: 忽略伪造 user_id

- **WHEN** 已认证用户 A 在 query/body 中传入 `user_id=B`
- **THEN** 服务端仍以 Principal A 查询，不能读取 B 的数据

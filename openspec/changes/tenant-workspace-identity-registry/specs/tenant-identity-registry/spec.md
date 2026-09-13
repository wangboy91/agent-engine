# tenant-identity-registry Specification

## ADDED Requirements

### Requirement: 租户与工作空间实例

平台可创建 Tenant；Tenant 可创建 TenantWorkspace（业务工作空间实例）。
TenantWorkspace 在租户内以 `workspace_key` 唯一。

#### Scenario: 创建租户与工作空间

- **WHEN** 管理 API 创建 Tenant 并在该 Tenant 下创建 TenantWorkspace
- **THEN** 返回稳定 ID，且同一 Tenant 下重复 `workspace_key` 被拒绝

#### Scenario: 工作空间归属租户

- **WHEN** 查询任意 TenantWorkspace
- **THEN** 记录包含 `tenant_id`，不能被其他租户的请求读取

### Requirement: Identity 定义与版本

每个 TenantWorkspace 可包含多个 IdentityDefinition；配置内容存放在不可变的 IdentityVersion 中。
版本状态至少包含 draft / published / archived。

#### Scenario: 创建草稿版本

- **WHEN** 在 IdentityDefinition 下创建 IdentityVersion
- **THEN** 版本为 draft，可修改绑定的 Skill/Tool 与模型配置

#### Scenario: 发布后不可变

- **WHEN** 对 published 版本尝试修改绑定
- **THEN** 请求被拒绝，必须创建新 draft 版本

#### Scenario: 运行可追溯版本

- **WHEN** 使用某 IdentityVersion 发起运行
- **THEN** Run 记录 `identity_version_id` 与资源快照

### Requirement: Identity 使用授权

仅 published 的 IdentityVersion 可授权给用户或用户组；授权决定员工端可见智能体。

#### Scenario: 授权已发布版本

- **WHEN** 为 published 版本创建 IdentityGrant
- **THEN** 被授权主体在 `/api/v1/me/identities` 中能看到该智能体

#### Scenario: 不可授权草稿

- **WHEN** 为 draft 版本创建 Grant
- **THEN** 返回 400 并说明仅 published 可授权

#### Scenario: 撤销后不可新建会话

- **WHEN** Grant 被删除或过期后用户创建新会话
- **THEN** 请求被拒绝

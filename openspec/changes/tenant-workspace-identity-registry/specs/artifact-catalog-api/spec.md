# artifact-catalog-api Specification

## ADDED Requirements

### Requirement: 产出物个人目录语义

Artifact 元数据按 owner 组织为可浏览目录：
`users/{owner_principal_id}/{identity}/{date}/{run_id}/{file}`。
员工 API 只能列出与读取本人目录树。

#### Scenario: 列出本人根目录

- **WHEN** `GET /api/v1/me/artifacts?path=/`
- **THEN** 仅返回当前 Principal 名下的顶层目录（通常为智能体名）

#### Scenario: 进入子目录

- **WHEN** `GET /api/v1/me/artifacts?path=/发展规划助手/2026-07-28`
- **THEN** 返回该路径下的 run 目录或文件，且均属于本人

#### Scenario: 他人产物不可见

- **WHEN** 用户 B 请求用户 A 的 artifact id 或构造 A 的路径
- **THEN** 返回 404，不泄露文件内容与精确存在性以外的信息

### Requirement: 下载与提权

本人可下载自己的产物；管理角色默认不能下载他人产物，显式提权必须带原因并产生审计事件。

#### Scenario: 本人下载

- **WHEN** owner 下载自己的 artifact
- **THEN** 校验通过并返回文件或短时下载凭证

#### Scenario: 无提权的管理读取被拒

- **WHEN** 管理角色未 elevate 直接下载他人 artifact
- **THEN** 请求失败

#### Scenario: 提权需原因

- **WHEN** 创建 artifact elevation 且 `reason` 为空
- **THEN** 返回 400

#### Scenario: 提权成功写审计

- **WHEN** 合法提权成功
- **THEN** 产生包含 actor、owner、reason、path_prefix 的审计事件

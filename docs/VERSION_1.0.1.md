# 版本 1.0.1 变更定义

状态：**目标已定稿**（原型 `1.0.1-r2` 冻结为实施目标）  
基线：`0.1.0`（工程验证版，127 tests passed）  
驱动：OpenSpec（见文末 Change 清单）

## 1. 版本定位

`1.0.1` 是 **从「可运行内核」到「可管理平台」的第一刀可实施切片**：

1. 产品目标以 `prototype/web`（r2）为准：管理控制台 + 用户工作台 + 角色视角 + 产出物目录树；
2. 实施顺序固定为：**先重构后端服务（平台模型 + 所有权隔离 + API 契约）**，再 **前后端分离落地 `web/`**；
3. 全程由 OpenSpec change 驱动，不在 change 外另写平行计划；
4. 保持 `SkillEngine` SDK/CLI 公开行为兼容（兼容层可保留，新能力走 `/api/v1`）。

## 2. 已冻结目标（原型 r2）

| 能力 | 目标行为 |
| --- | --- |
| 角色视角 | 平台/企业/空间/开发/运营/审计/员工；导航与写操作按角色收敛 |
| 创建智能体 | 五步向导：基本信息 → 模型 → 能力绑定 → 授权 → 发布检查 |
| 导入 Skill | 目录/上传/Registry + Schema/依赖校验清单 |
| 产出物目录 | `users/{owner}/智能体/日期/run/文件`；员工仅本人；管理默认锁定，提权需 reason + 审计 |
| 会话工作台 | 仅本人 Session/Run/产物；侧栏产物与目录树同一 ownership |

完整交互与文案见 [产品详细设计_1.0.1](../prototype/产品详细设计_1.0.1.md) 与 [权限架构设计](权限架构设计.md)。

## 3. 交付物

### 3.1 已完成（设计/原型）

| 交付 | 位置 |
| --- | --- |
| 迭代定义 | `docs/VERSION_1.0.1.md` |
| 架构 / 权限 / 技术实现 | `docs/架构文档_1.0.1.md`、`docs/权限架构设计.md`、`docs/技术实现文档_1.0.1.md` |
| 产品详设 | `prototype/产品详细设计_1.0.1.md` |
| HTML 原型 r2 | `prototype/web/` |
| 文档索引 | `docs/INDEX.md` |

### 3.2 待实施（OpenSpec）

| 顺序 | Change | 目标 |
| --- | --- | --- |
| 1 | `tenant-workspace-identity-registry` | 后端：领域模型、所有权字段、Principal 桩、`/api/v1`、隔离测试 |
| 2 | `frontend-backend-separation` | 前端：`web/` 工程，按 r2 原型对接只读管理 + 工作台 API |

## 4. 范围

### In Scope（1.0.1 实施）

**后端（Change 1）**

1. `Tenant` / `TenantWorkspace` / `WorkspaceBlueprint`（最小可用）
2. `IdentityDefinition` / `IdentityVersion` / `IdentityGrant`
3. RunContext 贯通 `tenant_id` / `tenant_workspace_id` / `owner_principal_id` / 资源快照
4. Session/Run/Artifact 所有权不可变与查询过滤
5. Artifact 逻辑路径与 `/api/v1/me/artifacts` 目录语义
6. 认证桩：可注入 Principal 的依赖（为真实 OIDC 预留）
7. 双用户越权自动化测试
8. **PostgreSQL**：平台注册表 + Session/Run/Trace（单库；预留 runtime 独立库配置）
9. 兼容：现有 CLI/`SkillEngine` 主路径不破坏

**前端（Change 2）**

1. 创建 `web/`，技术栈在 change design 内定案
2. 按 r2 实现管理端只读主路径 + 创建向导骨架 + 工作台 + 产物目录树
3. 开发期代理 engine API；OpenAPI 契约文件入库
4. `/ui` 兼容策略与文档更新

### Out of Scope

- 生产 OIDC 全量、PostgreSQL、KMS、队列/worker、对象存储多副本
- Prompt/Component/Knowledge 完整中心
- 多 Agent 编排、MCP
- 复刻任何真实厂商业务流程/人名

## 5. 验收标准（版本级）

1. OpenSpec 两个 change 的 tasks 全部勾选并通过 `openspec verify`；
2. 后端：A/B 双用户无法用对方 session/run/artifact ID 读到内容；
3. 后端：`/api/v1/me/*` 与管理 API 可被 Principal 中间件保护（桩级别也要有测试）；
4. 前端：`web/` 可本地启动，主路径与 r2 原型信息架构一致；
5. 回归：`engine` 下 pytest 基线不倒退（允许新增测试，不接受无关失败）；
6. 文档：`docs/INDEX.md` 与 change 设计中的决策一致。

## 6. 与 0.1.0 对比

| 维度 | 0.1.0 | 1.0.1 |
| --- | --- | --- |
| 定位 | 执行内核验证 | 平台第一刀（模型+API+前端骨架） |
| Identity | 简单绑定 | Definition/Version/Grant |
| 隔离 | user_id 可选 | Principal + owner 强制过滤 |
| 产物 | 本地文件 | 目录语义 + me API |
| 界面 | 内嵌 console | 独立 `web/`（由 change 2 落地） |

## 7. OpenSpec Change 清单（唯一计划源）

```text
openspec/changes/
  tenant-workspace-identity-registry/   # 先做：后端重构
    proposal.md
    design.md
    tasks.md
    specs/
      tenant-identity-registry/spec.md
      ownership-isolation/spec.md
      artifact-catalog-api/spec.md
  frontend-backend-separation/          # 后做：前后端分离（已更新依赖与目标）
    proposal.md
    design.md
    tasks.md
    specs/web-frontend/spec.md
```

实施时严格：`propose 完成 → apply 按 tasks 勾选 → verify → archive`，再进入下一个 change。

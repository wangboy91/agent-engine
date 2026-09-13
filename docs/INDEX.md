# 文档索引

> 更新于 1.0.1 迭代。根 README 仍是工程入口；本索引按「当前有效 / 历史追溯」分层，避免多份文档互相覆盖。

## 当前有效（以代码与本迭代为准）

| 文档 | 用途 |
| --- | --- |
| [../README.md](../README.md) | 项目定位、快速开始、API/CLI 入口 |
| [命令速查.md](命令速查.md) | **短命令**：`uv run ae` / pytest / web |
| [../AGENTS.md](../AGENTS.md) | 目录归位、开发命令、工作守则 |
| [VERSION_1.0.1.md](VERSION_1.0.1.md) | **本轮迭代定义**：范围、目标、验收、非目标 |
| [架构文档_1.0.1.md](架构文档_1.0.1.md) | 当前架构 + 目标平台架构（本迭代基线） |
| [权限架构设计.md](权限架构设计.md) | **SaaS 四维角色权限**：平台 / 开发 / 企业扩展 / 员工 |
| [技术实现文档_1.0.1.md](技术实现文档_1.0.1.md) | 领域模型、API、存储、隔离与实施任务拆解 |
| [../prototype/产品详细设计_1.0.1.md](../prototype/产品详细设计_1.0.1.md) | 产品功能、角色、页面与验收 |
| [../prototype/web/index.html](../prototype/web/index.html) | 管理控制台 + 用户工作台 HTML 原型 |
| [ADR_企业智能体租户与Workspace层级设计.md](ADR_企业智能体租户与Workspace层级设计.md) | Tenant / Workspace Blueprint / Identity 权威决策 |
| [架构总览与演进.md](架构总览与演进.md) | 0.1.0 内核分层与演进约束（仍有效） |
| [技术设计与生产化.md](技术设计与生产化.md) | 契约、模型、安全、部署要求（仍有效） |
| [当前能力评估与上线路线.md](当前能力评估与上线路线.md) | 成熟度矩阵与上线门槛 |
| [../openspec/WORKFLOW.md](../openspec/WORKFLOW.md) | 变更流程治理 |
| [../openspec/changes/tenant-workspace-identity-registry/](../openspec/changes/tenant-workspace-identity-registry/) | **1.0.1 Change1** 后端重构（先做） |
| [../openspec/changes/frontend-backend-separation/](../openspec/changes/frontend-backend-separation/) | **1.0.1 Change2** 前后端分离（后做） |

## 产品设计输入（prototype/）

| 文档 | 用途 |
| --- | --- |
| [../prototype/企业智能体平台功能拆解.md](../prototype/企业智能体平台功能拆解.md) | 功能域、角色、领域对象总表 |
| [../prototype/企业智能体Web管理端设计.md](../prototype/企业智能体Web管理端设计.md) | 管理端/工作台信息架构与隔离规则 |
| [../prototype/企业智能体_功能对齐与迭代路线.md](../prototype/企业智能体_功能对齐与迭代路线.md) | 与引擎对齐的 P0–P4 路线 |
| [../prototype/企业智能体平台现状对比与缺口.md](../prototype/企业智能体平台现状对比与缺口.md) | 现状 vs 缺口与优先级 |

## 历史 / 专题（保留追溯，不覆盖上述基线）

| 文档 | 说明 |
| --- | --- |
| Business_Agent_Base_Architecture.md | 长期业务智能体基座架构 |
| Business_Agent_Base_Roadmap.md | 基座路线图 |
| Agent_Runtime_Engineering.md | 运行时工程说明 |
| Workspace_Agent_Runtime_Roadmap.md | Workspace/Session 能力切片 |
| Skill_Engine_TECH_SPEC.md | Skill Engine 技术规格 |
| Skill_Run_Request_and_Routing.md | 运行请求与路由 |
| Runtime_Call_Graph.md | 调用图 |
| Memory_Knowledge_Cache_Design.md | 记忆/知识/缓存设计 |
| Core_Engine_Installation_Forms.md | 安装形态 |
| Project_Structure.md | 历史目录职责（部分路径已过时） |
| Usage_Guide.md | CLI/HTTP 补充 |
| Development_Checklist.md | 开发检查清单 |

## 原型截图

`prototype/screenshots/` 仅作产品形态参考（智能体/技能/工具/组件/提示词中心），不作为本引擎领域边界。

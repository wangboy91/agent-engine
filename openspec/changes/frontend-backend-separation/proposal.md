# Proposal: frontend-backend-separation

## Why

内核与界面变更频率不同。1.0.1 原型 r2 已定稿，但当前运行控制台仍是 `engine/app/interfaces/http/static/runtime-console.html` 内嵌单文件，界面迭代被绑死在 Python 包发布上。

**前置依赖：** `tenant-workspace-identity-registry` 必须先提供 `/api/v1` 契约与所有权隔离，否则前端只能继续堆 Mock，无法验收串线。

## What Changes

- 新增仓库一级目录 `web/`，承载管理控制台 + 用户工作台（对齐 `prototype/web` r2 信息架构与权限行为）。
- `engine/` 只保留 API 与内核；前端只消费公开 HTTP/SSE/WS，禁止 `import app`。
- 固化 OpenAPI 契约文件；开发期代理联调。
- 迁移期内保留 `/ui` 只读兼容；稳定后移除内嵌 runtime-console。

## Impact

- 新增：`web/`
- 受影响：`engine/app/interfaces/http/`（静态资源策略）、根 `README.md`、`AGENTS.md`
- 依赖 change：`tenant-workspace-identity-registry`（API + 隔离）
- 不改变：`SkillEngine` SDK/CLI 语义

## Non-goals

- 不在本 change 重写内核运行时
- 不做生产级前端 SSR/微服务
- 不实现 r2 之外的完整资源中心页面（Prompt/Component/Knowledge 等）

## 验收映射

以 `prototype/web` r2 为视觉与交互基线：角色视角、创建向导、产出物目录树、`/me` 隔离行为。

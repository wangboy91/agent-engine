# Design: frontend-backend-separation

状态:**已立项,未开始实施**。以下为设计方向与待定决策,实施前需逐项定案。

## 1. 边界原则

- 内核(`engine/`):Skill/Tool 运行时、模型网关、存储、治理。只暴露 HTTP API
  (REST + SSE/WebSocket),契约稳定、版本化。
- 前端(`web/`):全部界面。只通过公开 API 与内核通信,禁止 `import bkl_engine`。

## 2. 待定决策(实施前必须定案)

| # | 决策点 | 选项 | 备注 |
| --- | --- | --- | --- |
| D1 | 前端技术栈 | Vite + 原生 TS / React / Vue | 现有控制台是零依赖单文件 HTML,迁移成本最低的是轻量方案 |
| D2 | 开发期联调 | Vite devServer 代理 → engine API / CORS 直连 | 代理方案不需要内核开 CORS |
| D3 | 生产期托管 | engine FastAPI 托管 `web/dist` 静态产物 / 前端独立部署 | 前者部署简单,后者彻底解耦 |
| D4 | API 契约管理 | OpenAPI schema 导出为契约文件,前端据此生成客户端 | FastAPI 已有 schema,需固化版本策略 |
| D5 | SSE/WebSocket 通道 | 现有事件流 API 直接复用 / 抽象统一事件协议 | 影响前端状态管理选型 |

## 3. 迁移策略

1. 冻结内嵌控制台功能(不再新增能力)。
2. `web/` 项目重建现有控制台的全部只读能力(run/trace/artifact 查看等)。
3. 切换默认入口,`/ui` 指向新前端。
4. 移除 `engine/bkl_engine/interfaces/http/static/runtime-console.html` 及其挂载逻辑。

## 4. 风险

- 现有控制台与 API 的隐式耦合(字段、错误格式)在迁移中暴露 → 迁移前先以
  OpenAPI schema 对齐契约。
- 双入口并存期的路由/端口冲突 → 以 D2 定案的联调方式规避。

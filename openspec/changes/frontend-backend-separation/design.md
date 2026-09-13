# Design: frontend-backend-separation

状态：**已更新（1.0.1 定稿后）**  
依赖：`tenant-workspace-identity-registry` 完成 `/api/v1` 与隔离测试  
交互基线：`prototype/web`（1.0.1-r2）

## 1. 边界原则

- `engine/`：Skill/Tool 运行时、模型网关、存储、治理 API。契约版本化。
- `web/`：全部界面。只通过公开 API 通信，禁止 `import app`。

## 2. 已定案决策（原 D1–D5）

| # | 决策点 | 结论 | 理由 |
| --- | --- | --- | --- |
| D1 | 前端技术栈 | **Vite + React + TypeScript** | 与 r2 组件树（侧栏/表格/向导/目录树）匹配；生态成熟；后续可接组件库 |
| D2 | 开发期联调 | **Vite devServer proxy → engine API** | 不必先开危险 CORS；本地 `engine` serve + `web` dev 双端口 |
| D3 | 生产期托管 | **先 engine 托管 `web/dist`（静态挂载）** | 1.0.1 单机部署简单；独立部署留到后续 |
| D4 | API 契约管理 | **OpenAPI schema 导出为 `web/openapi.json`（或 `docs/api/openapi.json`）入库** | 前端可生成类型；CI 可 diff |
| D5 | 事件通道 | **复用现有 SSE/WS，先不做统一事件总线** | 降低 r2 范围；cursor 恢复可后置 |

## 3. 信息架构（对齐 r2）

```text
web/src
  app/                 # 路由、布局、角色上下文
  pages/console/       # 总览、智能体、创建向导、Skill、工具、Run、产物、审批、审计、设置
  pages/workbench/     # 我的智能体、会话、任务、产出物、记忆
  features/artifacts/  # 目录树、预览、提权申请
  features/identity/   # 向导步骤、绑定与授权
  api/                 # openapi 生成类型 + fetch 封装
  mock/                # 开发期可切换的 r2 mock（后端未就绪时）
```

路由前缀建议：

- 管理：`/console/*`
- 工作台：`/app/*`
- 开发调试：engine 仍可提供 `/ui` 旧入口直至 archive 本 change

## 4. 权限在前端的表达

前端**不做**真实鉴权，只做体验层：

1. 由登录后的 Principal 显示角色（或 dev 角色切换器，默认关闭于生产构建）；
2. 隐藏无权限入口；真正拒绝以 HTTP 401/403/404 为准；
3. 产物目录锁定节点点击后走 elevate API，不得本地“假装可看”；
4. query cache key 包含 tenant/workspace/principal，切换作用域清空。

## 5. 迁移策略

1. **Phase A**：后端 change 合并后，`web/` 用 mock + 真实 `/api/v1` 混合开发主路径；
2. **Phase B**：实现管理只读（总览/智能体列表/Run/产物元数据）+ 工作台 `/me`；
3. **Phase C**：创建向导与发布/授权写路径；审批流；
4. **Phase D**：`/ui` 切换到 `web/dist`；内嵌 console 只读；
5. **Phase E**：删除内嵌 `runtime-console.html` 与挂载逻辑。

## 6. 组件与视觉

- 视觉 token 直接继承 `prototype/web/styles.css`（主色 `#2563EB`、密度与表格规范）。
- 不引入重装饰；convention mode 管理台。
- 图标统一线性 SVG；状态必须文字+颜色。

## 7. 测试与验收

| 层级 | 内容 |
| --- | --- |
| 契约 | openapi.json 与 engine `/openapi.json` diff 检查 |
| 组件 | 关键页 smoke（渲染、导航、角色隐藏） |
| 联调 | 本地 engine + web：me 会话、产物树、A/B 串线手工/ e2e |
| 构建 | `web` build 成功；engine 能托管 dist |

## 8. 风险

- 后端契约未稳就写前端 → **门禁：依赖 change tasks 勾选完成**
- 双入口端口混淆 → README 写清 `engine:8000` + `web:5173`
- Mock 与真实字段漂移 → 以 openapi 类型为准，mock 走同一类型

## 9. 与原型目录关系

`prototype/web` 为**设计冻结稿**，不再大改；`web/` 为可运行工程实现。  
实现时允许组件化重构，但不得改变 r2 的权限语义与目录树行为。

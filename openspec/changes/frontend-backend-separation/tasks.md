# Tasks: frontend-backend-separation

状态：**apply 进行中**（`web/` 已创建并通过 typecheck/build）。  
按 WORKFLOW：逐条勾选。

## 0. 前置门禁

- [x] 确认 `tenant-workspace-identity-registry` 核心 `/api/v1` me/artifacts/identities 可用
- [x] 从 engine 导出 OpenAPI → `docs/api/openapi.json`（52 paths）

## 1. 契约

- [x] 契约文件入库 `docs/api/openapi.json`
- [ ] openapi-typescript 生成前端类型（当前手写 DTO，可后续接入）
- [ ] 契约 diff 检查脚本

## 2. 前端工程初始化

- [x] 创建 `web/`（Vite + React + TS + react-router）
- [x] 配置 dev proxy → `http://127.0.0.1:8000`
- [x] 抽取 r2 CSS token 与布局壳（顶栏/侧栏/主区）
- [x] 更新根 `README.md`、`AGENTS.md`：新增 `web/` 归位与启动命令

## 3. 只读主路径（对齐 r2）

- [x] 管理总览（租户数、审计摘要）
- [x] 智能体列表 + 详情（Definition/Version/发布/Grant）
- [x] Skill 列表（legacy /skills）
- [x] Run 列表（/api/v1/me/runs）
- [x] 产出物目录树：/api/v1/me/artifacts + 管理元数据
- [x] 审批队列（legacy waiting_approval + resume）

## 4. 写路径与向导

- [x] 创建 Definition + Version + 发布 + Grant（详情页）
- [ ] 完整五步向导 UI（r2 全量）
- [ ] 导入 Skill 表单
- [x] 产物 elevate 申请（reason 必填）

## 5. 用户工作台

- [x] 我的智能体卡片 + 开始会话
- [x] 会话页（列表 + 消息 + 发送到 /chat/messages）
- [x] 我的产出物（复用目录树，仅本人）
- [ ] 我的记忆（API 未就绪，占位）

## 6. 角色与安全体验

- [x] Principal 角色展示 + dev 角色切换器（DEV_ROLE_SWITCHER）
- [x] 无权限入口隐藏（canCreateAgent/canPublish/canApprove）
- [x] 切换 tenant 时 toast 提示清缓存
- [ ] 401/403 统一错误组件样式增强

## 7. 托管与切换

- [x] `npm run build` 成功（web/dist）
- [ ] engine 静态挂载 web/dist
- [ ] `/ui` 切换到新前端
- [ ] 移除内嵌 runtime-console

## 8. 收尾

- [x] typecheck / build 通过
- [ ] 与 r2 对照清单人工签字
- [ ] `openspec verify` → archive

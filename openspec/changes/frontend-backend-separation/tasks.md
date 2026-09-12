# Tasks: frontend-backend-separation

状态:已立项,未开始。按 WORKFLOW.md,实施时逐条完成并打勾。

## 1. 契约对齐

- [ ] 导出当前 FastAPI OpenAPI schema,固化 API 契约文件与版本策略(决策 D4)
- [ ] 梳理内嵌控制台实际使用的全部 API 端点与 SSE/WebSocket 事件,形成清单

## 2. 前端项目初始化

- [ ] 定案技术栈与联调/托管方式(决策 D1/D2/D3),结论回写 design.md
- [ ] 创建 `web/` 项目骨架,配置对 engine API 的开发期联调
- [ ] 更根 `README.md` 与 `AGENTS.md` 的目录归位规则(新增 `web/`)

## 3. 控制台迁移

- [ ] 在 `web/` 中重建现有运行控制台能力(run/trace/artifact 查看)
- [ ] `/ui` 默认入口切换到新前端,内嵌控制台转只读兼容
- [ ] 补齐前端构建与联调的测试/冒烟命令

## 4. 收尾

- [ ] 移除 `engine/bkl_engine/interfaces/http/static/runtime-console.html` 及挂载逻辑
- [ ] openspec verify -> archive

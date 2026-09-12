# Proposal: frontend-backend-separation

## Why

内核与界面的变更频率不同:`bkl_engine`(Skill 运行时内核)趋于稳定,而 Web
管理端/运行控制台会频繁迭代。当前运行控制台以内嵌静态文件形式存在于
`engine/bkl_engine/interfaces/http/static/runtime-console.html`,界面任何改动都要
改 Python 包并重新构建发布,两边的迭代节奏被绑死。

仓库目录已完成分类(`engine/` 自成项目根),需要补上对应的前端位置与边界约定。

## What Changes

- 新增 `web/` 前端项目(仓库根一级目录),承接现有内嵌运行控制台的全部界面能力,
  后续管理控制台/用户工作台界面都在此迭代。
- `engine/` 只保留 API 与内核职责:FastAPI 作为纯 API 服务,静态资源服务策略
  (开发期代理 / 生产期是否由引擎托管构建产物)在设计阶段定案。
- 内嵌 `runtime-console.html` 迁出 `bkl_engine`,由 `web/` 项目替代;
  迁移期内保留只读兼容入口,迁移完成后移除。
- 明确内核/界面的 API 契约边界:界面只依赖公开 HTTP API(含 SSE/WebSocket),
  不得 import `bkl_engine`,不得依赖内核内部模块。

## Impact

- 受影响代码:`engine/bkl_engine/interfaces/http/`(静态资源挂载、控制台路由)
- 新增目录:`web/`
- 文档:`docs/`、根 `README.md`、`AGENTS.md` 归位规则补充 `web/`
- 不改变 `SkillEngine` SDK/CLI 公开行为;API 路由保持兼容

## Non-goals

- 不重写内核任何运行时逻辑
- 不在本变更内实现新界面功能(仅迁移现有控制台能力)
- 不引入服务端渲染框架;前端技术选型在 design 阶段确定

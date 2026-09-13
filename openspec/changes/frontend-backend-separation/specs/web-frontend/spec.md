# web-frontend Specification

## ADDED Requirements

### Requirement: 前端独立项目目录

`web/` 是仓库一级目录，承载全部界面代码；`engine/` 不包含界面实现，仅提供公开 HTTP API。

#### Scenario: 界面改动不触碰内核

- **WHEN** 修改任意界面功能
- **THEN** 变更只发生在 `web/` 目录内
- **AND** `engine/app` 无代码改动

#### Scenario: 前端不依赖内核内部模块

- **WHEN** 构建 `web/` 项目
- **THEN** 不存在对 `app` 的任何 import 或构建依赖

### Requirement: 内核只暴露 API 契约

`engine/` 的 FastAPI 以 OpenAPI schema 作为与前端之间的稳定契约；界面能力仅通过公开 REST/SSE/WebSocket 获得。

#### Scenario: 契约文件可追溯

- **WHEN** API 契约发生变化
- **THEN** OpenAPI 契约文件同步更新，并可在仓库中追溯版本差异

### Requirement: 对齐 1.0.1 原型 r2 的信息架构与权限语义

前端必须实现管理控制台与用户工作台主路径，并保持与原型一致的权限行为：角色收敛导航、`/me` 数据、产出物个人目录树。

#### Scenario: 员工只见本人产出物

- **WHEN** 以最终用户身份打开产出物目录
- **THEN** 仅能浏览本人目录树，无法打开他人节点

#### Scenario: 管理读取他人产物需提权

- **WHEN** 管理角色打开他人 owner 目录
- **THEN** 界面呈现锁定/提权入口，且必须调用带 reason 的提权 API，而非本地直接展示内容

#### Scenario: 无权限入口不可用

- **WHEN** 当前角色缺少某写操作权限
- **THEN** 对应创建/发布入口隐藏或禁用，且后端仍会拒绝越权请求

### Requirement: 开发与生产托管

开发期通过代理访问 engine API；生产期由 engine 托管 `web/dist`（1.0.1）。

#### Scenario: 本地联调

- **WHEN** 启动 engine 与 web dev server
- **THEN** 浏览器请求经代理到达 engine，无需前端直连内网 CORS

#### Scenario: 生产静态托管

- **WHEN** 执行 web 生产构建并由 engine 挂载 dist
- **THEN** 访问管理端/工作台路由可加载静态资源与 API

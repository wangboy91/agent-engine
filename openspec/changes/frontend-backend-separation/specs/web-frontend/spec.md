# web-frontend Specification

## ADDED Requirements

### Requirement: 前端独立项目目录

`web/` 是仓库一级目录,承载全部界面代码;`engine/` 不包含界面实现,
仅提供公开 HTTP API。

#### Scenario: 界面改动不触碰内核

- **WHEN** 修改任意界面功能
- **THEN** 变更只发生在 `web/` 目录内
- **AND** `engine/bkl_engine` 无代码改动

#### Scenario: 前端不依赖内核内部模块

- **WHEN** 构建 `web/` 项目
- **THEN** 不存在对 `bkl_engine` 的任何 import 或构建依赖

### Requirement: 内核只暴露 API 契约

`engine/` 的 FastAPI 以 OpenAPI schema 作为与前端之间的稳定契约;
界面能力仅通过公开 REST/SSE/WebSocket 端点获得。

#### Scenario: 契约文件可追溯

- **WHEN** API 契约发生变化
- **THEN** OpenAPI 契约文件同步更新,并可在仓库中追溯版本差异

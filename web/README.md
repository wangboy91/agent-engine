# Agent Engine Web（1.0.1）

管理控制台 + 用户工作台。只调用 engine 公开 HTTP API，禁止 `import app`。

## 开发

```bash
# 1) 启动引擎 API（engine/ 目录）
cd engine
uv run ae serve --host 127.0.0.1 --port 8050 --config agent.yaml

# 2) 启动前端
cd web
npm install
npm run dev
# http://127.0.0.1:5001
```

开发代理见 `vite.config.ts`（`/api` → `127.0.0.1:8050`）。

## Principal（开发鉴权桩）

顶栏可切换演示角色；请求自动附加：

- `X-Tenant-Id`
- `X-Principal-Id`
- `X-Workspace-Roles`
- `X-Group-Ids`

生产构建将剥离角色切换器（见 `src/config.ts`）。

## 契约

OpenAPI 导出：`docs/api/openapi.json`。

## 生产构建

```bash
npm run build
# 产物 web/dist；可由 engine 静态托管（Change2 后期任务）
```

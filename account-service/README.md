# Account Service（独立账号权限服务）

与 **智能体基座（engine）** 分离：本服务只管登录、用户主数据、角色与账号映射；  
基座只消费 `Principal`（Bearer token / 网关头）并做 Grant / Run 隔离。

## 职责

| 有 | 无 |
| --- | --- |
| 登录、改密、用户列表 | Skill / Run / 产物 |
| 哈希密码（PBKDF2） | 智能体授权（IdentityGrant 在基座） |
| 角色 / 用户组字段 | 业务菜单权限 |
| `identity_links` 账号映射表 | 组织树权威源（可后续扩展） |

## 启动

```bash
cd account-service
uv sync --extra dev

# 建表并写入演示账号（哈希入库）
uv run python -m app.interfaces.scripts.seed_users

# 启动（默认 8001）
uv run account-service
```

目录（DDD 硬约束）：

```text
app/domain/           实体、密码策略、错误
app/application/      AuthService 用例 + Ports
app/infrastructure/   SQLAlchemy、HMAC token、config
app/interfaces/       HTTP 路由、seed 脚本
tests/                分层测试（禁止 application→infrastructure）
```

环境变量：

```text
ACCOUNT_DATABASE_URL=postgresql+psycopg://postgres:postgres123@192.168.0.104:55432/agent_engine
ACCOUNT_TOKEN_SECRET=agent-engine-1.0.1-demo
```

未设置时自动读取仓库根或本目录 `.env` 中同名变量。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/login` | `{username,password}` → `{access_token, principal, profile}` |
| POST | `/auth/change-password` | 改密（旧密码校验，新密码哈希入库） |
| GET | `/auth/me` | Bearer → Principal |
| GET | `/auth/users` | 用户列表（无密码字段） |
| POST | `/auth/users` | 创建用户（仅演示/运维） |
| GET | `/health` | 健康检查 |
| GET | `/openapi.json` | 契约 |

## 与基座、Web 的关系

```text
Web (:5001)
  ├─ 登录/用户 → Account Service (:8051)
  └─ 智能体/Run/产物 → Engine API (:8050)

Engine 校验 Authorization: Bearer（与本服务共用 token 签名密钥）
后期可用网关合并为同一域名：/account/* 与 /engine/*
```

## 部署说明

- 独立进程/容器；数据库表 `auth_users`、`identity_links`
- 生产应换 OIDC/JWT 验签，本服务可收缩为运维账号或映射服务
- 基座不要依赖本服务内部表结构，只依赖 token claims / Principal

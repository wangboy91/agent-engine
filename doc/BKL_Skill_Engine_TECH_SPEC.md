# BKL Skill Engine 技术需求文档

版本：v0.1  
技术栈：Python  
目标：先实现一个独立可复用的 Skill Engine，后续所有本地版、云端 SaaS、私有部署和垂直智能体产品都复用该引擎。  
开发方式：使用 Codex 按任务拆分逐步实现。

---

## 1. 项目定位

本项目不是先做“爆款实验室 SaaS”，也不是先做“本地口播视频软件”。

本项目第一阶段只做一个独立的、可复用的、可本地运行、可云端部署的 Python Skill Engine。

后续这些产品都可以复用它：

```text
爆款实验室 SaaS
本地 AI 口播视频软件
AI 穿搭顾问「许知衣」
王不懂的小实验内容生成器
小红书爆款笔记工具
本地生活探店内容工具
企业私有化 AI 内容工作台
```

这些项目表面不同，但底层都是同一个模式：

```text
用户输入
  ↓
调用某个 Skill
  ↓
Skill 调用 Tools
  ↓
返回结构化结果 / 文件产物 / Trace
```

---

## 2. 项目一句话

```text
所有业务流程放在 Skill 中，所有可执行动作沉淀成 Tool，Skill Engine 只负责让大模型在受控边界内调用工具并产出结构化结果。
```

---

## 3. 核心设计理念

本项目采用三层结构：

```text
Agent = 对外售卖的智能体产品包装
Skill = 业务能力与编排逻辑
Tool = 最小可执行能力
```

示例：

```text
AI口播视频智能体 Agent
  └── 口播视频生成 Skill
        ├── 脚本生成 Tool
        ├── 标题生成 Tool
        ├── 火山 TTS API Tool
        ├── 数字人 API Tool
        ├── 字幕 Python Tool
        └── FFmpeg 合成 Python Tool
```

核心原则：

1. 所有业务编排都放在 Skill 中。
2. Tool 只负责执行明确动作，不理解业务。
3. Skill 可以调用 API Tool、Python Tool、LLM Tool，也可以调用其他 Skill。
4. Engine 不关心具体业务，只负责运行 Skill。
5. Engine 必须提供工具注册、权限控制、Schema 校验、日志追踪、成本统计和产物管理。
6. 第一版不做复杂 Workflow，不做流程图，不做多 Agent 协作。
7. 后续所有项目通过微服务 API 或 Python SDK 复用该 Engine。

### 3.1 两种执行能力

BKL 必须同时支持两种执行模式：

```text
Direct Skill Execution
  调用方明确传入 skill_id + input JSON
  适合 API、CLI、自动化任务和稳定生产集成。

Agent-Orchestrated Execution
  用户提供自然语言或 scene_id
  Agent 负责识别意图、选择 Skill、补齐参数、要求确认、调用 SkillEngine。
```

这两种模式不能分裂成两套系统。Agent 是 `SkillEngine` 外面的一层受控编排，不是新的业务运行时。

详细设计见 [BKL Agent Runtime Engineering Plan](BKL_Agent_Runtime_Engineering.md)。

---

## 4. 系统边界

### 4.1 Engine 应该做

```text
执行 Skill
调用 Tool
管理 Tool Schema
管理 Skill Schema
调用大模型
记录 Trace
保存 Artifact
控制权限
记录成本
返回结构化结果
提供 REST API
提供 Python SDK
提供 CLI
```

### 4.2 Engine 不应该做

```text
用户登录注册
套餐订阅
积分充值
前端页面
具体业务表单
业务运营后台
内容社区
账号矩阵管理
本地桌面 UI
SaaS 营销站
```

这些属于 Product 层。

---

## 5. 整体微服务架构

```text
┌──────────────────────────────────────┐
│              Product Apps             │
│ 爆款实验室 / 本地软件 / 私有部署 / 其他项目 │
└───────────────────┬──────────────────┘
                    │
                    │ REST / SDK / gRPC
                    ▼
┌──────────────────────────────────────┐
│          BKL Skill Engine API         │
│       统一 Skill 执行入口              │
└───────────────────┬──────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
 Skill Runtime   Tool Runtime   Model Router
        │           │           │
        ▼           ▼           ▼
 Skill Registry  Tool Registry  OpenRouter / 火山 / OpenAI
        │           │
        ▼           ▼
 Trace Store   Artifact Store
        │           │
        ▼           ▼
 PostgreSQL    S3 / R2 / MinIO / Local FS
```

---

## 6. 部署形态

### 6.1 云端 SaaS 模式

```text
爆款实验室 Web UI
  ↓
调用 BKL Skill Engine 云服务
  ↓
使用平台模型 Key
  ↓
按积分扣费
  ↓
产物保存在云端
```

适合普通用户。

### 6.2 本地模式

```text
本地桌面 UI
  ↓
调用本机 BKL Skill Engine
  ↓
使用用户自己的 OpenRouter / 火山 Key
  ↓
产物保存在本地
```

适合高级用户、工作室、企业客户。

### 6.3 私有部署模式

```text
客户自己的服务器
  ↓
部署 BKL Skill Engine
  ↓
接客户自己的模型 / API / 素材库
  ↓
内部员工使用
```

适合企业客户、MCN、代运营团队。

---

## 7. 调用方式

Engine 需要同时支持两种调用方式。

### 7.1 作为微服务调用

适合 SaaS、私有部署、多项目共享。

```http
POST http://engine:8000/skills/talking-video/runs
```

### 7.2 作为 Python SDK 嵌入

适合本地版、CLI、测试。

```python
from bkl_engine import SkillEngine

engine = SkillEngine.load("./config")

result = await engine.run_skill(
    "talking-video",
    {
        "topic": "适合程序员的护眼台灯",
        "platform": "xiaohongshu"
    }
)
```

---

## 8. 技术栈

### 8.1 后端核心

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2.x
Alembic
SQLite / PostgreSQL
httpx
PyYAML
jsonschema
Typer
Rich
pytest
ruff
mypy
```

### 8.2 模型调用

第一版支持：

```text
OpenAI-compatible API
OpenRouter-compatible API
火山 / 豆包预留 Adapter
```

### 8.3 Tool 执行

第一版支持：

```text
API Tool
Python Tool
LLM Tool
Skill Tool
System Tool
```

Python Tool 推荐第一版先支持 subprocess 本地执行，生产环境切换 Docker 沙箱。

### 8.4 存储

本地开发：

```text
SQLite
本地文件目录
```

SaaS / 私有部署：

```text
PostgreSQL
S3 / R2 / MinIO
Redis / Queue
```

第一版可以不引入 Redis，先做同步执行和本地任务记录。

---

## 9. 核心模块

### 9.1 Skill Registry

负责 Skill 的注册、加载、校验和版本管理。

功能：

```text
加载 Skill
校验 SKILL.md frontmatter
校验 bkl.skill.json
校验 input_schema
校验 output_schema
管理 Skill 版本
启用 / 禁用 Skill
查询 Skill 可用工具
将 Skill 暴露为 Tool
```

---

### 9.2 Tool Registry

负责管理所有基础工具。

Tool 类型：

```text
api
python
llm
skill
system
```

功能：

```text
注册 Tool
校验 Tool Schema
生成 Tool 描述
按 Skill 过滤可用 Tool
测试 Tool
启用 / 禁用 Tool
版本管理
```

---

### 9.3 OpenAPI Tool Importer

负责把 `swagger.json` 或 `openapi.yaml` 注册成 API Tool。

功能：

```text
上传 openapi.json / openapi.yaml
解析 paths / methods / operationId
生成 tool_id
生成 input_schema
生成 output_schema
配置 base_url
配置 auth
测试调用
保存 Tool
```

要求：

1. 导入后不应该直接全量暴露给 Skill。
2. 由 Skill 显式声明 allowed_tools。
3. 自动生成的 Tool 描述需要允许人工编辑。
4. Secret 不允许进入 Prompt 和 Trace。

---

### 9.4 Python Tool Runner

负责执行标准 Python 工具。

功能：

```text
读取 tool.yaml
校验 input_schema
创建运行环境
执行 main.py
通过 stdin 传入 JSON
通过 stdout 读取 JSON
校验 output_schema
保存 artifacts
记录日志
```

第一版执行方式：

```text
subprocess 本地执行
```

P1 版本执行方式：

```text
Docker 沙箱执行
```

生产环境必须使用沙箱。

---

### 9.5 Skill Runtime

这是系统核心。

功能：

```text
加载 Skill prompt
加载 Skill allowed_tools
构造 LLM messages
执行 tool calling loop
校验每次 tool call
执行 Tool
返回 observation
继续推理
生成 final output
校验 output_schema
记录 trace
记录 cost
记录 artifact
```

---

### 9.6 Model Router

负责统一模型调用。

模型 Profile：

```text
fast
strong
cheap
json
vision
```

示例配置：

```yaml
profiles:
  fast:
    provider: openrouter
    model: openai/gpt-4.1-mini

  strong:
    provider: openrouter
    model: anthropic/claude-sonnet-4.5

  cheap:
    provider: volcengine
    model: doubao-lite

  json:
    provider: openrouter
    model: openai/gpt-4.1-mini
    response_format: json
```

Skill 只声明：

```yaml
model:
  profile: strong
```

不要让 Skill 直接写死具体 Provider。

---

### 9.7 Artifact Store

负责保存所有产物。

产物类型：

```text
text
json
image
audio
video
subtitle
zip
log
```

本地版保存到：

```text
./data/artifacts
```

SaaS 版保存到：

```text
S3 / R2 / MinIO
```

---

### 9.8 Trace Store

负责记录每次 Skill 执行过程。

必须记录：

```text
Skill 输入
LLM 请求
LLM 响应
Tool 调用
Tool 输入
Tool 输出
Tool 错误
Final Output
Token
Cost
耗时
重试次数
产物位置
```

---

### 9.9 Policy Engine

负责安全和成本控制。

控制内容：

```text
Skill 允许调用哪些 Tool
Tool 能不能联网
Tool 能访问哪些文件
Tool 能不能读取 Secret
最大工具调用次数
最大 token
最大积分
最大运行时间
最大输出文件大小
```

---

## 10. 对外 API 设计

第一版只需要暴露少量核心 API。

### 10.1 Tool API

```http
POST   /tools/register
POST   /tools/import-openapi
GET    /tools
GET    /tools/{tool_id}
POST   /tools/{tool_id}/test
PATCH  /tools/{tool_id}
DELETE /tools/{tool_id}
```

### 10.2 Skill API

```http
POST   /skills/register
GET    /skills
GET    /skills/{skill_id}
POST   /skills/{skill_id}/runs
PATCH  /skills/{skill_id}
DELETE /skills/{skill_id}
```

### 10.3 Run API

```http
GET    /runs
GET    /runs/{run_id}
GET    /runs/{run_id}/trace
GET    /runs/{run_id}/artifacts
```

### 10.4 Artifact API

```http
GET    /artifacts/{artifact_id}
```

---

## 11. 运行 Skill 请求示例

```http
POST /skills/talking-video/runs
```

请求：

```json
{
  "input": {
    "topic": "适合程序员的护眼台灯",
    "platform": "xiaohongshu",
    "duration_seconds": 60
  },
  "context": {
    "project_id": "bkl_lab",
    "user_id": "user_001"
  }
}
```

返回：

```json
{
  "run_id": "run_123",
  "status": "succeeded",
  "output": {
    "script": "完整口播脚本",
    "titles": ["标题1", "标题2", "标题3"],
    "audio_artifact_id": "artifact_audio_001",
    "video_artifact_id": "artifact_video_001"
  }
}
```

---

## 12. 数据模型

### 12.1 Skill

```python
class Skill(BaseModel):
    id: str
    name: str
    version: str
    description: str
    input_schema: dict
    output_schema: dict
    prompt: str
    allowed_tools: list[str]
    model_profile: str
    limits: SkillLimits
    enabled: bool = True
```

---

### 12.2 Tool

```python
class Tool(BaseModel):
    id: str
    name: str
    type: Literal["api", "python", "llm", "skill", "system"]
    description: str
    input_schema: dict
    output_schema: dict
    config: dict
    permissions: dict
    enabled: bool = True
```

---

### 12.3 SkillRun

```python
class SkillRun(BaseModel):
    id: str
    skill_id: str
    user_id: str | None = None
    status: Literal["pending", "running", "succeeded", "failed"]
    input: dict
    output: dict | None = None
    error: dict | None = None
    cost: float = 0
    tokens: int = 0
    created_at: datetime
    completed_at: datetime | None = None
```

---

### 12.4 ToolCall

```python
class ToolCall(BaseModel):
    id: str
    run_id: str
    tool_id: str
    status: Literal["pending", "running", "succeeded", "failed"]
    input: dict
    output: dict | None = None
    error: dict | None = None
    started_at: datetime
    completed_at: datetime | None = None
    cost: float = 0
    artifacts: list[str] = []
```

---

### 12.5 Artifact

```python
class Artifact(BaseModel):
    id: str
    run_id: str
    tool_call_id: str | None = None
    type: Literal["text", "json", "image", "audio", "video", "subtitle", "zip", "log"]
    mime_type: str
    uri: str
    metadata: dict = {}
    created_at: datetime
```

---

## 13. 数据库表

第一版需要这些表：

```text
skills
tools
skill_versions
tool_versions
skill_runs
tool_calls
artifacts
trace_events
provider_credentials
usage_records
```

第一版不需要：

```text
workflows
run_steps
```

因为本项目不做复杂 Workflow，执行过程由 Skill 内部通过 Tool Call 完成。

---

## 14. Skill 包格式

Skill 目录结构：

```text
skills/
  talking-video/
    SKILL.md
    bkl.skill.json
    input.schema.json
    output.schema.json
    examples.json
```

第一版采用行业通用 Skill 形态：每个 Skill 包必须包含标准 `SKILL.md`，并通过 BKL 专用的 `bkl.skill.json` 描述运行时配置。

`SKILL.md` 由两部分组成：

```text
YAML frontmatter
Markdown instructions
```

通用标准字段：

```text
name
description
```

`SKILL.md` 不允许写入 BKL Engine 私有运行时字段。schema、tools、model、limits 等引擎配置统一放在同目录的 `bkl.skill.json`，避免污染标准 Skill 元数据和 Markdown instructions。

### 14.1 SKILL.md 示例

```md
---
name: talking-video
description: Use when generating a structured talking-video draft from a topic, platform, persona, and product information.
---

你是一个“AI口播视频生成 Skill”。

你的目标是根据用户输入，完成一条适合短视频平台的口播视频生产。

你必须遵守以下原则：

1. 先理解用户输入的主题、平台、受众、时长和风格。
2. 如果缺少必要信息，可以根据平台默认值补全，不要反复追问。
3. 优先生成脚本，再生成标题，再生成语音，最后生成视频和字幕。
4. 每次调用工具前，确保输入符合工具 schema。
5. 不允许调用未授权工具。
6. 最终必须输出符合 output_schema 的 JSON。

你可以使用以下工具：

{{tools}}

用户输入：

{{input}}
```

### 14.2 bkl.skill.json 示例

```json
{
  "id": "talking-video",
  "version": "0.1.0",
  "input_schema": "input.schema.json",
  "output_schema": "output.schema.json",
  "model": {
    "profile": "strong",
    "fallback_profile": "fast"
  },
  "tools": {
    "allow": [
      "script_writer",
      "title_generator",
      "volc_tts_generate_audio",
      "avatar_video_create",
      "subtitle_generate_srt",
      "ffmpeg_merge_video",
      "viral_score_evaluate"
    ]
  },
  "limits": {
    "max_iterations": 8,
    "max_tool_calls": 12,
    "max_tokens": 12000,
    "timeout_seconds": 600,
    "max_credits": 100
  },
  "permissions": {
    "network": true,
    "filesystem": "workspace_only",
    "secrets": [
      "VOLCENGINE_API_KEY",
      "AVATAR_API_KEY"
    ]
  },
  "final_output": {
    "required": true,
    "format": "json"
  }
}
```

### 14.3 格式约束

第一版只支持这一套 Skill 包规范：标准 `SKILL.md` + BKL `bkl.skill.json`。旧式 `skill.yaml + prompt.md` 不兼容，避免项目同时存在两套 Skill 规范。

---

## 15. Python Tool 包格式

Python Tool 目录结构：

```text
tools/
  subtitle_generate_srt/
    tool.yaml
    input.schema.json
    output.schema.json
    main.py
    requirements.txt
```

### 15.1 tool.yaml 示例

```yaml
id: subtitle_generate_srt
type: python
name: 生成字幕文件
description: 根据音频和口播文案生成 SRT 字幕
entry: main.py
input_schema: input.schema.json
output_schema: output.schema.json

runtime:
  timeout_seconds: 120
  memory_mb: 512
  network: false
  filesystem:
    read:
      - workspace
    write:
      - artifacts
```

### 15.2 main.py 规范

```python
import json
import sys


def run(input_data: dict) -> dict:
    text = input_data["text"]
    audio_path = input_data["audio_path"]

    return {
        "srt_path": "/artifacts/subtitle.srt",
        "segments": []
    }


if __name__ == "__main__":
    input_data = json.loads(sys.stdin.read())
    output = run(input_data)
    print(json.dumps(output, ensure_ascii=False))
```

约定：

1. 输入必须从 stdin 读取 JSON。
2. 输出必须从 stdout 返回 JSON。
3. 不允许直接打印无关日志到 stdout。
4. 日志应输出到 stderr。
5. 文件产物必须写入 Engine 指定的 artifact 目录。

---

## 16. API Tool 注册格式

API Tool 可以通过 OpenAPI 自动生成，也可以手动配置。

示例：

```yaml
id: volc_tts_generate_audio
type: api
name: 火山语音合成
description: 根据文本生成语音音频

method: POST
url: /api/v1/tts

input_schema:
  type: object
  required:
    - text
    - voice
  properties:
    text:
      type: string
    voice:
      type: string
    speed:
      type: number

output_schema:
  type: object
  properties:
    audio_url:
      type: string
    duration:
      type: number

auth:
  provider: volcengine
  type: api_key

execution:
  mode: sync
```

异步任务示例：

```yaml
execution:
  mode: async_polling
  submit_operation: create_video
  status_operation: get_video_status
  result_field: video_url
  interval_seconds: 5
  timeout_seconds: 600
```

---

## 17. Skill Runtime 执行流程

```text
1. 接收用户输入
2. 加载 Skill
3. 校验 Skill input_schema
4. 加载 Skill allowed_tools
5. 构造系统 Prompt
6. 调用大模型
7. 大模型决定是否调用 Tool
8. Engine 校验 Tool 是否被允许
9. Engine 校验 Tool 输入
10. Engine 执行 Tool
11. Engine 校验 Tool 输出
12. Tool 输出作为 observation 返回给大模型
13. 循环直到生成 final output
14. 校验 Skill output_schema
15. 保存 run、tool_calls、trace、artifacts、usage
16. 返回最终结果
```

---

## 18. Skill Runtime 伪代码

```python
async def run_skill(skill_id: str, input_data: dict) -> dict:
    skill = await skill_registry.get(skill_id)

    validate_json_schema(skill.input_schema, input_data)

    tools = await tool_registry.get_allowed_tools(skill.allowed_tools)

    run = await skill_run_store.create(
        skill_id=skill.id,
        input=input_data,
        status="running",
    )

    messages = build_skill_messages(
        skill=skill,
        input_data=input_data,
        tools=tools,
    )

    iterations = 0
    tool_call_count = 0

    while iterations < skill.limits.max_iterations:
        iterations += 1

        llm_result = await model_router.chat(
            profile=skill.model_profile,
            messages=messages,
            tools=convert_tools_to_llm_schema(tools),
        )

        await trace_store.record_llm(run.id, llm_result)

        if llm_result.final_output is not None:
            validate_json_schema(skill.output_schema, llm_result.final_output)

            await skill_run_store.complete(
                run_id=run.id,
                output=llm_result.final_output,
            )

            return llm_result.final_output

        for call in llm_result.tool_calls:
            tool_call_count += 1

            if tool_call_count > skill.limits.max_tool_calls:
                raise RuntimeError("MAX_TOOL_CALLS_EXCEEDED")

            tool = find_allowed_tool(tools, call.tool_id)

            if tool is None:
                raise RuntimeError(f"TOOL_NOT_ALLOWED: {call.tool_id}")

            validate_json_schema(tool.input_schema, call.arguments)

            tool_result = await tool_executor.execute(
                tool=tool,
                arguments=call.arguments,
                context={
                    "run_id": run.id,
                    "skill_id": skill.id,
                },
            )

            validate_json_schema(tool.output_schema, tool_result.output)

            await trace_store.record_tool_call(
                run_id=run.id,
                tool_call=call,
                result=tool_result,
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(tool_result.output, ensure_ascii=False),
                }
            )

    raise RuntimeError("MAX_ITERATIONS_EXCEEDED")
```

---

## 19. CLI 设计

第一版先做 CLI，后面再做 Web UI。

命令示例：

```bash
bkl init
bkl serve --host 127.0.0.1 --port 8000 --config bkl.yaml

bkl tool register ./tools/subtitle_generate_srt
bkl tool import-openapi ./examples/volc-openapi.json
bkl tool list
bkl tool test subtitle_generate_srt ./examples/subtitle_input.json

bkl skill register ./skills/talking-video
bkl skill list
bkl skill run talking-video ./examples/talking_video_input.json

bkl run list
bkl run show <run_id>
bkl trace show <run_id>
```

`bkl init` 负责生成 `bkl.yaml + .env`。真实 API Key 只能写入 `.env`，不允许写入 `bkl.yaml`。

`bkl serve` 负责启动 FastAPI 服务。服务端部署、本地 GUI、其他业务系统 HTTP 调用都应复用这个入口，不再单独绕过 `SkillEngine`。

---

## 20. 项目目录结构

当前源码目录职责详见 [BKL Project Structure](BKL_Project_Structure.md)。本节保留宏观目录结构，具体文件说明以代码导览文档为准。

```text
bkl-skill-engine/
  README.md
  TECH_SPEC.md
  pyproject.toml
  .env.example

  bkl_engine/
    __init__.py

    core/
      schemas.py
      errors.py
      config.py

    skills/
      registry.py
      loader.py
      runtime.py
      prompt.py

    tools/
      registry.py
      executor.py
      api_tool.py
      python_tool.py
      llm_tool.py
      skill_tool.py
      openapi_importer.py

    models/
      router.py
      providers/
        openai_compatible.py
        openrouter.py
        volcengine.py

    storage/
      database.py
      models.py
      repositories.py
      artifact_store.py

    trace/
      trace_store.py
      events.py

    policy/
      policy_engine.py

    cli/
      main.py
      tool_commands.py
      skill_commands.py
      run_commands.py

    api/
      main.py
      routes_tools.py
      routes_skills.py
      routes_runs.py

  examples/
    skills/
      talking-video/
        SKILL.md
        bkl.skill.json
        input.schema.json
        output.schema.json
        examples.json

    tools/
      subtitle_generate_srt/
        tool.yaml
        input.schema.json
        output.schema.json
        main.py
        requirements.txt

    inputs/
      talking_video_input.json
      subtitle_input.json

  tests/
    test_skill_loader.py
    test_tool_loader.py
    test_python_tool_runner.py
    test_skill_runtime.py
    test_openapi_importer.py
```

---

## 21. P0 功能需求

### P0-1 Tool Registry

必须实现：

```text
创建 Tool
读取 Tool
更新 Tool
删除 Tool
启用 / 禁用 Tool
按 type 查询 Tool
按 Skill 查询允许的 Tool
```

---

### P0-2 Python Tool Runner

必须实现：

```text
读取 tool.yaml
读取 input_schema
读取 output_schema
执行 main.py
stdin JSON 输入
stdout JSON 输出
超时控制
错误捕获
stderr 日志捕获
输出 Schema 校验
```

---

### P0-3 OpenAPI Tool Importer

必须实现：

```text
上传 openapi.json / openapi.yaml
解析 operationId
生成 API Tool
配置 base_url
配置 auth
生成 input_schema
生成 output_schema
测试调用
```

---

### P0-4 Skill Registry

必须实现：

```text
创建 Skill
读取 SKILL.md
配置 Markdown instructions
配置 input_schema
配置 output_schema
配置 allowed_tools
配置 model_profile
配置 limits
启用 / 禁用 Skill
```

---

### P0-5 Skill Runtime

必须实现：

```text
运行 Skill
调用 LLM
向 LLM 暴露 allowed_tools
执行 tool calls
追加 tool observations
生成 final output
校验 output_schema
限制最大轮次
限制最大工具调用数
```

---

### P0-6 Trace & Log

必须记录：

```text
Skill 输入
LLM 请求摘要
LLM 响应摘要
Tool 调用
Tool 输入
Tool 输出
Tool 错误
Final Output
Token
Cost
耗时
```

---

### P0-7 Artifact Store

必须实现：

```text
保存文件
生成 artifact_id
返回 artifact_uri
关联 run_id
关联 tool_call_id
支持本地文件存储
```

---

### P0-8 FastAPI 服务

必须实现：

```text
启动 API 服务
注册 Tool
注册 Skill
运行 Skill
查询 Run
查询 Trace
查询 Artifact
```

---

## 22. P1 功能需求

```text
Skill 调用 Skill
异步 API Tool
Webhook Tool
Tool 执行重试
Tool 调用缓存
Tool 版本管理
Skill 版本管理
Tool 测试面板
Prompt 版本管理
积分扣费
本地 credential 加密存储
Docker 沙箱执行 Python Tool
```

---

## 23. P2 功能需求

```text
Skill 市场
Skill 自动生成草稿
OpenAPI 导入后 AI 自动优化 Tool 描述
Python Tool 可视化创建
MCP Server 兼容
团队空间
权限系统
审计日志
沙箱增强
多模型路由策略
分布式队列
多租户隔离
```

---

## 24. 安全要求

### 24.1 Python Tool 安全

生产环境必须遵守：

```text
禁止 shell=True
禁止任意系统命令
禁止访问非 workspace 目录
禁止默认联网
禁止默认读取 secret
限制 CPU
限制内存
限制运行时间
限制输出文件大小
```

---

### 24.2 API Tool 安全

必须遵守：

```text
Secret 不进入 Prompt
Secret 不写入 Trace
Secret 不出现在错误日志中
API base_url 必须经过白名单或管理员确认
导入 OpenAPI 后必须人工确认工具描述
```

---

### 24.3 Skill 安全

必须遵守：

```text
Skill 只能调用 allowed_tools
Skill 不能访问全局工具池
Skill 不能直接读取 Credential
Skill 输出必须通过 output_schema 校验
Skill 达到最大轮次必须终止
Skill 达到最大工具调用数必须终止
```

---

## 25. 成本控制

每个 Skill 必须配置：

```yaml
limits:
  max_iterations: 8
  max_tool_calls: 12
  max_tokens: 12000
  timeout_seconds: 600
  max_credits: 100
```

每个 Tool 必须支持：

```text
timeout_seconds
max_output_size
retry_policy
cost_estimate
```

每次运行必须统计：

```text
input_tokens
output_tokens
tool_cost
model_cost
credits_charged
```

---

## 26. 第一阶段主链路

第一阶段不要被 SaaS、本地版、积分、UI 分散，只跑通这条主链路：

```text
注册一个 Python Tool
  ↓
注册一个 Skill
  ↓
Skill 通过大模型决定调用 Tool
  ↓
Tool 返回结果
  ↓
Skill 输出最终 JSON
  ↓
Engine 记录 Trace
  ↓
Engine 保存 Artifact
  ↓
API / CLI 能查询结果
```

---

## 27. 第一阶段验收标准

最小可用版本 v0.1 必须做到：

```text
1. 可以注册 Tool
2. 可以注册 Skill
3. 可以运行 Skill
4. Skill 可以调用 Python Tool
5. Skill 可以调用 API Tool
6. Skill 可以调用 LLM
7. 每次运行都有 run_id
8. 每次 Tool 调用都有 trace
9. 输出必须符合 output_schema
10. 文件产物进入 Artifact Store
11. CLI 可以跑
12. FastAPI 可以跑
13. Engine 可以作为微服务被外部项目调用
14. Engine 可以作为 Python SDK 被本地项目嵌入
```

---

## 28. 第一版示例 Skill：AI 口播视频生成

### 输入

```json
{
  "topic": "一款适合程序员的护眼台灯",
  "platform": "xiaohongshu",
  "duration_seconds": 60,
  "persona": "真实自然的产品推荐博主",
  "selling_points": [
    "光线柔和",
    "适合长时间写代码",
    "桌面不占空间"
  ]
}
```

### 输出

```json
{
  "script": "完整口播脚本",
  "titles": [
    "标题1",
    "标题2",
    "标题3"
  ],
  "audio_artifact_id": "artifact_xxx",
  "video_artifact_id": "artifact_yyy",
  "subtitle_artifact_id": "artifact_zzz",
  "viral_score": {
    "score": 82,
    "reason": "开头有痛点，但转化钩子还可以加强"
  }
}
```

---

## 29. Codex 开发方式

使用 Codex 时，不要一次性让它完成整个项目。  
应该按小任务逐步推进。

每个任务要求：

```text
目标明确
文件范围明确
验收标准明确
必须写测试
必须能运行
```

---

## 30. Codex 任务拆分

### Task 1：初始化 Python 项目

给 Codex 的任务：

```text
请初始化一个 Python 3.12 项目，项目名为 bkl-skill-engine。

要求：
1. 使用 pyproject.toml 管理依赖。
2. 添加 FastAPI、Pydantic v2、SQLAlchemy、Alembic、Typer、Rich、pytest、ruff、mypy。
3. 创建基础目录结构。
4. 添加 README.md。
5. 添加 .env.example。
6. 添加一个最简单的 CLI 命令：bkl --version。
7. 添加 pytest 基础测试。
8. 确保 pytest、ruff、mypy 可以运行。
```

验收标准：

```text
pytest 通过
ruff check 通过
mypy 通过
bkl --version 可执行
```

---

### Task 2：实现 Tool 数据结构和 Tool Loader

给 Codex 的任务：

```text
请实现 Tool 的 Pydantic 数据结构和本地 Tool Loader。

要求：
1. 定义 Tool、ToolPermissions、ToolRuntimeConfig。
2. 支持读取 tool.yaml。
3. 支持读取 input.schema.json 和 output.schema.json。
4. 校验必填字段：id、type、name、description、input_schema、output_schema。
5. 添加测试用例。
6. 在 examples/tools/subtitle_generate_srt 下创建一个示例 Tool。
```

验收标准：

```text
可以成功加载 examples/tools/subtitle_generate_srt/tool.yaml
缺少必填字段时会报清晰错误
pytest 通过
```

---

### Task 3：实现 Python Tool Runner

给 Codex 的任务：

```text
请实现 Python Tool Runner。

要求：
1. 通过 stdin 向 main.py 传入 JSON。
2. 通过 stdout 读取 JSON 输出。
3. 捕获 stderr 作为日志。
4. 支持 timeout_seconds。
5. 校验输入 JSON Schema。
6. 校验输出 JSON Schema。
7. 执行失败时返回结构化错误。
8. 添加测试用例。
```

验收标准：

```text
可以执行 subtitle_generate_srt 示例 Tool
输入不符合 schema 时失败
输出不符合 schema 时失败
超时时失败
pytest 通过
```

---

### Task 4：实现 Skill 数据结构和 Skill Loader

给 Codex 的任务：

```text
请实现 Skill 的 Pydantic 数据结构和本地 Skill Loader。

要求：
1. 定义 Skill、SkillLimits、SkillModelConfig。
2. 支持读取行业标准 SKILL.md。
3. 支持解析 YAML frontmatter 和 Markdown instructions。
4. 支持读取 BKL bkl.skill.json。
5. 支持读取 input.schema.json 和 output.schema.json。
6. 支持 allowed_tools 配置。
7. 添加 examples/skills/talking-video 示例。
8. 添加测试用例。
```

验收标准：

```text
可以成功加载 talking-video Skill
缺少 SKILL.md frontmatter 时会报错
缺少 bkl.skill.json 时会报错
allowed_tools 为空时会报错
pytest 通过
```

---

### Task 5：实现 Tool Registry

给 Codex 的任务：

```text
请实现本地 Tool Registry。

要求：
1. 支持 register_tool(path)。
2. 支持 get_tool(tool_id)。
3. 支持 list_tools()。
4. 支持 enable_tool(tool_id)。
5. 支持 disable_tool(tool_id)。
6. 支持根据 allowed_tools 过滤工具。
7. 暂时使用内存存储。
8. 添加测试用例。
```

验收标准：

```text
可以注册多个 Tool
可以按 id 查询 Tool
可以根据 Skill 的 allowed_tools 返回可用工具
pytest 通过
```

---

### Task 6：实现 Skill Registry

给 Codex 的任务：

```text
请实现本地 Skill Registry。

要求：
1. 支持 register_skill(path)。
2. 支持 get_skill(skill_id)。
3. 支持 list_skills()。
4. 支持 enable_skill(skill_id)。
5. 支持 disable_skill(skill_id)。
6. 暂时使用内存存储。
7. 添加测试用例。
```

验收标准：

```text
可以注册 Skill
可以按 id 查询 Skill
可以启用和禁用 Skill
pytest 通过
```

---

### Task 7：实现 Model Router 基础版

给 Codex 的任务：

```text
请实现 Model Router 基础版。

要求：
1. 定义 ModelRouter 接口。
2. 实现 OpenAI-compatible Provider。
3. 支持 base_url、api_key、model。
4. 支持 chat(messages, tools)。
5. 支持返回 tool_calls。
6. 支持返回 final_output。
7. 添加 mock provider 方便测试。
8. 添加测试用例。
```

验收标准：

```text
Mock provider 可以模拟 final_output
Mock provider 可以模拟 tool_calls
Skill Runtime 可以用 mock provider 做单元测试
pytest 通过
```

---

### Task 8：实现 Skill Runtime 基础版

给 Codex 的任务：

```text
请实现 Skill Runtime。

要求：
1. 接收 skill_id 和 input_data。
2. 校验 Skill input_schema。
3. 加载 allowed_tools。
4. 构造 messages。
5. 调用 Model Router。
6. 执行 tool_calls。
7. 将 Tool 输出追加为 observation。
8. 循环直到 final_output。
9. 校验 Skill output_schema。
10. 限制 max_iterations。
11. 限制 max_tool_calls。
12. 添加测试用例。
```

验收标准：

```text
可以运行一个 mock Skill
可以调用一个 mock Tool
可以产出 final_output
超过 max_iterations 会失败
超过 max_tool_calls 会失败
未授权 Tool 会失败
pytest 通过
```

---

### Task 9：实现 Trace Store

给 Codex 的任务：

```text
请实现 Trace Store 基础版。

要求：
1. 定义 TraceEvent。
2. 记录 skill_started。
3. 记录 llm_called。
4. 记录 tool_called。
5. 记录 tool_succeeded。
6. 记录 tool_failed。
7. 记录 skill_succeeded。
8. 记录 skill_failed。
9. 第一版使用内存存储。
10. 添加测试用例。
```

验收标准：

```text
每次 Skill Run 都能查询到完整 Trace
Tool 调用失败时能记录错误
pytest 通过
```

---

### Task 10：实现 Artifact Store

给 Codex 的任务：

```text
请实现 Artifact Store 基础版。

要求：
1. 支持本地文件系统保存 artifact。
2. 支持生成 artifact_id。
3. 支持通过 artifact_id 查询 artifact。
4. 支持关联 run_id 和 tool_call_id。
5. 支持保存 text、json、audio、video、image、subtitle 类型。
6. 添加测试用例。
```

验收标准：

```text
可以保存并读取 artifact
可以通过 run_id 查询 artifact
pytest 通过
```

---

### Task 11：实现 CLI

给 Codex 的任务：

```text
请实现 Typer CLI。

要求：
1. bkl init
2. bkl serve
3. bkl tool register <path>
4. bkl tool list
5. bkl tool test <tool_id> <input_json>
6. bkl skill register <path>
7. bkl skill list
8. bkl skill run <skill_id> <input_json>
9. bkl trace show <run_id>
10. 使用 Rich 美化输出。
```

验收标准：

```text
可以通过 CLI 初始化 bkl.yaml + .env
可以通过 CLI 启动 FastAPI 服务
可以通过 CLI 注册 Tool
可以通过 CLI 注册 Skill
可以通过 CLI 运行 Skill
可以查看 Trace
```

---

### Task 12：实现 FastAPI 服务

给 Codex 的任务：

```text
请实现 FastAPI 服务。

要求：
1. POST /tools/register
2. GET /tools
3. GET /tools/{tool_id}
4. POST /skills/register
5. GET /skills
6. GET /skills/{skill_id}
7. POST /skills/{skill_id}/runs
8. GET /runs/{run_id}
9. GET /runs/{run_id}/trace
10. GET /runs/{run_id}/artifacts
11. 添加 API 测试。
```

验收标准：

```text
FastAPI 可以启动
可以通过 API 注册 Tool
可以通过 API 注册 Skill
可以通过 API 运行 Skill
可以查询 Run 和 Trace
pytest 通过
```

---

### Task 13：实现 OpenAPI Tool Importer

给 Codex 的任务：

```text
请实现 OpenAPI Tool Importer。

要求：
1. 支持读取 openapi.json。
2. 支持读取 openapi.yaml。
3. 解析 paths、methods、operationId。
4. 生成 Tool 定义。
5. 生成 input_schema。
6. 生成 output_schema。
7. 支持 base_url 配置。
8. 支持 auth 配置。
9. 添加测试用例。
```

验收标准：

```text
可以从一个简单 openapi.json 生成 API Tool
没有 operationId 时可以生成稳定 tool_id
pytest 通过
```

---

## 31. 里程碑

### Milestone 1：Tool 可执行

完成内容：

```text
Tool Loader
Python Tool Runner
Tool Registry
CLI tool test
```

产出：

```text
可以执行一个标准 Python Tool
```

---

### Milestone 2：Skill 可运行

完成内容：

```text
Skill Loader
Skill Registry
Skill Runtime
Mock Model Provider
Trace Store
```

产出：

```text
可以运行一个 Skill，并调用 Tool
```

---

### Milestone 3：LLM 可编排 Tool

完成内容：

```text
Model Router
OpenAI-compatible Provider
Tool Calling Loop
Schema 校验
Final Output 校验
```

产出：

```text
大模型可以根据 Skill 指令选择并调用工具
```

---

### Milestone 4：API Tool 可导入

完成内容：

```text
OpenAPI Importer
API Tool Executor
Auth 配置
API Tool Test
```

产出：

```text
swagger.json 可以变成可调用工具
```

---

### Milestone 5：微服务可复用

完成内容：

```text
FastAPI 服务
REST API
Python SDK
CLI
本地 Artifact Store
Trace 查询
```

产出：

```text
外部项目可以通过 API 或 SDK 调用 BKL Skill Engine
```

---

### Milestone 6：口播视频 MVP

完成内容：

```text
talking-video Skill
script_writer Tool
title_generator Tool
tts Tool
subtitle Tool
viral_score Tool
```

产出：

```text
输入主题后，可以生成口播视频生产链路中的结构化产物
```

---

## 32. 后续产品如何复用

以后每个产品不需要重写 Agent 逻辑，只需要提供：

```text
产品自己的 UI
产品自己的 Skill 包
产品自己的 Tool 包
产品自己的业务数据库
产品自己的计费方式
```

然后调用 Engine：

```text
Product App → BKL Skill Engine → Skill → Tool → Artifact
```

例如：

### 32.1 爆款实验室

```text
口播视频 Skill
小红书笔记 Skill
探店文案 Skill
商品种草 Skill
标题评分 Skill
```

### 32.2 许知衣 AI 穿搭顾问

```text
穿搭分析 Skill
单品推荐 Skill
小红书穿搭文案 Skill
商品搜索 API Tool
图片分析 Tool
```

### 32.3 王不懂的小实验

```text
实验内容生成 Skill
儿童提问引导 Skill
图文脚本 Skill
图片 Prompt Tool
安全检查 Tool
```

---

## 33. 暂不实现内容

第一版明确不做：

```text
复杂 Workflow
可视化拖拽流程
Skill 市场
多 Agent 协作
团队权限
复杂积分系统
分布式队列
浏览器自动化
长期记忆
自动发布内容
SaaS 前端
本地桌面端
```

这些放到 P1/P2 或产品层实现。

---

## 34. 最终目标

BKL Skill Engine 的最终目标不是做一个通用 Agent 平台，而是成为所有 AI 产品的底层执行内核。

最终结构：

```text
bkl-skill-engine
  ↑
  ├── 爆款实验室 SaaS
  ├── 本地口播视频软件
  ├── 许知衣 AI 穿搭顾问
  ├── 王不懂的小实验
  └── 企业私有化内容工作台
```

底层全部复用：

```text
Skill Runtime
Tool Registry
Model Router
Artifact Store
Trace Store
Policy Engine
REST API
Python SDK
CLI
```

---

## 34.1 安装与部署形态

BKL 只维护一个 Core Engine，不做多套互相分叉的引擎实现。

详细决策文档见 [BKL Core Engine Installation Forms](BKL_Core_Engine_Installation_Forms.md)。

推荐安装形态：

```text
bkl-core
  Skill Loader
  Tool Runner
  Model Router
  Runtime
  Trace / Artifact / Catalog

bkl-cli
  bkl init
  bkl chat
  bkl skill run
  bkl tool import
  bkl serve

bkl-server
  FastAPI HTTP API
  Auth
  Persistence
  Worker / Queue
  Docker image

bkl-desktop
  Local GUI
  Local bkl serve
  Model / Tool / Skill / Run management
```

约束：

```text
Skill 规范只有一套：SKILL.md + bkl.skill.json
Tool 规范只有一套：tool.yaml
模型配置只有一套：bkl.yaml + .env
CLI、HTTP、GUI 都调用同一个 SkillEngine
```

---

## 35. v0.1 开发前补充约定

当前文档已经可以开始实现，但为了让第一版 API、CLI、SDK 三种调用方式共享同一套内核，v0.1 开发前需要补齐以下实现契约。

### 35.1 P0 最小范围收敛

P0 必须先跑通最小闭环：

```text
本地配置加载
本地 Tool / Skill 包加载
内存 Registry
Python Tool Runner
Mock Model Provider
Skill Runtime Tool Calling Loop
Trace Store
Artifact Store
Typer CLI
FastAPI API
bkl init
bkl serve
持久化 Catalog：.bkl/catalog.json
```

P0 中 OpenAI-compatible Provider、API Tool Executor、OpenAPI Importer 可以实现基础骨架，但测试主链路必须优先使用 Mock Model Provider，避免第一阶段被外部模型 Key、网络和第三方 API 阻塞。

### 35.2 单一 Engine 内核

API、CLI、Python SDK 不应该各自实现业务逻辑。

必须统一调用同一个 `SkillEngine` Facade：

```python
class SkillEngine:
    @classmethod
    def load(cls, config_path: str | None = None) -> "SkillEngine":
        ...

    async def register_tool(self, path: str) -> Tool:
        ...

    async def register_skill(self, path: str) -> Skill:
        ...

    async def run_skill(
        self,
        skill_id: str,
        input_data: dict,
        context: RunContext | None = None,
    ) -> RunResult:
        ...
```

调用关系：

```text
CLI ─┐
API ─┼── SkillEngine ─── Registry / Runtime / Store
SDK ─┘
```

### 35.3 配置文件规范

第一版需要明确配置入口，默认路径为：

```text
./bkl.yaml
./.env
```

示例：

```yaml
app:
  name: bkl-skill-engine
  environment: local

storage:
  database_url: sqlite:///./data/bkl_engine.db
  artifact_root: ./data/artifacts

registries:
  skills_dir: ./examples/skills
  tools_dir: ./examples/tools

models:
  default_profile: mock
  profiles:
    mock:
      provider: mock
      model: mock-tool-calling
    fast:
      provider: openai_compatible
      model: openai/gpt-4.1-mini
      base_url: ${OPENAI_COMPATIBLE_BASE_URL}
      api_key_env: OPENAI_COMPATIBLE_API_KEY

runtime:
  max_concurrent_runs: 4
  default_timeout_seconds: 600
  trace_redaction: true
```

Secrets 只允许通过环境变量或本地 credential store 引用，不允许写入 `SKILL.md`、`tool.yaml`、Prompt、Trace。

### 35.4 Run 返回结构统一

API、CLI、SDK 都必须围绕同一个 `RunResult`：

```python
class RunResult(BaseModel):
    run_id: str
    status: Literal["pending", "running", "succeeded", "failed"]
    skill_id: str
    output: dict | None = None
    error: EngineError | None = None
    artifacts: list[Artifact] = []
    trace_summary: dict = {}
    usage: UsageSummary = UsageSummary()
```

REST API 返回：

```json
{
  "run_id": "run_123",
  "status": "succeeded",
  "skill_id": "talking-video",
  "output": {},
  "error": null,
  "artifacts": [],
  "trace_summary": {},
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "model_cost": 0,
    "tool_cost": 0,
    "credits_charged": 0
  }
}
```

### 35.5 错误模型统一

所有 API、CLI、SDK 错误必须统一为结构化错误：

```python
class EngineError(BaseModel):
    code: str
    message: str
    details: dict = {}
    retryable: bool = False
```

第一版至少定义这些错误码：

```text
SKILL_NOT_FOUND
TOOL_NOT_FOUND
TOOL_NOT_ALLOWED
INPUT_SCHEMA_INVALID
OUTPUT_SCHEMA_INVALID
TOOL_INPUT_SCHEMA_INVALID
TOOL_OUTPUT_SCHEMA_INVALID
MODEL_PROVIDER_ERROR
PYTHON_TOOL_FAILED
PYTHON_TOOL_TIMEOUT
MAX_ITERATIONS_EXCEEDED
MAX_TOOL_CALLS_EXCEEDED
RUN_TIMEOUT
ARTIFACT_NOT_FOUND
CONFIG_INVALID
SECRET_NOT_AVAILABLE
```

### 35.6 同步与异步运行约定

P0 默认支持同步执行：

```http
POST /skills/{skill_id}/runs
```

请求体：

```json
{
  "input": {},
  "context": {},
  "mode": "sync"
}
```

P1 再增加异步执行：

```json
{
  "input": {},
  "context": {},
  "mode": "async"
}
```

P0 即使内部同步执行，也必须保存 `Run` 和 `Trace`，保证后续可以平滑切到队列执行。

### 35.7 CLI 与 API 参数对齐

CLI 命令必须能表达 API 的核心参数：

```bash
bkl skill run talking-video ./examples/inputs/talking-video-input.json \
  --context ./examples/inputs/context.json \
  --mode sync \
  --output json
```

CLI 输出模式：

```text
table   给人看
json    给脚本和自动化系统看
```

CLI 退出码：

```text
0 成功
1 业务执行失败
2 参数或配置错误
3 外部服务错误
```

### 35.8 JSON Schema 约定

Skill 和 Tool 的 schema 统一使用 JSON Schema Draft 2020-12。

约定：

```text
input_schema 必须是 object
output_schema 必须是 object
required 字段必须显式声明
additionalProperties 默认建议为 false
```

第一版可以使用 `jsonschema` 进行校验，但所有校验错误必须转换为 `EngineError`。

### 35.9 Trace 脱敏规则

Trace 可以记录调试所需信息，但必须默认脱敏：

```text
Authorization header
API Key
Bearer Token
Cookie
Set-Cookie
password
secret
token
credential
```

Trace Event 基础结构：

```python
class TraceEvent(BaseModel):
    id: str
    run_id: str
    type: str
    timestamp: datetime
    message: str
    data: dict = {}
```

### 35.10 Artifact 路径约定

Python Tool 不应该自己决定最终 artifact URI。

Engine 在执行 Tool 时通过环境变量传入：

```text
BKL_RUN_ID
BKL_TOOL_CALL_ID
BKL_ARTIFACT_DIR
```

Python Tool 只把文件写到 `BKL_ARTIFACT_DIR` 下，并在 stdout JSON 中返回相对路径：

```json
{
  "files": [
    {
      "path": "subtitle.srt",
      "type": "subtitle",
      "mime_type": "application/x-subrip"
    }
  ]
}
```

Engine 负责登记 artifact、生成 artifact_id、生成 artifact_uri。

### 35.11 API Tool 执行边界

API Tool 第一版需要明确这些字段：

```yaml
method: POST
url: /api/v1/tts
base_url: ${VOLCENGINE_BASE_URL}
timeout_seconds: 60

auth:
  type: api_key
  header: Authorization
  value_env: VOLCENGINE_API_KEY

request:
  content_type: application/json

response:
  output_path: $.data
```

禁止 Tool 配置中直接保存 secret 明文。

### 35.12 测试分层

P0 测试必须分三层：

```text
单元测试：loader、schema、runner、registry、stores
集成测试：Skill Runtime + Mock Model + Python Tool
接口测试：FastAPI TestClient + CLI runner
```

第一阶段不要求真实调用外部模型，但必须保留 provider contract test，后续接 OpenRouter / OpenAI-compatible 时复用。

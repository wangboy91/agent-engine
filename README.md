# BKL Skill Engine

Language: [中文](#中文) | [English](#english)

---

## 中文

BKL Skill Engine 是一个可复用的 Python Skill 运行时，用于加载标准 `SKILL.md`、执行 Tools，并返回结构化结果、Artifacts 和 Trace。

### 当前能力

- 加载本地 Tool 包：`tool.yaml`
- 通过 JSON stdin/stdout 执行 Python Tool
- 加载标准 Skill 包：`SKILL.md` frontmatter + Markdown instructions + `bkl.skill.json`
- 支持同步 Skill Runtime 和 tool-calling loop
- 支持 Mock、OpenAI-compatible、Anthropic-compatible 模型协议
- 支持 `bkl.yaml + .env` 多模型 profile 配置，并通过 `models.active_profile` 启用其中一个
- 记录 in-memory Run 和 Trace
- 保存本地 Artifact
- SDK、CLI、FastAPI 共用同一个 `SkillEngine` facade
- 支持从简单 OpenAPI operation 导入 API Tool
- 支持第一版 Agent 编排：自然语言路由 Skill、场景映射、输入补齐、`bkl chat --once` 和 `/chat/messages`

### 安装形态

BKL 只维护一个 Core Engine，按使用场景提供不同入口：

- **CLI / SDK**：适合开发者、本地脚本、CI 和服务器批处理
- **Server / HTTP**：通过 `bkl serve` 部署 FastAPI 服务，供其他系统调用
- **Desktop / Local GUI**：后续本地界面启动本机 `bkl serve`，通过 HTTP API 管理模型、Tool、Skill 和运行记录

Skill、Tool、模型配置在所有形态下保持同一套规范。

### 快速安装与升级

在仓库根目录执行一条命令即可安装 CLI；重复执行同一条命令会覆盖旧版本并完成升级：

```bash
uv tool install --force --upgrade .
```

安装后验证：

```bash
bkl --version
```

如果 shell 找不到 `bkl`，先执行：

```bash
uv tool update-shell
```

再重新打开终端。示例 Tool、Skill 和输入文件在当前仓库里，下面的示例命令默认都从仓库根目录执行。

完整使用说明见 [BKL Usage Guide](doc/BKL_Usage_Guide.md)。

业务智能体基座目标架构见 [BKL Business Agent Base Architecture](doc/BKL_Business_Agent_Base_Architecture.md)。

业务智能体基座迭代路线见 [BKL Business Agent Base Roadmap](doc/BKL_Business_Agent_Base_Roadmap.md)。

详细架构决策见 [BKL Core Engine Installation Forms](doc/BKL_Core_Engine_Installation_Forms.md)。

Skill 运行请求和路由选择见 [BKL Skill Run Request and Routing](doc/BKL_Skill_Run_Request_and_Routing.md)。

Agent 工程化设计见 [BKL Agent Runtime Engineering Plan](doc/BKL_Agent_Runtime_Engineering.md)。

代码目录结构和文件职责见 [BKL Project Structure](doc/BKL_Project_Structure.md)。

### Skill 格式

Skill 包只支持一套规范：标准 `SKILL.md` + BKL `bkl.skill.json`。

`SKILL.md` 遵循行业常见 Skill 形态：YAML frontmatter 只保留标准元数据 `name` 和 `description`，后面是 Markdown instructions。BKL 引擎自己的运行时配置不写进 `SKILL.md`，统一放在同目录的 `bkl.skill.json`。

```text
talking-video/
  SKILL.md
  bkl.skill.json
  schemas/input.schema.json
  schemas/output.schema.json
  examples/examples.json
```

```md
---
name: talking-video
description: Use when generating a structured talking-video draft.
---

# AI 口播视频生成

Follow the workflow and return JSON matching `schemas/output.schema.json`.
```

```json
{
  "id": "talking-video",
  "version": "0.1.0",
  "input_schema": "schemas/input.schema.json",
  "output_schema": "schemas/output.schema.json",
  "model": {
    "profile": "mock"
  },
  "tools": {
    "allow": [
      "subtitle_generate_srt"
    ]
  }
}
```

### 开发环境

安装开发依赖：

```bash
uv --cache-dir .uv-cache sync --extra dev
```

运行基础检查：

```bash
uv --cache-dir .uv-cache run --extra dev pytest
uv --cache-dir .uv-cache run --extra dev ruff check .
uv --cache-dir .uv-cache run --extra dev mypy bkl_engine
```

查看 CLI 版本：

```bash
bkl --version
```

### 模型配置

模型配置位于 `bkl.yaml`。可以同时配置多个 profile，并通过 `models.active_profile` 选择当前启用的模型。

可以用启动向导生成配置：

```bash
uv --cache-dir .uv-cache run --extra dev bkl init \
  --protocol openai-compatible \
  --profile xfyun_openai \
  --base-url https://maas-coding-api.cn-huabei-1.xf-yun.com/v2 \
  --model astron-code-latest \
  --api-key "你的密钥"
```

如果当前目录已经有 `bkl.yaml`，`bkl init` 会拒绝覆盖。确认要替换现有配置时加 `--force`；如果要保留现有配置，用 `--config bkl.xfyun.yaml --env-file .env.xfyun` 写入另一组文件。

也可以复制示例配置：

```bash
cp bkl.example.yaml bkl.yaml
```

在 `.env` 中配置密钥和模型，不要把真实密钥提交到 git：

```bash
OPENAI_COMPATIBLE_BASE_URL=https://maas-coding-api.cn-huabei-1.xf-yun.com/v2
OPENAI_AUTH_TOKEN=...
OPENAI_MODEL=astron-code-latest

ANTHROPIC_BASE_URL=https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic
ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_MODEL=astron-code-latest
```

支持的协议：

- `openai-compatible`：调用 `{base_url}/chat/completions`
- `anthropic`：调用 `{base_url}/v1/messages`

配置文件只保存环境变量名称，不保存密钥值。

### Catalog 持久化

`bkl tool register` 和 `bkl skill register` 默认会写入 `.bkl/catalog.json`。`bkl serve` 启动时会读取这个 catalog，因此服务重启后仍能看到已导入的 Tool 和 Skill。

```bash
uv --cache-dir .uv-cache run --extra dev bkl tool register \
  resources/tools/subtitle_generate_srt

uv --cache-dir .uv-cache run --extra dev bkl skill register \
  resources/skills/talking-video
```

可以通过 `--catalog` 指定其他 catalog 文件，便于测试。当前产品底座不把这个文件当作全局技能市场使用，它只是本地运行时可加载 Tool/Skill 包的缓存。

面向业务使用时，Skill 先安装到 workspace，再由 identity 绑定可使用的 Skill。这样前期保持一个工作区、一个身份也能独立管理和修改自己的技能；后续如果需要全局技能市场，可以在 workspace catalog 之上再加分发层。

`SkillEngine.load()` 同时会使用同目录下的工作区和会话状态文件：

- `.bkl/workspaces.json`：保存 workspace、identity、workspace 安装/启停的 Skill，以及 identity 绑定的 Skill。
- `.bkl/sessions.json`：保存 chat session、messages、turns、run_ids、workspace 和 identity 元数据。
- `.bkl/runs.json`：保存 Skill/Workflow run 的最终状态、输出、错误和 usage 摘要。
- `.bkl/traces.json`：保存运行过程事件；敏感字段会按 key 自动脱敏。
- `.bkl/policies.json`：保存 workspace / identity / global 级 Tool allow、ask、deny 规则，以及 Tool 审批记录。
- `.bkl/secrets.json`：保存本地 SecretStore；API 只返回 metadata，不返回 secret 明文。

`.bkl/` 已加入 `.gitignore`。测试模式 `SkillEngine.create_for_testing()` 仍使用内存 store，避免测试污染本地状态。

Workspace Skill Catalog API：

- `POST /workspaces/{workspace_id}/skills`：把已注册的 Skill 安装到当前 workspace。
- `GET /workspaces/{workspace_id}/skills`：查看当前 workspace 的 Skill 目录。
- `PATCH /workspaces/{workspace_id}/skills/{skill_id}`：启用或停用 workspace 内的 Skill。
- `POST /workspaces/{workspace_id}/identities/{identity_id}/skills`：把 workspace 已安装且启用的 Skill 绑定给 identity。

### CLI 示例

启动 HTTP 服务：

```bash
uv --cache-dir .uv-cache run --extra dev bkl serve \
  --host 127.0.0.1 \
  --port 8000 \
  --config bkl.yaml
```

启动 HTTP/SSE/WebSocket 网关：

```bash
bkl gateway \
  --host 127.0.0.1 \
  --port 8000 \
  --config bkl.yaml
```

执行示例 Python Tool：

```bash
uv --cache-dir .uv-cache run --extra dev bkl tool test \
  resources/tools/subtitle_generate_srt \
  resources/inputs/subtitle_input.json \
  --output json
```

使用 Mock 模型运行示例 Skill：

```bash
uv --cache-dir .uv-cache run --extra dev bkl skill run \
  talking-video \
  resources/inputs/talking-video-input.json \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --output json
```

返回里的 `output` 是业务结果，`trace_summary` 是执行过程摘要，`artifacts` 是登记到 ArtifactStore 的文件产物。普通 Skill 会把最终输出保存为 `data/artifacts/<run_id>/<skill-id>-output.json`，路径会出现在 `artifacts[0].uri`。`Mock script for ...` 表示当前使用 mock 模型配置，只用于本地 smoke test；真实内容生成需要配置真实模型并传入 `--config bkl.yaml`。

运行「内容视频生产工作流」示例：

```bash
uv --cache-dir .uv-cache run --extra dev bkl skill run \
  content-video-workflow \
  resources/inputs/content-video-workflow-input.json \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --output json
```

该 Workflow Skill 会按顺序运行多个子 Skill，并输出从想法到分镜提示词的结构化资产：

```text
content-brief-planner
  -> hook-plan-generator
  -> style-bible-planner
  -> talking-script-writer
  -> script-segmenter
  -> storyboard-designer
  -> render-prompt-builder
```

最终结果包含 `ContentBrief`、`HookPlan`、`StyleBible`、`Script`、`ScriptSegments`、`Storyboard` 和 `RenderPromptPack`，并会在 artifact 目录写入 `content-video-workflow.json`。真实视频生成、TTS、FFmpeg 或 Remotion 合成可以作为后续 Provider Adapter 或独立工作流继续接入。

运行「王不懂的小实验」示例 Skill：

```bash
uv --cache-dir .uv-cache run --extra dev bkl skill run \
  wangbudong-experiment \
  resources/inputs/wangbudong-experiment-input.json \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --output json
```

该 Skill 会调用 `wangbudong_write_prompt_pack`，在本次 run 的 artifact 目录里写入 `00-实验拆解.md`、`01-首图提示词.md`、`02-分步骤提示词.md`、`03-小红书文案.md`。

使用 Agent 模式从自然语言运行 Skill：

```bash
uv --cache-dir .uv-cache run --extra dev bkl chat \
  --once "帮我生成60秒小红书口播视频，主题是程序员护眼台灯" \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --output json
```

Agent 会先从已注册或扫描到的 Skill 中选择候选 `skill_id`，再根据目标 Skill 的 `schemas/input.schema.json` 抽取输入。缺少必填字段时不会运行 Skill，而是返回 `needs_input`。

输入一句内容并输出分镜提示词：

```bash
bkl chat \
  --once "介绍openspec" \
  --skill content-video-workflow \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --config bkl.yaml \
  --view prompts \
  --output json
```

这里 `--config bkl.yaml` 会使用真实模型配置；不加时 CLI 默认使用 mock 测试模型。`--view prompts` 只输出 `storyboard` 和 `render_prompt_pack`。

查看 workflow 执行过程：

```bash
bkl chat \
  --once "介绍openspec" \
  --skill content-video-workflow \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --config bkl.yaml \
  --view trace \
  --output json
```

`--view trace` 展示可观测执行过程：`trace_summary`、`workflow_steps` 和 `artifacts`。每个 workflow step 会带自己的子 run `trace_summary` 和 `artifacts`。它不会暴露模型隐藏思考链；对齐 OpenAI/Anthropic 的做法，应展示 tool calls、事件、状态和可审计中间产物。

使用 `bkl.yaml + .env` 中的真实模型配置运行示例 Skill：

```bash
uv --cache-dir .uv-cache run --extra dev bkl skill run \
  talking-video \
  resources/inputs/talking-video-input.json \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --config bkl.yaml \
  --output json
```

判断 Skill 是否真正触发 Tool，看返回里的 `trace_summary`：

```json
{
  "llm_called": 2,
  "tool_called": 1,
  "tool_succeeded": 1,
  "tool_failed": 0
}
```

### Python SDK 示例

```python
import asyncio

from bkl_engine.engine import SkillEngine


async def main() -> None:
    engine = SkillEngine.load("bkl.yaml")
    await engine.register_tool("resources/tools/subtitle_generate_srt")
    await engine.register_skill("resources/skills/talking-video")
    result = await engine.run_skill(
        "talking-video",
        {
            "topic": "适合程序员的护眼台灯",
            "platform": "xiaohongshu",
            "duration_seconds": 60,
        },
    )
    print(result.model_dump(mode="json"))


asyncio.run(main())
```

### API 示例

启动 FastAPI：

```bash
uv --cache-dir .uv-cache run --extra dev bkl serve --config bkl.yaml
```

注册 Tool 和 Skill，然后运行：

```bash
curl -X POST http://127.0.0.1:8000/tools/register \
  -H 'Content-Type: application/json' \
  -d '{"path":"resources/tools/subtitle_generate_srt"}'

curl -X POST http://127.0.0.1:8000/skills/register \
  -H 'Content-Type: application/json' \
  -d '{"path":"resources/skills/talking-video"}'

curl -X POST http://127.0.0.1:8000/skills/talking-video/runs \
  -H 'Content-Type: application/json' \
  -d '{"input":{"topic":"适合程序员的护眼台灯","platform":"xiaohongshu","duration_seconds":60},"mode":"sync"}'

curl -X POST http://127.0.0.1:8000/chat/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我生成60秒小红书口播视频，主题是程序员护眼台灯"}'
```

---

## English

BKL Skill Engine is a reusable Python runtime for loading standard `SKILL.md` packages, executing Tools, and returning structured results, Artifacts, and Trace data.

### Current Capabilities

- Load local Tool packages from `tool.yaml`
- Execute Python Tools through JSON stdin/stdout
- Load standard Skill packages from `SKILL.md` frontmatter + Markdown instructions + `bkl.skill.json`
- Run a synchronous Skill Runtime with a tool-calling loop
- Support Mock, OpenAI-compatible, and Anthropic-compatible model protocols
- Support multiple model profiles through `bkl.yaml + .env`, with `models.active_profile` selecting the active one
- Record in-memory Runs and Traces
- Save local Artifacts
- Share the same `SkillEngine` facade across SDK, CLI, and FastAPI
- Import simple OpenAPI operations as API Tools
- Support the first Agent orchestration slice: natural-language Skill routing, scene mapping, input resolution, `bkl chat --once`, and `/chat/messages`

### Installation Forms

BKL keeps one Core Engine and exposes different entrypoints for different deployment targets:

- **CLI / SDK**: local scripts, CI, developer workflows, and server batch jobs
- **Server / HTTP**: deploy FastAPI through `bkl serve` for other systems to call
- **Desktop / Local GUI**: a future local UI can start `bkl serve` locally and manage models, Tools, Skills, and runs through HTTP

Skill, Tool, and model configuration formats stay the same across all forms.

See [BKL Business Agent Base Architecture](doc/BKL_Business_Agent_Base_Architecture.md) for the target DDD architecture.

See [BKL Business Agent Base Roadmap](doc/BKL_Business_Agent_Base_Roadmap.md) for the architecture hardening roadmap.

See [BKL Core Engine Installation Forms](doc/BKL_Core_Engine_Installation_Forms.md) for the detailed architecture decision.

See [BKL Skill Run Request and Routing](doc/BKL_Skill_Run_Request_and_Routing.md) for run request and routing details.

See [BKL Agent Runtime Engineering Plan](doc/BKL_Agent_Runtime_Engineering.md) for the Agent orchestration design.

See [BKL Project Structure](doc/BKL_Project_Structure.md) for source layout and file responsibilities.

### Skill Format

Only one Skill package format is supported: standard `SKILL.md` + BKL `bkl.skill.json`.

`SKILL.md` follows the common Skill shape: YAML frontmatter contains only the standard `name` and `description` metadata, followed by Markdown instructions. BKL runtime configuration does not live inside `SKILL.md`; it belongs in the sibling `bkl.skill.json` file.

```text
talking-video/
  SKILL.md
  bkl.skill.json
  schemas/input.schema.json
  schemas/output.schema.json
  examples/examples.json
```

```md
---
name: talking-video
description: Use when generating a structured talking-video draft.
---

# AI Talking Video Generation

Follow the workflow and return JSON matching `schemas/output.schema.json`.
```

```json
{
  "id": "talking-video",
  "version": "0.1.0",
  "input_schema": "schemas/input.schema.json",
  "output_schema": "schemas/output.schema.json",
  "model": {
    "profile": "mock"
  },
  "tools": {
    "allow": [
      "subtitle_generate_srt"
    ]
  }
}
```

### Development

Install or upgrade the CLI from the repository root:

```bash
uv tool install --force --upgrade .
```

Verify the installed command:

```bash
bkl --version
```

If `bkl` is not on `PATH`, run:

```bash
uv tool update-shell
```

Then restart your shell. Example commands below assume they are run from the repository root, because the sample Tools, Skills, and inputs live in this checkout.

For a full usage guide, see [BKL Usage Guide](doc/BKL_Usage_Guide.md).

Install development dependencies:

```bash
uv --cache-dir .uv-cache sync --extra dev
```

Run baseline checks:

```bash
uv --cache-dir .uv-cache run --extra dev pytest
uv --cache-dir .uv-cache run --extra dev ruff check .
uv --cache-dir .uv-cache run --extra dev mypy bkl_engine
```

Check the CLI version:

```bash
bkl --version
```

### Model Configuration

Model providers are configured in `bkl.yaml`. You can define multiple profiles and choose the active one with `models.active_profile`.

Generate configuration with the init command:

```bash
uv --cache-dir .uv-cache run --extra dev bkl init \
  --protocol openai-compatible \
  --profile xfyun_openai \
  --base-url https://maas-coding-api.cn-huabei-1.xf-yun.com/v2 \
  --model astron-code-latest \
  --api-key "your-api-key"
```

If `bkl.yaml` already exists, `bkl init` refuses to overwrite it. Add `--force` only when you want to replace the existing config. To keep the existing config, use `--config bkl.xfyun.yaml --env-file .env.xfyun` for a separate file pair.

You can also copy the example config:

```bash
cp bkl.example.yaml bkl.yaml
```

Set credentials and model names in `.env`. Do not commit real secrets:

```bash
OPENAI_COMPATIBLE_BASE_URL=https://maas-coding-api.cn-huabei-1.xf-yun.com/v2
OPENAI_AUTH_TOKEN=...
OPENAI_MODEL=astron-code-latest

ANTHROPIC_BASE_URL=https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic
ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_MODEL=astron-code-latest
```

Supported protocols:

- `openai-compatible`: calls `{base_url}/chat/completions`
- `anthropic`: calls `{base_url}/v1/messages`

Config files store environment variable names only, not secret values.

### Catalog Persistence

`bkl tool register` and `bkl skill register` write to `.bkl/catalog.json` by default. `bkl serve` loads that catalog on startup, so imported Tools and Skills remain available after restart.

```bash
uv --cache-dir .uv-cache run --extra dev bkl tool register \
  resources/tools/subtitle_generate_srt

uv --cache-dir .uv-cache run --extra dev bkl skill register \
  resources/skills/talking-video
```

Use `--catalog` to select another catalog file for tests. The product base does
not treat this file as a global Skill marketplace yet; it is only the local
runtime cache of loadable Tool and Skill packages.

For business use, install Skills into a workspace first, then bind the enabled
workspace Skills to an identity. This keeps the early product shape simple: one
workspace and one identity can manage their own editable Skill catalog. A global
Skill marketplace can be added later as a distribution layer above workspace
catalogs.

`SkillEngine.load()` also uses local workspace and session state files next to
the catalog:

- `.bkl/workspaces.json`: stores workspaces, identities, workspace-installed
  Skills with enabled state, and identity Skill bindings.
- `.bkl/sessions.json`: stores chat sessions, messages, turns, run ids,
  workspace metadata, and identity metadata.
- `.bkl/runs.json`: stores final Skill/Workflow run status, output, errors, and
  usage summaries.
- `.bkl/traces.json`: stores execution trace events with automatic redaction for
  sensitive keys.
- `.bkl/policies.json`: stores global, workspace, and identity Tool allow, ask,
  and deny policies plus approval records.
- `.bkl/secrets.json`: stores the local SecretStore. APIs return metadata only,
  not secret values.

Workspace Skill Catalog APIs:

- `POST /workspaces/{workspace_id}/skills`: install a registered Skill into the workspace.
- `GET /workspaces/{workspace_id}/skills`: list workspace Skills.
- `PATCH /workspaces/{workspace_id}/skills/{skill_id}`: enable or disable a workspace Skill.
- `POST /workspaces/{workspace_id}/identities/{identity_id}/skills`: bind an enabled workspace Skill to an identity.

### CLI Examples

Start the HTTP service:

```bash
uv --cache-dir .uv-cache run --extra dev bkl serve \
  --host 127.0.0.1 \
  --port 8000 \
  --config bkl.yaml
```

Start the HTTP/SSE/WebSocket gateway:

```bash
bkl gateway \
  --host 127.0.0.1 \
  --port 8000 \
  --config bkl.yaml
```

Execute the example Python Tool:

```bash
uv --cache-dir .uv-cache run --extra dev bkl tool test \
  resources/tools/subtitle_generate_srt \
  resources/inputs/subtitle_input.json \
  --output json
```

Run the example Skill with the mock model:

```bash
uv --cache-dir .uv-cache run --extra dev bkl skill run \
  talking-video \
  resources/inputs/talking-video-input.json \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --output json
```

In the response, `output` is the business result, `trace_summary` is the execution-process summary, and `artifacts` lists files registered by the ArtifactStore. A normal Skill saves final output to `data/artifacts/<run_id>/<skill-id>-output.json`, and the path appears in `artifacts[0].uri`. `Mock script for ...` means the mock model profile is active for local smoke tests; use a real model config with `--config bkl.yaml` for real generation.

Run the Wangbudong experiment example Skill:

```bash
uv --cache-dir .uv-cache run --extra dev bkl skill run \
  wangbudong-experiment \
  resources/inputs/wangbudong-experiment-input.json \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --output json
```

This Skill calls `wangbudong_write_prompt_pack` and writes `00-实验拆解.md`, `01-首图提示词.md`, `02-分步骤提示词.md`, and `03-小红书文案.md` into the run artifact directory.

Run a Skill through the Agent layer from natural language:

```bash
uv --cache-dir .uv-cache run --extra dev bkl chat \
  --once "帮我生成60秒小红书口播视频，主题是程序员护眼台灯" \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --output json
```

The Agent selects a candidate `skill_id` from registered or scanned Skills, then extracts input from the target Skill's `schemas/input.schema.json`. If required fields are missing, it returns `needs_input` instead of running the Skill.

Run the full content-video workflow from one topic and print only storyboard/render prompts:

```bash
bkl chat \
  --once "介绍openspec" \
  --skill content-video-workflow \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --config bkl.yaml \
  --view prompts \
  --output json
```

`--config bkl.yaml` uses your real model profile; without it, the CLI uses the mock test model. `--view prompts` prints only `storyboard` and `render_prompt_pack`.

Run the example Skill with the real model profile from `bkl.yaml + .env`:

```bash
uv --cache-dir .uv-cache run --extra dev bkl skill run \
  talking-video \
  resources/inputs/talking-video-input.json \
  --skills-dir resources/skills \
  --tools-dir resources/tools \
  --config bkl.yaml \
  --output json
```

To confirm that the Skill triggered a Tool, check `trace_summary`:

```json
{
  "llm_called": 2,
  "tool_called": 1,
  "tool_succeeded": 1,
  "tool_failed": 0
}
```

### Python SDK Example

```python
import asyncio

from bkl_engine.engine import SkillEngine


async def main() -> None:
    engine = SkillEngine.load("bkl.yaml")
    await engine.register_tool("resources/tools/subtitle_generate_srt")
    await engine.register_skill("resources/skills/talking-video")
    result = await engine.run_skill(
        "talking-video",
        {
            "topic": "适合程序员的护眼台灯",
            "platform": "xiaohongshu",
            "duration_seconds": 60,
        },
    )
    print(result.model_dump(mode="json"))


asyncio.run(main())
```

### API Example

Start FastAPI:

```bash
uv --cache-dir .uv-cache run --extra dev bkl serve --config bkl.yaml
```

Register a Tool and Skill, then run:

```bash
curl -X POST http://127.0.0.1:8000/tools/register \
  -H 'Content-Type: application/json' \
  -d '{"path":"resources/tools/subtitle_generate_srt"}'

curl -X POST http://127.0.0.1:8000/skills/register \
  -H 'Content-Type: application/json' \
  -d '{"path":"resources/skills/talking-video"}'

curl -X POST http://127.0.0.1:8000/skills/talking-video/runs \
  -H 'Content-Type: application/json' \
  -d '{"input":{"topic":"适合程序员的护眼台灯","platform":"xiaohongshu","duration_seconds":60},"mode":"sync"}'

curl -X POST http://127.0.0.1:8000/chat/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我生成60秒小红书口播视频，主题是程序员护眼台灯"}'
```

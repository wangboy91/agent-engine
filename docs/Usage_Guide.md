# BKL Usage Guide

这份文档面向直接使用 `bkl` CLI、SDK 和网关的用户。开发者验证命令仍以 README 和 `pyproject.toml` 为准。

## 1. 安装与升级

在仓库根目录执行：

```bash
uv tool install --force --upgrade .
```

这条命令同时用于首次安装和后续升级。安装后检查版本：

```bash
bkl --version
```

如果终端找不到 `bkl`：

```bash
uv tool update-shell
```

然后重新打开终端。

## 2. 初始化模型配置

本地 mock 示例不需要真实密钥。要接入真实 OpenAI-compatible 模型，可以生成 `bkl.yaml` 和 `.env`：

```bash
bkl init \
  --protocol openai-compatible \
  --profile xfyun_openai \
  --base-url https://maas-coding-api.cn-huabei-1.xf-yun.com/v2 \
  --model astron-code-latest \
  --api-key "你的密钥"
```

如果当前目录已经有 `bkl.yaml`，`bkl init` 会拒绝覆盖。确认要替换现有配置时加 `--force`：

```bash
bkl init \
  --protocol openai-compatible \
  --profile xfyun_openai \
  --base-url https://maas-coding-api.cn-huabei-1.xf-yun.com/v2 \
  --model astron-code-latest \
  --api-key "你的密钥" \
  --force
```

如果只是想保留现有配置并创建另一份配置文件，使用 `--config` 和 `--env-file`：

```bash
bkl init \
  --protocol openai-compatible \
  --profile xfyun_openai \
  --base-url https://maas-coding-api.cn-huabei-1.xf-yun.com/v2 \
  --model astron-code-latest \
  --api-key "你的密钥" \
  --config bkl.xfyun.yaml \
  --env-file .env.xfyun
```

配置文件只保存环境变量名，密钥写入 `.env`。不要提交 `.env`。

## 3. 快速自测

以下命令默认从仓库根目录执行，因为示例 Tool、Skill 和输入文件都在当前仓库内。

测试 CLI：

```bash
bkl --version
```

测试 Python Tool：

```bash
bkl tool test \
  engine/resources/tools/subtitle_generate_srt \
  engine/resources/inputs/subtitle_input.json \
  --output json
```

运行口播视频 Skill：

```bash
bkl skill run \
  talking-video \
  engine/resources/inputs/talking-video-input.json \
  --skills-dir engine/resources/skills \
  --tools-dir engine/resources/tools \
  --output json
```

返回 JSON 中的关键字段：

- `output`：本次 Skill 的业务结果，例如脚本、标题、字幕路径和字幕分段。
- `trace_summary`：执行过程摘要，例如模型调用次数、工具调用次数、工具成功/失败次数。
- `artifacts`：本次 run 记录的文件产物。普通 Skill 会把最终输出保存为 `data/artifacts/<run_id>/<skill-id>-output.json`，路径会出现在 `artifacts[0].uri`。

如果看到 `Mock script for ...`，说明当前使用的是 mock 模型配置。这是本地 smoke test 的预期结果，不是调用真实大模型。要生成真实内容，需要用 `bkl init` 配置真实模型 profile，并在运行时传入 `--config bkl.yaml`。

运行内容视频生产工作流：

```bash
bkl skill run \
  content-video-workflow \
  engine/resources/inputs/content-video-workflow-input.json \
  --skills-dir engine/resources/skills \
  --tools-dir engine/resources/tools \
  --output json
```

该工作流会输出脚本、分镜和渲染提示词。后续真实视频生成、TTS、FFmpeg 或 Remotion 合成可以作为独立 Provider Adapter 或下游工作流继续接入。

## 4. Agent 自然语言调用

一次性自然语言调用：

```bash
bkl chat \
  --once "帮我生成60秒小红书口播视频，主题是程序员护眼台灯" \
  --skills-dir engine/resources/skills \
  --tools-dir engine/resources/tools \
  --output json
```

如果 Agent 能识别意图并补齐必填输入，会直接运行对应 Skill。缺少必填字段时会返回 `needs_input`。

### 输入一句内容，输出分镜提示词

如果你要把一句内容直接走完整内容视频工作流，例如“介绍 openspec”，并只看分镜和生成提示词：

```bash
bkl chat \
  --once "介绍openspec" \
  --skill content-video-workflow \
  --skills-dir engine/resources/skills \
  --tools-dir engine/resources/tools \
  --config bkl.yaml \
  --view prompts \
  --output json
```

关键点：

- `--config bkl.yaml`：使用真实模型配置；不加这个参数时，CLI 默认使用 mock 测试模型。
- `--skill content-video-workflow`：强制走完整工作流，而不是只跑单个 `talking-video` Skill。
- `--view prompts`：只输出 `storyboard` 和 `render_prompt_pack`，适合直接拿分镜提示词。
- 只输入一句 topic 时，默认 `platform=xiaohongshu`、`duration_seconds=60`。

### 查看执行过程

如果你想看 workflow 执行了哪些步骤、每一步的子 run，以及模型/工具调用摘要：

```bash
bkl chat \
  --once "介绍openspec" \
  --skill content-video-workflow \
  --skills-dir engine/resources/skills \
  --tools-dir engine/resources/tools \
  --config bkl.yaml \
  --view trace \
  --output json
```

`--view trace` 输出：

- `trace_summary`：模型调用、工具调用、workflow step 成功/失败计数。
- `workflow_steps`：每个 workflow step 的 `step_id`、`skill_id`、`run_id`、`status`，以及该子 run 的 `trace_summary` 和 `artifacts`。
- `artifacts`：最终结果文件路径。

这对应 OpenAI/Anthropic 常见的 tool call / event trace 思路：展示可观测执行过程、工具调用和中间产物。模型内部隐藏思考链不会原样暴露；如果模型或 provider 返回 reasoning summary，后续可以作为单独字段记录。

指定 Skill 调用：

```bash
bkl chat \
  --once "主题是程序员护眼台灯" \
  --skill talking-video \
  --input engine/resources/inputs/talking-video-input.json \
  --skills-dir engine/resources/skills \
  --tools-dir engine/resources/tools \
  --output json
```

## 5. 启动网关

启动 HTTP/SSE/WebSocket 网关：

```bash
bkl gateway \
  --host 127.0.0.1 \
  --port 8000 \
  --config bkl.yaml
```

如果只需要普通 HTTP 服务，也可以使用：

```bash
bkl serve --host 127.0.0.1 --port 8000 --config bkl.yaml
```

## 6. 注册 Tool 和 Skill

服务启动后，注册示例 Tool：

```bash
curl -X POST http://127.0.0.1:8000/tools/register \
  -H 'Content-Type: application/json' \
  -d '{"path":"engine/resources/tools/subtitle_generate_srt"}'
```

注册示例 Skill：

```bash
curl -X POST http://127.0.0.1:8000/skills/register \
  -H 'Content-Type: application/json' \
  -d '{"path":"engine/resources/skills/talking-video"}'
```

注册内容视频工作流需要同时注册 `engine/resources/tools` 和 `engine/resources/skills` 中相关包。CLI 示例会自动扫描目录；HTTP 服务更适合先通过 catalog 持久化注册结果。

## 7. HTTP 调用

同步执行指定 Skill：

```bash
curl -X POST http://127.0.0.1:8000/skills/talking-video/runs \
  -H 'Content-Type: application/json' \
  -d '{"input":{"topic":"适合程序员的护眼台灯","platform":"xiaohongshu","duration_seconds":60},"mode":"sync"}'
```

通过 Agent 执行：

```bash
curl -X POST http://127.0.0.1:8000/chat/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我生成60秒小红书口播视频，主题是程序员护眼台灯"}'
```

## 8. SSE 调用

指定 Skill 的事件流：

```bash
curl -N -X POST http://127.0.0.1:8000/skills/talking-video/runs/events \
  -H 'Content-Type: application/json' \
  -d '{"input":{"topic":"适合程序员的护眼台灯","platform":"xiaohongshu","duration_seconds":60}}'
```

Agent 的事件流：

```bash
curl -N -X POST http://127.0.0.1:8000/chat/messages/events \
  -H 'Content-Type: application/json' \
  -d '{"message":"帮我生成60秒小红书口播视频，主题是程序员护眼台灯"}'
```

当前事件包括 `run_started`、`run_completed`、`run_failed`、`agent_started`、`agent_completed` 和 `agent_failed`。

## 9. WebSocket 调用

Skill WebSocket 路径：

```text
ws://127.0.0.1:8000/ws/skills/{skill_id}/runs
```

发送 JSON：

```json
{
  "input": {
    "topic": "适合程序员的护眼台灯",
    "platform": "xiaohongshu",
    "duration_seconds": 60
  }
}
```

Agent WebSocket 路径：

```text
ws://127.0.0.1:8000/ws/chat
```

发送 JSON：

```json
{
  "message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯"
}
```

服务端会返回 `*_started` 和 `*_completed` 或 `*_failed` 事件。

## 10. 开发验证

开发环境使用：

```bash
uv --cache-dir .uv-cache sync --extra dev
```

完整验证：

```bash
uv --cache-dir .uv-cache run --extra dev pytest
uv --cache-dir .uv-cache run --extra dev ruff check .
uv --cache-dir .uv-cache run --extra dev mypy app
```

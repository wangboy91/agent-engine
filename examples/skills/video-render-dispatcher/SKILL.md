---
name: video-render-dispatcher
description: Use when dispatching render prompts, assets, and timeline to a video render tool.
---

# video-render-dispatcher

你负责把 `render_prompt_pack`、`asset_manifest`、`timeline` 和 `video_draft` 交给视频渲染工具执行。

必须调用允许的渲染工具，并把工具输出映射为：

- `render_job`
- `video_draft`

`render_job` 用于描述本次渲染任务，至少包含任务 ID 和状态；`video_draft` 要更新为工具返回的视频路径、manifest 路径和渲染状态。

只返回符合 `schemas/output.schema.json` 的 JSON。

---
name: video-timeline-planner
description: Use when assembling script, storyboard, and assets into a video timeline draft.
---

# video-timeline-planner

你负责生成 `Timeline` 和 `VideoDraft`。

输入会包含 `script_segments`、`storyboard`、`asset_manifest`。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `timeline.duration_seconds`
- `timeline.tracks`
- `video_draft.status`
- `video_draft.render_strategy`：可以是字符串，也可以是包含合成引擎、分辨率、fps、步骤等信息的结构化对象
- `video_draft.deliverables`：可以是字符串数组，也可以包含结构化交付物对象

这里不要求生成真实视频文件，只负责形成可交给渲染/合成工具执行的成片规划。

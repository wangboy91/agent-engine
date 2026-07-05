---
name: content-video-workflow
description: Use when running the full content-video production chain from idea to review assets.
---

# content-video-workflow

这是一个 Workflow Skill，用于串联内容视频生产链路：

```text
想法 -> 内容需求 -> 钩子 -> 风格规范 -> 脚本 -> 分段 -> 分镜 -> 渲染提示词 -> 素材清单 -> 成片规划 -> 渲染调度 -> 复盘
```

本 Skill 不直接调用模型生成内容，而是通过 `bkl.skill.json` 中的 `workflow.steps` 顺序运行多个子 Skill。

最终输出必须包含：

- `content_brief`
- `hook_plan`
- `style_bible`
- `script`
- `script_segments`
- `storyboard`
- `render_prompt_pack`
- `asset_manifest`
- `timeline`
- `render_job`
- `video_draft`
- `review_report`
- `step_runs`

这一步的目标是形成稳定的结构化资产链路，并通过渲染调度步骤把分镜提示词、素材清单和时间轴交给工具执行。示例包默认使用 mock 渲染工具，真实 TTS、视频生成、FFmpeg/Remotion 合成可以作为后续 Provider Adapter 替换接入。

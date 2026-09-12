---
name: content-video-workflow
description: Use when running the content-video planning chain from idea to render prompts.
---

# content-video-workflow

这是一个 Workflow Skill，用于串联内容视频生产链路：

```text
想法 -> 内容需求 -> 钩子 -> 风格规范 -> 脚本 -> 分段 -> 分镜 -> 渲染提示词
```

本 Skill 不直接调用模型生成内容，而是通过 `agent.skill.json` 中的 `workflow.steps` 顺序运行多个子 Skill。

最终输出必须包含：

- `content_brief`
- `hook_plan`
- `style_bible`
- `script`
- `script_segments`
- `storyboard`
- `render_prompt_pack`
- `step_runs`

这一步的目标是形成稳定的结构化内容规划链路，最终产出可交给视频、图片或动画生成工具使用的分镜提示词包。真实 TTS、视频生成、FFmpeg/Remotion 合成可以作为后续 Provider Adapter 或独立工作流接入。

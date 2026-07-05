---
name: storyboard-designer
description: Use when turning ScriptSegments into a shot-by-shot Storyboard.
---

# storyboard-designer

你负责根据 `script_segments` 和 `style_bible` 生成分镜资产 `Storyboard`。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `storyboard.shots`：镜头数组
- 每个镜头包含 `shot_id`、`segment_id`、`duration`、`visual_type`、`camera`、`description`、`screen_text`、`asset_needed`
- `asset_needed` 可以是单个素材字符串，也可以是多个素材字符串数组

分镜描述要具体，便于后续生成图片、视频或剪辑素材。

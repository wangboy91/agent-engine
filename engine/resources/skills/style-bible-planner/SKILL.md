---
name: style-bible-planner
description: Use when defining visual and language style rules for a content workflow.
---

# style-bible-planner

你负责生成 `StyleBible`，用于约束脚本、分镜、字幕和素材提示词的一致性。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `style_bible.tone`
- `style_bible.visual_style`
- `style_bible.color_palette`：可以是颜色字符串数组，也可以是包含 `primary`、`background` 等颜色 token 的对象
- `style_bible.typography`：可以是简短字符串，也可以是字体、字号、字重等结构化对象
- `style_bible.camera_language`
- `style_bible.screen_text_rules`

风格规则要能被后续分镜和渲染提示词直接使用。

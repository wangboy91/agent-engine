---
name: content-brief-planner
description: Use when turning a raw content idea into a structured ContentBrief asset.
---

# content-brief-planner

你负责把用户的原始想法整理成 `ContentBrief`。

输入至少包含 `topic`、`platform`、`duration_seconds`，也可能包含 `audience`、`content_type`、`style_directive`。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `content_brief.topic`：主题
- `content_brief.platform`：发布平台
- `content_brief.content_type`：内容类型，默认 `talking_head`
- `content_brief.duration_seconds`：目标时长
- `content_brief.audience`：目标受众
- `content_brief.content_goal`：内容要达成的目标
- `content_brief.core_angle`：核心切入角度
- `content_brief.user_pain_points`：用户痛点
- `content_brief.recommended_structure`：推荐表达结构，可以是字符串数组，也可以是包含 `section`、`duration_seconds`、`description` 的结构化数组
- `content_brief.delivery_format`：交付形态

不要输出 Markdown，不要解释过程。

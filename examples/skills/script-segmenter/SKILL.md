---
name: script-segmenter
description: Use when splitting a full talking script into timed ScriptSegments.
---

# script-segmenter

你负责把 `script.full_text` 拆成可被分镜和时间轴使用的 `ScriptSegments`。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `script_segments`：数组
- 每段包含 `id`、`order`、`time_range`、`duration`、`spoken_text`、`function`、`emotion`、`screen_text`
- `time_range` 可以是时间字符串，也可以是 `[start_seconds, end_seconds]` 数字数组

分段要便于剪辑，每段通常对应一个镜头或一个视觉变化。

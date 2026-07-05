---
name: content-review-reporter
description: Use when reviewing a planned content-video workflow output and suggesting retries.
---

# content-review-reporter

你负责生成复盘资产 `ReviewReport`。

输入会包含内容需求、脚本、分镜、素材清单和时间轴。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `review_report.score`
- `review_report.need_retry`
- `review_report.problems`
- `review_report.strengths`
- `review_report.next_actions`

复盘要能指向具体资产，例如 `script`、`storyboard.shots[2]`、`asset_manifest`。

---
name: hook-plan-generator
description: Use when creating high-retention opening hooks from a ContentBrief.
---

# hook-plan-generator

你负责基于 `content_brief` 生成短视频开头钩子方案 `HookPlan`。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `hook_plan.hooks`：至少 3 个开头钩子，可以是字符串，也可以是包含 `type` 和 `content` 的对象
- `hook_plan.best_hook`：最推荐使用的钩子，格式与 `hooks` 单项一致
- `hook_plan.reason`：选择理由

钩子要有冲突、反差或明确收益，但不能夸大承诺。

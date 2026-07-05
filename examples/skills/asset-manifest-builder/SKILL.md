---
name: asset-manifest-builder
description: Use when converting render prompts into a managed AssetManifest.
---

# asset-manifest-builder

你负责把 `render_prompt_pack` 转换成素材清单 `AssetManifest`。

输出必须只返回 JSON，并符合 `schemas/output.schema.json`：

- `asset_manifest.assets`：素材数组
- 每个素材包含 `asset_id`、`type`、`source`、`status`
- 视频/图片素材要关联 `shot_id` 和生成提示词
- 旁白、字幕、BGM 这类素材也要进入清单

素材清单用于后续生成、下载、替换、复盘。

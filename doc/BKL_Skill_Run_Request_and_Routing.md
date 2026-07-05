# BKL Skill Run Request and Routing

本文说明三件事：

1. 运行 Skill 时输入参数从哪里来
2. 输出参数从哪里来
3. 根据用户需求如何锁定要运行哪个 Skill

## 1. Skill 包里的职责分工

一个 Skill 包由这些文件共同决定运行契约：

```text
SKILL.md
bkl.skill.json
input.schema.json
output.schema.json
examples.json
```

职责：

```text
SKILL.md
  给模型看的说明书：什么时候使用、如何执行、注意事项、输出要求。

bkl.skill.json
  给引擎看的运行配置：skill id、schema 文件、允许调用的 tools、模型 profile、limits。

input.schema.json
  给调用方看的入参契约：运行这个 Skill 必须传哪些字段、字段类型是什么。

output.schema.json
  给调用方看的出参契约：运行成功后 result.output 必须包含哪些字段、字段类型是什么。

examples.json
  示例输入输出，用于测试、展示、未来 few-shot 或评测。
```

## 2. 当前 talking-video 示例

`examples/skills/talking-video/bkl.skill.json` 里声明：

```json
{
  "id": "talking-video",
  "input_schema": "input.schema.json",
  "output_schema": "output.schema.json",
  "tools": {
    "allow": [
      "subtitle_generate_srt"
    ]
  }
}
```

所以这个 Skill 的运行 ID 是：

```text
talking-video
```

它的入参来自 `input.schema.json`：

```json
{
  "required": ["topic", "platform", "duration_seconds"],
  "properties": {
    "topic": {
      "type": "string"
    },
    "platform": {
      "type": "string"
    },
    "duration_seconds": {
      "type": "integer",
      "minimum": 1
    }
  }
}
```

所以运行请求必须传：

```json
{
  "topic": "适合程序员的护眼台灯",
  "platform": "xiaohongshu",
  "duration_seconds": 60
}
```

它的出参来自 `output.schema.json`：

```json
{
  "required": ["script", "titles", "subtitle_path", "segments"],
  "properties": {
    "script": {
      "type": "string"
    },
    "titles": {
      "type": "array"
    },
    "subtitle_path": {
      "type": "string"
    },
    "segments": {
      "type": "array"
    }
  }
}
```

所以运行成功后，`result.output` 至少会包含：

```json
{
  "script": "...",
  "titles": ["..."],
  "subtitle_path": "subtitle.srt",
  "segments": []
}
```

## 3. CLI 运行请求

CLI 当前是显式指定 Skill：

```bash
bkl skill run talking-video examples/inputs/talking-video-input.json \
  --skills-dir examples/skills \
  --tools-dir examples/tools \
  --output json
```

这里的含义：

```text
talking-video
  要运行的 skill_id。

examples/inputs/talking-video-input.json
  请求入参，必须符合 talking-video/input.schema.json。

--skills-dir
  从哪里扫描 Skill 包。

--tools-dir
  从哪里扫描 Tool 包。

--output json
  按 JSON 输出 RunResult，方便服务或脚本读取。
```

## 4. HTTP 运行请求

HTTP 当前也是显式指定 Skill：

```http
POST /skills/talking-video/runs
```

请求体：

```json
{
  "input": {
    "topic": "适合程序员的护眼台灯",
    "platform": "xiaohongshu",
    "duration_seconds": 60
  },
  "mode": "sync"
}
```

这里的 `input` 必须符合 `talking-video/input.schema.json`。

响应是统一的 `RunResult`：

```json
{
  "run_id": "run_xxx",
  "status": "succeeded",
  "skill_id": "talking-video",
  "output": {
    "script": "...",
    "titles": ["..."],
    "subtitle_path": "subtitle.srt",
    "segments": []
  },
  "error": null,
  "artifacts": [],
  "trace_summary": {
    "llm_called": 2,
    "tool_called": 1,
    "tool_succeeded": 1,
    "tool_failed": 0
  }
}
```

## 5. Runtime 实际做了什么校验

当前 Runtime 会做两次 schema 校验：

```text
运行前：
  input 必须符合 skill.input_schema。

模型返回最终结果后：
  output 必须符合 skill.output_schema。
```

如果输入不符合 schema，运行会失败并返回结构化错误。

如果模型最终输出不符合 schema，运行也会失败并返回结构化错误。

## 6. 如何根据需求锁定 Skill

有三种方式，推荐按产品阶段逐步实现。

### 6.1 方式一：显式指定 skill_id

这是当前已经实现的方式。

适合：

- CLI
- API
- 开发调试
- 后端服务明确知道自己要调用哪个 Skill

示例：

```text
用户已经选择“口播视频生成”
后端直接运行 skill_id = talking-video
```

优点：

- 稳定
- 可控
- 不需要模型判断
- 适合生产接口

### 6.2 方式二：应用场景映射到 Skill

这是产品里最推荐的方式。

应用先决定场景，再由场景映射到固定 Skill。

示例：

```text
应用：本地口播视频软件
页面：生成口播视频
Skill：talking-video

应用：OpenAPI Tool 创建器
页面：导入 OpenAPI
Skill：openapi_tool_builder

应用：Skill 工作台
页面：创建 Skill
Skill：skill_creator
```

请求链路：

```text
用户进入某个应用页面
  -> 页面知道 scene_id
  -> scene_id 映射到 skill_id
  -> 前端根据 input_schema 生成表单
  -> 用户填写表单
  -> 后端运行 skill_id
  -> 前端根据 output_schema 渲染结果
```

这种方式下，不需要每次让模型猜运行哪个 Skill。

### 6.3 方式三：自然语言 Skill Router

这是 `bkl chat` 未来要做的方式。

用户说：

```text
帮我做一个 60 秒的小红书口播视频，主题是程序员护眼台灯
```

Router 从 catalog 中读取所有 Skill 的：

```text
skill_id
name
description
input_schema
output_schema
SKILL.md 摘要
```

然后判断最匹配的 Skill：

```json
{
  "skill_id": "talking-video",
  "confidence": 0.92,
  "input": {
    "topic": "程序员护眼台灯",
    "platform": "xiaohongshu",
    "duration_seconds": 60
  }
}
```

如果置信度低，或者缺少必填字段，就先问用户确认。

示例：

```text
我找到两个可能的 Skill：
1. talking-video：生成口播视频脚本和字幕
2. title_generator：只生成标题

你要生成完整口播视频，还是只要标题？
```

## 7. 推荐策略

不同场景的推荐路由方式：

```text
生产 API
  显式 skill_id。

具体应用页面
  scene_id -> skill_id。

本地 GUI 工作台
  用户选择 Skill，或用自然语言 router 辅助推荐。

bkl chat
  自然语言 router 选择 Skill，低置信度时要求确认。

后台自动化流程
  显式 skill_id 或 workflow step 绑定 skill_id。
```

## 8. 下一步要实现的能力

当前已经实现：

```text
显式 skill_id 运行
input_schema 校验
output_schema 校验
catalog 持久化
```

下一步建议实现：

```text
Skill Router
  输入自然语言需求
  从 catalog 读取候选 Skill
  输出 skill_id + input 草稿 + confidence

Scene Mapping
  scene_id -> skill_id
  前端/应用可以按场景直接运行 Skill

Schema-driven Form
  前端读取 input_schema
  自动生成表单
  提交后运行 Skill
```

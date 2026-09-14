# agent-engine(后端内核)

Agent Engine AI 产品的 Python Skill 运行时内核。这里是独立的项目根:构建、运行、测试都从本目录启动。

```bash
cd engine
uv sync --extra dev          # 首次
uv run pytest                # 测试
uv run ae --version          # CLI
uv run ae serve --host 127.0.0.1 --port 8050 --config agent.yaml
```

- 包代码:`app/`(`engine.py` 是唯一公共门面 `SkillEngine`)
- 测试:`tests/`;本地资源包:`resources/`
- 运行时输出:`.agent/`、`data/`(均已 gitignore)
- 架构与使用文档:仓库根目录的 `README.md` 与 `docs/`
- 变更流程规范:仓库根目录的 `openspec/`

前端界面(未来 `web/` 目录)与内核的分离方案见 `openspec/changes/`。

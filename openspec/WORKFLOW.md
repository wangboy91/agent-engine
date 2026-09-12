# 变更流程治理(权威规则)

本仓库同时装有 OpenSpec(项目级 skills + CLI)和 Superpowers(Claude Code 全局)。
两套都自带"规划 -> 执行"流程,同时触发会互相打架。以下分工是唯一合法用法,所有 agent(Claude Code / Codex / 其他)都必须遵守。

## 驱动者:OpenSpec(负责变更全生命周期)

- 新功能/修复:openspec propose -> 生成 proposal.md / specs/ / design.md / tasks.md
- 实现:openspec apply(严格按 tasks.md 逐条实现、逐条打勾 `- [ ]` -> `- [x]`)
- 收尾:openspec verify -> openspec archive
- 所有计划产物只允许存在于 openspec/changes/<change>/ 下

## 质量动作:Superpowers(只允许在这些场景用)

- brainstorming —— 需求模糊时先把想法聊清楚,结论喂给 openspec propose
- test-driven-development + verification-before-completion —— 在 apply 的每个 task 内部:先写测试 -> 实现 -> 验证
- systematic-debugging —— 排查疑难 bug
- requesting-code-review / finishing-a-development-branch / using-git-worktrees —— 收尾评审、合并、隔离分支

## 禁止(以下正是"不顺畅"的来源)

- 禁止运行 superpowers 的 writing-plans / executing-plans / subagent-driven-development / dispatching-parallel-agents 作为并行流程
- 禁止为同一变更同时维护 openspec 的 tasks.md 和 docs/superpowers/plans/*.md
- 若发现 docs/superpowers/plans/ 下出现本仓库的计划文件 -> 说明走错流程,删除并回到 openspec

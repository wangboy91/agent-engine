# BKL Workspace Agent Runtime Roadmap

## Goal

BKL Skill Engine is a business Skill runtime. The product shape is a multi-tenant
workspace where different identities manage and use different business Skills
through a chat-like UI.

## Runtime Axes

- Workspace: isolates users, identities, Skill catalogs, runs, artifacts, and permissions.
- Identity: represents a business role/persona, such as content operator, marketer,
  reviewer, or automation owner.
- Skill: reusable business capability with explicit input/output schema.
- Session: chat-like conversation scoped to one workspace and identity.
- Run: one concrete Skill or workflow execution.
- Event: real-time execution signal for UI, CLI, SSE, and WebSocket clients.

## Current Foundation

- `RunContext` has first-class `workspace_id`, `identity_id`, and `role_id`.
- Chat API accepts `context` and passes it into Skill execution.
- Workflow steps support `depends_on` and `max_parallel_steps`.
- `content-video-workflow` is configured as a DAG, allowing independent planning
  steps to run concurrently.
- Trace events are published through an in-memory event bus and can persist to
  the local JSON trace store.
- SSE and WebSocket gateways stream live execution events such as
  `skill_started`, `workflow_step_started`, `llm_called`, `tool_called`,
  `workflow_step_succeeded`, and final completion/failure events.
- SSE and WebSocket subscriptions can be scoped by workspace and identity.
- Workspace Skill catalogs are available through in-memory stores for tests and
  JSON stores for local runtime.
- A Skill must be installed and enabled in the active workspace before an
  identity can bind or route to it.
- Identities bind the subset of enabled workspace Skill ids they are allowed to
  use.
- Chat routing respects the active identity Skill catalog when
  `workspace_id` and `identity_id` are present in `RunContext`.
- Tool execution policy supports global, workspace, and identity rules with
  `allow`, `ask`, and `deny` effects. Identity rules override workspace rules.
- `ask` policies create persistent Tool approval records. Approved records allow
  a rerun for the same workspace, identity, Skill, and Tool.
- Runs waiting on Tool approval can resume with the same `run_id` after approval.
- SecretStore supports workspace-scoped secrets and `secret_ref` resolution for
  Tool arguments. Secret APIs return metadata only.
- Agent sessions can persist messages, turns, run ids, workspace, and identity
  metadata through the local JSON session store.
- `SkillEngine.load()` uses `.bkl/workspaces.json` and `.bkl/sessions.json` by
  default, alongside `.bkl/catalog.json`, `.bkl/runs.json`, and
  `.bkl/traces.json`, `.bkl/policies.json`, and `.bkl/secrets.json` for local
  runtime state.

## Target Architecture

```text
UI / CLI / SDK / Gateway
  -> Session API
    -> Agent Runtime
      -> Permission Engine
      -> Skill Router
      -> Workflow DAG Runner
        -> Skill Runtime
        -> Tool Runtime
        -> Model Router
      -> Event Stream
    -> Workspace Stores
      -> Sessions
      -> Runs
      -> Traces
      -> Artifacts
      -> Skill Catalog
      -> Identity Permissions
```

## Near-Term Slices

1. Session Resume Semantics
   - Local JSON persistence exists for `AgentSession`, `AgentTurn`, messages,
     selected identity, and workspace.
   - Add reconnect/resume semantics for long-running sessions and UI cursors.

2. Durable Event Bus
   - Local JSON persistence exists for trace events.
   - Workspace/identity-scoped subscriptions exist for live SSE/WebSocket streams.
   - Persist event cursors for reconnect/resume.
   - Use the same event contract for CLI, SSE, and WebSocket.

3. Permission Model
   - Identity-level Skill allow/deny exists through workspace-installed identity
     Skill bindings.
   - Tool-level global/workspace/identity allow/ask/deny exists.
   - Approval records exist for risky Tool calls.
   - In-run resume after approval exists for waiting runs.
   - SecretStore and `secret_ref` resolution exist for tools.
   - Workspace-level Skill enable/disable exists.
   - Secret encryption / cloud KMS integration.

4. Workspace Catalog Hardening
   - Local JSON persistence exists for workspace-installed Skills, enabled state,
     and identity Skill bindings.
   - Workspace-scoped Skill install/list/enable/disable APIs exist.
   - Identity binding rejects Skills that are not installed in the workspace.
   - Disabled workspace Skills are not routable by identity chat.
   - Add identity-specific default scenes and available Skills.
   - Add migration path from JSON files to SQLite/Postgres for SaaS deployment.

5. UI Integration
   - Workspace switcher.
   - Identity switcher.
   - Chat session list.
   - Skill library per identity.
   - Live execution timeline based on events.

## Workflow Guidance

Use full workflows for production tasks and short workflows for draft outputs.
For example:

- `content-video-prompt-workflow`: content brief -> script -> segments ->
  storyboard -> render prompt pack.
- `content-video-full-workflow`: prompt workflow -> asset manifest -> timeline ->
  render dispatch -> review report.

This keeps interactive UI latency low while preserving a complete production path.

## Streaming Gateway Events

SSE endpoints:

- `POST /skills/{skill_id}/runs/events`
- `POST /chat/messages/events`

WebSocket endpoints:

- `WS /ws/skills/{skill_id}/runs`
- `WS /ws/chat`

Event frames use the trace event type as the event name when the runtime emits
trace data. The final frame remains `run_completed`, `run_failed`,
`agent_completed`, or `agent_failed`.

Example SSE event names:

```text
run_started
skill_started
workflow_step_started
llm_called
tool_called
tool_succeeded
workflow_step_succeeded
run_completed
```

The payload is the serialized `TraceEvent` for runtime events, including
`run_id`, `type`, `timestamp`, `message`, and `data`.

## Workspace And Session APIs

Workspace and identity APIs:

- `POST /workspaces`
- `GET /workspaces`
- `POST /workspaces/{workspace_id}/identities`
- `GET /workspaces/{workspace_id}/identities`
- `POST /workspaces/{workspace_id}/skills`
- `GET /workspaces/{workspace_id}/skills`
- `PATCH /workspaces/{workspace_id}/skills/{skill_id}`
- `POST /workspaces/{workspace_id}/identities/{identity_id}/skills`
- `GET /workspaces/{workspace_id}/identities/{identity_id}/skills`
- `POST /workspaces/{workspace_id}/secrets`
- `GET /workspaces/{workspace_id}/secrets`
- `POST /workspaces/{workspace_id}/tool-policies`
- `GET /workspaces/{workspace_id}/tool-policies`
- `POST /workspaces/{workspace_id}/identities/{identity_id}/tool-policies`
- `GET /workspaces/{workspace_id}/identities/{identity_id}/tool-policies`
- `GET /tool-approvals`
- `GET /tool-approvals/{approval_id}`
- `POST /tool-approvals/{approval_id}/approve`
- `POST /tool-approvals/{approval_id}/deny`
- `POST /runs/{run_id}/resume`

Session APIs:

- `GET /sessions`
- `GET /sessions?workspace_id=...&identity_id=...`
- `GET /sessions/{session_id}`

Chat requests can scope execution:

```json
{
  "session_id": "sess_content_ops_001",
  "message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯",
  "context": {
    "workspace_id": "workspace_content_ops",
    "identity_id": "identity_xhs_operator"
  }
}
```

When both `workspace_id` and `identity_id` are present, routing is constrained
to enabled Skills installed in that workspace and bound to that identity. The
early product shape intentionally avoids a product-level global Skill catalog;
`.bkl/catalog.json` remains the local runtime cache of loadable Tool and Skill
packages, while `.bkl/workspaces.json` owns the business-facing Skill catalog.

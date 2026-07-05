# BKL Skill Engine Development Checklist

Status: active development checklist for v0.1.

This checklist turns the technical spec and installation-form decision into implementation order. The rule is to keep one Core Engine and make CLI, API, SDK, and future Desktop reuse it.

Target business-agent architecture: [BKL Business Agent Base Architecture](BKL_Business_Agent_Base_Architecture.md).

Architecture hardening roadmap: [BKL Business Agent Base Roadmap](BKL_Business_Agent_Base_Roadmap.md).

## 1. P0 Completed Baseline

- [x] Python package skeleton with `pyproject.toml`
- [x] shared Pydantic schemas and structured errors
- [x] Tool loader for `tool.yaml`
- [x] Python Tool runner with JSON stdin/stdout
- [x] Tool registry
- [x] standard Skill loader: `SKILL.md + bkl.skill.json`
- [x] Skill registry
- [x] Skill runtime tool-calling loop
- [x] Mock model provider
- [x] OpenAI-compatible model provider
- [x] Anthropic-compatible model provider
- [x] model profiles from `bkl.yaml + .env`
- [x] in-memory run store
- [x] in-memory trace store
- [x] local artifact store
- [x] CLI basics: version, tool test, skill run
- [x] FastAPI basics: register Tool, register Skill, run Skill, query run/trace/artifact
- [x] OpenAPI Tool importer skeleton
- [x] `bkl init`
- [x] `bkl serve`
- [x] installation-form architecture document
- [x] example Skill: `examples/skills/talking-video`
- [x] example Skill: `examples/skills/wangbudong-experiment`
- [x] example Tool: `examples/tools/wangbudong_write_prompt_pack`

## 2. Current Iteration: Persistent Catalog

Goal: make Tool and Skill imports survive CLI/API/server restarts.

- [x] add `.bkl/catalog.json` schema
- [x] add `JsonCatalogStore`
- [x] persist registered Tools with id, package path, enabled flag, and validation timestamp
- [x] persist registered Skills with id, package path, enabled flag, and validation timestamp
- [x] load catalog entries during `SkillEngine.load`
- [x] make CLI `tool register` and `skill register` write catalog entries
- [x] make CLI/API list registered catalog entries after restart
- [x] keep tests isolated with explicit temporary catalog paths
- [x] document catalog behavior in README and installation-form doc

Acceptance:

- [x] registering a Tool writes `.bkl/catalog.json`
- [x] registering a Skill writes `.bkl/catalog.json`
- [x] a fresh `SkillEngine.load(..., catalog_path=...)` loads registered packages
- [x] CLI register commands can write to a specified catalog path
- [x] full test suite, ruff, and mypy pass

## 3. Next Iteration: Agent Runtime and Natural Language Management

Goal: support both direct Skill execution and Agent-orchestrated execution without duplicating runtime logic.

Design reference: [BKL Agent Runtime Engineering Plan](BKL_Agent_Runtime_Engineering.md).

- [x] add Agent runtime packages under `domain/agent/` and `application/agent/`
- [x] add Agent schemas: session, turn, route decision, action plan, action result
- [x] add Scene Mapping: `scene_id -> skill_id + defaults`
- [x] add Skill Router: natural language request -> candidate `skill_id`
- [x] add confidence threshold and user confirmation for ambiguous routing
- [x] add Input Resolver: natural language + `input.schema.json` -> input draft + missing fields
- [ ] expose input schema for schema-driven forms
- [ ] document how frontend derives form fields from `input.schema.json`
- [x] add `AgentLoop` with bounded `max_agent_steps`
- [x] add deterministic Action Registry skeleton: run Skill, list Skills, list Tools
- [ ] expand Action Registry: import, validate, configure, explain trace
- [x] add `bkl chat`
- [x] add `bkl chat --once`
- [ ] add safe management actions: configure model, import Tool, import Skill, validate, run, list catalog
- [ ] use deterministic code paths for writes
- [ ] require confirmation before file writes or destructive changes
- [ ] persist chat session trace
- [x] expose equivalent `/chat/messages` API

Acceptance:

- [ ] user can ask to import a Tool by path
- [ ] user can ask to import a Skill by path
- [x] user can ask to run a registered Skill with natural language input
- [x] user can run a Skill through `scene_id -> skill_id`
- [x] missing required input fields trigger a follow-up question
- [ ] chat actions are recorded in trace
- [ ] unsafe writes require confirmation

## 4. Architecture Hardening Iteration

Goal: make the codebase structurally ready for business agents, multi-agent orchestration, local software, cloud SaaS, and private deployments.

Design reference: [BKL Business Agent Base Architecture](BKL_Business_Agent_Base_Architecture.md) and [BKL Business Agent Base Roadmap](BKL_Business_Agent_Base_Roadmap.md).

- [x] create initial DDD package boundaries: `domain/`, `application/`, `infrastructure/`, `interfaces/`
- [x] add first application ports for RunStore, TraceStore, ArtifactStore
- [ ] define remaining ports for AgentSessionStore, PolicyEngine, SecretStore, MemoryStore, KnowledgeRetriever, EventBus
- [x] keep `SkillEngine` as the stable public facade during migration
- [x] migrate Agent schemas, scene mapping, routing, input resolution, actions, confirmation, and loop to DDD canonical paths
- [x] migrate Skill runtime to application-layer canonical path
- [x] migrate Tool executor to application-layer canonical path
- [x] migrate Skill/Tool package loaders, OpenAPI importer, Python Tool runner, and API Tool runner to infrastructure canonical paths
- [x] migrate in-memory registries, persistence stores, and trace store to infrastructure canonical paths
- [x] move Skill, Tool, Execution, and Model DTOs to domain canonical paths while keeping `core.schemas` compatibility exports
- [x] migrate CLI and HTTP adapters to `interfaces/cli` and `interfaces/http` while keeping legacy `cli/` and `api/` compatibility modules
- [x] keep legacy `agents/`, `skills/`, and `tools/` imports as compatibility adapters only
- [x] wire PolicyEngine into ToolExecutor before Python/API Tool execution
- [ ] stop Python Tool from inheriting unrestricted environment variables by default
- [ ] add durable local run/trace/artifact metadata storage
- [ ] add Agent session and turn persistence
- [x] add explicit AgentTurnState and ExecutionState enums as state-machine anchors
- [ ] convert AgentLoop into an explicit state machine
- [x] record `tool_policy_checked` and `tool_failed` trace events
- [ ] add trace parent-child span ids for agent turn -> action -> skill run -> model turn -> tool call -> artifact
- [ ] add Memory/RAG ports without making RAG mandatory for every Skill

Acceptance:

- [ ] existing CLI/API/SDK behavior remains compatible
- [ ] all write or risky actions have deterministic policy decisions
- [ ] run and trace survive restart in local mode
- [ ] Agent confirmation can pause and resume from persisted state
- [ ] multi-agent design can be implemented through task/mailbox/event ports instead of ad hoc direct calls

## 5. Server Deployment Iteration

Goal: make `bkl serve` usable by other services beyond local testing.

- [ ] API key auth middleware
- [ ] configurable workspace root
- [ ] request id and structured access logs
- [ ] Dockerfile
- [ ] health and readiness endpoints
- [ ] persistent run/trace/artifact storage adapter
- [ ] queue/worker skeleton for async runs

Acceptance:

- [ ] service can start from Docker
- [ ] authenticated API clients can register and run Skills
- [ ] unauthenticated requests are rejected when auth is enabled
- [ ] run and trace survive process restart

## 6. Desktop / Local GUI Iteration

Goal: make a local user interface without creating a second engine.

- [ ] choose shell: Tauri, Electron, or browser-only local UI
- [ ] local server lifecycle manager
- [ ] model profile screen
- [ ] Tool catalog screen
- [ ] Skill catalog screen
- [ ] run console
- [ ] trace viewer
- [ ] artifact viewer

Acceptance:

- [ ] GUI starts or connects to local `bkl serve`
- [ ] GUI manages model config through the same API
- [ ] GUI registers Tools and Skills through the same API
- [ ] GUI runs Skills and displays trace/artifacts

## 7. Built-in Skill Packs

Goal: ship useful starter packs without hardcoding product-specific behavior into the engine.

- [ ] `core/model-config-assistant`
- [ ] `core/tool-import-assistant`
- [ ] `core/skill-creator`
- [ ] `core/skill-validator`
- [ ] `core/skill-runner`
- [x] `media/talking-video` example
- [x] `media/wangbudong-experiment` example
- [ ] `data/openapi-tool-builder`

Acceptance:

- [ ] built-in packs use the same `SKILL.md + bkl.skill.json` format
- [ ] users can disable or remove built-in packs
- [ ] built-in packs are documented as examples, not engine internals

## 8. Quality Gates

Every implementation iteration must pass:

```bash
uv --cache-dir .uv-cache run --extra dev pytest
uv --cache-dir .uv-cache run --extra dev ruff check .
uv --cache-dir .uv-cache run --extra dev mypy bkl_engine
```

For model/API features, tests must use mock providers by default. Real provider tests are smoke tests only and must not print secrets.

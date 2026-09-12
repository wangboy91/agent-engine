# Agent Engine Core Engine Installation Forms

Status: accepted for v0.1 architecture, implementation still in progress.

## 1. Conclusion

Agent Engine uses one Core Engine and exposes multiple installation forms.

Do not build separate engines for CLI, server, desktop, or SaaS products. All entrypoints must call the same `SkillEngine` facade and share the same Skill, Tool, model config, run result, trace, and artifact contracts.

```text
CLI ─┐
API ─┼── SkillEngine ─── Registry / Runtime / Model Router / Tool Executor / Store
SDK ─┘

Desktop GUI ─── local HTTP ─── ae serve ─── SkillEngine
External service ─ HTTP ────── ae serve ─── SkillEngine
```

This keeps learning cost low and avoids version drift between local tools, server deployment, and future GUI products.

## 2. Installation Forms

### 2.1 CLI / SDK

Target users:

- developers
- local scripts
- CI jobs
- server batch tasks
- debugging and test workflows

Entrypoints:

```bash
ae init
ae tool register ./tools/foo
ae skill register ./skills/bar
ae skill run bar input.json --output json
ae chat
```

The CLI should be able to express the same core actions as the HTTP API.

### 2.2 Server / HTTP

Target users:

- backend services
- SaaS systems
- private deployments
- workflow systems that need stable HTTP integration

Entrypoint:

```bash
ae serve --host 0.0.0.0 --port 8000 --config agent.yaml
```

Core endpoints:

```text
POST /tools/register
GET  /tools
POST /skills/register
GET  /skills
POST /skills/{skill_id}/runs
GET  /runs/{run_id}
GET  /runs/{run_id}/trace
GET  /runs/{run_id}/artifacts
```

Production server deployments will later add auth, durable persistence, workers, queueing, rate limits, and Docker packaging. Those are server concerns and must not change the Core Engine contract.

### 2.3 Desktop / Local GUI

Target users:

- non-technical local users
- content operators
- local-first product workflows

The desktop app should not embed a separate engine implementation. It should start or connect to local `ae serve` and call the same HTTP API as any other client.

Recommended shape:

```text
Desktop shell
  starts local ae serve
  opens local Web UI
  calls http://127.0.0.1:<port>
```

Possible packaging choices:

- Tauri shell + local Python engine
- Electron shell + local Python engine
- Web UI + locally installed CLI/server

The GUI manages model config, Tool catalog, Skill catalog, run history, traces, and artifacts through HTTP.

## 3. Package Boundaries

Current repository is a single Python package. The logical boundaries should already be respected so future packaging can split without rewriting behavior.

```text
agent-engine-core
  core schemas and errors
  config loading
  Skill loader and registry
  Tool loader, executor, and registry
  Model router and providers
  Skill runtime
  Trace store
  Artifact store
  Catalog store

agent-engine-cli
  Typer commands
  ae init
  ae chat
  ae serve launcher
  CLI output formatting

agent-engine-server
  FastAPI app
  API models
  auth middleware
  deployment settings
  worker integration

agent-engine-desktop
  local UI
  local server lifecycle
  OS-specific packaging
```

Rule: CLI, API, and Desktop may format input/output, but they must not duplicate Skill loading, Tool execution, model routing, trace, artifact, or run logic.

## 4. Shared Contracts

These contracts are shared by every installation form.

### Skill Package

Only one Skill package format is supported:

```text
SKILL.md
agent.skill.json
input.schema.json
output.schema.json
examples.json
```

`SKILL.md` contains standard Skill metadata and Markdown instructions. Agent Engine runtime config belongs in `agent.skill.json`.

### Tool Package

Only one Tool package format is supported:

```text
tool.yaml
input.schema.json
output.schema.json
main.py
```

### Model Config

Only one model config shape is supported:

```text
agent.yaml
.env
```

`agent.yaml` stores provider profile configuration and environment variable names. Real secrets are stored in `.env` or a future credential store.

### RunResult

SDK, CLI, and API all return the same logical run result:

```text
run_id
status
skill_id
output
error
artifacts
trace_summary
usage
created_at
completed_at
```

CLI can render this as table or JSON, but the JSON mode must match the API/SDK shape.

## 5. State and Persistence

Current v0.1 implementation uses `.agent/catalog.json` for registered Tool and Skill packages, in-memory run/trace stores, and local artifacts. The catalog is the first persistent state layer required by CLI, Server, and future Desktop.

The persistent local state layout should be:

```text
.agent/
  catalog.json
  runs/
  traces/
data/
  artifacts/
```

Minimum catalog contents:

```text
registered tools
registered skills
package paths
enabled flags
last validation result
```

Current catalog contents:

```text
version
tools[id].path
tools[id].enabled
tools[id].last_validated_at
skills[id].path
skills[id].enabled
skills[id].last_validated_at
```

Server deployments can later replace catalog JSON with PostgreSQL and object storage. The Core Engine should depend on repository/store interfaces, not on a specific storage backend.

## 6. Natural Language Control

`ae chat` should be an orchestration layer over safe management tools, not a free-form file-editing agent.

Allowed management actions:

```text
configure model profile
test model connection
import Tool package
import Skill package
create Skill package
validate Tool
validate Skill
run Skill
list catalog
explain run trace
```

The chat layer can use model reasoning to select actions, but actual writes must go through deterministic code paths and validation.

## 7. Security Rules

Secrets:

- never write real API keys into `agent.yaml`
- never write secrets into `SKILL.md`, `tool.yaml`, prompts, traces, or artifacts
- `ae init` may write API keys to `.env`
- server deployments should move secrets to environment variables or credential stores

Server:

- local development can run without auth
- public or private network deployment must add authentication
- API Tool base URLs must be reviewed or restricted
- filesystem access must stay scoped to the configured workspace

Desktop:

- local GUI should bind to `127.0.0.1` by default
- if remote access is enabled, it must use explicit auth

## 8. Implementation Roadmap

### Iteration 1: Startup Forms

Status: implemented.

- `ae init`
- `ae serve`
- README and tech spec installation-form docs

### Iteration 2: Persistent Catalog

Status: implemented for Tool and Skill package registration.

- `.agent/catalog.json`
- catalog-backed CLI register
- catalog-backed CLI list when catalog exists
- `ae serve` loads catalog on startup

Remaining follow-up:

- idempotent import reporting
- catalog validation command
- catalog enable/disable commands
- persistent run/trace stores

### Iteration 3: Natural Language Chat

- `ae chat`
- management tools for Tool/Skill import and validation
- chat session trace
- safe confirmation before writes

### Iteration 4: Server Deployment

- API auth
- Dockerfile
- durable run/trace/artifact storage
- worker queue skeleton

### Iteration 5: Local GUI

- local server launcher
- model configuration screen
- Tool/Skill catalog screen
- run console
- trace/artifact viewer

## 9. Current Decision Status

Converged:

- one Core Engine
- multiple installation forms
- one Skill spec
- one Tool spec
- one model config shape
- CLI/API/SDK share `SkillEngine`
- desktop should call local HTTP instead of embedding duplicate runtime logic

Still open:

- exact catalog persistence schema
- whether CLI/server optional dependencies should split in packaging
- desktop shell choice
- server auth strategy
- async worker implementation
- natural language chat confirmation policy

So the architecture opinion is converged enough to continue implementation. The product and deployment details are not finished; they should be resolved through the roadmap above.

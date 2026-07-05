# AGENTS.md

## Project Overview

This repository is `bkl-skill-engine`, a Python Skill runtime for BKL AI products.
It loads local Skill packages, executes Tool packages, routes model calls, records
runs/traces/artifacts, and exposes the same core engine through SDK, CLI, and FastAPI.

The main facade is `bkl_engine.engine.SkillEngine`.

## Repository Layout

- `bkl_engine/engine.py`: public facade shared by SDK, CLI, and API.
- `bkl_engine/core/`: Pydantic schemas, config loading, and shared errors.
- `bkl_engine/skills/`: Skill loading, registry, prompt/runtime loop, and output validation.
- `bkl_engine/tools/`: Tool loading, registry, Python/API tool execution, OpenAPI importer.
- `bkl_engine/models/`: model router plus mock, OpenAI-compatible, and Anthropic-compatible providers.
- `bkl_engine/agents/`: natural-language Skill routing, scene mapping, input resolution, and agent loop.
- `bkl_engine/api/main.py`: FastAPI app and current routes.
- `bkl_engine/cli/main.py`: Typer CLI entrypoint; command split files are placeholders for later.
- `bkl_engine/storage/`: local artifact store, catalog store, and in-memory run store.
- `bkl_engine/trace/`: in-memory trace store.
- `examples/skills/`: sample Skill packages.
- `examples/tools/`: sample Tool packages.
- `examples/inputs/`: sample JSON inputs for CLI/manual tests.
- `tests/`: pytest suite, organized by subsystem.
- `doc/`: architecture and project-structure notes. Some Chinese sections are currently mojibake;
  the English README section is the most reliable quick-start reference.

## Skill And Tool Package Conventions

Skill packages use:

- `SKILL.md`: YAML frontmatter with `name` and `description`, followed by instructions.
- `bkl.skill.json`: BKL runtime config, model profile, schema paths, allowed tools.
- `schemas/input.schema.json` and `schemas/output.schema.json`: JSON Schema contracts.
- `examples/examples.json`: examples for documentation and tests.

Tool packages use:

- `tool.yaml`: tool id/type/entry/schema/runtime configuration.
- `input.schema.json` and `output.schema.json`: JSON Schema contracts.
- `main.py` for Python tools. Python tools communicate through JSON stdin/stdout and receive
  artifact context through `BKL_RUN_ID`, `BKL_TOOL_CALL_ID`, and `BKL_ARTIFACT_DIR`.

Keep Skill runtime configuration out of `SKILL.md`; put it in `bkl.skill.json`.

## Development Commands

Prefer `uv` because the default system Python may not have dependencies installed.

```bash
uv --cache-dir .uv-cache run --extra dev pytest
uv --cache-dir .uv-cache run --extra dev ruff check .
uv --cache-dir .uv-cache run --extra dev mypy bkl_engine
```

Useful CLI smoke tests:

```bash
uv --cache-dir .uv-cache run --extra dev bkl --version
uv --cache-dir .uv-cache run --extra dev bkl tool test examples/tools/subtitle_generate_srt examples/inputs/subtitle_input.json --output json
uv --cache-dir .uv-cache run --extra dev bkl skill run talking-video examples/inputs/talking-video-input.json --skills-dir examples/skills --tools-dir examples/tools --output json
uv --cache-dir .uv-cache run --extra dev bkl chat --once "generate a 60 second talking video about eye-friendly desk lamps for programmers" --skills-dir examples/skills --tools-dir examples/tools --output json
```

The project declares `requires-python = ">=3.12"` in `pyproject.toml`.

## Known Baseline Notes

At the time this file was added, running:

```bash
uv --cache-dir .uv-cache run --extra dev pytest
```

used CPython 3.14.3 and produced `45 passed, 4 failed, 1 warning`. The failures were all
from `wangbudong_write_prompt_pack` execution paths:

- `tests/test_agent_runtime.py::test_agent_loop_routes_natural_language_to_registered_skill`
- `tests/test_python_tool_runner.py::test_wangbudong_prompt_pack_tool_writes_markdown_files`
- `tests/test_python_tool_runner.py::test_python_tool_runner_resolves_relative_artifact_dir_from_caller_cwd`
- `tests/test_skill_runtime.py::test_skill_engine_runs_wangbudong-experiment_skill`

The immediate cause is that `examples/tools/wangbudong_write_prompt_pack/main.py` contains
mojibake and broken Python string literals, so the Python tool exits with code 1.

## Working Guidelines

- Do not commit real secrets. `.env` is ignored and may contain local credentials.
- Generated artifacts belong under `data/`, which is ignored.
- `.bkl/catalog.json` may be created by registration commands; use `--catalog` for isolated tests.
- Keep changes scoped to the active subsystem and follow the existing Pydantic/Typer/FastAPI style.
- Add or update tests when changing runtime behavior, schemas, model provider request mapping,
  CLI/API behavior, or Skill/Tool loading.
- For narrow examples or fixture fixes, prefer focused tests over broad end-to-end rewrites.
- Preserve public behavior of `SkillEngine` unless intentionally changing the SDK/API contract.
- Use structured JSON/schema APIs for Skill and Tool contracts instead of ad hoc parsing.
- Be careful with files that already contain mojibake; fix encoding deliberately rather than making
  partial text edits that leave invalid Python or invalid JSON.

## Common Verification Targets

- Skill loader changes: `tests/test_skill_loader.py`
- Tool loader/runner changes: `tests/test_tool_loader.py`, `tests/test_python_tool_runner.py`
- Skill runtime changes: `tests/test_skill_runtime.py`
- Agent routing changes: `tests/test_agent_runtime.py`
- CLI/API changes: `tests/test_cli.py`, `tests/test_api_cli.py`
- Model config/provider changes: `tests/test_model_config.py`, `tests/test_model_providers.py`
- Catalog/artifact/trace storage changes: `tests/test_catalog_store.py`, `tests/test_stores.py`

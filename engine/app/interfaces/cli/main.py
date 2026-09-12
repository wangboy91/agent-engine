"""Typer command line entrypoint."""

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any

import typer
import uvicorn
import yaml
from rich.console import Console

from app import __version__
from app.application.agent import HandleAgentMessageCommand, HandleAgentMessageUseCase
from app.application.skill import RunSkillCommand, RunSkillUseCase
from app.domain.errors import AgentEngineError
from app.domain.policy import PolicyEffect
from app.domain.tool import ToolExecutionContext
from app.engine import SkillEngine
from app.infrastructure.package_loaders.skill_loader import load_skill
from app.infrastructure.package_loaders.tool_loader import load_tool
from app.infrastructure.tool_runners.python_tool import PythonToolRunner

app = typer.Typer(help="Agent Engine command line interface.")
tool_app = typer.Typer(help="Tool commands.")
skill_app = typer.Typer(help="Skill commands.")
run_app = typer.Typer(help="Run commands.")
trace_app = typer.Typer(help="Trace commands.")
workspace_app = typer.Typer(help="Workspace and identity resource commands.")
console = Console()
MODEL_PROTOCOLS = {"mock", "openai-compatible", "anthropic"}
DEFAULT_CONFIG_PATH = Path("agent.yaml")
DEFAULT_CATALOG_PATH = Path(".agent/catalog.json")


def version_callback(value: bool) -> None:
    if value:
        console.print(f"agent-engine {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Run Agent Engine commands."""


@app.command("init")
def init_config(
    protocol: Annotated[str, typer.Option(help="Model protocol to configure.")] = "mock",
    profile: Annotated[str, typer.Option(help="Model profile name.")] = "mock",
    base_url: Annotated[str | None, typer.Option(help="Provider base URL.")] = None,
    model: Annotated[str | None, typer.Option(help="Model name.")] = None,
    api_key: Annotated[str | None, typer.Option(help="API key written only to .env.")] = None,
    api_key_env: Annotated[
        str | None,
        typer.Option(help="Environment variable name for API key."),
    ] = None,
    config: Annotated[Path, typer.Option(help="Config file to write.")] = DEFAULT_CONFIG_PATH,
    env_file: Annotated[Path | None, typer.Option(help=".env file to write API key into.")] = None,
    force: Annotated[bool, typer.Option(help="Overwrite an existing config file.")] = False,
    output: Annotated[str, typer.Option(help="Output format: table or json.")] = "table",
) -> None:
    """Initialize model configuration for the engine."""

    if protocol not in MODEL_PROTOCOLS:
        raise typer.BadParameter(f"protocol must be one of: {', '.join(sorted(MODEL_PROTOCOLS))}")
    if config.exists() and not force:
        raise typer.BadParameter(f"Config already exists: {config}. Use --force to overwrite.")

    resolved_model = model or ("mock-tool-calling" if protocol == "mock" else None)
    if resolved_model is None:
        raise typer.BadParameter("--model is required for non-mock protocols")
    if protocol != "mock" and not base_url:
        raise typer.BadParameter("--base-url is required for non-mock protocols")

    resolved_api_key_env = api_key_env or _default_api_key_env(protocol)
    profile_config: dict[str, Any] = {
        "protocol": protocol,
        "model": resolved_model,
    }
    if base_url is not None:
        profile_config["base_url"] = base_url
    if resolved_api_key_env is not None:
        profile_config["api_key_env"] = resolved_api_key_env

    config_data = {
        "models": {
            "active_profile": profile,
            "profiles": {
                profile: profile_config,
            },
        }
    }
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        yaml.safe_dump(config_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    resolved_env_file = env_file or config.parent / ".env"
    if api_key and resolved_api_key_env:
        _write_dotenv_value(resolved_env_file, resolved_api_key_env, api_key)

    summary = {
        "config": str(config),
        "env_file": str(resolved_env_file),
        "active_profile": profile,
        "protocol": protocol,
        "model": resolved_model,
        "api_key_env": resolved_api_key_env,
    }
    if output == "json":
        typer.echo(json.dumps(summary, ensure_ascii=False))
    else:
        console.print(summary)


@app.command("serve")
def serve(
    host: Annotated[str, typer.Option(help="Host to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to bind.")] = 8000,
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to load.")] = (
        DEFAULT_CATALOG_PATH
    ),
    reload: Annotated[bool, typer.Option(help="Enable uvicorn reload.")] = False,
) -> None:
    """Start the FastAPI service."""

    from app.interfaces.http.main import create_app

    engine = SkillEngine.load(config, catalog_path=catalog)
    api = create_app(engine)
    uvicorn.run(api, host=host, port=port, reload=reload)


@app.command("gateway")
def gateway(
    host: Annotated[str, typer.Option(help="Host to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to bind.")] = 8000,
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to load.")] = (
        DEFAULT_CATALOG_PATH
    ),
    reload: Annotated[bool, typer.Option(help="Enable uvicorn reload.")] = False,
) -> None:
    """Start the HTTP/SSE/WebSocket gateway."""

    from app.interfaces.http.main import create_app

    engine = SkillEngine.load(config, catalog_path=catalog)
    api = create_app(engine)
    uvicorn.run(api, host=host, port=port, reload=reload)


@app.command("chat")
def chat(
    once: Annotated[
        str | None,
        typer.Option(help="Run one natural-language Agent turn and exit."),
    ] = None,
    scene: Annotated[str | None, typer.Option(help="Scene id to route deterministically.")] = None,
    skill: Annotated[str | None, typer.Option(help="Explicit skill id to run.")] = None,
    input_json: Annotated[
        Path | None,
        typer.Option("--input", help="Optional JSON input draft."),
    ] = None,
    skills_dir: Annotated[Path, typer.Option(help="Directory containing Skill packages.")] = (
        Path("resources/skills")
    ),
    tools_dir: Annotated[Path, typer.Option(help="Directory containing Tool packages.")] = (
        Path("resources/tools")
    ),
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    output: Annotated[str, typer.Option(help="Output format: table or json.")] = "table",
    view: Annotated[
        str,
        typer.Option(help="Response view: full, prompts, or trace."),
    ] = "full",
) -> None:
    """Run the Agent orchestration layer."""

    engine = SkillEngine.load(config) if config is not None else SkillEngine.create_for_testing()
    _register_all(engine, tools_dir=tools_dir, skills_dir=skills_dir)
    use_case = HandleAgentMessageUseCase(engine)
    input_data = _read_json(input_json) if input_json is not None else None

    if once is not None:
        try:
            response = asyncio.run(
                use_case.execute(
                    HandleAgentMessageCommand(
                        message=once,
                        scene_id=scene,
                        skill_id=skill,
                        input=input_data or {},
                    )
                )
            )
        except AgentEngineError as exc:
            _print_error(exc, output)
            raise typer.Exit(1) from exc
        _print_agent_response(response.model_dump(mode="json"), output, view)
        return

    console.print("ae chat interactive mode. Type 'exit' to quit.")
    while True:
        message = typer.prompt("ae")
        if message.strip().lower() in {"exit", "quit"}:
            return
        try:
            response = asyncio.run(
                use_case.execute(
                    HandleAgentMessageCommand(message=message, scene_id=scene, skill_id=skill)
                )
            )
        except AgentEngineError as exc:
            _print_error(exc, output)
            continue
        _print_agent_response(response.model_dump(mode="json"), output, view)


@tool_app.command("register")
def tool_register(
    path: Path,
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to write.")] = (
        DEFAULT_CATALOG_PATH
    ),
) -> None:
    engine = SkillEngine.load(config, catalog_path=catalog)
    tool = asyncio.run(engine.register_tool(path))
    console.print_json(data=tool.model_dump(mode="json"))


@tool_app.command("list")
def tool_list(
    tools_dir: Path = Path("resources/tools"),
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to read.")] = (
        DEFAULT_CATALOG_PATH
    ),
) -> None:
    if catalog is not None and catalog.exists():
        engine = SkillEngine.load(config, catalog_path=catalog)
        tools = engine.tool_registry.list_tools()
    else:
        tools = [load_tool(path) for path in _iter_package_dirs(tools_dir, "tool.yaml")]
    console.print_json(data=[tool.model_dump(mode="json") for tool in tools])


@tool_app.command("test")
def tool_test(path: Path, input_json: Path, output: str = "table") -> None:
    tool = load_tool(path)
    payload = _read_json(input_json)
    result = asyncio.run(
        PythonToolRunner().execute(
            tool,
            payload,
            _tool_context_for_cli(),
        )
    )
    if output == "json":
        typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    else:
        console.print(result.model_dump(mode="json"))


@skill_app.command("register")
def skill_register(
    path: Path,
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to write.")] = (
        DEFAULT_CATALOG_PATH
    ),
) -> None:
    engine = SkillEngine.load(config, catalog_path=catalog)
    skill = asyncio.run(engine.register_skill(path))
    console.print_json(data=skill.model_dump(mode="json"))


@skill_app.command("list")
def skill_list(
    skills_dir: Path = Path("resources/skills"),
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to read.")] = (
        DEFAULT_CATALOG_PATH
    ),
) -> None:
    if catalog is not None and catalog.exists():
        engine = SkillEngine.load(config, catalog_path=catalog)
        skills = engine.skill_registry.list_skills()
    else:
        skills = [load_skill(path) for path in _iter_skill_dirs(skills_dir)]
    console.print_json(
        data=[skill.model_dump(mode="json") for skill in skills]
    )


@skill_app.command("run")
def skill_run(
    skill_id: str,
    input_json: Path,
    skills_dir: Path = Path("resources/skills"),
    tools_dir: Path = Path("resources/tools"),
    config: Path | None = None,
    output: str = "table",
) -> None:
    engine = SkillEngine.load(config) if config is not None else SkillEngine.create_for_testing()
    _register_all(engine, tools_dir=tools_dir, skills_dir=skills_dir)
    result = asyncio.run(
        RunSkillUseCase(engine).execute(
            RunSkillCommand(skill_id=skill_id, input=_read_json(input_json))
        )
    )
    if output == "json":
        typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    else:
        console.print(result.model_dump(mode="json"))


@run_app.command("list")
def run_list() -> None:
    engine = SkillEngine.load()
    console.print_json(data=[run.model_dump(mode="json") for run in engine.run_store.list_runs()])


@trace_app.command("show")
def trace_show(run_id: str) -> None:
    engine = SkillEngine.load()
    console.print_json(
        data=[event.model_dump(mode="json") for event in engine.trace_store.list_events(run_id)]
    )


@workspace_app.command("ensure")
def workspace_ensure(
    workspace_id: str,
    identity_id: str,
    workspace_name: Annotated[str | None, typer.Option(help="Workspace display name.")] = None,
    identity_name: Annotated[str | None, typer.Option(help="Identity display name.")] = None,
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to load/write.")] = (
        DEFAULT_CATALOG_PATH
    ),
    output: Annotated[str, typer.Option(help="Output format: table or json.")] = "table",
) -> None:
    engine = SkillEngine.load(config, catalog_path=catalog)
    result = _ensure_workspace_identity(
        engine,
        workspace_id,
        identity_id,
        workspace_name,
        identity_name,
    )
    _print_data(result, output)


@workspace_app.command("scan")
def workspace_scan(
    workspace_id: str,
    identity_id: str,
    skills_dir: Annotated[
        Path,
        typer.Option(help="Directory containing Skill resource packages."),
    ] = Path("resources/skills"),
    tools_dir: Annotated[
        Path | None,
        typer.Option(help="Directory containing Tool resource packages."),
    ] = Path("resources/tools"),
    workspace_name: Annotated[str | None, typer.Option(help="Workspace display name.")] = None,
    identity_name: Annotated[str | None, typer.Option(help="Identity display name.")] = None,
    bind_to_identity: Annotated[
        bool,
        typer.Option(help="Bind scanned Skills to the identity."),
    ] = True,
    allow_tools_for_identity: Annotated[
        bool,
        typer.Option(help="Grant allow tool policies to the identity."),
    ] = True,
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to load/write.")] = (
        DEFAULT_CATALOG_PATH
    ),
    output: Annotated[str, typer.Option(help="Output format: table or json.")] = "table",
) -> None:
    engine = SkillEngine.load(config, catalog_path=catalog)
    _ensure_workspace_identity(
        engine,
        workspace_id,
        identity_id,
        workspace_name,
        identity_name,
    )
    result = _scan_workspace_resources(
        engine,
        workspace_id,
        identity_id,
        skills_dir,
        tools_dir,
        bind_to_identity=bind_to_identity,
        allow_tools_for_identity=allow_tools_for_identity,
    )
    _print_data(result, output)


@workspace_app.command("register-skill")
def workspace_register_skill(
    workspace_id: str,
    identity_id: str,
    path: Path,
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to load/write.")] = (
        DEFAULT_CATALOG_PATH
    ),
    output: Annotated[str, typer.Option(help="Output format: table or json.")] = "table",
) -> None:
    engine = SkillEngine.load(config, catalog_path=catalog)
    _ensure_workspace_identity(engine, workspace_id, identity_id, None, None)
    result = _register_identity_skill(engine, workspace_id, identity_id, path)
    _print_data(result, output)


@workspace_app.command("register-tool")
def workspace_register_tool(
    workspace_id: str,
    identity_id: str,
    path: Path,
    effect: Annotated[
        PolicyEffect,
        typer.Option(help="Tool policy effect for this identity."),
    ] = "allow",
    config: Annotated[Path | None, typer.Option(help="Config file to load.")] = None,
    catalog: Annotated[Path | None, typer.Option(help="Catalog file to load/write.")] = (
        DEFAULT_CATALOG_PATH
    ),
    output: Annotated[str, typer.Option(help="Output format: table or json.")] = "table",
) -> None:
    engine = SkillEngine.load(config, catalog_path=catalog)
    _ensure_workspace_identity(engine, workspace_id, identity_id, None, None)
    result = _register_identity_tool(engine, workspace_id, identity_id, path, effect)
    _print_data(result, output)


def _register_all(engine: SkillEngine, tools_dir: Path, skills_dir: Path) -> None:
    for path in _iter_package_dirs(tools_dir, "tool.yaml"):
        asyncio.run(engine.register_tool(path))
    for path in _iter_skill_dirs(skills_dir):
        asyncio.run(engine.register_skill(path))


def _iter_package_dirs(root: Path, marker: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path.parent for path in root.rglob(marker))


def _iter_skill_dirs(root: Path) -> list[Path]:
    return _iter_package_dirs(root, "SKILL.md")


def _read_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise typer.BadParameter(f"JSON input must be an object: {path}")
    return data


def _print_agent_response(data: dict[str, object], output: str, view: str) -> None:
    data = _agent_response_view(data, view)
    if output == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
    else:
        console.print_json(data=data)


def _print_error(exc: AgentEngineError, output: str) -> None:
    data = {
        "status": "failed",
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "retryable": exc.retryable,
        },
    }
    if output == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
    else:
        console.print_json(data=data)


def _print_data(data: dict[str, object], output: str) -> None:
    if output == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
    else:
        console.print_json(data=data)


def _ensure_workspace_identity(
    engine: SkillEngine,
    workspace_id: str,
    identity_id: str,
    workspace_name: str | None,
    identity_name: str | None,
) -> dict[str, object]:
    try:
        workspace = engine.workspace_store.create_workspace(
            workspace_id,
            workspace_name or workspace_id,
        )
    except AgentEngineError as exc:
        if exc.code != "WORKSPACE_ALREADY_EXISTS":
            raise
        workspace = engine.workspace_store.get_workspace(workspace_id)

    try:
        identity = engine.workspace_store.create_identity(
            workspace_id,
            identity_id,
            identity_name or identity_id,
        )
    except AgentEngineError as exc:
        if exc.code != "IDENTITY_ALREADY_EXISTS":
            raise
        identity = engine.workspace_store.get_identity(workspace_id, identity_id)

    return {
        "workspace": workspace.model_dump(mode="json"),
        "identity": identity.model_dump(mode="json"),
    }


def _scan_workspace_resources(
    engine: SkillEngine,
    workspace_id: str,
    identity_id: str,
    skills_dir: Path,
    tools_dir: Path | None,
    bind_to_identity: bool,
    allow_tools_for_identity: bool,
) -> dict[str, object]:
    registered_tool_ids: list[str] = []
    identity_tool_ids: list[str] = []
    if tools_dir is not None:
        for tool_path in _iter_package_dirs(tools_dir, "tool.yaml"):
            if allow_tools_for_identity:
                result = _register_identity_tool(
                    engine,
                    workspace_id,
                    identity_id,
                    tool_path,
                    "allow",
                )
                tool_data = result["tool"]
                if isinstance(tool_data, dict):
                    registered_tool_ids.append(str(tool_data["id"]))
                    identity_tool_ids.append(str(tool_data["id"]))
            else:
                tool = asyncio.run(engine.register_tool(tool_path))
                registered_tool_ids.append(tool.id)

    registered_skill_ids: list[str] = []
    installed_skill_ids: list[str] = []
    bound_skill_ids: list[str] = []
    for skill_path in _iter_package_dirs(skills_dir, "agent.skill.json"):
        skill = asyncio.run(engine.register_skill(skill_path))
        registered_skill_ids.append(skill.id)
        engine.workspace_store.install_skill(
            workspace_id,
            skill.id,
            display_name=skill.name,
            enabled=True,
        )
        installed_skill_ids.append(skill.id)
        if bind_to_identity:
            engine.workspace_store.bind_skill(workspace_id, identity_id, skill.id)
            bound_skill_ids.append(skill.id)

    return {
        "workspace_id": workspace_id,
        "identity_id": identity_id,
        "skills_dir": skills_dir.as_posix(),
        "tools_dir": tools_dir.as_posix() if tools_dir is not None else None,
        "registered_tools": registered_tool_ids,
        "identity_tools": identity_tool_ids,
        "registered_skills": registered_skill_ids,
        "installed_skills": installed_skill_ids,
        "bound_skills": bound_skill_ids,
    }


def _register_identity_skill(
    engine: SkillEngine,
    workspace_id: str,
    identity_id: str,
    path: Path,
) -> dict[str, object]:
    skill = asyncio.run(engine.register_skill(path))
    workspace_skill = engine.workspace_store.install_skill(
        workspace_id,
        skill.id,
        display_name=skill.name,
        enabled=True,
    )
    identity = engine.workspace_store.bind_skill(workspace_id, identity_id, skill.id)
    return {
        "workspace_id": workspace_id,
        "identity_id": identity_id,
        "skill": skill.model_dump(mode="json"),
        "workspace_skill": workspace_skill.model_dump(mode="json"),
        "identity": identity.model_dump(mode="json"),
    }


def _register_identity_tool(
    engine: SkillEngine,
    workspace_id: str,
    identity_id: str,
    path: Path,
    effect: PolicyEffect,
) -> dict[str, object]:
    tool = asyncio.run(engine.register_tool(path))
    rule = engine.policy_store.set_tool_rule(
        tool.id,
        effect,
        workspace_id=workspace_id,
        identity_id=identity_id,
        reason="cli workspace registration",
    )
    return {
        "workspace_id": workspace_id,
        "identity_id": identity_id,
        "tool": tool.model_dump(mode="json"),
        "policy": rule.model_dump(mode="json"),
    }


def _agent_response_view(data: dict[str, object], view: str) -> dict[str, object]:
    if view == "full":
        return data
    if view == "trace":
        raw_output = data.get("output")
        skill_output = raw_output if isinstance(raw_output, dict) else {}
        raw_action_results = data.get("action_results")
        action_results = raw_action_results if isinstance(raw_action_results, list) else []
        if action_results and isinstance(action_results[0], dict):
            first_action = action_results[0]
        else:
            first_action = {}
        trace_summary = (
            first_action.get("trace_summary", {})
            if isinstance(first_action, dict)
            else {}
        )
        return {
            "status": data.get("status"),
            "run_ids": data.get("run_ids", []),
            "trace_summary": trace_summary,
            "workflow_steps": skill_output.get("step_runs", []),
            "artifacts": data.get("artifacts", []),
        }

    if view != "prompts":
        raise typer.BadParameter("view must be one of: full, prompts, trace")

    raw_output = data.get("output")
    skill_output = raw_output if isinstance(raw_output, dict) else {}
    return {
        "status": data.get("status"),
        "run_ids": data.get("run_ids", []),
        "storyboard": skill_output.get("storyboard"),
        "render_prompt_pack": skill_output.get("render_prompt_pack"),
        "artifacts": data.get("artifacts", []),
    }


def _default_api_key_env(protocol: str) -> str | None:
    if protocol == "openai-compatible":
        return "OPENAI_AUTH_TOKEN"
    if protocol == "anthropic":
        return "ANTHROPIC_AUTH_TOKEN"
    return None


def _write_dotenv_value(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    assignment = f"{key}={value}"
    for index, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[index] = assignment
            break
    else:
        lines.append(assignment)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _tool_context_for_cli() -> ToolExecutionContext:
    return ToolExecutionContext(
        run_id="cli_run",
        tool_call_id="cli_tool_call",
        artifact_dir=Path("data/artifacts/cli_run/cli_tool_call"),
    )


app.add_typer(tool_app, name="tool")
app.add_typer(skill_app, name="skill")
app.add_typer(run_app, name="run")
app.add_typer(trace_app, name="trace")
app.add_typer(workspace_app, name="workspace")


if __name__ == "__main__":
    app()

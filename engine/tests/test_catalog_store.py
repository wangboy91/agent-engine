import json
from pathlib import Path

from app.domain.execution import RunResult
from app.engine import SkillEngine


def test_engine_persists_and_loads_catalog_entries(tmp_path: Path) -> None:
    config_path = _write_mock_config(tmp_path)
    catalog_path = tmp_path / ".bkl" / "catalog.json"

    engine = SkillEngine.load(config_path, catalog_path=catalog_path)
    tool = _run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    skill = _run(engine.register_skill("resources/skills/talking-video"))

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["version"] == 1
    assert catalog["tools"]["subtitle_generate_srt"]["id"] == tool.id
    assert (
        catalog["tools"]["subtitle_generate_srt"]["path"]
        == "resources/tools/subtitle_generate_srt"
    )
    assert catalog["tools"]["subtitle_generate_srt"]["enabled"] is True
    assert catalog["skills"]["talking-video"]["id"] == skill.id
    assert catalog["skills"]["talking-video"]["path"] == "resources/skills/talking-video"
    assert catalog["skills"]["talking-video"]["enabled"] is True

    reloaded = SkillEngine.load(config_path, catalog_path=catalog_path)

    assert [registered_tool.id for registered_tool in reloaded.tool_registry.list_tools()] == [
        "subtitle_generate_srt"
    ]
    assert [registered_skill.id for registered_skill in reloaded.skill_registry.list_skills()] == [
        "talking-video"
    ]


def test_engine_load_migrates_legacy_examples_catalog_paths(tmp_path: Path) -> None:
    config_path = _write_mock_config(tmp_path)
    catalog_path = tmp_path / ".bkl" / "catalog.json"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text(
        json.dumps(
            {
                "version": 1,
                "tools": {
                    "subtitle_generate_srt": {
                        "id": "subtitle_generate_srt",
                        "path": "examples/tools/subtitle_generate_srt",
                        "enabled": True,
                    }
                },
                "skills": {
                    "talking-video": {
                        "id": "talking-video",
                        "path": "examples/skills/talking-video",
                        "enabled": True,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    reloaded = SkillEngine.load(config_path, catalog_path=catalog_path)

    assert [registered_tool.id for registered_tool in reloaded.tool_registry.list_tools()] == [
        "subtitle_generate_srt"
    ]
    assert [registered_skill.id for registered_skill in reloaded.skill_registry.list_skills()] == [
        "talking-video"
    ]


def test_engine_can_disable_catalog_loading(tmp_path: Path) -> None:
    config_path = _write_mock_config(tmp_path)

    engine = SkillEngine.load(config_path, catalog_path=None)
    _run(engine.register_tool("resources/tools/subtitle_generate_srt"))

    assert not (tmp_path / ".bkl" / "catalog.json").exists()


def test_engine_load_persists_workspace_and_session_state(tmp_path: Path) -> None:
    config_path = _write_mock_config(tmp_path)
    catalog_path = tmp_path / ".bkl" / "catalog.json"

    engine = SkillEngine.load(config_path, catalog_path=catalog_path)
    _run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    _run(engine.register_skill("resources/skills/talking-video"))
    engine.workspace_store.create_workspace("workspace_content_ops", "Content Ops")
    engine.workspace_store.create_identity(
        "workspace_content_ops",
        "identity_xhs_operator",
        "小红书运营",
    )
    engine.workspace_store.install_skill("workspace_content_ops", "talking-video", "口播视频")
    engine.workspace_store.bind_skill(
        "workspace_content_ops",
        "identity_xhs_operator",
        "talking-video",
    )
    engine.session_store.ensure_session(
        "sess_001",
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
    )

    reloaded = SkillEngine.load(config_path, catalog_path=catalog_path)

    assert reloaded.workspace_store.get_workspace("workspace_content_ops").name == "Content Ops"
    assert reloaded.workspace_store.list_identity_skill_ids(
        "workspace_content_ops",
        "identity_xhs_operator",
    ) == ["talking-video"]
    assert reloaded.session_store.get("sess_001").workspace_id == "workspace_content_ops"


def test_engine_load_persists_run_and_trace_state(tmp_path: Path) -> None:
    config_path = _write_mock_config(tmp_path)
    catalog_path = tmp_path / ".bkl" / "catalog.json"

    engine = SkillEngine.load(config_path, catalog_path=catalog_path)
    engine.run_store.save(RunResult(run_id="run_001", status="succeeded", skill_id="demo"))
    engine.trace_store.record(
        "run_001",
        "skill_started",
        "Skill started",
        {"workspace_id": "workspace_content_ops"},
    )

    reloaded = SkillEngine.load(config_path, catalog_path=catalog_path)

    assert reloaded.run_store.get("run_001").status == "succeeded"
    assert reloaded.trace_store.list_events("run_001")[0].data["workspace_id"] == (
        "workspace_content_ops"
    )


def test_engine_load_persists_tool_policy_state(tmp_path: Path) -> None:
    config_path = _write_mock_config(tmp_path)
    catalog_path = tmp_path / ".bkl" / "catalog.json"

    engine = SkillEngine.load(config_path, catalog_path=catalog_path)
    engine.policy_store.set_tool_rule(
        "subtitle_generate_srt",
        "ask",
        workspace_id="workspace_content_ops",
        reason="requires operator confirmation",
    )

    reloaded = SkillEngine.load(config_path, catalog_path=catalog_path)
    rule = reloaded.policy_store.find_tool_rule(
        "subtitle_generate_srt",
        workspace_id="workspace_content_ops",
    )

    assert rule is not None
    assert rule.effect == "ask"
    assert rule.reason == "requires operator confirmation"


def test_engine_load_persists_secret_state(tmp_path: Path) -> None:
    config_path = _write_mock_config(tmp_path)
    catalog_path = tmp_path / ".bkl" / "catalog.json"

    engine = SkillEngine.load(config_path, catalog_path=catalog_path)
    engine.secret_store.set_secret(
        "VIDEO_API_KEY",
        "secret-value",
        workspace_id="workspace_content_ops",
    )

    reloaded = SkillEngine.load(config_path, catalog_path=catalog_path)

    assert reloaded.secret_store.get_secret(
        "VIDEO_API_KEY",
        "workspace_content_ops",
    ).value == "secret-value"


def _write_mock_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "bkl.yaml"
    config_path.write_text(
        "\n".join(
            [
                "models:",
                "  active_profile: mock",
                "  profiles:",
                "    mock:",
                "      protocol: mock",
                "      model: mock-tool-calling",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def _run(coroutine):  # type: ignore[no-untyped-def]
    import asyncio

    return asyncio.run(coroutine)

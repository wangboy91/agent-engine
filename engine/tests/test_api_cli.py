import json
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app.application.execution.skill_runtime import SkillRuntimeError
from app.domain.model import ModelResponse
from app.engine import SkillEngine
from app.interfaces.cli.main import app as cli_app
from app.interfaces.http.main import create_app


def test_cli_tool_test_executes_python_tool() -> None:
    result = CliRunner().invoke(
        cli_app,
        [
            "tool",
            "test",
            "resources/tools/subtitle_generate_srt",
            "resources/inputs/subtitle_input.json",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["output"]["srt_path"] == "subtitle.srt"


def test_cli_skill_run_executes_default_mock_chain() -> None:
    result = CliRunner().invoke(
        cli_app,
        [
            "skill",
            "run",
            "talking-video",
            "resources/inputs/talking-video-input.json",
            "--skills-dir",
            "resources/skills",
            "--tools-dir",
            "resources/tools",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "succeeded"
    assert payload["output"]["subtitle_path"] == "subtitle.srt"


def test_cli_skill_run_can_load_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.yaml"
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
    result = CliRunner().invoke(
        cli_app,
        [
            "skill",
            "run",
            "talking-video",
            "resources/inputs/talking-video-input.json",
            "--skills-dir",
            "resources/skills",
            "--tools-dir",
            "resources/tools",
            "--config",
            str(config_path),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "succeeded"


def test_fastapi_registers_and_runs_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    tool_response = client.post(
        "/tools/register",
        json={"path": "resources/tools/subtitle_generate_srt"},
    )
    assert tool_response.status_code == 200
    assert tool_response.json()["id"] == "subtitle_generate_srt"

    skill_response = client.post(
        "/skills/register",
        json={"path": "resources/skills/talking-video"},
    )
    assert skill_response.status_code == 200
    assert skill_response.json()["id"] == "talking-video"

    run_response = client.post(
        "/skills/talking-video/runs",
        json={
            "input": {
                "topic": "适合程序员的护眼台灯",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
            "context": {"user_id": "user_001"},
            "mode": "sync",
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "succeeded"

    trace_response = client.get(f"/runs/{run_payload['run_id']}/trace")
    assert trace_response.status_code == 200
    assert any(event["type"] == "tool_succeeded" for event in trace_response.json())


def test_legacy_runtime_console_ui_removed(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    assert client.get("/ui").status_code == 404
    assert client.get("/ui/assets/runtime-console.js").status_code == 404


def test_fastapi_workspace_skill_scan_registers_installs_and_binds(
    tmp_path: Path,
) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_xhs_operator", "name": "小红书运营"},
    )

    response = client.post(
        "/workspaces/workspace_content_ops/skills/scan",
        json={
            "skills_dir": "resources/skills",
            "tools_dir": "resources/tools",
            "identity_id": "identity_xhs_operator",
            "bind_to_identity": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "content-video-workflow" in payload["registered_skills"]
    assert "content-video-workflow" in payload["installed_skills"]
    assert "content-video-workflow" in payload["bound_skills"]
    assert "mock_video_render" in payload["registered_tools"]
    assert "mock_video_render" in payload["identity_tools"]

    identity_skills = client.get(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/skills"
    )
    assert identity_skills.status_code == 200
    assert any(skill["id"] == "content-video-workflow" for skill in identity_skills.json())

    identity_tools = client.get(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/tool-policies"
    )
    assert identity_tools.status_code == 200
    assert any(rule["tool_id"] == "mock_video_render" for rule in identity_tools.json())


def test_fastapi_identity_registers_single_skill_and_tool_resource(
    tmp_path: Path,
) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_xhs_operator", "name": "小红书运营"},
    )

    skill_response = client.post(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/skills/register",
        json={"path": "resources/skills/talking-video"},
    )
    tool_response = client.post(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/tools/register",
        json={"path": "resources/tools/subtitle_generate_srt"},
    )

    assert skill_response.status_code == 200
    assert skill_response.json()["skill"]["id"] == "talking-video"
    assert "talking-video" in skill_response.json()["identity"]["skill_ids"]
    assert tool_response.status_code == 200
    assert tool_response.json()["tool"]["id"] == "subtitle_generate_srt"
    assert tool_response.json()["policy"]["identity_id"] == "identity_xhs_operator"


def test_cli_chat_once_runs_skill_from_natural_language() -> None:
    result = CliRunner().invoke(
        cli_app,
        [
            "chat",
            "--once",
            "帮我生成60秒小红书口播视频，主题是程序员护眼台灯",
            "--skills-dir",
            "resources/skills",
            "--tools-dir",
            "resources/tools",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["route_decision"]["skill_id"] == "talking-video"
    assert payload["output"]["subtitle_path"] == "subtitle.srt"
    assert payload["action_results"][0]["trace_summary"]["tool_called"] == 1


def test_cli_chat_once_runs_content_workflow_from_plain_topic() -> None:
    result = CliRunner().invoke(
        cli_app,
        [
            "chat",
            "--once",
            "介绍openspec",
            "--skill",
            "content-video-workflow",
            "--skills-dir",
            "resources/skills",
            "--tools-dir",
            "resources/tools",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["route_decision"]["input_draft"]["topic"] == "介绍openspec"
    assert payload["route_decision"]["input_draft"]["duration_seconds"] == 60
    assert payload["output"]["render_prompt_pack"]["prompts"]


def test_cli_chat_once_can_print_prompt_view_for_content_workflow() -> None:
    result = CliRunner().invoke(
        cli_app,
        [
            "chat",
            "--once",
            "介绍openspec",
            "--skill",
            "content-video-workflow",
            "--skills-dir",
            "resources/skills",
            "--tools-dir",
            "resources/tools",
            "--view",
            "prompts",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert "output" not in payload
    assert payload["storyboard"]["shots"]
    assert payload["render_prompt_pack"]["prompts"]


def test_cli_chat_once_can_print_trace_view_for_content_workflow() -> None:
    result = CliRunner().invoke(
        cli_app,
        [
            "chat",
            "--once",
            "介绍openspec",
            "--skill",
            "content-video-workflow",
            "--skills-dir",
            "resources/skills",
            "--tools-dir",
            "resources/tools",
            "--view",
            "trace",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["trace_summary"]["workflow_step_succeeded"] == 7
    assert len(payload["workflow_steps"]) == 7
    assert payload["workflow_steps"][0]["skill_id"] == "content-brief-planner"
    assert payload["workflow_steps"][0]["trace_summary"]["llm_called"] == 1
    assert payload["workflow_steps"][-1]["skill_id"] == "render-prompt-builder"


def test_cli_chat_once_prints_structured_error_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fail_execute(self, command):  # type: ignore[no-untyped-def]
        del self, command
        raise SkillRuntimeError(
            "WORKFLOW_STEP_FAILED",
            "Workflow step failed: storyboard (storyboard-designer)",
            {"step_id": "storyboard", "skill_id": "storyboard-designer"},
            retryable=True,
        )

    monkeypatch.setattr(
        "app.interfaces.cli.main.HandleAgentMessageUseCase.execute",
        fail_execute,
    )

    result = CliRunner().invoke(
        cli_app,
        [
            "chat",
            "--once",
            "介绍openspec",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "WORKFLOW_STEP_FAILED"
    assert payload["error"]["details"]["step_id"] == "storyboard"
    assert payload["error"]["retryable"] is True


def test_fastapi_chat_messages_runs_registered_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})
    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_marketer", "name": "营销身份"},
    )
    client.post(
        "/workspaces/workspace_content_ops/skills",
        json={"skill_id": "talking-video", "display_name": "口播视频"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities/identity_marketer/skills",
        json={"skill_id": "talking-video"},
    )

    response = client.post(
        "/chat/messages",
        json={
            "message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯",
            "context": {
                "workspace_id": "workspace_content_ops",
                "identity_id": "identity_marketer",
                "role_id": "role_owner",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["route_decision"]["skill_id"] == "talking-video"
    assert payload["run_ids"]
    assert payload["action_results"][0]["trace_summary"]["tool_succeeded"] == 1

    trace_response = client.get(f"/runs/{payload['run_ids'][0]}/trace")
    skill_started = next(
        event for event in trace_response.json()
        if event["type"] == "skill_started"
    )
    assert skill_started["data"]["workspace_id"] == "workspace_content_ops"
    assert skill_started["data"]["identity_id"] == "identity_marketer"
    assert skill_started["data"]["role_id"] == "role_owner"


def test_fastapi_chat_messages_confirm_runs_candidate_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})

    waiting = client.post("/chat/messages", json={"message": "介绍openspec"})

    assert waiting.status_code == 200
    waiting_payload = waiting.json()
    assert waiting_payload["status"] == "requires_confirmation"
    assert waiting_payload["requires_confirmation"] is True
    assert waiting_payload["confirmation"]["action_id"] == "confirm_run_skill:talking-video"

    confirmed = client.post(
        "/chat/messages",
        json={"message": "介绍openspec", "confirm": True},
    )

    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()
    assert confirmed_payload["status"] == "completed"
    assert confirmed_payload["route_decision"]["skill_id"] == "talking-video"
    assert confirmed_payload["run_ids"]


def test_fastapi_workspace_identity_skill_catalog_and_sessions(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})

    workspace_response = client.post(
        "/workspaces",
        json={
            "workspace_id": "workspace_content_ops",
            "name": "Content Ops",
        },
    )
    assert workspace_response.status_code == 200

    identity_response = client.post(
        "/workspaces/workspace_content_ops/identities",
        json={
            "identity_id": "identity_xhs_operator",
            "name": "小红书运营",
        },
    )
    assert identity_response.status_code == 200

    install_response = client.post(
        "/workspaces/workspace_content_ops/skills",
        json={"skill_id": "talking-video", "display_name": "口播视频"},
    )
    assert install_response.status_code == 200
    assert install_response.json()["workspace_id"] == "workspace_content_ops"
    assert install_response.json()["skill_id"] == "talking-video"

    workspace_skills_response = client.get("/workspaces/workspace_content_ops/skills")
    assert workspace_skills_response.status_code == 200
    assert workspace_skills_response.json()[0]["skill_id"] == "talking-video"

    bind_response = client.post(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/skills",
        json={"skill_id": "talking-video"},
    )
    assert bind_response.status_code == 200
    assert bind_response.json()["skill_ids"] == ["talking-video"]

    skills_response = client.get(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/skills"
    )
    assert skills_response.status_code == 200
    assert skills_response.json()[0]["id"] == "talking-video"

    chat_response = client.post(
        "/chat/messages",
        json={
            "session_id": "sess_content_ops_001",
            "message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯",
            "context": {
                "workspace_id": "workspace_content_ops",
                "identity_id": "identity_xhs_operator",
            },
        },
    )
    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    assert chat_payload["status"] == "completed"
    assert chat_payload["route_decision"]["skill_id"] == "talking-video"

    session_response = client.get("/sessions/sess_content_ops_001")
    assert session_response.status_code == 200
    session_payload = session_response.json()
    assert session_payload["workspace_id"] == "workspace_content_ops"
    assert session_payload["identity_id"] == "identity_xhs_operator"
    assert len(session_payload["messages"]) == 2
    assert session_payload["turns"][0]["run_ids"] == chat_payload["run_ids"]

    sessions_response = client.get(
        "/sessions?workspace_id=workspace_content_ops&identity_id=identity_xhs_operator"
    )
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["session_id"] == "sess_content_ops_001"


def test_fastapi_identity_cannot_bind_uninstalled_workspace_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/skills/register", json={"path": "resources/skills/talking-video"})
    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_xhs_operator", "name": "小红书运营"},
    )

    bind_response = client.post(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/skills",
        json={"skill_id": "talking-video"},
    )

    assert bind_response.status_code == 400
    assert "not installed in workspace" in bind_response.json()["detail"]


def test_fastapi_disabled_workspace_skill_is_not_routable_for_identity(
    tmp_path: Path,
) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})
    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_xhs_operator", "name": "小红书运营"},
    )
    client.post(
        "/workspaces/workspace_content_ops/skills",
        json={"skill_id": "talking-video", "enabled": True},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/skills",
        json={"skill_id": "talking-video"},
    )
    disabled = client.patch(
        "/workspaces/workspace_content_ops/skills/talking-video",
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    response = client.post(
        "/chat/messages",
        json={
            "message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯",
            "skill_id": "talking-video",
            "context": {
                "workspace_id": "workspace_content_ops",
                "identity_id": "identity_xhs_operator",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_input"
    assert response.json()["route_decision"]["reason"] == (
        "skill is not available to the active identity"
    )


def test_fastapi_workspace_and_identity_tool_policy_apis(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_xhs_operator", "name": "小红书运营"},
    )

    workspace_policy = client.post(
        "/workspaces/workspace_content_ops/tool-policies",
        json={
            "tool_id": "subtitle_generate_srt",
            "effect": "deny",
            "reason": "workspace default deny",
            "risk": "medium",
        },
    )
    assert workspace_policy.status_code == 200
    assert workspace_policy.json()["effect"] == "deny"
    assert workspace_policy.json()["workspace_id"] == "workspace_content_ops"
    assert workspace_policy.json()["identity_id"] is None

    identity_policy = client.post(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/tool-policies",
        json={
            "tool_id": "subtitle_generate_srt",
            "effect": "allow",
            "reason": "operator override",
        },
    )
    assert identity_policy.status_code == 200
    assert identity_policy.json()["effect"] == "allow"
    assert identity_policy.json()["identity_id"] == "identity_xhs_operator"

    identity_policies = client.get(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/tool-policies"
    )
    assert identity_policies.status_code == 200
    assert identity_policies.json()[0]["effect"] == "allow"


def test_fastapi_workspace_secret_api_returns_metadata_only(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )

    created = client.post(
        "/workspaces/workspace_content_ops/secrets",
        json={
            "name": "VIDEO_API_KEY",
            "value": "secret-value",
            "description": "Video provider key",
        },
    )
    assert created.status_code == 200
    assert created.json()["name"] == "VIDEO_API_KEY"
    assert "value" not in created.json()

    listed = client.get("/workspaces/workspace_content_ops/secrets")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "VIDEO_API_KEY"
    assert "value" not in listed.json()[0]


def test_fastapi_tool_approval_flow_allows_rerun_after_approval(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})
    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_xhs_operator", "name": "小红书运营"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities/identity_xhs_operator/tool-policies",
        json={
            "tool_id": "subtitle_generate_srt",
            "effect": "ask",
            "reason": "approval required",
            "risk": "medium",
        },
    )

    first_run = client.post(
        "/skills/talking-video/runs",
        json={
            "input": {
                "topic": "适合程序员的护眼台灯",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
            "context": {
                "workspace_id": "workspace_content_ops",
                "identity_id": "identity_xhs_operator",
            },
        },
    )
    assert first_run.status_code == 200
    assert first_run.json()["status"] == "waiting_approval"
    run_id = first_run.json()["run_id"]

    approvals = client.get(
        "/tool-approvals?workspace_id=workspace_content_ops&identity_id=identity_xhs_operator&status=pending"
    )
    assert approvals.status_code == 200
    approval_id = approvals.json()[0]["approval_id"]

    approved = client.post(
        f"/tool-approvals/{approval_id}/approve",
        json={"decided_by": "user_001"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    second_run = client.post(f"/runs/{run_id}/resume")
    assert second_run.status_code == 200
    assert second_run.json()["status"] == "succeeded"
    assert second_run.json()["run_id"] == run_id


def test_fastapi_chat_blocks_skill_outside_active_identity_catalog(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})
    client.post(
        "/workspaces",
        json={"workspace_id": "workspace_content_ops", "name": "Content Ops"},
    )
    client.post(
        "/workspaces/workspace_content_ops/identities",
        json={"identity_id": "identity_reviewer", "name": "审核员"},
    )

    response = client.post(
        "/chat/messages",
        json={
            "message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯",
            "skill_id": "talking-video",
            "context": {
                "workspace_id": "workspace_content_ops",
                "identity_id": "identity_reviewer",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_input"
    assert payload["run_ids"] == []
    assert payload["route_decision"]["reason"] == (
        "skill is not available to the active identity"
    )


def test_fastapi_skill_run_sse_streams_result(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})

    with client.stream(
        "POST",
        "/skills/talking-video/runs/events",
        json={
            "input": {
                "topic": "适合程序员的护眼台灯",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            }
        },
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_started" in body
    assert "event: skill_started" in body
    assert "event: tool_called" in body
    assert "event: tool_succeeded" in body
    assert "event: run_completed" in body
    assert '"status":"succeeded"' in body


def test_fastapi_chat_sse_streams_markdown_result(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})

    with client.stream(
        "POST",
        "/chat/messages/events",
        json={"message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯"},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: agent_started" in body
    assert "event: markdown_delta" in body
    assert "event: markdown_completed" in body
    assert "event: agent_completed" in body
    assert "### 运行结果" in body
    assert "程序员护眼台灯" in body


def test_fastapi_chat_sse_streams_model_deltas(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(
        artifact_root=tmp_path,
        model_provider=StreamingContentBriefProvider(),
    )
    client = TestClient(create_app(engine))
    client.post("/skills/register", json={"path": "resources/skills/content-brief-planner"})

    with client.stream(
        "POST",
        "/chat/messages/events",
        json={
            "message": "介绍openspec",
            "skill_id": "content-brief-planner",
            "input": {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
        },
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: llm_delta" in body
    assert '"delta":"{\\"content_brief\\""' in body
    assert "event: markdown_delta" in body
    assert "event: agent_completed" in body


def test_fastapi_workflow_sse_streams_step_events(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/mock_video_render"})
    for skill_id in [
        "content-brief-planner",
        "hook-plan-generator",
        "style-bible-planner",
        "talking-script-writer",
        "script-segmenter",
        "storyboard-designer",
        "render-prompt-builder",
        "content-video-workflow",
    ]:
        client.post("/skills/register", json={"path": f"resources/skills/{skill_id}"})

    with client.stream(
        "POST",
        "/skills/content-video-workflow/runs/events",
        json={
            "input": {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            }
        },
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: workflow_step_started" in body
    assert '"step_id":"content_brief"' in body
    assert '"step_id":"hook_plan"' in body
    assert '"step_id":"render_prompt_pack"' in body
    assert "event: workflow_step_succeeded" in body
    assert "event: run_completed" in body


def test_fastapi_chat_websocket_returns_agent_result(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    client = TestClient(create_app(engine))

    client.post("/tools/register", json={"path": "resources/tools/subtitle_generate_srt"})
    client.post("/skills/register", json={"path": "resources/skills/talking-video"})

    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_json(
            {"message": "帮我生成60秒小红书口播视频，主题是程序员护眼台灯"}
        )
        messages = []
        while True:
            message = websocket.receive_json()
            messages.append(message)
            if message["event"] == "agent_completed":
                break

    assert messages[0]["event"] == "agent_started"
    event_names = [message["event"] for message in messages]
    assert "skill_started" in event_names
    assert "tool_called" in event_names
    assert "tool_succeeded" in event_names
    completed = messages[-1]
    assert completed["data"]["status"] == "completed"
    assert completed["data"]["route_decision"]["skill_id"] == "talking-video"


class StreamingContentBriefProvider:
    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        stream_callback=None,  # type: ignore[no-untyped-def]
    ) -> ModelResponse:
        del profile, messages, tools
        if stream_callback is not None:
            await stream_callback('{"content_brief"')
            await stream_callback(':{ "topic":"介绍openspec" }}')
        return ModelResponse(
            final_output={
                "content_brief": {
                    "topic": "介绍openspec",
                    "platform": "xiaohongshu",
                    "content_type": "talking_head",
                    "duration_seconds": 60,
                    "audience": "开发者",
                    "content_goal": "介绍工具价值",
                    "core_angle": "用规范驱动交付",
                    "user_pain_points": ["需求易变", "沟通成本高"],
                    "recommended_structure": ["痛点", "解释", "场景"],
                    "delivery_format": "口播视频",
                }
            }
        )

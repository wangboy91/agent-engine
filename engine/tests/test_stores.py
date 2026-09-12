from pathlib import Path

from app.domain.agent import AgentMessage, AgentTurn
from app.domain.execution import RunResult
from app.infrastructure.persistence.artifact_store import LocalArtifactStore
from app.infrastructure.persistence.memory_store import LocalMarkdownMemoryStore
from app.infrastructure.persistence.policy_store import JsonPolicyStore
from app.infrastructure.persistence.run_store import JsonRunStore
from app.infrastructure.persistence.secret_store import JsonSecretStore
from app.infrastructure.persistence.session_store import JsonAgentSessionStore
from app.infrastructure.persistence.workspace_store import JsonWorkspaceStore
from app.infrastructure.tracing.trace_store import InMemoryTraceStore, JsonTraceStore


def test_artifact_store_saves_and_lists_text_artifacts(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    artifact = store.save_text(
        run_id="run_1",
        content="hello",
        artifact_type="text",
        filename="hello.txt",
        tool_call_id="call_1",
    )

    assert artifact.id
    assert store.read_text(artifact.id) == "hello"
    assert store.list_by_run("run_1") == [artifact]


def test_trace_store_records_run_events() -> None:
    store = InMemoryTraceStore()

    event = store.record("run_1", "skill_started", "Skill started", {"skill_id": "demo"})

    assert event.id
    assert store.list_events("run_1")[0].type == "skill_started"
    assert store.list_events("run_1")[0].data["skill_id"] == "demo"


def test_json_run_store_persists_runs(tmp_path: Path) -> None:
    path = tmp_path / ".agent" / "runs.json"
    store = JsonRunStore(path)

    store.save(RunResult(run_id="run_1", status="succeeded", skill_id="talking-video"))

    reloaded = JsonRunStore(path)

    assert reloaded.get("run_1").status == "succeeded"
    assert reloaded.get("run_1").skill_id == "talking-video"


def test_json_trace_store_persists_events_and_redacts_secrets(tmp_path: Path) -> None:
    path = tmp_path / ".agent" / "traces.json"
    store = JsonTraceStore(path)

    store.record(
        "run_1",
        "tool_called",
        "Tool called",
        {"workspace_id": "workspace_content_ops", "api_key": "secret-value"},
    )

    reloaded = JsonTraceStore(path)
    event = reloaded.list_events("run_1")[0]

    assert event.type == "tool_called"
    assert event.data["workspace_id"] == "workspace_content_ops"
    assert event.data["api_key"] == "[REDACTED]"


def test_json_policy_store_persists_tool_rules_and_resolves_specificity(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".agent" / "policies.json"
    store = JsonPolicyStore(path)

    store.set_tool_rule(
        "subtitle_generate_srt",
        "deny",
        workspace_id="workspace_content_ops",
        reason="workspace blocks subtitles",
    )
    store.set_tool_rule(
        "subtitle_generate_srt",
        "allow",
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
        reason="operator can generate subtitles",
    )

    reloaded = JsonPolicyStore(path)

    workspace_rule = reloaded.find_tool_rule("subtitle_generate_srt", "workspace_content_ops")
    identity_rule = reloaded.find_tool_rule(
        "subtitle_generate_srt",
        "workspace_content_ops",
        "identity_xhs_operator",
    )
    assert workspace_rule is not None
    assert identity_rule is not None
    assert workspace_rule.effect == "deny"
    assert identity_rule.effect == "allow"


def test_json_policy_store_persists_tool_approvals(tmp_path: Path) -> None:
    path = tmp_path / ".agent" / "policies.json"
    store = JsonPolicyStore(path)

    approval = store.create_tool_approval(
        "subtitle_generate_srt",
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
        skill_id="talking-video",
        run_id="run_001",
        tool_call_id="tool_001",
        rule_id="identity:workspace_content_ops:identity_xhs_operator:subtitle_generate_srt",
        reason="needs approval",
    )
    store.approve_tool_approval(approval.approval_id, decided_by="user_001")

    reloaded = JsonPolicyStore(path)
    persisted = reloaded.get_tool_approval(approval.approval_id)
    active = reloaded.find_active_tool_approval(
        "subtitle_generate_srt",
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
        skill_id="talking-video",
    )

    assert persisted.status == "approved"
    assert persisted.decided_by == "user_001"
    assert active is not None
    assert active.approval_id == approval.approval_id


def test_json_secret_store_persists_secrets_but_lists_only_metadata(tmp_path: Path) -> None:
    path = tmp_path / ".agent" / "secrets.json"
    store = JsonSecretStore(path)

    view = store.set_secret(
        "VIDEO_API_KEY",
        "secret-value",
        workspace_id="workspace_content_ops",
        description="Video provider key",
    )

    reloaded = JsonSecretStore(path)
    persisted = reloaded.get_secret("VIDEO_API_KEY", "workspace_content_ops")
    listed = reloaded.list_secrets("workspace_content_ops")[0]

    assert persisted.value == "secret-value"
    assert view.name == "VIDEO_API_KEY"
    assert listed.name == "VIDEO_API_KEY"
    assert not hasattr(listed, "value")


def test_trace_store_subscription_filters_by_workspace_and_identity() -> None:
    async def scenario() -> list[str]:
        store = InMemoryTraceStore()
        async with store.subscribe(
            workspace_id="workspace_content_ops",
            identity_id="identity_xhs_operator",
        ) as queue:
            store.record(
                "run_ignored",
                "skill_started",
                "Skill started",
                {
                    "workspace_id": "workspace_other",
                    "identity_id": "identity_xhs_operator",
                },
            )
            store.record(
                "run_accepted",
                "skill_started",
                "Skill started",
                {
                    "workspace_id": "workspace_content_ops",
                    "identity_id": "identity_xhs_operator",
                },
            )
            store.record("run_accepted", "llm_called", "Model called", {})
            events = [await queue.get(), await queue.get()]
            return [event.type for event in events]

    assert _run(scenario()) == ["skill_started", "llm_called"]


def test_json_workspace_store_persists_identities_and_skill_bindings(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".agent" / "workspaces.json"
    store = JsonWorkspaceStore(path)

    store.create_workspace("workspace_content_ops", "Content Ops")
    store.create_identity(
        "workspace_content_ops",
        "identity_xhs_operator",
        "小红书运营",
    )
    store.install_skill("workspace_content_ops", "talking-video", "口播视频")
    store.bind_skill("workspace_content_ops", "identity_xhs_operator", "talking-video")

    reloaded = JsonWorkspaceStore(path)

    assert reloaded.get_workspace("workspace_content_ops").name == "Content Ops"
    identity = reloaded.get_identity("workspace_content_ops", "identity_xhs_operator")
    assert identity.name == "小红书运营"
    assert identity.skill_ids == ["talking-video"]
    assert reloaded.list_workspace_skill_ids("workspace_content_ops") == ["talking-video"]


def test_workspace_store_requires_skill_install_before_identity_binding(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".agent" / "workspaces.json"
    store = JsonWorkspaceStore(path)

    store.create_workspace("workspace_content_ops", "Content Ops")
    store.create_identity("workspace_content_ops", "identity_xhs_operator", "小红书运营")

    try:
        store.bind_skill("workspace_content_ops", "identity_xhs_operator", "talking-video")
    except Exception as exc:
        assert "WORKSPACE_SKILL_NOT_INSTALLED" in str(exc)
    else:
        raise AssertionError("Expected workspace skill installation to be required")


def test_json_session_store_persists_messages_and_turns(tmp_path: Path) -> None:
    path = tmp_path / ".agent" / "sessions.json"
    store = JsonAgentSessionStore(path)

    store.ensure_session(
        "sess_001",
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
        user_id="user_001",
    )
    store.append_message("sess_001", AgentMessage(role="user", content="介绍openspec"))
    store.append_turn("sess_001", AgentTurn(turn_id="turn_001", user_message="介绍openspec"))

    reloaded = JsonAgentSessionStore(path)
    session = reloaded.get("sess_001")

    assert session.workspace_id == "workspace_content_ops"
    assert session.identity_id == "identity_xhs_operator"
    assert session.user_id == "user_001"
    assert session.messages[0].content == "介绍openspec"
    assert session.turns[0].turn_id == "turn_001"


def test_local_markdown_memory_store_appends_and_reads_snapshot(tmp_path: Path) -> None:
    root = tmp_path / ".agent" / "memory"
    store = LocalMarkdownMemoryStore(root)

    store.append_entry(
        "workspace_content_ops",
        "identity_xhs_operator",
        "memory",
        "默认使用 resources/skills 作为技能目录",
    )
    store.append_entry(
        "workspace_content_ops",
        "identity_xhs_operator",
        "user",
        "用户喜欢中文、直接、少废话的回答",
    )

    reloaded = LocalMarkdownMemoryStore(root)
    snapshot = reloaded.load_snapshot("workspace_content_ops", "identity_xhs_operator")

    assert snapshot.workspace_id == "workspace_content_ops"
    assert snapshot.identity_id == "identity_xhs_operator"
    assert "默认使用 resources/skills" in snapshot.memory
    assert "用户喜欢中文" in snapshot.user
    assert snapshot.sources[0].target == "memory"
    assert snapshot.sources[0].path == (
        root / "workspace_content_ops" / "identity_xhs_operator" / "MEMORY.md"
    )
    assert snapshot.sources[1].target == "user"


def _run(coroutine):  # type: ignore[no-untyped-def]
    import asyncio

    return asyncio.run(coroutine)

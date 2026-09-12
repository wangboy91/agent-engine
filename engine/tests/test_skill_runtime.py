import asyncio
import json
from pathlib import Path

import pytest

from app.application.execution.skill_runtime import SkillRuntimeError
from app.domain.errors import BklEngineError
from app.domain.execution import RunContext
from app.domain.model import ModelResponse, ToolCallRequest
from app.engine import SkillEngine
from app.infrastructure.model_gateway.router import MockModelProvider


def test_skill_engine_runs_mock_skill_with_python_tool(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("resources/skills/talking-video"))

    result = asyncio.run(
        engine.run_skill(
            "talking-video",
            {
                "topic": "适合程序员的护眼台灯",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["script"].startswith("Mock script")
    assert result.output["subtitle_path"] == "subtitle.srt"
    assert result.run_id
    assert result.artifacts
    assert result.artifacts[0].uri.endswith("talking-video-output.json")
    assert "Mock script" in Path(result.artifacts[0].uri).read_text(encoding="utf-8")
    assert result.trace_summary["tool_called"] == 1
    assert result.trace_summary["tool_succeeded"] == 1
    assert any(
        event.type == "tool_succeeded"
        for event in engine.trace_store.list_events(result.run_id)
    )


def test_workspace_tool_policy_denies_tool_execution(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("resources/skills/talking-video"))
    engine.policy_store.set_tool_rule(
        "subtitle_generate_srt",
        "deny",
        workspace_id="workspace_content_ops",
        reason="subtitle generation disabled in workspace",
        risk="medium",
    )

    with pytest.raises(SkillRuntimeError, match="TOOL_POLICY_DENIED"):
        asyncio.run(
            engine.run_skill(
                "talking-video",
                {
                    "topic": "适合程序员的护眼台灯",
                    "platform": "xiaohongshu",
                    "duration_seconds": 60,
                },
                context=RunContext(workspace_id="workspace_content_ops"),
            )
        )

    failed_run = engine.run_store.list_runs()[0]
    policy_event = [
        event for event in engine.trace_store.list_events(failed_run.run_id)
        if event.type == "tool_policy_checked"
    ][0]
    assert failed_run.status == "failed"
    assert policy_event.data["effect"] == "deny"
    assert policy_event.data["details"]["scope"] == "workspace"


def test_identity_tool_policy_overrides_workspace_policy(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("resources/skills/talking-video"))
    engine.policy_store.set_tool_rule(
        "subtitle_generate_srt",
        "deny",
        workspace_id="workspace_content_ops",
    )
    engine.policy_store.set_tool_rule(
        "subtitle_generate_srt",
        "allow",
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
    )

    result = asyncio.run(
        engine.run_skill(
            "talking-video",
            {
                "topic": "适合程序员的护眼台灯",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
            context=RunContext(
                workspace_id="workspace_content_ops",
                identity_id="identity_xhs_operator",
            ),
        )
    )

    policy_event = [
        event for event in engine.trace_store.list_events(result.run_id)
        if event.type == "tool_policy_checked"
    ][-1]
    assert result.status == "succeeded"
    assert policy_event.data["effect"] == "allow"
    assert policy_event.data["details"]["scope"] == "identity"


def test_ask_tool_policy_creates_approval_and_approved_request_allows_rerun(
    tmp_path: Path,
) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("resources/skills/talking-video"))
    engine.policy_store.set_tool_rule(
        "subtitle_generate_srt",
        "ask",
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
        reason="operator approval required",
        risk="medium",
    )
    context = RunContext(
        workspace_id="workspace_content_ops",
        identity_id="identity_xhs_operator",
    )

    waiting = asyncio.run(
        engine.run_skill(
            "talking-video",
            {
                "topic": "适合程序员的护眼台灯",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
            context=context,
        )
    )

    assert waiting.status == "waiting_approval"
    assert waiting.pending_approval is not None
    approval_id = waiting.pending_approval["approval_id"]
    approval = engine.policy_store.get_tool_approval(str(approval_id))
    assert approval.status == "pending"
    assert approval.tool_id == "subtitle_generate_srt"

    engine.policy_store.approve_tool_approval(approval.approval_id, decided_by="user_001")
    result = asyncio.run(engine.resume_run(waiting.run_id))

    policy_event = [
        event for event in engine.trace_store.list_events(result.run_id)
        if event.type == "tool_policy_checked"
    ][-1]
    assert result.status == "succeeded"
    assert result.run_id == waiting.run_id
    assert policy_event.data["effect"] == "allow"
    assert policy_event.data["details"]["approval_id"] == approval.approval_id
    assert policy_event.data["details"]["approval_status"] == "approved"
    assert any(
        event.type == "run_resumed"
        for event in engine.trace_store.list_events(result.run_id)
    )


def test_skill_engine_runs_wangbudong_experiment_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("resources/tools/wangbudong_write_prompt_pack"))
    asyncio.run(engine.register_skill("resources/skills/wangbudong-experiment"))

    result = asyncio.run(
        engine.run_skill(
            "wangbudong-experiment",
            {
                "experiment_title": "彩虹牛奶",
                "materials": ["牛奶", "色素", "洗洁精", "棉签"],
                "target_phenomenon": "色素在牛奶表面扩散成彩虹纹路",
                "age_range": "3-8岁",
                "content_lane": "趣味引流",
            },
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["experiment_title"] == "彩虹牛奶"
    assert "00-实验拆解.md" in result.output["files"]
    assert result.output["step_prompt_count"] >= 4
    assert result.trace_summary["tool_called"] == 1
    assert result.trace_summary["tool_succeeded"] == 1


def test_skill_runtime_normalizes_arrow_separated_string_array_output(tmp_path: Path) -> None:
    provider = MockModelProvider(
        [
            ModelResponse(
                final_output={
                    "content_brief": {
                        "topic": "介绍openspec",
                        "platform": "xiaohongshu",
                        "content_type": "talking_head",
                        "duration_seconds": 60,
                        "audience": "目标用户",
                        "content_goal": "让用户理解 OpenSpec 的价值",
                        "core_angle": "用规范驱动 AI 工程协作",
                        "user_pain_points": ["需求容易漂移", "实现和设计脱节"],
                        "recommended_structure": (
                            "Hook(痛点共鸣/抛出疑问) -> "
                            "Concept(一句话解释OpenSpec) -> "
                            "Value(核心优势与场景展示) -> CTA(引导互动或体验)"
                        ),
                        "delivery_format": "vertical_talking_video",
                    }
                }
            )
        ]
    )
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/content-brief-planner"))

    result = asyncio.run(
        engine.run_skill(
            "content-brief-planner",
            {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    structure = result.output["content_brief"]["recommended_structure"]
    assert structure == [
        "Hook(痛点共鸣/抛出疑问)",
        "Concept(一句话解释OpenSpec)",
        "Value(核心优势与场景展示)",
        "CTA(引导互动或体验)",
    ]


def test_content_brief_accepts_structured_recommended_structure(tmp_path: Path) -> None:
    provider = MockModelProvider(
        [
            ModelResponse(
                final_output={
                    "content_brief": {
                        "topic": "介绍openspec",
                        "platform": "xiaohongshu",
                        "content_type": "talking_head",
                        "duration_seconds": 60,
                        "audience": "AI 工程师",
                        "content_goal": "让用户理解 OpenSpec 的价值",
                        "core_angle": "用规范驱动 AI 工程协作",
                        "user_pain_points": ["需求容易漂移", "实现和设计脱节"],
                        "recommended_structure": [
                            {
                                "section": "价值展示与行动号召",
                                "duration_seconds": 20,
                                "description": "展示使用 OpenSpec 后的理想状态。",
                            }
                        ],
                        "delivery_format": "vertical_talking_video",
                    }
                }
            )
        ]
    )
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/content-brief-planner"))

    result = asyncio.run(
        engine.run_skill(
            "content-brief-planner",
            {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    structure = result.output["content_brief"]["recommended_structure"]
    assert structure[0]["section"] == "价值展示与行动号召"


def test_style_bible_accepts_structured_typography_output(tmp_path: Path) -> None:
    provider = MockModelProvider(
        [
            ModelResponse(
                final_output={
                    "style_bible": {
                        "tone": "清晰、可信、面向工程团队",
                        "visual_style": "竖屏口播配合产品界面标注",
                        "color_palette": {
                            "primary": "#1D4ED8",
                            "background": "#F8FAFC",
                            "text_main": "#111827",
                        },
                        "typography": {
                            "heading": {
                                "font_family": "Noto Sans SC",
                                "font_weight": 700,
                            },
                            "body": {
                                "font_family": "Noto Sans SC",
                                "font_weight": 400,
                            },
                        },
                        "camera_language": "正面半身口播，穿插屏幕录制",
                        "screen_text_rules": ["每屏不超过两行", "关键词加粗"],
                    }
                }
            )
        ]
    )
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/style-bible-planner"))

    result = asyncio.run(
        engine.run_skill(
            "style-bible-planner",
            {"content_brief": {"topic": "介绍openspec"}},
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["style_bible"]["color_palette"]["primary"] == "#1D4ED8"
    assert result.output["style_bible"]["typography"]["heading"]["font_weight"] == 700


def test_hook_plan_accepts_structured_hook_output(tmp_path: Path) -> None:
    provider = MockModelProvider(
        [
            ModelResponse(
                final_output={
                    "hook_plan": {
                        "hooks": [
                            {
                                "type": "pain",
                                "content": "你写的规范，为什么团队还是执行不起来？",
                            },
                            {
                                "type": "contrast",
                                "content": "OpenSpec 不是文档工具，而是让规范进入执行流程。",
                            },
                            {
                                "type": "curiosity",
                                "content": "都在说 OpenSpec，它到底解决了什么问题？",
                            },
                        ],
                        "best_hook": {
                            "type": "pain",
                            "content": "你写的规范，为什么团队还是执行不起来？",
                        },
                        "reason": "痛点明确，适合作为一分钟口播开头。",
                    }
                }
            )
        ]
    )
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/hook-plan-generator"))

    result = asyncio.run(
        engine.run_skill(
            "hook-plan-generator",
            {"content_brief": {"topic": "介绍openspec"}},
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["hook_plan"]["hooks"][0]["content"].startswith("你写的规范")
    assert result.output["hook_plan"]["best_hook"]["type"] == "pain"


def test_skill_runtime_normalizes_scalar_string_fields(tmp_path: Path) -> None:
    provider = MockModelProvider(
        [
            ModelResponse(
                final_output={
                    "script_segments": [
                        {
                            "id": 7,
                            "order": 7,
                            "time_range": "00:45-00:52",
                            "duration": 7,
                            "spoken_text": "OpenSpec 让规范不只停留在文档里。",
                            "function": "value",
                            "emotion": "confident",
                            "screen_text": "规范进入执行流程",
                        }
                    ]
                }
            )
        ]
    )
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/script-segmenter"))

    result = asyncio.run(
        engine.run_skill(
            "script-segmenter",
            {"script": {"full_text": "OpenSpec 让规范不只停留在文档里。"}},
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["script_segments"][0]["id"] == "7"


def test_script_segmenter_accepts_numeric_time_range(tmp_path: Path) -> None:
    provider = MockModelProvider(
        [
            ModelResponse(
                final_output={
                    "script_segments": [
                        {
                            "id": "1",
                            "order": 1,
                            "time_range": [0, 4],
                            "duration": 4,
                            "spoken_text": "别人准点下班，你还在手动填模板？",
                            "function": "Hook引入",
                            "emotion": "共情",
                            "screen_text": "别人准点下班 VS 你还在填模板",
                        }
                    ]
                }
            )
        ]
    )
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/script-segmenter"))

    result = asyncio.run(
        engine.run_skill(
            "script-segmenter",
            {"script": {"full_text": "别人准点下班，你还在手动填模板？"}},
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["script_segments"][0]["time_range"] == [0, 4]


def test_storyboard_accepts_multiple_assets_per_shot(tmp_path: Path) -> None:
    provider = MockModelProvider(
        [
            ModelResponse(
                final_output={
                    "storyboard": {
                        "shots": [
                            {
                                "shot_id": "shot_01",
                                "segment_id": "1",
                                "duration": 6,
                                "visual_type": "talking_head",
                                "camera": "medium close-up",
                                "description": "口播人物指向屏幕关键词。",
                                "screen_text": "OpenSpec 是什么？",
                                "asset_needed": [
                                    "口播人物素材",
                                    "关键词标题贴纸",
                                    "屏幕录制素材",
                                ],
                            }
                        ]
                    }
                }
            )
        ]
    )
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/storyboard-designer"))

    result = asyncio.run(
        engine.run_skill(
            "storyboard-designer",
            {
                "script_segments": [{"id": "1", "spoken_text": "OpenSpec 是什么？"}],
                "style_bible": {},
            },
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["storyboard"]["shots"][0]["asset_needed"][1] == "关键词标题贴纸"


def test_workflow_runs_ready_dag_steps_in_parallel(tmp_path: Path) -> None:
    provider = ConcurrentModelProvider()
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill(_write_json_output_skill(tmp_path, "dag-a", "a")))
    asyncio.run(engine.register_skill(_write_json_output_skill(tmp_path, "dag-b", "b")))
    asyncio.run(engine.register_skill(_write_dag_workflow_skill(tmp_path)))

    result = asyncio.run(engine.run_skill("dag-workflow", {}))

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["a"] == "dag-a"
    assert result.output["b"] == "dag-b"
    assert provider.max_active_calls == 2
    assert [step["step_id"] for step in result.output["step_runs"]] == ["a", "b"]


def test_skill_started_trace_includes_workspace_identity_context(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_skill("resources/skills/content-brief-planner"))

    result = asyncio.run(
        engine.run_skill(
            "content-brief-planner",
            {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
            RunContext(
                user_id="user_001",
                workspace_id="workspace_content_ops",
                identity_id="identity_marketer",
                role_id="role_owner",
            ),
        )
    )

    skill_started = next(
        event for event in engine.trace_store.list_events(result.run_id)
        if event.type == "skill_started"
    )
    assert skill_started.data["user_id"] == "user_001"
    assert skill_started.data["workspace_id"] == "workspace_content_ops"
    assert skill_started.data["identity_id"] == "identity_marketer"
    assert skill_started.data["role_id"] == "role_owner"


def test_skill_runtime_schema_error_includes_output_preview(tmp_path: Path) -> None:
    provider = MockModelProvider([ModelResponse(final_output={"text": "not the expected object"})])
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/render-prompt-builder"))

    with pytest.raises(SkillRuntimeError) as exc_info:
        asyncio.run(
            engine.run_skill(
                "render-prompt-builder",
                {"storyboard": {"shots": []}, "style_bible": {}},
            )
        )

    assert exc_info.value.code == "OUTPUT_SCHEMA_INVALID"
    assert exc_info.value.details["path"] == []
    assert exc_info.value.details["root_keys"] == ["text"]
    assert "not the expected object" in exc_info.value.details["instance_preview"]


def test_workflow_step_failure_includes_step_context(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(
        artifact_root=tmp_path,
        model_provider=FailingModelProvider(),
    )
    asyncio.run(engine.register_skill("resources/skills/content-brief-planner"))
    asyncio.run(engine.register_skill("resources/skills/content-video-workflow"))

    with pytest.raises(SkillRuntimeError) as exc_info:
        asyncio.run(
            engine.run_skill(
                "content-video-workflow",
                {
                    "topic": "介绍openspec",
                    "platform": "xiaohongshu",
                    "duration_seconds": 60,
                },
            )
        )

    assert exc_info.value.code == "WORKFLOW_STEP_FAILED"
    assert exc_info.value.details["step_id"] == "content_brief"
    assert exc_info.value.details["skill_id"] == "content-brief-planner"
    assert exc_info.value.details["cause_code"] == "MODEL_PROVIDER_ERROR"


def test_skill_runtime_retries_retryable_model_errors(tmp_path: Path) -> None:
    provider = RetryOnceModelProvider()
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_skill("resources/skills/content-brief-planner"))

    result = asyncio.run(
        engine.run_skill(
            "content-brief-planner",
            {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
        )
    )

    assert result.status == "succeeded"
    assert provider.calls == 2
    assert result.trace_summary["llm_failed"] == 1
    assert result.trace_summary["llm_retried"] == 1


def test_skill_runtime_rejects_tool_not_allowed(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(
        artifact_root=tmp_path,
        model_provider=MockModelProvider(
            [
                ModelResponse(
                    tool_calls=[
                        ToolCallRequest(
                            id="call_bad",
                            tool_id="not_allowed",
                            arguments={},
                        )
                    ]
                )
            ]
        ),
    )
    asyncio.run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("resources/skills/talking-video"))

    with pytest.raises(SkillRuntimeError, match="TOOL_NOT_ALLOWED"):
        asyncio.run(
            engine.run_skill(
                "talking-video",
                {
                    "topic": "适合程序员的护眼台灯",
                    "platform": "xiaohongshu",
                    "duration_seconds": 60,
                },
            )
        )


def test_skill_runtime_stops_at_max_iterations(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(
        artifact_root=tmp_path,
        model_provider=MockModelProvider(
            [
                ModelResponse(tool_calls=[]),
                ModelResponse(tool_calls=[]),
                ModelResponse(tool_calls=[]),
            ]
        ),
    )
    asyncio.run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("resources/skills/talking-video"))

    with pytest.raises(SkillRuntimeError, match="MAX_ITERATIONS_EXCEEDED"):
        asyncio.run(
            engine.run_skill(
                "talking-video",
                {
                    "topic": "适合程序员的护眼台灯",
                    "platform": "xiaohongshu",
                    "duration_seconds": 60,
                },
            )
        )


def test_skill_runtime_appends_assistant_tool_call_message(tmp_path: Path) -> None:
    provider = RecordingToolCallProvider()
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path, model_provider=provider)
    asyncio.run(engine.register_tool("resources/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("resources/skills/talking-video"))

    result = asyncio.run(
        engine.run_skill(
            "talking-video",
            {
                "topic": "适合程序员的护眼台灯",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
        )
    )

    assert result.status == "succeeded"
    second_call_messages = provider.calls[1]
    assert second_call_messages[-2]["role"] == "assistant"
    assert second_call_messages[-2]["tool_calls"][0]["function"]["name"] == "subtitle_generate_srt"
    assert second_call_messages[-1]["role"] == "tool"


def test_skill_runtime_injects_memory_snapshot_into_system_prompt(tmp_path: Path) -> None:
    provider = RecordingFinalOutputProvider(
        {
            "content_brief": {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "content_type": "talking_head",
                "duration_seconds": 60,
                "audience": "AI 工程师",
                "content_goal": "让用户理解 OpenSpec 的价值",
                "core_angle": "用规范驱动 AI 工程协作",
                "user_pain_points": ["需求容易漂移", "实现和设计脱节"],
                "recommended_structure": ["Hook", "Value", "CTA"],
                "delivery_format": "vertical_talking_video",
            }
        }
    )
    engine = SkillEngine.create_for_testing(
        artifact_root=tmp_path,
        model_provider=provider,
        memory_root=tmp_path / ".bkl" / "memory",
    )
    engine.memory_store.append_entry(
        "workspace_content_ops",
        "identity_xhs_operator",
        "memory",
        "默认使用 resources/skills 作为技能目录",
    )
    engine.memory_store.append_entry(
        "workspace_content_ops",
        "identity_xhs_operator",
        "user",
        "用户喜欢中文、直接、少废话的回答",
    )
    asyncio.run(engine.register_skill("resources/skills/content-brief-planner"))

    result = asyncio.run(
        engine.run_skill(
            "content-brief-planner",
            {
                "topic": "介绍openspec",
                "platform": "xiaohongshu",
                "duration_seconds": 60,
            },
            context=RunContext(
                workspace_id="workspace_content_ops",
                identity_id="identity_xhs_operator",
            ),
        )
    )

    assert result.status == "succeeded"
    system_prompt = str(provider.calls[0][0]["content"])
    assert "# Workspace Memory" in system_prompt
    assert "默认使用 resources/skills 作为技能目录" in system_prompt
    assert "# User Profile" in system_prompt
    assert "用户喜欢中文、直接、少废话的回答" in system_prompt

    memory_events = [
        event for event in engine.trace_store.list_events(result.run_id)
        if event.type == "memory_loaded"
    ]
    assert len(memory_events) == 1
    assert memory_events[0].data["workspace_id"] == "workspace_content_ops"
    assert memory_events[0].data["identity_id"] == "identity_xhs_operator"
    assert memory_events[0].data["source_count"] == 2
    assert "默认使用 resources/skills" not in json.dumps(
        memory_events[0].data,
        ensure_ascii=False,
    )


class RecordingToolCallProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        del profile, tools
        self.calls.append([dict(message) for message in messages])
        if len(self.calls) == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCallRequest(
                        id="call_recorded",
                        tool_id="subtitle_generate_srt",
                        arguments={"text": "hello", "audio_path": "audio.wav"},
                    )
                ]
            )
        return ModelResponse(
            final_output={
                "script": "Mock script",
                "titles": ["title"],
                "subtitle_path": "subtitle.srt",
                "segments": [],
            }
        )


class RecordingFinalOutputProvider:
    def __init__(self, final_output: dict[str, object]) -> None:
        self.final_output = final_output
        self.calls: list[list[dict[str, object]]] = []

    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        del profile, tools
        self.calls.append([dict(message) for message in messages])
        return ModelResponse(final_output=self.final_output)


class FailingModelProvider:
    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        del profile, messages, tools
        raise BklEngineError(
            "MODEL_PROVIDER_ERROR",
            "model endpoint disconnected",
            {"error_type": "RemoteProtocolError"},
            retryable=True,
        )


class RetryOnceModelProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        del profile, messages, tools
        self.calls += 1
        if self.calls == 1:
            raise BklEngineError(
                "MODEL_PROVIDER_ERROR",
                "model endpoint disconnected",
                {"error_type": "RemoteProtocolError"},
                retryable=True,
            )
        return ModelResponse(
            final_output={
                "content_brief": {
                    "topic": "介绍openspec",
                    "platform": "xiaohongshu",
                    "content_type": "talking_head",
                    "duration_seconds": 60,
                    "audience": "AI 工程师",
                    "content_goal": "让用户理解 OpenSpec 的价值",
                    "core_angle": "用规范驱动 AI 工程协作",
                    "user_pain_points": ["需求容易漂移", "实现和设计脱节"],
                    "recommended_structure": ["Hook", "Value", "CTA"],
                    "delivery_format": "vertical_talking_video",
                }
            }
        )


class ConcurrentModelProvider:
    def __init__(self) -> None:
        self.active_calls = 0
        self.max_active_calls = 0

    async def chat(
        self,
        profile: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelResponse:
        del profile, tools
        system_prompt = ""
        for message in messages:
            if message.get("role") == "system":
                content = message.get("content")
                system_prompt = content if isinstance(content, str) else ""
                break

        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            await asyncio.sleep(0.05)
        finally:
            self.active_calls -= 1

        if "dag-a" in system_prompt:
            return ModelResponse(final_output={"a": "dag-a"})
        if "dag-b" in system_prompt:
            return ModelResponse(final_output={"b": "dag-b"})
        return ModelResponse(final_output={})


def _write_json_output_skill(tmp_path: Path, skill_id: str, output_key: str) -> Path:
    skill_dir = tmp_path / skill_id
    skill_dir.mkdir()
    schemas_dir = skill_dir / "schemas"
    schemas_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {skill_id}",
                f"description: Test Skill {skill_id}.",
                "---",
                f"# {skill_id}",
                "",
                f"Return JSON for {skill_id}.",
            ]
        ),
        encoding="utf-8",
    )
    (skill_dir / "bkl.skill.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "version": "0.1.0",
                "input_schema": "schemas/input.schema.json",
                "output_schema": "schemas/output.schema.json",
                "model": {"profile": "mock"},
                "tools": {"allow": []},
                "limits": {"max_iterations": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (schemas_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "additionalProperties": True}),
        encoding="utf-8",
    )
    (schemas_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "required": [output_key],
                "additionalProperties": True,
                "properties": {output_key: {"type": "string"}},
            }
        ),
        encoding="utf-8",
    )
    return skill_dir


def _write_dag_workflow_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "dag-workflow"
    skill_dir.mkdir()
    schemas_dir = skill_dir / "schemas"
    schemas_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: dag-workflow",
                "description: Test DAG workflow.",
                "---",
                "# dag-workflow",
                "",
                "Run two independent steps.",
            ]
        ),
        encoding="utf-8",
    )
    (skill_dir / "bkl.skill.json").write_text(
        json.dumps(
            {
                "id": "dag-workflow",
                "version": "0.1.0",
                "input_schema": "schemas/input.schema.json",
                "output_schema": "schemas/output.schema.json",
                "model": {"profile": "mock"},
                "tools": {"allow": []},
                "workflow": {
                    "output_artifact": "dag-workflow-output.json",
                    "max_parallel_steps": 2,
                    "steps": [
                        {"id": "a", "skill_id": "dag-a"},
                        {"id": "b", "skill_id": "dag-b"},
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (schemas_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "additionalProperties": True}),
        encoding="utf-8",
    )
    (schemas_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "required": ["workflow_id", "input", "step_runs", "a", "b"],
                "additionalProperties": True,
            }
        ),
        encoding="utf-8",
    )
    return skill_dir

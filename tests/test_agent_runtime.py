import asyncio
from pathlib import Path

from bkl_engine.application.agent.state_machine import AgentLoop
from bkl_engine.domain.agent import SceneDefinition, SceneMapping
from bkl_engine.domain.execution import RunContext
from bkl_engine.engine import SkillEngine


def test_agent_loop_runs_skill_from_scene_mapping_with_defaults(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("examples/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_skill("examples/skills/talking-video"))
    loop = AgentLoop(
        engine,
        scene_mapping=SceneMapping(
            {
                "talking-video-writer": SceneDefinition(
                    scene_id="talking-video-writer",
                    skill_id="talking-video",
                    title="口播视频生成",
                    defaults={"platform": "xiaohongshu", "duration_seconds": 60},
                )
            }
        ),
    )

    response = asyncio.run(
        loop.handle_message("主题是程序员护眼台灯", scene_id="talking-video-writer")
    )

    assert response.status == "completed"
    assert response.route_decision is not None
    assert response.route_decision.skill_id == "talking-video"
    assert response.run_ids
    assert response.output is not None
    assert response.output["subtitle_path"] == "subtitle.srt"
    assert response.action_results[0].trace_summary["tool_called"] == 1
    assert response.action_results[0].trace_summary["tool_succeeded"] == 1


def test_agent_loop_routes_natural_language_to_registered_skill(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("examples/tools/wangbudong_write_prompt_pack"))
    asyncio.run(engine.register_skill("examples/skills/wangbudong-experiment"))
    loop = AgentLoop(engine)

    response = asyncio.run(
        loop.handle_message(
            "帮我做一个王不懂小实验，实验标题是彩虹牛奶，"
            "材料有牛奶、色素、洗洁精，现象是色素扩散成彩虹纹路"
        )
    )

    assert response.status == "completed"
    assert response.route_decision is not None
    assert response.route_decision.skill_id == "wangbudong-experiment"
    assert response.run_ids
    assert response.output is not None
    assert response.output["experiment_title"] == "彩虹牛奶"


def test_agent_loop_runs_content_video_workflow_from_plain_topic(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("examples/tools/mock_video_render"))
    for skill_id in [
        "content-brief-planner",
        "hook-plan-generator",
        "style-bible-planner",
        "talking-script-writer",
        "script-segmenter",
        "storyboard-designer",
        "render-prompt-builder",
        "asset-manifest-builder",
        "video-timeline-planner",
        "video-render-dispatcher",
        "content-review-reporter",
        "content-video-workflow",
    ]:
        asyncio.run(engine.register_skill(f"examples/skills/{skill_id}"))
    loop = AgentLoop(engine)

    response = asyncio.run(
        loop.handle_message("介绍openspec", skill_id="content-video-workflow")
    )

    assert response.status == "completed"
    assert response.route_decision is not None
    assert response.route_decision.input_draft["topic"] == "介绍openspec"
    assert response.route_decision.input_draft["platform"] == "xiaohongshu"
    assert response.route_decision.input_draft["duration_seconds"] == 60
    assert response.output is not None
    assert response.output["storyboard"]["shots"]
    assert response.output["render_prompt_pack"]["prompts"]


def test_agent_loop_asks_for_missing_required_skill_input(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("examples/tools/wangbudong_write_prompt_pack"))
    asyncio.run(engine.register_skill("examples/skills/wangbudong-experiment"))
    loop = AgentLoop(engine)

    response = asyncio.run(
        loop.handle_message("帮我做一个王不懂小实验，实验标题是彩虹牛奶")
    )

    assert response.status == "needs_input"
    assert response.run_ids == []
    assert response.missing_fields == ["materials", "target_phenomenon"]
    assert "materials" in response.message


def test_agent_loop_routes_only_within_active_identity_catalog(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    asyncio.run(engine.register_tool("examples/tools/subtitle_generate_srt"))
    asyncio.run(engine.register_tool("examples/tools/wangbudong_write_prompt_pack"))
    asyncio.run(engine.register_skill("examples/skills/talking-video"))
    asyncio.run(engine.register_skill("examples/skills/wangbudong-experiment"))
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
    loop = AgentLoop(engine)

    response = asyncio.run(
        loop.handle_message(
            "帮我生成小红书口播视频，主题是程序员护眼台灯",
            input_data={"platform": "xiaohongshu", "duration_seconds": 60},
            context=RunContext(
                workspace_id="workspace_content_ops",
                identity_id="identity_xhs_operator",
            ),
        )
    )

    assert response.status == "completed"
    assert response.route_decision is not None
    assert response.route_decision.skill_id == "talking-video"

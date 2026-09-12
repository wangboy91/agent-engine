import asyncio
from pathlib import Path

from app.engine import SkillEngine

CONTENT_VIDEO_SKILLS = [
    "content-brief-planner",
    "hook-plan-generator",
    "style-bible-planner",
    "talking-script-writer",
    "script-segmenter",
    "storyboard-designer",
    "render-prompt-builder",
    "content-video-workflow",
]


def test_content_video_workflow_runs_prompt_planning_steps(tmp_path: Path) -> None:
    engine = SkillEngine.create_for_testing(artifact_root=tmp_path)
    for skill_id in CONTENT_VIDEO_SKILLS:
        asyncio.run(engine.register_skill(f"resources/skills/{skill_id}"))

    result = asyncio.run(
        engine.run_skill(
            "content-video-workflow",
            {
                "topic": "AI Agent 如何落地到企业内容运营",
                "platform": "douyin",
                "duration_seconds": 60,
                "audience": "传统行业老板 / 自媒体工作者",
                "content_type": "talking_head",
                "style_directive": "真实口播、直接、有案例感",
            },
        )
    )

    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["workflow_id"] == "content-video-workflow"
    assert len(result.output["step_runs"]) == 7
    assert result.output["content_brief"]["topic"] == "AI Agent 如何落地到企业内容运营"
    assert result.output["hook_plan"]["best_hook"]
    assert result.output["script"]["full_text"]
    assert len(result.output["script_segments"]) >= 1
    assert len(result.output["storyboard"]["shots"]) == len(result.output["script_segments"])
    assert len(result.output["render_prompt_pack"]["prompts"]) == len(
        result.output["storyboard"]["shots"]
    )
    assert result.trace_summary["workflow_step_succeeded"] == 7
    assert result.artifacts[0].uri.endswith("content-video-workflow.json")

    child_run_ids = [step["run_id"] for step in result.output["step_runs"]]
    assert all(engine.run_store.get(run_id).status == "succeeded" for run_id in child_run_ids)

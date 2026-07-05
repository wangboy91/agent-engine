from pathlib import Path

import pytest

from bkl_engine.infrastructure.package_loaders.skill_loader import SkillLoadError, load_skill


def test_loads_skill_package_from_directory() -> None:
    skill = load_skill("resources/skills/talking-video")

    assert skill.id == "talking-video"
    assert skill.name == "talking-video"
    assert skill.model.profile == "mock"
    assert skill.allowed_tools == ["subtitle_generate_srt"]
    assert skill.input_schema["required"] == ["topic", "platform", "duration_seconds"]
    assert "口播视频生成" in skill.prompt


def test_loads_wangbudong_experiment_skill_package() -> None:
    skill = load_skill("resources/skills/wangbudong-experiment")

    assert skill.id == "wangbudong-experiment"
    assert skill.name == "wangbudong-experiment"
    assert skill.allowed_tools == ["wangbudong_write_prompt_pack"]
    assert skill.input_schema["required"] == [
        "experiment_title",
        "materials",
        "target_phenomenon",
    ]
    assert "王不懂的小实验" in skill.prompt


def test_loads_standard_skill_md_with_runtime_config(tmp_path: Path) -> None:
    skill_dir = _write_standard_skill(tmp_path)

    skill = load_skill(skill_dir)

    assert skill.id == "demo_skill"
    assert skill.name == "demo-skill"
    assert skill.description == "Use when testing standard SKILL.md parsing."
    assert skill.version == "0.2.0"
    assert skill.allowed_tools == ["demo_tool"]
    assert skill.model.profile == "mock"
    assert skill.prompt == "# Demo Skill\n\nRun the demo workflow."


def test_standard_skill_md_requires_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bad_standard_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Missing frontmatter", encoding="utf-8")

    with pytest.raises(SkillLoadError, match="frontmatter"):
        load_skill(skill_dir)


def test_standard_skill_without_bkl_sidecar_loads_with_default_contract(tmp_path: Path) -> None:
    skill_dir = tmp_path / "missing_runtime_config"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: demo-skill",
                "description: Use when testing standard SKILL.md parsing.",
                "---",
                "# Demo Skill",
                "",
                "Run the demo workflow.",
            ]
        ),
        encoding="utf-8",
    )

    skill = load_skill(skill_dir)

    assert skill.id == "demo-skill"
    assert skill.allowed_tools == []
    assert skill.input_schema["properties"]["user_input"]["type"] == "string"
    assert skill.output_schema["additionalProperties"] is True


def test_standard_skill_rejects_bkl_frontmatter_extension(tmp_path: Path) -> None:
    skill_dir = _write_standard_skill(tmp_path)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8").replace(
            "description: Use when testing standard SKILL.md parsing.\n---",
            "description: Use when testing standard SKILL.md parsing.\nbkl:\n  id: bad\n---",
        ),
        encoding="utf-8",
    )

    with pytest.raises(SkillLoadError, match="bkl.skill.json"):
        load_skill(skill_dir)


def test_skill_loader_rejects_non_standard_skill_packages(tmp_path: Path) -> None:
    skill_dir = _write_non_standard_skill(tmp_path)

    with pytest.raises(SkillLoadError, match="SKILL.md"):
        load_skill(skill_dir)


def test_skill_loader_allows_model_only_skill(tmp_path: Path) -> None:
    skill_dir = _write_standard_skill(tmp_path, allowed_tools=[])

    skill = load_skill(skill_dir)

    assert skill.allowed_tools == []
    assert skill.workflow is None


def test_loads_workflow_skill_package() -> None:
    skill = load_skill("resources/skills/content-video-workflow")

    assert skill.id == "content-video-workflow"
    assert skill.allowed_tools == []
    assert skill.workflow is not None
    assert skill.workflow.max_parallel_steps == 2
    assert [step.skill_id for step in skill.workflow.steps] == [
        "content-brief-planner",
        "hook-plan-generator",
        "style-bible-planner",
        "talking-script-writer",
        "script-segmenter",
        "storyboard-designer",
        "render-prompt-builder",
    ]
    assert skill.workflow.steps[1].depends_on == ["content_brief"]
    assert skill.workflow.steps[2].depends_on == ["content_brief"]
    assert skill.workflow.steps[-1].depends_on == ["storyboard"]
    assert skill.workflow.output_artifact == "content-video-workflow.json"


def test_loads_direct_tool_skill_execution_config(tmp_path: Path) -> None:
    skill = load_skill(_write_direct_tool_skill(tmp_path))

    assert skill.execution.type == "direct_tool"
    assert skill.execution.tool_id == "demo_tool"
    assert skill.execution.output_mapping["result.id"] == "id"


def _write_non_standard_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "non_standard_skill"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        "\n".join(
            [
                "id: non_standard_skill",
                "name: Non Standard Skill",
                "version: 0.1.0",
                "description: Non standard",
                "input_schema: input.schema.json",
                "output_schema: output.schema.json",
                "prompt: prompt.md",
                "tools:",
                "  allow:",
                "    - demo_tool",
            ]
        ),
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text("Non standard prompt", encoding="utf-8")
    (skill_dir / "input.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    (skill_dir / "output.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    return skill_dir


def _write_standard_skill(
    tmp_path: Path,
    allowed_tools: list[str] | None = None,
) -> Path:
    skill_dir = tmp_path / "demo_standard_skill"
    skill_dir.mkdir()
    allowed = allowed_tools if allowed_tools is not None else ["demo_tool"]
    if allowed:
        allow_lines = ["    \"allow\": ["]
        allow_lines.extend(f'      "{tool_id}",' for tool_id in allowed)
        allow_lines[-1] = allow_lines[-1].rstrip(",")
        allow_lines.append("    ]")
    else:
        allow_lines = ['    "allow": []']
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: demo-skill",
                "description: Use when testing standard SKILL.md parsing.",
                "---",
                "# Demo Skill",
                "",
                "Run the demo workflow.",
            ]
        ),
        encoding="utf-8",
    )
    schemas_dir = skill_dir / "schemas"
    schemas_dir.mkdir()
    (skill_dir / "bkl.skill.json").write_text(
        "\n".join(
            [
                "{",
                '  "id": "demo_skill",',
                '  "version": "0.2.0",',
                '  "input_schema": "schemas/input.schema.json",',
                '  "output_schema": "schemas/output.schema.json",',
                '  "model": {',
                '    "profile": "mock"',
                "  },",
                '  "tools": {',
                *allow_lines,
                "  }",
                "}",
            ]
        ),
        encoding="utf-8",
    )
    (schemas_dir / "input.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    (schemas_dir / "output.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    return skill_dir


def _write_direct_tool_skill(tmp_path: Path) -> Path:
    skill_dir = _write_standard_skill(tmp_path)
    config_path = skill_dir / "bkl.skill.json"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "  }\n}",
            '  },\n'
            '  "execution": {\n'
            '    "type": "direct_tool",\n'
            '    "tool_id": "demo_tool",\n'
            '    "input_mapping": {"input": "input"},\n'
            '    "output_mapping": {"result.id": "id"}\n'
            "  }\n"
            "}",
        ),
        encoding="utf-8",
    )
    return skill_dir

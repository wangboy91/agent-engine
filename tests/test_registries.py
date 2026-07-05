from bkl_engine.infrastructure.repositories.skill_registry import InMemorySkillRegistry
from bkl_engine.infrastructure.repositories.tool_registry import InMemoryToolRegistry


def test_tool_registry_registers_and_filters_allowed_tools() -> None:
    registry = InMemoryToolRegistry()
    registry.register_tool("examples/tools/subtitle_generate_srt")

    assert registry.get_tool("subtitle_generate_srt").id == "subtitle_generate_srt"
    assert [tool.id for tool in registry.get_allowed_tools(["subtitle_generate_srt"])] == [
        "subtitle_generate_srt"
    ]


def test_skill_registry_registers_and_lists_skills() -> None:
    registry = InMemorySkillRegistry()
    registry.register_skill("examples/skills/talking-video")

    assert registry.get_skill("talking-video").id == "talking-video"
    assert [skill.id for skill in registry.list_skills()] == ["talking-video"]

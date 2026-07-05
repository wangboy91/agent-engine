from pathlib import Path

import pytest

from bkl_engine.infrastructure.package_loaders.tool_loader import ToolLoadError, load_tool


def test_loads_python_tool_package_from_directory() -> None:
    tool = load_tool(Path("resources/tools/subtitle_generate_srt"))

    assert tool.id == "subtitle_generate_srt"
    assert tool.type == "python"
    assert tool.name == "生成字幕文件"
    assert tool.description == "根据音频和口播文案生成 SRT 字幕"
    assert tool.entry == "main.py"
    assert tool.input_schema["required"] == ["text", "audio_path"]
    assert tool.output_schema["required"] == ["srt_path", "segments"]
    assert tool.runtime.timeout_seconds == 120
    assert tool.runtime.memory_mb == 512
    assert tool.permissions.network is False
    assert tool.permissions.filesystem_read == ["workspace"]
    assert tool.permissions.filesystem_write == ["artifacts"]


def test_loader_reports_missing_required_tool_fields(tmp_path: Path) -> None:
    tool_dir = tmp_path / "bad_tool"
    tool_dir.mkdir()
    (tool_dir / "tool.yaml").write_text(
        "\n".join(
            [
                "id: bad_tool",
                "type: python",
                "name: Bad Tool",
                "input_schema: input.schema.json",
                "output_schema: output.schema.json",
            ]
        ),
        encoding="utf-8",
    )
    (tool_dir / "input.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    (tool_dir / "output.schema.json").write_text('{"type": "object"}', encoding="utf-8")

    with pytest.raises(ToolLoadError, match="description"):
        load_tool(tool_dir)

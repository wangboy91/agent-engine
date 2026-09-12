import asyncio
from pathlib import Path

import pytest

from app.domain.tool import ToolExecutionContext
from app.infrastructure.package_loaders.tool_loader import load_tool
from app.infrastructure.tool_runners.python_tool import (
    PythonToolRunner,
    ToolExecutionError,
)


def test_python_tool_runner_executes_tool_with_json_stdio(tmp_path: Path) -> None:
    tool = load_tool("resources/tools/subtitle_generate_srt")
    result = asyncio.run(
        PythonToolRunner().execute(
            tool,
            {"text": "hello", "audio_path": "audio.wav"},
            ToolExecutionContext(
                run_id="run_test",
                tool_call_id="call_test",
                artifact_dir=tmp_path,
            ),
        )
    )

    assert result.output["srt_path"] == "subtitle.srt"
    assert result.output["segments"][0]["text"] == "hello"
    assert result.stderr == ""


def test_wangbudong_prompt_pack_tool_writes_markdown_files(tmp_path: Path) -> None:
    tool = load_tool("resources/tools/wangbudong_write_prompt_pack")
    result = asyncio.run(
        PythonToolRunner().execute(
            tool,
            {
                "experiment_title": "彩虹牛奶",
                "materials": ["牛奶", "色素", "洗洁精", "棉签"],
                "target_phenomenon": "色素在牛奶表面扩散成彩虹纹路",
                "age_range": "3-8岁",
                "content_lane": "趣味引流",
                "include_operations_card": False,
            },
            ToolExecutionContext(
                run_id="run_test",
                tool_call_id="call_wangbudong",
                artifact_dir=tmp_path,
            ),
        )
    )

    assert result.output["experiment_title"] == "彩虹牛奶"
    assert result.output["output_dir"] == str(tmp_path)
    assert "00-实验拆解.md" in result.output["files"]
    assert "01-首图提示词.md" in result.output["files"]
    assert "02-分步骤提示词.md" in result.output["files"]
    assert "03-小红书文案.md" in result.output["files"]
    assert (tmp_path / "00-实验拆解.md").exists()
    assert "实验合理性论证" in (tmp_path / "00-实验拆解.md").read_text(encoding="utf-8")


def test_python_tool_runner_resolves_relative_artifact_dir_from_caller_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool(Path.cwd() / "resources/tools/wangbudong_write_prompt_pack")
    monkeypatch.chdir(tmp_path)

    result = asyncio.run(
        PythonToolRunner().execute(
            tool,
            {
                "experiment_title": "彩虹牛奶",
                "materials": ["牛奶", "色素", "洗洁精", "棉签"],
                "target_phenomenon": "色素在牛奶表面扩散成彩虹纹路",
            },
            ToolExecutionContext(
                run_id="run_test",
                tool_call_id="call_relative",
                artifact_dir=Path("relative_artifacts"),
            ),
        )
    )

    expected_dir = tmp_path / "relative_artifacts"
    assert result.output["output_dir"] == str(expected_dir.resolve())
    assert (expected_dir / "00-实验拆解.md").exists()


def test_python_tool_runner_rejects_invalid_input_schema(tmp_path: Path) -> None:
    tool = load_tool("resources/tools/subtitle_generate_srt")

    with pytest.raises(ToolExecutionError, match="TOOL_INPUT_SCHEMA_INVALID"):
        asyncio.run(
            PythonToolRunner().execute(
                tool,
                {"text": "missing audio path"},
                ToolExecutionContext(
                    run_id="run_test",
                    tool_call_id="call_test",
                    artifact_dir=tmp_path,
                ),
            )
        )


def test_python_tool_runner_reports_timeout(tmp_path: Path) -> None:
    tool_dir = tmp_path / "slow_tool"
    tool_dir.mkdir()
    (tool_dir / "tool.yaml").write_text(
        "\n".join(
            [
                "id: slow_tool",
                "type: python",
                "name: Slow Tool",
                "description: Sleeps longer than allowed",
                "entry: main.py",
                "input_schema: input.schema.json",
                "output_schema: output.schema.json",
                "runtime:",
                "  timeout_seconds: 1",
            ]
        ),
        encoding="utf-8",
    )
    (tool_dir / "input.schema.json").write_text(
        '{"type": "object", "additionalProperties": false}',
        encoding="utf-8",
    )
    (tool_dir / "output.schema.json").write_text(
        '{"type": "object", "additionalProperties": false}',
        encoding="utf-8",
    )
    (tool_dir / "main.py").write_text(
        "import time\n"
        "time.sleep(5)\n"
        "print('{}')\n",
        encoding="utf-8",
    )

    with pytest.raises(ToolExecutionError, match="PYTHON_TOOL_TIMEOUT"):
        asyncio.run(
            PythonToolRunner().execute(
                load_tool(tool_dir),
                {},
                ToolExecutionContext(
                    run_id="run_test",
                    tool_call_id="call_test",
                    artifact_dir=tmp_path / "artifacts",
                ),
            )
        )

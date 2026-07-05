import json

import yaml
from typer.testing import CliRunner

from bkl_engine import __version__
from bkl_engine.interfaces.cli.main import app


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_prints_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "bkl-skill-engine 0.1.0" in result.stdout


def test_cli_init_writes_model_config_and_env_without_leaking_secret(tmp_path) -> None:  # type: ignore[no-untyped-def]
    config_path = tmp_path / "bkl.yaml"
    env_path = tmp_path / ".env"

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--protocol",
            "openai-compatible",
            "--profile",
            "xfyun_openai",
            "--base-url",
            "https://example.com/v2",
            "--model",
            "astron-code-latest",
            "--api-key",
            "secret-token",
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert "secret-token" not in result.stdout
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["models"]["active_profile"] == "xfyun_openai"
    profile = config["models"]["profiles"]["xfyun_openai"]
    assert profile["protocol"] == "openai-compatible"
    assert profile["base_url"] == "https://example.com/v2"
    assert profile["model"] == "astron-code-latest"
    assert profile["api_key_env"] == "OPENAI_AUTH_TOKEN"
    assert "secret-token" not in config_path.read_text(encoding="utf-8")
    assert "OPENAI_AUTH_TOKEN=secret-token" in env_path.read_text(encoding="utf-8")


def test_cli_init_refuses_to_overwrite_config_without_force(tmp_path) -> None:  # type: ignore[no-untyped-def]
    config_path = tmp_path / "bkl.yaml"
    config_path.write_text("existing: true\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--protocol",
            "mock",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code != 0
    assert config_path.read_text(encoding="utf-8") == "existing: true\n"


def test_cli_serve_starts_fastapi_app_with_config(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
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
    captured = {}

    def fake_run(api, **kwargs):  # type: ignore[no-untyped-def]
        captured["api"] = api
        captured["kwargs"] = kwargs

    monkeypatch.setattr("bkl_engine.interfaces.cli.main.uvicorn.run", fake_run)

    result = CliRunner().invoke(
        app,
        [
            "serve",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert captured["api"].title == "BKL Skill Engine"
    assert captured["kwargs"]["host"] == "0.0.0.0"
    assert captured["kwargs"]["port"] == 9000


def test_cli_gateway_starts_fastapi_app_with_stream_transports(
    monkeypatch, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    config_path = _write_mock_config(tmp_path)
    captured = {}

    def fake_run(api, **kwargs):  # type: ignore[no-untyped-def]
        captured["api"] = api
        captured["kwargs"] = kwargs

    monkeypatch.setattr("bkl_engine.interfaces.cli.main.uvicorn.run", fake_run)

    result = CliRunner().invoke(
        app,
        [
            "gateway",
            "--host",
            "0.0.0.0",
            "--port",
            "9100",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert captured["api"].title == "BKL Skill Engine"
    assert captured["kwargs"]["host"] == "0.0.0.0"
    assert captured["kwargs"]["port"] == 9100


def test_cli_register_commands_write_catalog(tmp_path) -> None:  # type: ignore[no-untyped-def]
    config_path = _write_mock_config(tmp_path)
    catalog_path = tmp_path / ".bkl" / "catalog.json"

    tool_result = CliRunner().invoke(
        app,
        [
            "tool",
            "register",
            "examples/tools/subtitle_generate_srt",
            "--config",
            str(config_path),
            "--catalog",
            str(catalog_path),
        ],
    )
    skill_result = CliRunner().invoke(
        app,
        [
            "skill",
            "register",
            "examples/skills/talking-video",
            "--config",
            str(config_path),
            "--catalog",
            str(catalog_path),
        ],
    )

    assert tool_result.exit_code == 0
    assert skill_result.exit_code == 0
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert (
        catalog["tools"]["subtitle_generate_srt"]["path"]
        == "examples/tools/subtitle_generate_srt"
    )
    assert catalog["skills"]["talking-video"]["path"] == "examples/skills/talking-video"


def _write_mock_config(tmp_path):  # type: ignore[no-untyped-def]
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

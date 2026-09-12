from pathlib import Path

from app.engine import SkillEngine
from app.infrastructure.config.engine_config import load_engine_config
from app.infrastructure.model_gateway.providers.openai_compatible import (
    OpenAICompatibleProvider,
)


def test_loads_multiple_model_profiles_with_active_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.com/v2")
    monkeypatch.setenv("ASTRON_MODEL", "astron-code-latest")
    config_path = tmp_path / "bkl.yaml"
    config_path.write_text(
        "\n".join(
            [
                "models:",
                "  active_profile: xfyun_openai",
                "  profiles:",
                "    xfyun_openai:",
                "      protocol: openai-compatible",
                "      base_url: ${OPENAI_COMPATIBLE_BASE_URL}",
                "      api_key_env: ANTHROPIC_AUTH_TOKEN",
                "      model: ${ASTRON_MODEL}",
                "    xfyun_anthropic:",
                "      protocol: anthropic",
                "      base_url: https://example.com/anthropic",
                "      api_key_env: ANTHROPIC_AUTH_TOKEN",
                "      model: astron-code-latest",
            ]
        ),
        encoding="utf-8",
    )

    config = load_engine_config(config_path)

    assert config.models.active_profile == "xfyun_openai"
    assert config.models.profiles["xfyun_openai"].protocol == "openai-compatible"
    assert config.models.profiles["xfyun_openai"].base_url == "https://example.com/v2"
    assert config.models.profiles["xfyun_openai"].api_key_env == "ANTHROPIC_AUTH_TOKEN"
    assert config.models.profiles["xfyun_openai"].model == "astron-code-latest"
    assert config.models.profiles["xfyun_anthropic"].protocol == "anthropic"


def test_load_engine_config_reads_local_dotenv(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_COMPATIBLE_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "OPENAI_COMPATIBLE_BASE_URL=https://dotenv.example.com/v2",
                "ANTHROPIC_MODEL=astron-code-latest",
            ]
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "bkl.yaml"
    config_path.write_text(
        "\n".join(
            [
                "models:",
                "  active_profile: dotenv_openai",
                "  profiles:",
                "    dotenv_openai:",
                "      protocol: openai-compatible",
                "      base_url: ${OPENAI_COMPATIBLE_BASE_URL}",
                "      api_key_env: OPENAI_AUTH_TOKEN",
                "      model: ${ANTHROPIC_MODEL}",
            ]
        ),
        encoding="utf-8",
    )

    config = load_engine_config(config_path)

    assert config.models.profiles["dotenv_openai"].base_url == "https://dotenv.example.com/v2"
    assert config.models.profiles["dotenv_openai"].model == "astron-code-latest"


def test_skill_engine_load_uses_active_configured_model_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://example.com/v2")
    config_path = tmp_path / "bkl.yaml"
    config_path.write_text(
        "\n".join(
            [
                "models:",
                "  active_profile: xfyun_openai",
                "  profiles:",
                "    xfyun_openai:",
                "      protocol: openai-compatible",
                "      base_url: ${OPENAI_COMPATIBLE_BASE_URL}",
                "      api_key_env: ANTHROPIC_AUTH_TOKEN",
                "      model: astron-code-latest",
            ]
        ),
        encoding="utf-8",
    )

    engine = SkillEngine.load(config_path)

    assert engine.model_router.active_profile == "xfyun_openai"
    assert isinstance(engine.model_router.providers["xfyun_openai"], OpenAICompatibleProvider)

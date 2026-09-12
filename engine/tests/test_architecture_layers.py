import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BKL_ENGINE_ROOT = PROJECT_ROOT / "app"
APPLICATION_ROOT = PROJECT_ROOT / "app" / "application"


def test_app_top_level_uses_ddd_layout_only() -> None:
    allowed_directories = {"application", "domain", "infrastructure", "interfaces"}
    actual_directories = {
        path.name
        for path in BKL_ENGINE_ROOT.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }

    assert actual_directories == allowed_directories


def test_application_layer_has_no_infrastructure_or_facade_imports() -> None:
    banned_prefixes = (
        "app.engine",
        "app.infrastructure",
        "app.models",
        "app.storage",
        "app.trace",
    )

    violations: list[str] = []
    for path in sorted(APPLICATION_ROOT.rglob("*.py")):
        imported_modules = _imported_modules(path)
        for module in imported_modules:
            if module.startswith(banned_prefixes):
                relative = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative}: {module}")

    assert violations == []


def test_domain_models_have_canonical_modules() -> None:
    from app.domain.execution import RunResult
    from app.domain.skill import Skill
    from app.domain.tool import Tool

    assert Skill.__module__ == "app.domain.skill.schemas"
    assert Tool.__module__ == "app.domain.tool.schemas"
    assert RunResult.__module__ == "app.domain.execution.schemas"


def test_in_memory_adapters_live_in_infrastructure_layer() -> None:
    from app.infrastructure.persistence.artifact_store import LocalArtifactStore
    from app.infrastructure.persistence.catalog_store import JsonCatalogStore
    from app.infrastructure.persistence.run_store import InMemoryRunStore
    from app.infrastructure.repositories.skill_registry import InMemorySkillRegistry
    from app.infrastructure.repositories.tool_registry import InMemoryToolRegistry
    from app.infrastructure.tracing.trace_store import InMemoryTraceStore

    assert InMemorySkillRegistry.__module__ == (
        "app.infrastructure.repositories.skill_registry"
    )
    assert InMemoryToolRegistry.__module__ == (
        "app.infrastructure.repositories.tool_registry"
    )
    assert LocalArtifactStore.__module__ == "app.infrastructure.persistence.artifact_store"
    assert JsonCatalogStore.__module__ == "app.infrastructure.persistence.catalog_store"
    assert InMemoryRunStore.__module__ == "app.infrastructure.persistence.run_store"
    assert InMemoryTraceStore.__module__ == "app.infrastructure.tracing.trace_store"


def test_interface_adapters_have_canonical_modules() -> None:
    from app.interfaces.cli import main as cli_module
    from app.interfaces.http.main import create_app

    assert create_app.__module__ == "app.interfaces.http.main"
    assert cli_module.__name__ == "app.interfaces.cli.main"


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return modules

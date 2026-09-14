"""Architecture layer tests for account-service (DDD constraint)."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "app"
APPLICATION_ROOT = APP_ROOT / "application"
DOMAIN_ROOT = APP_ROOT / "domain"


def test_ddd_layout_only() -> None:
    allowed = {"application", "domain", "infrastructure", "interfaces"}
    actual = {
        p.name
        for p in APP_ROOT.iterdir()
        if p.is_dir() and p.name != "__pycache__"
    }
    assert actual == allowed


def test_application_has_no_infrastructure_imports() -> None:
    banned = ("app.infrastructure", "app.interfaces", "sqlalchemy", "fastapi")
    violations: list[str] = []
    for path in APPLICATION_ROOT.rglob("*.py"):
        for mod in _imports(path):
            if mod.startswith(banned) or mod == "sqlalchemy":
                violations.append(f"{path.name}: {mod}")
    assert violations == []


def test_domain_has_no_framework_imports() -> None:
    banned_prefixes = ("fastapi", "sqlalchemy", "app.infrastructure", "app.interfaces")
    violations: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        for mod in _imports(path):
            if any(mod == b or mod.startswith(b + ".") for b in banned_prefixes):
                violations.append(f"{path.name}: {mod}")
    assert violations == []


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules

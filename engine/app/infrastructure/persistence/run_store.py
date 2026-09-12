"""Run store primitives."""

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.domain.errors import BklEngineError
from app.domain.execution import RunResult


class RunDocument(BaseModel):
    version: int = 1
    runs: dict[str, RunResult] = Field(default_factory=dict)


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunResult] = {}

    def save(self, run: RunResult) -> RunResult:
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> RunResult:
        run = self._runs.get(run_id)
        if run is None:
            raise BklEngineError("RUN_NOT_FOUND", f"Run not found: {run_id}")
        return run

    def list_runs(self) -> list[RunResult]:
        return list(self._runs.values())


class JsonRunStore(InMemoryRunStore):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        super().__init__()
        self._load_into_memory()

    def save(self, run: RunResult) -> RunResult:
        saved = super().save(run)
        self._save()
        return saved

    def _load_into_memory(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            document = RunDocument.model_validate(raw)
        except json.JSONDecodeError as exc:
            raise BklEngineError(
                "RUN_STORE_INVALID",
                f"Invalid run store JSON: {self.path}",
            ) from exc
        except ValidationError as exc:
            raise BklEngineError(
                "RUN_STORE_INVALID",
                f"Invalid run store shape: {self.path}",
            ) from exc
        self._runs = dict(document.runs)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = RunDocument(runs=dict(self._runs))
        self.path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

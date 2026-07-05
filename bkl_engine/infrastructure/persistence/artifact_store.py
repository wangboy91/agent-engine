"""Artifact store primitives."""

from pathlib import Path
from uuid import uuid4

from bkl_engine.domain.errors import BklEngineError
from bkl_engine.domain.execution import Artifact, ArtifactType


class LocalArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, Artifact] = {}

    def tool_artifact_dir(self, run_id: str, tool_call_id: str) -> Path:
        return self.root / run_id / tool_call_id

    def save_text(
        self,
        run_id: str,
        content: str,
        artifact_type: ArtifactType,
        filename: str,
        tool_call_id: str | None = None,
        mime_type: str = "text/plain",
    ) -> Artifact:
        artifact_id = f"artifact_{uuid4().hex}"
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / filename
        path.write_text(content, encoding="utf-8")
        artifact = Artifact(
            id=artifact_id,
            run_id=run_id,
            tool_call_id=tool_call_id,
            type=artifact_type,
            mime_type=mime_type,
            uri=str(path),
        )
        self._artifacts[artifact_id] = artifact
        return artifact

    def register_file(
        self,
        run_id: str,
        path: str | Path,
        artifact_type: ArtifactType,
        mime_type: str,
        tool_call_id: str | None = None,
    ) -> Artifact:
        artifact_id = f"artifact_{uuid4().hex}"
        artifact = Artifact(
            id=artifact_id,
            run_id=run_id,
            tool_call_id=tool_call_id,
            type=artifact_type,
            mime_type=mime_type,
            uri=str(path),
        )
        self._artifacts[artifact_id] = artifact
        return artifact

    def get(self, artifact_id: str) -> Artifact:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise BklEngineError("ARTIFACT_NOT_FOUND", f"Artifact not found: {artifact_id}")
        return artifact

    def read_text(self, artifact_id: str) -> str:
        artifact = self.get(artifact_id)
        return Path(artifact.uri).read_text(encoding="utf-8")

    def list_by_run(self, run_id: str) -> list[Artifact]:
        return [artifact for artifact in self._artifacts.values() if artifact.run_id == run_id]

import hashlib
import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from aivitals_engine.contracts.result import ModelInfo

INDEX_FILENAME = "model_registry.json"
REGISTRY_SCHEMA_VERSION = "1.0.0"
HASH_CHUNK_BYTES = 1024 * 1024


class ModelKind(StrEnum):
    RPPG_DEEP = "rppg_deep"
    BLOOD_PRESSURE = "blood_pressure"
    HEALTH_RISK = "health_risk"
    CONFIDENCE_CALIBRATOR = "confidence_calibrator"
    RULE_SET = "rule_set"


class ModelStatus(StrEnum):
    EXPERIMENTAL = "experimental"
    RESEARCH_ONLY = "research_only"
    VALIDATED = "validated"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


class ModelEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_\-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    kind: ModelKind
    status: ModelStatus
    artifact_path: str
    checksum_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    created_at: datetime
    dataset_version: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""

    @property
    def version_key(self) -> tuple[int, ...]:
        return tuple(int(part) for part in self.version.split("."))

    def to_model_info(self) -> ModelInfo:
        return ModelInfo(name=self.name, version=self.version, checksum_sha256=self.checksum_sha256)


class RegistryError(Exception):
    pass


class ModelNotFoundError(RegistryError):
    pass


class DuplicateModelVersionError(RegistryError):
    pass


class ChecksumMismatchError(RegistryError):
    pass


class ArtifactOutsideRegistryError(RegistryError):
    pass


def compute_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelRegistry:
    def __init__(self, root_dir: Path | str) -> None:
        self._root = Path(root_dir).resolve()
        self._index_path = self._root / INDEX_FILENAME
        self._lock = RLock()

    @property
    def root(self) -> Path:
        return self._root

    def register(
        self,
        name: str,
        version: str,
        kind: ModelKind,
        artifact_path: Path | str,
        status: ModelStatus = ModelStatus.EXPERIMENTAL,
        dataset_version: str | None = None,
        metrics: dict[str, float] | None = None,
        notes: str = "",
    ) -> ModelEntry:
        artifact = self._resolve_inside_root(artifact_path)
        with self._lock:
            entries = self._load()
            if any(entry.name == name and entry.version == version for entry in entries):
                raise DuplicateModelVersionError(f"Model {name} phiên bản {version} đã tồn tại trong registry")
            entry = ModelEntry(
                name=name,
                version=version,
                kind=kind,
                status=status,
                artifact_path=artifact.relative_to(self._root).as_posix(),
                checksum_sha256=compute_sha256(artifact),
                created_at=datetime.now(tz=UTC),
                dataset_version=dataset_version,
                metrics=metrics or {},
                notes=notes,
            )
            self._save([*entries, entry])
        return entry

    def list_entries(self, kind: ModelKind | None = None, status: ModelStatus | None = None) -> list[ModelEntry]:
        with self._lock:
            entries = self._load()
        return [
            entry
            for entry in entries
            if (kind is None or entry.kind is kind) and (status is None or entry.status is status)
        ]

    def get(self, name: str, version: str) -> ModelEntry:
        for entry in self.list_entries():
            if entry.name == name and entry.version == version:
                return entry
        raise ModelNotFoundError(f"Không tìm thấy model {name} phiên bản {version}")

    def latest(self, name: str, allowed_statuses: Iterable[ModelStatus] | None = None) -> ModelEntry:
        allowed = set(allowed_statuses) if allowed_statuses is not None else None
        candidates = [
            entry
            for entry in self.list_entries()
            if entry.name == name and (allowed is None or entry.status in allowed)
        ]
        if not candidates:
            raise ModelNotFoundError(f"Không có phiên bản phù hợp cho model {name}")
        return max(candidates, key=lambda entry: entry.version_key)

    def update_status(self, name: str, version: str, status: ModelStatus) -> ModelEntry:
        with self._lock:
            entries = self._load()
            target = next((entry for entry in entries if entry.name == name and entry.version == version), None)
            if target is None:
                raise ModelNotFoundError(f"Không tìm thấy model {name} phiên bản {version}")
            updated = target.model_copy(update={"status": status})
            self._save([updated if entry is target else entry for entry in entries])
        return updated

    def verify(self, entry: ModelEntry) -> Path:
        artifact = self._root / entry.artifact_path
        if not artifact.is_file():
            raise ModelNotFoundError(f"Thiếu file artifact của model {entry.name}: {entry.artifact_path}")
        actual = compute_sha256(artifact)
        if actual != entry.checksum_sha256:
            raise ChecksumMismatchError(f"Checksum của model {entry.name} {entry.version} không khớp")
        return artifact

    def resolve_artifact(self, name: str, version: str) -> Path:
        return self.verify(self.get(name, version))

    def _resolve_inside_root(self, artifact_path: Path | str) -> Path:
        candidate = Path(artifact_path)
        artifact = (candidate if candidate.is_absolute() else self._root / candidate).resolve()
        if not artifact.is_relative_to(self._root):
            raise ArtifactOutsideRegistryError("Artifact phải nằm trong thư mục registry")
        if not artifact.is_file():
            raise ModelNotFoundError(f"Không tìm thấy file artifact: {artifact}")
        return artifact

    def _load(self) -> list[ModelEntry]:
        if not self._index_path.exists():
            return []
        payload = json.loads(self._index_path.read_text(encoding="utf-8"))
        return [ModelEntry.model_validate(item) for item in payload.get("models", [])]

    def _save(self, entries: list[ModelEntry]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "models": [entry.model_dump(mode="json") for entry in entries],
        }
        temporary = self._index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self._index_path)

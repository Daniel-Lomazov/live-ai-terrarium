from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from live_ai_terrarium.contracts.records import ArtifactRef
from live_ai_terrarium.storage.filesystem import HostFilesystem
from live_ai_terrarium.storage.paths import RunScope, StoragePaths


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


class LogCaptureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LogEntryInput(LogCaptureModel):
    occurred_at: str
    broker_name: str
    stream: str
    message: str
    cycle_id: str | None = None

    @field_validator("occurred_at", "broker_name", "stream")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @field_validator("cycle_id")
    @classmethod
    def validate_cycle_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name="cycle_id")


class CapturedLogEntry(LogEntryInput):
    sequence: int = Field(ge=1)


class LogBundle(LogCaptureModel):
    uuid: UUID = Field(default_factory=uuid4)
    project_id: str
    glass_box_id: str
    experiment_id: str
    run_id: str
    created_at: str
    log_file: str

    @field_validator("project_id", "glass_box_id", "experiment_id", "run_id", "created_at", "log_file")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @property
    def artifact_ref(self) -> ArtifactRef:
        return ArtifactRef(uuid=self.uuid, locator=self.log_file)


class LogAppendReceipt(LogCaptureModel):
    bundle_ref: ArtifactRef
    first_sequence: int = Field(ge=1)
    last_sequence: int = Field(ge=1)
    entry_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_sequence_window(self) -> LogAppendReceipt:
        if self.last_sequence < self.first_sequence:
            raise ValueError("last_sequence must be greater than or equal to first_sequence")
        if self.last_sequence - self.first_sequence + 1 != self.entry_count:
            raise ValueError("entry_count must match the captured sequence window")
        return self


class LogCaptureBroker:
    def __init__(self, storage_paths: StoragePaths, filesystem: HostFilesystem | None = None) -> None:
        self._storage_paths = storage_paths
        self._filesystem = filesystem or HostFilesystem(storage_paths)

    def bundle_path(self, run: RunScope) -> Path:
        return self._log_dir(run) / "full-log-bundle.jsonl"

    def bundle_metadata_path(self, run: RunScope) -> Path:
        return self._log_dir(run) / "full-log-bundle.json"

    def ensure_bundle(self, run: RunScope, *, created_at: str | None = None) -> LogBundle:
        metadata_path = self.bundle_metadata_path(run)
        if metadata_path.exists():
            return self.read_bundle(run)
        if created_at is None:
            raise ValueError("created_at is required to initialize the brokered full-log bundle")

        bundle = LogBundle(
            project_id=run.project_id,
            glass_box_id=run.glassbox_id,
            experiment_id=run.experiment_id,
            run_id=run.run_id,
            created_at=created_at,
            log_file=str(self.bundle_path(run)),
        )
        self._filesystem.write_json(metadata_path, bundle.model_dump(mode="json"))
        return bundle

    def read_bundle(self, run: RunScope) -> LogBundle:
        metadata_path = self.bundle_metadata_path(run)
        if not metadata_path.exists():
            raise FileNotFoundError(f"Missing brokered full-log bundle metadata: {metadata_path}")
        return LogBundle.model_validate_json(metadata_path.read_text(encoding="utf-8"))

    def append_entries(self, run: RunScope, *, entries: Sequence[LogEntryInput]) -> LogAppendReceipt:
        if not entries:
            raise ValueError("entries must not be empty")

        bundle = self.ensure_bundle(run, created_at=entries[0].occurred_at)
        first_sequence = self._next_sequence(run)
        captured_entries = [
            CapturedLogEntry(sequence=first_sequence + index, **entry.model_dump(mode="python"))
            for index, entry in enumerate(entries)
        ]
        self._filesystem.append_jsonl(
            self.bundle_path(run),
            [entry.model_dump(mode="json") for entry in captured_entries],
        )
        return LogAppendReceipt(
            bundle_ref=bundle.artifact_ref,
            first_sequence=first_sequence,
            last_sequence=captured_entries[-1].sequence,
            entry_count=len(captured_entries),
        )

    def read_entries(self, run: RunScope) -> list[CapturedLogEntry]:
        log_path = self.bundle_path(run)
        if not log_path.exists():
            return []
        entries: list[CapturedLogEntry] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entries.append(CapturedLogEntry.model_validate_json(line))
        return entries

    def _next_sequence(self, run: RunScope) -> int:
        existing_entries = self.read_entries(run)
        if not existing_entries:
            return 1
        return existing_entries[-1].sequence + 1

    def _log_dir(self, run: RunScope) -> Path:
        return self._storage_paths.state_root.joinpath(
            "logs",
            "projects",
            run.project_id,
            "glassboxes",
            run.glassbox_id,
            "experiments",
            run.experiment_id,
            "runs",
            run.run_id,
            "brokered",
        )


__all__ = [
    "CapturedLogEntry",
    "LogAppendReceipt",
    "LogBundle",
    "LogCaptureBroker",
    "LogEntryInput",
]
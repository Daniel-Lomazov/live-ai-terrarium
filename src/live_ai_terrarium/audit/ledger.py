from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..control.commands import CanonicalAction, CommandScope, normalize_action
from ..storage.filesystem import HostFilesystem
from ..storage.paths import StoragePaths

AuditEventType = Literal[
    "command.requested",
    "command.approval_requested",
    "command.approved",
    "command.rejected",
    "command.started",
    "command.completed",
    "command.failed",
]
AuditMetadataValue = str | int | float | bool | None


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def _validate_hash(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a 64-character lowercase hexadecimal digest")
    return value


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    command_id: UUID
    action: CanonicalAction
    event_type: AuditEventType
    occurred_at: str
    actor_id: str
    actor_role: str
    scope: CommandScope
    cycle_id: str | None = None
    approval_id: UUID | None = None
    receipt_id: UUID | None = None
    details: dict[str, AuditMetadataValue] = Field(default_factory=dict)

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, value: str | CanonicalAction) -> CanonicalAction:
        if isinstance(value, str):
            return normalize_action(value)
        return value

    @field_validator("occurred_at", "actor_id", "actor_role")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @field_validator("cycle_id")
    @classmethod
    def validate_cycle_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name="cycle_id")

    @field_validator("details")
    @classmethod
    def validate_details(cls, value: dict[str, AuditMetadataValue]) -> dict[str, AuditMetadataValue]:
        return {_require_text(key, field_name="details key"): item for key, item in value.items()}

    @model_validator(mode="after")
    def validate_run_scope(self) -> AuditEvent:
        if self.scope.run_id is None:
            raise ValueError("audit events require a run-scoped command scope")
        return self


class AuditLedgerEntry(AuditEvent):
    previous_event_hash: str | None = None
    current_event_hash: str

    @field_validator("previous_event_hash", "current_event_hash")
    @classmethod
    def validate_hashes(cls, value: str | None, info) -> str | None:
        return _validate_hash(value, field_name=info.field_name)


class AuditLedgerIntegrityError(ValueError):
    pass


class AuditLedger:
    def __init__(self, storage_paths: StoragePaths, filesystem: HostFilesystem | None = None) -> None:
        self._storage_paths = storage_paths
        self._filesystem = filesystem or HostFilesystem(storage_paths)

    def ledger_path_for_scope(self, scope: CommandScope) -> Path:
        if scope.run_id is None or scope.experiment_id is None:
            raise ValueError("audit ledger requires experiment and run identifiers")
        return self._storage_paths.state_root.joinpath(
            "audit",
            "projects",
            scope.project_id,
            "glassboxes",
            scope.glass_box_id,
            "experiments",
            scope.experiment_id,
            "runs",
            scope.run_id,
            "ledger.jsonl",
        )

    def append(self, event: AuditEvent) -> AuditLedgerEntry:
        previous_hash = self._last_hash(event.scope)
        entry = AuditLedgerEntry(
            **event.model_dump(mode="python"),
            previous_event_hash=previous_hash,
            current_event_hash=self._hash_event(event=event, previous_event_hash=previous_hash),
        )
        self._filesystem.append_jsonl(self.ledger_path_for_scope(event.scope), [entry.model_dump(mode="json")])
        return entry

    def read_run_events(self, scope: CommandScope) -> list[AuditLedgerEntry]:
        ledger_path = self.ledger_path_for_scope(scope)
        if not ledger_path.exists():
            return []
        entries: list[AuditLedgerEntry] = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entries.append(AuditLedgerEntry.model_validate_json(line))
        return entries

    def verify_run_chain(self, scope: CommandScope) -> list[AuditLedgerEntry]:
        verified_entries = self.read_run_events(scope)
        previous_hash: str | None = None
        for index, entry in enumerate(verified_entries):
            if entry.previous_event_hash != previous_hash:
                raise AuditLedgerIntegrityError(
                    f"Audit tamper detected: previous hash mismatch at ledger index {index}"
                )
            expected_hash = self._hash_persisted_entry(entry)
            if entry.current_event_hash != expected_hash:
                raise AuditLedgerIntegrityError(
                    f"Audit tamper detected: current hash mismatch at ledger index {index}"
                )
            previous_hash = entry.current_event_hash
        return verified_entries

    def _last_hash(self, scope: CommandScope) -> str | None:
        existing_entries = self.read_run_events(scope)
        if not existing_entries:
            return None
        return existing_entries[-1].current_event_hash

    def _hash_event(self, *, event: AuditEvent, previous_event_hash: str | None) -> str:
        payload = AuditLedgerEntry(
            **event.model_dump(mode="python"),
            previous_event_hash=previous_event_hash,
            current_event_hash="0" * 64,
        ).model_dump(mode="json", exclude={"current_event_hash"})
        return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()

    def _hash_persisted_entry(self, entry: AuditLedgerEntry) -> str:
        payload = entry.model_dump(mode="json", exclude={"current_event_hash"})
        return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


__all__ = [
    "AuditEvent",
    "AuditLedger",
    "AuditLedgerEntry",
    "AuditLedgerIntegrityError",
    "AuditEventType",
]
from __future__ import annotations

import re
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CANONICAL_ACTIONS = (
    "observe",
    "mode switch",
    "pause",
    "resume",
    "branch",
    "clone",
    "reset",
    "rollback",
)
CONTROL_ACTIONS = CANONICAL_ACTIONS[2:]
OBSERVATION_ONLY_MODE = "observation-only"

CanonicalAction = Literal[
    "observe",
    "mode switch",
    "pause",
    "resume",
    "branch",
    "clone",
    "reset",
    "rollback",
]
ReceiptStatus = Literal[
    "requested",
    "approved",
    "active",
    "completed",
    "expired",
    "revoked",
    "rejected",
]
SurfaceMetadataValue = str | int | float | bool | None

_ACTION_SEPARATOR_PATTERN = re.compile(r"[\s_-]+")


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def normalize_action(value: str) -> CanonicalAction:
    normalized = _ACTION_SEPARATOR_PATTERN.sub(" ", _require_text(value, field_name="action").lower())
    if normalized not in CANONICAL_ACTIONS:
        raise ValueError("action must normalize to a canonical action")
    return normalized  # type: ignore[return-value]


class CommandScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    glass_box_id: str
    experiment_id: str | None = None
    run_id: str | None = None

    @field_validator("project_id", "glass_box_id", "experiment_id", "run_id")
    @classmethod
    def validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_hierarchy(self) -> CommandScope:
        if self.run_id is not None and self.experiment_id is None:
            raise ValueError("run_id requires experiment_id")
        return self

    def scope_key(self) -> tuple[str, str, str | None, str | None]:
        return (self.project_id, self.glass_box_id, self.experiment_id, self.run_id)

    def matches(self, other: CommandScope) -> bool:
        return self.scope_key() == other.scope_key()


class ModeSwitchReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: UUID = Field(default_factory=uuid4)
    scope: CommandScope
    mode_context: str
    target_mode: str
    status: ReceiptStatus

    @field_validator("mode_context", "target_mode")
    @classmethod
    def validate_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    def is_active_for(self, *, scope: CommandScope, current_mode: str, mode_context: str) -> bool:
        return (
            self.status == "active"
            and self.scope.matches(scope)
            and self.mode_context == mode_context
            and self.target_mode == current_mode
        )


class CommandEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: UUID = Field(default_factory=uuid4)
    action: CanonicalAction
    scope: CommandScope
    idempotency_key: str | None = None
    target_mode: str | None = None
    surface: str | None = None
    surface_metadata: dict[str, SurfaceMetadataValue] = Field(default_factory=dict)

    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, value: str | CanonicalAction) -> CanonicalAction:
        if isinstance(value, str):
            return normalize_action(value)
        if value not in CANONICAL_ACTIONS:
            raise ValueError("action must be a canonical action")
        return value

    @field_validator("idempotency_key", "target_mode", "surface")
    @classmethod
    def validate_text_fields(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name=info.field_name)

    @field_validator("surface_metadata")
    @classmethod
    def validate_surface_metadata(
        cls,
        value: dict[str, SurfaceMetadataValue],
    ) -> dict[str, SurfaceMetadataValue]:
        return {_require_text(key, field_name="surface_metadata key"): item for key, item in value.items()}

    @model_validator(mode="after")
    def validate_mode_switch_fields(self) -> CommandEnvelope:
        if self.action == "mode switch" and self.target_mode is None:
            raise ValueError("target_mode is required for mode switch")
        if self.action != "mode switch" and self.target_mode is not None:
            raise ValueError("target_mode is only valid for mode switch")
        return self

    def semantic_fingerprint(self) -> tuple[object, ...]:
        return (self.action, *self.scope.scope_key(), self.target_mode)


__all__ = [
    "CANONICAL_ACTIONS",
    "CONTROL_ACTIONS",
    "CommandEnvelope",
    "CommandScope",
    "ModeSwitchReceipt",
    "OBSERVATION_ONLY_MODE",
    "normalize_action",
]
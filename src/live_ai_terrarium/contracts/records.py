from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ids import AgentId, CycleId, ExperimentId, GlassBoxId, IncidentId, MutationId, ProjectId, RunId

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
GIT_SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")
IMAGE_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")

StopConditionType = Literal[
    "repeated crashes",
    "syntax failure",
    "regression or score drop",
    "forbidden action attempt",
    "resource overuse",
    "log silence",
]


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactRef(ContractModel):
    uuid: UUID
    locator: str

    @field_validator("locator")
    @classmethod
    def validate_locator(cls, value: str) -> str:
        return _require_text(value, field_name="locator")


class RunLimits(ContractModel):
    values: dict[str, int | float | bool | str]

    @field_validator("values")
    @classmethod
    def validate_values(cls, value: dict[str, int | float | bool | str]) -> dict[str, int | float | bool | str]:
        if not value:
            raise ValueError("values must not be empty")
        return value


class HashOrSnapshot(ContractModel):
    sha256: str | None = None
    snapshot_ref: ArtifactRef | None = None

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("sha256 must be a 64-character lowercase hexadecimal digest")
        return value

    @model_validator(mode="after")
    def validate_source(self) -> HashOrSnapshot:
        if self.sha256 is None and self.snapshot_ref is None:
            raise ValueError("either sha256 or snapshot_ref is required")
        return self


class TokenUsage(ContractModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> TokenUsage:
        if self.total_tokens < self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must be at least input_tokens + output_tokens")
        return self


class ResourceUsage(ContractModel):
    cpu_percent: float = Field(ge=0, le=100)
    ram_mb: int = Field(ge=0)
    disk_mb: int = Field(ge=0)


class RunRecord(ContractModel):
    project_id: ProjectId
    glass_box_id: GlassBoxId
    experiment_id: ExperimentId
    run_id: RunId
    task_identity: str
    seed: int
    limits: RunLimits
    model_version: str
    outer_repo_commit_sha: str
    container_image_digest: str
    release_tag: str | None = None
    image_name_label: str | None = None
    runtime_profile: HashOrSnapshot
    command_catalog: HashOrSnapshot
    audit_event_refs: list[ArtifactRef] = Field(default_factory=list)
    full_log_bundle_ref: ArtifactRef | None = None

    @field_validator("task_identity", "model_version")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @field_validator("release_tag", "image_name_label")
    @classmethod
    def validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name=info.field_name)

    @field_validator("outer_repo_commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str) -> str:
        if not GIT_SHA_PATTERN.fullmatch(value):
            raise ValueError("outer_repo_commit_sha must be a 40-character lowercase hexadecimal SHA")
        return value

    @field_validator("container_image_digest")
    @classmethod
    def validate_container_digest(cls, value: str) -> str:
        if not IMAGE_DIGEST_PATTERN.fullmatch(value):
            raise ValueError("container_image_digest must be a sha256 digest")
        return value


class CycleRecord(ContractModel):
    project_id: ProjectId
    glass_box_id: GlassBoxId
    experiment_id: ExperimentId
    run_id: RunId
    cycle_id: CycleId
    mutation_id: MutationId
    task_identity: str
    diff_summary: str | None = None
    diff_ref: ArtifactRef | None = None
    gate_decision: str
    score: float
    test_result: str
    error_summary: str | None
    model_identity: str
    prompt_ref: ArtifactRef
    token_usage: TokenUsage
    latency_ms: int = Field(ge=0)
    resources: ResourceUsage
    snapshot_refs: list[ArtifactRef] = Field(min_length=1)
    audit_event_refs: list[ArtifactRef] = Field(min_length=1)
    full_log_bundle_ref: ArtifactRef

    @field_validator("task_identity", "gate_decision", "test_result", "model_identity")
    @classmethod
    def validate_cycle_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @field_validator("diff_summary")
    @classmethod
    def validate_diff_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name="diff_summary")

    @field_validator("error_summary")
    @classmethod
    def validate_error_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name="error_summary")

    @model_validator(mode="after")
    def validate_diff_evidence(self) -> CycleRecord:
        if self.diff_summary is None and self.diff_ref is None:
            raise ValueError("either diff_summary or diff_ref is required")
        return self


class IncidentRecord(ContractModel):
    incident_id: IncidentId
    run_id: RunId
    cycle_id: CycleId
    stop_condition_type: StopConditionType
    trigger_detail: str
    snapshot_ref: ArtifactRef
    branch_ref: ArtifactRef | None = None
    recovery_outcome: str | None = None
    incident_report_ref: ArtifactRef

    @field_validator("trigger_detail")
    @classmethod
    def validate_trigger_detail(cls, value: str) -> str:
        return _require_text(value, field_name="trigger_detail")

    @field_validator("recovery_outcome")
    @classmethod
    def validate_recovery_outcome(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name="recovery_outcome")


class AnnotationRecord(ContractModel):
    uuid: UUID
    run_id: RunId
    cycle_id: CycleId | None = None
    annotator_agent_id: AgentId
    annotation: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("annotation")
    @classmethod
    def validate_annotation(cls, value: str) -> str:
        return _require_text(value, field_name="annotation")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        return [_require_text(tag, field_name="tag") for tag in value]


__all__ = [
    "AnnotationRecord",
    "ArtifactRef",
    "CycleRecord",
    "HashOrSnapshot",
    "IncidentRecord",
    "ResourceUsage",
    "RunLimits",
    "RunRecord",
    "StopConditionType",
    "TokenUsage",
]
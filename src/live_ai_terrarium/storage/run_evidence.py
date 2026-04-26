from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from live_ai_terrarium.audit.ledger import AuditLedger, AuditLedgerIntegrityError
from live_ai_terrarium.control.commands import CommandScope
from live_ai_terrarium.contracts.records import (
    ArtifactRef,
    GIT_SHA_PATTERN,
    IMAGE_DIGEST_PATTERN,
    HashOrSnapshot,
    RunLimits,
)
from live_ai_terrarium.storage.filesystem import HostFilesystem
from live_ai_terrarium.storage.paths import CycleScope, RunScope, StoragePaths


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


class EvidenceLookupError(FileNotFoundError):
    pass


class RunEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RunStartManifest(RunEvidenceModel):
    uuid: UUID = Field(default_factory=uuid4)
    created_at: str
    project_id: str
    glass_box_id: str
    experiment_id: str
    run_id: str
    task_identity: str
    seed: int
    limits: RunLimits
    model_version: str
    outer_repo_commit_sha: str
    container_image_digest: str
    runtime_profile: HashOrSnapshot
    command_catalog: HashOrSnapshot
    supplemental_labels: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "created_at",
        "project_id",
        "glass_box_id",
        "experiment_id",
        "run_id",
        "task_identity",
        "model_version",
    )
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @field_validator("outer_repo_commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str) -> str:
        if not GIT_SHA_PATTERN.fullmatch(value):
            raise ValueError("outer_repo_commit_sha must be a 40-character lowercase hexadecimal SHA")
        return value

    @field_validator("container_image_digest")
    @classmethod
    def validate_image_digest(cls, value: str) -> str:
        if not IMAGE_DIGEST_PATTERN.fullmatch(value):
            raise ValueError("container_image_digest must be a sha256 digest")
        return value

    @field_validator("supplemental_labels")
    @classmethod
    def validate_supplemental_labels(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            _require_text(key, field_name="supplemental_labels key"): _require_text(
                item,
                field_name=f"supplemental_labels[{key}]",
            )
            for key, item in value.items()
        }


class CycleAuditLink(RunEvidenceModel):
    uuid: UUID = Field(default_factory=uuid4)
    project_id: str
    glass_box_id: str
    experiment_id: str
    run_id: str
    cycle_id: str
    audit_event_refs: list[ArtifactRef] = Field(min_length=1)
    full_log_bundle_ref: ArtifactRef
    log_sequence_start: int = Field(ge=1)
    log_sequence_end: int = Field(ge=1)

    @field_validator("project_id", "glass_box_id", "experiment_id", "run_id", "cycle_id")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_log_sequence_window(self) -> CycleAuditLink:
        if self.log_sequence_end < self.log_sequence_start:
            raise ValueError("log_sequence_end must be greater than or equal to log_sequence_start")
        return self


class ProofConsumerEvidence(RunEvidenceModel):
    manifest: RunStartManifest
    manifest_ref: ArtifactRef
    cycle_link: CycleAuditLink
    cycle_link_ref: ArtifactRef
    full_log_bundle_ref: ArtifactRef
    audit_event_refs: list[ArtifactRef]


class RunEvidenceStore:
    def __init__(
        self,
        storage_paths: StoragePaths,
        filesystem: HostFilesystem | None = None,
        audit_ledger: AuditLedger | None = None,
    ) -> None:
        self._storage_paths = storage_paths
        self._filesystem = filesystem or HostFilesystem(storage_paths)
        self._audit_ledger = audit_ledger or AuditLedger(storage_paths)

    def create_run_manifest(
        self,
        run: RunScope,
        *,
        created_at: str,
        task_identity: str,
        seed: int,
        limits: dict[str, int | float | bool | str] | RunLimits,
        model_version: str,
        outer_repo_commit_sha: str,
        container_image_digest: str,
        runtime_profile: HashOrSnapshot,
        command_catalog: HashOrSnapshot,
        supplemental_labels: dict[str, str] | None = None,
    ) -> RunStartManifest:
        manifest = RunStartManifest(
            created_at=created_at,
            project_id=run.project_id,
            glass_box_id=run.glassbox_id,
            experiment_id=run.experiment_id,
            run_id=run.run_id,
            task_identity=task_identity,
            seed=seed,
            limits=self._coerce_limits(limits),
            model_version=model_version,
            outer_repo_commit_sha=outer_repo_commit_sha,
            container_image_digest=container_image_digest,
            runtime_profile=runtime_profile,
            command_catalog=command_catalog,
            supplemental_labels=supplemental_labels or {},
        )
        manifest_path = self._storage_paths.run_manifest_file(run)
        try:
            self._filesystem.write_json(manifest_path, manifest.model_dump(mode="json"))
        except FileExistsError as error:
            raise FileExistsError(f"Append-only run-start reproducibility manifest already exists: {manifest_path}") from error
        return manifest

    def read_run_manifest(self, run: RunScope) -> RunStartManifest:
        manifest_path = self._storage_paths.run_manifest_file(run)
        if not manifest_path.exists():
            raise EvidenceLookupError(f"Missing run-start reproducibility manifest: {manifest_path}")
        return RunStartManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    def link_cycle_to_audit(
        self,
        cycle: CycleScope,
        *,
        audit_event_refs: list[ArtifactRef],
        full_log_bundle_ref: ArtifactRef,
        log_sequence_start: int,
        log_sequence_end: int,
    ) -> CycleAuditLink:
        self.read_run_manifest(cycle.run)
        link = CycleAuditLink(
            project_id=cycle.run.project_id,
            glass_box_id=cycle.run.glassbox_id,
            experiment_id=cycle.run.experiment_id,
            run_id=cycle.run.run_id,
            cycle_id=cycle.cycle_id,
            audit_event_refs=audit_event_refs,
            full_log_bundle_ref=full_log_bundle_ref,
            log_sequence_start=log_sequence_start,
            log_sequence_end=log_sequence_end,
        )
        self._filesystem.write_json(self._cycle_link_path(cycle), link.model_dump(mode="json"))
        return link

    def read_cycle_link(self, cycle: CycleScope) -> CycleAuditLink:
        link_path = self._cycle_link_path(cycle)
        if not link_path.exists():
            raise EvidenceLookupError(f"Missing cycle-to-audit linkage: {link_path}")
        return CycleAuditLink.model_validate_json(link_path.read_text(encoding="utf-8"))

    def lookup_cycle_proof_evidence(self, cycle: CycleScope) -> ProofConsumerEvidence:
        manifest = self.read_run_manifest(cycle.run)
        cycle_link = self.read_cycle_link(cycle)
        self._resolve_verified_audit_refs(cycle.run, cycle_link.audit_event_refs)
        bundle_path = Path(cycle_link.full_log_bundle_ref.locator)
        if not bundle_path.exists():
            raise EvidenceLookupError(f"Missing full-log bundle: {bundle_path}")
        return ProofConsumerEvidence(
            manifest=manifest,
            manifest_ref=ArtifactRef(uuid=manifest.uuid, locator=str(self._storage_paths.run_manifest_file(cycle.run))),
            cycle_link=cycle_link,
            cycle_link_ref=ArtifactRef(uuid=cycle_link.uuid, locator=str(self._cycle_link_path(cycle))),
            full_log_bundle_ref=cycle_link.full_log_bundle_ref,
            audit_event_refs=cycle_link.audit_event_refs,
        )

    def _cycle_link_path(self, cycle: CycleScope) -> Path:
        return self._storage_paths.state_root.joinpath(
            "evidence",
            "projects",
            cycle.run.project_id,
            "glassboxes",
            cycle.run.glassbox_id,
            "experiments",
            cycle.run.experiment_id,
            "runs",
            cycle.run.run_id,
            "cycles",
            f"{cycle.cycle_id}-audit-link.json",
        )

    def _coerce_limits(self, limits: dict[str, int | float | bool | str] | RunLimits) -> RunLimits:
        if isinstance(limits, RunLimits):
            return limits
        return RunLimits(values=limits)

    def _resolve_verified_audit_refs(
        self,
        run: RunScope,
        audit_event_refs: list[ArtifactRef],
    ) -> None:
        scope = CommandScope(
            project_id=run.project_id,
            glass_box_id=run.glassbox_id,
            experiment_id=run.experiment_id,
            run_id=run.run_id,
        )
        try:
            verified_entries = self._audit_ledger.verify_run_chain(scope)
        except AuditLedgerIntegrityError as error:
            raise EvidenceLookupError(f"audit chain verification failed: {error}") from error

        canonical_locator = self._audit_ledger.ledger_path_for_scope(scope).resolve(strict=False)
        verified_event_ids = {entry.event_id for entry in verified_entries}
        for ref in audit_event_refs:
            locator = Path(ref.locator).resolve(strict=False)
            if locator != canonical_locator or ref.uuid not in verified_event_ids:
                raise EvidenceLookupError(
                    f"audit ref could not be resolved against the canonical audit ledger: {ref.locator}"
                )


__all__ = [
    "CycleAuditLink",
    "EvidenceLookupError",
    "ProofConsumerEvidence",
    "RunEvidenceStore",
    "RunStartManifest",
]
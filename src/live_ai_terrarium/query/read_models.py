from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from live_ai_terrarium.contracts.records import ResourceUsage, TokenUsage
from live_ai_terrarium.control.commands import CanonicalAction
from live_ai_terrarium.orchestrator.runtime import LifecycleState

ObservationModeState = Literal[
    "observation-only",
    "mode-switch requested",
    "mode-switch active",
    "paused",
    "incident open",
    "recovery executing",
    "recovery completed",
]
ApprovalState = Literal["not-requested", "requested", "approved", "rejected"]
IncidentState = Literal["clear", "open"]


@dataclass(frozen=True, slots=True)
class ReproducibilityManifestSummary:
    created_at: str
    task_identity: str
    seed: int
    model_version: str
    outer_repo_commit_sha: str
    container_image_digest: str
    limits: dict[str, int | float | bool | str]
    release_tag: str | None
    image_name: str | None
    runtime_profile_locator: str | None
    runtime_profile_sha256: str | None
    command_catalog_locator: str | None
    command_catalog_sha256: str | None


@dataclass(frozen=True, slots=True)
class ActiveModeSwitchReceiptView:
    receipt_id: UUID
    target_mode: str
    mode_context: str
    status: str = "active"


@dataclass(frozen=True, slots=True)
class CommandReceiptView:
    action: CanonicalAction
    status: str
    occurred_at: str
    actor_id: str
    actor_role: str
    cycle_id: str | None
    approval_id: UUID | None
    receipt_id: UUID | None
    target_mode: str | None
    target_cycle_id: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class AuditStatusView:
    latest_command_receipts: dict[CanonicalAction, CommandReceiptView]
    timeline: tuple[CommandReceiptView, ...]


@dataclass(frozen=True, slots=True)
class CycleSummaryView:
    cycle_id: str
    gate_decision: str
    score: float
    test_result: str
    error_summary: str | None
    full_log_bundle_ref: str
    log_sequence_range: tuple[int, int] | None
    has_incident: bool


@dataclass(frozen=True, slots=True)
class ReversibilityView:
    incident_state: IncidentState
    incident_id: str | None
    incident_report_ref: str | None
    snapshot_ref: str | None
    branch_ref: str | None
    ordered_steps: tuple[str, ...]
    full_log_refs: tuple[str, ...]
    last_stable_cycle: str | None
    rollback_target: str | None
    recovery_outcome: str | None
    restore_manifest_ref: str | None


@dataclass(frozen=True, slots=True)
class RunSummaryView:
    run_id: str
    current_mode: str
    lifecycle_state: LifecycleState
    observation_mode_state: ObservationModeState
    active_mode_switch_receipt: ActiveModeSwitchReceiptView | None
    available_actions: tuple[CanonicalAction, ...]
    deny_reason_by_action: dict[CanonicalAction, str]
    audit_status: AuditStatusView
    approval_status: ApprovalState
    incident_state: IncidentState
    last_stable_cycle: str | None
    rollback_target: str | None
    snapshot_refs: tuple[str, ...]
    branch_clone_refs: tuple[str, ...]
    reproducibility_manifest: ReproducibilityManifestSummary
    full_log_bundle_refs: tuple[str, ...]
    cycle_summaries: tuple[CycleSummaryView, ...]


@dataclass(frozen=True, slots=True)
class CycleDetailView:
    run_id: str
    cycle_id: str
    current_mode: str
    lifecycle_state: LifecycleState
    observation_mode_state: ObservationModeState
    active_mode_switch_receipt: ActiveModeSwitchReceiptView | None
    available_actions: tuple[CanonicalAction, ...]
    deny_reason_by_action: dict[CanonicalAction, str]
    approval_status: ApprovalState
    gate_decision: str
    score: float
    test_result: str
    error_summary: str | None
    diff_summary: str | None
    model_identity: str
    prompt_ref: str
    token_usage: TokenUsage
    latency_ms: int
    resources: ResourceUsage
    snapshot_refs: tuple[str, ...]
    audit_event_refs: tuple[str, ...]
    full_log_bundle_ref: str
    audit_timeline: tuple[CommandReceiptView, ...]
    reversibility: ReversibilityView
    reproducibility_manifest: ReproducibilityManifestSummary


__all__ = [
    "ActiveModeSwitchReceiptView",
    "ApprovalState",
    "AuditStatusView",
    "CommandReceiptView",
    "CycleDetailView",
    "CycleSummaryView",
    "IncidentState",
    "ObservationModeState",
    "ReproducibilityManifestSummary",
    "ReversibilityView",
    "RunSummaryView",
]
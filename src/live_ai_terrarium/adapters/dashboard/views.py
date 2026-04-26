from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from live_ai_terrarium.control.commands import CANONICAL_ACTIONS, CanonicalAction, CommandEnvelope, CommandScope
from live_ai_terrarium.query.read_models import CommandReceiptView, CycleDetailView, RunSummaryView

PageName = str
_DEFAULT_MAX_CYCLES = 10


class DashboardBackend(Protocol):
    def load_run_summary(self, scope: CommandScope) -> RunSummaryView: ...

    def load_cycle_detail(self, scope: CommandScope, cycle_id: str) -> CycleDetailView: ...

    def dispatch_command(
        self,
        command: CommandEnvelope,
        *,
        cycle_id: str | None,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        reason: str | None = None,
    ) -> dict[str, object] | None: ...


@dataclass(frozen=True, slots=True)
class SidebarView:
    scope: CommandScope
    current_mode_badge: str
    active_receipt_badge: str | None


@dataclass(frozen=True, slots=True)
class TopStatusView:
    current_cycle_id: str | None
    stable_cycle_count: int
    latest_decision: str | None
    incident_state: str
    last_stable_cycle: str | None
    rollback_target: str | None


@dataclass(frozen=True, slots=True)
class ActionControlView:
    action: CanonicalAction
    label: str
    enabled: bool
    deny_reason: str | None


@dataclass(frozen=True, slots=True)
class CycleRowView:
    cycle_id: str
    decision: str
    score: float
    test_result: str
    error_summary: str | None
    diff_summary: str | None
    model_identity: str | None
    prompt_ref: str | None
    total_tokens: int | None
    latency_ms: int | None
    cpu_percent: float | None
    ram_mb: int | None
    disk_mb: int | None
    full_log_bundle_ref: str
    has_incident: bool


@dataclass(frozen=True, slots=True)
class RunOverviewView:
    summary_cards: dict[str, str]
    cycle_rows: tuple[CycleRowView, ...]
    score_trend: tuple[tuple[str, float], ...]
    decision_trend: tuple[tuple[str, str], ...]
    token_latency_trend: tuple[tuple[str, int | None, int | None], ...]
    resource_trend: tuple[tuple[str, float | None, int | None, int | None], ...]
    failures_panel: dict[str, object]


@dataclass(frozen=True, slots=True)
class CycleDetailPanelView:
    cycle_id: str
    diff_summary: str | None
    decision: str
    score: float
    test_result: str
    error_summary: str | None
    model_identity: str
    prompt_ref: str
    total_tokens: int
    latency_ms: int
    cpu_percent: float
    ram_mb: int
    disk_mb: int
    snapshot_refs: tuple[str, ...]
    audit_timeline: tuple[CommandReceiptView, ...]
    incident_state: str
    last_stable_cycle: str | None
    rollback_target: str | None
    branch_ref: str | None
    recovery_outcome: str | None


@dataclass(frozen=True, slots=True)
class ApprovalsAuditView:
    control_state: str
    pending_approval_count: int
    active_mode_switch_receipt: str | None
    timeline: tuple[CommandReceiptView, ...]
    deny_reasons: dict[CanonicalAction, str]


@dataclass(frozen=True, slots=True)
class IncidentsRecoveryView:
    incident_state: str
    incident_id: str | None
    incident_report_ref: str | None
    snapshot_refs: tuple[str, ...]
    branch_refs: tuple[str, ...]
    last_stable_cycle: str | None
    rollback_target: str | None
    reset_anchor: str | None
    recovery_outcome: str | None
    latest_recovery_receipts: tuple[CommandReceiptView, ...]


@dataclass(frozen=True, slots=True)
class DashboardState:
    scope: CommandScope
    sidebar: SidebarView
    top_status: TopStatusView
    action_rail: tuple[ActionControlView, ...]
    run_overview: RunOverviewView
    cycle_detail: CycleDetailPanelView | None
    approvals_audit: ApprovalsAuditView
    incidents_recovery: IncidentsRecoveryView


@dataclass(frozen=True, slots=True)
class DashboardActionResult:
    action: CanonicalAction
    command: CommandEnvelope | None
    receipt_payload: dict[str, object] | None
    refreshed_state: DashboardState | None


class DashboardController:
    def __init__(self, backend: DashboardBackend) -> None:
        self._backend = backend

    def load(
        self,
        *,
        scope: CommandScope,
        selected_cycle_id: str | None = None,
    ) -> DashboardState:
        run_summary = self._backend.load_run_summary(scope)
        effective_cycle_id = selected_cycle_id or self._default_cycle_id(run_summary)
        cycle_detail = None if effective_cycle_id is None else self._backend.load_cycle_detail(scope, effective_cycle_id)
        return self._build_state(
            scope=scope,
            run_summary=run_summary,
            cycle_detail=cycle_detail,
            selected_cycle_id=effective_cycle_id,
        )

    def perform_action(
        self,
        *,
        action: CanonicalAction,
        scope: CommandScope,
        selected_cycle_id: str | None = None,
        target_mode: str | None = None,
        clone_run_id: str | None = None,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        reason: str | None = None,
    ) -> DashboardActionResult:
        if action == "observe":
            return DashboardActionResult(
                action=action,
                command=None,
                receipt_payload=None,
                refreshed_state=self.load(scope=scope, selected_cycle_id=selected_cycle_id),
            )

        command = self._build_command(
            action=action,
            scope=scope,
            selected_cycle_id=selected_cycle_id,
            target_mode=target_mode,
            clone_run_id=clone_run_id,
        )
        payload = self._backend.dispatch_command(
            command,
            cycle_id=selected_cycle_id,
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            mode_context=mode_context,
            reason=reason,
        )
        return DashboardActionResult(
            action=action,
            command=command,
            receipt_payload=None if payload is None else dict(payload),
            refreshed_state=None,
        )

    def _build_state(
        self,
        *,
        scope: CommandScope,
        run_summary: RunSummaryView,
        cycle_detail: CycleDetailView | None,
        selected_cycle_id: str | None,
    ) -> DashboardState:
        stable_cycle_count = sum(1 for cycle in run_summary.cycle_summaries if cycle.gate_decision == "accepted")
        max_cycles = self._max_cycles(run_summary)
        latest_cycle = self._latest_cycle(run_summary)

        sidebar = SidebarView(
            scope=scope,
            current_mode_badge=run_summary.current_mode,
            active_receipt_badge=(
                None
                if run_summary.active_mode_switch_receipt is None
                else str(run_summary.active_mode_switch_receipt.receipt_id)
            ),
        )
        top_status = TopStatusView(
            current_cycle_id=selected_cycle_id or (None if latest_cycle is None else latest_cycle.cycle_id),
            stable_cycle_count=stable_cycle_count,
            latest_decision=None if latest_cycle is None else latest_cycle.gate_decision,
            incident_state=run_summary.incident_state,
            last_stable_cycle=run_summary.last_stable_cycle,
            rollback_target=run_summary.rollback_target,
        )
        action_rail = tuple(
            ActionControlView(
                action=action,
                label=action.title(),
                enabled=action in run_summary.available_actions,
                deny_reason=run_summary.deny_reason_by_action.get(action),
            )
            for action in CANONICAL_ACTIONS
        )
        run_overview = RunOverviewView(
            summary_cards={
                "Current mode": run_summary.current_mode,
                "Latest cycle decision": "-" if latest_cycle is None else latest_cycle.gate_decision,
                "Latest score": "-" if latest_cycle is None else f"{latest_cycle.score:.2f}",
                "Latest test result": "-" if latest_cycle is None else latest_cycle.test_result,
                "Incident state": run_summary.incident_state,
                "Stable-cycle count": f"{stable_cycle_count}/{max_cycles}",
            },
            cycle_rows=self._cycle_rows(run_summary, cycle_detail),
            score_trend=tuple((cycle.cycle_id, cycle.score) for cycle in run_summary.cycle_summaries),
            decision_trend=tuple((cycle.cycle_id, cycle.gate_decision) for cycle in run_summary.cycle_summaries),
            token_latency_trend=tuple(
                (
                    row.cycle_id,
                    row.total_tokens,
                    row.latency_ms,
                )
                for row in self._cycle_rows(run_summary, cycle_detail)
            ),
            resource_trend=tuple(
                (
                    row.cycle_id,
                    row.cpu_percent,
                    row.ram_mb,
                    row.disk_mb,
                )
                for row in self._cycle_rows(run_summary, cycle_detail)
            ),
            failures_panel={
                "open_incident_count": sum(1 for cycle in run_summary.cycle_summaries if cycle.has_incident),
                "last_stop_condition": self._last_recovery_outcome(cycle_detail),
                "recovery_page": "Incidents And Recovery",
            },
        )
        approvals_audit = ApprovalsAuditView(
            control_state=run_summary.observation_mode_state,
            pending_approval_count=1 if run_summary.approval_status == "requested" else 0,
            active_mode_switch_receipt=(
                None
                if run_summary.active_mode_switch_receipt is None
                else str(run_summary.active_mode_switch_receipt.receipt_id)
            ),
            timeline=run_summary.audit_status.timeline,
            deny_reasons=dict(run_summary.deny_reason_by_action),
        )
        incidents_recovery = IncidentsRecoveryView(
            incident_state=(
                run_summary.incident_state
                if cycle_detail is None
                else cycle_detail.reversibility.incident_state
            ),
            incident_id=None if cycle_detail is None else cycle_detail.reversibility.incident_id,
            incident_report_ref=(
                None if cycle_detail is None else cycle_detail.reversibility.incident_report_ref
            ),
            snapshot_refs=(
                run_summary.snapshot_refs
                if cycle_detail is None
                else self._unique((*cycle_detail.snapshot_refs, *run_summary.snapshot_refs))
            ),
            branch_refs=self._branch_refs(run_summary, cycle_detail),
            last_stable_cycle=(
                run_summary.last_stable_cycle
                if cycle_detail is None
                else cycle_detail.reversibility.last_stable_cycle
            ),
            rollback_target=(
                run_summary.rollback_target
                if cycle_detail is None
                else cycle_detail.reversibility.rollback_target
            ),
            reset_anchor=run_summary.last_stable_cycle,
            recovery_outcome=self._last_recovery_outcome(cycle_detail),
            latest_recovery_receipts=self._recovery_receipts(run_summary, cycle_detail),
        )
        cycle_panel = None if cycle_detail is None else self._cycle_panel(cycle_detail)
        return DashboardState(
            scope=scope,
            sidebar=sidebar,
            top_status=top_status,
            action_rail=action_rail,
            run_overview=run_overview,
            cycle_detail=cycle_panel,
            approvals_audit=approvals_audit,
            incidents_recovery=incidents_recovery,
        )

    def _build_command(
        self,
        *,
        action: CanonicalAction,
        scope: CommandScope,
        selected_cycle_id: str | None,
        target_mode: str | None,
        clone_run_id: str | None,
    ) -> CommandEnvelope:
        surface_metadata: dict[str, str] = {}
        if action == "mode switch":
            if target_mode is None or not target_mode.strip():
                raise ValueError("mode switch dashboard actions require target_mode")
            return CommandEnvelope(
                action=action,
                scope=scope,
                target_mode=target_mode,
                surface="dashboard",
                surface_metadata=surface_metadata,
            )
        if action == "clone":
            if clone_run_id is None or not clone_run_id.strip():
                raise ValueError("clone dashboard actions require clone_run_id")
            surface_metadata["clone_run_id"] = clone_run_id
        if action == "rollback":
            if selected_cycle_id is None or not selected_cycle_id.strip():
                raise ValueError("rollback dashboard actions require selected_cycle_id")
            surface_metadata["target_cycle_id"] = selected_cycle_id
        return CommandEnvelope(
            action=action,
            scope=scope,
            surface="dashboard",
            surface_metadata=surface_metadata,
        )

    def _cycle_panel(self, cycle_detail: CycleDetailView) -> CycleDetailPanelView:
        return CycleDetailPanelView(
            cycle_id=cycle_detail.cycle_id,
            diff_summary=cycle_detail.diff_summary,
            decision=cycle_detail.gate_decision,
            score=cycle_detail.score,
            test_result=cycle_detail.test_result,
            error_summary=cycle_detail.error_summary,
            model_identity=cycle_detail.model_identity,
            prompt_ref=cycle_detail.prompt_ref,
            total_tokens=cycle_detail.token_usage.total_tokens,
            latency_ms=cycle_detail.latency_ms,
            cpu_percent=cycle_detail.resources.cpu_percent,
            ram_mb=cycle_detail.resources.ram_mb,
            disk_mb=cycle_detail.resources.disk_mb,
            snapshot_refs=cycle_detail.snapshot_refs,
            audit_timeline=cycle_detail.audit_timeline,
            incident_state=cycle_detail.reversibility.incident_state,
            last_stable_cycle=cycle_detail.reversibility.last_stable_cycle,
            rollback_target=cycle_detail.reversibility.rollback_target,
            branch_ref=cycle_detail.reversibility.branch_ref,
            recovery_outcome=cycle_detail.reversibility.recovery_outcome,
        )

    def _cycle_rows(
        self,
        run_summary: RunSummaryView,
        cycle_detail: CycleDetailView | None,
    ) -> tuple[CycleRowView, ...]:
        rows: list[CycleRowView] = []
        for cycle in run_summary.cycle_summaries:
            detail = cycle_detail if cycle_detail is not None and cycle_detail.cycle_id == cycle.cycle_id else None
            rows.append(
                CycleRowView(
                    cycle_id=cycle.cycle_id,
                    decision=cycle.gate_decision,
                    score=cycle.score,
                    test_result=cycle.test_result,
                    error_summary=cycle.error_summary,
                    diff_summary=None if detail is None else detail.diff_summary,
                    model_identity=None if detail is None else detail.model_identity,
                    prompt_ref=None if detail is None else detail.prompt_ref,
                    total_tokens=None if detail is None else detail.token_usage.total_tokens,
                    latency_ms=None if detail is None else detail.latency_ms,
                    cpu_percent=None if detail is None else detail.resources.cpu_percent,
                    ram_mb=None if detail is None else detail.resources.ram_mb,
                    disk_mb=None if detail is None else detail.resources.disk_mb,
                    full_log_bundle_ref=cycle.full_log_bundle_ref,
                    has_incident=cycle.has_incident,
                )
            )
        return tuple(rows)

    def _recovery_receipts(
        self,
        run_summary: RunSummaryView,
        cycle_detail: CycleDetailView | None,
    ) -> tuple[CommandReceiptView, ...]:
        timeline = run_summary.audit_status.timeline if cycle_detail is None else cycle_detail.audit_timeline
        return tuple(receipt for receipt in timeline if receipt.action in {"branch", "clone", "reset", "rollback", "pause", "resume"})

    def _branch_refs(
        self,
        run_summary: RunSummaryView,
        cycle_detail: CycleDetailView | None,
    ) -> tuple[str, ...]:
        detail_refs: tuple[str, ...] = ()
        if cycle_detail is not None and cycle_detail.reversibility.branch_ref is not None:
            detail_refs = (cycle_detail.reversibility.branch_ref,)
        return self._unique((*run_summary.branch_clone_refs, *detail_refs))

    def _last_recovery_outcome(self, cycle_detail: CycleDetailView | None) -> str | None:
        if cycle_detail is None:
            return None
        return cycle_detail.reversibility.recovery_outcome

    def _default_cycle_id(self, run_summary: RunSummaryView) -> str | None:
        latest_cycle = self._latest_cycle(run_summary)
        if latest_cycle is None:
            return None
        return latest_cycle.cycle_id

    def _latest_cycle(self, run_summary: RunSummaryView):
        if not run_summary.cycle_summaries:
            return None
        return run_summary.cycle_summaries[-1]

    def _max_cycles(self, run_summary: RunSummaryView) -> int:
        value = run_summary.reproducibility_manifest.limits.get("max_cycles")
        if isinstance(value, int):
            return value
        return _DEFAULT_MAX_CYCLES

    def _unique(self, values: tuple[str, ...] | list[str] | tuple[str | None, ...]) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value is None or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return tuple(ordered)


__all__ = [
    "ActionControlView",
    "ApprovalsAuditView",
    "CycleDetailPanelView",
    "CycleRowView",
    "DashboardActionResult",
    "DashboardBackend",
    "DashboardController",
    "DashboardState",
    "IncidentsRecoveryView",
    "RunOverviewView",
    "SidebarView",
    "TopStatusView",
]
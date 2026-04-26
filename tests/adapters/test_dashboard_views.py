from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from live_ai_terrarium.adapters.dashboard.views import DashboardController
from live_ai_terrarium.contracts.records import ResourceUsage, TokenUsage
from live_ai_terrarium.control.commands import CANONICAL_ACTIONS, CommandEnvelope, CommandScope
from live_ai_terrarium.query.read_models import (
    ActiveModeSwitchReceiptView,
    AuditStatusView,
    CommandReceiptView,
    CycleDetailView,
    CycleSummaryView,
    ReproducibilityManifestSummary,
    ReversibilityView,
    RunSummaryView,
)


def make_scope() -> CommandScope:
    return CommandScope(
        project_id="project-live-ai-terrarium",
        glass_box_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id="run-stability-baseline",
    )


def make_manifest_summary() -> ReproducibilityManifestSummary:
    return ReproducibilityManifestSummary(
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-016",
        seed=7,
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        limits={"max_cycles": 10, "max_cpu_percent": 90},
        release_tag="milestone/v1-wave7",
        image_name="glassbox:v1",
        runtime_profile_locator="security/runtime-profile.yaml",
        runtime_profile_sha256=None,
        command_catalog_locator="security/command-specs.yaml",
        command_catalog_sha256=None,
    )


def make_timeline() -> tuple[CommandReceiptView, ...]:
    mode_switch_receipt_id = uuid4()
    approval_id = uuid4()
    return (
        CommandReceiptView(
            action="mode switch",
            status="requested",
            occurred_at="2026-04-26T10:00:00Z",
            actor_id="observer-1",
            actor_role="operator",
            cycle_id=None,
            approval_id=None,
            receipt_id=None,
            target_mode=None,
            target_cycle_id=None,
            reason="Need intervention for incident triage.",
        ),
        CommandReceiptView(
            action="mode switch",
            status="approval_requested",
            occurred_at="2026-04-26T10:00:01Z",
            actor_id="observer-1",
            actor_role="operator",
            cycle_id=None,
            approval_id=approval_id,
            receipt_id=None,
            target_mode=None,
            target_cycle_id=None,
            reason="Need intervention for incident triage.",
        ),
        CommandReceiptView(
            action="mode switch",
            status="approved",
            occurred_at="2026-04-26T10:00:02Z",
            actor_id="approver-1",
            actor_role="observer",
            cycle_id=None,
            approval_id=approval_id,
            receipt_id=mode_switch_receipt_id,
            target_mode="control-enabled",
            target_cycle_id=None,
            reason="Approved for rollback prep.",
        ),
        CommandReceiptView(
            action="rollback",
            status="completed",
            occurred_at="2026-04-26T10:05:15Z",
            actor_id="operator-1",
            actor_role="operator",
            cycle_id="cycle-0002",
            approval_id=None,
            receipt_id=None,
            target_mode=None,
            target_cycle_id="cycle-0001",
            reason=None,
        ),
    )


def make_run_summary() -> RunSummaryView:
    timeline = make_timeline()
    return RunSummaryView(
        run_id="run-stability-baseline",
        current_mode="observation-only",
        lifecycle_state="active",
        observation_mode_state="observation-only",
        active_mode_switch_receipt=None,
        available_actions=("observe", "mode switch"),
        deny_reason_by_action={
            "pause": "Active mode-switch receipt required for this scope.",
            "resume": "Active mode-switch receipt required for this scope.",
            "branch": "Active mode-switch receipt required for this scope.",
            "clone": "Active mode-switch receipt required for this scope.",
            "reset": "Active mode-switch receipt required for this scope.",
            "rollback": "Active mode-switch receipt required for this scope.",
        },
        audit_status=AuditStatusView(
            latest_command_receipts={
                "mode switch": timeline[2],
                "rollback": timeline[3],
            },
            timeline=timeline,
        ),
        approval_status="requested",
        incident_state="open",
        last_stable_cycle="cycle-0001",
        rollback_target="cycle-0001",
        snapshot_refs=(
            "snapshots/cycles/cycle-0001/manifest.json",
            "snapshots/full/snapshot-incident-syntax-failure/manifest.json",
        ),
        branch_clone_refs=("mirrors/branches/branch-syntax-failure-cycle-0002.json",),
        reproducibility_manifest=make_manifest_summary(),
        full_log_bundle_refs=(
            "logs/full-log-bundle.jsonl",
            "logs/cycle-0002/full-log-bundle.jsonl",
        ),
        cycle_summaries=(
            CycleSummaryView(
                cycle_id="cycle-0001",
                gate_decision="accepted",
                score=0.98,
                test_result="passed",
                error_summary=None,
                full_log_bundle_ref="logs/cycle-0001/full-log-bundle.jsonl",
                log_sequence_range=(1, 9),
                has_incident=False,
            ),
            CycleSummaryView(
                cycle_id="cycle-0002",
                gate_decision="rejected",
                score=0.41,
                test_result="failed",
                error_summary="regression detected in smoke tests",
                full_log_bundle_ref="logs/cycle-0002/full-log-bundle.jsonl",
                log_sequence_range=(10, 19),
                has_incident=True,
            ),
        ),
    )


def make_cycle_detail() -> CycleDetailView:
    timeline = make_timeline()
    return CycleDetailView(
        run_id="run-stability-baseline",
        cycle_id="cycle-0002",
        current_mode="observation-only",
        lifecycle_state="active",
        observation_mode_state="incident open",
        active_mode_switch_receipt=ActiveModeSwitchReceiptView(
            receipt_id=uuid4(),
            target_mode="control-enabled",
            mode_context="mode-context-1",
        ),
        available_actions=CANONICAL_ACTIONS,
        deny_reason_by_action={},
        approval_status="approved",
        gate_decision="rejected",
        score=0.41,
        test_result="failed",
        error_summary="regression detected in smoke tests",
        diff_summary="Updated worker logic for cycle-0002.",
        model_identity="gpt-5.4",
        prompt_ref="prompts/cycle-0002.json",
        token_usage=TokenUsage(input_tokens=120, output_tokens=24, total_tokens=144),
        latency_ms=913,
        resources=ResourceUsage(cpu_percent=44.5, ram_mb=258, disk_mb=1026),
        snapshot_refs=(
            "snapshots/cycles/cycle-0002/manifest.json",
            "snapshots/full/snapshot-incident-syntax-failure/manifest.json",
        ),
        audit_event_refs=(
            "audit/cycle-0002/requested.json",
            "audit/cycle-0002/completed.json",
        ),
        full_log_bundle_ref="logs/cycle-0002/full-log-bundle.jsonl",
        audit_timeline=timeline,
        reversibility=ReversibilityView(
            incident_state="open",
            incident_id="incident-syntax-failure",
            incident_report_ref="incidents/incident-syntax-failure/report.json",
            snapshot_ref="snapshots/full/snapshot-incident-syntax-failure/manifest.json",
            branch_ref="mirrors/branches/branch-syntax-failure-cycle-0002.json",
            ordered_steps=("pause", "snapshot", "rollback", "report"),
            full_log_refs=("logs/cycle-0002/full-log-bundle.jsonl",),
            last_stable_cycle="cycle-0001",
            rollback_target="cycle-0001",
            recovery_outcome="rolled back to last accepted stable cycle cycle-0001",
            restore_manifest_ref="snapshots/cycles/cycle-0001/manifest.json",
        ),
        reproducibility_manifest=make_manifest_summary(),
    )


@dataclass(frozen=True, slots=True)
class SubmittedCommand:
    command: CommandEnvelope
    cycle_id: str | None
    actor_id: str
    actor_role: str
    occurred_at: str
    mode_context: str
    reason: str | None


@dataclass
class RecordingDashboardBackend:
    run_summary: RunSummaryView = field(default_factory=make_run_summary)
    cycle_detail: CycleDetailView = field(default_factory=make_cycle_detail)
    loaded_run_scopes: list[CommandScope] = field(default_factory=list)
    loaded_cycle_requests: list[tuple[CommandScope, str]] = field(default_factory=list)
    submitted_commands: list[SubmittedCommand] = field(default_factory=list)

    def load_run_summary(self, scope: CommandScope) -> RunSummaryView:
        self.loaded_run_scopes.append(scope)
        return self.run_summary

    def load_cycle_detail(self, scope: CommandScope, cycle_id: str) -> CycleDetailView:
        self.loaded_cycle_requests.append((scope, cycle_id))
        return self.cycle_detail

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
    ) -> dict[str, object]:
        self.submitted_commands.append(
            SubmittedCommand(
                command=command,
                cycle_id=cycle_id,
                actor_id=actor_id,
                actor_role=actor_role,
                occurred_at=occurred_at,
                mode_context=mode_context,
                reason=reason,
            )
        )
        return {"receipt_status": "requested", "action": command.action}


def test_dashboard_controller_projects_shared_query_models_into_all_required_views() -> None:
    scope = make_scope()
    backend = RecordingDashboardBackend()
    controller = DashboardController(backend)

    state = controller.load(scope=scope, selected_cycle_id="cycle-0002")

    assert backend.loaded_run_scopes == [scope]
    assert backend.loaded_cycle_requests == [(scope, "cycle-0002")]
    assert tuple(action.action for action in state.action_rail) == CANONICAL_ACTIONS
    assert state.sidebar.current_mode_badge == "observation-only"
    assert state.top_status.current_cycle_id == "cycle-0002"
    assert state.top_status.latest_decision == "rejected"
    assert state.top_status.incident_state == "open"
    assert state.top_status.last_stable_cycle == "cycle-0001"
    assert state.top_status.rollback_target == "cycle-0001"
    assert state.run_overview.summary_cards["Current mode"] == "observation-only"
    assert state.run_overview.summary_cards["Latest cycle decision"] == "rejected"
    assert state.run_overview.summary_cards["Stable-cycle count"] == "1/10"
    assert state.run_overview.failures_panel["open_incident_count"] == 1
    assert state.run_overview.failures_panel["recovery_page"] == "Incidents And Recovery"
    assert state.run_overview.cycle_rows[1].diff_summary == "Updated worker logic for cycle-0002."
    assert state.run_overview.cycle_rows[1].error_summary == "regression detected in smoke tests"
    assert state.cycle_detail.diff_summary == "Updated worker logic for cycle-0002."
    assert state.cycle_detail.rollback_target == "cycle-0001"
    assert state.cycle_detail.snapshot_refs[-1] == "snapshots/full/snapshot-incident-syntax-failure/manifest.json"
    assert state.approvals_audit.control_state == "observation-only"
    assert state.approvals_audit.pending_approval_count == 1
    assert state.approvals_audit.deny_reasons["pause"] == "Active mode-switch receipt required for this scope."
    assert state.approvals_audit.timeline[0].status == "requested"
    assert state.incidents_recovery.incident_state == "open"
    assert state.incidents_recovery.branch_refs == ("mirrors/branches/branch-syntax-failure-cycle-0002.json",)
    assert state.incidents_recovery.recovery_outcome == "rolled back to last accepted stable cycle cycle-0001"
    pause_control = next(control for control in state.action_rail if control.action == "pause")
    assert pause_control.enabled is False
    assert pause_control.deny_reason == "Active mode-switch receipt required for this scope."


def test_dashboard_controller_observe_refreshes_through_query_only() -> None:
    scope = make_scope()
    backend = RecordingDashboardBackend()
    controller = DashboardController(backend)

    result = controller.perform_action(
        action="observe",
        scope=scope,
        selected_cycle_id="cycle-0002",
        actor_id="observer-1",
        actor_role="operator",
        occurred_at="2026-04-26T10:10:00Z",
        mode_context="mode-context-1",
    )

    assert result.action == "observe"
    assert result.command is None
    assert result.refreshed_state is not None
    assert backend.loaded_run_scopes == [scope]
    assert backend.loaded_cycle_requests == [(scope, "cycle-0002")]
    assert backend.submitted_commands == []


@pytest.mark.parametrize(
    ("action", "selected_cycle_id", "target_mode", "clone_run_id", "expected_cycle_id", "expected_metadata"),
    [
        ("mode switch", None, "control-enabled", None, None, {}),
        ("pause", None, None, None, None, {}),
        ("resume", None, None, None, None, {}),
        ("branch", "cycle-0002", None, None, "cycle-0002", {}),
        ("clone", "cycle-0002", None, "run-clone-0002", "cycle-0002", {"clone_run_id": "run-clone-0002"}),
        ("reset", None, None, None, None, {}),
        ("rollback", "cycle-0002", None, None, "cycle-0002", {"target_cycle_id": "cycle-0002"}),
    ],
)
def test_dashboard_controller_dispatches_canonical_actions_with_backend_metadata(
    action: str,
    selected_cycle_id: str | None,
    target_mode: str | None,
    clone_run_id: str | None,
    expected_cycle_id: str | None,
    expected_metadata: dict[str, str],
) -> None:
    scope = make_scope()
    backend = RecordingDashboardBackend()
    controller = DashboardController(backend)

    result = controller.perform_action(
        action=action,
        scope=scope,
        selected_cycle_id=selected_cycle_id,
        target_mode=target_mode,
        clone_run_id=clone_run_id,
        actor_id="operator-1",
        actor_role="operator",
        occurred_at="2026-04-26T10:10:05Z",
        mode_context="mode-context-1",
        reason="dashboard interaction",
    )

    assert result.action == action
    assert result.command is not None
    assert result.receipt_payload == {"receipt_status": "requested", "action": action}
    submitted = backend.submitted_commands[-1]
    assert submitted.command.action == action
    assert submitted.command.scope == scope
    assert submitted.command.surface == "dashboard"
    assert submitted.command.target_mode == target_mode
    assert submitted.cycle_id == expected_cycle_id
    assert submitted.actor_id == "operator-1"
    assert submitted.actor_role == "operator"
    assert submitted.occurred_at == "2026-04-26T10:10:05Z"
    assert submitted.mode_context == "mode-context-1"
    assert submitted.reason == "dashboard interaction"
    for key, value in expected_metadata.items():
        assert submitted.command.surface_metadata[key] == value

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - exercised only when the dashboard extra is missing.
    st = None

from live_ai_terrarium.adapters.dashboard.streamlit_app import render_dashboard
from live_ai_terrarium.adapters.dashboard.views import DashboardBackend
from live_ai_terrarium.contracts.records import ResourceUsage, TokenUsage
from live_ai_terrarium.control.commands import CANONICAL_ACTIONS, CommandEnvelope, CommandScope
from live_ai_terrarium.query.read_models import (
    AuditStatusView,
    CommandReceiptView,
    CycleDetailView,
    CycleSummaryView,
    ReproducibilityManifestSummary,
    ReversibilityView,
    RunSummaryView,
)

PREVIEW_SCOPE = CommandScope(
    project_id="project-live-ai-terrarium",
    glass_box_id="gb-local-dev",
    experiment_id="exp-proof-loop",
    run_id="run-dashboard-preview",
)
DEFAULT_CYCLE_ID = "cycle-0010"


def build_preview_scope() -> CommandScope:
    return PREVIEW_SCOPE


def build_preview_manifest() -> ReproducibilityManifestSummary:
    return ReproducibilityManifestSummary(
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-018",
        seed=18,
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        limits={"max_cycles": 10, "max_cpu_percent": 90},
        release_tag="v1.0.1",
        image_name="glassbox:v1",
        runtime_profile_locator="infra/security/runtime-profile.yaml",
        runtime_profile_sha256=None,
        command_catalog_locator="infra/security/command-specs.yaml",
        command_catalog_sha256=None,
    )


def build_preview_timeline() -> tuple[CommandReceiptView, ...]:
    approval_id = UUID("11111111-1111-4111-8111-111111111111")
    receipt_id = UUID("22222222-2222-4222-8222-222222222222")
    return (
        CommandReceiptView(
            action="mode switch",
            status="requested",
            occurred_at="2026-04-26T10:00:00Z",
            actor_id="operator-local",
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
            actor_id="operator-local",
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
            actor_id="approver-local",
            actor_role="observer",
            cycle_id=None,
            approval_id=approval_id,
            receipt_id=receipt_id,
            target_mode="control-enabled",
            target_cycle_id=None,
            reason="Approved for rollback prep.",
        ),
        CommandReceiptView(
            action="rollback",
            status="completed",
            occurred_at="2026-04-26T10:05:15Z",
            actor_id="operator-local",
            actor_role="operator",
            cycle_id="cycle-0010",
            approval_id=None,
            receipt_id=None,
            target_mode=None,
            target_cycle_id="cycle-0009",
            reason=None,
        ),
    )


def build_preview_run_summary() -> RunSummaryView:
    timeline = build_preview_timeline()
    cycle_summaries = tuple(
        CycleSummaryView(
            cycle_id=f"cycle-{index:04d}",
            gate_decision="accepted" if index < 10 else "rejected",
            score=0.90 + (index / 100) if index < 10 else 0.41,
            test_result="passed" if index < 10 else "failed",
            error_summary=None if index < 10 else "regression detected in smoke tests",
            full_log_bundle_ref=f"logs/cycle-{index:04d}/full-log-bundle.jsonl",
            log_sequence_range=((index - 1) * 10 + 1, index * 10),
            has_incident=index == 10,
        )
        for index in range(1, 11)
    )
    return RunSummaryView(
        run_id=PREVIEW_SCOPE.run_id or "run-dashboard-preview",
        current_mode="observation-only",
        lifecycle_state="active",
        observation_mode_state="observation-only",
        active_mode_switch_receipt=None,
        available_actions=("observe", "mode switch"),
        deny_reason_by_action={
            action: "Active mode-switch receipt required for this scope."
            for action in CANONICAL_ACTIONS
            if action not in {"observe", "mode switch"}
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
        last_stable_cycle="cycle-0009",
        rollback_target="cycle-0009",
        snapshot_refs=(
            "snapshots/cycles/cycle-0009/manifest.json",
            "snapshots/full/snapshot-incident-syntax-failure/manifest.json",
        ),
        branch_clone_refs=("mirrors/branches/branch-syntax-failure-cycle-0010.json",),
        reproducibility_manifest=build_preview_manifest(),
        full_log_bundle_refs=(
            "logs/full-log-bundle.jsonl",
            "logs/cycle-0010/full-log-bundle.jsonl",
        ),
        cycle_summaries=cycle_summaries,
    )


def build_preview_cycle_detail(cycle_id: str) -> CycleDetailView:
    timeline = build_preview_timeline()
    cycle_number = int(cycle_id.rsplit("-", 1)[-1])
    is_incident_cycle = cycle_id == DEFAULT_CYCLE_ID
    return CycleDetailView(
        run_id=PREVIEW_SCOPE.run_id or "run-dashboard-preview",
        cycle_id=cycle_id,
        current_mode="observation-only",
        lifecycle_state="active",
        observation_mode_state="incident open" if is_incident_cycle else "observation-only",
        active_mode_switch_receipt=None,
        available_actions=("observe", "mode switch"),
        deny_reason_by_action={
            action: "Active mode-switch receipt required for this scope."
            for action in CANONICAL_ACTIONS
            if action not in {"observe", "mode switch"}
        },
        approval_status="requested" if is_incident_cycle else "not-requested",
        gate_decision="rejected" if is_incident_cycle else "accepted",
        score=0.41 if is_incident_cycle else 0.90 + (cycle_number / 100),
        test_result="failed" if is_incident_cycle else "passed",
        error_summary="regression detected in smoke tests" if is_incident_cycle else None,
        diff_summary=f"Updated worker logic for {cycle_id}.",
        model_identity="gpt-5.4",
        prompt_ref=f"prompts/{cycle_id}.json",
        token_usage=TokenUsage(
            input_tokens=120 + cycle_number,
            output_tokens=20 + cycle_number,
            total_tokens=160 + (2 * cycle_number),
        ),
        latency_ms=900 + cycle_number,
        resources=ResourceUsage(
            cpu_percent=42.0 + cycle_number,
            ram_mb=256 + cycle_number,
            disk_mb=1024 + cycle_number,
        ),
        snapshot_refs=(
            f"snapshots/cycles/{cycle_id}/manifest.json",
            "snapshots/full/snapshot-incident-syntax-failure/manifest.json",
        ),
        audit_event_refs=(
            f"audit/{cycle_id}/requested.json",
            f"audit/{cycle_id}/completed.json",
        ),
        full_log_bundle_ref=f"logs/{cycle_id}/full-log-bundle.jsonl",
        audit_timeline=timeline,
        reversibility=ReversibilityView(
            incident_state="open" if is_incident_cycle else "clear",
            incident_id="incident-syntax-failure" if is_incident_cycle else None,
            incident_report_ref="incidents/incident-syntax-failure/report.json" if is_incident_cycle else None,
            snapshot_ref="snapshots/full/snapshot-incident-syntax-failure/manifest.json" if is_incident_cycle else None,
            branch_ref="mirrors/branches/branch-syntax-failure-cycle-0010.json" if is_incident_cycle else None,
            ordered_steps=("pause", "snapshot", "rollback", "report") if is_incident_cycle else (),
            full_log_refs=(f"logs/{cycle_id}/full-log-bundle.jsonl",),
            last_stable_cycle="cycle-0009",
            rollback_target="cycle-0009",
            recovery_outcome="rolled back to last accepted stable cycle cycle-0009" if is_incident_cycle else None,
            restore_manifest_ref="snapshots/cycles/cycle-0009/manifest.json" if is_incident_cycle else None,
        ),
        reproducibility_manifest=build_preview_manifest(),
    )


@dataclass
class PreviewDashboardBackend(DashboardBackend):
    run_summary: RunSummaryView

    def load_run_summary(self, scope: CommandScope) -> RunSummaryView:
        if scope != PREVIEW_SCOPE:
            raise ValueError(f"Unsupported preview scope: {scope}")
        return self.run_summary

    def load_cycle_detail(self, scope: CommandScope, cycle_id: str) -> CycleDetailView:
        if scope != PREVIEW_SCOPE:
            raise ValueError(f"Unsupported preview scope: {scope}")
        return build_preview_cycle_detail(cycle_id)

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
        del cycle_id, actor_id, actor_role, occurred_at, mode_context, reason
        return {
            "command": command.model_dump(mode="json"),
            "dispatch_result": {
                "status": "denied",
                "deny_reason": f"{command.action} requires an active mode-switch receipt for the same scope and mode context",
            },
        }


def build_preview_backend() -> PreviewDashboardBackend:
    return PreviewDashboardBackend(run_summary=build_preview_run_summary())


def main() -> None:
    if st is None:
        raise ModuleNotFoundError(
            "streamlit is not installed; install the dashboard extra to launch the dashboard preview"
        )

    preview_cycles = [f"cycle-{index:04d}" for index in range(1, 11)]
    selected_cycle_id = cast(
        str,
        st.sidebar.selectbox(
            "Cycle",
            preview_cycles,
            index=preview_cycles.index(DEFAULT_CYCLE_ID),
        ),
    )
    render_dashboard(
        build_preview_backend(),
        scope=build_preview_scope(),
        selected_cycle_id=selected_cycle_id,
        streamlit_module=st,
        configure_page=False,
    )


if __name__ == "__main__":
    main()

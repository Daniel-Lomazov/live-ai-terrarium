from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from live_ai_terrarium.control.commands import CommandScope

from .views import DashboardBackend, DashboardController, DashboardState

try:
    import streamlit as _streamlit
except ModuleNotFoundError:  # pragma: no cover - exercised only when dashboard extra is missing.
    _streamlit = None


class StreamlitLike(Protocol):
    def set_page_config(self, **kwargs: object) -> None: ...

    def title(self, body: str) -> None: ...

    def subheader(self, body: str) -> None: ...

    def caption(self, body: str) -> None: ...

    def write(self, body: object) -> None: ...

    def json(self, body: object) -> None: ...

    def code(self, body: str, *, language: str | None = None) -> None: ...

    def columns(self, spec: int) -> list[Any]: ...


def render_dashboard(
    backend: DashboardBackend,
    *,
    scope: CommandScope,
    selected_cycle_id: str | None = None,
    streamlit_module: StreamlitLike | None = None,
    configure_page: bool = True,
) -> DashboardState:
    st = _require_streamlit(streamlit_module)
    controller = DashboardController(backend)
    state = controller.load(scope=scope, selected_cycle_id=selected_cycle_id)

    if configure_page:
        st.set_page_config(page_title="Live AI Terrarium", layout="wide")
    st.title("Live AI Terrarium")
    st.caption("Read-first dashboard over the shared query and command backend.")
    _render_sidebar(st, state)
    _render_status_strip(st, state)
    _render_action_rail(st, state)
    _render_run_overview(st, state)
    if state.cycle_detail is not None:
        _render_cycle_detail(st, state)
    _render_approvals_audit(st, state)
    _render_incidents_recovery(st, state)
    return state


def _require_streamlit(streamlit_module: StreamlitLike | None) -> StreamlitLike:
    if streamlit_module is not None:
        return streamlit_module
    if _streamlit is None:
        raise ModuleNotFoundError(
            "streamlit is not installed; install the dashboard extra to render the Streamlit adapter"
        )
    return _streamlit


def _render_sidebar(st: StreamlitLike, state: DashboardState) -> None:
    st.subheader("Scope")
    st.json(
        {
            "project_id": state.scope.project_id,
            "glass_box_id": state.scope.glass_box_id,
            "experiment_id": state.scope.experiment_id,
            "run_id": state.scope.run_id,
            "current_mode": state.sidebar.current_mode_badge,
            "active_receipt": state.sidebar.active_receipt_badge,
        }
    )


def _render_status_strip(st: StreamlitLike, state: DashboardState) -> None:
    st.subheader("Status")
    st.write(
        {
            "current_cycle": state.top_status.current_cycle_id,
            "stable_cycles": state.top_status.stable_cycle_count,
            "latest_decision": state.top_status.latest_decision,
            "incident_state": state.top_status.incident_state,
            "last_stable_cycle": state.top_status.last_stable_cycle,
            "rollback_target": state.top_status.rollback_target,
        }
    )


def _render_action_rail(st: StreamlitLike, state: DashboardState) -> None:
    st.subheader("Action Rail")
    st.write(
        [
            {
                "action": control.action,
                "enabled": control.enabled,
                "deny_reason": control.deny_reason,
            }
            for control in state.action_rail
        ]
    )


def _render_run_overview(st: StreamlitLike, state: DashboardState) -> None:
    st.subheader("Run Overview")
    st.json(state.run_overview.summary_cards)
    st.write(
        [
            {
                "cycle_id": row.cycle_id,
                "decision": row.decision,
                "score": row.score,
                "test_result": row.test_result,
                "error_summary": row.error_summary,
                "diff_summary": row.diff_summary,
                "model_identity": row.model_identity,
                "prompt_ref": row.prompt_ref,
                "total_tokens": row.total_tokens,
                "latency_ms": row.latency_ms,
                "cpu_percent": row.cpu_percent,
                "ram_mb": row.ram_mb,
                "disk_mb": row.disk_mb,
                "full_log_bundle_ref": row.full_log_bundle_ref,
                "has_incident": row.has_incident,
            }
            for row in state.run_overview.cycle_rows
        ]
    )
    st.json(state.run_overview.failures_panel)


def _render_cycle_detail(st: StreamlitLike, state: DashboardState) -> None:
    if state.cycle_detail is None:
        return
    st.subheader("Cycle Detail")
    st.code(state.cycle_detail.diff_summary or "No diff summary available.", language="diff")
    st.json(
        {
            "cycle_id": state.cycle_detail.cycle_id,
            "decision": state.cycle_detail.decision,
            "score": state.cycle_detail.score,
            "test_result": state.cycle_detail.test_result,
            "error_summary": state.cycle_detail.error_summary,
            "model_identity": state.cycle_detail.model_identity,
            "prompt_ref": state.cycle_detail.prompt_ref,
            "total_tokens": state.cycle_detail.total_tokens,
            "latency_ms": state.cycle_detail.latency_ms,
            "cpu_percent": state.cycle_detail.cpu_percent,
            "ram_mb": state.cycle_detail.ram_mb,
            "disk_mb": state.cycle_detail.disk_mb,
            "snapshot_refs": state.cycle_detail.snapshot_refs,
            "rollback_target": state.cycle_detail.rollback_target,
            "branch_ref": state.cycle_detail.branch_ref,
            "recovery_outcome": state.cycle_detail.recovery_outcome,
        }
    )
    st.write([asdict(receipt) for receipt in state.cycle_detail.audit_timeline])


def _render_approvals_audit(st: StreamlitLike, state: DashboardState) -> None:
    st.subheader("Approvals And Audit")
    st.json(
        {
            "control_state": state.approvals_audit.control_state,
            "pending_approval_count": state.approvals_audit.pending_approval_count,
            "active_mode_switch_receipt": state.approvals_audit.active_mode_switch_receipt,
            "deny_reasons": state.approvals_audit.deny_reasons,
        }
    )
    st.write([asdict(receipt) for receipt in state.approvals_audit.timeline])


def _render_incidents_recovery(st: StreamlitLike, state: DashboardState) -> None:
    st.subheader("Incidents And Recovery")
    st.json(
        {
            "incident_state": state.incidents_recovery.incident_state,
            "incident_id": state.incidents_recovery.incident_id,
            "incident_report_ref": state.incidents_recovery.incident_report_ref,
            "snapshot_refs": state.incidents_recovery.snapshot_refs,
            "branch_refs": state.incidents_recovery.branch_refs,
            "last_stable_cycle": state.incidents_recovery.last_stable_cycle,
            "rollback_target": state.incidents_recovery.rollback_target,
            "reset_anchor": state.incidents_recovery.reset_anchor,
            "recovery_outcome": state.incidents_recovery.recovery_outcome,
        }
    )
    st.write([asdict(receipt) for receipt in state.incidents_recovery.latest_recovery_receipts])


__all__ = ["render_dashboard"]
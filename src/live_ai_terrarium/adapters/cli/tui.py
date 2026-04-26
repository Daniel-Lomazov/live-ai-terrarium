from __future__ import annotations

from typing import Literal

from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table

from live_ai_terrarium.control.commands import CANONICAL_ACTIONS, CommandScope
from live_ai_terrarium.query.read_models import CommandReceiptView, CycleDetailView, RunSummaryView

from .gb import CommandReceipt, GbCli

TuiView = Literal["summary", "cycle", "audit", "recovery"]


class RichTuiAdapter:
    def __init__(
        self,
        *,
        query_backend,
        control_backend,
        actor_id: str = "operator-local",
        actor_role: str = "operator",
        mode_context: str = "terminal-session",
    ) -> None:
        self._cli = GbCli(
            query_backend=query_backend,
            control_backend=control_backend,
            surface="tui",
            actor_id=actor_id,
            actor_role=actor_role,
            mode_context=mode_context,
        )

    def observe(self, *, scope: CommandScope, cycle_id: str | None = None):
        return self._cli.observe(scope=scope, cycle_id=cycle_id)

    def submit_action(self, *, action, scope: CommandScope, **kwargs) -> CommandReceipt:
        return self._cli.submit_action(action=action, scope=scope, **kwargs)

    def render(
        self,
        *,
        view: TuiView,
        scope: CommandScope,
        cycle_id: str | None = None,
        last_receipt: CommandReceipt | CommandReceiptView | None = None,
    ) -> Layout:
        run_summary = self.observe(scope=scope)
        cycle_detail = None
        if view == "cycle":
            if cycle_id is None:
                raise ValueError("cycle view requires cycle_id")
            cycle_detail = self.observe(scope=scope, cycle_id=cycle_id)
        return self._build_layout(
            scope=scope,
            run_summary=run_summary,
            cycle_detail=cycle_detail,
            view=view,
            last_receipt=last_receipt,
        )

    def _build_layout(
        self,
        *,
        scope: CommandScope,
        run_summary: RunSummaryView,
        cycle_detail: CycleDetailView | None,
        view: TuiView,
        last_receipt: CommandReceipt | CommandReceiptView | None,
    ) -> Layout:
        layout = Layout(name="root")
        layout.split_column(
            Layout(self._header(scope, run_summary), name="header", size=5),
            Layout(name="body"),
            Layout(self._footer(run_summary, last_receipt), name="footer", size=5),
        )
        layout["body"].split_row(
            Layout(self._left_pane(run_summary), name="left", size=38),
            Layout(self._center_pane(run_summary, cycle_detail, view), name="center"),
            Layout(self._right_pane(run_summary), name="right", size=42),
        )
        return layout

    def _header(self, scope: CommandScope, run_summary: RunSummaryView) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(ratio=2)
        table.add_column(ratio=2)
        table.add_column(ratio=1)
        table.add_row(
            f"Scope: {scope.project_id}/{scope.glass_box_id}/{scope.run_id or 'unscoped'}",
            f"Mode: {run_summary.current_mode} | State: {run_summary.lifecycle_state}",
            f"Incident: {run_summary.incident_state}",
        )
        table.add_row(
            f"Active receipt: {self._active_receipt_text(run_summary)}",
            f"Last stable: {run_summary.last_stable_cycle or 'none'}",
            f"Rollback: {run_summary.rollback_target or 'none'}",
        )
        return Panel(table, title="Header")

    def _left_pane(self, run_summary: RunSummaryView) -> Panel:
        cycles = Table(title="Cycles", expand=True)
        cycles.add_column("Cycle")
        cycles.add_column("Decision")
        cycles.add_column("Score")
        cycles.add_column("Tests")
        for cycle in run_summary.cycle_summaries:
            cycles.add_row(cycle.cycle_id, cycle.gate_decision, f"{cycle.score:.2f}", cycle.test_result)
        return Panel(cycles, title=f"Run {run_summary.run_id}")

    def _center_pane(
        self,
        run_summary: RunSummaryView,
        cycle_detail: CycleDetailView | None,
        view: TuiView,
    ) -> Panel:
        if view == "summary":
            accepted_cycles = sum(1 for cycle in run_summary.cycle_summaries if cycle.gate_decision == "accepted")
            summary = Table.grid(expand=True)
            summary.add_column()
            summary.add_column()
            summary.add_row("Stable progress", f"{accepted_cycles}/{len(run_summary.cycle_summaries)} accepted cycles")
            summary.add_row("Approval status", run_summary.approval_status)
            summary.add_row("Observation state", run_summary.observation_mode_state)
            summary.add_row("Task", run_summary.reproducibility_manifest.task_identity)
            summary.add_row("Logs", ", ".join(run_summary.full_log_bundle_refs) or "none")
            return Panel(summary, title="Summary")
        if view == "cycle":
            if cycle_detail is None:
                raise ValueError("cycle view requires cycle detail")
            evidence = Table.grid(expand=True)
            evidence.add_column()
            evidence.add_row(f"Task: {run_summary.reproducibility_manifest.task_identity}")
            evidence.add_row(f"Decision: {cycle_detail.gate_decision}")
            evidence.add_row(f"Score: {cycle_detail.score:.2f}")
            evidence.add_row(f"Tests: {cycle_detail.test_result}")
            evidence.add_row(f"Errors: {cycle_detail.error_summary or 'none'}")
            evidence.add_row(f"Incident: {cycle_detail.reversibility.incident_id or cycle_detail.reversibility.incident_state}")
            evidence.add_row(cycle_detail.diff_summary or "none")
            evidence.add_row(f"Model: {cycle_detail.model_identity}")
            evidence.add_row(f"Prompt: {cycle_detail.prompt_ref}")
            evidence.add_row(f"Tokens: {cycle_detail.token_usage.total_tokens}")
            evidence.add_row(f"Latency: {cycle_detail.latency_ms} ms")
            evidence.add_row(f"CPU: {cycle_detail.resources.cpu_percent}%")
            evidence.add_row(f"RAM: {cycle_detail.resources.ram_mb} MB")
            evidence.add_row(f"Disk: {cycle_detail.resources.disk_mb} MB")
            return Panel(Group(evidence, Panel(cycle_detail.diff_summary or "none", title="Diff")), title=f"Cycle {cycle_detail.cycle_id}")
        if view == "audit":
            timeline = Table(title="Audit Timeline", expand=True)
            timeline.add_column("Action")
            timeline.add_column("Status")
            timeline.add_column("Time")
            timeline.add_column("Target")
            for item in run_summary.audit_status.timeline:
                timeline.add_row(item.action, item.status, item.occurred_at, item.target_cycle_id or item.target_mode or "")
            return Panel(timeline, title="Audit")
        recovery = Table.grid(expand=True)
        recovery.add_column(style="bold")
        recovery.add_column()
        recovery.add_row("Incident", run_summary.incident_state)
        recovery.add_row("Last stable", run_summary.last_stable_cycle or "none")
        recovery.add_row("Rollback target", run_summary.rollback_target or "none")
        recovery.add_row("Snapshots", ", ".join(run_summary.snapshot_refs) or "none")
        recovery.add_row("Branch refs", ", ".join(run_summary.branch_clone_refs) or "none")
        recovery.add_row("Logs", ", ".join(run_summary.full_log_bundle_refs) or "none")
        return Panel(recovery, title="Recovery")

    def _right_pane(self, run_summary: RunSummaryView) -> Panel:
        actions = Table(title="Actions", expand=True)
        actions.add_column("Action")
        actions.add_column("State")
        actions.add_column("Reason")
        available = set(run_summary.available_actions)
        for action in CANONICAL_ACTIONS:
            actions.add_row(
                action,
                "available" if action in available else "blocked",
                run_summary.deny_reason_by_action.get(action, ""),
            )
        approval = Table.grid(expand=True)
        approval.add_column(style="bold")
        approval.add_column()
        approval.add_row("Approval", run_summary.approval_status)
        approval.add_row("Observation state", run_summary.observation_mode_state)
        approval.add_row("Active receipt", self._active_receipt_text(run_summary))
        return Panel(Group(approval, actions), title="Controls")

    def _footer(
        self,
        run_summary: RunSummaryView,
        last_receipt: CommandReceipt | CommandReceiptView | None,
    ) -> Panel:
        receipt = last_receipt
        if receipt is None and run_summary.audit_status.timeline:
            receipt = run_summary.audit_status.timeline[-1]
        footer = Table.grid(expand=True)
        footer.add_column(style="bold")
        footer.add_column()
        footer.add_row("Refresh", "shared query service")
        if receipt is None:
            footer.add_row("Latest receipt", "none")
        elif isinstance(receipt, CommandReceiptView):
            footer.add_row("Latest receipt", f"{receipt.action} {receipt.status} @ {receipt.occurred_at}")
        else:
            footer.add_row("Latest receipt", f"{receipt.action} {receipt.status}")
        return Panel(footer, title="Footer")

    def _active_receipt_text(self, run_summary: RunSummaryView) -> str:
        if run_summary.active_mode_switch_receipt is None:
            return "none"
        receipt = run_summary.active_mode_switch_receipt
        return f"{receipt.receipt_id} ({receipt.target_mode})"


__all__ = ["RichTuiAdapter", "TuiView"]
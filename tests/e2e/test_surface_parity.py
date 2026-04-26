from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from live_ai_terrarium.adapters.api.app import create_app as create_api_app
from live_ai_terrarium.adapters.cli.gb import CommandReceipt, SubmissionContext, create_app as create_cli_app
from live_ai_terrarium.adapters.cli.tui import RichTuiAdapter
from live_ai_terrarium.adapters.dashboard.views import DashboardController
from live_ai_terrarium.contracts.records import ResourceUsage, TokenUsage
from live_ai_terrarium.control.commands import CANONICAL_ACTIONS, CommandEnvelope, CommandScope, ModeSwitchReceipt
from live_ai_terrarium.control.dispatcher import CommandDispatcher, DispatchContext, DispatchResult
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
        run_id="run-surface-parity",
    )


def make_manifest_summary() -> ReproducibilityManifestSummary:
    return ReproducibilityManifestSummary(
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-017",
        seed=17,
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        limits={"max_cycles": 10, "max_cpu_percent": 90},
        release_tag="milestone/v1-wave8",
        image_name="glassbox:v1",
        runtime_profile_locator=None,
        runtime_profile_sha256="c" * 64,
        command_catalog_locator=None,
        command_catalog_sha256="d" * 64,
    )


def make_timeline(*, unlocked: bool) -> tuple[CommandReceiptView, ...]:
    if not unlocked:
        return ()
    receipt_id = UUID("11111111-1111-4111-8111-111111111111")
    return (
        CommandReceiptView(
            action="mode switch",
            status="completed",
            occurred_at="2026-04-26T10:00:00Z",
            actor_id="operator-local",
            actor_role="operator",
            cycle_id=None,
            approval_id=None,
            receipt_id=receipt_id,
            target_mode="control-enabled",
            target_cycle_id=None,
            reason=None,
        ),
    )


def make_run_summary(*, unlocked: bool) -> RunSummaryView:
    timeline = make_timeline(unlocked=unlocked)
    return RunSummaryView(
        run_id="run-surface-parity",
        current_mode="control-enabled" if unlocked else "observation-only",
        lifecycle_state="active",
        observation_mode_state="mode-switch active" if unlocked else "observation-only",
        active_mode_switch_receipt=(
            ActiveModeSwitchReceiptView(
                receipt_id=timeline[0].receipt_id,
                target_mode="control-enabled",
                mode_context="mode-context-1",
            )
            if unlocked
            else None
        ),
        available_actions=CANONICAL_ACTIONS if unlocked else ("observe", "mode switch"),
        deny_reason_by_action=(
            {}
            if unlocked
            else {
                action: "Active mode-switch receipt required for this scope."
                for action in ("pause", "resume", "branch", "clone", "reset", "rollback")
            }
        ),
        audit_status=AuditStatusView(
            latest_command_receipts={} if not timeline else {"mode switch": timeline[-1]},
            timeline=timeline,
        ),
        approval_status="approved" if unlocked else "not-requested",
        incident_state="clear",
        last_stable_cycle="cycle-0001",
        rollback_target="cycle-0001",
        snapshot_refs=("snapshots/cycles/cycle-0001/manifest.json",),
        branch_clone_refs=("mirrors/branches/branch-cycle-0002.json",) if unlocked else (),
        reproducibility_manifest=make_manifest_summary(),
        full_log_bundle_refs=("logs/full-log-bundle.jsonl",),
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


def make_cycle_detail(*, unlocked: bool) -> CycleDetailView:
    timeline = make_timeline(unlocked=unlocked)
    return CycleDetailView(
        run_id="run-surface-parity",
        cycle_id="cycle-0002",
        current_mode="control-enabled" if unlocked else "observation-only",
        lifecycle_state="active",
        observation_mode_state="mode-switch active" if unlocked else "observation-only",
        active_mode_switch_receipt=(
            ActiveModeSwitchReceiptView(
                receipt_id=timeline[0].receipt_id,
                target_mode="control-enabled",
                mode_context="mode-context-1",
            )
            if unlocked
            else None
        ),
        available_actions=CANONICAL_ACTIONS if unlocked else ("observe", "mode switch"),
        deny_reason_by_action=(
            {}
            if unlocked
            else {
                action: "Active mode-switch receipt required for this scope."
                for action in ("pause", "resume", "branch", "clone", "reset", "rollback")
            }
        ),
        approval_status="approved" if unlocked else "not-requested",
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
        audit_event_refs=("audit/cycle-0002/requested.json", "audit/cycle-0002/completed.json"),
        full_log_bundle_ref="logs/cycle-0002/full-log-bundle.jsonl",
        audit_timeline=timeline,
        reversibility=ReversibilityView(
            incident_state="clear",
            incident_id=None,
            incident_report_ref=None,
            snapshot_ref="snapshots/full/snapshot-incident-syntax-failure/manifest.json",
            branch_ref="mirrors/branches/branch-cycle-0002.json" if unlocked else None,
            ordered_steps=("pause", "snapshot", "rollback", "report") if unlocked else (),
            full_log_refs=("logs/cycle-0002/full-log-bundle.jsonl",),
            last_stable_cycle="cycle-0001",
            rollback_target="cycle-0001",
            recovery_outcome="rollback completed" if unlocked else None,
            restore_manifest_ref="snapshots/cycles/cycle-0001/manifest.json" if unlocked else None,
        ),
        reproducibility_manifest=make_manifest_summary(),
    )


def make_command_payload(*, idempotency_key: str) -> dict[str, object]:
    return {
        "scope": make_scope().model_dump(mode="json"),
        "actor_id": "operator-local",
        "actor_role": "operator",
        "occurred_at": "2026-04-26T10:00:00Z",
        "mode_context": "mode-context-1",
        "idempotency_key": idempotency_key,
        "surface_metadata": {"source": "surface-parity"},
    }


def command_options(scope: CommandScope) -> list[str]:
    return [
        "--project-id",
        scope.project_id,
        "--glass-box-id",
        scope.glass_box_id,
        "--experiment-id",
        scope.experiment_id or "",
        "--run-id",
        scope.run_id or "",
        "--mode-context",
        "mode-context-1",
    ]


@dataclass(frozen=True, slots=True)
class SubmittedCommand:
    command: CommandEnvelope
    cycle_id: str | None
    mode_context: str
    reason: str | None


class SharedSurfaceBackend:
    def __init__(self, *, unlocked: bool) -> None:
        self.run_summary = make_run_summary(unlocked=unlocked)
        self.cycle_detail = make_cycle_detail(unlocked=unlocked)
        self.current_mode = self.run_summary.current_mode
        self.active_receipt = None
        if unlocked:
            self.active_receipt = ModeSwitchReceipt(
                scope=make_scope(),
                mode_context="mode-context-1",
                target_mode="control-enabled",
                status="active",
            )
        self.submissions: list[SubmittedCommand] = []

    def observe_run(self, scope: CommandScope) -> RunSummaryView:
        assert scope == make_scope()
        return self.run_summary

    def observe_cycle(self, scope: CommandScope, *, cycle_id: str) -> CycleDetailView:
        assert scope == make_scope()
        assert cycle_id == "cycle-0002"
        return self.cycle_detail

    def read_run(self, scope: CommandScope) -> RunSummaryView:
        return self.observe_run(scope)

    def read_cycle(self, scope: CommandScope, cycle_id: str) -> CycleDetailView:
        return self.observe_cycle(scope, cycle_id=cycle_id)

    def load_run_summary(self, scope: CommandScope) -> RunSummaryView:
        return self.observe_run(scope)

    def load_cycle_detail(self, scope: CommandScope, cycle_id: str) -> CycleDetailView:
        return self.observe_cycle(scope, cycle_id=cycle_id)

    def dispatch_command(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        cycle_id: str | None = None,
        reason: str | None = None,
        approval_actor_id: str | None = None,
        approval_actor_role: str | None = None,
        approval_occurred_at: str | None = None,
        approval_reason: str | None = None,
    ) -> dict[str, object]:
        del actor_id, actor_role, occurred_at, approval_actor_id, approval_actor_role, approval_occurred_at, approval_reason
        result = self._dispatch(command, mode_context=mode_context, cycle_id=cycle_id, reason=reason)
        return {
            "command": command.model_dump(mode="json"),
            "dispatch_result": result.model_dump(mode="json"),
        }

    def submit(self, command: CommandEnvelope, submission: SubmissionContext) -> CommandReceipt:
        result = self._dispatch(
            command,
            mode_context=submission.mode_context,
            cycle_id=submission.cycle_id,
            reason=submission.reason,
        )
        return CommandReceipt(
            action=command.action,
            status=result.status,
            receipt_id=result.receipt_id,
            deny_reason=result.deny_reason,
            current_mode=self.current_mode,
            lifecycle_state="paused" if command.action == "pause" and result.status == "allowed" else "active",
            details=result.handler_result,
        )

    def _dispatch(
        self,
        command: CommandEnvelope,
        *,
        mode_context: str,
        cycle_id: str | None,
        reason: str | None,
    ) -> DispatchResult:
        self.submissions.append(
            SubmittedCommand(
                command=command,
                cycle_id=cycle_id,
                mode_context=mode_context,
                reason=reason,
            )
        )

        def handler(allowed_command: CommandEnvelope) -> dict[str, object]:
            if allowed_command.action == "mode switch":
                self.current_mode = allowed_command.target_mode or self.current_mode
                self.active_receipt = ModeSwitchReceipt(
                    scope=allowed_command.scope,
                    mode_context=mode_context,
                    target_mode=self.current_mode,
                    status="active",
                )
            return {
                "surface": allowed_command.surface,
                "clone_run_id": allowed_command.surface_metadata.get("clone_run_id"),
                "target_cycle_id": allowed_command.surface_metadata.get("target_cycle_id"),
                "branch_name": allowed_command.surface_metadata.get("branch_name"),
            }

        return CommandDispatcher(handler=handler).dispatch(
            command,
            DispatchContext(
                current_mode=self.current_mode,
                mode_context=mode_context,
                mode_switch_receipt=self.active_receipt,
            ),
        )


def semantic_signature(submission: SubmittedCommand) -> tuple[object, ...]:
    return (
        submission.command.action,
        submission.command.scope.scope_key(),
        submission.command.target_mode,
        submission.command.surface_metadata.get("clone_run_id"),
        submission.command.surface_metadata.get("target_cycle_id"),
        submission.mode_context,
        submission.reason,
    )


def invoke_api_action(action: str, *, unlocked: bool) -> tuple[SharedSurfaceBackend, dict[str, object]]:
    backend = SharedSurfaceBackend(unlocked=unlocked)
    client = TestClient(create_api_app(command_backend=backend, query_backend=backend))
    payload = make_command_payload(idempotency_key=f"api-{action}")
    if action == "mode switch":
        payload["target_mode"] = "control-enabled"
    if action == "branch":
        payload["surface_metadata"]["branch_name"] = "branch-cycle-0002"
    if action == "clone":
        payload["surface_metadata"]["clone_run_id"] = "run-clone-0002"
    if action == "rollback":
        payload["surface_metadata"]["target_cycle_id"] = "cycle-0001"
    if action == "reset":
        payload["reason"] = "operator reset"
    response = client.post(f"/api/commands/{'mode-switch' if action == 'mode switch' else action}", json=payload)
    return backend, {"status_code": response.status_code, "payload": response.json()}


def invoke_cli_action(action: str, *, unlocked: bool) -> tuple[SharedSurfaceBackend, dict[str, object]]:
    backend = SharedSurfaceBackend(unlocked=unlocked)
    runner = CliRunner()
    cli_app = create_cli_app(query_backend=backend, control_backend=backend)
    scope = make_scope()
    argv = {
        "mode switch": ["mode-switch", *command_options(scope), "--target-mode", "control-enabled"],
        "pause": ["pause", *command_options(scope)],
        "resume": ["resume", *command_options(scope)],
        "branch": ["branch", *command_options(scope), "--branch-name", "branch-cycle-0002"],
        "clone": ["clone", *command_options(scope), "--clone-run-id", "run-clone-0002"],
        "reset": ["reset", *command_options(scope), "--reason", "operator reset"],
        "rollback": ["rollback", *command_options(scope), "--target-cycle-id", "cycle-0001"],
    }[action]
    result = runner.invoke(cli_app, argv)
    return backend, {"exit_code": result.exit_code, "payload": json.loads(result.stdout)}


def invoke_tui_action(action: str, *, unlocked: bool) -> tuple[SharedSurfaceBackend, CommandReceipt]:
    backend = SharedSurfaceBackend(unlocked=unlocked)
    tui = RichTuiAdapter(query_backend=backend, control_backend=backend, mode_context="mode-context-1")
    kwargs = {
        "mode switch": {"target_mode": "control-enabled"},
        "pause": {},
        "resume": {},
        "branch": {"branch_name": "branch-cycle-0002"},
        "clone": {"clone_run_id": "run-clone-0002"},
        "reset": {"reason": "operator reset"},
        "rollback": {"target_cycle_id": "cycle-0001"},
    }[action]
    receipt = tui.submit_action(action=action, scope=make_scope(), **kwargs)
    return backend, receipt


def invoke_dashboard_action(action: str, *, unlocked: bool) -> tuple[SharedSurfaceBackend, dict[str, object] | None]:
    backend = SharedSurfaceBackend(unlocked=unlocked)
    controller = DashboardController(backend)
    result = controller.perform_action(
        action=action,
        scope=make_scope(),
        selected_cycle_id=(
            "cycle-0001"
            if action == "rollback"
            else "cycle-0002"
            if action in {"branch", "clone"}
            else None
        ),
        target_mode="control-enabled" if action == "mode switch" else None,
        clone_run_id="run-clone-0002" if action == "clone" else None,
        actor_id="operator-local",
        actor_role="operator",
        occurred_at="2026-04-26T10:00:00Z",
        mode_context="mode-context-1",
        reason="operator reset" if action == "reset" else None,
    )
    return backend, result.receipt_payload


def test_surface_observe_paths_share_the_same_read_model_truth() -> None:
    locked_backend = SharedSurfaceBackend(unlocked=False)
    scope = make_scope()
    api_client = TestClient(create_api_app(command_backend=locked_backend, query_backend=locked_backend))
    cli_runner = CliRunner()
    cli_app = create_cli_app(query_backend=locked_backend, control_backend=locked_backend)
    tui = RichTuiAdapter(query_backend=locked_backend, control_backend=locked_backend, mode_context="mode-context-1")
    dashboard_state = DashboardController(locked_backend).load(scope=scope, selected_cycle_id="cycle-0002")

    api_run = api_client.get(
        "/api/observe/runs/project-live-ai-terrarium/gb-local-dev/exp-proof-loop/run-surface-parity"
    )
    api_cycle = api_client.get(
        "/api/observe/runs/project-live-ai-terrarium/gb-local-dev/exp-proof-loop/run-surface-parity/cycles/cycle-0002"
    )
    cli_run = cli_runner.invoke(cli_app, ["observe", *command_options(scope)])
    cli_cycle = cli_runner.invoke(cli_app, ["observe", *command_options(scope), "--cycle-id", "cycle-0002"])
    tui_run = tui.observe(scope=scope)
    tui_cycle = tui.observe(scope=scope, cycle_id="cycle-0002")

    assert api_run.status_code == 200
    assert api_cycle.status_code == 200
    assert cli_run.exit_code == 0
    assert cli_cycle.exit_code == 0
    assert api_run.json() == jsonable_encoder(locked_backend.run_summary)
    assert api_cycle.json() == jsonable_encoder(locked_backend.cycle_detail)
    assert json.loads(cli_run.stdout) == jsonable_encoder(locked_backend.run_summary)
    assert json.loads(cli_cycle.stdout) == jsonable_encoder(locked_backend.cycle_detail)
    assert tui_run == locked_backend.run_summary
    assert tui_cycle == locked_backend.cycle_detail
    assert tuple(control.action for control in dashboard_state.action_rail if control.enabled) == ("observe", "mode switch")
    assert dashboard_state.cycle_detail is not None
    assert dashboard_state.cycle_detail.diff_summary == locked_backend.cycle_detail.diff_summary


@pytest.mark.parametrize("action", ["mode switch", "pause", "resume", "branch", "clone", "reset", "rollback"])
def test_action_receipts_and_command_semantics_match_across_surfaces(action: str) -> None:
    api_backend, api_result = invoke_api_action(action, unlocked=True)
    cli_backend, cli_result = invoke_cli_action(action, unlocked=True)
    tui_backend, tui_result = invoke_tui_action(action, unlocked=True)
    dashboard_backend, dashboard_result = invoke_dashboard_action(action, unlocked=True)

    assert api_result["status_code"] == 202
    assert api_result["payload"]["dispatch_result"]["status"] == "allowed"
    assert cli_result["exit_code"] == 0
    assert cli_result["payload"]["status"] == "allowed"
    assert tui_result.status == "allowed"
    assert dashboard_result is not None
    assert dashboard_result["dispatch_result"]["status"] == "allowed"
    assert semantic_signature(api_backend.submissions[-1]) == semantic_signature(cli_backend.submissions[-1])
    assert semantic_signature(cli_backend.submissions[-1]) == semantic_signature(tui_backend.submissions[-1])
    assert semantic_signature(tui_backend.submissions[-1]) == semantic_signature(dashboard_backend.submissions[-1])


@pytest.mark.parametrize("action", ["pause", "resume", "branch", "clone", "reset", "rollback"])
def test_sensitive_actions_fail_closed_before_active_mode_switch_receipt(action: str) -> None:
    api_backend, api_result = invoke_api_action(action, unlocked=False)
    cli_backend, cli_result = invoke_cli_action(action, unlocked=False)
    tui_backend, tui_result = invoke_tui_action(action, unlocked=False)
    dashboard_backend, dashboard_result = invoke_dashboard_action(action, unlocked=False)

    expected_reason = f"{action} requires an active mode-switch receipt for the same scope and mode context"

    assert api_result["status_code"] == 403
    assert api_result["payload"]["dispatch_result"]["status"] == "denied"
    assert api_result["payload"]["dispatch_result"]["deny_reason"] == expected_reason
    assert cli_result["exit_code"] == 0
    assert cli_result["payload"]["status"] == "denied"
    assert cli_result["payload"]["deny_reason"] == expected_reason
    assert tui_result.status == "denied"
    assert tui_result.deny_reason == expected_reason
    assert dashboard_result is not None
    assert dashboard_result["dispatch_result"]["status"] == "denied"
    assert dashboard_result["dispatch_result"]["deny_reason"] == expected_reason
    assert semantic_signature(api_backend.submissions[-1]) == semantic_signature(cli_backend.submissions[-1])
    assert semantic_signature(cli_backend.submissions[-1]) == semantic_signature(tui_backend.submissions[-1])
    assert semantic_signature(tui_backend.submissions[-1]) == semantic_signature(dashboard_backend.submissions[-1])

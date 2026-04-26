from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from rich.console import Console
from typer.testing import CliRunner

from live_ai_terrarium.audit.ledger import AuditLedgerEntry
from live_ai_terrarium.contracts.records import (
    ArtifactRef,
    CycleRecord,
    HashOrSnapshot,
    IncidentRecord,
    ResourceUsage,
    RunLimits,
    RunRecord,
    TokenUsage,
)
from live_ai_terrarium.control.commands import CANONICAL_ACTIONS, CommandEnvelope, CommandScope, ModeSwitchReceipt
from live_ai_terrarium.control.dispatcher import CommandDispatcher, DispatchContext
from live_ai_terrarium.orchestrator.runtime import LifecycleReceipt
from live_ai_terrarium.query.service import QueryService
from live_ai_terrarium.storage.paths import RunScope
from live_ai_terrarium.storage.run_evidence import CycleAuditLink, RunStartManifest

from live_ai_terrarium.adapters.cli.gb import CommandReceipt, SubmissionContext, create_app
from live_ai_terrarium.adapters.cli.tui import RichTuiAdapter


def make_run_scope(*, run_id: str = "run-stability-baseline") -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id=run_id,
    )


def make_command_scope(run: RunScope) -> CommandScope:
    return CommandScope(
        project_id=run.project_id,
        glass_box_id=run.glassbox_id,
        experiment_id=run.experiment_id,
        run_id=run.run_id,
    )


def make_artifact_ref(locator: str) -> ArtifactRef:
    return ArtifactRef(uuid=uuid4(), locator=locator)


def make_run_record(run: RunScope) -> RunRecord:
    return RunRecord(
        project_id={"uuid": str(uuid4()), "readable_id": run.project_id},
        glass_box_id={"uuid": str(uuid4()), "readable_id": run.glassbox_id},
        experiment_id={"uuid": str(uuid4()), "readable_id": run.experiment_id},
        run_id={"uuid": str(uuid4()), "readable_id": run.run_id},
        task_identity="LAT-015",
        seed=7,
        limits=RunLimits(values={"max_cycles": 10, "max_cpu_percent": 90}),
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        release_tag="v1.0.1",
        image_name_label="glassbox:v1",
        runtime_profile=HashOrSnapshot(snapshot_ref=make_artifact_ref("security/runtime-profile.yaml")),
        command_catalog=HashOrSnapshot(snapshot_ref=make_artifact_ref("security/command-specs.yaml")),
        audit_event_refs=[make_artifact_ref("audit/requested.json")],
        full_log_bundle_ref=make_artifact_ref("logs/full-log-bundle.jsonl"),
    )


def make_cycle_record(run: RunScope, *, cycle_id: str, score: float, decision: str, test_result: str) -> CycleRecord:
    index = int(cycle_id.rsplit("-", 1)[-1])
    return CycleRecord(
        project_id={"uuid": str(uuid4()), "readable_id": run.project_id},
        glass_box_id={"uuid": str(uuid4()), "readable_id": run.glassbox_id},
        experiment_id={"uuid": str(uuid4()), "readable_id": run.experiment_id},
        run_id={"uuid": str(uuid4()), "readable_id": run.run_id},
        cycle_id={"uuid": str(uuid4()), "readable_id": cycle_id},
        mutation_id={"uuid": str(uuid4()), "readable_id": f"mutation-{index:04d}"},
        task_identity="LAT-015",
        diff_summary=f"Updated worker logic for {cycle_id}.",
        diff_ref=make_artifact_ref(f"diffs/{cycle_id}.patch"),
        gate_decision=decision,
        score=score,
        test_result=test_result,
        error_summary=None if decision == "accepted" else "regression detected in smoke tests",
        model_identity="gpt-5.4",
        prompt_ref=make_artifact_ref(f"prompts/{cycle_id}.json"),
        token_usage=TokenUsage(input_tokens=100 + index, output_tokens=20 + index, total_tokens=140 + (2 * index)),
        latency_ms=900 + index,
        resources=ResourceUsage(cpu_percent=42.5 + index, ram_mb=256 + index, disk_mb=1024 + index),
        snapshot_refs=[
            make_artifact_ref(f"snapshots/cycles/{cycle_id}/manifest.json"),
            make_artifact_ref(f"snapshots/full/snapshot-{cycle_id}/manifest.json"),
        ],
        audit_event_refs=[
            make_artifact_ref(f"audit/{cycle_id}/requested.json"),
            make_artifact_ref(f"audit/{cycle_id}/completed.json"),
        ],
        full_log_bundle_ref=make_artifact_ref(f"logs/{cycle_id}/full-log-bundle.jsonl"),
    )


def make_manifest(run: RunScope) -> RunStartManifest:
    return RunStartManifest(
        created_at="2026-04-26T09:59:59Z",
        project_id=run.project_id,
        glass_box_id=run.glassbox_id,
        experiment_id=run.experiment_id,
        run_id=run.run_id,
        task_identity="LAT-015",
        seed=7,
        limits=RunLimits(values={"max_cycles": 10, "max_cpu_percent": 90}),
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        runtime_profile=HashOrSnapshot(snapshot_ref=make_artifact_ref("security/runtime-profile.yaml")),
        command_catalog=HashOrSnapshot(snapshot_ref=make_artifact_ref("security/command-specs.yaml")),
        supplemental_labels={"release_tag": "v1.0.1", "image_name": "glassbox:v1"},
    )


def make_cycle_link(run: RunScope, *, cycle_id: str) -> CycleAuditLink:
    return CycleAuditLink(
        project_id=run.project_id,
        glass_box_id=run.glassbox_id,
        experiment_id=run.experiment_id,
        run_id=run.run_id,
        cycle_id=cycle_id,
        audit_event_refs=[
            make_artifact_ref(f"audit/{cycle_id}/requested.json"),
            make_artifact_ref(f"audit/{cycle_id}/approved.json"),
            make_artifact_ref(f"audit/{cycle_id}/completed.json"),
        ],
        full_log_bundle_ref=make_artifact_ref(f"logs/{cycle_id}/full-log-bundle.jsonl"),
        log_sequence_start=11,
        log_sequence_end=19,
    )


def make_audit_entry(
    run: RunScope,
    *,
    action: str,
    event_type: str,
    occurred_at: str,
    actor_id: str,
    cycle_id: str | None = None,
    receipt_id: UUID | None = None,
    approval_id: UUID | None = None,
    details: dict[str, str] | None = None,
) -> AuditLedgerEntry:
    return AuditLedgerEntry(
        command_id=uuid4(),
        action=action,
        event_type=event_type,
        occurred_at=occurred_at,
        actor_id=actor_id,
        actor_role="operator",
        scope=make_command_scope(run),
        cycle_id=cycle_id,
        receipt_id=receipt_id,
        approval_id=approval_id,
        details=details or {},
        previous_event_hash=None,
        current_event_hash="0" * 64,
    )


def make_incident_record(run: RunScope, *, cycle_id: str) -> IncidentRecord:
    return IncidentRecord(
        incident_id={"uuid": str(uuid4()), "readable_id": "incident-syntax-failure"},
        run_id={"uuid": str(uuid4()), "readable_id": run.run_id},
        cycle_id={"uuid": str(uuid4()), "readable_id": cycle_id},
        stop_condition_type="syntax failure",
        trigger_detail="pytest reported a syntax error in app.py.",
        snapshot_ref=make_artifact_ref("snapshots/full/snapshot-incident-syntax-failure/manifest.json"),
        branch_ref=make_artifact_ref("mirrors/branches/branch-syntax-failure-cycle-0002.json"),
        recovery_outcome="rolled back to last accepted stable cycle cycle-0001",
        incident_report_ref=make_artifact_ref("incidents/incident-syntax-failure/report.json"),
    )


def build_sample_views() -> tuple[CommandScope, object, object]:
    run = make_run_scope()
    run_record = make_run_record(run)
    cycle_1 = make_cycle_record(run, cycle_id="cycle-0001", score=0.98, decision="accepted", test_result="passed")
    cycle_2 = make_cycle_record(run, cycle_id="cycle-0002", score=0.41, decision="rejected", test_result="failed")
    manifest = make_manifest(run)
    cycle_links = {
        "cycle-0001": make_cycle_link(run, cycle_id="cycle-0001"),
        "cycle-0002": make_cycle_link(run, cycle_id="cycle-0002"),
    }
    incident = make_incident_record(run, cycle_id="cycle-0002")
    mode_switch_receipt_id = uuid4()
    approval_id = uuid4()
    audit_entries = [
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.requested",
            occurred_at="2026-04-26T10:00:00Z",
            actor_id="observer-1",
            details={"mode_context": "mode-context-1"},
        ),
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.approval_requested",
            occurred_at="2026-04-26T10:00:01Z",
            actor_id="observer-1",
            approval_id=approval_id,
            details={"mode_context": "mode-context-1"},
        ),
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.approved",
            occurred_at="2026-04-26T10:00:02Z",
            actor_id="operator-1",
            approval_id=approval_id,
            receipt_id=mode_switch_receipt_id,
            details={"mode_context": "mode-context-1"},
        ),
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.completed",
            occurred_at="2026-04-26T10:00:03Z",
            actor_id="operator-1",
            receipt_id=mode_switch_receipt_id,
            details={"mode_context": "mode-context-1", "target_mode": "control-enabled"},
        ),
        make_audit_entry(
            run,
            action="rollback",
            event_type="command.started",
            occurred_at="2026-04-26T10:05:00Z",
            actor_id="operator-1",
            cycle_id="cycle-0002",
            details={"target_cycle_id": "cycle-0001"},
        ),
        make_audit_entry(
            run,
            action="rollback",
            event_type="command.completed",
            occurred_at="2026-04-26T10:05:15Z",
            actor_id="operator-1",
            cycle_id="cycle-0002",
            details={"target_cycle_id": "cycle-0001"},
        ),
    ]
    query_service = QueryService()
    scope = make_command_scope(run)
    run_summary = query_service.build_run_summary(
        run_record=run_record,
        cycle_records=[cycle_1, cycle_2],
        audit_events=audit_entries,
        lifecycle_receipt=LifecycleReceipt(
            action="rollback",
            run=run,
            lifecycle_state="active",
            current_mode="control-enabled",
            target_cycle_id="cycle-0001",
        ),
        manifest=manifest,
        cycle_links=cycle_links,
        incident_records=[incident],
        recovery_reports={
            incident.incident_id.readable_id: {
                "ordered_steps": ["pause", "snapshot", "rollback", "report"],
                "full_log_refs": ["logs/recovery/incident-syntax-failure.jsonl"],
                "branch": {
                    "branch_name": "branch-syntax-failure-cycle-0002",
                    "branch_ref": "mirrors/branches/branch-syntax-failure-cycle-0002.json",
                },
                "recovery": {
                    "rollback_target": "cycle-0001",
                    "outcome": "rollback completed",
                    "restore_manifest": "snapshots/full/snapshot-incident-syntax-failure/restore.json",
                },
            }
        },
    )
    cycle_detail = query_service.build_cycle_detail(
        cycle_record=cycle_2,
        run_record=run_record,
        audit_events=audit_entries,
        lifecycle_receipt=LifecycleReceipt(
            action="rollback",
            run=run,
            lifecycle_state="active",
            current_mode="control-enabled",
            target_cycle_id="cycle-0001",
        ),
        manifest=manifest,
        cycle_link=cycle_links["cycle-0002"],
        incident_record=incident,
        recovery_report={
            "ordered_steps": ["pause", "snapshot", "rollback", "report"],
            "full_log_refs": ["logs/recovery/incident-syntax-failure.jsonl"],
            "branch": {
                "branch_name": "branch-syntax-failure-cycle-0002",
                "branch_ref": "mirrors/branches/branch-syntax-failure-cycle-0002.json",
            },
            "recovery": {
                "rollback_target": "cycle-0001",
                "outcome": "rollback completed",
                "restore_manifest": "snapshots/full/snapshot-incident-syntax-failure/restore.json",
            },
        },
    )
    return scope, run_summary, cycle_detail


class RecordingQueryBackend:
    def __init__(self, run_summary, cycle_detail) -> None:
        self._run_summary = run_summary
        self._cycle_detail = cycle_detail
        self.calls: list[tuple[str, str | None]] = []

    def read_run(self, scope: CommandScope):
        self.calls.append(("run", scope.run_id))
        return self._run_summary

    def read_cycle(self, scope: CommandScope, cycle_id: str):
        self.calls.append(("cycle", cycle_id))
        return self._cycle_detail


@dataclass
class RecordingControlBackend:
    submissions: list[tuple[CommandEnvelope, SubmissionContext]]

    def __init__(self) -> None:
        self.submissions = []

    def submit(self, command: CommandEnvelope, submission: SubmissionContext) -> CommandReceipt:
        self.submissions.append((command, submission))
        return CommandReceipt(
            action=command.action,
            status="accepted",
            receipt_id=uuid4(),
            deny_reason=None,
            current_mode=command.target_mode or "control-enabled",
            lifecycle_state="paused" if command.action == "pause" else "active",
            details={k: v for k, v in command.surface_metadata.items() if v is not None},
        )


class DispatcherBackedControlBackend:
    def __init__(self) -> None:
        self.current_mode = "observation-only"
        self.lifecycle_state = "active"
        self.active_receipt: ModeSwitchReceipt | None = None

    def submit(self, command: CommandEnvelope, submission: SubmissionContext) -> CommandReceipt:
        dispatcher = CommandDispatcher(handler=self._handler)
        result = dispatcher.dispatch(
            command,
            DispatchContext(
                current_mode=self.current_mode,
                mode_context=submission.mode_context,
                mode_switch_receipt=self.active_receipt,
            ),
        )
        if result.status == "allowed" and command.action == "mode switch":
            self.current_mode = command.target_mode or self.current_mode
            self.active_receipt = ModeSwitchReceipt(
                receipt_id=result.receipt_id,
                scope=command.scope,
                mode_context=submission.mode_context,
                target_mode=self.current_mode,
                status="active",
            )
        elif result.status == "allowed" and command.action == "pause":
            self.lifecycle_state = "paused"
        elif result.status == "allowed" and command.action == "resume":
            self.lifecycle_state = "active"
        return CommandReceipt(
            action=command.action,
            status=result.status,
            receipt_id=result.receipt_id,
            deny_reason=result.deny_reason,
            current_mode=self.current_mode,
            lifecycle_state=self.lifecycle_state,
            details=result.handler_result or {},
        )

    def _handler(self, command: CommandEnvelope) -> dict[str, object]:
        return {
            "action": command.action,
            "target_mode": command.target_mode,
            "clone_run_id": command.surface_metadata.get("clone_run_id"),
            "target_cycle_id": command.surface_metadata.get("target_cycle_id"),
            "branch_name": command.surface_metadata.get("branch_name"),
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


def render_text(renderable) -> str:
    console = Console(width=120, record=True)
    console.print(renderable)
    return console.export_text()


def semantic_signature(command: CommandEnvelope, submission: SubmissionContext) -> tuple[object, ...]:
    return (
        command.action,
        command.scope.scope_key(),
        command.target_mode,
        command.surface_metadata.get("clone_run_id"),
        command.surface_metadata.get("target_cycle_id"),
        command.surface_metadata.get("branch_name"),
        submission.reason,
        submission.cycle_id,
        submission.mode_context,
    )


def test_cli_observe_and_tui_views_read_shared_query_models() -> None:
    scope, run_summary, cycle_detail = build_sample_views()
    query_backend = RecordingQueryBackend(run_summary, cycle_detail)
    control_backend = RecordingControlBackend()
    runner = CliRunner()
    app = create_app(query_backend=query_backend, control_backend=control_backend)

    run_result = runner.invoke(app, ["observe", *command_options(scope)])
    cycle_result = runner.invoke(app, ["observe", *command_options(scope), "--cycle-id", "cycle-0002"])

    assert run_result.exit_code == 0
    assert cycle_result.exit_code == 0
    assert json.loads(run_result.stdout)["available_actions"] == list(run_summary.available_actions)
    assert json.loads(cycle_result.stdout)["diff_summary"] == cycle_detail.diff_summary

    tui = RichTuiAdapter(query_backend=query_backend, control_backend=control_backend, mode_context="mode-context-1")
    cycle_view = render_text(tui.render(view="cycle", scope=scope, cycle_id="cycle-0002"))
    audit_view = render_text(tui.render(view="audit", scope=scope))
    recovery_view = render_text(tui.render(view="recovery", scope=scope))

    assert "Updated worker logic for cycle-0002." in cycle_view
    assert "rejected" in cycle_view
    assert "incident-syntax-failure" in cycle_view
    assert "mode switch" in audit_view
    assert "rollback" in audit_view
    assert "cycle-0001" in recovery_view
    assert query_backend.calls == [
        ("run", scope.run_id),
        ("cycle", "cycle-0002"),
        ("run", scope.run_id),
        ("cycle", "cycle-0002"),
        ("run", scope.run_id),
        ("run", scope.run_id),
    ]
    assert control_backend.submissions == []


def test_cli_and_tui_cover_all_non_observe_actions_with_matching_command_semantics() -> None:
    scope, run_summary, cycle_detail = build_sample_views()
    query_backend = RecordingQueryBackend(run_summary, cycle_detail)
    control_backend = RecordingControlBackend()
    runner = CliRunner()
    app = create_app(query_backend=query_backend, control_backend=control_backend)
    tui = RichTuiAdapter(query_backend=query_backend, control_backend=control_backend, mode_context="mode-context-1")
    command_specs = [
        ("mode switch", ["mode-switch", *command_options(scope), "--target-mode", "control-enabled"], {"target_mode": "control-enabled"}),
        ("pause", ["pause", *command_options(scope)], {}),
        ("resume", ["resume", *command_options(scope)], {}),
        ("branch", ["branch", *command_options(scope), "--branch-name", "branch-cycle-0002"], {"branch_name": "branch-cycle-0002"}),
        ("clone", ["clone", *command_options(scope), "--clone-run-id", "run-clone"], {"clone_run_id": "run-clone"}),
        ("reset", ["reset", *command_options(scope), "--reason", "operator reset"], {"reason": "operator reset"}),
        ("rollback", ["rollback", *command_options(scope), "--target-cycle-id", "cycle-0001"], {"target_cycle_id": "cycle-0001"}),
    ]

    for action, argv, kwargs in command_specs:
        result = runner.invoke(app, argv)

        assert result.exit_code == 0
        assert json.loads(result.stdout)["action"] == action

        tui.submit_action(action=action, scope=scope, **kwargs)

    assert tuple(spec[0] for spec in command_specs) == CANONICAL_ACTIONS[1:]
    assert len(control_backend.submissions) == len(command_specs) * 2

    cli_submissions = control_backend.submissions[0::2]
    tui_submissions = control_backend.submissions[1::2]
    for (cli_command, cli_context), (tui_command, tui_context) in zip(cli_submissions, tui_submissions, strict=True):
        assert semantic_signature(cli_command, cli_context) == semantic_signature(tui_command, tui_context)


def test_cli_and_tui_preserve_dispatcher_receipt_parity_for_observation_only_controls() -> None:
    scope, run_summary, cycle_detail = build_sample_views()
    runner = CliRunner()

    cli_query_backend = RecordingQueryBackend(run_summary, cycle_detail)
    cli_control_backend = DispatcherBackedControlBackend()
    cli_app = create_app(query_backend=cli_query_backend, control_backend=cli_control_backend)

    tui_query_backend = RecordingQueryBackend(run_summary, cycle_detail)
    tui_control_backend = DispatcherBackedControlBackend()
    tui = RichTuiAdapter(query_backend=tui_query_backend, control_backend=tui_control_backend, mode_context="mode-context-1")

    cli_denied = runner.invoke(cli_app, ["pause", *command_options(scope)])
    tui_denied = tui.submit_action(action="pause", scope=scope)

    assert cli_denied.exit_code == 0
    assert json.loads(cli_denied.stdout)["status"] == "denied"
    assert json.loads(cli_denied.stdout)["deny_reason"] == tui_denied.deny_reason

    cli_mode_switch = runner.invoke(
        cli_app,
        ["mode-switch", *command_options(scope), "--target-mode", "control-enabled"],
    )
    tui_mode_switch = tui.submit_action(action="mode switch", scope=scope, target_mode="control-enabled")
    cli_pause = runner.invoke(cli_app, ["pause", *command_options(scope)])
    tui_pause = tui.submit_action(action="pause", scope=scope)

    assert json.loads(cli_mode_switch.stdout)["status"] == "allowed"
    assert tui_mode_switch.status == "allowed"
    assert json.loads(cli_pause.stdout)["status"] == "allowed"
    assert json.loads(cli_pause.stdout)["lifecycle_state"] == "paused"
    assert tui_pause.status == "allowed"
    assert tui_pause.lifecycle_state == "paused"
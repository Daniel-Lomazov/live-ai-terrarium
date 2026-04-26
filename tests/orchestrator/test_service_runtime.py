from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from live_ai_terrarium.audit.ledger import AuditLedger
from live_ai_terrarium.control.commands import CommandEnvelope, CommandScope, OBSERVATION_ONLY_MODE
from live_ai_terrarium.orchestrator.service import HostOrchestratorService
from live_ai_terrarium.storage.paths import RunScope, StoragePaths


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


def test_orchestrator_service_exposes_host_side_lifecycle_and_broker_hooks(tmp_path) -> None:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    service = HostOrchestratorService(storage_paths=storage)
    run_scope = make_run_scope()

    registered = service.register_run(
        run_scope,
        container_name="glassbox-gb-local-dev",
        image_digest="sha256:" + ("a" * 64),
        workspace_volume="glassbox-gb-local-dev-workspace",
    )

    assert registered.registration.run == run_scope
    assert registered.registration.runtime_profile_name == "glassbox-hardened-v1"
    assert registered.registration.network_mode == "none"
    assert registered.registration.published_ports == ()
    assert registered.registration.boundary_policy.outbox_path == PurePosixPath("/workspace/.gb/outbox")
    assert registered.current_mode == OBSERVATION_ONLY_MODE

    mode_switched = service.mode_switch(run_scope, target_mode="control-enabled")
    paused = service.pause(run_scope)
    resumed = service.resume(run_scope)
    reset = service.reset(run_scope, reason="manual reset")
    cloned = service.clone(run_scope, clone_run=make_run_scope(run_id="run-clone"))
    rolled_back = service.rollback(run_scope, target_cycle_id="cycle-0004")
    restored = service.restore(run_scope, snapshot_id="snapshot-0001")

    assert mode_switched.action == "mode switch"
    assert mode_switched.current_mode == "control-enabled"
    assert paused.lifecycle_state == "paused"
    assert resumed.lifecycle_state == "active"
    assert reset.reason == "manual reset"
    assert cloned.clone_run == make_run_scope(run_id="run-clone")
    assert rolled_back.target_cycle_id == "cycle-0004"
    assert restored.snapshot_id == "snapshot-0001"

    hooks = service.hooks_for(run_scope)

    assert hooks.log_capture.run == run_scope
    assert hooks.log_capture.channel == "run-log-capture"
    assert hooks.evidence_write.run == run_scope
    assert hooks.evidence_write.sandbox_outbox_path == PurePosixPath("/workspace/.gb/outbox")


def test_orchestrator_service_brokers_only_sanctioned_outbox_exports(tmp_path) -> None:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    service = HostOrchestratorService(storage_paths=storage)
    run_scope = make_run_scope()
    service.register_run(
        run_scope,
        container_name="glassbox-gb-local-dev",
        image_digest="sha256:" + ("b" * 64),
        workspace_volume="glassbox-gb-local-dev-workspace",
    )

    receipt = service.export_text(
        run_scope,
        export_id="artifact-0001",
        sandbox_path="/workspace/.gb/outbox/cycle-0001/report.txt",
        content="accepted artifact\n",
    )

    assert receipt.host_artifact_path.read_text(encoding="utf-8") == "accepted artifact\n"
    assert receipt.sandbox_path == PurePosixPath("/workspace/.gb/outbox/cycle-0001/report.txt")

    with pytest.raises(ValueError, match="outbox"):
        service.export_text(
            run_scope,
            export_id="artifact-0002",
            sandbox_path="/workspace/results/report.txt",
            content="denied artifact\n",
        )


def test_orchestrator_service_authorizes_runtime_tool_paths_without_direct_host_access(tmp_path) -> None:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    service = HostOrchestratorService(storage_paths=storage)
    run_scope = make_run_scope()
    service.register_run(
        run_scope,
        container_name="glassbox-gb-local-dev",
        image_digest="sha256:" + ("c" * 64),
        workspace_volume="glassbox-gb-local-dev-workspace",
    )

    tool_path = tmp_path / "sandbox-tooling" / "workspace" / "input.txt"

    assert service.authorize_runtime_host_path(run_scope, candidate_path=tool_path) == tool_path.resolve(strict=False)

    with pytest.raises(ValueError, match="host-controlled"):
        service.authorize_runtime_host_path(
            run_scope,
            candidate_path=storage.run_record_file(run_scope),
        )


def test_orchestrator_service_executes_an_auditable_backend_command_path(tmp_path) -> None:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    service = HostOrchestratorService(storage_paths=storage)
    run_scope = make_run_scope()
    service.register_run(
        run_scope,
        container_name="glassbox-gb-local-dev",
        image_digest="sha256:" + ("d" * 64),
        workspace_volume="glassbox-gb-local-dev-workspace",
    )
    scope = make_command_scope(run_scope)

    denied_pause = service.execute_command(
        CommandEnvelope(
            action="pause",
            scope=scope,
            idempotency_key="pause-before-receipt",
            surface="cli",
        ),
        actor_id="operator-local",
        actor_role="operator",
        occurred_at="2026-04-26T10:00:00Z",
        mode_context="mode-context-1",
    )

    assert denied_pause.dispatch_result.status == "denied"
    assert denied_pause.lifecycle_receipt is None
    assert service.describe_run(run_scope).lifecycle_state == "active"
    assert service.describe_run(run_scope).current_mode == OBSERVATION_ONLY_MODE

    mode_switch = service.execute_command(
        CommandEnvelope(
            action="mode switch",
            scope=scope,
            target_mode="control-enabled",
            idempotency_key="mode-switch-once",
            surface="cli",
        ),
        actor_id="operator-local",
        actor_role="operator",
        occurred_at="2026-04-26T10:00:01Z",
        mode_context="mode-context-1",
        approval_actor_id="approver-local",
        approval_actor_role="observer",
        approval_occurred_at="2026-04-26T10:00:02Z",
    )

    assert mode_switch.dispatch_result.status == "allowed"
    assert mode_switch.approval_record is not None
    assert mode_switch.approval_record.status == "approved"
    assert mode_switch.lifecycle_receipt is not None
    assert mode_switch.lifecycle_receipt.action == "mode switch"
    assert service.describe_run(run_scope).current_mode == "control-enabled"

    allowed_pause = service.execute_command(
        CommandEnvelope(
            action="pause",
            scope=scope,
            idempotency_key="pause-after-receipt",
            surface="dashboard",
        ),
        actor_id="operator-local",
        actor_role="operator",
        occurred_at="2026-04-26T10:00:03Z",
        mode_context="mode-context-1",
    )

    assert allowed_pause.dispatch_result.status == "allowed"
    assert allowed_pause.lifecycle_receipt is not None
    assert allowed_pause.lifecycle_receipt.action == "pause"
    assert allowed_pause.lifecycle_receipt.lifecycle_state == "paused"
    assert service.describe_run(run_scope).lifecycle_state == "paused"

    audit_events = AuditLedger(storage).read_run_events(scope)

    assert [event.event_type for event in audit_events] == [
        "command.requested",
        "command.failed",
        "command.requested",
        "command.approval_requested",
        "command.approved",
        "command.started",
        "command.completed",
        "command.requested",
        "command.started",
        "command.completed",
    ]
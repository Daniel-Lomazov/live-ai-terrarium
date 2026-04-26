from __future__ import annotations

import json

import pytest

from live_ai_terrarium.audit.ledger import AuditEvent, AuditLedger, AuditLedgerIntegrityError
from live_ai_terrarium.control.approval import ApprovalService
from live_ai_terrarium.control.commands import CommandEnvelope, CommandScope
from live_ai_terrarium.storage.paths import StoragePaths


def make_scope() -> CommandScope:
    return CommandScope(
        project_id="project-live-ai-terrarium",
        glass_box_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id="run-stability-baseline",
    )


def make_mode_switch_command() -> CommandEnvelope:
    return CommandEnvelope(
        action="mode switch",
        scope=make_scope(),
        target_mode="control-enabled",
        idempotency_key="mode-switch-once",
        surface="cli",
    )


def make_pause_command() -> CommandEnvelope:
    return CommandEnvelope(
        action="pause",
        scope=make_scope(),
        idempotency_key="pause-once",
        surface="dashboard",
    )


def make_ledger(tmp_path) -> AuditLedger:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    return AuditLedger(storage)


def test_ledger_appends_run_scoped_events_with_hash_chain(tmp_path) -> None:
    ledger = make_ledger(tmp_path)
    command = make_pause_command()

    requested = ledger.append(
        AuditEvent(
            command_id=command.command_id,
            action=command.action,
            event_type="command.requested",
            occurred_at="2026-04-26T09:00:00Z",
            actor_id="agent-orchestrator",
            actor_role="operator",
            scope=command.scope,
        )
    )
    started = ledger.append(
        AuditEvent(
            command_id=command.command_id,
            action=command.action,
            event_type="command.started",
            occurred_at="2026-04-26T09:00:01Z",
            actor_id="agent-orchestrator",
            actor_role="operator",
            scope=command.scope,
            cycle_id="cycle-0001",
        )
    )

    assert requested.previous_event_hash is None
    assert isinstance(requested.current_event_hash, str)
    assert len(requested.current_event_hash) == 64
    assert started.previous_event_hash == requested.current_event_hash
    assert isinstance(started.current_event_hash, str)
    assert len(started.current_event_hash) == 64
    assert [event.event_type for event in ledger.read_run_events(command.scope)] == [
        "command.requested",
        "command.started",
    ]

    ledger.verify_run_chain(command.scope)


def test_ledger_detects_tampering_after_append(tmp_path) -> None:
    ledger = make_ledger(tmp_path)
    command = make_pause_command()

    ledger.append(
        AuditEvent(
            command_id=command.command_id,
            action=command.action,
            event_type="command.requested",
            occurred_at="2026-04-26T09:00:00Z",
            actor_id="agent-orchestrator",
            actor_role="operator",
            scope=command.scope,
        )
    )
    ledger.append(
        AuditEvent(
            command_id=command.command_id,
            action=command.action,
            event_type="command.failed",
            occurred_at="2026-04-26T09:00:01Z",
            actor_id="agent-orchestrator",
            actor_role="operator",
            scope=command.scope,
            details={"reason": "simulated-failure"},
        )
    )

    ledger_path = ledger.ledger_path_for_scope(command.scope)
    entries = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    entries[0]["actor_role"] = "tampered"
    ledger_path.write_text("\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n", encoding="utf-8")

    with pytest.raises(AuditLedgerIntegrityError, match="tamper"):
        ledger.verify_run_chain(command.scope)


def test_approval_service_requires_recorded_approval_before_started_event(tmp_path) -> None:
    ledger = make_ledger(tmp_path)
    approval_service = ApprovalService(ledger=ledger)
    command = make_mode_switch_command()

    request = approval_service.record_request(
        command,
        actor_id="agent-orchestrator",
        actor_role="operator",
        occurred_at="2026-04-26T09:00:00Z",
        mode_context="mode-context-1",
        reason="unlock controlled actions",
    )

    with pytest.raises(PermissionError, match="approved approval"):
        approval_service.record_started(
            command,
            actor_id="agent-orchestrator",
            actor_role="operator",
            occurred_at="2026-04-26T09:00:01Z",
        )

    approved = approval_service.approve(
        request.approval_id,
        actor_id="agent-orchestrator",
        actor_role="operator",
        occurred_at="2026-04-26T09:00:02Z",
        mode_context="mode-context-1",
    )
    approval_service.record_started(
        command,
        actor_id="agent-orchestrator",
        actor_role="operator",
        occurred_at="2026-04-26T09:00:03Z",
        approval_id=approved.approval_id,
    )
    approval_service.record_completed(
        command,
        actor_id="agent-orchestrator",
        actor_role="operator",
        occurred_at="2026-04-26T09:00:04Z",
        approval_id=approved.approval_id,
    )

    assert request.status == "requested"
    assert approved.status == "approved"
    assert approved.mode_switch_receipt is not None
    assert approved.mode_switch_receipt.is_active_for(
        scope=command.scope,
        current_mode="control-enabled",
        mode_context="mode-context-1",
    )
    assert [event.event_type for event in ledger.read_run_events(command.scope)] == [
        "command.requested",
        "command.approval_requested",
        "command.approved",
        "command.started",
        "command.completed",
    ]


def test_approval_service_rejection_keeps_mode_switch_blocked(tmp_path) -> None:
    ledger = make_ledger(tmp_path)
    approval_service = ApprovalService(ledger=ledger)
    command = make_mode_switch_command()

    request = approval_service.record_request(
        command,
        actor_id="agent-orchestrator",
        actor_role="operator",
        occurred_at="2026-04-26T09:00:00Z",
        mode_context="mode-context-1",
    )
    rejected = approval_service.reject(
        request.approval_id,
        actor_id="agent-observer",
        actor_role="observer",
        occurred_at="2026-04-26T09:00:01Z",
        reason="operator review denied control unlock",
    )

    with pytest.raises(PermissionError, match="approved approval"):
        approval_service.record_started(
            command,
            actor_id="agent-orchestrator",
            actor_role="operator",
            occurred_at="2026-04-26T09:00:02Z",
            approval_id=rejected.approval_id,
        )

    assert rejected.status == "rejected"
    assert rejected.mode_switch_receipt is None
    assert [event.event_type for event in ledger.read_run_events(command.scope)] == [
        "command.requested",
        "command.approval_requested",
        "command.rejected",
    ]
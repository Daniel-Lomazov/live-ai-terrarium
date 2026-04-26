from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from live_ai_terrarium.audit.ledger import AuditEvent, AuditLedger
from live_ai_terrarium.contracts.records import ArtifactRef, HashOrSnapshot
from live_ai_terrarium.control.commands import CommandScope
from live_ai_terrarium.orchestrator.service import HostOrchestratorService
from live_ai_terrarium.recovery.recovery import RecoveryController
from live_ai_terrarium.recovery.snapshots import SnapshotService
from live_ai_terrarium.storage.log_capture import LogCaptureBroker, LogEntryInput
from live_ai_terrarium.storage.paths import CycleScope, RunScope, StoragePaths
from live_ai_terrarium.storage.run_evidence import RunEvidenceStore


def make_run_scope(*, run_id: str = "run-rollback-proof") -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id=run_id,
    )


def make_cycle_scope(run: RunScope, *, cycle_id: str) -> CycleScope:
    return CycleScope(run=run, cycle_id=cycle_id)


def make_storage(tmp_path: Path) -> tuple[StoragePaths, RunEvidenceStore, LogCaptureBroker, AuditLedger]:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    return storage, RunEvidenceStore(storage), LogCaptureBroker(storage), AuditLedger(storage)


def make_command_scope(run: RunScope) -> CommandScope:
    return CommandScope(
        project_id=run.project_id,
        glass_box_id=run.glassbox_id,
        experiment_id=run.experiment_id,
        run_id=run.run_id,
    )


def make_hash_snapshot(seed: str) -> HashOrSnapshot:
    return HashOrSnapshot(sha256=seed * 64)


def write_workspace_files(workspace_dir: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = workspace_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def make_orchestrator(tmp_path: Path, run: RunScope) -> tuple[StoragePaths, HostOrchestratorService]:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    orchestrator = HostOrchestratorService(storage_paths=storage)
    orchestrator.register_run(
        run,
        container_name="glassbox-gb-local-dev",
        image_digest="sha256:" + ("a" * 64),
        workspace_volume="glassbox-gb-local-dev-workspace",
    )
    return storage, orchestrator


def append_recovery_audit_refs(
    *,
    ledger: AuditLedger,
    run: RunScope,
    cycle_id: str,
    action: str,
    occurred_at: str,
    target_cycle_id: str | None = None,
) -> list[ArtifactRef]:
    scope = make_command_scope(run)
    command_id = uuid4()
    requested_entry = ledger.append(
        AuditEvent(
            command_id=command_id,
            action=action,
            event_type="command.requested",
            occurred_at=occurred_at,
            actor_id="operator-local",
            actor_role="operator",
            scope=scope,
            cycle_id=cycle_id,
            details={} if target_cycle_id is None else {"target_cycle_id": target_cycle_id},
        )
    )
    completed_entry = ledger.append(
        AuditEvent(
            command_id=command_id,
            action=action,
            event_type="command.completed",
            occurred_at=occurred_at.replace(":00Z", ":15Z"),
            actor_id="operator-local",
            actor_role="operator",
            scope=scope,
            cycle_id=cycle_id,
            details={} if target_cycle_id is None else {"target_cycle_id": target_cycle_id},
        )
    )
    ledger_locator = str(ledger.ledger_path_for_scope(scope))
    return [
        ArtifactRef(uuid=requested_entry.event_id, locator=ledger_locator),
        ArtifactRef(uuid=completed_entry.event_id, locator=ledger_locator),
    ]


def test_branch_and_continue_keeps_branch_snapshot_and_log_evidence(tmp_path: Path) -> None:
    run = make_run_scope(run_id="run-branch-proof")
    cycle_scope = make_cycle_scope(run, cycle_id="cycle-0010")
    workspace_dir = tmp_path / "workspace"
    write_workspace_files(
        workspace_dir,
        {
            "app.py": "print('failing path')\n",
            "notes/error.txt": "resource overuse observed\n",
        },
    )

    storage, orchestrator = make_orchestrator(tmp_path, run)
    evidence = RunEvidenceStore(storage)
    log_capture = LogCaptureBroker(storage)
    evidence.create_run_manifest(
        run,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-017",
        seed=17,
        limits={"max_cycles": 10, "max_cpu_percent": 90},
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        runtime_profile=make_hash_snapshot("c"),
        command_catalog=make_hash_snapshot("d"),
    )
    log_receipt = log_capture.append_entries(
        run,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:10:00Z",
                broker_name="orchestrator",
                stream="stdout",
                message="cycle-0010 hit resource overuse",
                cycle_id="cycle-0010",
            )
        ],
    )
    controller = RecoveryController(orchestrator=orchestrator, snapshots=SnapshotService(storage))

    outcome = controller.branch_and_continue(
        cycle_scope=cycle_scope,
        workspace_dir=workspace_dir,
        incident_id="incident-resource-overuse",
        branch_name="branch-resource-overuse-cycle-0010",
        stop_condition_type="resource overuse",
        trigger_detail="CPU stayed above 90 percent of budget for 31 seconds.",
        full_log_refs=(log_receipt.bundle_ref.locator,),
    )

    report_payload = json.loads(outcome.incident_report_path.read_text(encoding="utf-8"))
    mirror_path = storage.state_root / outcome.branch_ref.locator
    mirror_payload = json.loads(mirror_path.read_text(encoding="utf-8"))

    assert outcome.ordered_steps == ("pause", "snapshot", "branch-and-continue", "report")
    assert outcome.pause_receipt.action == "pause"
    assert outcome.branch_ref is not None
    assert mirror_path.exists()
    assert report_payload["branch"]["branch_ref"] == outcome.branch_ref.locator
    assert report_payload["evidence"]["failing_cycle_snapshot"] == outcome.cycle_snapshot.artifact_ref.locator
    assert report_payload["evidence"]["full_snapshot"] == outcome.full_snapshot.artifact_ref.locator
    assert report_payload["full_log_refs"] == [log_receipt.bundle_ref.locator]
    assert mirror_payload["sandbox_branch_name"] == "branch-resource-overuse-cycle-0010"
    assert mirror_payload["full_log_refs"] == [log_receipt.bundle_ref.locator]


def test_manual_rollback_restores_last_accepted_state_and_preserves_proof_refs(tmp_path: Path) -> None:
    run = make_run_scope(run_id="run-manual-rollback-proof")
    accepted_cycle = make_cycle_scope(run, cycle_id="cycle-0009")
    failing_cycle = make_cycle_scope(run, cycle_id="cycle-0010")
    workspace_dir = tmp_path / "workspace"
    storage, orchestrator = make_orchestrator(tmp_path, run)
    evidence, log_capture, ledger = RunEvidenceStore(storage), LogCaptureBroker(storage), AuditLedger(storage)
    snapshots = SnapshotService(storage)
    controller = RecoveryController(orchestrator=orchestrator, snapshots=snapshots)

    evidence.create_run_manifest(
        run,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-017",
        seed=17,
        limits={"max_cycles": 10, "max_cpu_percent": 90},
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        runtime_profile=make_hash_snapshot("c"),
        command_catalog=make_hash_snapshot("d"),
    )

    accepted_content = "print('accepted stable state')\n"
    write_workspace_files(workspace_dir, {"app.py": accepted_content, "README.md": "stable\n"})
    accepted_snapshot = snapshots.capture_cycle_snapshot(accepted_cycle, workspace_dir=workspace_dir)
    write_workspace_files(
        workspace_dir,
        {
            "app.py": "print('broken state')\nsyntax error\n",
            "README.md": "failing\n",
        },
    )
    log_receipt = log_capture.append_entries(
        run,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:10:00Z",
                broker_name="evaluator",
                stream="stderr",
                message="cycle-0010 syntax failure",
                cycle_id="cycle-0010",
            )
        ],
    )

    outcome = controller.manual_rollback(
        cycle_scope=failing_cycle,
        workspace_dir=workspace_dir,
        incident_id="incident-syntax-failure",
        stop_condition_type="syntax failure",
        trigger_detail="pytest reported a syntax error in app.py.",
        last_accepted_cycle_id="cycle-0009",
        full_log_refs=(log_receipt.bundle_ref.locator,),
    )

    audit_refs = append_recovery_audit_refs(
        ledger=ledger,
        run=run,
        cycle_id="cycle-0010",
        action="rollback",
        occurred_at="2026-04-26T10:10:00Z",
        target_cycle_id="cycle-0009",
    )
    evidence.link_cycle_to_audit(
        failing_cycle,
        audit_event_refs=audit_refs,
        full_log_bundle_ref=log_receipt.bundle_ref,
        log_sequence_start=log_receipt.first_sequence,
        log_sequence_end=log_receipt.last_sequence,
    )
    proof_evidence = evidence.lookup_cycle_proof_evidence(failing_cycle)
    report_payload = json.loads(outcome.incident_report_path.read_text(encoding="utf-8"))

    assert outcome.ordered_steps == ("pause", "snapshot", "rollback", "report")
    assert outcome.rollback_receipt is not None
    assert outcome.rollback_receipt.action == "rollback"
    assert outcome.rollback_receipt.target_cycle_id == "cycle-0009"
    assert (workspace_dir / "app.py").read_text(encoding="utf-8") == accepted_content
    assert report_payload["recovery"]["rollback_target"] == "cycle-0009"
    assert report_payload["recovery"]["restore_manifest"] == accepted_snapshot.artifact_ref.locator
    assert proof_evidence.full_log_bundle_ref.locator == log_receipt.bundle_ref.locator
    assert [ref.uuid for ref in proof_evidence.audit_event_refs] == [ref.uuid for ref in audit_refs]
    assert Path(proof_evidence.cycle_link_ref.locator).exists()

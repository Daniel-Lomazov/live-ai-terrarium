from __future__ import annotations

import json
from pathlib import Path

from live_ai_terrarium.orchestrator.service import HostOrchestratorService
from live_ai_terrarium.recovery.recovery import RecoveryController
from live_ai_terrarium.recovery.snapshots import SnapshotService
from live_ai_terrarium.storage.paths import CycleScope, RunScope, StoragePaths


def make_run_scope(*, run_id: str = "run-stability-baseline") -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id=run_id,
    )


def make_cycle_scope(run: RunScope, *, cycle_id: str) -> CycleScope:
    return CycleScope(run=run, cycle_id=cycle_id)


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


def write_workspace_files(workspace_dir: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = workspace_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_branch_and_continue_enforces_pause_then_snapshot_then_report(tmp_path: Path) -> None:
    run = make_run_scope()
    cycle = make_cycle_scope(run, cycle_id="cycle-0005")
    workspace_dir = tmp_path / "workspace"
    write_workspace_files(
        workspace_dir,
        {
            "app.py": "print('failing path')\n",
            "notes/error.txt": "cpu spike observed\n",
        },
    )
    storage, orchestrator = make_orchestrator(tmp_path, run)
    controller = RecoveryController(
        orchestrator=orchestrator,
        snapshots=SnapshotService(storage),
    )

    outcome = controller.branch_and_continue(
        cycle_scope=cycle,
        workspace_dir=workspace_dir,
        incident_id="incident-resource-overuse",
        branch_name="branch-resource-overuse-cycle-0005",
        stop_condition_type="resource overuse",
        trigger_detail="CPU stayed above 90 percent of budget for 31 seconds.",
        full_log_refs=("logs/bundles/cycle-0005",),
    )

    assert outcome.ordered_steps == (
        "pause",
        "snapshot",
        "branch-and-continue",
        "report",
    )
    assert outcome.pause_receipt.action == "pause"
    assert outcome.cycle_snapshot.artifact_ref.locator.endswith("/cycles/cycle-0005/manifest.json")
    assert "/full/" in outcome.full_snapshot.artifact_ref.locator
    assert outcome.incident_report_path.exists()


def test_branch_and_continue_writes_mirror_evidence_and_incident_bundle(tmp_path: Path) -> None:
    run = make_run_scope()
    cycle = make_cycle_scope(run, cycle_id="cycle-0005")
    workspace_dir = tmp_path / "workspace"
    write_workspace_files(
        workspace_dir,
        {
            "agent.log": "cycle failed with resource overuse\n",
            "src/worker.py": "raise RuntimeError('cpu runaway')\n",
        },
    )
    storage, orchestrator = make_orchestrator(tmp_path, run)
    controller = RecoveryController(
        orchestrator=orchestrator,
        snapshots=SnapshotService(storage),
    )

    outcome = controller.branch_and_continue(
        cycle_scope=cycle,
        workspace_dir=workspace_dir,
        incident_id="incident-resource-overuse",
        branch_name="branch-resource-overuse-cycle-0005",
        stop_condition_type="resource overuse",
        trigger_detail="CPU stayed above 90 percent of budget for 31 seconds.",
        full_log_refs=("logs/bundles/cycle-0005", "logs/bundles/run-stability-baseline"),
    )

    mirror_evidence_path = storage.mirror_dir(run) / "branches" / "branch-resource-overuse-cycle-0005.json"
    mirror_payload = json.loads(mirror_evidence_path.read_text(encoding="utf-8"))
    incident_payload = json.loads(outcome.incident_record_path.read_text(encoding="utf-8"))
    report_payload = json.loads(outcome.incident_report_path.read_text(encoding="utf-8"))

    assert mirror_payload["sandbox_branch_name"] == "branch-resource-overuse-cycle-0005"
    assert mirror_payload["outer_repo_branch_created"] is False
    assert mirror_payload["source_cycle_id"] == "cycle-0005"
    assert mirror_payload["snapshot_ref"] == outcome.full_snapshot.artifact_ref.locator

    assert incident_payload["branch_ref"]["locator"] == outcome.branch_ref.locator
    assert incident_payload["snapshot_ref"]["locator"] == outcome.full_snapshot.artifact_ref.locator
    assert report_payload["branch"]["branch_name"] == "branch-resource-overuse-cycle-0005"
    assert report_payload["evidence"]["failing_cycle_snapshot"] == outcome.cycle_snapshot.artifact_ref.locator
    assert report_payload["full_log_refs"] == [
        "logs/bundles/cycle-0005",
        "logs/bundles/run-stability-baseline",
    ]


def test_manual_rollback_restores_last_accepted_stable_state(tmp_path: Path) -> None:
    run = make_run_scope()
    accepted_cycle = make_cycle_scope(run, cycle_id="cycle-0004")
    failing_cycle = make_cycle_scope(run, cycle_id="cycle-0005")
    workspace_dir = tmp_path / "workspace"
    storage, orchestrator = make_orchestrator(tmp_path, run)
    snapshots = SnapshotService(storage)
    controller = RecoveryController(orchestrator=orchestrator, snapshots=snapshots)

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

    outcome = controller.manual_rollback(
        cycle_scope=failing_cycle,
        workspace_dir=workspace_dir,
        incident_id="incident-syntax-failure",
        stop_condition_type="syntax failure",
        trigger_detail="pytest reported a syntax error in app.py.",
        last_accepted_cycle_id="cycle-0004",
        full_log_refs=("logs/bundles/cycle-0005",),
    )

    report_payload = json.loads(outcome.incident_report_path.read_text(encoding="utf-8"))

    assert outcome.ordered_steps == ("pause", "snapshot", "rollback", "report")
    assert outcome.rollback_receipt is not None
    assert outcome.rollback_receipt.action == "rollback"
    assert outcome.rollback_receipt.target_cycle_id == "cycle-0004"
    assert (workspace_dir / "app.py").read_text(encoding="utf-8") == accepted_content
    assert report_payload["recovery"]["rollback_target"] == "cycle-0004"
    assert report_payload["recovery"]["restore_manifest"] == accepted_snapshot.artifact_ref.locator
    assert report_payload["evidence"]["failing_cycle_snapshot"] == outcome.cycle_snapshot.artifact_ref.locator


def test_reconstruct_restore_plan_from_snapshot_manifest_is_deterministic(tmp_path: Path) -> None:
    run = make_run_scope()
    storage, _ = make_orchestrator(tmp_path, run)
    snapshots = SnapshotService(storage)
    workspace_dir = tmp_path / "workspace"
    write_workspace_files(
        workspace_dir,
        {
            "z-last.txt": "z\n",
            "a-first.txt": "a\n",
            "nested/m-middle.txt": "m\n",
        },
    )

    capture = snapshots.capture_full_snapshot(
        run,
        snapshot_id="snapshot-stop-cycle-0005",
        workspace_dir=workspace_dir,
        reason="stop condition",
    )
    plan = snapshots.reconstruct_restore(capture.artifact_ref.locator)

    assert plan.snapshot_id == "snapshot-stop-cycle-0005"
    assert plan.manifest_locator == capture.artifact_ref.locator
    assert [entry.relative_path for entry in plan.entries] == [
        "a-first.txt",
        "nested/m-middle.txt",
        "z-last.txt",
    ]
    assert plan.entries[0].source_path.exists()
    assert plan.entries[1].source_locator.endswith("/snapshot-stop-cycle-0005/files/nested/m-middle.txt")
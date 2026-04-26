from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from live_ai_terrarium.control.commands import OBSERVATION_ONLY_MODE
from live_ai_terrarium.orchestrator.service import HostOrchestratorService
from live_ai_terrarium.storage.paths import RunScope, StoragePaths


def make_run_scope(*, run_id: str = "run-stability-baseline") -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id=run_id,
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
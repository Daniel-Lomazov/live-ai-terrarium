from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from live_ai_terrarium.orchestrator.boundary import SandboxBoundaryPolicy
from live_ai_terrarium.storage.exports import AppendOnlyExportWriter
from live_ai_terrarium.storage.paths import RunScope, StoragePaths


def make_run_scope() -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id="run-stability-baseline",
    )


def test_boundary_models_one_workspace_mount_and_no_extra_shared_mounts() -> None:
    policy = SandboxBoundaryPolicy.v1()

    assert policy.workspace_mount_target == PurePosixPath("/workspace")
    assert policy.outbox_path == PurePosixPath("/workspace/.gb/outbox")
    assert policy.shared_mount_targets == (PurePosixPath("/workspace"),)

    with pytest.raises(ValueError, match="extra shared mount"):
        policy.validate_shared_mounts(["/workspace", "/host/state"])


@pytest.mark.parametrize(
    ("path_factory", "message"),
    [
        (lambda storage, run: storage.run_record_file(run), "host-controlled"),
        (lambda storage, run: storage.export_item_dir(run, "artifact-0001"), "host-controlled"),
    ],
)
def test_boundary_blocks_direct_host_access(path_factory, message: str, tmp_path) -> None:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    policy = SandboxBoundaryPolicy.v1()
    run_scope = make_run_scope()

    with pytest.raises(ValueError, match=message):
        policy.validate_no_direct_host_access(path_factory(storage, run_scope), storage)


@pytest.mark.parametrize(
    "invalid_target",
    [
        "/workspace/results/final.txt",
        "/workspace/.gb/outbox/../cycles/cycle-0001.json",
        "relative/outbox.txt",
    ],
)
def test_boundary_rejects_invalid_export_targets(invalid_target: str) -> None:
    policy = SandboxBoundaryPolicy.v1()

    with pytest.raises(ValueError, match="outbox"):
        policy.validate_export_target(invalid_target)


def test_export_writer_is_append_only_and_denies_rewrite(tmp_path) -> None:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    writer = AppendOnlyExportWriter(storage)
    run_scope = make_run_scope()

    receipt = writer.export_text(
        run_scope,
        export_id="artifact-0001",
        sandbox_path="/workspace/.gb/outbox/cycle-0001/report.txt",
        content="accepted artifact\n",
    )

    assert receipt.artifact_id == "artifact-0001"
    assert receipt.sandbox_path == PurePosixPath("/workspace/.gb/outbox/cycle-0001/report.txt")
    assert receipt.host_artifact_path.read_text(encoding="utf-8") == "accepted artifact\n"
    assert receipt.manifest_path.read_text(encoding="utf-8").splitlines() == [
        '{"artifact_id":"artifact-0001","sandbox_path":"/workspace/.gb/outbox/cycle-0001/report.txt"}'
    ]

    with pytest.raises(FileExistsError, match="append-only"):
        writer.export_text(
            run_scope,
            export_id="artifact-0001",
            sandbox_path="/workspace/.gb/outbox/cycle-0001/report.txt",
            content="rewritten artifact\n",
        )
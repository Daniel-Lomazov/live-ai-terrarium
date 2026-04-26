from __future__ import annotations

import json
from pathlib import PureWindowsPath

import pytest

from live_ai_terrarium.storage.filesystem import HostFilesystem
from live_ai_terrarium.storage.paths import (
    CycleScope,
    IncidentScope,
    ProofBundleScope,
    RunScope,
    StoragePaths,
)


def as_windows_path(value: object) -> PureWindowsPath:
    return PureWindowsPath(str(value))


def make_run_scope() -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id="run-stability-baseline",
    )


def test_storage_roots_default_under_localappdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")

    storage = StoragePaths.from_local_appdata()

    assert as_windows_path(storage.state_root) == PureWindowsPath(
        r"C:\Users\tester\AppData\Local\LiveAITerrarium\state"
    )
    assert as_windows_path(storage.backup_root) == PureWindowsPath(
        r"C:\Users\tester\AppData\Local\LiveAITerrarium\backups"
    )


def test_run_scoped_paths_are_deterministic_and_distinct() -> None:
    storage = StoragePaths.from_local_appdata(r"C:\LocalAppData")
    run_scope = make_run_scope()
    cycle_scope = CycleScope(run=run_scope, cycle_id="cycle-0003")
    incident_scope = IncidentScope(run=run_scope, incident_id="incident-resource-overuse")
    proof_scope = ProofBundleScope(run=run_scope, bundle_id="proof-ten-cycle")

    run_record = storage.run_record_file(run_scope)
    run_manifest = storage.run_manifest_file(run_scope)
    cycle_record = storage.cycle_record_file(cycle_scope)
    cycle_snapshot = storage.cycle_snapshot_dir(cycle_scope)
    full_snapshot = storage.full_snapshot_dir(run_scope, "snapshot-0005")
    export_item = storage.export_item_dir(run_scope, "mutation-0001")
    mirror_dir = storage.mirror_dir(run_scope)
    incident_file = storage.incident_file(incident_scope)
    proof_bundle_dir = storage.proof_bundle_dir(proof_scope)
    backup_bundle_dir = storage.backup_proof_bundle_dir(proof_scope)

    assert as_windows_path(run_record) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\records\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\run.json"
    )
    assert as_windows_path(run_manifest) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\manifests\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\run-start-reproducibility.json"
    )
    assert as_windows_path(cycle_record) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\records\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\cycles\cycle-0003.json"
    )
    assert as_windows_path(cycle_snapshot) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\snapshots\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\cycles\cycle-0003\files"
    )
    assert as_windows_path(full_snapshot) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\snapshots\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\full\snapshot-0005"
    )
    assert as_windows_path(export_item) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\exports\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\items\mutation-0001"
    )
    assert as_windows_path(mirror_dir) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\mirrors\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\git"
    )
    assert as_windows_path(incident_file) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\incidents\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\incident-resource-overuse.json"
    )
    assert as_windows_path(proof_bundle_dir) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\state\proofs\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\bundles\proof-ten-cycle"
    )
    assert as_windows_path(backup_bundle_dir) == PureWindowsPath(
        r"C:\LocalAppData\LiveAITerrarium\backups\projects\project-live-ai-terrarium\glassboxes\gb-local-dev\experiments\exp-proof-loop\runs\run-stability-baseline\proofs\proof-ten-cycle"
    )

    state_root = as_windows_path(storage.state_root)
    backup_root = as_windows_path(storage.backup_root)

    assert as_windows_path(run_record).is_relative_to(state_root)
    assert as_windows_path(run_manifest).is_relative_to(state_root)
    assert as_windows_path(cycle_record).is_relative_to(state_root)
    assert as_windows_path(cycle_snapshot).is_relative_to(state_root)
    assert as_windows_path(full_snapshot).is_relative_to(state_root)
    assert as_windows_path(export_item).is_relative_to(state_root)
    assert as_windows_path(mirror_dir).is_relative_to(state_root)
    assert as_windows_path(incident_file).is_relative_to(state_root)
    assert as_windows_path(proof_bundle_dir).is_relative_to(state_root)
    assert as_windows_path(backup_bundle_dir).is_relative_to(backup_root)

    assert len(
        {
            str(run_record),
            str(run_manifest),
            str(cycle_record),
            str(cycle_snapshot),
            str(full_snapshot),
            str(export_item),
            str(mirror_dir),
            str(incident_file),
            str(proof_bundle_dir),
            str(backup_bundle_dir),
        }
    ) == 10


def test_windows_unsafe_segments_are_rejected() -> None:
    with pytest.raises(ValueError, match="Windows-safe"):
        RunScope(
            project_id="project-live-ai-terrarium",
            glassbox_id="gb-local-dev",
            experiment_id="exp-proof-loop",
            run_id="run:bad",
        )


def test_host_filesystem_creates_parents_and_guards_writes(tmp_path) -> None:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    filesystem = HostFilesystem(storage)
    run_scope = make_run_scope()
    proof_scope = ProofBundleScope(run=run_scope, bundle_id="proof-ten-cycle")

    run_record = storage.run_record_file(run_scope)
    proof_index = storage.proof_bundle_dir(proof_scope) / "bundle-index.jsonl"

    filesystem.write_json(run_record, {"run_id": run_scope.run_id})
    filesystem.append_jsonl(
        proof_index,
        [
            {"artifact": "manifest", "path": "run-start-reproducibility.json"},
            {"artifact": "logs", "path": "full-log-bundle.jsonl"},
        ],
    )

    assert json.loads(run_record.read_text(encoding="utf-8")) == {
        "run_id": "run-stability-baseline"
    }
    assert proof_index.read_text(encoding="utf-8").splitlines() == [
        '{"artifact":"manifest","path":"run-start-reproducibility.json"}',
        '{"artifact":"logs","path":"full-log-bundle.jsonl"}',
    ]

    with pytest.raises(FileExistsError):
        filesystem.write_json(run_record, {"run_id": "run-overwrite"})

    with pytest.raises(ValueError, match="host-controlled"):
        filesystem.write_json(tmp_path / "repo" / "run.json", {"run_id": run_scope.run_id})
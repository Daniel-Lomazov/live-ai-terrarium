from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from live_ai_terrarium.audit.ledger import AuditEvent, AuditLedger
from live_ai_terrarium.contracts.records import (
    ArtifactRef,
    CycleRecord,
    HashOrSnapshot,
    ResourceUsage,
    RunLimits,
    RunRecord,
    TokenUsage,
)
from live_ai_terrarium.control.commands import CommandScope
from live_ai_terrarium.orchestrator.runtime import LifecycleReceipt
from live_ai_terrarium.query.service import QueryService
from live_ai_terrarium.storage.filesystem import HostFilesystem
from live_ai_terrarium.storage.log_capture import LogCaptureBroker, LogEntryInput
from live_ai_terrarium.storage.paths import CycleScope, ProofBundleScope, RunScope, StoragePaths
from live_ai_terrarium.storage.run_evidence import RunEvidenceStore


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def proof_clearance_path() -> Path:
    return repository_root() / "docs" / "reviews" / "proof-clearance-status.yaml"


def read_proof_clearance_status(path: Path) -> tuple[str | None, list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing proof-clearance status artifact: {path}")

    status: str | None = None
    blocker_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("status:"):
            status = stripped.partition(":")[2].strip().strip('"')
        if stripped.startswith("blocker_ids:"):
            raw_value = stripped.partition(":")[2].strip()
            if raw_value == "[]":
                blocker_ids = []
            elif raw_value.startswith("[") and raw_value.endswith("]"):
                blocker_ids = [
                    item.strip().strip('"')
                    for item in raw_value[1:-1].split(",")
                    if item.strip()
                ]

    return status, blocker_ids


def require_cleared_proof_status(path: Path) -> None:
    status, blocker_ids = read_proof_clearance_status(path)
    if status != "cleared":
        raise RuntimeError(
            f"Proof harness refused to run because proof-clearance status is {status!r} with blockers {blocker_ids}"
        )


def make_run_scope(*, run_id: str = "run-ten-cycle-proof") -> RunScope:
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


def make_hash_snapshot(seed: str) -> HashOrSnapshot:
    return HashOrSnapshot(sha256=seed * 64)


def make_run_record(run: RunScope, *, bundle_locator: str) -> RunRecord:
    return RunRecord(
        project_id={"uuid": str(uuid4()), "readable_id": run.project_id},
        glass_box_id={"uuid": str(uuid4()), "readable_id": run.glassbox_id},
        experiment_id={"uuid": str(uuid4()), "readable_id": run.experiment_id},
        run_id={"uuid": str(uuid4()), "readable_id": run.run_id},
        task_identity="LAT-017",
        seed=17,
        limits=RunLimits(values={"max_cycles": 10, "max_cpu_percent": 90}),
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        release_tag="milestone/v1-wave8",
        image_name_label="glassbox:v1",
        runtime_profile=make_hash_snapshot("c"),
        command_catalog=make_hash_snapshot("d"),
        audit_event_refs=[make_artifact_ref("audit/run-start.json")],
        full_log_bundle_ref=make_artifact_ref(bundle_locator),
    )


def make_cycle_record(run: RunScope, *, cycle_id: str, bundle_locator: str, score: float) -> CycleRecord:
    cycle_number = int(cycle_id.rsplit("-", 1)[-1])
    return CycleRecord(
        project_id={"uuid": str(uuid4()), "readable_id": run.project_id},
        glass_box_id={"uuid": str(uuid4()), "readable_id": run.glassbox_id},
        experiment_id={"uuid": str(uuid4()), "readable_id": run.experiment_id},
        run_id={"uuid": str(uuid4()), "readable_id": run.run_id},
        cycle_id={"uuid": str(uuid4()), "readable_id": cycle_id},
        mutation_id={"uuid": str(uuid4()), "readable_id": f"mutation-{cycle_number:04d}"},
        task_identity="LAT-017",
        diff_summary=f"Accepted mutation for {cycle_id}.",
        diff_ref=make_artifact_ref(f"diffs/{cycle_id}.patch"),
        gate_decision="accepted",
        score=score,
        test_result="passed",
        error_summary=None,
        model_identity="gpt-5.4",
        prompt_ref=make_artifact_ref(f"prompts/{cycle_id}.json"),
        token_usage=TokenUsage(
            input_tokens=110 + cycle_number,
            output_tokens=20 + cycle_number,
            total_tokens=150 + (2 * cycle_number),
        ),
        latency_ms=800 + cycle_number,
        resources=ResourceUsage(
            cpu_percent=40.0 + cycle_number,
            ram_mb=256 + cycle_number,
            disk_mb=1024 + cycle_number,
        ),
        snapshot_refs=[
            make_artifact_ref(f"snapshots/cycles/{cycle_id}/manifest.json"),
            make_artifact_ref(f"snapshots/full/snapshot-{cycle_id}/manifest.json"),
        ],
        audit_event_refs=[
            make_artifact_ref(f"audit/{cycle_id}/requested.json"),
            make_artifact_ref(f"audit/{cycle_id}/completed.json"),
        ],
        full_log_bundle_ref=make_artifact_ref(bundle_locator),
    )


def make_storage(tmp_path: Path) -> tuple[StoragePaths, HostFilesystem, RunEvidenceStore, LogCaptureBroker, AuditLedger]:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    filesystem = HostFilesystem(storage)
    return storage, filesystem, RunEvidenceStore(storage), LogCaptureBroker(storage), AuditLedger(storage)


def write_canonical_run_record(filesystem: HostFilesystem, storage: StoragePaths, run: RunScope, run_record: RunRecord) -> None:
    filesystem.write_json(storage.run_record_file(run), run_record.model_dump(mode="json"))


def write_canonical_cycle_record(
    filesystem: HostFilesystem,
    storage: StoragePaths,
    cycle_scope: CycleScope,
    cycle_record: CycleRecord,
) -> None:
    filesystem.write_json(
        storage.cycle_record_file(cycle_scope),
        cycle_record.model_dump(mode="json"),
    )


def cycle_timestamp(cycle_number: int, second: int) -> str:
    return f"2026-04-26T10:{cycle_number:02d}:{second:02d}Z"


def append_cycle_evidence(
    *,
    run: RunScope,
    cycle_scope: CycleScope,
    evidence: RunEvidenceStore,
    log_capture: LogCaptureBroker,
    ledger: AuditLedger,
) -> None:
    append_receipt = log_capture.append_entries(
        run,
        entries=[
            LogEntryInput(
                occurred_at=cycle_timestamp(int(cycle_scope.cycle_id[-4:]), 0),
                broker_name="orchestrator",
                stream="stdout",
                message=f"{cycle_scope.cycle_id}: cycle started",
                cycle_id=cycle_scope.cycle_id,
            ),
            LogEntryInput(
                occurred_at=cycle_timestamp(int(cycle_scope.cycle_id[-4:]), 1),
                broker_name="evaluator",
                stream="stdout",
                message=f"{cycle_scope.cycle_id}: gate accepted",
                cycle_id=cycle_scope.cycle_id,
            ),
        ],
    )

    command_id = uuid4()
    scope = make_command_scope(run)
    requested_entry = ledger.append(
        AuditEvent(
            command_id=command_id,
            action="observe",
            event_type="command.requested",
            occurred_at=cycle_timestamp(int(cycle_scope.cycle_id[-4:]), 2),
            actor_id="operator-local",
            actor_role="operator",
            scope=scope,
            cycle_id=cycle_scope.cycle_id,
            details={"mode_context": "observation-only"},
        )
    )
    completed_entry = ledger.append(
        AuditEvent(
            command_id=command_id,
            action="observe",
            event_type="command.completed",
            occurred_at=cycle_timestamp(int(cycle_scope.cycle_id[-4:]), 3),
            actor_id="operator-local",
            actor_role="operator",
            scope=scope,
            cycle_id=cycle_scope.cycle_id,
            details={"mode_context": "observation-only"},
        )
    )

    ledger_locator = str(ledger.ledger_path_for_scope(scope))
    evidence.link_cycle_to_audit(
        cycle_scope,
        audit_event_refs=[
            ArtifactRef(uuid=requested_entry.event_id, locator=ledger_locator),
            ArtifactRef(uuid=completed_entry.event_id, locator=ledger_locator),
        ],
        full_log_bundle_ref=append_receipt.bundle_ref,
        log_sequence_start=append_receipt.first_sequence,
        log_sequence_end=append_receipt.last_sequence,
    )


def test_proof_harness_fails_closed_when_clearance_file_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "proof-clearance-status.yaml"

    with pytest.raises(FileNotFoundError, match="Missing proof-clearance status artifact"):
        require_cleared_proof_status(missing_path)


def test_proof_harness_fails_closed_when_clearance_is_blocked(tmp_path: Path) -> None:
    blocked_path = tmp_path / "proof-clearance-status.yaml"
    blocked_path.write_text(
        "plan_id: 20260426-live-ai-terrarium-v1\nstatus: blocked\nblocker_ids: [BND-001]\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="proof-clearance status is 'blocked'"):
        require_cleared_proof_status(blocked_path)


def test_ten_cycle_proof_harness_emits_inventory_for_ten_stable_cycles(tmp_path: Path) -> None:
    require_cleared_proof_status(proof_clearance_path())

    run = make_run_scope()
    storage, filesystem, evidence, log_capture, ledger = make_storage(tmp_path)

    manifest = evidence.create_run_manifest(
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
        supplemental_labels={"release_tag": "milestone/v1-wave8", "image_name": "glassbox:v1"},
    )
    bundle = log_capture.ensure_bundle(run, created_at="2026-04-26T09:59:59Z")
    run_record = make_run_record(run, bundle_locator=bundle.artifact_ref.locator)
    write_canonical_run_record(filesystem, storage, run, run_record)

    cycle_records: list[CycleRecord] = []
    cycle_links = {}
    for cycle_number in range(1, 11):
        cycle_id = f"cycle-{cycle_number:04d}"
        cycle_scope = CycleScope(run=run, cycle_id=cycle_id)
        append_cycle_evidence(
            run=run,
            cycle_scope=cycle_scope,
            evidence=evidence,
            log_capture=log_capture,
            ledger=ledger,
        )
        cycle_record = make_cycle_record(
            run,
            cycle_id=cycle_id,
            bundle_locator=bundle.artifact_ref.locator,
            score=0.90 + (cycle_number / 100),
        )
        write_canonical_cycle_record(filesystem, storage, cycle_scope, cycle_record)
        cycle_records.append(cycle_record)
        cycle_links[cycle_id] = evidence.read_cycle_link(cycle_scope)

    verified_audit_events = ledger.verify_run_chain(make_command_scope(run))
    run_summary = QueryService().build_run_summary(
        run_record=run_record,
        cycle_records=cycle_records,
        audit_events=verified_audit_events,
        lifecycle_receipt=LifecycleReceipt(
            action="resume",
            run=run,
            lifecycle_state="active",
            current_mode="observation-only",
        ),
        manifest=manifest,
        cycle_links=cycle_links,
        incident_records=[],
        recovery_reports={},
    )

    proof_bundle_scope = ProofBundleScope(run=run, bundle_id="proof-ten-cycle")
    proof_bundle_dir = filesystem.ensure_directory(storage.proof_bundle_dir(proof_bundle_scope))
    proof_inventory: list[dict[str, object]] = []
    for cycle_record in cycle_records:
        cycle_scope = CycleScope(run=run, cycle_id=cycle_record.cycle_id.readable_id)
        consumer_evidence = evidence.lookup_cycle_proof_evidence(cycle_scope)
        proof_inventory.append(
            {
                "cycle_id": cycle_scope.cycle_id,
                "cycle_record_ref": str(storage.cycle_record_file(cycle_scope)),
                "cycle_link_ref": consumer_evidence.cycle_link_ref.locator,
                "full_log_bundle_ref": consumer_evidence.full_log_bundle_ref.locator,
                "audit_event_ids": [str(ref.uuid) for ref in consumer_evidence.audit_event_refs],
                "audit_locator": consumer_evidence.audit_event_refs[0].locator,
            }
        )

    proof_manifest_path = filesystem.write_json(
        proof_bundle_dir / "proof-manifest.json",
        {
            "proof_clearance_status": "cleared",
            "run_manifest_ref": str(storage.run_manifest_file(run)),
            "run_record_ref": str(storage.run_record_file(run)),
            "immutable_build_identity": {
                "outer_repo_commit_sha": manifest.outer_repo_commit_sha,
                "container_image_digest": manifest.container_image_digest,
            },
            "reproducibility_manifest": manifest.model_dump(mode="json"),
            "canonical_cycle_record_refs": [
                str(storage.cycle_record_file(CycleScope(run=run, cycle_id=record.cycle_id.readable_id)))
                for record in cycle_records
            ],
            "cycle_evidence_inventory": proof_inventory,
        },
    )

    captured_logs = log_capture.read_entries(run)
    persisted_proof_manifest = json.loads(proof_manifest_path.read_text(encoding="utf-8"))

    assert run_summary.last_stable_cycle == "cycle-0010"
    assert len(run_summary.cycle_summaries) == 10
    assert all(cycle.gate_decision == "accepted" for cycle in run_summary.cycle_summaries)
    assert run_summary.reproducibility_manifest.outer_repo_commit_sha == "a" * 40
    assert run_summary.reproducibility_manifest.container_image_digest == "sha256:" + ("b" * 64)
    assert run_summary.reproducibility_manifest.runtime_profile_sha256 == "c" * 64
    assert run_summary.reproducibility_manifest.command_catalog_sha256 == "d" * 64
    assert len(captured_logs) == 20
    assert [entry.sequence for entry in captured_logs] == list(range(1, 21))
    assert {entry.cycle_id for entry in captured_logs} == {f"cycle-{index:04d}" for index in range(1, 11)}
    assert persisted_proof_manifest["proof_clearance_status"] == "cleared"
    assert len(persisted_proof_manifest["canonical_cycle_record_refs"]) == 10
    assert len(persisted_proof_manifest["cycle_evidence_inventory"]) == 10
    assert Path(persisted_proof_manifest["run_manifest_ref"]).exists()
    assert Path(persisted_proof_manifest["run_record_ref"]).exists()
    assert all(Path(path).exists() for path in persisted_proof_manifest["canonical_cycle_record_refs"])
    assert Path(persisted_proof_manifest["cycle_evidence_inventory"][0]["full_log_bundle_ref"]).exists()
    assert persisted_proof_manifest["cycle_evidence_inventory"][0]["audit_locator"] == str(
        ledger.ledger_path_for_scope(make_command_scope(run))
    )
    assert len(persisted_proof_manifest["cycle_evidence_inventory"][0]["audit_event_ids"]) == 2

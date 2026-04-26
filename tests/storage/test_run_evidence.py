from __future__ import annotations

import json
from uuid import uuid4

import pytest

from live_ai_terrarium.audit.ledger import AuditEvent, AuditLedger
from live_ai_terrarium.control.commands import CommandEnvelope, CommandScope
from live_ai_terrarium.contracts.records import ArtifactRef, HashOrSnapshot
from live_ai_terrarium.storage.log_capture import LogCaptureBroker, LogEntryInput
from live_ai_terrarium.storage.paths import CycleScope, RunScope, StoragePaths
from live_ai_terrarium.storage.run_evidence import EvidenceLookupError, RunEvidenceStore


def make_run_scope() -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id="run-stability-baseline",
    )


def make_cycle_scope(run: RunScope | None = None) -> CycleScope:
    return CycleScope(run=run or make_run_scope(), cycle_id="cycle-0001")


def make_store(tmp_path) -> tuple[StoragePaths, RunEvidenceStore, LogCaptureBroker]:
    storage = StoragePaths.from_local_appdata(tmp_path / "LocalAppData")
    return storage, RunEvidenceStore(storage), LogCaptureBroker(storage)


def make_hash_snapshot(seed: str) -> HashOrSnapshot:
    return HashOrSnapshot(sha256=seed * 64)


def make_audit_ref(name: str) -> ArtifactRef:
    return ArtifactRef(uuid=uuid4(), locator=f"audit/{name}.json")


def make_command_scope(run: RunScope) -> CommandScope:
    return CommandScope(
        project_id=run.project_id,
        glass_box_id=run.glassbox_id,
        experiment_id=run.experiment_id,
        run_id=run.run_id,
    )


def append_audit_refs(storage: StoragePaths, run: RunScope, *, cycle_id: str) -> list[ArtifactRef]:
    ledger = AuditLedger(storage)
    scope = make_command_scope(run)
    command = CommandEnvelope(action="pause", scope=scope, idempotency_key="pause-once", surface="cli")
    requested = ledger.append(
        AuditEvent(
            command_id=command.command_id,
            action=command.action,
            event_type="command.requested",
            occurred_at="2026-04-26T10:00:00Z",
            actor_id="operator-local",
            actor_role="operator",
            scope=scope,
        )
    )
    started = ledger.append(
        AuditEvent(
            command_id=command.command_id,
            action=command.action,
            event_type="command.started",
            occurred_at="2026-04-26T10:00:01Z",
            actor_id="operator-local",
            actor_role="operator",
            scope=scope,
            cycle_id=cycle_id,
        )
    )
    ledger_locator = str(ledger.ledger_path_for_scope(scope))
    return [
        ArtifactRef(uuid=requested.event_id, locator=ledger_locator),
        ArtifactRef(uuid=started.event_id, locator=ledger_locator),
    ]


def test_manifest_must_exist_before_cycle_one_linkage_and_is_immutable(tmp_path) -> None:
    storage, evidence, log_capture = make_store(tmp_path)
    run_scope = make_run_scope()
    cycle_scope = make_cycle_scope(run_scope)
    receipt = log_capture.append_entries(
        run_scope,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:00:00Z",
                broker_name="orchestrator",
                stream="stdout",
                message="cycle boot",
                cycle_id=cycle_scope.cycle_id,
            )
        ],
    )

    with pytest.raises(EvidenceLookupError, match="run-start reproducibility manifest"):
        evidence.link_cycle_to_audit(
            cycle_scope,
            audit_event_refs=[make_audit_ref("requested")],
            full_log_bundle_ref=receipt.bundle_ref,
            log_sequence_start=receipt.first_sequence,
            log_sequence_end=receipt.last_sequence,
        )

    manifest = evidence.create_run_manifest(
        run_scope,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-025",
        seed=7,
        limits={"max_cycles": 10, "max_cpu_percent": 90},
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        runtime_profile=make_hash_snapshot("c"),
        command_catalog=make_hash_snapshot("d"),
        supplemental_labels={"release_tag": "v1.0.1", "image_name": "glassbox:v1"},
    )

    assert storage.run_manifest_file(run_scope).exists()
    assert manifest.created_at == "2026-04-26T09:59:59Z"
    assert manifest.run_id == run_scope.run_id

    with pytest.raises(FileExistsError, match="run-start reproducibility manifest"):
        evidence.create_run_manifest(
            run_scope,
            created_at="2026-04-26T10:00:00Z",
            task_identity="LAT-025-retry",
            seed=8,
            limits={"max_cycles": 5},
            model_version="gpt-5.4-retry",
            outer_repo_commit_sha="1" * 40,
            container_image_digest="sha256:" + ("2" * 64),
            runtime_profile=make_hash_snapshot("e"),
            command_catalog=make_hash_snapshot("f"),
        )


def test_manifest_captures_required_immutable_build_identity_and_labels(tmp_path) -> None:
    _, evidence, _ = make_store(tmp_path)
    run_scope = make_run_scope()

    evidence.create_run_manifest(
        run_scope,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-025",
        seed=11,
        limits={"max_cycles": 10, "timeout_seconds": 60},
        model_version="gpt-5.4",
        outer_repo_commit_sha="0" * 40,
        container_image_digest="sha256:" + ("f" * 64),
        runtime_profile=HashOrSnapshot(snapshot_ref=ArtifactRef(uuid=uuid4(), locator="runtime/profile.yaml")),
        command_catalog=HashOrSnapshot(snapshot_ref=ArtifactRef(uuid=uuid4(), locator="security/command-specs.yaml")),
        supplemental_labels={"release_tag": "v1.0.1", "image_name": "glassbox:v1"},
    )

    loaded = evidence.read_run_manifest(run_scope)

    assert loaded.outer_repo_commit_sha == "0" * 40
    assert loaded.container_image_digest == "sha256:" + ("f" * 64)
    assert loaded.task_identity == "LAT-025"
    assert loaded.seed == 11
    assert loaded.limits.values == {"max_cycles": 10, "timeout_seconds": 60}
    assert loaded.model_version == "gpt-5.4"
    assert loaded.runtime_profile.snapshot_ref is not None
    assert loaded.command_catalog.snapshot_ref is not None
    assert loaded.supplemental_labels == {
        "release_tag": "v1.0.1",
        "image_name": "glassbox:v1",
    }


def test_log_capture_appends_brokered_entries_without_overwriting_history(tmp_path) -> None:
    storage, _, log_capture = make_store(tmp_path)
    run_scope = make_run_scope()

    first = log_capture.append_entries(
        run_scope,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:00:00Z",
                broker_name="orchestrator",
                stream="stdout",
                message="alpha",
                cycle_id="cycle-0001",
            ),
            LogEntryInput(
                occurred_at="2026-04-26T10:00:01Z",
                broker_name="orchestrator",
                stream="stdout",
                message="beta",
                cycle_id="cycle-0001",
            ),
        ],
    )
    second = log_capture.append_entries(
        run_scope,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:00:02Z",
                broker_name="gateway",
                stream="stderr",
                message="gamma",
                cycle_id="cycle-0001",
            )
        ],
    )

    assert first.first_sequence == 1
    assert first.last_sequence == 2
    assert second.first_sequence == 3
    assert second.last_sequence == 3
    assert first.bundle_ref == second.bundle_ref

    lines = log_capture.read_entries(run_scope)
    assert [line.sequence for line in lines] == [1, 2, 3]
    assert [line.message for line in lines] == ["alpha", "beta", "gamma"]

    raw_lines = storage.state_root.joinpath(
        "logs",
        "projects",
        run_scope.project_id,
        "glassboxes",
        run_scope.glassbox_id,
        "experiments",
        run_scope.experiment_id,
        "runs",
        run_scope.run_id,
        "brokered",
        "full-log-bundle.jsonl",
    ).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["sequence"] for line in raw_lines] == [1, 2, 3]


def test_cycle_to_audit_linkage_resolves_audit_and_log_bundle_refs(tmp_path) -> None:
    storage, evidence, log_capture = make_store(tmp_path)
    run_scope = make_run_scope()
    cycle_scope = make_cycle_scope(run_scope)

    evidence.create_run_manifest(
        run_scope,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-025",
        seed=13,
        limits={"max_cycles": 10},
        model_version="gpt-5.4",
        outer_repo_commit_sha="1" * 40,
        container_image_digest="sha256:" + ("2" * 64),
        runtime_profile=make_hash_snapshot("3"),
        command_catalog=make_hash_snapshot("4"),
    )
    receipt = log_capture.append_entries(
        run_scope,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:00:00Z",
                broker_name="orchestrator",
                stream="stdout",
                message="cycle log",
                cycle_id=cycle_scope.cycle_id,
            )
        ],
    )
    audit_refs = append_audit_refs(storage, run_scope, cycle_id=cycle_scope.cycle_id)

    linked = evidence.link_cycle_to_audit(
        cycle_scope,
        audit_event_refs=audit_refs,
        full_log_bundle_ref=receipt.bundle_ref,
        log_sequence_start=receipt.first_sequence,
        log_sequence_end=receipt.last_sequence,
    )
    proof_inputs = evidence.lookup_cycle_proof_evidence(cycle_scope)

    assert linked.audit_event_refs == audit_refs
    assert linked.full_log_bundle_ref == receipt.bundle_ref
    assert linked.log_sequence_start == 1
    assert linked.log_sequence_end == 1
    assert proof_inputs.manifest.run_id == run_scope.run_id
    assert proof_inputs.cycle_link.cycle_id == cycle_scope.cycle_id
    assert proof_inputs.full_log_bundle_ref == receipt.bundle_ref
    assert proof_inputs.audit_event_refs == audit_refs


def test_proof_consumer_lookup_fails_closed_when_audit_chain_is_tampered(tmp_path) -> None:
    storage, evidence, log_capture = make_store(tmp_path)
    run_scope = make_run_scope()
    cycle_scope = make_cycle_scope(run_scope)

    evidence.create_run_manifest(
        run_scope,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-025",
        seed=14,
        limits={"max_cycles": 10},
        model_version="gpt-5.4",
        outer_repo_commit_sha="2" * 40,
        container_image_digest="sha256:" + ("3" * 64),
        runtime_profile=make_hash_snapshot("4"),
        command_catalog=make_hash_snapshot("5"),
    )
    receipt = log_capture.append_entries(
        run_scope,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:00:00Z",
                broker_name="orchestrator",
                stream="stdout",
                message="cycle log",
                cycle_id=cycle_scope.cycle_id,
            )
        ],
    )
    audit_refs = append_audit_refs(storage, run_scope, cycle_id=cycle_scope.cycle_id)

    evidence.link_cycle_to_audit(
        cycle_scope,
        audit_event_refs=audit_refs,
        full_log_bundle_ref=receipt.bundle_ref,
        log_sequence_start=receipt.first_sequence,
        log_sequence_end=receipt.last_sequence,
    )

    ledger_path = AuditLedger(storage).ledger_path_for_scope(make_command_scope(run_scope))
    tampered = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    tampered[0]["actor_role"] = "tampered"
    ledger_path.write_text("\n".join(json.dumps(entry, sort_keys=True) for entry in tampered) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceLookupError, match="audit chain"):
        evidence.lookup_cycle_proof_evidence(cycle_scope)


def test_proof_consumer_lookup_fails_closed_when_audit_ref_does_not_resolve(tmp_path) -> None:
    _, evidence, log_capture = make_store(tmp_path)
    run_scope = make_run_scope()
    cycle_scope = make_cycle_scope(run_scope)

    evidence.create_run_manifest(
        run_scope,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-025",
        seed=15,
        limits={"max_cycles": 10},
        model_version="gpt-5.4",
        outer_repo_commit_sha="3" * 40,
        container_image_digest="sha256:" + ("4" * 64),
        runtime_profile=make_hash_snapshot("5"),
        command_catalog=make_hash_snapshot("6"),
    )
    receipt = log_capture.append_entries(
        run_scope,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:00:00Z",
                broker_name="orchestrator",
                stream="stdout",
                message="cycle log",
                cycle_id=cycle_scope.cycle_id,
            )
        ],
    )

    evidence.link_cycle_to_audit(
        cycle_scope,
        audit_event_refs=[make_audit_ref("unresolved")],
        full_log_bundle_ref=receipt.bundle_ref,
        log_sequence_start=receipt.first_sequence,
        log_sequence_end=receipt.last_sequence,
    )

    with pytest.raises(EvidenceLookupError, match="audit ref"):
        evidence.lookup_cycle_proof_evidence(cycle_scope)


def test_proof_consumer_lookups_fail_closed_for_missing_evidence(tmp_path) -> None:
    storage, evidence, log_capture = make_store(tmp_path)
    run_scope = make_run_scope()
    cycle_scope = make_cycle_scope(run_scope)

    with pytest.raises(EvidenceLookupError, match="run-start reproducibility manifest"):
        evidence.read_run_manifest(run_scope)

    evidence.create_run_manifest(
        run_scope,
        created_at="2026-04-26T09:59:59Z",
        task_identity="LAT-025",
        seed=21,
        limits={"max_cycles": 10},
        model_version="gpt-5.4",
        outer_repo_commit_sha="5" * 40,
        container_image_digest="sha256:" + ("6" * 64),
        runtime_profile=make_hash_snapshot("7"),
        command_catalog=make_hash_snapshot("8"),
    )

    with pytest.raises(EvidenceLookupError, match="cycle-to-audit linkage"):
        evidence.lookup_cycle_proof_evidence(cycle_scope)

    receipt = log_capture.append_entries(
        run_scope,
        entries=[
            LogEntryInput(
                occurred_at="2026-04-26T10:00:00Z",
                broker_name="orchestrator",
                stream="stdout",
                message="cycle log",
                cycle_id=cycle_scope.cycle_id,
            )
        ],
    )
    evidence.link_cycle_to_audit(
        cycle_scope,
        audit_event_refs=append_audit_refs(storage, run_scope, cycle_id=cycle_scope.cycle_id),
        full_log_bundle_ref=receipt.bundle_ref,
        log_sequence_start=receipt.first_sequence,
        log_sequence_end=receipt.last_sequence,
    )

    bundle_path = log_capture.bundle_path(run_scope)
    bundle_path.unlink()

    with pytest.raises(EvidenceLookupError, match="full-log bundle"):
        evidence.lookup_cycle_proof_evidence(cycle_scope)
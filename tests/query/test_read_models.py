from __future__ import annotations

from pathlib import Path
from uuid import uuid4

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
from live_ai_terrarium.control.commands import CommandScope, OBSERVATION_ONLY_MODE
from live_ai_terrarium.orchestrator.runtime import LifecycleReceipt
from live_ai_terrarium.query.service import QueryService
from live_ai_terrarium.storage.paths import RunScope
from live_ai_terrarium.storage.run_evidence import CycleAuditLink, RunStartManifest


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
        task_identity="LAT-024",
        seed=7,
        limits=RunLimits(values={"max_cycles": 10, "max_cpu_percent": 90}),
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        release_tag="v1.0.0",
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
        task_identity="LAT-024",
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
        task_identity="LAT-024",
        seed=7,
        limits=RunLimits(values={"max_cycles": 10, "max_cpu_percent": 90}),
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        runtime_profile=HashOrSnapshot(snapshot_ref=make_artifact_ref("security/runtime-profile.yaml")),
        command_catalog=HashOrSnapshot(snapshot_ref=make_artifact_ref("security/command-specs.yaml")),
        supplemental_labels={"release_tag": "v1.0.0", "image_name": "glassbox:v1"},
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
    receipt_id=None,
    approval_id=None,
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


def test_query_service_builds_run_summary_and_cycle_detail_from_canonical_inputs() -> None:
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
            details={"mode_context": OBSERVATION_ONLY_MODE},
        ),
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.approval_requested",
            occurred_at="2026-04-26T10:00:01Z",
            actor_id="observer-1",
            approval_id=approval_id,
            details={"mode_context": OBSERVATION_ONLY_MODE},
        ),
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.approved",
            occurred_at="2026-04-26T10:00:02Z",
            actor_id="operator-1",
            approval_id=approval_id,
            receipt_id=mode_switch_receipt_id,
            details={"mode_context": OBSERVATION_ONLY_MODE},
        ),
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.completed",
            occurred_at="2026-04-26T10:00:03Z",
            actor_id="operator-1",
            receipt_id=mode_switch_receipt_id,
            details={"mode_context": OBSERVATION_ONLY_MODE, "target_mode": "control-enabled"},
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
    service = QueryService()

    run_summary = service.build_run_summary(
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
            "incident-syntax-failure": {
                "ordered_steps": ["pause", "snapshot", "rollback", "report"],
                "recovery": {
                    "outcome": "rolled back to last accepted stable cycle cycle-0001",
                    "rollback_target": "cycle-0001",
                    "restore_manifest": "snapshots/cycles/cycle-0001/manifest.json",
                },
                "branch": {
                    "branch_name": "branch-syntax-failure-cycle-0002",
                    "branch_ref": "mirrors/branches/branch-syntax-failure-cycle-0002.json",
                },
                "full_log_refs": ["logs/cycle-0002/full-log-bundle.jsonl"],
            }
        },
    )
    cycle_detail = service.build_cycle_detail(
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
            "recovery": {
                "outcome": "rolled back to last accepted stable cycle cycle-0001",
                "rollback_target": "cycle-0001",
                "restore_manifest": "snapshots/cycles/cycle-0001/manifest.json",
            },
            "branch": {
                "branch_name": "branch-syntax-failure-cycle-0002",
                "branch_ref": "mirrors/branches/branch-syntax-failure-cycle-0002.json",
            },
            "full_log_refs": ["logs/cycle-0002/full-log-bundle.jsonl"],
        },
    )

    assert run_summary.run_id == run.run_id
    assert run_summary.current_mode == "control-enabled"
    assert run_summary.active_mode_switch_receipt is not None
    assert run_summary.active_mode_switch_receipt.target_mode == "control-enabled"
    assert run_summary.available_actions == (
        "observe",
        "mode switch",
        "pause",
        "resume",
        "branch",
        "clone",
        "reset",
        "rollback",
    )
    assert run_summary.deny_reason_by_action == {}
    assert run_summary.last_stable_cycle == "cycle-0001"
    assert run_summary.rollback_target == "cycle-0001"
    assert run_summary.incident_state == "open"
    assert run_summary.reproducibility_manifest.release_tag == "v1.0.0"
    assert run_summary.reproducibility_manifest.image_name == "glassbox:v1"
    assert run_summary.reproducibility_manifest.runtime_profile_locator == "security/runtime-profile.yaml"
    assert run_summary.full_log_bundle_refs == (
        "logs/full-log-bundle.jsonl",
        "logs/cycle-0001/full-log-bundle.jsonl",
        "logs/cycle-0002/full-log-bundle.jsonl",
    )
    assert [summary.cycle_id for summary in run_summary.cycle_summaries] == ["cycle-0001", "cycle-0002"]
    assert run_summary.cycle_summaries[0].log_sequence_range == (11, 19)
    assert run_summary.cycle_summaries[1].has_incident is True
    assert run_summary.audit_status.latest_command_receipts["mode switch"].status == "completed"
    assert run_summary.audit_status.latest_command_receipts["rollback"].target_cycle_id == "cycle-0001"

    assert cycle_detail.cycle_id == "cycle-0002"
    assert cycle_detail.current_mode == "control-enabled"
    assert cycle_detail.observation_mode_state == "mode-switch active"
    assert cycle_detail.gate_decision == "rejected"
    assert cycle_detail.approval_status == "approved"
    assert cycle_detail.snapshot_refs == (
        "snapshots/cycles/cycle-0002/manifest.json",
        "snapshots/full/snapshot-cycle-0002/manifest.json",
    )
    assert cycle_detail.full_log_bundle_ref == "logs/cycle-0002/full-log-bundle.jsonl"
    assert cycle_detail.audit_timeline[-1].status == "completed"
    assert cycle_detail.audit_timeline[-1].action == "rollback"
    assert cycle_detail.reversibility.last_stable_cycle == "cycle-0001"
    assert cycle_detail.reversibility.rollback_target == "cycle-0001"
    assert cycle_detail.reversibility.recovery_outcome == "rolled back to last accepted stable cycle cycle-0001"
    assert cycle_detail.reversibility.branch_ref == "mirrors/branches/branch-syntax-failure-cycle-0002.json"
    assert cycle_detail.reversibility.restore_manifest_ref == "snapshots/cycles/cycle-0001/manifest.json"
    assert cycle_detail.reproducibility_manifest.command_catalog_locator == "security/command-specs.yaml"


def test_query_service_keeps_control_actions_blocked_without_active_mode_switch_receipt() -> None:
    run = make_run_scope(run_id="run-observe-only")
    run_record = make_run_record(run)
    cycle = make_cycle_record(run, cycle_id="cycle-0001", score=0.94, decision="accepted", test_result="passed")
    manifest = make_manifest(run)
    audit_entries = [
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.requested",
            occurred_at="2026-04-26T11:00:00Z",
            actor_id="observer-2",
            details={"mode_context": OBSERVATION_ONLY_MODE},
        ),
        make_audit_entry(
            run,
            action="mode switch",
            event_type="command.rejected",
            occurred_at="2026-04-26T11:00:05Z",
            actor_id="approver-2",
            details={"reason": "operator review denied control unlock"},
        ),
    ]
    service = QueryService()

    summary = service.build_run_summary(
        run_record=run_record,
        cycle_records=[cycle],
        audit_events=audit_entries,
        lifecycle_receipt=LifecycleReceipt(
            action="resume",
            run=run,
            lifecycle_state="active",
            current_mode=OBSERVATION_ONLY_MODE,
        ),
        manifest=manifest,
        cycle_links={"cycle-0001": make_cycle_link(run, cycle_id="cycle-0001")},
        incident_records=[],
        recovery_reports={},
    )

    assert summary.current_mode == OBSERVATION_ONLY_MODE
    assert summary.active_mode_switch_receipt is None
    assert summary.available_actions == ("observe", "mode switch")
    assert summary.deny_reason_by_action == {
        "pause": "Active mode-switch receipt required for this scope.",
        "resume": "Active mode-switch receipt required for this scope.",
        "branch": "Active mode-switch receipt required for this scope.",
        "clone": "Active mode-switch receipt required for this scope.",
        "reset": "Active mode-switch receipt required for this scope.",
        "rollback": "Active mode-switch receipt required for this scope.",
    }
    assert summary.audit_status.latest_command_receipts["mode switch"].status == "rejected"
    assert summary.observation_mode_state == "observation-only"
    assert summary.incident_state == "clear"
    assert summary.last_stable_cycle == "cycle-0001"
    assert summary.rollback_target == "cycle-0001"
    assert summary.full_log_bundle_refs == (
        "logs/full-log-bundle.jsonl",
        "logs/cycle-0001/full-log-bundle.jsonl",
    )


def test_query_service_only_surfaces_host_controlled_evidence_refs() -> None:
    run = make_run_scope(run_id="run-host-evidence-only")
    run_record = make_run_record(run)
    cycle = make_cycle_record(run, cycle_id="cycle-0003", score=0.88, decision="accepted", test_result="passed")
    manifest = make_manifest(run)
    cycle_link = make_cycle_link(run, cycle_id="cycle-0003")
    service = QueryService()

    detail = service.build_cycle_detail(
        cycle_record=cycle,
        run_record=run_record,
        audit_events=[],
        lifecycle_receipt=LifecycleReceipt(
            action="resume",
            run=run,
            lifecycle_state="paused",
            current_mode=OBSERVATION_ONLY_MODE,
        ),
        manifest=manifest,
        cycle_link=cycle_link,
        incident_record=None,
        recovery_report=None,
    )

    expected_prefixes = ("logs/", "snapshots/", "audit/", "security/")
    evidence_refs = (
        detail.full_log_bundle_ref,
        *detail.snapshot_refs,
        *detail.audit_event_refs,
        detail.reproducibility_manifest.runtime_profile_locator,
        detail.reproducibility_manifest.command_catalog_locator,
    )

    assert all(not Path(ref).is_absolute() for ref in evidence_refs)
    assert all(ref.startswith(expected_prefixes) for ref in evidence_refs)
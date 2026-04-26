from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from live_ai_terrarium.contracts.ids import (  # noqa: E402
    AgentId,
    CycleId,
    ExperimentId,
    GlassBoxId,
    IncidentId,
    MutationId,
    ProjectId,
    RunId,
)
from live_ai_terrarium.contracts.records import (  # noqa: E402
    AnnotationRecord,
    ArtifactRef,
    CycleRecord,
    HashOrSnapshot,
    IncidentRecord,
    ResourceUsage,
    RunLimits,
    RunRecord,
    TokenUsage,
)


PROJECT_UUID = UUID("11111111-1111-4111-8111-111111111111")
GLASS_BOX_UUID = UUID("22222222-2222-4222-8222-222222222222")
EXPERIMENT_UUID = UUID("33333333-3333-4333-8333-333333333333")
RUN_UUID = UUID("44444444-4444-4444-8444-444444444444")
CYCLE_UUID = UUID("55555555-5555-4555-8555-555555555555")
MUTATION_UUID = UUID("66666666-6666-4666-8666-666666666666")
INCIDENT_UUID = UUID("77777777-7777-4777-8777-777777777777")
AGENT_UUID = UUID("88888888-8888-4888-8888-888888888888")
ANNOTATION_UUID = UUID("99999999-9999-4999-8999-999999999999")


def make_ids() -> dict[str, object]:
    return {
        "project_id": ProjectId.from_slug("live-ai-terrarium", uuid=PROJECT_UUID, label="Live AI Terrarium"),
        "glass_box_id": GlassBoxId.from_slug("local-dev", uuid=GLASS_BOX_UUID, label="Local Dev"),
        "experiment_id": ExperimentId.from_slug("proof-loop", uuid=EXPERIMENT_UUID),
        "run_id": RunId.from_slug("stability-baseline", uuid=RUN_UUID),
        "cycle_id": CycleId.from_slug("0001", uuid=CYCLE_UUID),
        "mutation_id": MutationId.from_slug("0001", uuid=MUTATION_UUID),
        "incident_id": IncidentId.from_slug("resource-overuse", uuid=INCIDENT_UUID),
        "agent_id": AgentId.from_slug("observer-main", uuid=AGENT_UUID),
    }


def make_artifact(locator: str, seed: str) -> ArtifactRef:
    return ArtifactRef(uuid=UUID(seed), locator=locator)


def dump_payload(model: object) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def test_readable_ids_use_fixed_prefixes_and_store_uuid() -> None:
    ids = make_ids()

    assert ids["project_id"].readable_id == "project-live-ai-terrarium"
    assert ids["glass_box_id"].readable_id == "gb-local-dev"
    assert ids["experiment_id"].readable_id == "exp-proof-loop"
    assert ids["run_id"].readable_id == "run-stability-baseline"
    assert ids["cycle_id"].readable_id == "cycle-0001"
    assert ids["mutation_id"].readable_id == "mutation-0001"
    assert ids["incident_id"].readable_id == "incident-resource-overuse"
    assert ids["agent_id"].readable_id == "agent-observer-main"
    assert ids["project_id"].uuid == PROJECT_UUID

    with pytest.raises(ValidationError):
        ExperimentId(uuid=EXPERIMENT_UUID, readable_id="project-proof-loop")

    with pytest.raises(ValidationError):
        MutationId(uuid=MUTATION_UUID, readable_id="mutation-Bad-Case")


def test_run_record_requires_reproducibility_inputs_and_supports_stable_refs() -> None:
    ids = make_ids()
    audit_ref = make_artifact("audit/events/0001", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    bundle_ref = make_artifact("logs/bundles/run-0001", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    record = RunRecord(
        project_id=ids["project_id"],
        glass_box_id=ids["glass_box_id"],
        experiment_id=ids["experiment_id"],
        run_id=ids["run_id"],
        task_identity="ten-stable-cycles",
        seed=7,
        limits=RunLimits(values={"max_cycles": 10, "max_runtime_seconds": 1800}),
        model_version="gpt-5.4",
        outer_repo_commit_sha="a" * 40,
        container_image_digest="sha256:" + ("b" * 64),
        release_tag="milestone/v1-contracts",
        image_name_label="live-ai-terrarium:dev",
        runtime_profile=HashOrSnapshot(sha256="c" * 64),
        command_catalog=HashOrSnapshot(
            snapshot_ref=make_artifact(
                "commands/catalog/current",
                "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            )
        ),
        audit_event_refs=[audit_ref],
        full_log_bundle_ref=bundle_ref,
    )

    assert record.run_id.uuid == RUN_UUID
    assert record.runtime_profile.sha256 == "c" * 64
    assert record.full_log_bundle_ref.locator == "logs/bundles/run-0001"
    assert record.audit_event_refs[0].locator == "audit/events/0001"

    payload = dump_payload(record)
    assert payload["run_id"]["uuid"] == str(RUN_UUID)

    bad_payload = dump_payload(record)
    del bad_payload["outer_repo_commit_sha"]
    with pytest.raises(ValidationError):
        RunRecord(**bad_payload)

    with pytest.raises(ValidationError):
        HashOrSnapshot()


def test_cycle_record_requires_proof_signals_and_artifact_links() -> None:
    ids = make_ids()
    record = CycleRecord(
        project_id=ids["project_id"],
        glass_box_id=ids["glass_box_id"],
        experiment_id=ids["experiment_id"],
        run_id=ids["run_id"],
        cycle_id=ids["cycle_id"],
        mutation_id=ids["mutation_id"],
        task_identity="repair contract test imports",
        diff_summary="1 file added, 2 files changed",
        gate_decision="accepted",
        score=0.97,
        test_result="passed",
        error_summary=None,
        model_identity="gpt-5.4",
        prompt_ref=make_artifact("prompts/cycle-0001.md", "dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        token_usage=TokenUsage(input_tokens=144, output_tokens=89, total_tokens=233),
        latency_ms=1200,
        resources=ResourceUsage(cpu_percent=68.5, ram_mb=512, disk_mb=2048),
        snapshot_refs=[
            make_artifact("snapshots/cycle-0001", "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
        ],
        audit_event_refs=[
            make_artifact("audit/events/0002", "ffffffff-ffff-4fff-8fff-ffffffffffff")
        ],
        full_log_bundle_ref=make_artifact(
            "logs/bundles/cycle-0001",
            "12121212-1212-4212-8212-121212121212",
        ),
    )

    assert record.cycle_id.readable_id == "cycle-0001"
    assert record.resources.disk_mb == 2048
    assert record.full_log_bundle_ref.locator == "logs/bundles/cycle-0001"

    payload = dump_payload(record)
    payload.pop("diff_summary")
    with pytest.raises(ValidationError):
        CycleRecord(**payload)


def test_incident_and_annotation_records_link_by_canonical_ids() -> None:
    ids = make_ids()

    incident = IncidentRecord(
        incident_id=ids["incident_id"],
        run_id=ids["run_id"],
        cycle_id=ids["cycle_id"],
        stop_condition_type="resource overuse",
        trigger_detail="CPU stayed above 90 percent of budget for 31 seconds.",
        snapshot_ref=make_artifact("snapshots/cycle-0001", "13131313-1313-4313-8313-131313131313"),
        branch_ref=make_artifact("branches/resource-overuse", "14141414-1414-4414-8414-141414141414"),
        recovery_outcome="rolled back to last accepted stable cycle",
        incident_report_ref=make_artifact(
            "incidents/resource-overuse/report.md",
            "15151515-1515-4515-8515-151515151515",
        ),
    )

    annotation = AnnotationRecord(
        uuid=ANNOTATION_UUID,
        run_id=ids["run_id"],
        cycle_id=ids["cycle_id"],
        annotator_agent_id=ids["agent_id"],
        annotation="Investigate CPU spike before resuming non-observation mode.",
        tags=["resource-overuse", "triage"],
    )

    assert incident.run_id.uuid == annotation.run_id.uuid
    assert incident.cycle_id.readable_id == annotation.cycle_id.readable_id
    assert annotation.annotator_agent_id.readable_id == "agent-observer-main"

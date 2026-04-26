from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

from live_ai_terrarium.contracts.ids import CycleId, IncidentId, RunId
from live_ai_terrarium.contracts.records import ArtifactRef, IncidentRecord, StopConditionType
from live_ai_terrarium.orchestrator.runtime import LifecycleReceipt
from live_ai_terrarium.orchestrator.service import HostOrchestratorService
from live_ai_terrarium.recovery.snapshots import RestorePlan, SnapshotCapture, SnapshotService
from live_ai_terrarium.storage.filesystem import HostFilesystem
from live_ai_terrarium.storage.paths import CycleScope, IncidentScope


def _stable_uuid(key: str) -> UUID:
    return uuid5(NAMESPACE_URL, key)


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def _normalize_readable_id(value: str, *, prefix: str) -> str:
    text = _require_text(value, field_name=prefix)
    return text if text.startswith(f"{prefix}-") else f"{prefix}-{text}"


def _artifact_ref(locator: str) -> ArtifactRef:
    return ArtifactRef(uuid=_stable_uuid(f"artifact:{locator}"), locator=locator)


@dataclass(frozen=True)
class RecoveryOutcome:
    ordered_steps: tuple[str, ...]
    pause_receipt: LifecycleReceipt
    cycle_snapshot: SnapshotCapture
    full_snapshot: SnapshotCapture
    incident_record: IncidentRecord
    incident_record_path: Path
    incident_report_path: Path
    branch_ref: ArtifactRef | None = None
    rollback_receipt: LifecycleReceipt | None = None
    restore_receipt: LifecycleReceipt | None = None
    restore_plan: RestorePlan | None = None


class RecoveryController:
    def __init__(
        self,
        *,
        orchestrator: HostOrchestratorService,
        snapshots: SnapshotService,
        filesystem: HostFilesystem | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._snapshots = snapshots
        self._storage_paths = snapshots.storage_paths
        self._filesystem = filesystem or HostFilesystem(self._storage_paths)

    def branch_and_continue(
        self,
        *,
        cycle_scope: CycleScope,
        workspace_dir: str | Path,
        incident_id: str,
        branch_name: str,
        stop_condition_type: StopConditionType,
        trigger_detail: str,
        full_log_refs: Sequence[str] = (),
    ) -> RecoveryOutcome:
        pause_receipt = self._orchestrator.pause(cycle_scope.run)
        cycle_snapshot, full_snapshot = self._capture_failure_snapshots(
            cycle_scope=cycle_scope,
            workspace_dir=workspace_dir,
            incident_id=incident_id,
        )
        branch_ref = self._write_branch_evidence(
            cycle_scope=cycle_scope,
            branch_name=branch_name,
            cycle_snapshot=cycle_snapshot,
            full_snapshot=full_snapshot,
            full_log_refs=full_log_refs,
        )
        incident_record, incident_record_path, incident_report_path = self._write_incident_bundle(
            ordered_steps=("pause", "snapshot", "branch-and-continue", "report"),
            cycle_scope=cycle_scope,
            incident_id=incident_id,
            stop_condition_type=stop_condition_type,
            trigger_detail=trigger_detail,
            cycle_snapshot=cycle_snapshot,
            full_snapshot=full_snapshot,
            branch_ref=branch_ref,
            recovery_outcome="branched and continued from failing state",
            rollback_target=None,
            restore_manifest=None,
            full_log_refs=full_log_refs,
        )
        return RecoveryOutcome(
            ordered_steps=("pause", "snapshot", "branch-and-continue", "report"),
            pause_receipt=pause_receipt,
            cycle_snapshot=cycle_snapshot,
            full_snapshot=full_snapshot,
            incident_record=incident_record,
            incident_record_path=incident_record_path,
            incident_report_path=incident_report_path,
            branch_ref=branch_ref,
        )

    def manual_rollback(
        self,
        *,
        cycle_scope: CycleScope,
        workspace_dir: str | Path,
        incident_id: str,
        stop_condition_type: StopConditionType,
        trigger_detail: str,
        last_accepted_cycle_id: str,
        full_log_refs: Sequence[str] = (),
    ) -> RecoveryOutcome:
        pause_receipt = self._orchestrator.pause(cycle_scope.run)
        cycle_snapshot, full_snapshot = self._capture_failure_snapshots(
            cycle_scope=cycle_scope,
            workspace_dir=workspace_dir,
            incident_id=incident_id,
        )
        rollback_receipt = self._orchestrator.rollback(
            cycle_scope.run,
            target_cycle_id=_require_text(last_accepted_cycle_id, field_name="last_accepted_cycle_id"),
        )
        restore_plan = self._snapshots.restore_cycle_snapshot(
            CycleScope(run=cycle_scope.run, cycle_id=last_accepted_cycle_id),
            workspace_dir=workspace_dir,
        )
        incident_record, incident_record_path, incident_report_path = self._write_incident_bundle(
            ordered_steps=("pause", "snapshot", "rollback", "report"),
            cycle_scope=cycle_scope,
            incident_id=incident_id,
            stop_condition_type=stop_condition_type,
            trigger_detail=trigger_detail,
            cycle_snapshot=cycle_snapshot,
            full_snapshot=full_snapshot,
            branch_ref=None,
            recovery_outcome=f"rolled back to last accepted stable cycle {last_accepted_cycle_id}",
            rollback_target=last_accepted_cycle_id,
            restore_manifest=restore_plan.manifest_locator,
            full_log_refs=full_log_refs,
        )
        return RecoveryOutcome(
            ordered_steps=("pause", "snapshot", "rollback", "report"),
            pause_receipt=pause_receipt,
            cycle_snapshot=cycle_snapshot,
            full_snapshot=full_snapshot,
            incident_record=incident_record,
            incident_record_path=incident_record_path,
            incident_report_path=incident_report_path,
            rollback_receipt=rollback_receipt,
            restore_plan=restore_plan,
        )

    def kill_and_restore(
        self,
        *,
        cycle_scope: CycleScope,
        workspace_dir: str | Path,
        incident_id: str,
        stop_condition_type: StopConditionType,
        trigger_detail: str,
        restore_manifest_locator: str,
        full_log_refs: Sequence[str] = (),
    ) -> RecoveryOutcome:
        pause_receipt = self._orchestrator.pause(cycle_scope.run)
        cycle_snapshot, full_snapshot = self._capture_failure_snapshots(
            cycle_scope=cycle_scope,
            workspace_dir=workspace_dir,
            incident_id=incident_id,
        )
        restore_receipt = self._orchestrator.restore(
            cycle_scope.run,
            snapshot_id=full_snapshot.snapshot_id,
        )
        restore_plan = self._snapshots.restore_snapshot(
            restore_manifest_locator,
            workspace_dir=workspace_dir,
        )
        incident_record, incident_record_path, incident_report_path = self._write_incident_bundle(
            ordered_steps=("pause", "snapshot", "kill/restore", "report"),
            cycle_scope=cycle_scope,
            incident_id=incident_id,
            stop_condition_type=stop_condition_type,
            trigger_detail=trigger_detail,
            cycle_snapshot=cycle_snapshot,
            full_snapshot=full_snapshot,
            branch_ref=None,
            recovery_outcome=f"restored snapshot {restore_plan.snapshot_id}",
            rollback_target=None,
            restore_manifest=restore_plan.manifest_locator,
            full_log_refs=full_log_refs,
        )
        return RecoveryOutcome(
            ordered_steps=("pause", "snapshot", "kill/restore", "report"),
            pause_receipt=pause_receipt,
            cycle_snapshot=cycle_snapshot,
            full_snapshot=full_snapshot,
            incident_record=incident_record,
            incident_record_path=incident_record_path,
            incident_report_path=incident_report_path,
            restore_receipt=restore_receipt,
            restore_plan=restore_plan,
        )

    def _capture_failure_snapshots(
        self,
        *,
        cycle_scope: CycleScope,
        workspace_dir: str | Path,
        incident_id: str,
    ) -> tuple[SnapshotCapture, SnapshotCapture]:
        cycle_snapshot = self._snapshots.capture_cycle_snapshot(cycle_scope, workspace_dir=workspace_dir)
        full_snapshot = self._snapshots.capture_full_snapshot(
            cycle_scope.run,
            snapshot_id=self._full_snapshot_id(incident_id),
            workspace_dir=workspace_dir,
            reason="stop condition",
        )
        return cycle_snapshot, full_snapshot

    def _write_branch_evidence(
        self,
        *,
        cycle_scope: CycleScope,
        branch_name: str,
        cycle_snapshot: SnapshotCapture,
        full_snapshot: SnapshotCapture,
        full_log_refs: Sequence[str],
    ) -> ArtifactRef:
        mirror_path = self._storage_paths.mirror_dir(cycle_scope.run) / "branches" / f"{branch_name}.json"
        payload = {
            "uuid": str(_stable_uuid(f"branch:{cycle_scope.run.run_id}:{branch_name}")),
            "run_id": cycle_scope.run.run_id,
            "source_cycle_id": cycle_scope.cycle_id,
            "sandbox_branch_name": branch_name,
            "snapshot_ref": full_snapshot.artifact_ref.locator,
            "failing_cycle_snapshot": cycle_snapshot.artifact_ref.locator,
            "outer_repo_branch_created": False,
            "full_log_refs": list(full_log_refs),
        }
        written_path = self._filesystem.write_json(mirror_path, payload)
        return _artifact_ref(self._locator_for(written_path))

    def _write_incident_bundle(
        self,
        *,
        ordered_steps: tuple[str, ...],
        cycle_scope: CycleScope,
        incident_id: str,
        stop_condition_type: StopConditionType,
        trigger_detail: str,
        cycle_snapshot: SnapshotCapture,
        full_snapshot: SnapshotCapture,
        branch_ref: ArtifactRef | None,
        recovery_outcome: str,
        rollback_target: str | None,
        restore_manifest: str | None,
        full_log_refs: Sequence[str],
    ) -> tuple[IncidentRecord, Path, Path]:
        incident_scope = IncidentScope(run=cycle_scope.run, incident_id=incident_id)
        incident_record_path = self._storage_paths.incident_file(incident_scope)
        incident_report_path = incident_record_path.with_suffix("") / "report.json"
        report_payload = {
            "uuid": str(_stable_uuid(f"incident-report:{incident_id}")),
            "incident_id": incident_id,
            "run_id": cycle_scope.run.run_id,
            "cycle_id": cycle_scope.cycle_id,
            "stop_condition_type": stop_condition_type,
            "trigger_detail": trigger_detail,
            "ordered_steps": list(ordered_steps),
            "evidence": {
                "failing_cycle_snapshot": cycle_snapshot.artifact_ref.locator,
                "full_snapshot": full_snapshot.artifact_ref.locator,
            },
            "branch": None
            if branch_ref is None
            else {
                "branch_name": Path(branch_ref.locator).stem,
                "branch_ref": branch_ref.locator,
            },
            "recovery": {
                "outcome": recovery_outcome,
                "rollback_target": rollback_target,
                "restore_manifest": restore_manifest,
            },
            "full_log_refs": list(full_log_refs),
        }
        written_report_path = self._filesystem.write_json(incident_report_path, report_payload)
        incident_record = IncidentRecord(
            incident_id=IncidentId(
                uuid=_stable_uuid(f"incident-id:{incident_id}"),
                readable_id=_normalize_readable_id(incident_id, prefix="incident"),
            ),
            run_id=RunId(
                uuid=_stable_uuid(f"run-id:{cycle_scope.run.run_id}"),
                readable_id=_normalize_readable_id(cycle_scope.run.run_id, prefix="run"),
            ),
            cycle_id=CycleId(
                uuid=_stable_uuid(f"cycle-id:{cycle_scope.cycle_id}"),
                readable_id=_normalize_readable_id(cycle_scope.cycle_id, prefix="cycle"),
            ),
            stop_condition_type=stop_condition_type,
            trigger_detail=trigger_detail,
            snapshot_ref=full_snapshot.artifact_ref,
            branch_ref=branch_ref,
            recovery_outcome=recovery_outcome,
            incident_report_ref=_artifact_ref(self._locator_for(written_report_path)),
        )
        written_record_path = self._filesystem.write_json(
            incident_record_path,
            incident_record.model_dump(mode="json"),
        )
        return incident_record, written_record_path, written_report_path

    def _full_snapshot_id(self, incident_id: str) -> str:
        normalized = _normalize_readable_id(incident_id, prefix="incident")
        return f"snapshot-{normalized.removeprefix('incident-')}"

    def _locator_for(self, path: Path) -> str:
        relative_path = path.resolve(strict=False).relative_to(self._storage_paths.state_root.resolve(strict=False))
        return relative_path.as_posix()


__all__ = ["RecoveryController", "RecoveryOutcome"]
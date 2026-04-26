from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from live_ai_terrarium.audit.ledger import AuditLedger
from live_ai_terrarium.control.approval import ApprovalRecord, ApprovalService
from live_ai_terrarium.control.commands import (
    CommandEnvelope,
    CommandScope,
    ModeSwitchReceipt,
    OBSERVATION_ONLY_MODE,
)
from live_ai_terrarium.control.dispatcher import CommandDispatcher, DispatchContext, DispatchResult
from live_ai_terrarium.orchestrator.boundary import SANCTIONED_OUTBOX_PATH
from live_ai_terrarium.orchestrator.runtime import (
    InMemoryOrchestratorRuntime,
    LifecycleReceipt,
    OrchestratorRuntime,
    RuntimeRegistration,
    RuntimeSession,
)
from live_ai_terrarium.storage.exports import AppendOnlyExportWriter, ExportReceipt
from live_ai_terrarium.storage.paths import RunScope, StoragePaths


@dataclass(frozen=True)
class RunLogCaptureHook:
    run: RunScope
    channel: str = "run-log-capture"


@dataclass(frozen=True)
class RunEvidenceWriteHook:
    run: RunScope
    sandbox_outbox_path: PurePosixPath = SANCTIONED_OUTBOX_PATH
    channel: str = "append-only-export"


@dataclass(frozen=True)
class OrchestratorHooks:
    log_capture: RunLogCaptureHook
    evidence_write: RunEvidenceWriteHook


@dataclass(frozen=True)
class CommandExecutionReceipt:
    command: CommandEnvelope
    dispatch_result: DispatchResult
    approval_record: ApprovalRecord | None = None
    lifecycle_receipt: LifecycleReceipt | None = None


@dataclass(frozen=True)
class _AllowedCommandOutcome:
    approval_record: ApprovalRecord | None
    lifecycle_receipt: LifecycleReceipt


class HostOrchestratorService:
    def __init__(
        self,
        *,
        storage_paths: StoragePaths,
        runtime: OrchestratorRuntime | None = None,
        export_writer: AppendOnlyExportWriter | None = None,
    ) -> None:
        self._storage_paths = storage_paths
        self._runtime = runtime or InMemoryOrchestratorRuntime()
        self._export_writer = export_writer or AppendOnlyExportWriter(storage_paths)
        self._audit_ledger = AuditLedger(storage_paths)
        self._approval_service = ApprovalService(ledger=self._audit_ledger)
        self._active_mode_switch_receipts: dict[RunScope, ModeSwitchReceipt] = {}

    def register_run(
        self,
        run: RunScope,
        *,
        container_name: str,
        image_digest: str,
        workspace_volume: str,
    ) -> RuntimeSession:
        registration = RuntimeRegistration(
            run=run,
            container_name=container_name,
            image_digest=image_digest,
            workspace_volume=workspace_volume,
        )
        return self._runtime.register_run(registration)

    def describe_run(self, run: RunScope) -> RuntimeSession:
        return self._runtime.describe_run(run)

    def hooks_for(self, run: RunScope) -> OrchestratorHooks:
        self.describe_run(run)
        return OrchestratorHooks(
            log_capture=self.log_capture_hook(run),
            evidence_write=self.evidence_write_hook(run),
        )

    def log_capture_hook(self, run: RunScope) -> RunLogCaptureHook:
        self.describe_run(run)
        return RunLogCaptureHook(run=run)

    def evidence_write_hook(self, run: RunScope) -> RunEvidenceWriteHook:
        self.describe_run(run)
        return RunEvidenceWriteHook(run=run)

    def authorize_runtime_host_path(
        self,
        run: RunScope,
        *,
        candidate_path: str | Path,
    ) -> Path:
        session = self.describe_run(run)
        return session.registration.boundary_policy.validate_no_direct_host_access(
            candidate_path,
            self._storage_paths,
        )

    def execute_command(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        cycle_id: str | None = None,
        reason: str | None = None,
        approval_actor_id: str | None = None,
        approval_actor_role: str | None = None,
        approval_occurred_at: str | None = None,
        approval_reason: str | None = None,
    ) -> CommandExecutionReceipt:
        run = self._run_scope_from_command(command.scope)
        self.describe_run(run)
        outcome: _AllowedCommandOutcome | None = None

        def handler(allowed_command: CommandEnvelope) -> dict[str, object]:
            nonlocal outcome
            outcome = self._execute_allowed_command(
                allowed_command,
                actor_id=actor_id,
                actor_role=actor_role,
                occurred_at=occurred_at,
                mode_context=mode_context,
                cycle_id=cycle_id,
                reason=reason,
                approval_actor_id=approval_actor_id,
                approval_actor_role=approval_actor_role,
                approval_occurred_at=approval_occurred_at,
                approval_reason=approval_reason,
            )
            return self._handler_result(outcome)

        dispatch_result = CommandDispatcher(handler=handler).dispatch(
            command,
            self._dispatch_context(run, mode_context=mode_context),
        )

        if dispatch_result.status == "denied":
            self._approval_service.record_request(
                command,
                actor_id=actor_id,
                actor_role=actor_role,
                occurred_at=occurred_at,
                mode_context=mode_context,
                reason=reason,
                cycle_id=cycle_id,
                details={"dispatch_status": "denied", "surface": command.surface},
            )
            self._approval_service.record_failed(
                command,
                actor_id=actor_id,
                actor_role=actor_role,
                occurred_at=occurred_at,
                cycle_id=cycle_id,
                details={"deny_reason": dispatch_result.deny_reason, "surface": command.surface},
            )
            return CommandExecutionReceipt(command=command, dispatch_result=dispatch_result)

        if outcome is None:
            raise RuntimeError("dispatcher allowed a command without executing the composed handler")

        return CommandExecutionReceipt(
            command=command,
            dispatch_result=dispatch_result,
            approval_record=outcome.approval_record,
            lifecycle_receipt=outcome.lifecycle_receipt,
        )

    def mode_switch(self, run: RunScope, *, target_mode: str) -> LifecycleReceipt:
        return self._runtime.mode_switch(run, target_mode=target_mode)

    def pause(self, run: RunScope) -> LifecycleReceipt:
        return self._runtime.pause(run)

    def resume(self, run: RunScope) -> LifecycleReceipt:
        return self._runtime.resume(run)

    def reset(self, run: RunScope, *, reason: str | None = None) -> LifecycleReceipt:
        return self._runtime.reset(run, reason=reason)

    def clone(self, run: RunScope, *, clone_run: RunScope) -> LifecycleReceipt:
        return self._runtime.clone(run, clone_run=clone_run)

    def rollback(self, run: RunScope, *, target_cycle_id: str) -> LifecycleReceipt:
        return self._runtime.rollback(run, target_cycle_id=target_cycle_id)

    def restore(self, run: RunScope, *, snapshot_id: str) -> LifecycleReceipt:
        return self._runtime.restore(run, snapshot_id=snapshot_id)

    def export_text(
        self,
        run: RunScope,
        *,
        export_id: str,
        sandbox_path: str,
        content: str,
    ) -> ExportReceipt:
        self.describe_run(run)
        return self._export_writer.export_text(
            run,
            export_id=export_id,
            sandbox_path=sandbox_path,
            content=content,
        )

    def export_bytes(
        self,
        run: RunScope,
        *,
        export_id: str,
        sandbox_path: str,
        payload: bytes,
    ) -> ExportReceipt:
        self.describe_run(run)
        return self._export_writer.export_bytes(
            run,
            export_id=export_id,
            sandbox_path=sandbox_path,
            payload=payload,
        )

    def _execute_allowed_command(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        cycle_id: str | None,
        reason: str | None,
        approval_actor_id: str | None,
        approval_actor_role: str | None,
        approval_occurred_at: str | None,
        approval_reason: str | None,
    ) -> _AllowedCommandOutcome:
        approval_record = self._approval_service.record_request(
            command,
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            mode_context=mode_context,
            reason=reason,
            cycle_id=cycle_id,
            details={"dispatch_status": "allowed", "surface": command.surface},
        )
        if approval_record is not None:
            approval_record = self._approval_service.approve(
                approval_record.approval_id,
                actor_id=approval_actor_id or actor_id,
                actor_role=approval_actor_role or actor_role,
                occurred_at=approval_occurred_at or occurred_at,
                mode_context=mode_context,
                reason=approval_reason,
            )
        approval_id = approval_record.approval_id if approval_record is not None else None
        lifecycle_timestamp = approval_occurred_at or occurred_at

        self._approval_service.record_started(
            command,
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=lifecycle_timestamp,
            approval_id=approval_id,
            cycle_id=cycle_id,
            details={"surface": command.surface},
        )
        try:
            lifecycle_receipt = self._apply_runtime_command(command)
        except Exception as error:
            self._approval_service.record_failed(
                command,
                actor_id=actor_id,
                actor_role=actor_role,
                occurred_at=lifecycle_timestamp,
                approval_id=approval_id,
                cycle_id=cycle_id,
                details={"reason": str(error), "surface": command.surface},
            )
            raise

        self._remember_control_receipt(command, approval_record, lifecycle_receipt)
        self._approval_service.record_completed(
            command,
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=lifecycle_timestamp,
            approval_id=approval_id,
            cycle_id=cycle_id,
            details=self._lifecycle_details(command, lifecycle_receipt),
        )
        return _AllowedCommandOutcome(
            approval_record=approval_record,
            lifecycle_receipt=lifecycle_receipt,
        )

    def _dispatch_context(self, run: RunScope, *, mode_context: str) -> DispatchContext:
        session = self.describe_run(run)
        return DispatchContext(
            current_mode=session.current_mode,
            mode_context=mode_context,
            mode_switch_receipt=self._active_mode_switch_receipts.get(run),
        )

    def _apply_runtime_command(self, command: CommandEnvelope) -> LifecycleReceipt:
        run = self._run_scope_from_command(command.scope)
        if command.action == "mode switch":
            if command.target_mode is None:
                raise ValueError("mode switch commands require target_mode")
            return self._runtime.mode_switch(run, target_mode=command.target_mode)
        if command.action == "pause":
            return self._runtime.pause(run)
        if command.action == "resume":
            return self._runtime.resume(run)
        if command.action == "reset":
            return self._runtime.reset(run)
        if command.action == "clone":
            clone_run = self._clone_run_for(command)
            return self._runtime.clone(run, clone_run=clone_run)
        if command.action == "rollback":
            return self._runtime.rollback(run, target_cycle_id=self._rollback_target(command))
        raise ValueError(f"unsupported orchestrator command action: {command.action}")

    def _handler_result(self, outcome: _AllowedCommandOutcome) -> dict[str, object]:
        result: dict[str, object] = {
            "action": outcome.lifecycle_receipt.action,
            "current_mode": outcome.lifecycle_receipt.current_mode,
            "lifecycle_state": outcome.lifecycle_receipt.lifecycle_state,
        }
        if outcome.approval_record is not None:
            result["approval_status"] = outcome.approval_record.status
            result["approval_id"] = str(outcome.approval_record.approval_id)
        return result

    def _remember_control_receipt(
        self,
        command: CommandEnvelope,
        approval_record: ApprovalRecord | None,
        lifecycle_receipt: LifecycleReceipt,
    ) -> None:
        run = self._run_scope_from_command(command.scope)
        if command.action == "mode switch" and approval_record is not None and approval_record.mode_switch_receipt is not None:
            self._active_mode_switch_receipts[run] = approval_record.mode_switch_receipt
            return
        if lifecycle_receipt.current_mode == OBSERVATION_ONLY_MODE:
            self._active_mode_switch_receipts.pop(run, None)

    def _lifecycle_details(
        self,
        command: CommandEnvelope,
        lifecycle_receipt: LifecycleReceipt,
    ) -> dict[str, object]:
        details: dict[str, object] = {
            "surface": command.surface,
            "current_mode": lifecycle_receipt.current_mode,
            "lifecycle_state": lifecycle_receipt.lifecycle_state,
        }
        if lifecycle_receipt.reason is not None:
            details["reason"] = lifecycle_receipt.reason
        if lifecycle_receipt.target_cycle_id is not None:
            details["target_cycle_id"] = lifecycle_receipt.target_cycle_id
        if lifecycle_receipt.snapshot_id is not None:
            details["snapshot_id"] = lifecycle_receipt.snapshot_id
        if lifecycle_receipt.clone_run is not None:
            details["clone_run_id"] = lifecycle_receipt.clone_run.run_id
        return details

    def _run_scope_from_command(self, scope: CommandScope) -> RunScope:
        if scope.run_id is None or scope.experiment_id is None:
            raise ValueError("orchestrator commands must be run-scoped")
        return RunScope(
            project_id=scope.project_id,
            glassbox_id=scope.glass_box_id,
            experiment_id=scope.experiment_id,
            run_id=scope.run_id,
        )

    def _clone_run_for(self, command: CommandEnvelope) -> RunScope:
        run = self._run_scope_from_command(command.scope)
        clone_run_id = command.surface_metadata.get("clone_run_id")
        if not isinstance(clone_run_id, str) or not clone_run_id.strip():
            raise ValueError("clone commands require surface_metadata.clone_run_id")
        return RunScope(
            project_id=run.project_id,
            glassbox_id=run.glassbox_id,
            experiment_id=run.experiment_id,
            run_id=clone_run_id,
        )

    def _rollback_target(self, command: CommandEnvelope) -> str:
        rollback_target = command.surface_metadata.get("target_cycle_id")
        if not isinstance(rollback_target, str) or not rollback_target.strip():
            raise ValueError("rollback commands require surface_metadata.target_cycle_id")
        return rollback_target


__all__ = [
    "CommandExecutionReceipt",
    "HostOrchestratorService",
    "OrchestratorHooks",
    "RunEvidenceWriteHook",
    "RunLogCaptureHook",
]
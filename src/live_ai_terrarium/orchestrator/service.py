from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

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


__all__ = [
    "HostOrchestratorService",
    "OrchestratorHooks",
    "RunEvidenceWriteHook",
    "RunLogCaptureHook",
]
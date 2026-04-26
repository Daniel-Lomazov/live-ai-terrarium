from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from live_ai_terrarium.orchestrator.boundary import SandboxBoundaryPolicy
from live_ai_terrarium.storage.filesystem import HostFilesystem
from live_ai_terrarium.storage.paths import RunScope, StoragePaths


@dataclass(frozen=True)
class ExportReceipt:
    artifact_id: str
    sandbox_path: PurePosixPath
    host_export_dir: Path
    host_artifact_path: Path
    manifest_path: Path


class AppendOnlyExportWriter:
    def __init__(
        self,
        storage_paths: StoragePaths,
        *,
        filesystem: HostFilesystem | None = None,
        boundary_policy: SandboxBoundaryPolicy | None = None,
    ) -> None:
        self._storage_paths = storage_paths
        self._filesystem = filesystem or HostFilesystem(storage_paths)
        self._boundary_policy = boundary_policy or SandboxBoundaryPolicy.v1()

    def export_text(
        self,
        run: RunScope,
        *,
        export_id: str,
        sandbox_path: str,
        content: str,
    ) -> ExportReceipt:
        return self.export_bytes(
            run,
            export_id=export_id,
            sandbox_path=sandbox_path,
            payload=content.encode("utf-8"),
        )

    def export_bytes(
        self,
        run: RunScope,
        *,
        export_id: str,
        sandbox_path: str,
        payload: bytes,
    ) -> ExportReceipt:
        normalized_sandbox_path = self._boundary_policy.validate_export_target(sandbox_path)
        export_dir = self._storage_paths.export_item_dir(run, export_id)
        if export_dir.exists():
            raise FileExistsError(
                f"append-only export contract denies in-place rewrite for artifact id: {export_id}"
            )

        artifact_name = normalized_sandbox_path.name
        if not artifact_name:
            raise ValueError("Export target must reference a file below the sanctioned outbox")

        self._filesystem.ensure_directory(export_dir)

        host_artifact_path = self._filesystem.write_bytes(
            export_dir / artifact_name,
            payload,
            overwrite=False,
        )
        manifest_path = self.append_manifest_entry(
            run,
            artifact_id=export_id,
            sandbox_path=normalized_sandbox_path,
        )
        return ExportReceipt(
            artifact_id=export_id,
            sandbox_path=normalized_sandbox_path,
            host_export_dir=export_dir,
            host_artifact_path=host_artifact_path,
            manifest_path=manifest_path,
        )

    def append_manifest_entry(
        self,
        run: RunScope,
        *,
        artifact_id: str,
        sandbox_path: str | PurePosixPath,
    ) -> Path:
        normalized_sandbox_path = self._boundary_policy.validate_export_target(sandbox_path)
        manifest_path = self._run_manifest_path(run)
        self._filesystem.append_jsonl(
            manifest_path,
            [
                {
                    "artifact_id": artifact_id,
                    "sandbox_path": str(normalized_sandbox_path),
                }
            ],
        )
        return manifest_path

    def _run_manifest_path(self, run: RunScope) -> Path:
        return self._storage_paths.export_item_dir(run, "manifest-placeholder").parent / "manifest.jsonl"


__all__ = ["AppendOnlyExportWriter", "ExportReceipt"]
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid5

from live_ai_terrarium.contracts.records import ArtifactRef
from live_ai_terrarium.storage.filesystem import HostFilesystem
from live_ai_terrarium.storage.paths import CycleScope, RunScope, StoragePaths

SnapshotKind = Literal["cycle", "full"]


def _stable_uuid(key: str) -> UUID:
    return uuid5(NAMESPACE_URL, key)


def _artifact_ref(locator: str) -> ArtifactRef:
    return ArtifactRef(uuid=_stable_uuid(f"artifact:{locator}"), locator=locator)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_workspace_dir(workspace_dir: str | Path) -> Path:
    target = Path(workspace_dir)
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(f"workspace_dir must exist and be a directory: {target}")
    return target


@dataclass(frozen=True)
class SnapshotCapture:
    snapshot_id: str
    kind: SnapshotKind
    manifest_path: Path
    files_dir: Path
    artifact_ref: ArtifactRef
    file_count: int


@dataclass(frozen=True)
class RestoreEntry:
    relative_path: str
    sha256: str
    size_bytes: int
    source_path: Path
    source_locator: str


@dataclass(frozen=True)
class RestorePlan:
    snapshot_id: str
    kind: SnapshotKind
    manifest_path: Path
    manifest_locator: str
    entries: tuple[RestoreEntry, ...]


class SnapshotService:
    def __init__(
        self,
        storage_paths: StoragePaths,
        *,
        filesystem: HostFilesystem | None = None,
    ) -> None:
        self._storage_paths = storage_paths
        self._filesystem = filesystem or HostFilesystem(storage_paths)

    @property
    def storage_paths(self) -> StoragePaths:
        return self._storage_paths

    def capture_cycle_snapshot(
        self,
        cycle_scope: CycleScope,
        *,
        workspace_dir: str | Path,
    ) -> SnapshotCapture:
        files_dir = self._storage_paths.cycle_snapshot_dir(cycle_scope)
        manifest_path = files_dir.parent / "manifest.json"
        return self._capture_snapshot(
            snapshot_id=cycle_scope.cycle_id,
            kind="cycle",
            run=cycle_scope.run,
            workspace_dir=workspace_dir,
            files_dir=files_dir,
            manifest_path=manifest_path,
            cycle_id=cycle_scope.cycle_id,
            reason="per-cycle",
        )

    def capture_full_snapshot(
        self,
        run: RunScope,
        *,
        snapshot_id: str,
        workspace_dir: str | Path,
        reason: str,
    ) -> SnapshotCapture:
        snapshot_root = self._storage_paths.full_snapshot_dir(run, snapshot_id)
        files_dir = snapshot_root / "files"
        manifest_path = snapshot_root / "manifest.json"
        return self._capture_snapshot(
            snapshot_id=snapshot_id,
            kind="full",
            run=run,
            workspace_dir=workspace_dir,
            files_dir=files_dir,
            manifest_path=manifest_path,
            cycle_id=None,
            reason=reason,
        )

    def reconstruct_restore(self, manifest_locator: str) -> RestorePlan:
        manifest_path = self._locator_to_path(manifest_locator)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = tuple(
            RestoreEntry(
                relative_path=entry["relative_path"],
                sha256=entry["sha256"],
                size_bytes=entry["size_bytes"],
                source_path=self._locator_to_path(entry["source_locator"]),
                source_locator=entry["source_locator"],
            )
            for entry in payload["entries"]
        )
        return RestorePlan(
            snapshot_id=payload["snapshot_id"],
            kind=payload["kind"],
            manifest_path=manifest_path,
            manifest_locator=manifest_locator,
            entries=entries,
        )

    def restore_cycle_snapshot(
        self,
        cycle_scope: CycleScope,
        *,
        workspace_dir: str | Path,
    ) -> RestorePlan:
        manifest_path = self._storage_paths.cycle_snapshot_dir(cycle_scope).parent / "manifest.json"
        return self.restore_snapshot(self._locator_for(manifest_path), workspace_dir=workspace_dir)

    def restore_snapshot(
        self,
        manifest_locator: str,
        *,
        workspace_dir: str | Path,
    ) -> RestorePlan:
        plan = self.reconstruct_restore(manifest_locator)
        workspace_root = _require_workspace_dir(workspace_dir)
        expected_paths = {entry.relative_path for entry in plan.entries}

        for file_path in sorted(
            (path for path in workspace_root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(workspace_root).as_posix(),
            reverse=True,
        ):
            relative_path = file_path.relative_to(workspace_root).as_posix()
            if relative_path not in expected_paths:
                file_path.unlink()

        for entry in plan.entries:
            target = workspace_root / Path(entry.relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(entry.source_path.read_bytes())

        for directory in sorted(
            (path for path in workspace_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()

        return plan

    def _capture_snapshot(
        self,
        *,
        snapshot_id: str,
        kind: SnapshotKind,
        run: RunScope,
        workspace_dir: str | Path,
        files_dir: Path,
        manifest_path: Path,
        cycle_id: str | None,
        reason: str,
    ) -> SnapshotCapture:
        workspace_root = _require_workspace_dir(workspace_dir)
        entries: list[dict[str, object]] = []

        for file_path in sorted(
            (path for path in workspace_root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(workspace_root).as_posix(),
        ):
            relative_path = file_path.relative_to(workspace_root).as_posix()
            destination = files_dir / Path(relative_path)
            payload = file_path.read_bytes()
            self._filesystem.write_bytes(destination, payload)
            entries.append(
                {
                    "relative_path": relative_path,
                    "sha256": _sha256_bytes(payload),
                    "size_bytes": len(payload),
                    "source_locator": self._locator_for(destination),
                }
            )

        manifest_locator = self._locator_for(manifest_path)
        manifest_payload = {
            "uuid": str(_stable_uuid(f"snapshot:{kind}:{run.run_id}:{snapshot_id}")),
            "snapshot_id": snapshot_id,
            "kind": kind,
            "run": {
                "project_id": run.project_id,
                "glassbox_id": run.glassbox_id,
                "experiment_id": run.experiment_id,
                "run_id": run.run_id,
            },
            "cycle_id": cycle_id,
            "reason": reason,
            "captured_at": datetime.now(UTC).isoformat(),
            "workspace_root": str(workspace_root.resolve()),
            "manifest_locator": manifest_locator,
            "entries": entries,
        }
        self._filesystem.write_json(manifest_path, manifest_payload)

        return SnapshotCapture(
            snapshot_id=snapshot_id,
            kind=kind,
            manifest_path=manifest_path,
            files_dir=files_dir,
            artifact_ref=_artifact_ref(manifest_locator),
            file_count=len(entries),
        )

    def _locator_for(self, path: Path) -> str:
        relative_path = path.resolve(strict=False).relative_to(self._storage_paths.state_root.resolve(strict=False))
        return relative_path.as_posix()

    def _locator_to_path(self, locator: str) -> Path:
        return self._storage_paths.state_root / Path(locator)


__all__ = [
    "RestoreEntry",
    "RestorePlan",
    "SnapshotCapture",
    "SnapshotService",
]
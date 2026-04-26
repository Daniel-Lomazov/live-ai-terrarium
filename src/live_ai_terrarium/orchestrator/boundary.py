from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from live_ai_terrarium.storage.paths import StoragePaths

WORKSPACE_MOUNT_TARGET = PurePosixPath("/workspace")
SANCTIONED_OUTBOX_PATH = WORKSPACE_MOUNT_TARGET / ".gb" / "outbox"
HOST_CONTROL_SURFACES = frozenset(
    {
        "docker_socket",
        "host_filesystem",
        "dashboard_sinks",
        "snapshot_sinks",
        "log_sinks",
    }
)


def _normalize_posix_path(value: str | PurePosixPath, *, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path under the sanctioned outbox")
    if ".." in path.parts:
        raise ValueError(f"{label} must stay within the sanctioned outbox")
    return path


@dataclass(frozen=True)
class SandboxBoundaryPolicy:
    workspace_mount_target: PurePosixPath = WORKSPACE_MOUNT_TARGET
    outbox_path: PurePosixPath = SANCTIONED_OUTBOX_PATH
    shared_mount_targets: tuple[PurePosixPath, ...] = (WORKSPACE_MOUNT_TARGET,)
    blocked_host_surfaces: frozenset[str] = field(default_factory=lambda: HOST_CONTROL_SURFACES)

    def __post_init__(self) -> None:
        if self.outbox_path != self.workspace_mount_target / ".gb" / "outbox":
            raise ValueError("Sandbox boundary must use the sanctioned /workspace/.gb/outbox path")
        self.validate_shared_mounts(self.shared_mount_targets)

    @classmethod
    def v1(cls) -> "SandboxBoundaryPolicy":
        return cls()

    def validate_shared_mounts(
        self,
        mount_targets: Iterable[str | PurePosixPath],
    ) -> tuple[PurePosixPath, ...]:
        normalized_targets = tuple(
            _normalize_posix_path(target, label="mount target") for target in mount_targets
        )
        if normalized_targets != (self.workspace_mount_target,):
            raise ValueError(
                "Sandbox boundary denies any extra shared mount; only /workspace may be mounted"
            )
        return normalized_targets

    def validate_export_target(self, target: str | PurePosixPath) -> PurePosixPath:
        normalized_target = _normalize_posix_path(target, label="export target")
        if normalized_target == self.outbox_path or not normalized_target.is_relative_to(self.outbox_path):
            raise ValueError("Export target must stay under the sanctioned outbox path")
        return normalized_target

    def validate_no_direct_host_access(
        self,
        candidate: str | Path,
        storage_paths: StoragePaths,
    ) -> Path:
        normalized_candidate = Path(candidate).resolve(strict=False)
        if storage_paths.is_host_controlled_path(normalized_candidate):
            raise ValueError(
                "Sandbox boundary denies direct access to host-controlled records, logs, snapshots, mirrors, and exports"
            )
        return normalized_candidate


__all__ = [
    "HOST_CONTROL_SURFACES",
    "SANCTIONED_OUTBOX_PATH",
    "SandboxBoundaryPolicy",
    "WORKSPACE_MOUNT_TARGET",
]
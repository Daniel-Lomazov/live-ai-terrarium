from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "LiveAITerrarium"
STATE_DIR_NAME = "state"
BACKUP_DIR_NAME = "backups"

_READABLE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def _validate_windows_safe_segment(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty Windows-safe readable ID")
    if not _READABLE_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be a Windows-safe readable ID")
    if value.lower() in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{label} must be a Windows-safe readable ID")
    return value


@dataclass(frozen=True)
class RunScope:
    project_id: str
    glassbox_id: str
    experiment_id: str
    run_id: str

    def __post_init__(self) -> None:
        _validate_windows_safe_segment(self.project_id, label="project_id")
        _validate_windows_safe_segment(self.glassbox_id, label="glassbox_id")
        _validate_windows_safe_segment(self.experiment_id, label="experiment_id")
        _validate_windows_safe_segment(self.run_id, label="run_id")


@dataclass(frozen=True)
class CycleScope:
    run: RunScope
    cycle_id: str

    def __post_init__(self) -> None:
        _validate_windows_safe_segment(self.cycle_id, label="cycle_id")


@dataclass(frozen=True)
class IncidentScope:
    run: RunScope
    incident_id: str

    def __post_init__(self) -> None:
        _validate_windows_safe_segment(self.incident_id, label="incident_id")


@dataclass(frozen=True)
class ProofBundleScope:
    run: RunScope
    bundle_id: str

    def __post_init__(self) -> None:
        _validate_windows_safe_segment(self.bundle_id, label="bundle_id")


@dataclass(frozen=True)
class StoragePaths:
    state_root: Path
    backup_root: Path

    @classmethod
    def from_local_appdata(cls, local_appdata: str | Path | None = None) -> "StoragePaths":
        base_root = Path(local_appdata) if local_appdata is not None else _read_local_appdata()
        return cls(
            state_root=base_root / APP_DIR_NAME / STATE_DIR_NAME,
            backup_root=base_root / APP_DIR_NAME / BACKUP_DIR_NAME,
        )

    @property
    def host_controlled_roots(self) -> tuple[Path, Path]:
        return (self.state_root, self.backup_root)

    def run_record_file(self, run: RunScope) -> Path:
        return self._state_path("records", *self._run_segments(run), "run.json")

    def run_manifest_file(self, run: RunScope) -> Path:
        return self._state_path(
            "manifests",
            *self._run_segments(run),
            "run-start-reproducibility.json",
        )

    def cycle_record_file(self, cycle: CycleScope) -> Path:
        return self._state_path(
            "records",
            *self._run_segments(cycle.run),
            "cycles",
            f"{cycle.cycle_id}.json",
        )

    def cycle_snapshot_dir(self, cycle: CycleScope) -> Path:
        return self._state_path(
            "snapshots",
            *self._run_segments(cycle.run),
            "cycles",
            cycle.cycle_id,
            "files",
        )

    def full_snapshot_dir(self, run: RunScope, snapshot_id: str) -> Path:
        return self._state_path(
            "snapshots",
            *self._run_segments(run),
            "full",
            _validate_windows_safe_segment(snapshot_id, label="snapshot_id"),
        )

    def export_item_dir(self, run: RunScope, export_id: str) -> Path:
        return self._state_path(
            "exports",
            *self._run_segments(run),
            "items",
            _validate_windows_safe_segment(export_id, label="export_id"),
        )

    def mirror_dir(self, run: RunScope) -> Path:
        return self._state_path("mirrors", *self._run_segments(run), "git")

    def incident_file(self, incident: IncidentScope) -> Path:
        return self._state_path(
            "incidents",
            *self._run_segments(incident.run),
            f"{incident.incident_id}.json",
        )

    def proof_bundle_dir(self, proof_bundle: ProofBundleScope) -> Path:
        return self._state_path(
            "proofs",
            *self._run_segments(proof_bundle.run),
            "bundles",
            proof_bundle.bundle_id,
        )

    def backup_proof_bundle_dir(self, proof_bundle: ProofBundleScope) -> Path:
        return self._backup_path(
            *self._run_segments(proof_bundle.run),
            "proofs",
            proof_bundle.bundle_id,
        )

    def is_host_controlled_path(self, candidate: str | Path) -> bool:
        normalized_candidate = Path(candidate).resolve(strict=False)
        return any(
            _is_relative_to(normalized_candidate, root.resolve(strict=False))
            for root in self.host_controlled_roots
        )

    def _state_path(self, *parts: str) -> Path:
        return self.state_root.joinpath(*parts)

    def _backup_path(self, *parts: str) -> Path:
        return self.backup_root.joinpath(*parts)

    def _run_segments(self, run: RunScope) -> tuple[str, ...]:
        return (
            "projects",
            run.project_id,
            "glassboxes",
            run.glassbox_id,
            "experiments",
            run.experiment_id,
            "runs",
            run.run_id,
        )


def _read_local_appdata() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise RuntimeError("LOCALAPPDATA is required for host-controlled state roots")
    return Path(value)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True

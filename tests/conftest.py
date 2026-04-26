from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def local_first_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Path]:
    state_root = tmp_path / "state"
    backup_root = tmp_path / "backups"
    export_root = tmp_path / "outbox"

    state_root.mkdir()
    backup_root.mkdir()
    export_root.mkdir()

    monkeypatch.setenv("LIVE_AI_TERRARIUM_STATE_ROOT", str(state_root))
    monkeypatch.setenv("LIVE_AI_TERRARIUM_BACKUP_ROOT", str(backup_root))
    monkeypatch.setenv("LIVE_AI_TERRARIUM_EXPORT_ROOT", str(export_root))

    return {
        "state_root": state_root,
        "backup_root": backup_root,
        "export_root": export_root,
    }
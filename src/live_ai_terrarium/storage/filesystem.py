from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from live_ai_terrarium.storage.paths import StoragePaths


class HostFilesystem:
    def __init__(self, storage_paths: StoragePaths) -> None:
        self._storage_paths = storage_paths

    def ensure_directory(self, path: str | Path) -> Path:
        target = Path(path)
        self._ensure_host_controlled(target)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def write_json(
        self,
        path: str | Path,
        payload: Any,
        *,
        overwrite: bool = False,
    ) -> Path:
        target = self._prepare_file(path, overwrite=overwrite)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def write_text(
        self,
        path: str | Path,
        content: str,
        *,
        overwrite: bool = False,
    ) -> Path:
        target = self._prepare_file(path, overwrite=overwrite)
        target.write_text(content, encoding="utf-8")
        return target

    def write_bytes(
        self,
        path: str | Path,
        payload: bytes,
        *,
        overwrite: bool = False,
    ) -> Path:
        target = self._prepare_file(path, overwrite=overwrite)
        target.write_bytes(payload)
        return target

    def append_jsonl(self, path: str | Path, entries: Iterable[Any]) -> Path:
        target = Path(path)
        self._ensure_host_controlled(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, separators=(",", ":"), sort_keys=True))
                handle.write("\n")
        return target

    def _prepare_file(self, path: str | Path, *, overwrite: bool) -> Path:
        target = Path(path)
        self._ensure_host_controlled(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not overwrite:
            raise FileExistsError(f"Append-only host-controlled path already exists: {target}")
        return target

    def _ensure_host_controlled(self, path: Path) -> None:
        if not self._storage_paths.is_host_controlled_path(path):
            raise ValueError(f"Path must stay under host-controlled storage roots: {path}")
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Protocol

from live_ai_terrarium.contracts.records import IMAGE_DIGEST_PATTERN
from live_ai_terrarium.control.commands import OBSERVATION_ONLY_MODE
from live_ai_terrarium.orchestrator.boundary import SandboxBoundaryPolicy
from live_ai_terrarium.storage.paths import RunScope

LifecycleAction = Literal[
    "mode switch",
    "pause",
    "resume",
    "reset",
    "clone",
    "rollback",
    "restore",
]
LifecycleState = Literal["active", "paused"]


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


@dataclass(frozen=True)
class RuntimeRegistration:
    run: RunScope
    container_name: str
    image_digest: str
    workspace_volume: str
    runtime_profile_name: str = "glassbox-hardened-v1"
    network_mode: str = "none"
    published_ports: tuple[int, ...] = ()
    boundary_policy: SandboxBoundaryPolicy = field(default_factory=SandboxBoundaryPolicy.v1)

    def __post_init__(self) -> None:
        _require_text(self.container_name, field_name="container_name")
        _require_text(self.workspace_volume, field_name="workspace_volume")
        _require_text(self.runtime_profile_name, field_name="runtime_profile_name")
        if not IMAGE_DIGEST_PATTERN.fullmatch(self.image_digest):
            raise ValueError("image_digest must be a pinned sha256 digest")
        if self.network_mode != "none":
            raise ValueError("runtime must disable direct sandbox network access")
        if self.published_ports:
            raise ValueError("runtime must publish zero ports")
        self.boundary_policy.validate_shared_mounts((self.boundary_policy.workspace_mount_target,))


@dataclass(frozen=True)
class RuntimeSession:
    registration: RuntimeRegistration
    lifecycle_state: LifecycleState = "active"
    current_mode: str = OBSERVATION_ONLY_MODE
    last_action: LifecycleAction | None = None
    reason: str | None = None
    clone_source_run: RunScope | None = None
    target_cycle_id: str | None = None
    snapshot_id: str | None = None


@dataclass(frozen=True)
class LifecycleReceipt:
    action: LifecycleAction
    run: RunScope
    lifecycle_state: LifecycleState
    current_mode: str
    reason: str | None = None
    clone_run: RunScope | None = None
    target_cycle_id: str | None = None
    snapshot_id: str | None = None


class OrchestratorRuntime(Protocol):
    def register_run(self, registration: RuntimeRegistration) -> RuntimeSession: ...

    def describe_run(self, run: RunScope) -> RuntimeSession: ...

    def mode_switch(self, run: RunScope, *, target_mode: str) -> LifecycleReceipt: ...

    def pause(self, run: RunScope) -> LifecycleReceipt: ...

    def resume(self, run: RunScope) -> LifecycleReceipt: ...

    def reset(self, run: RunScope, *, reason: str | None = None) -> LifecycleReceipt: ...

    def clone(self, run: RunScope, *, clone_run: RunScope) -> LifecycleReceipt: ...

    def rollback(self, run: RunScope, *, target_cycle_id: str) -> LifecycleReceipt: ...

    def restore(self, run: RunScope, *, snapshot_id: str) -> LifecycleReceipt: ...


class InMemoryOrchestratorRuntime:
    def __init__(self) -> None:
        self._sessions: dict[RunScope, RuntimeSession] = {}

    def register_run(self, registration: RuntimeRegistration) -> RuntimeSession:
        if registration.run in self._sessions:
            raise FileExistsError(f"runtime session already exists for run: {registration.run.run_id}")
        session = RuntimeSession(registration=registration)
        self._sessions[registration.run] = session
        return session

    def describe_run(self, run: RunScope) -> RuntimeSession:
        return self._require_session(run)

    def mode_switch(self, run: RunScope, *, target_mode: str) -> LifecycleReceipt:
        session = self._require_session(run)
        updated = replace(
            session,
            current_mode=_require_text(target_mode, field_name="target_mode"),
            last_action="mode switch",
            reason=None,
        )
        self._sessions[run] = updated
        return self._receipt("mode switch", updated)

    def pause(self, run: RunScope) -> LifecycleReceipt:
        session = self._require_session(run)
        updated = replace(session, lifecycle_state="paused", last_action="pause", reason=None)
        self._sessions[run] = updated
        return self._receipt("pause", updated)

    def resume(self, run: RunScope) -> LifecycleReceipt:
        session = self._require_session(run)
        updated = replace(session, lifecycle_state="active", last_action="resume", reason=None)
        self._sessions[run] = updated
        return self._receipt("resume", updated)

    def reset(self, run: RunScope, *, reason: str | None = None) -> LifecycleReceipt:
        session = self._require_session(run)
        updated = replace(
            session,
            lifecycle_state="active",
            current_mode=OBSERVATION_ONLY_MODE,
            last_action="reset",
            reason=None if reason is None else _require_text(reason, field_name="reason"),
            target_cycle_id=None,
            snapshot_id=None,
        )
        self._sessions[run] = updated
        return self._receipt("reset", updated)

    def clone(self, run: RunScope, *, clone_run: RunScope) -> LifecycleReceipt:
        source_session = self._require_session(run)
        if clone_run in self._sessions:
            raise FileExistsError(f"runtime session already exists for run: {clone_run.run_id}")
        cloned_registration = replace(source_session.registration, run=clone_run)
        self._sessions[clone_run] = RuntimeSession(
            registration=cloned_registration,
            lifecycle_state="active",
            current_mode=OBSERVATION_ONLY_MODE,
            last_action="clone",
            clone_source_run=run,
        )
        updated_source = replace(source_session, last_action="clone", reason=None)
        self._sessions[run] = updated_source
        return self._receipt("clone", updated_source, clone_run=clone_run)

    def rollback(self, run: RunScope, *, target_cycle_id: str) -> LifecycleReceipt:
        session = self._require_session(run)
        updated = replace(
            session,
            lifecycle_state="active",
            current_mode=OBSERVATION_ONLY_MODE,
            last_action="rollback",
            reason=None,
            target_cycle_id=_require_text(target_cycle_id, field_name="target_cycle_id"),
            snapshot_id=None,
        )
        self._sessions[run] = updated
        return self._receipt("rollback", updated)

    def restore(self, run: RunScope, *, snapshot_id: str) -> LifecycleReceipt:
        session = self._require_session(run)
        updated = replace(
            session,
            lifecycle_state="active",
            current_mode=OBSERVATION_ONLY_MODE,
            last_action="restore",
            reason=None,
            target_cycle_id=None,
            snapshot_id=_require_text(snapshot_id, field_name="snapshot_id"),
        )
        self._sessions[run] = updated
        return self._receipt("restore", updated)

    def _require_session(self, run: RunScope) -> RuntimeSession:
        try:
            return self._sessions[run]
        except KeyError as error:
            raise KeyError(f"runtime session is not registered for run: {run.run_id}") from error

    def _receipt(
        self,
        action: LifecycleAction,
        session: RuntimeSession,
        *,
        clone_run: RunScope | None = None,
    ) -> LifecycleReceipt:
        return LifecycleReceipt(
            action=action,
            run=session.registration.run,
            lifecycle_state=session.lifecycle_state,
            current_mode=session.current_mode,
            reason=session.reason,
            clone_run=clone_run,
            target_cycle_id=session.target_cycle_id,
            snapshot_id=session.snapshot_id,
        )


__all__ = [
    "InMemoryOrchestratorRuntime",
    "LifecycleReceipt",
    "LifecycleState",
    "OrchestratorRuntime",
    "RuntimeRegistration",
    "RuntimeSession",
]
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any, Protocol
from uuid import UUID

import typer
from pydantic import BaseModel

from live_ai_terrarium.control.commands import CanonicalAction, CommandEnvelope, CommandScope
from live_ai_terrarium.query.read_models import CycleDetailView, RunSummaryView

JsonScalar = str | int | float | bool | None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SubmissionContext:
    actor_id: str = "operator-local"
    actor_role: str = "operator"
    mode_context: str = "terminal-session"
    occurred_at: str | None = None
    reason: str | None = None
    cycle_id: str | None = None
    approval_actor_id: str | None = None
    approval_actor_role: str | None = None
    approval_occurred_at: str | None = None
    approval_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    action: CanonicalAction
    status: str
    receipt_id: UUID | None
    deny_reason: str | None = None
    current_mode: str | None = None
    lifecycle_state: str | None = None
    details: dict[str, object] | None = None


class QueryBackend(Protocol):
    def read_run(self, scope: CommandScope) -> RunSummaryView: ...

    def read_cycle(self, scope: CommandScope, cycle_id: str) -> CycleDetailView: ...


class ControlBackend(Protocol):
    def submit(self, command: CommandEnvelope, submission: SubmissionContext) -> CommandReceipt: ...


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def _scope_from_values(
    *,
    project_id: str,
    glass_box_id: str,
    experiment_id: str | None,
    run_id: str | None,
) -> CommandScope:
    return CommandScope(
        project_id=project_id,
        glass_box_id=glass_box_id,
        experiment_id=_optional_text(experiment_id),
        run_id=_optional_text(run_id),
    )


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, BaseModel):
        return {key: _jsonable(item) for key, item in value.model_dump(mode="python").items()}
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return str(value)


def _emit_json(payload: object) -> None:
    typer.echo(json.dumps(_jsonable(payload), sort_keys=True))


class GbCli:
    def __init__(
        self,
        *,
        query_backend: QueryBackend,
        control_backend: ControlBackend,
        surface: str = "cli",
        actor_id: str = "operator-local",
        actor_role: str = "operator",
        mode_context: str = "terminal-session",
        clock=utc_now,
    ) -> None:
        self._query_backend = query_backend
        self._control_backend = control_backend
        self._surface = surface
        self._actor_id = actor_id
        self._actor_role = actor_role
        self._mode_context = mode_context
        self._clock = clock

    def observe(self, *, scope: CommandScope, cycle_id: str | None = None) -> RunSummaryView | CycleDetailView:
        if cycle_id is None:
            return self._query_backend.read_run(scope)
        return self._query_backend.read_cycle(scope, cycle_id)

    def submit_action(
        self,
        *,
        action: CanonicalAction,
        scope: CommandScope,
        target_mode: str | None = None,
        branch_name: str | None = None,
        clone_run_id: str | None = None,
        target_cycle_id: str | None = None,
        reason: str | None = None,
        cycle_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        mode_context: str | None = None,
        occurred_at: str | None = None,
        approval_actor_id: str | None = None,
        approval_actor_role: str | None = None,
        approval_occurred_at: str | None = None,
        approval_reason: str | None = None,
    ) -> CommandReceipt:
        command = CommandEnvelope(
            action=action,
            scope=scope,
            target_mode=_optional_text(target_mode),
            surface=self._surface,
            surface_metadata=self._surface_metadata(
                branch_name=branch_name,
                clone_run_id=clone_run_id,
                target_cycle_id=target_cycle_id,
            ),
        )
        submission = SubmissionContext(
            actor_id=actor_id or self._actor_id,
            actor_role=actor_role or self._actor_role,
            mode_context=mode_context or self._mode_context,
            occurred_at=occurred_at or self._clock(),
            reason=_optional_text(reason),
            cycle_id=_optional_text(cycle_id),
            approval_actor_id=_optional_text(approval_actor_id),
            approval_actor_role=_optional_text(approval_actor_role),
            approval_occurred_at=_optional_text(approval_occurred_at),
            approval_reason=_optional_text(approval_reason),
        )
        return self._control_backend.submit(command, submission)

    def _surface_metadata(
        self,
        *,
        branch_name: str | None,
        clone_run_id: str | None,
        target_cycle_id: str | None,
    ) -> dict[str, JsonScalar]:
        metadata: dict[str, JsonScalar] = {}
        if _optional_text(branch_name) is not None:
            metadata["branch_name"] = _optional_text(branch_name)
        if _optional_text(clone_run_id) is not None:
            metadata["clone_run_id"] = _optional_text(clone_run_id)
        if _optional_text(target_cycle_id) is not None:
            metadata["target_cycle_id"] = _optional_text(target_cycle_id)
        return metadata


def create_app(
    *,
    query_backend: QueryBackend,
    control_backend: ControlBackend,
    default_actor_id: str = "operator-local",
    default_actor_role: str = "operator",
    default_mode_context: str = "terminal-session",
) -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    cli = GbCli(
        query_backend=query_backend,
        control_backend=control_backend,
        actor_id=default_actor_id,
        actor_role=default_actor_role,
        mode_context=default_mode_context,
    )

    def submit_command(
        *,
        action: CanonicalAction,
        project_id: str,
        glass_box_id: str,
        experiment_id: str | None,
        run_id: str | None,
        mode_context: str,
        reason: str | None = None,
        cycle_id: str | None = None,
        target_mode: str | None = None,
        branch_name: str | None = None,
        clone_run_id: str | None = None,
        target_cycle_id: str | None = None,
    ) -> None:
        receipt = cli.submit_action(
            action=action,
            scope=_scope_from_values(
                project_id=project_id,
                glass_box_id=glass_box_id,
                experiment_id=experiment_id,
                run_id=run_id,
            ),
            target_mode=target_mode,
            branch_name=branch_name,
            clone_run_id=clone_run_id,
            target_cycle_id=target_cycle_id,
            reason=reason,
            cycle_id=cycle_id,
            mode_context=mode_context,
        )
        _emit_json(receipt)

    @app.command("observe")
    def observe(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        del mode_context
        payload = cli.observe(
            scope=_scope_from_values(
                project_id=project_id,
                glass_box_id=glass_box_id,
                experiment_id=experiment_id,
                run_id=run_id,
            ),
            cycle_id=_optional_text(cycle_id),
        )
        _emit_json(payload)

    @app.command("mode-switch")
    def mode_switch(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        target_mode: str = typer.Option(...),
        reason: str | None = typer.Option(None),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        submit_command(
            action="mode switch",
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
            mode_context=mode_context,
            target_mode=target_mode,
            reason=reason,
            cycle_id=cycle_id,
        )

    @app.command("pause")
    def pause(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        reason: str | None = typer.Option(None),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        submit_command(
            action="pause",
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
            mode_context=mode_context,
            reason=reason,
            cycle_id=cycle_id,
        )

    @app.command("resume")
    def resume(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        reason: str | None = typer.Option(None),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        submit_command(
            action="resume",
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
            mode_context=mode_context,
            reason=reason,
            cycle_id=cycle_id,
        )

    @app.command("branch")
    def branch(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        branch_name: str | None = typer.Option(None),
        reason: str | None = typer.Option(None),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        submit_command(
            action="branch",
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
            mode_context=mode_context,
            branch_name=branch_name,
            reason=reason,
            cycle_id=cycle_id,
        )

    @app.command("clone")
    def clone(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        clone_run_id: str | None = typer.Option(None),
        reason: str | None = typer.Option(None),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        submit_command(
            action="clone",
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
            mode_context=mode_context,
            clone_run_id=clone_run_id,
            reason=reason,
            cycle_id=cycle_id,
        )

    @app.command("reset")
    def reset(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        reason: str | None = typer.Option(None),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        submit_command(
            action="reset",
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
            mode_context=mode_context,
            reason=reason,
            cycle_id=cycle_id,
        )

    @app.command("rollback")
    def rollback(
        project_id: str = typer.Option(...),
        glass_box_id: str = typer.Option(...),
        experiment_id: str | None = typer.Option(None),
        run_id: str | None = typer.Option(None),
        mode_context: str = typer.Option(default_mode_context),
        target_cycle_id: str | None = typer.Option(None),
        reason: str | None = typer.Option(None),
        cycle_id: str | None = typer.Option(None),
    ) -> None:
        submit_command(
            action="rollback",
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
            mode_context=mode_context,
            target_cycle_id=target_cycle_id,
            reason=reason,
            cycle_id=cycle_id,
        )

    return app


__all__ = [
    "CommandReceipt",
    "ControlBackend",
    "GbCli",
    "QueryBackend",
    "SubmissionContext",
    "create_app",
    "utc_now",
]

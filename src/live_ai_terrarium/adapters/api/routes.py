from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from fastapi import APIRouter, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from live_ai_terrarium.control.commands import CanonicalAction, CommandEnvelope, CommandScope


class CommandBackend(Protocol):
    def dispatch_command(
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
    ) -> object: ...


class QueryBackend(Protocol):
    def observe_run(self, scope: CommandScope) -> object: ...

    def observe_cycle(self, scope: CommandScope, *, cycle_id: str) -> object: ...


class ScopePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    glass_box_id: str
    experiment_id: str
    run_id: str

    def to_scope(self) -> CommandScope:
        try:
            return CommandScope(**self.model_dump())
        except ValidationError as error:
            raise _request_validation_error(error) from error


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: ScopePayload
    actor_id: str
    actor_role: str
    occurred_at: str
    mode_context: str
    idempotency_key: str | None = None
    cycle_id: str | None = None
    reason: str | None = None
    approval_actor_id: str | None = None
    approval_actor_role: str | None = None
    approval_occurred_at: str | None = None
    approval_reason: str | None = None
    surface_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    def to_command(self, *, action: CanonicalAction, target_mode: str | None = None) -> CommandEnvelope:
        try:
            return CommandEnvelope(
                action=action,
                scope=self.scope.to_scope(),
                idempotency_key=self.idempotency_key,
                target_mode=target_mode,
                surface="api",
                surface_metadata=self.surface_metadata,
            )
        except ValidationError as error:
            raise _request_validation_error(error) from error


class ModeSwitchCommandRequest(CommandRequest):
    target_mode: str


def build_api_router(*, command_backend: CommandBackend, query_backend: QueryBackend) -> APIRouter:
    router = APIRouter()

    @router.get("/observe/runs/{project_id}/{glass_box_id}/{experiment_id}/{run_id}")
    def observe_run(
        project_id: str,
        glass_box_id: str,
        experiment_id: str,
        run_id: str,
    ) -> object:
        return jsonable_encoder(
            query_backend.observe_run(
                _scope_from_path(
                    project_id=project_id,
                    glass_box_id=glass_box_id,
                    experiment_id=experiment_id,
                    run_id=run_id,
                )
            )
        )

    @router.get("/observe/runs/{project_id}/{glass_box_id}/{experiment_id}/{run_id}/cycles/{cycle_id}")
    def observe_cycle(
        project_id: str,
        glass_box_id: str,
        experiment_id: str,
        run_id: str,
        cycle_id: str,
    ) -> object:
        return jsonable_encoder(
            query_backend.observe_cycle(
                _scope_from_path(
                    project_id=project_id,
                    glass_box_id=glass_box_id,
                    experiment_id=experiment_id,
                    run_id=run_id,
                ),
                cycle_id=cycle_id,
            )
        )

    @router.post("/commands/mode-switch")
    def mode_switch(request: ModeSwitchCommandRequest) -> JSONResponse:
        return _dispatch_command(
            command_backend,
            request,
            action="mode switch",
            target_mode=request.target_mode,
        )

    @router.post("/commands/pause")
    def pause(request: CommandRequest) -> JSONResponse:
        return _dispatch_command(command_backend, request, action="pause")

    @router.post("/commands/resume")
    def resume(request: CommandRequest) -> JSONResponse:
        return _dispatch_command(command_backend, request, action="resume")

    @router.post("/commands/branch")
    def branch(request: CommandRequest) -> JSONResponse:
        return _dispatch_command(command_backend, request, action="branch")

    @router.post("/commands/clone")
    def clone(request: CommandRequest) -> JSONResponse:
        return _dispatch_command(command_backend, request, action="clone")

    @router.post("/commands/reset")
    def reset(request: CommandRequest) -> JSONResponse:
        return _dispatch_command(command_backend, request, action="reset")

    @router.post("/commands/rollback")
    def rollback(request: CommandRequest) -> JSONResponse:
        return _dispatch_command(command_backend, request, action="rollback")

    return router


def _dispatch_command(
    command_backend: CommandBackend,
    request: CommandRequest,
    *,
    action: CanonicalAction,
    target_mode: str | None = None,
) -> JSONResponse:
    payload = jsonable_encoder(
        command_backend.dispatch_command(
            request.to_command(action=action, target_mode=target_mode),
            actor_id=request.actor_id,
            actor_role=request.actor_role,
            occurred_at=request.occurred_at,
            mode_context=request.mode_context,
            cycle_id=request.cycle_id,
            reason=request.reason,
            approval_actor_id=request.approval_actor_id,
            approval_actor_role=request.approval_actor_role,
            approval_occurred_at=request.approval_occurred_at,
            approval_reason=request.approval_reason,
        )
    )
    return JSONResponse(
        content=payload,
        status_code=_response_status(payload),
    )


def _scope_from_path(
    *,
    project_id: str,
    glass_box_id: str,
    experiment_id: str,
    run_id: str,
) -> CommandScope:
    try:
        return CommandScope(
            project_id=project_id,
            glass_box_id=glass_box_id,
            experiment_id=experiment_id,
            run_id=run_id,
        )
    except ValidationError as error:
        raise _request_validation_error(error) from error


def _response_status(payload: object) -> int:
    if not isinstance(payload, Mapping):
        return status.HTTP_202_ACCEPTED
    dispatch_result = payload.get("dispatch_result")
    if isinstance(dispatch_result, Mapping) and dispatch_result.get("status") == "denied":
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_202_ACCEPTED


def _request_validation_error(error: ValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=jsonable_encoder(error.errors()),
    )


__all__ = ["CommandBackend", "QueryBackend", "build_api_router"]
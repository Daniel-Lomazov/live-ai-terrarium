from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .commands import CONTROL_ACTIONS, CommandEnvelope, CommandScope, ModeSwitchReceipt, OBSERVATION_ONLY_MODE

DispatchStatus = Literal["allowed", "denied"]


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


class DispatchContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current_mode: str
    mode_context: str
    mode_switch_receipt: ModeSwitchReceipt | None = None

    @field_validator("current_mode", "mode_context")
    @classmethod
    def validate_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    def control_is_unlocked_for(self, scope: CommandScope) -> bool:
        receipt = self.mode_switch_receipt
        return (
            receipt is not None
            and self.current_mode != OBSERVATION_ONLY_MODE
            and receipt.is_active_for(scope=scope, current_mode=self.current_mode, mode_context=self.mode_context)
        )


class DispatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: UUID = Field(default_factory=uuid4)
    command: CommandEnvelope
    status: DispatchStatus
    deny_reason: str | None = None
    handler_result: dict[str, object] | None = None
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def validate_state(self) -> DispatchResult:
        if self.status == "allowed" and self.deny_reason is not None:
            raise ValueError("deny_reason is only valid for denied results")
        if self.status == "denied" and not self.deny_reason:
            raise ValueError("deny_reason is required for denied results")
        return self


@dataclass(frozen=True)
class _CachedDispatch:
    receipt_id: UUID
    semantic_fingerprint: tuple[object, ...]
    status: DispatchStatus
    deny_reason: str | None
    handler_result: dict[str, object] | None

    def to_result(self, command: CommandEnvelope, *, replay: bool) -> DispatchResult:
        return DispatchResult(
            receipt_id=self.receipt_id,
            command=command,
            status=self.status,
            deny_reason=self.deny_reason,
            handler_result=deepcopy(self.handler_result),
            idempotent_replay=replay,
        )


class CommandDispatcher:
    def __init__(
        self,
        *,
        handler: Callable[[CommandEnvelope], Mapping[str, object] | None],
    ) -> None:
        self._handler = handler
        self._idempotency_cache: dict[str, _CachedDispatch] = {}

    def dispatch(self, command: CommandEnvelope, context: DispatchContext) -> DispatchResult:
        cached = self._get_cached_dispatch(command)
        if cached is not None:
            return cached.to_result(command, replay=True)

        deny_reason = self._deny_reason(command, context)
        if deny_reason is not None:
            result = DispatchResult(
                command=command,
                status="denied",
                deny_reason=deny_reason,
            )
        else:
            result = DispatchResult(
                command=command,
                status="allowed",
                handler_result=self._invoke_handler(command),
            )

        self._remember(command, result)
        return result

    def _get_cached_dispatch(self, command: CommandEnvelope) -> _CachedDispatch | None:
        if command.idempotency_key is None:
            return None
        cached = self._idempotency_cache.get(command.idempotency_key)
        if cached is None:
            return None
        if cached.semantic_fingerprint != command.semantic_fingerprint():
            raise ValueError("idempotency_key cannot be reused for a different semantic command")
        return cached

    def _remember(self, command: CommandEnvelope, result: DispatchResult) -> None:
        if command.idempotency_key is None:
            return
        self._idempotency_cache[command.idempotency_key] = _CachedDispatch(
            receipt_id=result.receipt_id,
            semantic_fingerprint=command.semantic_fingerprint(),
            status=result.status,
            deny_reason=result.deny_reason,
            handler_result=deepcopy(result.handler_result),
        )

    def _deny_reason(self, command: CommandEnvelope, context: DispatchContext) -> str | None:
        if command.action in ("observe", "mode switch"):
            return None
        if command.action in CONTROL_ACTIONS and not context.control_is_unlocked_for(command.scope):
            return f"{command.action} requires an active mode-switch receipt for the same scope and mode context"
        return None

    def _invoke_handler(self, command: CommandEnvelope) -> dict[str, object] | None:
        handler_result = self._handler(command)
        if handler_result is None:
            return None
        return dict(handler_result)


__all__ = ["CommandDispatcher", "DispatchContext", "DispatchResult"]
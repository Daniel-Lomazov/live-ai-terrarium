from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from live_ai_terrarium.control.commands import (
    CANONICAL_ACTIONS,
    CommandEnvelope,
    CommandScope,
    ModeSwitchReceipt,
)
from live_ai_terrarium.control.dispatcher import CommandDispatcher, DispatchContext


def make_scope(*, run_id: str = "run-stability-baseline") -> CommandScope:
    return CommandScope(
        project_id="project-live-ai-terrarium",
        glass_box_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id=run_id,
    )


class RecordingHandler:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, command: CommandEnvelope) -> dict[str, Any]:
        self.calls.append(command.action)
        return {"handled_action": command.action, "scope": command.scope.run_id}


def test_command_envelope_normalizes_actions_and_preserves_surface_metadata() -> None:
    command = CommandEnvelope(
        action="  MODE_SWITCH ",
        scope=make_scope(),
        target_mode="control-enabled",
        surface="dashboard",
        surface_metadata={"button": "unlock", "hotkey": "m"},
    )

    assert CANONICAL_ACTIONS == (
        "observe",
        "mode switch",
        "pause",
        "resume",
        "branch",
        "clone",
        "reset",
        "rollback",
    )
    assert command.action == "mode switch"
    assert command.surface_metadata == {"button": "unlock", "hotkey": "m"}


def test_command_envelope_rejects_non_canonical_actions() -> None:
    with pytest.raises(ValidationError, match="canonical action"):
        CommandEnvelope(action="delete", scope=make_scope())


def test_dispatcher_denies_control_actions_without_active_mode_switch_receipt() -> None:
    dispatcher = CommandDispatcher(handler=RecordingHandler())
    command = CommandEnvelope(action="pause", scope=make_scope(), idempotency_key="pause-once")
    context = DispatchContext(current_mode="observation-only", mode_context="mode-context-1")

    result = dispatcher.dispatch(command, context)

    assert result.status == "denied"
    assert result.deny_reason == "pause requires an active mode-switch receipt for the same scope and mode context"


def test_dispatcher_denies_control_actions_for_historical_or_stale_receipts() -> None:
    dispatcher = CommandDispatcher(handler=RecordingHandler())
    command = CommandEnvelope(action="branch", scope=make_scope(), idempotency_key="branch-once")

    historical_context = DispatchContext(
        current_mode="control-enabled",
        mode_context="mode-context-2",
        mode_switch_receipt=ModeSwitchReceipt(
            scope=make_scope(),
            mode_context="mode-context-1",
            target_mode="control-enabled",
            status="completed",
        ),
    )
    stale_context = DispatchContext(
        current_mode="control-enabled",
        mode_context="mode-context-2",
        mode_switch_receipt=ModeSwitchReceipt(
            scope=make_scope(run_id="run-other"),
            mode_context="mode-context-2",
            target_mode="control-enabled",
            status="active",
        ),
    )

    historical_result = dispatcher.dispatch(command, historical_context)
    stale_result = dispatcher.dispatch(command, stale_context)

    assert historical_result.status == "denied"
    assert historical_result.deny_reason == (
        "branch requires an active mode-switch receipt for the same scope and mode context"
    )
    assert stale_result.status == "denied"
    assert stale_result.deny_reason == (
        "branch requires an active mode-switch receipt for the same scope and mode context"
    )


def test_dispatcher_allows_control_actions_when_receipt_matches_scope_and_context() -> None:
    handler = RecordingHandler()
    dispatcher = CommandDispatcher(handler=handler)
    command = CommandEnvelope(action="resume", scope=make_scope(), idempotency_key="resume-once")
    context = DispatchContext(
        current_mode="control-enabled",
        mode_context="mode-context-2",
        mode_switch_receipt=ModeSwitchReceipt(
            scope=make_scope(),
            mode_context="mode-context-2",
            target_mode="control-enabled",
            status="active",
        ),
    )

    result = dispatcher.dispatch(command, context)

    assert result.status == "allowed"
    assert result.handler_result == {
        "handled_action": "resume",
        "scope": "run-stability-baseline",
    }
    assert handler.calls == ["resume"]


def test_dispatcher_reuses_cached_result_for_same_idempotency_key() -> None:
    handler = RecordingHandler()
    dispatcher = CommandDispatcher(handler=handler)
    context = DispatchContext(
        current_mode="control-enabled",
        mode_context="mode-context-7",
        mode_switch_receipt=ModeSwitchReceipt(
            scope=make_scope(),
            mode_context="mode-context-7",
            target_mode="control-enabled",
            status="active",
        ),
    )

    first = dispatcher.dispatch(
        CommandEnvelope(
            action="rollback",
            scope=make_scope(),
            idempotency_key="rollback-once",
            surface="cli",
            surface_metadata={"command": "gb rollback"},
        ),
        context,
    )
    second = dispatcher.dispatch(
        CommandEnvelope(
            action="rollback",
            scope=make_scope(),
            idempotency_key="rollback-once",
            surface="dashboard",
            surface_metadata={"button": "Rollback"},
        ),
        context,
    )

    assert first.status == "allowed"
    assert second.status == "allowed"
    assert second.idempotent_replay is True
    assert second.receipt_id == first.receipt_id
    assert handler.calls == ["rollback"]
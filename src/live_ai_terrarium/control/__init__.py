"""Shared control-plane models and dispatcher primitives."""

from .commands import CANONICAL_ACTIONS, CONTROL_ACTIONS, CommandEnvelope, CommandScope, ModeSwitchReceipt
from .dispatcher import CommandDispatcher, DispatchContext, DispatchResult

__all__ = [
    "CANONICAL_ACTIONS",
    "CONTROL_ACTIONS",
    "CommandDispatcher",
    "CommandEnvelope",
    "CommandScope",
    "DispatchContext",
    "DispatchResult",
    "ModeSwitchReceipt",
]
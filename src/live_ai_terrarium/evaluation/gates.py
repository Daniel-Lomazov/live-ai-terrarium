from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

REPEATED_CRASH_THRESHOLD = 3
RESOURCE_OVERUSE_THRESHOLD_PERCENT = 90.0
RESOURCE_OVERUSE_SAMPLE_COUNT = 3
LOG_SILENCE_THRESHOLD_SECONDS = 60

StopConditionCode = Literal[
    "repeated_crashes",
    "syntax_failure",
    "regression_score_drop",
    "forbidden_action_attempt",
    "resource_overuse",
    "log_silence",
]
GateFailureCode = Literal["required_tests", "cycle_execution"]
GateDecision = Literal["accepted", "rejected", "stopped"]


class GateCycleInput(Protocol):
    cycle_id: str
    syntax_ok: bool
    tests_ok: bool
    crash_terminated: bool
    score: float
    cpu_percent_samples: tuple[float, ...]
    memory_percent_samples: tuple[float, ...]
    resource_limit_breached: bool
    log_silence_seconds: int
    heartbeat_silence_seconds: int


class GateContext(Protocol):
    latest_baseline_score: float | None
    consecutive_crash_count: int


@dataclass(frozen=True)
class StopCondition:
    code: StopConditionCode
    detail: str


@dataclass(frozen=True)
class GateEvaluation:
    decision: GateDecision
    accepted: bool
    failed_gates: tuple[GateFailureCode, ...]
    stop_conditions: tuple[StopCondition, ...]


class GateEvaluator:
    def evaluate(
        self,
        cycle_input: GateCycleInput,
        context: GateContext,
        *,
        forbidden_tool_ids: tuple[str, ...] = (),
    ) -> GateEvaluation:
        stop_conditions = self._detect_stop_conditions(
            cycle_input,
            context,
            forbidden_tool_ids=forbidden_tool_ids,
        )
        if stop_conditions:
            return GateEvaluation(
                decision="stopped",
                accepted=False,
                failed_gates=(),
                stop_conditions=stop_conditions,
            )

        failed_gates: list[GateFailureCode] = []
        if cycle_input.crash_terminated:
            failed_gates.append("cycle_execution")
        if not cycle_input.tests_ok:
            failed_gates.append("required_tests")
        if failed_gates:
            return GateEvaluation(
                decision="rejected",
                accepted=False,
                failed_gates=tuple(failed_gates),
                stop_conditions=(),
            )

        return GateEvaluation(
            decision="accepted",
            accepted=True,
            failed_gates=(),
            stop_conditions=(),
        )

    def _detect_stop_conditions(
        self,
        cycle_input: GateCycleInput,
        context: GateContext,
        *,
        forbidden_tool_ids: tuple[str, ...],
    ) -> tuple[StopCondition, ...]:
        stop_conditions: list[StopCondition] = []

        if forbidden_tool_ids:
            joined_ids = ", ".join(forbidden_tool_ids)
            stop_conditions.append(
                StopCondition(
                    code="forbidden_action_attempt",
                    detail=f"Denied tool request attempted: {joined_ids}",
                )
            )

        if self._resource_overuse_detected(cycle_input):
            stop_conditions.append(
                StopCondition(
                    code="resource_overuse",
                    detail=(
                        "Container resource budget exceeded or sustained CPU or memory usage above "
                        f"{RESOURCE_OVERUSE_THRESHOLD_PERCENT:.0f} percent"
                    ),
                )
            )

        if max(cycle_input.log_silence_seconds, cycle_input.heartbeat_silence_seconds) >= LOG_SILENCE_THRESHOLD_SECONDS:
            stop_conditions.append(
                StopCondition(
                    code="log_silence",
                    detail=(
                        "No brokered log activity or heartbeat was observed for "
                        f"{LOG_SILENCE_THRESHOLD_SECONDS} seconds"
                    ),
                )
            )

        if cycle_input.crash_terminated and context.consecutive_crash_count + 1 >= REPEATED_CRASH_THRESHOLD:
            stop_conditions.append(
                StopCondition(
                    code="repeated_crashes",
                    detail=(
                        f"Cycle terminated after {REPEATED_CRASH_THRESHOLD} consecutive crash cycles "
                        "within the same run"
                    ),
                )
            )

        if not cycle_input.syntax_ok:
            stop_conditions.append(
                StopCondition(
                    code="syntax_failure",
                    detail="Syntax gate failed for the affected cycle",
                )
            )

        baseline_score = context.latest_baseline_score
        if baseline_score is not None and cycle_input.score < baseline_score:
            stop_conditions.append(
                StopCondition(
                    code="regression_score_drop",
                    detail=(
                        f"Cycle score {cycle_input.score:.3f} regressed below the accepted baseline "
                        f"{baseline_score:.3f}"
                    ),
                )
            )

        return tuple(stop_conditions)

    def _resource_overuse_detected(self, cycle_input: GateCycleInput) -> bool:
        if cycle_input.resource_limit_breached:
            return True
        return self._has_sustained_overuse(cycle_input.cpu_percent_samples) or self._has_sustained_overuse(
            cycle_input.memory_percent_samples
        )

    def _has_sustained_overuse(self, samples: tuple[float, ...]) -> bool:
        sustained = 0
        for sample in samples:
            if sample > RESOURCE_OVERUSE_THRESHOLD_PERCENT:
                sustained += 1
                if sustained >= RESOURCE_OVERUSE_SAMPLE_COUNT:
                    return True
            else:
                sustained = 0
        return False


__all__ = [
    "GateDecision",
    "GateEvaluation",
    "GateEvaluator",
    "GateFailureCode",
    "LOG_SILENCE_THRESHOLD_SECONDS",
    "REPEATED_CRASH_THRESHOLD",
    "RESOURCE_OVERUSE_SAMPLE_COUNT",
    "RESOURCE_OVERUSE_THRESHOLD_PERCENT",
    "StopCondition",
    "StopConditionCode",
]
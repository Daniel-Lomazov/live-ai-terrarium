from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from live_ai_terrarium.evaluation.gates import GateEvaluator, GateFailureCode, StopCondition, StopConditionCode
from live_ai_terrarium.orchestrator.boundary import SandboxBoundaryPolicy

RunnerDecision = Literal["accepted", "rejected", "stopped"]
ParetoMetadata = dict[str, float | int | str | None]


def _require_cycle_identifier(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("cycle_id must not be empty")
    return normalized


@dataclass(frozen=True)
class RunnerCycleInput:
    cycle_id: str
    requested_tool_ids: tuple[str, ...] = ()
    syntax_ok: bool = True
    tests_ok: bool = True
    crash_terminated: bool = False
    score: float = 0.0
    cpu_percent_samples: tuple[float, ...] = ()
    memory_percent_samples: tuple[float, ...] = ()
    resource_limit_breached: bool = False
    log_silence_seconds: int = 0
    heartbeat_silence_seconds: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "cycle_id", _require_cycle_identifier(self.cycle_id))


@dataclass(frozen=True)
class PersistedStopCondition:
    cycle_id: str
    code: StopConditionCode
    detail: str


@dataclass(frozen=True)
class RunnerContext:
    allowed_tool_ids: frozenset[str]
    boundary_policy: SandboxBoundaryPolicy = field(default_factory=SandboxBoundaryPolicy.v1)
    latest_baseline_score: float | None = None
    consecutive_crash_count: int = 0
    stable_cycle_count: int = 0
    stable_cycle_target: int = 10
    persisted_stop_conditions: tuple[PersistedStopCondition, ...] = ()

    def __post_init__(self) -> None:
        if self.stable_cycle_target < 1:
            raise ValueError("stable_cycle_target must be at least 1")
        if self.consecutive_crash_count < 0:
            raise ValueError("consecutive_crash_count must be non-negative")
        if self.stable_cycle_count < 0:
            raise ValueError("stable_cycle_count must be non-negative")


@dataclass(frozen=True)
class RunnerResult:
    cycle_id: str
    decision: RunnerDecision
    accepted: bool
    failed_gates: tuple[GateFailureCode, ...]
    stop_conditions: tuple[StopCondition, ...]
    stable_cycle_count: int
    latest_baseline_score: float | None
    consecutive_crash_count: int
    milestone_reached: bool
    pareto_metadata: ParetoMetadata | None
    next_context: RunnerContext


class AgentCycleRunner:
    def __init__(
        self,
        *,
        evaluator: GateEvaluator,
        pareto_callback: callable | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._pareto_callback = pareto_callback

    def run_cycle(self, cycle_input: RunnerCycleInput, context: RunnerContext) -> RunnerResult:
        self._validate_boundary_assumptions(context)

        forbidden_tool_ids = tuple(
            tool_id for tool_id in cycle_input.requested_tool_ids if tool_id not in context.allowed_tool_ids
        )
        evaluation = self._evaluator.evaluate(
            cycle_input,
            context,
            forbidden_tool_ids=forbidden_tool_ids,
        )

        next_context = self._build_next_context(cycle_input, context, evaluation.stop_conditions, evaluation.accepted)
        pareto_metadata = self._compute_pareto_metadata(cycle_input, context, evaluation.accepted)

        return RunnerResult(
            cycle_id=cycle_input.cycle_id,
            decision=evaluation.decision,
            accepted=evaluation.accepted,
            failed_gates=evaluation.failed_gates,
            stop_conditions=evaluation.stop_conditions,
            stable_cycle_count=next_context.stable_cycle_count,
            latest_baseline_score=next_context.latest_baseline_score,
            consecutive_crash_count=next_context.consecutive_crash_count,
            milestone_reached=next_context.stable_cycle_count >= next_context.stable_cycle_target,
            pareto_metadata=pareto_metadata,
            next_context=next_context,
        )

    def _build_next_context(
        self,
        cycle_input: RunnerCycleInput,
        context: RunnerContext,
        stop_conditions: tuple[StopCondition, ...],
        accepted: bool,
    ) -> RunnerContext:
        persisted_stops = context.persisted_stop_conditions + tuple(
            PersistedStopCondition(
                cycle_id=cycle_input.cycle_id,
                code=condition.code,
                detail=condition.detail,
            )
            for condition in stop_conditions
        )
        return replace(
            context,
            latest_baseline_score=cycle_input.score if accepted else context.latest_baseline_score,
            consecutive_crash_count=context.consecutive_crash_count + 1 if cycle_input.crash_terminated else 0,
            stable_cycle_count=context.stable_cycle_count + (1 if accepted else 0),
            persisted_stop_conditions=persisted_stops,
        )

    def _compute_pareto_metadata(
        self,
        cycle_input: RunnerCycleInput,
        context: RunnerContext,
        accepted: bool,
    ) -> ParetoMetadata | None:
        if not accepted or self._pareto_callback is None:
            return None
        metadata = self._pareto_callback(cycle_input.score, context.latest_baseline_score)
        if metadata is None:
            return None
        return dict(metadata)

    def _validate_boundary_assumptions(self, context: RunnerContext) -> None:
        context.boundary_policy.validate_shared_mounts(context.boundary_policy.shared_mount_targets)


__all__ = [
    "AgentCycleRunner",
    "ParetoMetadata",
    "PersistedStopCondition",
    "RunnerContext",
    "RunnerCycleInput",
    "RunnerDecision",
    "RunnerResult",
]
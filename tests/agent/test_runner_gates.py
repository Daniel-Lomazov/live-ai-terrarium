from __future__ import annotations

from dataclasses import replace

import pytest

from live_ai_terrarium.agent.runner import AgentCycleRunner, RunnerContext, RunnerCycleInput
from live_ai_terrarium.evaluation.gates import GateEvaluator, StopConditionCode


def make_cycle_input(**overrides: object) -> RunnerCycleInput:
    cycle_input = RunnerCycleInput(
        cycle_id="cycle-0001",
        requested_tool_ids=("python.pytest",),
        syntax_ok=True,
        tests_ok=True,
        crash_terminated=False,
        score=0.8,
        cpu_percent_samples=(25.0, 40.0),
        memory_percent_samples=(45.0,),
        resource_limit_breached=False,
        log_silence_seconds=0,
        heartbeat_silence_seconds=0,
    )
    return replace(cycle_input, **overrides)


def make_context(**overrides: object) -> RunnerContext:
    context = RunnerContext(
        allowed_tool_ids=frozenset({"python.pytest", "git.status_short"}),
        stable_cycle_target=10,
    )
    return replace(context, **overrides)


def test_runner_accepts_valid_cycle_and_updates_baseline_and_stable_count() -> None:
    ranking_calls: list[tuple[float, float | None]] = []

    def ranking_callback(score: float, baseline_score: float | None) -> dict[str, float | None]:
        ranking_calls.append((score, baseline_score))
        return {"score": score, "baseline_score": baseline_score}

    runner = AgentCycleRunner(
        evaluator=GateEvaluator(),
        pareto_callback=ranking_callback,
    )

    result = runner.run_cycle(make_cycle_input(), make_context())

    assert result.decision == "accepted"
    assert result.accepted is True
    assert result.stable_cycle_count == 1
    assert result.latest_baseline_score == pytest.approx(0.8)
    assert result.stop_conditions == ()
    assert result.pareto_metadata == {"score": 0.8, "baseline_score": None}
    assert ranking_calls == [(0.8, None)]


def test_runner_stops_for_forbidden_tool_attempt_before_ranking() -> None:
    ranking_calls: list[tuple[float, float | None]] = []

    def ranking_callback(score: float, baseline_score: float | None) -> dict[str, float | None]:
        ranking_calls.append((score, baseline_score))
        return {"score": score, "baseline_score": baseline_score}

    runner = AgentCycleRunner(
        evaluator=GateEvaluator(),
        pareto_callback=ranking_callback,
    )

    result = runner.run_cycle(
        make_cycle_input(requested_tool_ids=("python.pytest", "docker.exec")),
        make_context(),
    )

    assert result.decision == "stopped"
    assert result.accepted is False
    assert [condition.code for condition in result.stop_conditions] == ["forbidden_action_attempt"]
    assert result.pareto_metadata is None
    assert ranking_calls == []


@pytest.mark.parametrize(
    ("cycle_input", "expected_codes"),
    [
        (
            make_cycle_input(syntax_ok=False),
            ("syntax_failure",),
        ),
        (
            make_cycle_input(crash_terminated=True, cycle_id="cycle-0003"),
            ("repeated_crashes",),
        ),
        (
            make_cycle_input(log_silence_seconds=60),
            ("log_silence",),
        ),
        (
            make_cycle_input(cpu_percent_samples=(91.0, 92.0, 95.0)),
            ("resource_overuse",),
        ),
        (
            make_cycle_input(score=0.5),
            ("regression_score_drop",),
        ),
    ],
)
def test_runner_detects_selected_stop_conditions(
    cycle_input: RunnerCycleInput,
    expected_codes: tuple[StopConditionCode, ...],
) -> None:
    runner = AgentCycleRunner(evaluator=GateEvaluator())
    context = replace(make_context(), latest_baseline_score=0.8, consecutive_crash_count=2)

    result = runner.run_cycle(cycle_input, context)

    assert result.decision == "stopped"
    assert result.accepted is False
    assert tuple(condition.code for condition in result.stop_conditions) == expected_codes


def test_gate_evaluator_rejects_failed_tests_without_stop_condition() -> None:
    evaluator = GateEvaluator()

    evaluation = evaluator.evaluate(
        make_cycle_input(tests_ok=False),
        make_context(latest_baseline_score=0.8),
    )

    assert evaluation.decision == "rejected"
    assert evaluation.accepted is False
    assert evaluation.stop_conditions == ()
    assert evaluation.failed_gates == ("required_tests",)


def test_runner_counts_only_accepted_cycles_toward_milestone() -> None:
    runner = AgentCycleRunner(evaluator=GateEvaluator())
    context = replace(make_context(stable_cycle_target=10), stable_cycle_count=9, latest_baseline_score=0.8)

    accepted = runner.run_cycle(make_cycle_input(cycle_id="cycle-0010", score=0.82), context)
    rejected = runner.run_cycle(make_cycle_input(cycle_id="cycle-0011", tests_ok=False, score=0.83), accepted.next_context)

    assert accepted.stable_cycle_count == 10
    assert accepted.milestone_reached is True
    assert rejected.stable_cycle_count == 10
    assert rejected.milestone_reached is True
    assert rejected.latest_baseline_score == pytest.approx(0.82)


def test_evaluator_exposes_all_stop_condition_codes() -> None:
    assert StopConditionCode.__args__ == (
        "repeated_crashes",
        "syntax_failure",
        "regression_score_drop",
        "forbidden_action_attempt",
        "resource_overuse",
        "log_silence",
    )
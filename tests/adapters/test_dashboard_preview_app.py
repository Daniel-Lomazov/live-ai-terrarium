from __future__ import annotations

from live_ai_terrarium.adapters.dashboard.preview_app import (
    DEFAULT_CYCLE_ID,
    build_preview_backend,
    build_preview_cycle_detail,
    build_preview_scope,
)


def test_preview_backend_exposes_ten_cycle_proof_shaped_data() -> None:
    backend = build_preview_backend()
    scope = build_preview_scope()

    run_summary = backend.load_run_summary(scope)
    cycle_detail = backend.load_cycle_detail(scope, DEFAULT_CYCLE_ID)

    assert len(run_summary.cycle_summaries) == 10
    assert run_summary.cycle_summaries[0].cycle_id == "cycle-0001"
    assert run_summary.cycle_summaries[-1].cycle_id == "cycle-0010"
    assert run_summary.approval_status == "requested"
    assert run_summary.incident_state == "open"
    assert cycle_detail.cycle_id == DEFAULT_CYCLE_ID
    assert cycle_detail.reversibility.rollback_target == "cycle-0009"


def test_preview_cycle_builder_supports_drill_down_for_first_and_last_cycle() -> None:
    first_cycle = build_preview_cycle_detail("cycle-0001")
    last_cycle = build_preview_cycle_detail("cycle-0010")

    assert first_cycle.gate_decision == "accepted"
    assert first_cycle.error_summary is None
    assert last_cycle.gate_decision == "rejected"
    assert last_cycle.error_summary == "regression detected in smoke tests"
    assert last_cycle.reversibility.incident_id == "incident-syntax-failure"
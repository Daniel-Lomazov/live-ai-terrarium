# Live AI Terrarium v1 Ops Contract

Status: Frozen v1 baseline for LAT-001.

This document is normative for v1 operating defaults, stop conditions, recovery ordering, branch semantics, and proof preflight expectations.

## Sources

- `.github/live_ai_terrarium_questionnaire_working_file_v_1_0.md`
- `AGENTS.md`
- `docs/v1-architecture-brief.md`
- `docs/plan/20260426-live-ai-terrarium-v1/plan.yaml`

## Operating Baseline

- The system starts in observation-only mode.
- The v1 proof scope is one inner agent, one sandbox, no direct sandbox network, and simple tests.
- All operator surfaces share one backend command path and one read model.
- Sensitive control actions remain audit-logged and approval-gated when the approval policy requires them.

## Deterministic Acceptance And Baseline Rules

- A cycle is accepted only when syntax passes, required tests pass, no forbidden action occurs, and no regression is detected.
- The frozen no-regression baseline is the last accepted stable cycle for the active run.
- Stability and improvement trend are tracked signals, but they do not override failed gates.
- Pareto-style comparison ranks only candidates that already passed the required gates.

## Stop Conditions

The v1 stop-condition set is fixed as:

- repeated crashes,
- syntax failure,
- regression or score drop against the active run baseline,
- forbidden action attempt,
- resource overuse, and
- log silence.

The explicit v1 thresholds are:

| Stop condition | Frozen v1 threshold |
| --- | --- |
| repeated crashes | 3 consecutive crash-terminated cycles within the same run |
| syntax failure | Immediate stop for the affected cycle |
| regression or score drop | Immediate stop when the evaluator detects regression against the last accepted stable cycle for the active run |
| forbidden action attempt | Immediate stop when a denied action or denied tool request is attempted |
| resource overuse | Immediate stop on container hard-limit breach, or on sustained CPU or memory usage above 90 percent of the configured budget for 30 seconds |
| log silence | Stop after 60 seconds without brokered log activity or heartbeat activity during an active cycle |

## Snapshot Cadence

- A file-level snapshot is taken every cycle.
- A full workspace snapshot is taken every 5 cycles.
- A full workspace snapshot is also taken on every stop condition.
- Snapshot evidence is written before destructive recovery steps proceed.

## Failure And Recovery Ordering

Failure handling is evidence-first.

The frozen response order is:

`pause -> snapshot -> branch-and-continue or rollback or kill/restore -> report`

Additional rules:

- Manual rollback is the v1 rollback mode.
- The rollback target is the last accepted stable cycle for the active run.
- Kill and restore is used when the sandbox is unsafe or unrecoverable.
- Failure states are preserved for inspection rather than silently discarded.

## Branch-And-Continue Semantics

- Branch-and-continue creates a sandbox-inner Git branch from the current sandbox state.
- Branch-and-continue also writes external mirror evidence for that divergent state.
- Branch-and-continue does not create an outer-repository feature branch.
- The outer repository remains single-branch `main` for v1, except for annotated milestone tags and annotated release tags.
- Sandbox-inner branch evidence is part of reversibility proof and remains outside the outer main-only branch graph.

## Observation-Only Enforcement

- `observe` is the only action allowed by default in observation-only mode.
- `mode switch` is the only control action that may become available before other control actions, and only through an approval-compliant receipt as defined in the system contract.
- `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` remain denied until an active mode-switch receipt exists for the same run or instance scope and current mode context.
- A historical receipt alone does not unlock any control action.

## Proof-Clearance Expectations

- The ten-cycle proof harness must read `docs/reviews/proof-clearance-status.yaml` before executing milestone assertions.
- Proof execution fails closed when the clearance file is missing.
- Proof execution fails closed when the clearance status is `blocked`.
- Milestone proof execution is allowed only when the clearance status is `cleared`.

Before milestone success can be declared, the proof bundle must contain:

- the run-start reproducibility manifest,
- immutable build identity rooted in the required outer repo commit SHA and container image digest,
- preserved full logs,
- cycle-to-audit linkage evidence,
- branch-and-continue evidence when branching occurred,
- manual rollback evidence, and
- zero unrecoverable failures across the ten-cycle proof.

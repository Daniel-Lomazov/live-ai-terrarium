# Live AI Terrarium v1 System Contract

Status: Frozen v1 baseline for LAT-001.

This document is normative for v1 system behavior. It freezes the boundary, role, control-surface, and operator-action contract that later tasks consume.

## Sources

- `.github/live_ai_terrarium_questionnaire_working_file_v_1_0.md`
- `AGENTS.md`
- `docs/v1-architecture-brief.md`
- `docs/plan/20260426-live-ai-terrarium-v1/plan.yaml`

## Frozen v1 Baseline

- Implementation baseline is Python-first and uses FastAPI, Pydantic, Typer, Rich, Streamlit, pytest, and Docker CLI.
- v1 scope is one inner agent, one Glass-Box sandbox, no direct sandbox network, and a simple test suite.
- v1 success target is 10 stable cycles with full logs and rollback, with diff, score, and decision visible for every cycle.
- Observation-only is the default operating mode.

## Conceptual Hierarchy

The v1 conceptual hierarchy is fixed as:

`Project -> Glass-Box -> Experiment -> Run -> Cycle -> Mutation`

Internal implementation may be simplified, but stored records and operator language must preserve this hierarchy.

## Role Contract

| Role | Responsibility | Boundary |
| --- | --- | --- |
| Orchestrator | Own lifecycle for project, Glass-Box, experiment, run, cycle, and mutation. | Outside sandbox |
| Model Gateway | Mediate all model access, rate limits, and per-run scoping. | Outside sandbox |
| Inner Agent | Read and write sandbox-local files, run tests, call approved tools, and request model work through the gateway. | Inside sandbox |
| Evaluator | Apply gates, regression checks, and candidate comparison. | Separate logical role from Inner Agent |
| Dashboard | Present Streamlit and CLI or TUI views over shared records and shared control commands. | Outside sandbox |
| Observer or Annotator | Add interpretation and annotations without overriding gate decisions. | Separate logical role |

Strict logical and modular separation is required even if the first implementation runs these roles in one process or uses the same underlying model.

## Boundary And Export Contract

- Isolation unit is one Docker container per Glass-Box instance.
- The v1 boundary is hard: the sandbox has no host access and no shared mounts except one controlled export directory.
- The only sanctioned sandbox-to-host artifact egress path is `/workspace/.gb/outbox`.
- Logs, metrics, and diffs cross the boundary through a controlled API.
- Artifacts cross the boundary only through the append-only export channel rooted at `/workspace/.gb/outbox`.
- The sandbox has no direct internet access.
- Model access is available only through the external Model Gateway.
- No secrets may exist inside the sandbox.

## Inner-Agent Tool Boundary

The Inner Agent is allowed to:

- read and write its own sandbox files,
- run tests,
- request model work through the Model Gateway, and
- use limited shell functionality only through allowlisted commands exposed by validated interfaces.

The Inner Agent is denied from:

- controlling Docker or host system state,
- accessing the host filesystem,
- using direct network access,
- editing dashboard sinks, snapshot sinks, or log sinks,
- running background daemons, and
- downloading code dynamically.

## Canonical Operator Action List

The v1 operator action list is fixed as exactly:

`observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, `rollback`

No v1 surface may add a ninth control action or omit one of these actions from the shared contract.

## Cross-Surface Action Matrix

All operator surfaces must expose the same action set through one shared backend command path.

| Action | API | CLI or TUI | Dashboard | v1 rule |
| --- | --- | --- | --- | --- |
| observe | Required | Required | Required | Read-only inspection action |
| mode switch | Required | Required | Required | Explicit auditable command |
| pause | Required | Required | Required | Controlled action |
| resume | Required | Required | Required | Controlled action |
| branch | Required | Required | Required | Controlled action |
| clone | Required | Required | Required | Controlled action |
| reset | Required | Required | Required | Controlled action |
| rollback | Required | Required | Required | Controlled action |

Surface-specific labels may vary, but action meaning, audit behavior, and availability rules may not diverge.

## Observation-Only Allow Or Deny Matrix

Observation-only is an executable contract, not a documentation preference.

| Action | Default state in observation-only mode | Unlock rule |
| --- | --- | --- |
| observe | Allowed | No receipt required |
| mode switch | Conditionally allowed | Approval policy must permit the request and yield an active mode-switch receipt bound to the same run or instance scope and the current mode context |
| pause | Denied | Requires an active mode-switch receipt bound to the same run or instance scope and current mode context |
| resume | Denied | Requires an active mode-switch receipt bound to the same run or instance scope and current mode context |
| branch | Denied | Requires an active mode-switch receipt bound to the same run or instance scope and current mode context |
| clone | Denied | Requires an active mode-switch receipt bound to the same run or instance scope and current mode context |
| reset | Denied | Requires an active mode-switch receipt bound to the same run or instance scope and current mode context |
| rollback | Denied | Requires an active mode-switch receipt bound to the same run or instance scope and current mode context |

Additional rules:

- A historical receipt alone never unlocks controlled actions.
- A receipt bound to a different run, a different Glass-Box instance, or a stale mode context is invalid.
- Emergency handling may bypass the regular control path only through an explicit emergency command path if such a path exists.
- Dashboard toggles and CLI commands must call the same auditable backend command path used by the API.

## Deterministic Acceptance Boundary

- Acceptance is gate-first and deterministic.
- A cycle is kept only when required gates pass and no regression is detected.
- Pareto comparison is allowed only after gates pass; it does not override failed gates.

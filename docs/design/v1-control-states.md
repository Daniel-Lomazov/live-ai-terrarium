# V1 Control States

## Purpose

This document is the operator control contract for v1. Streamlit, Rich TUI, CLI, and API must all project these same states and actions over one shared backend.

The design goals are fixed by the questionnaire and plan:

- Observation-only is the default mode.
- `mode switch` is explicit and approval-gated.
- `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` fail closed until an active mode-switch receipt exists for the same run or instance scope and current mode context.
- `observe` remains available by default.
- Surfaces do not implement their own lifecycle logic, approval rules, or recovery behavior.

## Shared Backend Path

All control surfaces use the same path.

```text
surface adapter
  -> canonical command envelope
  -> dispatcher / control backend
  -> approval service when required
  -> append-only audit ledger
  -> orchestrator lifecycle service and/or recovery service
  -> shared query service / read model
  -> surface refresh
```

Implementation rules:

1. The surface owns only scope selection, operator input, and rendering.
2. The dispatcher owns allow-or-deny decisions.
3. The approval service owns approval state and mode-switch receipts.
4. The orchestrator and recovery services own state-changing execution.
5. The query service owns summaries, drill-down data, command receipts, and action availability.
6. `observe` uses the shared query path only; every other action is a canonical command routed through the dispatcher.

## Shared Read Model Requirements

To avoid duplicated surface logic, the shared read model must expose these fields for the selected project, Glass-Box, experiment, run, or cycle scope:

| Field | Why every surface needs it |
| --- | --- |
| `current_mode` | Render observation-only versus control-enabled state without local guesses. |
| `active_mode_switch_receipt` | Prove whether control actions are unlocked for the current scope. |
| `available_actions` | Enable or disable controls from backend truth, not UI heuristics. |
| `deny_reason_by_action` | Explain why a disabled action is blocked. |
| `latest_command_receipts` | Show requested, approved, started, completed, and failed status. |
| `incident_state` | Render proof-critical failures and recovery status. |
| `last_stable_cycle` | Anchor rollback and branch decisions. |
| `rollback_target` | Show the current restore target selected by backend policy. |
| `snapshot_refs` | Link pause and recovery flows to real evidence. |
| `branch_clone_refs` | Show branch-and-continue and clone outcomes without surface-local bookkeeping. |

## Observation-Mode Contract

| Action | Observation-only default | Additional gate | Shared backend path | Surface expectation |
| --- | --- | --- | --- | --- |
| `observe` | Allowed | None | Surface -> query service | Never requires approval. |
| `mode switch` | Allowed to request | Approval policy must permit it and emit an active receipt for the same scope and current mode context | Surface -> dispatcher -> approval service -> audit -> lifecycle -> query service | Show requested, approved, rejected, and active receipt states. |
| `pause` | Denied | Active mode-switch receipt required | Surface -> dispatcher -> audit -> lifecycle -> query service | Disabled until receipt is active; show deny reason when blocked. |
| `resume` | Denied | Active mode-switch receipt required | Surface -> dispatcher -> audit -> lifecycle -> query service | Same semantics as `pause`. |
| `branch` | Denied | Active mode-switch receipt required | Surface -> dispatcher -> audit -> lifecycle -> recovery -> query service | Surface shows resulting branch evidence from backend. |
| `clone` | Denied | Active mode-switch receipt required | Surface -> dispatcher -> audit -> lifecycle -> recovery -> query service | Surface shows new instance reference from backend. |
| `reset` | Denied | Active mode-switch receipt required | Surface -> dispatcher -> audit -> lifecycle -> recovery -> query service | Surface must show target scope and confirmation state from backend. |
| `rollback` | Denied | Active mode-switch receipt required | Surface -> dispatcher -> audit -> lifecycle -> recovery -> query service | Surface must show last stable cycle, rollback target, and outcome receipt. |

Historical approvals do not unlock control. Only an active mode-switch receipt bound to the same run or instance scope and current mode context enables control actions.

## Compact Operator Action Matrix

| Action | Backend owner | API | CLI/TUI | Dashboard | Proof parity |
| --- | --- | --- | --- | --- | --- |
| `observe` | `LAT-024` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |
| `mode switch` | `LAT-009` + `LAT-010` + `LAT-011` + `LAT-025` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |
| `pause` | `LAT-009` + `LAT-010` + `LAT-011` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |
| `resume` | `LAT-009` + `LAT-010` + `LAT-011` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |
| `branch` | `LAT-009` + `LAT-010` + `LAT-011` + `LAT-013` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |
| `clone` | `LAT-009` + `LAT-010` + `LAT-011` + `LAT-013` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |
| `reset` | `LAT-009` + `LAT-010` + `LAT-011` + `LAT-013` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |
| `rollback` | `LAT-009` + `LAT-010` + `LAT-011` + `LAT-013` | `LAT-014` | `LAT-015` | `LAT-016` | `LAT-017` |

## Canonical Control States

| State | Backend indicator | Surface rendering requirements |
| --- | --- | --- |
| Observation-only | `current_mode=observation-only`, no active mode-switch receipt | Show `observe` as available, `mode switch` as requestable, and every other action as disabled with a backend deny reason. |
| Mode-switch requested | Command receipt `requested` or `approval_requested` | Keep control actions disabled. Show pending approval state and request scope. |
| Mode-switch active | Active mode-switch receipt bound to the current scope and mode context | Render control actions from `available_actions`; do not hardcode enabled buttons. |
| Command in flight | Latest command receipt `started` for current scope | Freeze duplicate submissions for the same action and show progress from receipt status only. |
| Paused | Lifecycle state reports paused | Keep observation views fully available and render recovery actions from `available_actions`. |
| Incident open | `incident_state=open` | Show failure banner, evidence links, and recovery actions without hiding current cycle evidence. |
| Recovery executing | Recovery command receipt `started` | Show target branch, clone, reset anchor, or rollback target with backend-owned status text. |
| Recovery completed | Recovery command receipt `completed` | Refresh summaries from the shared read model and show resulting refs or new scope IDs. |

## Proof-Critical Evidence Set

These signals must appear in both the Streamlit and Rich TUI designs.

| Signal | Source of truth |
| --- | --- |
| Task | Canonical cycle record |
| Diff | Canonical cycle record |
| Score | Canonical cycle record |
| Decision | Evaluator result projected into the read model |
| Test result | Canonical cycle record |
| Errors | Canonical cycle record |
| Model identity | Canonical cycle record |
| Prompt reference | Canonical cycle record |
| Token usage | Canonical cycle record |
| Latency | Canonical cycle record |
| CPU usage | Canonical cycle record |
| RAM usage | Canonical cycle record |
| Disk usage | Canonical cycle record |
| Approval status | Approval service and audit projection |
| Active mode-switch receipt | Approval service and audit projection |
| Command receipt timeline | Audit projection |
| Incident state | Incident and recovery projection |
| Last stable cycle | Recovery projection |
| Rollback target | Recovery projection |

## Surface Constraints

- No surface may mutate lifecycle state locally.
- No surface may infer approval state from button history or local cache.
- No surface may compute proof-critical aggregates from raw files on its own.
- All surfaces read canonical records and projections from the shared query service.
- All surfaces submit the same action names: `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, `rollback`.

## Implementation Handoff

Use this document as the contract for `LAT-014`, `LAT-015`, and `LAT-016`.

- API routes should expose the eight canonical actions and the read-model fields above.
- Rich TUI should treat disabled controls and receipt panels as backend projections, not local state machines.
- Streamlit should keep one action rail and one receipt model across all pages.
- Proof tests should compare receipts and read-model outputs across surfaces, not screenshot text alone.
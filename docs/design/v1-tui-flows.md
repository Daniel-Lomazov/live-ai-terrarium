# V1 Rich TUI Flows

## Purpose

This document defines the Rich TUI operator experience for v1. The terminal surface is keyboard-efficient, but it is not allowed to diverge from the Streamlit, CLI, or API semantics.

The TUI uses the same shared backend path:

- Read through the shared query service.
- Submit canonical actions through the dispatcher.
- Render approval and command receipts from the audit projection.
- Keep observation-only as the startup default.

## Layout Model

The TUI should use a persistent multi-pane layout instead of a wizard.

| Region | Required content | Data source |
| --- | --- | --- |
| Header | Scope path, current mode, active mode-switch receipt, incident badge, last stable cycle, rollback target | Shared query service |
| Left pane | Run list and cycle list with decision and health markers | Shared query service |
| Center pane | Summary view or diff view for the selected cycle | Shared query service |
| Right pane | Evidence stack, approval state, available actions, deny reasons | Shared query service |
| Footer | Latest command receipt, action prompt state, refresh status | Audit projection and query service |

This keeps the operator in one screen while still surfacing proof-critical evidence and control state.

## View Set

| View | Operator question | Required content |
| --- | --- | --- |
| Summary | What is the current state of the run? | Stable-cycle progress, decision trail, score trend summary, incident summary, current mode, available actions |
| Cycle | Why did this cycle pass, fail, or get rolled back? | Diff, task, score, decision, test result, errors, model, prompt ref, tokens, latency, CPU/RAM/disk, latest receipts |
| Audit | Is control mode active and what approvals or denials exist? | Active mode-switch receipt, pending approvals, deny reasons, command timeline |
| Recovery | What evidence exists and what recovery actions are safe? | Pause snapshot refs, last stable cycle, rollback target, branch refs, clone refs, reset anchor, incident state |

The operator switches views, but the scope and action semantics stay constant.

## Interaction Model

The TUI has two interaction layers:

1. Browse layer
   - Move between runs and cycles.
   - Switch between Summary, Cycle, Audit, and Recovery views.
   - Refresh via the shared query path.
2. Action layer
   - Open a command palette or action prompt.
   - Choose one of the eight canonical actions.
   - Submit a reason or scope-specific parameter if required.
   - Wait for backend receipt updates in the footer and Audit view.

If later accelerator keys are added, they must populate the same action layer and still dispatch the same canonical action names.

## Core Flows

### Flow 1: Observe By Default

1. Operator starts the TUI.
2. Summary view loads for the selected run.
3. Header shows `observation-only` and no active mode-switch receipt.
4. Right pane shows `observe` as available and the other control actions as blocked with deny reasons.
5. Operator can inspect cycles, diff, score, decision, tests, errors, model, prompt ref, tokens, latency, CPU, RAM, disk, incidents, last stable cycle, and rollback target without approval.

### Flow 2: Request Mode Switch

1. Operator opens the action layer and selects `mode switch`.
2. TUI collects scope and reason.
3. TUI submits the canonical command envelope to the dispatcher.
4. Footer immediately shows `requested` and then `approval_requested`, `approved`, or `rejected`.
5. Audit view shows the same receipt progression.
6. Only when an active mode-switch receipt exists for the same scope and current mode context does the right pane move from blocked controls to backend-provided `available_actions`.

### Flow 3: Pause Or Resume

1. Operator enters the action layer and chooses `pause` or `resume`.
2. TUI checks no local conditions beyond what the read model already exposes.
3. Dispatcher decides whether the action is allowed.
4. Footer and Audit view show receipt progression.
5. If `pause` completes, Recovery view surfaces snapshot refs and any incident context.
6. If `resume` completes, Summary view reflects the new lifecycle state.

### Flow 4: Branch, Clone, Reset, Or Rollback

1. Operator opens Recovery or Cycle view to inspect the selected target scope.
2. Operator enters the action layer and chooses `branch`, `clone`, `reset`, or `rollback`.
3. TUI submits the canonical action and waits for receipts.
4. Recovery view shows backend-owned evidence only:
   - `branch`: branch ref and evidence link
   - `clone`: new instance or run ref
   - `reset`: reset anchor or baseline
   - `rollback`: last stable cycle and rollback target
5. Summary and Cycle views refresh from the shared query path after completion.

## TUI Control Routing

| Action | Trigger in TUI | Enabled when | Backend path | Visible outcome |
| --- | --- | --- | --- | --- |
| `observe` | Browse refresh or action layer | Always | TUI -> query service | Refreshed panes and footer timestamp |
| `mode switch` | Action layer | Request always available; approval decides outcome | TUI -> dispatcher -> approval -> audit -> lifecycle -> query service | Header receipt badge and Audit view receipt timeline |
| `pause` | Action layer | `available_actions` includes `pause` | TUI -> dispatcher -> audit -> lifecycle -> query service | Footer receipt and Recovery snapshot refs |
| `resume` | Action layer | `available_actions` includes `resume` | TUI -> dispatcher -> audit -> lifecycle -> query service | Footer receipt and updated lifecycle state |
| `branch` | Action layer from Cycle or Recovery view | `available_actions` includes `branch` | TUI -> dispatcher -> audit -> lifecycle -> recovery -> query service | Recovery branch ref |
| `clone` | Action layer from Cycle or Recovery view | `available_actions` includes `clone` | TUI -> dispatcher -> audit -> lifecycle -> recovery -> query service | Recovery clone ref |
| `reset` | Action layer from Recovery view | `available_actions` includes `reset` | TUI -> dispatcher -> audit -> lifecycle -> recovery -> query service | Recovery reset anchor and completion receipt |
| `rollback` | Action layer from Cycle or Recovery view | `available_actions` includes `rollback` | TUI -> dispatcher -> audit -> lifecycle -> recovery -> query service | Header rollback target, Recovery panel evidence, and completion receipt |

The TUI never performs shell-side control operations directly.

## Observation-Only Default

The startup state must make the fail-closed rule obvious:

- Header badge: `observation-only`
- Audit view: no active mode-switch receipt
- Right pane: `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` rendered as blocked with backend deny reasons
- Footer hint: `mode switch` is the only control path that can unlock intervention, and it still depends on approval policy

This keeps the terminal surface aligned with the dashboard and the API behavior.

## Proof-Critical Signal Coverage

Every signal below must be visible in this surface.

| Signal | Where it appears in the TUI |
| --- | --- |
| Task | Left pane selection context and Cycle view evidence stack |
| Diff | Center pane Cycle view |
| Score | Summary view, left-pane markers, and Cycle view evidence stack |
| Decision | Summary view, left-pane markers, and Cycle view evidence stack |
| Test result | Summary view and Cycle view evidence stack |
| Errors | Summary incident summary, footer failure snippets, and Cycle view evidence stack |
| Model identity | Cycle view evidence stack |
| Prompt reference | Cycle view evidence stack |
| Token usage | Summary metrics row and Cycle view evidence stack |
| Latency | Summary metrics row and Cycle view evidence stack |
| CPU usage | Summary metrics row and Cycle view evidence stack |
| RAM usage | Summary metrics row and Cycle view evidence stack |
| Disk usage | Summary metrics row and Cycle view evidence stack |
| Approval status | Audit view and right-pane approval state block |
| Active mode-switch receipt | Header badge and Audit view |
| Command receipt timeline | Footer and Audit view timeline |
| Incident state | Header badge, Summary view incident summary, and Recovery view |
| Last stable cycle | Header and Recovery view |
| Rollback target | Header and Recovery view |

## Practical Notes For LAT-015

- Keep one action layer that always emits the canonical action names.
- Prefer read-model-driven enablement over TUI-local conditionals.
- Show deny reasons inline in the right pane so operators do not have to attempt blocked actions to learn policy.
- Keep the footer focused on receipt progression, not on duplicating the entire audit timeline.
- Refresh all panes from the shared query path after every completed or failed action.
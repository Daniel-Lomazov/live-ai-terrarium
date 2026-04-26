# V1 Streamlit Surfaces

## Purpose

This document defines the practical Streamlit operator surface for v1. It is a read-first dashboard over the shared backend, not a second control system.

Non-negotiable rules:

- Every control submits a canonical action to the shared dispatcher.
- Every page reads the same summaries, cycle records, approvals, and receipts from the shared query path.
- Observation-only is the default state on first load.
- Approval state and recovery evidence stay visible alongside the underlying cycle data.

## Global Frame

Every page uses the same frame so operators do not relearn control placement:

| Region | Content | Data source |
| --- | --- | --- |
| Sidebar scope picker | Project, Glass-Box, experiment, run, cycle filters; current mode badge; active receipt badge | Shared query service |
| Top status strip | Current cycle, stable-cycle count, latest decision, incident badge, last stable cycle, rollback target | Shared query service |
| Action rail | `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, `rollback` | Dispatcher-backed command widgets |
| Page body | Summary, drill-down, audit, or recovery content depending on selected page | Shared query service |
| Receipt drawer | Latest requested, approved, rejected, started, completed, failed receipts for current scope | Audit projection |

The action rail does not change command semantics per page. Pages only change the evidence shown after a command runs.

## Page Map

| Page | Primary operator question | Required content | Control behavior |
| --- | --- | --- | --- |
| Run Overview | Is the run healthy, explainable, and on track for 10 stable cycles? | Run summary cards, cycle table, decision trend, score trend, test and incident summary, resource trend strip | Uses global action rail only. |
| Cycle Detail | Why was this cycle accepted, rejected, paused, or rolled back? | Full diff viewer, task, score, decision, tests, errors, model, prompt ref, tokens, latency, CPU/RAM/disk, receipt timeline | Uses global action rail; `branch`, `clone`, and `rollback` operate on the selected cycle scope. |
| Approvals And Audit | Is control mode active, what is pending approval, and what command history exists? | Pending approval queue, active mode-switch receipt, command lifecycle timeline, deny reasons, actor and scope metadata | `mode switch` is the primary action here; other controls remain disabled unless the active receipt exists. |
| Incidents And Recovery | What failed, what evidence was captured, and what can be restored safely? | Incident list, pause snapshot refs, branch refs, clone refs, last stable cycle, rollback target, reset anchor, recovery outcome receipts | `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` remain routed through the same action rail. |

## Run Overview Layout

The default landing page is Run Overview.

Required layout blocks:

1. Summary row
   - Current mode
   - Latest cycle decision
   - Latest score
   - Latest test result
   - Incident state
   - Stable-cycle count toward 10-cycle proof
2. Cycle table
   - One row per cycle
   - Columns: cycle ID, task, decision, score, test result, errors, model identity, prompt reference, token usage, latency, CPU, RAM, disk, diff summary, latest receipt
3. Trends row
   - Score over cycle index
   - Decision trail over cycle index
   - Token and latency trend
   - CPU, RAM, and disk trend
4. Failures and incidents panel
   - Open incident count
   - Last stop condition hit
   - Link to recovery page

This page answers the fast operator question: can I keep observing, or do I need to enter controlled intervention?

## Cycle Detail Layout

Cycle Detail is the proof-critical drill-down view.

| Panel | Required content |
| --- | --- |
| Diff panel | Full diff with file list, change summary, and accepted or rejected decision marker |
| Evidence panel | Task, score, decision, test result, errors, model identity, prompt reference, token usage, latency, CPU, RAM, disk |
| Command panel | Latest receipts for actions affecting this cycle or its run scope |
| Recovery panel | Snapshot refs, last stable cycle, rollback target, branch refs, clone refs |

The page must keep the diff and the evaluator evidence visible at the same time. Operators should not have to switch tabs to answer why a cycle changed and whether it remains safe to keep.

## Approvals And Audit Layout

This page makes approval-gated mode switching explicit and auditable.

Required blocks:

- Active control-state card showing observation-only, approval pending, or control-enabled.
- Pending approval queue with scope, reason, requester, requested time, and current status.
- Active mode-switch receipt card with run or instance scope and mode context.
- Command timeline with `requested`, `approval_requested`, `approved`, `rejected`, `started`, `completed`, and `failed` events.
- Deny-reason panel for blocked `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` actions.

Operators must be able to verify why control is blocked without leaving the dashboard.

## Incidents And Recovery Layout

This page is the implementation-facing recovery surface.

Required blocks:

- Incident summary with stop condition, first detected time, affected scope, and current status.
- Pause-and-snapshot evidence block.
- Last stable cycle block.
- Rollback target block.
- Branch-and-continue evidence block.
- Clone outcome block.
- Reset anchor or baseline block.
- Latest recovery command receipt block.

The page shows recovery evidence first, then the available actions. That matches the evidence-preserving failure policy.

## Streamlit Control Rendering Rules

| Action | Widget location | Enabled when | Backend path | After-action rendering |
| --- | --- | --- | --- | --- |
| `observe` | Global action rail | Always | Streamlit widget -> query service | Refresh cards, tables, and receipts. |
| `mode switch` | Global action rail and Approvals And Audit page | Request always available; approval decides outcome | Streamlit widget -> dispatcher -> approval -> audit -> lifecycle -> query service | Show pending or active receipt in receipt drawer and control-state card. |
| `pause` | Global action rail and Incidents And Recovery page | `available_actions` includes `pause` | Streamlit widget -> dispatcher -> audit -> lifecycle -> query service | Show new receipt and any pause snapshot refs. |
| `resume` | Global action rail and Incidents And Recovery page | `available_actions` includes `resume` | Streamlit widget -> dispatcher -> audit -> lifecycle -> query service | Show resumed state and latest receipt. |
| `branch` | Global action rail, Cycle Detail, Incidents And Recovery | `available_actions` includes `branch` | Streamlit widget -> dispatcher -> audit -> lifecycle -> recovery -> query service | Show branch ref and linked evidence. |
| `clone` | Global action rail, Cycle Detail, Incidents And Recovery | `available_actions` includes `clone` | Streamlit widget -> dispatcher -> audit -> lifecycle -> recovery -> query service | Show new instance or run ref. |
| `reset` | Global action rail and Incidents And Recovery | `available_actions` includes `reset` | Streamlit widget -> dispatcher -> audit -> lifecycle -> recovery -> query service | Show reset anchor and completion receipt. |
| `rollback` | Global action rail, Cycle Detail, Incidents And Recovery | `available_actions` includes `rollback` | Streamlit widget -> dispatcher -> audit -> lifecycle -> recovery -> query service | Show rollback target, last stable cycle, and outcome receipt. |

Disabled controls must show the backend deny reason inline. Streamlit must not guess why a control is blocked.

## Observation-Only Default

Default first-load behavior:

1. Dashboard opens in Run Overview.
2. `observe` is available immediately.
3. `mode switch` is visible as a request action.
4. `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` render disabled.
5. The disable state shows that no active mode-switch receipt exists for the selected scope.
6. The control-state card links directly to Approvals And Audit.

## Proof-Critical Signal Coverage

Every signal below must be visible in this surface.

| Signal | Where it appears in Streamlit |
| --- | --- |
| Task | Run Overview cycle table and Cycle Detail evidence panel |
| Diff | Run Overview diff summary column and Cycle Detail diff panel |
| Score | Summary row, trend row, and Cycle Detail evidence panel |
| Decision | Summary row, decision trend, and Cycle Detail evidence panel |
| Test result | Summary row, cycle table, and Cycle Detail evidence panel |
| Errors | Cycle table, failure panel, and Cycle Detail evidence panel |
| Model identity | Cycle table and Cycle Detail evidence panel |
| Prompt reference | Cycle table and Cycle Detail evidence panel |
| Token usage | Cycle table, trend row, and Cycle Detail evidence panel |
| Latency | Cycle table, trend row, and Cycle Detail evidence panel |
| CPU usage | Cycle table, trend row, and Cycle Detail evidence panel |
| RAM usage | Cycle table, trend row, and Cycle Detail evidence panel |
| Disk usage | Cycle table, trend row, and Cycle Detail evidence panel |
| Approval status | Approvals And Audit page and control-state card |
| Active mode-switch receipt | Sidebar badge, control-state card, and receipt drawer |
| Command receipt timeline | Receipt drawer and Approvals And Audit page |
| Incident state | Top status strip, failure panel, and Incidents And Recovery page |
| Last stable cycle | Top status strip and Incidents And Recovery page |
| Rollback target | Top status strip, Cycle Detail recovery panel, and Incidents And Recovery page |

## Practical Notes For LAT-016

- Build the dashboard from one shared data loader layer so every page reads the same query outputs.
- Keep action widgets in one reusable action-rail component; page-specific buttons should only preselect scope, not change behavior.
- Render receipts and deny reasons from backend payloads, not from Streamlit session state.
- Treat page-local filters as presentation only; they must not become a second state model.
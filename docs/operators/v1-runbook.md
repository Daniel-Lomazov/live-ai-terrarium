# Live AI Terrarium v1 Operator Runbook

## Status

- Audience: operators and developers running the local v1 proof loop
- Basis: `docs/specs/v1-system-contract.md`, `docs/specs/v1-data-contract.md`, `docs/specs/v1-ops-contract.md`, `docs/design/v1-control-states.md`, and the current implementation in `src/live_ai_terrarium/`
- Purpose: describe the implemented startup, observation-first operation, control unlock, stop handling, recovery ordering, and proof prerequisites

## Operating Principle

Operate observation-first.

In the implemented system, `observe` is always available and every other control stays blocked until the backend holds an active mode-switch receipt for the same run scope and the same `mode_context`.

## Startup Sequence

Complete these steps in order before cycle 1.

1. Register the run with `HostOrchestratorService.register_run()` using a pinned image digest and a workspace volume name.
2. Create the run-start reproducibility manifest with `RunEvidenceStore.create_run_manifest()`.
3. Initialize brokered full-log capture with `LogCaptureBroker.ensure_bundle()`.
4. Confirm the run starts in `observation-only` mode through the shared read path.

### Expected startup state

After registration and before any mode switch:

- `current_mode` is `observation-only`.
- `lifecycle_state` is `active`.
- `active_mode_switch_receipt` is empty.
- `available_actions` contains only `observe` and `mode switch`.
- `deny_reason_by_action` explains why `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` are blocked.

## Observation-First Operation

Use the shared read path to inspect the run before unlocking control.

| Surface | Implemented observe path | What it returns |
| --- | --- | --- |
| API | `GET /api/observe/runs/{project}/{glassbox}/{experiment}/{run}` and `GET /api/observe/runs/{project}/{glassbox}/{experiment}/{run}/cycles/{cycle_id}` | JSON-encoded run summary and cycle detail views |
| CLI | `observe` command in the Typer `gb` adapter | JSON output of the same read model |
| Rich TUI | `RichTuiAdapter.observe()` and render views | Shared run summary, cycle detail, audit, and recovery panes |
| Streamlit | `DashboardController.load()` and `render_dashboard()` | Read-first dashboard state and evidence panels |

Observation-first checks to confirm before you unlock control:

1. The run summary shows the correct `task_identity`, seed, model version, and immutable build identity from the reproducibility manifest.
2. The latest cycle summary shows diff, score, decision, test result, error summary, and full-log bundle ref.
3. The audit panel shows the current receipt timeline without gaps.
4. The recovery panel shows the last stable cycle and rollback target you expect.

## Approval-Gated Controls

### Unlock flow

1. Submit `mode switch` for the same project, Glass-Box, experiment, and run scope you intend to control.
2. Use the same `mode_context` you will use for the subsequent control actions.
3. Let the approval service record `command.requested`, `command.approval_requested`, and then `command.approved` before command execution begins.
4. Confirm that the read model now exposes an active mode-switch receipt and that blocked actions moved into `available_actions`.

### What stays blocked until unlock

- `pause`
- `resume`
- `branch`
- `clone`
- `reset`
- `rollback`

Historical receipts do not unlock control. A receipt bound to another run or another `mode_context` does not unlock control.

### Current implementation note

The dispatcher and approval flow are the authoritative unlock path for surface-driven control. `mode switch` is the implemented approval-gated action today. The audit ledger records request, approval, start, completion, and failure receipts on the host side.

## Stop Conditions

The implemented stop-condition set and thresholds are:

| Stop condition | Frozen v1 threshold |
| --- | --- |
| repeated crashes | 3 consecutive crash-terminated cycles within the same run |
| syntax failure | Immediate stop for the affected cycle |
| regression or score drop | Immediate stop when the evaluator detects regression against the last accepted stable cycle for the active run |
| forbidden action attempt | Immediate stop when a denied action or denied tool request is attempted |
| resource overuse | Immediate stop on container hard-limit breach, or on sustained CPU or memory usage above 90 percent of the configured budget for 30 seconds |
| log silence | Stop after 60 seconds without brokered log activity or heartbeat activity during an active cycle |

Treat these thresholds as contract, not operator preference.

## Pause-Then-Snapshot Ordering

Failure handling is evidence-first.

When you are responding to a stop condition or preparing a destructive recovery step, keep this ordering:

1. Pause the run.
2. Capture the failing cycle snapshot.
3. Capture the full workspace snapshot.
4. Choose branch-and-continue, manual rollback, or kill-and-restore.
5. Write the incident report.

This is the implemented order in `RecoveryController`.

### Why the order matters

- The pause step freezes the lifecycle before recovery changes the workspace.
- The cycle snapshot preserves the exact failing cycle state.
- The full snapshot preserves the broader workspace before rollback or restore changes it.
- The incident report captures ordered steps, evidence refs, full-log refs, branch refs, and rollback or restore outcome.

## Branch-And-Continue

Use branch-and-continue when the failing state is worth preserving for inspection or continued experimentation.

### Implemented recovery path

`RecoveryController.branch_and_continue()` performs:

1. `pause`
2. failing cycle snapshot capture
3. full snapshot capture
4. branch evidence write
5. incident bundle write

### Outputs you should expect

- a pause receipt from the host orchestrator
- a failing-cycle snapshot ref
- a full snapshot ref
- a branch evidence JSON file under the host mirror tree
- an incident record and incident report with ordered steps and full-log refs

### Important branch rule

The branch evidence written by the recovery controller records `outer_repo_branch_created=false`.

That means branch-and-continue preserves a sandbox-inner divergent state plus host mirror evidence. It does not create an outer repository feature branch.

### Current implementation note

`branch` exists in the shared surface contract and in surface parity tests. The implemented proof-grade branch-and-continue behavior today is the recovery-controller workflow above.

## Manual Rollback

Use manual rollback when a known last accepted stable cycle exists and you need to restore the workspace to that point.

### Implemented rollback path

`RecoveryController.manual_rollback()` performs:

1. `pause`
2. failing cycle snapshot capture
3. full snapshot capture
4. host orchestrator `rollback` to the requested target cycle id
5. cycle snapshot restore of the last accepted stable cycle back into the workspace
6. incident bundle write

### Required inputs

- the failing `cycle_scope`
- the workspace directory to restore
- an `incident_id`
- the stop-condition type and trigger detail
- `last_accepted_cycle_id`
- any full-log refs that belong in the incident bundle

### Outputs you should expect

- a rollback receipt whose `target_cycle_id` matches the last accepted stable cycle
- restored workspace files from the accepted cycle snapshot
- an incident report that records the rollback target and restore manifest ref
- cycle-to-audit linkage and full-log refs that remain resolvable by proof consumers

The rollback target is always the last accepted stable cycle for the active run.

## Kill-And-Restore

Use kill-and-restore when the sandbox is unsafe or unrecoverable and you need to restore from a full snapshot manifest rather than from a single accepted cycle snapshot.

`RecoveryController.kill_and_restore()` performs:

1. `pause`
2. failing cycle snapshot capture
3. full snapshot capture
4. host orchestrator `restore` to the full snapshot id
5. workspace restore from the supplied full snapshot manifest
6. incident bundle write

`restore` is an internal recovery lifecycle operation, not a canonical operator surface action.

## Proof-Gate Prerequisites

Do not declare proof success until every prerequisite below is satisfied.

1. `docs/reviews/proof-clearance-status.yaml` exists.
2. Its `status` field is `cleared`.
3. The run-start reproducibility manifest already exists before cycle 1.
4. The manifest contains immutable build identity: outer repo commit SHA and container image digest.
5. Brokered full-log bundles exist for the run and the relevant cycles.
6. Cycle-to-audit linkage files exist and verify against the canonical hash-chained audit ledger.
7. Manual rollback evidence is preserved when rollback proof is in scope.
8. Branch evidence is preserved when branch-and-continue occurred.
9. The proof bundle shows zero unrecoverable failures across the ten-cycle proof.

### Proof harness behavior

The end-to-end proof harness in `tests/e2e/test_ten_cycle_proof.py` fails closed when:

- the proof-clearance file is missing, or
- the proof-clearance status is anything other than `cleared`.

The current clearance artifact in `docs/reviews/proof-clearance-status.yaml` is already set to `status: cleared`, so keep it current if the reviewed runtime or control assumptions change.

## Operator Short List

Use this condensed sequence during normal operation:

1. Start in observation-only and verify manifest, logs, current mode, and last stable cycle through the shared read path.
2. Request `mode switch` only when you need to perform a control action and keep the same run scope and `mode_context` through the action.
3. Treat stop conditions as immediate evidence-preservation events, not as optional warnings.
4. Preserve order: pause, snapshot, recover, report.
5. Prefer branch-and-continue when you need to preserve a failing path for inspection; prefer manual rollback when you need to restore the last accepted stable state.
6. Do not call proof complete until the clearance file is `cleared` and the manifest, logs, audit chain, and recovery evidence are all present.
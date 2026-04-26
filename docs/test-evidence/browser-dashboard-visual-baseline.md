# LAT-018 Browser Dashboard Visual Baseline

- Date: 2026-04-26
- Task: LAT-018
- Plan: 20260426-live-ai-terrarium-v1
- Target: `src/live_ai_terrarium/adapters/dashboard/preview_app.py`
- Preview URL: `http://localhost:8505`

## Baseline Capture Method

- The preview app was launched locally and confirmed reachable at `http://localhost:8505`.
- The browser page opened successfully in VS Code.
- This environment does not expose browser DOM inspection or screenshot capture tools, so this baseline is a textual render baseline derived from the launched app plus `streamlit.testing.v1.AppTest` output against the same entrypoint.

## Default View Baseline

- Page title: `Live AI Terrarium`
- Caption: `Read-first dashboard over the shared query and command backend.`
- Sidebar control: one `Cycle` selectbox with options `cycle-0001` through `cycle-0010`, defaulting to `cycle-0010`
- Main section order:
  1. `Scope`
  2. `Status`
  3. `Action Rail`
  4. `Run Overview`
  5. `Cycle Detail`
  6. `Approvals And Audit`
  7. `Incidents And Recovery`

## Proof-Critical Baseline Content

### Run Overview

- Summary cards:
  - `Current mode: observation-only`
  - `Latest cycle decision: rejected`
  - `Latest score: 0.41`
  - `Latest test result: failed`
  - `Incident state: open`
  - `Stable-cycle count: 9/10`
- Failures panel:
  - `open_incident_count: 1`
  - `last_stop_condition: rolled back to last accepted stable cycle cycle-0009`

### Cycle Detail, default `cycle-0010`

- Diff block text: `Updated worker logic for cycle-0010.`
- Evidence fields visible:
  - `decision: rejected`
  - `score: 0.41`
  - `test_result: failed`
  - `error_summary: regression detected in smoke tests`
  - `model_identity: gpt-5.4`
  - `prompt_ref: prompts/cycle-0010.json`
  - `total_tokens: 180`
  - `latency_ms: 910`
  - `cpu_percent: 52.0`
  - `ram_mb: 266`
  - `disk_mb: 1034`
  - `rollback_target: cycle-0009`
  - `branch_ref: mirrors/branches/branch-syntax-failure-cycle-0010.json`
  - `recovery_outcome: rolled back to last accepted stable cycle cycle-0009`

### Approvals And Audit

- Control-state block:
  - `control_state: observation-only`
  - `pending_approval_count: 1`
  - `active_mode_switch_receipt: null`
- Timeline statuses present in order:
  - `requested`
  - `approval_requested`
  - `approved`
  - `completed`

### Incidents And Recovery

- Incident block:
  - `incident_state: open`
  - `incident_id: incident-syntax-failure`
  - `incident_report_ref: incidents/incident-syntax-failure/report.json`
  - `last_stable_cycle: cycle-0009`
  - `rollback_target: cycle-0009`
  - `reset_anchor: cycle-0009`
  - `recovery_outcome: rolled back to last accepted stable cycle cycle-0009`
- Evidence refs visible:
  - `snapshots/cycles/cycle-0010/manifest.json`
  - `snapshots/full/snapshot-incident-syntax-failure/manifest.json`
  - `snapshots/cycles/cycle-0009/manifest.json`
  - `mirrors/branches/branch-syntax-failure-cycle-0010.json`

## Alternate Cycle Baseline

- Selecting `cycle-0001` updates the cycle detail view to:
  - diff block `Updated worker logic for cycle-0001.`
  - `decision: accepted`
  - `score: 0.91`
  - `test_result: passed`
  - `prompt_ref: prompts/cycle-0001.json`
  - `total_tokens: 162`

## Baseline Notes

- No pixel-perfect screenshot baseline was captured in this run.
- This file records the textual and structural baseline that was actually observed from the launched preview harness.
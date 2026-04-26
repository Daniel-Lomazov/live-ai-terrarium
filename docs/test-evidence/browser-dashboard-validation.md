# LAT-018 Browser Dashboard Validation

- Date: 2026-04-26
- Task: LAT-018
- Plan: 20260426-live-ai-terrarium-v1
- Target: `src/live_ai_terrarium/adapters/dashboard/preview_app.py`
- Preview URL: `http://localhost:8505`

## Method

- Launched the Streamlit preview harness from the workspace virtual environment with `PYTHONPATH=src`.
- Confirmed the local preview URL responded with HTTP 200 and opened successfully in the VS Code browser.
- Used `streamlit.testing.v1.AppTest` against the same entrypoint to validate rendered interaction state because browser DOM and screenshot tools are not enabled in this environment.

## Launch Evidence

- Streamlit published `http://localhost:8505`.
- `Invoke-WebRequest http://localhost:8505` returned `StatusCode : 200`.
- `open_browser_page` opened the local URL successfully.

## Validation Matrix Results

### Cycle drill-down visibility

Status: pass

- The sidebar cycle selector rendered options for `cycle-0001` through `cycle-0010`.
- Selecting `cycle-0001` rendered a cycle detail panel matching the canonical preview record:
  - diff summary: `Updated worker logic for cycle-0001.`
  - decision: `accepted`
  - score: `0.91`
  - test result: `passed`
  - prompt ref: `prompts/cycle-0001.json`
- Selecting `cycle-0010` rendered a cycle detail panel matching the canonical preview record:
  - diff summary: `Updated worker logic for cycle-0010.`
  - decision: `rejected`
  - score: `0.41`
  - test result: `failed`
  - error summary: `regression detected in smoke tests`
  - rollback target: `cycle-0009`

### Sensitive control visibility

Status: pass

- The action rail rendered `observe` and `mode switch` as enabled.
- The sensitive controls `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` rendered disabled.
- Each disabled control surfaced the same inline deny reason: `Active mode-switch receipt required for this scope.`
- The Approvals And Audit section rendered:
  - `control_state: observation-only`
  - `pending_approval_count: 1`
  - deny reasons for each sensitive control
  - mode-switch and rollback lifecycle statuses: `requested`, `approval_requested`, `approved`, `completed`

### Incident and rollback evidence

Status: pass

- The Incidents And Recovery section rendered:
  - `incident_state: open`
  - `incident_id: incident-syntax-failure`
  - `incident_report_ref: incidents/incident-syntax-failure/report.json`
  - snapshot refs for `cycle-0010`, the incident full snapshot, and `cycle-0009`
  - branch evidence `mirrors/branches/branch-syntax-failure-cycle-0010.json`
  - `last_stable_cycle: cycle-0009`
  - `rollback_target: cycle-0009`
  - `recovery_outcome: rolled back to last accepted stable cycle cycle-0009`
- The cycle-0010 detail panel repeated the rollback target, snapshot refs, branch ref, and recovery outcome.

## Design Contract Notes

- Match: the page exposes all four proof-critical surfaces in one render pass: Run Overview, Cycle Detail, Approvals And Audit, and Incidents And Recovery.
- Match: observation-only default state and sensitive-action deny reasons are visible without executing a control.
- Gap: the preview harness exposes cycle selection in the sidebar, but the full scope payload renders in a body `Scope` section instead of a fuller sidebar scope picker as described in `docs/design/v1-streamlit-surfaces.md`.
- Gap: the Cycle Detail view renders a diff summary code block, not a full diff viewer with file list.
- Gap: the Run Overview table only populates rich diff and evidence columns for the currently selected cycle row. Observed populated rows were `cycle-0001` when cycle 1 was selected and `cycle-0010` when cycle 10 was selected.

## Verdict

- Browser launch succeeded.
- The LAT-018 visibility scenarios passed against the canonical preview data.
- The preview harness still shows layout and evidence-density gaps relative to the design contract.
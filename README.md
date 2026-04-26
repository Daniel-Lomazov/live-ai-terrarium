# Live AI Terrarium

Live AI Terrarium is a local-first Glass-Box orchestration project built around one strict rule: proof comes before control.

The current `v1.0.1` public release carries forward the `v1.0.0` proof baseline with cleaner package metadata, clearer public-facing docs, and a more usable repository front door.

The repository currently delivers a single-host Milestone 1 baseline with:

- one hardened sandbox runtime boundary
- one shared command path across API, CLI/TUI, and Streamlit
- one shared read model for run, cycle, audit, and recovery state
- observation-first control with auditable mode switching
- proof-grade evidence capture, rollback, and branch-and-continue records
- a validated ten-cycle proof harness and browser-tested dashboard preview

## What This Repository Contains

The repository is organized around a small number of proof-critical slices:

- `src/live_ai_terrarium/`: runtime, control, audit, query, recovery, storage, and operator-surface code
- `tests/`: contract, adapter, storage, recovery, and end-to-end proof coverage
- `docs/specs/`: frozen v1 contracts
- `docs/runtime/`, `docs/operators/`, `docs/reviews/`: runtime rules, operator runbook, and proof-clearance reviews
- `docs/milestones/`, `docs/releases/`, `docs/test-evidence/`: release bundle, proof checklist, and browser evidence
- `infra/`: runtime profile and command-catalog inputs

## Release Status

The repository has been published with:

- milestone tag `milestone/v1-proof-complete`
- foundational proof release tag `v1.0.0`
- current public release tag `v1.0.1`

The release and proof bundle lives in:

- `docs/milestones/m1-proof-checklist.md`
- `docs/releases/v1.0.1.md`
- `docs/releases/v1.0.0.md`
- `docs/test-evidence/browser-dashboard-validation.md`
- `docs/test-evidence/browser-dashboard-visual-baseline.md`

## Local Setup

Python `3.12+` is required.

Install the project with all currently used extras:

```powershell
python -m pip install -e ".[api,cli,dashboard,test]"
```

If you want an isolated environment first:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[api,cli,dashboard,test]"
```

## Validate The Repository

Run the full test suite:

```powershell
python -m pytest
```

Run the proof-oriented slice that backs the release evidence:

```powershell
python -m pytest tests/e2e tests/adapters/test_dashboard_preview_app.py tests/adapters/test_dashboard_views.py -q
```

The recorded release validation result for that slice is `30 passed in 14.04s`.

## Run The Dashboard Preview

The repository includes a runnable Streamlit preview backed by proof-shaped in-memory data.

Launch it with:

```powershell
python -m streamlit run src/live_ai_terrarium/adapters/dashboard/preview_app.py --server.port 8505
```

What the preview is for:

- inspect cycle drill-down across ten sample cycles
- review approval and audit state
- inspect rollback and incident evidence panels
- validate dashboard behavior without needing a live orchestrator run

## Current Surface Model

The project already implements three operator surfaces over the same backend contract:

- FastAPI adapter in `src/live_ai_terrarium/adapters/api/`
- Typer CLI and Rich TUI in `src/live_ai_terrarium/adapters/cli/`
- Streamlit dashboard in `src/live_ai_terrarium/adapters/dashboard/`

The dashboard preview is the current out-of-the-box runnable UI entrypoint. The API and CLI/TUI are implemented as adapters intended to be wired into the shared backends, and their behavior is validated through tests.

## Core Operating Model

The v1 control model is intentionally conservative:

- `observe` is available by default
- `mode switch` is the approval-gated unlock action
- `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` fail closed until an active mode-switch receipt exists for the same scope and `mode_context`

Recovery is evidence-first:

1. pause
2. snapshot the failing cycle
3. snapshot the workspace
4. branch-and-continue, rollback, or restore
5. write incident evidence

## Start Reading Here

If you want the shortest path through the codebase, start with these files:

- `docs/releases/v1.0.0.md`
- `docs/milestones/m1-proof-checklist.md`
- `docs/v1-architecture-brief.md`
- `docs/operators/v1-runbook.md`
- `src/live_ai_terrarium/query/service.py`
- `src/live_ai_terrarium/control/dispatcher.py`
- `src/live_ai_terrarium/adapters/dashboard/preview_app.py`
- `tests/e2e/test_ten_cycle_proof.py`

## Notes

- The sanctioned sandbox egress path is `/workspace/.gb/outbox`.
- Sandbox-inner branch evidence is mirrored as host-controlled evidence; it is not outer repository history.
- The current root branch is `main`; milestone tags and release tags are the only outer-repository release markers.
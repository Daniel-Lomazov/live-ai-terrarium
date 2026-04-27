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

## Start Here

If you are new to the repository, use this order:

1. Read this README for setup, Docker usage, validation, and preview launch.
2. Read `docs/README.md` for the documentation map.
3. Read `docs/releases/v1.0.1.md` if you want the current public release summary.
4. Read `docs/milestones/m1-proof-checklist.md` if you want the original proof evidence behind the project baseline.

Choose the path that matches what you need:

- I want to run something now: use the local setup section, then launch the Streamlit preview.
- I want to validate the sandbox baseline: build the Glass-Box Docker image and run the Docker sanity check.
- I want to understand the runtime contract: read `docs/runtime/sandbox-runtime-contract.md`.
- I want the operator workflow: read `docs/operators/v1-runbook.md`.
- I want the architecture and code map: read `docs/v1-architecture-brief.md` and then the files listed later in this README.

## What This Repository Contains

The repository is organized around a small number of proof-critical slices:

- `src/live_ai_terrarium/`: runtime, control, audit, query, recovery, storage, and operator-surface code
- `tests/`: contract, adapter, storage, recovery, and end-to-end proof coverage
- `docs/specs/`: frozen v1 contracts
- `docs/runtime/`, `docs/operators/`, `docs/reviews/`: runtime rules, operator runbook, and proof-clearance reviews
- `docs/milestones/`, `docs/releases/`, `docs/test-evidence/`: release bundle, proof checklist, and browser evidence
- `infra/`: runtime profile and command-catalog inputs

## What You Can Actually Do With This Repo Today

The repository is strongest in three user-facing flows right now:

- inspect the proof-backed architecture, contracts, and evidence
- build and sanity-check the hardened Glass-Box container baseline
- launch the Streamlit preview and inspect proof-shaped run, cycle, audit, and rollback data

What is implemented but not yet packaged as a one-command product:

- the FastAPI surface exists and is validated through tests
- the Typer CLI and Rich TUI exist and are validated through tests
- the host orchestrator, approval flow, recovery flow, and shared query layer exist as implementation modules

What this means in practice:

- this repo is ready for exploration, validation, and extension
- the Streamlit preview is the easiest runnable entry point
- the Docker image is the sandbox baseline, not a full application launcher

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

## Prerequisites

For the common local workflows, you need:

- Python `3.12+`
- Docker Desktop or a compatible Docker engine if you want to build the sandbox image
- PowerShell on Windows for the documented command examples

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

## Build The Glass-Box Image

The sandbox image definition lives in `infra/docker/glassbox/Dockerfile`.

Build it from the repository root with:

```powershell
docker build -f infra/docker/glassbox/Dockerfile -t live-ai-terrarium-glassbox:v1 .
```

What this image is for:

- validating the hardened sandbox baseline
- matching the no-network, non-root, one-workspace contract described in the runtime docs
- acting as the container recipe that the host orchestrator expects to register by pinned digest

What this image is not:

- it is not the Streamlit dashboard image
- it is not an API server image
- it does not boot the product automatically; its default command is `sleep infinity`

If you only want to explore the repository UI and evidence flows, you do not need Docker first. The Streamlit preview can be launched directly from the local Python environment.

## Sanity-Check The Dockerfile Locally

If you want to verify the image behavior directly, create a dedicated workspace mount first.

```powershell
New-Item -ItemType Directory -Force .sandbox-workspace/.gb/outbox, .sandbox-workspace/.gb/cycles | Out-Null
$workspace = Join-Path (Get-Location) ".sandbox-workspace"
docker run --rm --network none --mount "type=bind,source=$workspace,target=/workspace" live-ai-terrarium-glassbox:v1 python -c "import os; print({'uid': os.getuid(), 'outbox': os.path.isdir('/workspace/.gb/outbox'), 'cycles': os.path.isdir('/workspace/.gb/cycles')})"
```

Expected result:

- the reported `uid` is not `0`
- `/workspace/.gb/outbox` exists
- `/workspace/.gb/cycles` exists

Why the extra workspace directory matters:

- bind-mounting the repository root directly over `/workspace` hides the directories created in the image layer
- the runtime contract expects the mounted workspace to expose `.gb/outbox` and `.gb/cycles`
- the host orchestrator normally provisions that workspace or volume for you

## Fastest First Run

If you want the quickest useful experience with the repository, do this:

1. Create and activate a Python virtual environment.
2. Install `.[api,cli,dashboard,test]`.
3. Launch the Streamlit preview.
4. Read the run summary, cycle drill-down, and rollback evidence in the UI.

Command sequence:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[api,cli,dashboard,test]"
python -m streamlit run src/live_ai_terrarium/adapters/dashboard/preview_app.py --server.port 8505
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

## Documentation Map

Use these documents for the next level of detail:

- `docs/README.md`: top-level documentation map
- `docs/releases/v1.0.1.md`: current maintenance release summary
- `docs/releases/v1.0.0.md`: original proof-backed baseline release
- `docs/milestones/m1-proof-checklist.md`: proof checklist and evidence inventory
- `docs/runtime/sandbox-runtime-contract.md`: sandbox boundary and Docker runtime contract
- `docs/operators/v1-runbook.md`: operator workflow and recovery path
- `docs/v1-architecture-brief.md`: architecture overview

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

- `docs/README.md`
- `docs/releases/v1.0.1.md`
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
- The sandbox baseline image is defined in `infra/docker/glassbox/Dockerfile` and is expected to run with `--network none`.
- Sandbox-inner branch evidence is mirrored as host-controlled evidence; it is not outer repository history.
- The current root branch is `main`; milestone tags and release tags are the only outer-repository release markers.
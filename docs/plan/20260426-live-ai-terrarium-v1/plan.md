# Live AI Terrarium v1 Plan

Plan ID: 20260426-live-ai-terrarium-v1

Objective: Build a local-first v1.0 Live AI Terrarium / Glass-Box from scratch in `c:/Users/lomaz/live-ai-terrarium` with one outer repo on `main`, one Docker container per Glass-Box, one shared backend for API plus CLI/TUI plus Streamlit, deterministic gate-first evaluation, ten stable cycles, rollback, and full observability plus reproducibility.

Summary:

| Metric | Value |
| --- | --- |
| Total tasks | 25 |
| Total waves | 10 |
| Wave 1 parallelism | 4 tasks |
| Risk | High |
| Representative critical path | LAT-001 -> LAT-005 -> LAT-023 -> LAT-011 -> LAT-025 -> LAT-024 -> LAT-014 -> LAT-017 -> LAT-021 -> LAT-022 |

## Targeted Tightening

| Concern | Owning tasks | Concrete repair |
| --- | --- | --- |
| Brokered full-log capture and append-only host storage | `LAT-011`, `LAT-025` | `LAT-011` exposes host-side broker hooks and `LAT-025` persists append-only run-scoped full-log bundles in host-controlled storage. |
| Run-start reproducibility records | `LAT-001`, `LAT-006`, `LAT-025` | `LAT-001` freezes the contract, `LAT-006` defines the schema, and `LAT-025` persists task identity, seed, limits, model version, required outer repo commit SHA and container image digest, optional release tag and human-readable image name supplemental labels, and runtime-profile plus command-catalog hash or embedded snapshot before cycle 1. |
| Cycle-to-audit linkage and read-side proof consumption | `LAT-010`, `LAT-024`, `LAT-025`, `LAT-017` | Audit receipts come from `LAT-010`, linkage manifests from `LAT-025`, shared projections from `LAT-024`, and proof enforcement from `LAT-017`. |
| Observation-only default and auditable mode switching | `LAT-009`, `LAT-010`, `LAT-014`, `LAT-015`, `LAT-016`, `LAT-019` | The dispatcher owns an executable allow-or-deny contract: `observe` is allowed by default, `mode switch` is approval-gated, the remaining control actions stay denied until an active mode-switch receipt bound to the same run or instance scope and current mode context exists, a historical receipt alone does not unlock control actions, and the review lane verifies the receipts before proof execution. |
| API, CLI/TUI, and dashboard action parity | `LAT-002`, `LAT-014`, `LAT-015`, `LAT-016`, `LAT-017` | The design docs now carry one compact operator-action matrix and the proof harness checks parity for `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback`. |

## Selected Operator Parity Matrix

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

Observation-mode command contract:

- `observe` is allowed by default in observation-only mode.
- `mode switch` is allowed only when the approval policy permits it and an active mode-switch receipt bound to the same run or instance scope and current mode context is emitted.
- `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` are denied until an active mode-switch receipt bound to the same run or instance scope and current mode context exists; a historical receipt alone does not unlock control actions.
- Emergency handling may flow only through an explicit emergency command path if that path is separately defined, policy-gated, and audited.

Assumptions:

- Python-first v1 using FastAPI, Pydantic, Typer, Rich, Streamlit, pytest, and Docker CLI.
- Host-controlled state root is `%LOCALAPPDATA%/LiveAITerrarium/state`; backups are under `%LOCALAPPDATA%/LiveAITerrarium/backups`.
- Audit events use SHA-256 chaining per run.
- The no-regression baseline is the last accepted stable cycle.
- Per-cycle snapshots happen every cycle; full workspace snapshots happen every 5 cycles and on stop conditions.
- Milestone tags use `milestone/v1-*`; the final release tag is annotated `v1.0.0`.
- The only sanctioned sandbox egress path is `/workspace/.gb/outbox`; no other sandbox-host shared mount or direct host path is available in v1.
- Repeated crashes default to 3 consecutive crash-terminated cycles per run; log silence defaults to 60 seconds without brokered log or heartbeat activity during an active cycle.
- Resource overuse defaults to container hard-limit breach or sustained CPU or memory usage above 90 percent of the configured budget for 30 seconds.
- Branch-and-continue creates a sandbox-inner git branch plus external mirror evidence; the outer repository remains single-branch `main` except for annotated milestone and release tags.

## Wave 1

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-001 | gem-documentation-writer | None | None | `docs/specs/v1-system-contract.md`, `docs/specs/v1-data-contract.md`, `docs/specs/v1-ops-contract.md` | Frozen v1 defaults for IDs, export boundary, stop-condition thresholds, snapshot cadence, regression baseline, branch semantics, immutable build identity, and the canonical action list. | Cross-check against questionnaire, AGENTS.md, architecture brief, and research docs, and confirm the explicit allow-or-deny contract for `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback`. |
| LAT-002 | gem-designer | None | None | `docs/design/v1-streamlit-surfaces.md`, `docs/design/v1-tui-flows.md`, `docs/design/v1-control-states.md` | Shared dashboard and TUI information architecture. | Verify every control maps to the shared backend path and every proof-critical signal appears in both surfaces. |
| LAT-003 | gem-devops | None | None | `.gitignore`, `.gitattributes`, `CHANGELOG.md` | Outer repo initialized on `main` with ignore policy for runtime artifacts and backups. | Verify root git repo exists on `main` and ignored paths cover mirrors, snapshots, exports, state, and backups. |
| LAT-004 | gem-devops | None | None | `docs/releases/tag-strategy.md`, `docs/milestones/README.md`, `docs/releases/README.md` | Written tag, release, and outer-versus-inner branch discipline. | Verify milestone tags and release tags are distinct, annotated, and keep sandbox branch evidence out of the outer branch graph. |

## Wave 2

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-005 | gem-implementer | LAT-001, LAT-003 | None | `pyproject.toml`, `src/live_ai_terrarium/__init__.py`, `tests/conftest.py` | Base Python package and pytest scaffold. | Validate imports and base test bootstrap. |
| LAT-006 | gem-implementer | LAT-001, LAT-003 | None | `src/live_ai_terrarium/contracts/ids.py`, `src/live_ai_terrarium/contracts/records.py`, `tests/contracts/test_ids_records.py` | Canonical ID, cycle, incident, and annotation contracts. | Run contract tests for IDs and required record fields. |
| LAT-007 | gem-devops | LAT-001, LAT-003 | None | `infra/docker/glassbox/Dockerfile`, `infra/security/runtime-profile.yaml`, `infra/security/command-specs.yaml` | Hardened single-container runtime scaffold and allowlist. | Validate non-root, no-network, and command-catalog restrictions. |
| LAT-008 | gem-implementer | LAT-001, LAT-003 | None | `src/live_ai_terrarium/storage/paths.py`, `src/live_ai_terrarium/storage/filesystem.py`, `tests/storage/test_filesystem_paths.py` | Host-controlled state path API for records, snapshots, mirrors, incidents, exports, and backups. | Run storage-path tests with Windows-style expectations. |

## Wave 3

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-023 | gem-implementer | LAT-005, LAT-007, LAT-008 | None | `src/live_ai_terrarium/orchestrator/boundary.py`, `src/live_ai_terrarium/storage/exports.py`, `tests/sandbox_contract/test_boundary_export_contract.py` | Executable boundary/export contract with one outbox path, append-only egress, and negative-path tests. | Run boundary contract tests for no extra mounts, blocked host access, and denied artifact rewrite. |
| LAT-009 | gem-implementer | LAT-005, LAT-006 | None | `src/live_ai_terrarium/control/commands.py`, `src/live_ai_terrarium/control/dispatcher.py`, `tests/control/test_dispatcher.py` | Canonical command envelope and shared dispatcher with an executable allow-or-deny observation-mode contract. | Run normalization, idempotency, invalid-command, and fail-closed pre-mode-switch denial tests. |

## Wave 4

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-010 | gem-implementer | LAT-006, LAT-008, LAT-009 | None | `src/live_ai_terrarium/audit/ledger.py`, `src/live_ai_terrarium/control/approval.py`, `tests/audit/test_ledger_approval.py` | Hash-chained append-only audit ledger and approval flow. | Run tamper-detection and approval-precondition tests. |
| LAT-011 | gem-implementer | LAT-005, LAT-007, LAT-008, LAT-023 | None | `src/live_ai_terrarium/orchestrator/service.py`, `src/live_ai_terrarium/orchestrator/runtime.py`, `src/live_ai_terrarium/gateway/service.py` | Host-side orchestrator, boundary/export enforcement, and model gateway services. | Validate lifecycle signatures, outbox-only egress, and per-run gateway request rules. |
| LAT-012 | gem-implementer | LAT-006, LAT-007, LAT-008, LAT-023 | None | `src/live_ai_terrarium/agent/runner.py`, `src/live_ai_terrarium/evaluation/gates.py`, `tests/agent/test_runner_gates.py` | Single-agent runner with deterministic gates, stable-cycle counting, and selected stop-condition detectors. | Run tests for repeated crashes, syntax fail, score drop, forbidden action attempt, resource overuse, log silence, and accepted-cycle counting. |

## Wave 5

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-013 | gem-implementer | LAT-008, LAT-010, LAT-011, LAT-012 | None | `src/live_ai_terrarium/recovery/snapshots.py`, `src/live_ai_terrarium/recovery/recovery.py`, `tests/recovery/test_recovery.py` | Failure-response controller, evidence-first recovery, snapshots, mirror updates, branch evidence, and incident bundling. | Run tests for pause-then-snapshot ordering, branch-and-continue, manual rollback, and restore reconstruction. |
| LAT-025 | gem-implementer | LAT-006, LAT-007, LAT-008, LAT-010, LAT-011, LAT-012 | None | `src/live_ai_terrarium/storage/run_evidence.py`, `src/live_ai_terrarium/storage/log_capture.py`, `tests/storage/test_run_evidence.py` | Run-start reproducibility manifest with immutable build identity, brokered append-only full-log capture, cycle-to-audit linkage, and proof-bundle inputs for later review and milestone proof tasks. | Run tests covering manifest creation before cycle 1, immutable build-identity capture, append-only log writes, cycle-to-audit linkage resolution, and proof-consumer lookup failures. |

## Wave 6

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-019 | gem-reviewer | LAT-007, LAT-010, LAT-011, LAT-023, LAT-025 | None | `docs/reviews/security-readiness-v1.md`, `docs/reviews/runtime-boundary-audit.md`, `docs/reviews/proof-clearance-status.yaml` | Focused boundary checklist, proof-gating security review, and structured proof-clearance status covering export boundaries, observation-only default, auditable mode switching, and run-evidence completeness. | Review boundary/export contract, gateway separation, audit integrity, mode-switch receipts, reproducibility manifest completeness, outer-versus-inner git separation, and emit cleared or blocked proof status. |
| LAT-024 | gem-implementer | LAT-006, LAT-008, LAT-010, LAT-012, LAT-013, LAT-025 | None | `src/live_ai_terrarium/query/service.py`, `src/live_ai_terrarium/query/read_models.py`, `tests/query/test_read_models.py` | Shared query/read-model service for summaries, cycle detail, audit status, reproducibility manifest summaries, full-log bundle references, and recovery-backed reversibility views. | Run read-model tests against canonical records, audit events, reproducibility manifests, log linkage manifests, and recovery artifacts, and confirm no surface needs direct filesystem reads or its own aggregate logic. |

## Wave 7

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-014 | gem-implementer | LAT-002, LAT-009, LAT-010, LAT-011, LAT-013, LAT-024 | None | `src/live_ai_terrarium/adapters/api/app.py`, `src/live_ai_terrarium/adapters/api/routes.py`, `tests/adapters/test_api.py` | Local API adapter exposing `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` over the shared command and read paths. | Run API adapter tests for eight-action parity, pre-mode-switch deny receipts, and shared read-model parity. |
| LAT-015 | gem-implementer | LAT-002, LAT-009, LAT-010, LAT-011, LAT-013, LAT-024 | None | `src/live_ai_terrarium/adapters/cli/gb.py`, `src/live_ai_terrarium/adapters/cli/tui.py`, `tests/adapters/test_cli_tui.py` | `gb` CLI and Rich TUI over the shared command and read paths with the same semantics for `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` as the API. | Run CLI and TUI parity tests over dispatcher receipts, eight-action coverage, and shared read models. |
| LAT-016 | gem-implementer | LAT-002, LAT-009, LAT-010, LAT-011, LAT-013, LAT-024 | None | `src/live_ai_terrarium/adapters/dashboard/streamlit_app.py`, `src/live_ai_terrarium/adapters/dashboard/views.py`, `tests/adapters/test_dashboard_views.py` | Streamlit dashboard over the shared command and read paths with proof-critical drill-down plus action parity for `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback`. | Run dashboard rendering and action-parity tests against canonical sample data, shared read-model outputs, and the same backend command path. |

## Wave 8

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-017 | gem-implementer | LAT-013, LAT-014, LAT-015, LAT-016, LAT-019, LAT-025 | None | `tests/e2e/test_ten_cycle_proof.py`, `tests/e2e/test_rollback_flow.py`, `tests/e2e/test_surface_parity.py` | Ten-cycle proof suite with canonical-record, immutable build identity, full-log, reversibility, and parity assertions for `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback`. | Run the proof suite, capture the canonical record inventory, confirm the machine-readable proof-clearance status gates execution, verify the proof bundle includes the required immutable-build reproducibility manifest and log-linkage artifacts, and prove disallowed commands fail closed before mode switch. |
| LAT-018 | gem-browser-tester | LAT-016 | None | `docs/test-evidence/browser-dashboard-validation.md`, `docs/test-evidence/browser-dashboard-visual-baseline.md` | Browser validation evidence for Streamlit proof flows. | Execute the browser validation matrix against proof-shaped data. |
| LAT-020 | gem-documentation-writer | LAT-013, LAT-014, LAT-015, LAT-016, LAT-019, LAT-025 | None | `docs/runtime/sandbox-runtime-contract.md`, `docs/operators/v1-runbook.md`, `docs/v1-architecture-brief.md` | Updated runtime contract, operator runbook, and architecture brief with boundary, failure-policy, reproducibility-manifest, mode-switch, and shared-read-path rules. | Verify docs reflect the implemented shared backend, stop conditions, rollback order, auditable mode-switch flow, run-start reproducibility records, and branch semantics. |

## Wave 9

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-021 | gem-devops | LAT-004, LAT-017, LAT-018, LAT-019, LAT-020 | LAT-003 | `docs/milestones/m1-proof-checklist.md`, `docs/releases/v1.0.0.md`, `CHANGELOG.md` | Release-proof bundle, milestone docs, changelog entries, and annotated milestone tags including the reproducibility manifest, cycle-to-audit linkage evidence, and preserved full-log bundle. | Verify the proof checklist links to e2e output, canonical record inventory, run-start reproducibility manifest, full logs, cycle-to-audit linkage evidence, boundary checklist, browser evidence, and reversibility artifacts before tagging. |

## Wave 10

| ID | Agent | Depends On | Conflicts | Target Files | Expected Output | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-022 | gem-devops | LAT-021 | None | None | Final annotated `v1.0.0` tag on `main`. | Verify clean `main`, completed proof checklist, and annotated final tag target. |

Critical path note: `LAT-025` is now the dedicated owner for run-start reproducibility manifests, brokered append-only full-log capture, and cycle-to-audit linkage. `LAT-024` and `LAT-019` both consume that evidence before `LAT-017` can execute the proof harness, while `LAT-013` remains a co-critical recovery gate for rollback and reversibility proof.
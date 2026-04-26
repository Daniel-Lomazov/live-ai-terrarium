# Milestone 1 Proof Checklist

## Status

- Milestone name: Milestone 1 proof-complete
- Milestone tag: `milestone/v1-proof-complete` (created on `main`)
- Outer `main` checkpoint: proof-backed release-bundle commit `1a04b57`, later carried forward on `main`
- Purpose: document why the outer `main` branch qualified for the proof-complete milestone tag and the final `v1.0.0` release tag

## Gate Summary

| Gate | Status | Evidence |
| --- | --- | --- |
| Ten stable cycles complete | Complete | `tests/e2e/test_ten_cycle_proof.py` and the Wave 8 validation command listed below |
| Zero unrecoverable failures in the proof loop | Complete | `tests/e2e/test_ten_cycle_proof.py` |
| Canonical per-cycle record emission | Complete | `tests/e2e/test_ten_cycle_proof.py` |
| Run-start reproducibility manifest captured before cycle 1 | Complete | `tests/e2e/test_ten_cycle_proof.py`, `src/live_ai_terrarium/storage/run_evidence.py` |
| Full logs preserved and linked to cycles | Complete | `tests/e2e/test_ten_cycle_proof.py`, `src/live_ai_terrarium/storage/log_capture.py` |
| Cycle-to-audit linkage verified against the canonical ledger | Complete | `tests/e2e/test_ten_cycle_proof.py`, `src/live_ai_terrarium/storage/run_evidence.py`, `docs/reviews/proof-clearance-status.yaml` |
| Branch-and-continue evidence preserved | Complete | `tests/e2e/test_rollback_flow.py`, `src/live_ai_terrarium/recovery/recovery.py` |
| Manual rollback to the last accepted stable cycle verified | Complete | `tests/e2e/test_rollback_flow.py`, `src/live_ai_terrarium/recovery/recovery.py` |
| API, CLI/TUI, and Streamlit parity verified | Complete | `tests/e2e/test_surface_parity.py` |
| Browser validation for the Streamlit dashboard | Complete | `docs/test-evidence/browser-dashboard-validation.md`, `docs/test-evidence/browser-dashboard-visual-baseline.md` |
| Runtime boundary and proof-clearance review | Complete | `docs/reviews/proof-clearance-status.yaml`, `docs/reviews/security-readiness-v1.md`, `docs/reviews/runtime-boundary-audit.md` |

## Validation Command

Wave 8 proof validation was executed with:

```text
c:/Users/lomaz/live-ai-terrarium/.venv/Scripts/python.exe -m pytest tests/e2e tests/adapters/test_dashboard_preview_app.py tests/adapters/test_dashboard_views.py -q
```

Recorded result:

```text
30 passed in 14.04s
```

## Evidence Inventory

### Proof harness

- `tests/e2e/test_ten_cycle_proof.py`
  - fails closed when `docs/reviews/proof-clearance-status.yaml` is missing or blocked
  - writes and validates ten canonical cycle records
  - creates and validates the proof inventory under the host-controlled proof bundle path
  - verifies immutable build identity from the run-start reproducibility manifest
  - verifies full-log preservation and audit linkage for every proof cycle

### Reversibility evidence

- `tests/e2e/test_rollback_flow.py`
  - validates `pause -> snapshot -> branch-and-continue -> report`
  - validates `pause -> snapshot -> rollback -> report`
  - verifies rollback restores the last accepted stable cycle into the workspace
  - verifies proof consumers can still resolve cycle linkage and full-log refs after rollback

### Cross-surface parity

- `tests/e2e/test_surface_parity.py`
  - validates the shared read-model truth across API, CLI, Rich TUI, and Streamlit controller state
  - validates consistent command semantics across `observe`, `mode switch`, `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback`
  - validates fail-closed behavior for `pause`, `resume`, `branch`, `clone`, `reset`, and `rollback` before an active mode-switch receipt exists

### Browser evidence

- `docs/test-evidence/browser-dashboard-validation.md`
- `docs/test-evidence/browser-dashboard-visual-baseline.md`

These files record the live browser validation against the Streamlit preview harness in `src/live_ai_terrarium/adapters/dashboard/preview_app.py`.

### Runtime and proof-gate review

- `docs/reviews/proof-clearance-status.yaml`
- `docs/reviews/security-readiness-v1.md`
- `docs/reviews/runtime-boundary-audit.md`

These files provide the proof-clearance gate and the focused runtime or boundary review required before the milestone harness may run.

## Milestone Contract Checklist

- Ten stable cycles complete with no unrecoverable failures.
- Every proof cycle emits a canonical cycle record with diff, score, decision, test result, model identity, prompt ref, token usage, latency, CPU, RAM, and disk fields.
- The proof harness captures the run-start reproducibility manifest before cycle 1.
- The proof harness validates outer repo commit SHA and container image digest as immutable build identity.
- Full logs are preserved in the brokered host-side bundle and remain linked to cycle ids.
- Cycle-to-audit linkage resolves against the canonical hash-chained audit ledger.
- Reversibility evidence includes both branch-and-continue and manual rollback flows.
- Surface parity is proven across API, CLI/TUI, and Streamlit state.
- Browser validation evidence exists for cycle drill-down, approval visibility, and incident or rollback evidence.

## Sandbox Evidence Boundary

The proof bundle references sandbox-inner branch-and-continue evidence only as mirrored host-controlled evidence.

- No sandbox branch graph was imported into the outer repository history.
- No nested sandbox `.git` data was committed into the outer repository.
- The milestone tag created from this checklist marks the outer `main` checkpoint only.

## Open Gaps

- None for the Milestone 1 proof-complete checkpoint.

This checklist is now the durable evidence record for the annotated milestone tag `milestone/v1-proof-complete` and the annotated release tag `v1.0.0` on `main`.

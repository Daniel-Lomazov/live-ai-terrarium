# Changelog

All notable changes to this repository will be tracked in this file.

The outer repository follows the validated plan in `docs/plan/20260426-live-ai-terrarium-v1/plan.md`: work lands on `main`, milestone tags stay separate from release tags, and the final `v1.0.0` tag is reserved for the Milestone 1 proof bundle.

## [Unreleased]

### Added

- Root `README.md` with public-facing setup, validation, and dashboard preview guidance.

### Changed

- Synced package metadata and advertised API version strings to `1.0.0`.
- Refreshed milestone and release guidance docs to reflect the current tagged repository state.
- Replaced stale wave-specific sample release tags in preview data and tests with `v1.0.0`.

## [1.0.0] - 2026-04-26

First proof-gated release for the local-first Live AI Terrarium v1 Milestone 1 contract.

### Added

- Frozen v1 spec pack, control-state design docs, tag strategy, and outer-repository release discipline.
- Python package scaffold, canonical IDs and records, hardened runtime profile, command catalog, and host-controlled storage paths.
- Executable sandbox boundary and append-only export contract.
- Shared command dispatcher, approval flow, append-only audit ledger, in-memory orchestrator runtime, and host model gateway.
- Deterministic evaluator gates and evidence-first recovery controller.
- Run-start reproducibility manifests, brokered full-log capture, and cycle-to-audit linkage for proof consumers.
- Shared read models for run summary, cycle detail, audit state, and recovery state.
- API, CLI/TUI, and Streamlit adapters over the same shared command and read paths.
- Wave 8 proof harness covering ten stable cycles, rollback evidence, and cross-surface parity.
- Streamlit preview harness plus browser validation evidence for proof-critical dashboard views.
- Long-lived runtime, operator, and architecture docs aligned to the implemented system.

### Release Gate

- Ten stable cycles in one Glass-Box run.
- Full logs, diffs, scores, and decision history per cycle.
- Evidence-preserving rollback from the last accepted stable state.
- No unrecoverable failures in the proof loop.
- Reproducibility and observability artifacts packaged before the final annotated `v1.0.0` tag.

### Evidence

- `docs/milestones/m1-proof-checklist.md`
- `docs/releases/v1.0.0.md`
- `docs/reviews/proof-clearance-status.yaml`
- `docs/test-evidence/browser-dashboard-validation.md`
- `docs/test-evidence/browser-dashboard-visual-baseline.md`
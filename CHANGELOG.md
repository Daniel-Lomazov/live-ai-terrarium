# Changelog

All notable changes to this repository will be tracked in this file.

The outer repository follows the validated plan in `docs/plan/20260426-live-ai-terrarium-v1/plan.md`: work lands on `main`, milestone tags stay separate from release tags, and the final `v1.0.0` tag is reserved for the Milestone 1 proof bundle.

## [Unreleased]

### Added

- Outer repository scaffolding for the Live AI Terrarium v1 proof-loop release path.
- Baseline ignore and attributes policy for runtime state, snapshots, exports, mirrors, backups, and local development artifacts.

## [1.0.0] - Planned

Reserved for the first proof-gated release once the validated plan is complete.

### Release Gate

- Ten stable cycles in one Glass-Box run.
- Full logs, diffs, scores, and decision history per cycle.
- Evidence-preserving rollback from the last accepted stable state.
- No unrecoverable failures in the proof loop.
- Reproducibility and observability artifacts packaged before the final annotated `v1.0.0` tag.
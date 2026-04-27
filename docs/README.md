# Documentation Guide

This directory is the documentation entry point for Live AI Terrarium.

If you are starting fresh, use the sections below instead of guessing which document matters first.

## Start Paths

### I want the current public summary

Read:

- `releases/v1.0.1.md`
- `../README.md`

### I want the original proof-backed baseline

Read:

- `milestones/m1-proof-checklist.md`
- `releases/v1.0.0.md`
- `test-evidence/browser-dashboard-validation.md`

### I want to understand the sandbox and Docker contract

Read:

- `runtime/sandbox-runtime-contract.md`
- `reviews/runtime-boundary-audit.md`
- `reviews/security-readiness-v1.md`

### I want the operator workflow

Read:

- `operators/v1-runbook.md`
- `design/v1-control-states.md`

### I want the architecture map

Read:

- `v1-architecture-brief.md`
- `specs/v1-system-contract.md`
- `specs/v1-data-contract.md`
- `specs/v1-ops-contract.md`

## Directory Map

- `design/`: UI flow and control-state design docs
- `milestones/`: named checkpoint evidence documents
- `operators/`: practical run and recovery guidance
- `plan/`: historical implementation planning and research records
- `releases/`: semver release notes and release policy
- `reviews/`: focused runtime, boundary, and proof-clearance reviews
- `runtime/`: current runtime and sandbox contract docs
- `specs/`: frozen v1 product contracts
- `test-evidence/`: browser and validation evidence artifacts

## Recommended Reading Order

For most users, this order works best:

1. `../README.md`
2. `releases/v1.0.1.md`
3. `runtime/sandbox-runtime-contract.md`
4. `operators/v1-runbook.md`
5. `v1-architecture-brief.md`

## Notes

- `plan/` is useful for project archaeology, but it is not the best starting point for users.
- `releases/v1.0.0.md` remains important because it explains the proof baseline that `v1.0.1` builds on.
- The Streamlit preview is the easiest runnable UI path for new users.
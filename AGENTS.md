# Live AI Terrarium / Glass-Box Repository Guide

## Repository Mission

This repository exists to implement v1 of Live AI Terrarium / Glass-Box: a container-isolated, observation-first environment that proves one inner agent can complete 10 stable cycles with full logs, rollback, and per-cycle visibility into diff, score, and decision.

Source of truth: `.github/live_ai_terrarium_questionnaire_working_file_v_1_0.md`.

If implementation docs or plans diverge from that questionnaire, bring them back into alignment instead of extending scope ad hoc.

## V1 Scope

- Single agent, single sandbox, no direct network, simple tests.
- Docker container per Glass-Box instance.
- Hard boundary: no host access and no shared mounts except a controlled export directory.
- Logs, metrics, and diffs cross the boundary through a controlled API; artifacts leave through an append-only export channel.
- Model access happens only through a centralized external Model Gateway.
- Observability is cycle-native: per-cycle records plus aggregated summaries with drill-down.
- Reversibility uses per-cycle file snapshots, periodic full filesystem snapshots, and a Git repo inside the sandbox mirrored externally.
- Human control surfaces are dashboard, CLI/`gb` commands, and API endpoints over one shared backend.

## Architectural Boundaries

- Required roles: Orchestrator, Model Gateway, Inner Agent, Evaluator, Dashboard, and Observer/Annotator.
- Keep strict logical and modular separation between roles even if the first cut runs in one process or uses the same underlying model.
- The Inner Agent may read and write its own sandbox files, run tests, request model work through the gateway, and use only allowlisted shell commands exposed through validated interfaces.
- The Inner Agent must never control Docker or system state, access the host filesystem, use direct network access, edit dashboard or snapshot or log sinks, run background daemons, or download code dynamically.
- No secrets live inside the sandbox.
- Host-controlled external storage and host-controlled log sinks are authoritative for audit and recovery.

## Git Discipline

- Treat per-cycle diffs and external Git mirroring as part of the product contract, not optional tooling.
- Preserve auditable history; prefer branch-and-continue over rewriting or deleting informative failure states.
- Keep changes small and traceable to a questionnaire decision or an explicit follow-up doc update.
- Do not add capabilities beyond the questionnaire-defined v1 scope for convenience.
- When architecture, scope, or operator behavior changes, update the questionnaire-derived docs in the same change.

## Implementation Principles

- Observation-only is the default mode in v1.
- All mode changes are explicit, auditable commands through the shared API path.
- Acceptance is deterministic: keep a cycle only when required gates pass and no regression is detected.
- Per-cycle records are the source of truth; dashboard and CLI views read the same records.
- Failure handling preserves evidence first: pause, snapshot, branch if useful, then rollback or kill and restore.
- Storage truth lives outside the sandbox; local sandbox state exists only for working convenience.
- Tooling should use typed interfaces and validated command specifications instead of ad hoc shell escape hatches.
- Prefer simple, inspectable implementations over premature service extraction while keeping role boundaries clean.
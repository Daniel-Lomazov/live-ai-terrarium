# Live AI Terrarium / Glass-Box v1 Architecture Brief

## Status

- Audience: developers
- Basis: completed questionnaire in `.github/live_ai_terrarium_questionnaire_working_file_v_1_0.md`
- Purpose: implementation handoff for the selected v1 architecture only

## V1 Goal

v1 proves that a single Glass-Box can run 10 stable cycles without unrecoverable failure while preserving full observability, reproducibility, and rollback.

The system is observation-first and safety-first. It records and evaluates by default; it does not start as an autonomous unrestricted agent runtime.

## Selected V1 Architecture

| Area | Selected v1 decision | Implementation consequence |
| --- | --- | --- |
| Isolation unit | Docker container per Glass-Box instance | Each sandbox has its own lifecycle-managed container runtime. |
| Boundary | Hard boundary: no host access and no shared mounts except a controlled export directory | Sandbox-host interaction must go through explicit control and export paths only. |
| Boundary crossings | Logs, metrics, and diffs via controlled API; artifacts via append-only export channel | Do not rely on direct host reads or writes from inside the sandbox. |
| Default mode | Observation-only | The first implementation must bias toward visibility and auditability rather than intervention. |
| Mode switching | Explicit API command plus dashboard toggle | Dashboard and CLI actions must call the same backend command path. |
| Networking | No internet inside Glass-Box; model API via external gateway only | No outbound internet or credentials inside the sandbox. |
| Tooling | Typed tool API plus validated command specs; limited allowlisted shell | Sandbox tooling must be explicit, auditable, and narrow. |
| Observability | Per-cycle records plus aggregated summaries with drill-down | Store detailed cycle records first, then render dashboards from that source of truth. |
| Reversibility | Per-cycle file snapshots, periodic full filesystem snapshots, and sandbox Git mirrored externally | Accepted and failing states must be reconstructable and branchable. |
| Evaluation | Rule-based gates plus Pareto comparison of valid candidates | Acceptance is gate-first; comparison is secondary. |
| Human control | Dashboard controls, CLI or `gb` commands, and API endpoints | All operator surfaces share one control contract. |
| First milestone | 10 stable cycles with full logs and rollback; dashboard shows diff, score, and decision per cycle | The first release is a proof loop, not a scale or autonomy release. |

## Roles And Boundaries

| Role | Responsibility | Boundary expectation |
| --- | --- | --- |
| Orchestrator | Owns project, Glass-Box, experiment, run, cycle, and mutation lifecycle | Outside sandbox control boundary |
| Model Gateway | Mediates model access with rate limits and per-run scoping | Outside sandbox; holds credentials and network reach |
| Inner Agent | Operates on sandbox-local files, tests, and approved tools | Inside sandbox only |
| Evaluator | Applies safety gates, regression checks, and candidate comparison | Separate logical role from Inner Agent |
| Dashboard | Presents Streamlit and CLI or rich TUI views over shared records | Reads and controls through shared API |
| Observer/Annotator | Adds interpretation or annotation without overriding core gates | Optional light role in v1, but still separate |

Strict logical separation is required even if the first implementation shares a process or model across roles.

## Non-Negotiable Constraints

- No host filesystem access from the sandbox.
- No secrets in the sandbox.
- No direct internet from the sandbox; model access is gateway-mediated only.
- Runtime hardening uses non-root execution, blocked egress, seccomp or apparmor, filesystem ACLs, and immutable mounts around host-facing surfaces.
- The Inner Agent cannot control Docker or host system state, edit dashboard or snapshot or log sinks, run background daemons, or download code dynamically.
- Stop conditions include repeated crashes, syntax failure, score drop, forbidden action attempt, resource overuse, and log silence.
- Audit logs must be append-only, externally controlled, and hash-chained for tamper evidence.
- Storage truth is host-controlled and mirrored externally; local sandbox state is not the authority.

## Canonical Records

Each cycle record is the observability source of truth and must capture at minimum:

- task
- diff
- score
- test result
- errors
- model identity
- prompt reference
- token usage
- latency
- CPU, RAM, and disk usage

The broader retained dataset for v1 also includes logs, prompts, diffs, metrics, snapshots, model outputs, model errors, resource traces, and annotations.

## Identity And Experiment Model

- Conceptual hierarchy: Project -> Glass-Box -> Experiment -> Run -> Cycle -> Mutation.
- Identity format: structured readable IDs plus internal UUIDs with human labels.
- Naming should combine project identity, Glass-Box identity, role, and agent identity, with experiment or run scope attached as metadata or suffix where useful.
- Comparisons across runs must keep tasks, seeds, and limits aligned and normalize metrics across models.

## Milestone 1 Contract

### Scope

- Single inner agent
- Single sandbox
- No direct network
- Simple tests

### Success Definition

- 10 stable cycles complete.
- Zero unrecoverable failures occur.
- Full logs are preserved.
- Rollback works from the last stable state.
- The dashboard exposes diff, score, and decision for each cycle.
- Every accepted cycle is inspectable, explainable, restorable, and reproducible.

## Acceptance Criteria

1. The runtime uses one Docker-contained Glass-Box with a hard boundary, no direct host access, and no direct sandbox internet access.
2. The only model path is a centralized external gateway with per-run scoping, and the sandbox contains no secrets.
3. Each cycle emits a canonical record containing task, diff, score, test result, errors, model, prompt reference, token usage, latency, and CPU or RAM or disk usage.
4. Dashboard and CLI views operate on the same underlying observability records and the same control API.
5. Acceptance remains deterministic: a cycle is kept only if required gates pass and no regression is detected.
6. Failure handling preserves evidence first through pause and snapshot, then branches or rolls back or restores according to severity.
7. Reversibility includes per-cycle file snapshots, periodic full snapshots, and sandbox Git mirrored externally.
8. The milestone proof completes 10 stable cycles with zero unrecoverable failures and a visible per-cycle diff, score, and decision trail.

## Out Of Scope For V1

- Multiple agents or complex multi-agent orchestration
- Complex tasks beyond the simple first test suite
- Direct sandbox internet access or domain allowlists
- Secrets or credential handling inside the sandbox
- Automated rollback as the trust anchor
- Weighted-score or learned-evaluator acceptance as the trust anchor
- Real-time event streaming as the primary observability contract
- Chat-based operator control as a required interface
- Database, blob store, or object store as a required first storage layer

## Implementation Order

1. Build the sandbox boundary and hardened container runtime first.
2. Establish the shared control API, stop conditions, and manual rollback path.
3. Implement canonical per-cycle records, external logging, snapshots, and Git mirroring.
4. Add the Model Gateway contract and the validated tool interface for the Inner Agent.
5. Implement evaluator gates and deterministic acceptance logic.
6. Layer Streamlit and CLI views on top of the shared records and control API.

This order stays within the questionnaire-defined v1 contract and avoids building scale or autonomy features before the safety and observability core exists.
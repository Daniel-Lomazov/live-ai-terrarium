# Live AI Terrarium v1 Data Contract

Status: Frozen v1 baseline for LAT-001.

This document is normative for v1 identifiers, state roots, canonical records, audit linkage, and run-start reproducibility evidence.

## Sources

- `.github/live_ai_terrarium_questionnaire_working_file_v_1_0.md`
- `AGENTS.md`
- `docs/v1-architecture-brief.md`
- `docs/plan/20260426-live-ai-terrarium-v1/plan.yaml`

## Authoritative State Roots

Durable truth lives outside the sandbox.

| Scope | Frozen v1 path | Rule |
| --- | --- | --- |
| Host-controlled state root | `%LOCALAPPDATA%/LiveAITerrarium/state` | Authoritative state for records, manifests, logs, snapshots, mirrors, and incidents |
| Host-controlled backup root | `%LOCALAPPDATA%/LiveAITerrarium/backups` | Backup target for durable recovery copies |
| Sandbox export outbox | `/workspace/.gb/outbox` | Only sanctioned sandbox-to-host artifact egress path |

The sandbox may keep local working copies, but those copies are not the recovery or audit authority.

## Readable ID Grammar

Every persisted v1 entity carries:

- one immutable machine identity field named `uuid`,
- one readable identity field named `readable_id`, and
- an optional mutable human display field named `label`.

The readable ID grammar is fixed as:

- format: `<prefix>-<slug>`
- allowed characters: lowercase ASCII letters, digits, and hyphens only
- slug pattern: `[a-z0-9]+(?:-[a-z0-9]+)*`

The fixed prefix set is:

- `project`
- `gb`
- `exp`
- `run`
- `cycle`
- `mutation`
- `incident`
- `agent`

Examples:

- `project-live-ai-terrarium`
- `gb-local-dev`
- `exp-proof-loop`
- `run-stability-baseline`
- `cycle-0003`
- `mutation-0001`

Readable IDs are unique within their parent scope. Global uniqueness is provided by `uuid` plus parent references, not by timestamps.

## UUID Storage Rule

- `uuid` is the primary machine-safe identity for durable storage and cross-record linkage.
- `uuid` must be written on every persisted record, manifest, receipt, snapshot index, and incident record.
- `uuid` is immutable after creation.
- `readable_id` is for operator navigation, folder naming, and human review.
- `label` is descriptive only and has no identity semantics.
- Timestamps are metadata only and must not be used as the primary identity.

## Agent Naming Default

The default v1 agent-readable naming pattern is:

`lait-gb-<glassbox-suffix>-<role>-<agent-suffix>`

`glassbox-suffix` and `agent-suffix` are the slug portions of the corresponding readable IDs.

The role token must be one of:

- `orchestrator`
- `gateway`
- `inner-agent`
- `evaluator`
- `dashboard`
- `observer`

## Canonical Record Minimums

### Cycle Record

Each cycle record is the source of truth for v1 observability and must contain at minimum:

- project, Glass-Box, experiment, run, cycle, and mutation identifiers,
- task identity,
- diff summary or diff reference,
- gate decision,
- score,
- test result,
- error summary,
- model identity,
- prompt reference,
- token usage,
- latency,
- CPU, RAM, and disk usage,
- snapshot references,
- audit event references, and
- full-log bundle reference.

### Incident Record

Each incident record must contain at minimum:

- run and cycle identifiers,
- stop-condition type,
- stop-condition trigger detail,
- snapshot reference,
- branch reference when branch-and-continue occurs,
- rollback or restore outcome when recovery occurs, and
- incident report reference.

## Audit Chain Contract

- Audit events are append-only and authoritative outside the sandbox.
- The v1 audit chain algorithm is SHA-256.
- The hash chain is scoped per run.
- Each audit event must store its own SHA-256 hash and the previous event hash for the same run.
- The chain begins at run start and remains contiguous for the full run lifetime.

## Run-Start Reproducibility Manifest

The run-start reproducibility manifest is mandatory.

- It must exist in host-controlled storage before cycle 1 begins.
- It becomes immutable after creation.
- A run that lacks the manifest is not eligible to advance to cycle 1.

The manifest must contain these required fields:

| Field | v1 rule |
| --- | --- |
| task identity | Required |
| seed | Required |
| limits | Required |
| model version | Required |
| outer repo commit SHA | Required immutable build-identity field |
| container image digest | Required immutable build-identity field |
| runtime-profile hash or embedded snapshot | Required |
| command-catalog hash or embedded snapshot | Required |

The manifest may additionally contain these supplemental labels:

- release tag
- human-readable image name

Supplemental labels are informative only. They never satisfy the immutable build-identity requirement on their own.

## Evidence Linkage Contract

- Full logs are captured through a brokered host-side path and stored append-only.
- Cycle records, incident records, and proof bundles must link to audit events and full-log bundles through canonical identifiers or canonical references.
- Proof consumers must be able to resolve audit evidence, log evidence, snapshot evidence, and branch evidence without ad hoc path reconstruction.

## Retention Baseline

- v1 retains full history for logs, prompts, diffs, metrics, snapshots, model outputs, model errors, resource traces, and annotations.
- v1 storage is local plus backup on a versioned filesystem.
- Hot and cold tiering with compression is allowed, but deletion of required proof or recovery evidence is not part of the v1 contract.

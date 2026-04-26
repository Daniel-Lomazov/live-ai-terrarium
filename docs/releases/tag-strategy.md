# Tag Strategy

## Purpose

This document defines the outer-repository tag and branch policy for Live AI Terrarium v1.
It keeps proof checkpoints distinct from the final release tag and keeps sandbox-inner Git history out of the outer repository graph.

LAT-004 writes the policy only. It does not create tags or commits.

## Outer Repository Rules

- The outer project repository is the host-controlled source tree for product code, docs, and release evidence.
- The outer repository stays on a single long-lived branch: `main`.
- Milestone tags and release tags are created from commits already on `main`.
- The outer repository does not use sandbox branch-and-continue branches as outer feature branches.

## Ref Types

| Ref type | Name pattern | Required form | Created from | Purpose |
| --- | --- | --- | --- | --- |
| Milestone tag | `milestone/v1-<checkpoint-slug>` | Annotated tag | `main` | Marks proof checkpoints and architecture-complete states without implying a semver release. |
| Release tag | `v1.0.0` | Annotated tag | `main` | Marks the first Milestone 1 proof release after all required evidence is present. |
| Outer branch | `main` | Branch | n/a | Carries the auditable outer project history for v1. |

## Annotated Tag Requirement

- Milestone tags must be annotated tags.
- The final `v1.0.0` tag must be an annotated tag.
- Lightweight tags are not valid for milestone or release markers in this repository.
- Each annotated tag message should name the checkpoint, the evidence docs, and the reason the commit is releasable.

## Milestone Tag Namespace

Use milestone tags only under this namespace:

- `milestone/v1-<checkpoint-slug>`

Guidance for the slug:

- Keep the slug short, descriptive, and proof-oriented.
- Prefer checkpoint names that describe the state of evidence, not implementation trivia.
- Do not use semver strings inside the milestone namespace.

Examples:

- `milestone/v1-foundation-frozen`
- `milestone/v1-proof-ready`
- `milestone/v1-proof-complete`

Milestone tags are not releases. They are durable evidence markers that show the outer `main` branch reached a named checkpoint.

## Final Release Tag

The only v1 final release tag defined by the current plan is:

- `v1.0.0`

Rules for `v1.0.0`:

- It is reserved for the Milestone 1 proof release.
- It must point to a commit already on `main`.
- It must be annotated.
- It must not be created until the repository contains the required proof bundle and release notes.

## Gate For Milestone Tags

Before cutting a milestone tag later:

- The relevant milestone document under `docs/milestones/` is present on `main`.
- The commit on `main` contains the evidence summary for that checkpoint.
- The tag message names the checkpoint and the backing evidence.
- Any sandbox branch evidence is linked as mirrored evidence, not imported as outer Git history.

## Gate For `v1.0.0`

Before cutting `v1.0.0` later, the outer `main` commit must document the Milestone 1 proof contract:

- 10 stable cycles completed.
- Zero unrecoverable failures.
- Full logs preserved.
- Rollback to the last accepted stable state verified.
- Per-cycle diff, score, and decision visibility available.
- Reversibility evidence includes branch-and-continue evidence and manual rollback evidence.
- Release notes exist under `docs/releases/v1.0.0.md`.

`v1.0.0` is premature if the repository cannot point to the proof evidence above.

## Outer Versus Sandbox Branch Discipline

| Surface | Allowed refs | What it is for | What it must not do |
| --- | --- | --- | --- |
| Outer repository | `main`, annotated milestone tags, annotated `v1.0.0` | Product history, docs, release evidence, operator-facing proof summaries | Carry sandbox-inner branch graphs or mirrored sandbox refs |
| Sandbox inner Git repo | Run-local branches created by branch-and-continue | Preserve failing or exploratory states inside the Glass-Box lifecycle | Become the authoritative product history |
| External sandbox mirror | Mirrored copies of sandbox refs and evidence | Preserve reversibility evidence outside the sandbox boundary | Pollute the outer repo branch graph or release namespace |

## Mirror And Branch-And-Continue Rules

- Branch-and-continue creates a branch inside the sandbox-inner Git repository.
- The branch is mirrored out to host-controlled evidence storage for audit and recovery.
- The mirror exists to retain evidence and reconstruct failures, not to act as an outer development branch.
- The outer repository must never merge, cherry-pick, fetch, or subtree-import sandbox mirror history as part of normal v1 workflow.
- If sandbox work reveals a product change worth keeping, that change is re-applied as a fresh auditable commit on outer `main`, with the mirrored sandbox evidence referenced in docs.

## Practical Storage Boundary

- Keep sandbox mirrors in host-controlled state outside the tracked source tree, or in an ignored path if local workspace storage is temporarily needed.
- Keep only summary evidence, manifests, and human-readable proof docs in the outer repository.
- Do not commit nested sandbox `.git` directories, mirrored refs, or raw branch stores into the outer repository.

This keeps sandbox branch evidence available without making it part of the outer branch graph.

## Operational Checklist

When a later task is ready to create a milestone tag:

1. Confirm the checkpoint commit is already on `main`.
2. Confirm the matching milestone doc exists under `docs/milestones/`.
3. Confirm the tag name uses `milestone/v1-<checkpoint-slug>`.
4. Confirm the tag will be annotated.

When a later task is ready to create `v1.0.0`:

1. Confirm the proof bundle on `main` satisfies the Milestone 1 contract.
2. Confirm `docs/releases/v1.0.0.md` summarizes the proof evidence.
3. Confirm rollback and branch-and-continue evidence are referenced as mirrored evidence.
4. Confirm the tag will be annotated and created from `main`.
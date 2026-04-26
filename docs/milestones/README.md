# Milestones

## Purpose

This directory holds written checkpoint documents that justify outer-repository milestone tags.
Each milestone document explains what proof or implementation checkpoint was reached on outer `main` and what evidence supports that checkpoint.

Milestone documents support milestone tags. They are not release notes.

## Tag Relationship

- Every outer milestone tag uses the namespace `milestone/v1-<checkpoint-slug>`.
- Every milestone tag is an annotated tag created from a commit already on `main`.
- A milestone document must exist before its matching milestone tag is created.
- Milestone tags are distinct from the final release tag `v1.0.0`.

## What Belongs Here

Use this directory for checkpoint documents such as:

- architecture freeze notes,
- proof-readiness checklists,
- proof-complete checklists,
- evidence summaries that justify a named milestone tag.

The first proof-oriented document is `m1-proof-checklist.md`, and its matching milestone tag already exists as `milestone/v1-proof-complete`.

## Minimum Content For A Milestone Doc

Each milestone document should include:

- the milestone name,
- the intended milestone tag name,
- the outer `main` checkpoint it describes,
- the evidence list that justifies the tag,
- open gaps or follow-up blockers, if any,
- references to sandbox mirror evidence when reversibility or failure preservation matters.

## Outer-Main Workflow

Milestone documents are part of the outer repository workflow:

1. Update the milestone document on outer `main`.
2. Link the checkpoint to the proof evidence already captured by the project.
3. Review whether the checkpoint is a milestone tag or a final release candidate.
4. Create the annotated milestone tag from `main` when the checkpoint is actually satisfied, or verify the existing tag still points at the documented checkpoint.

The document comes first. The tag is only the durable marker for that documented state.

## Sandbox Evidence Boundary

Milestone docs may reference sandbox reversibility evidence, including:

- branch-and-continue branch names,
- incident bundles,
- snapshot manifests,
- mirrored run evidence.

Milestone docs must not turn that evidence into outer repository history:

- Do not create outer branches to mirror sandbox branch names.
- Do not commit mirrored sandbox refs or nested sandbox `.git` data into this repository.
- Do not treat sandbox branch graphs as if they were part of outer `main`.

If sandbox evidence matters to the milestone, describe it and link to the mirrored evidence location or exported report. Keep the full branch graph outside the outer repository history.

## Milestones Versus Releases

Use a milestone document when you need to show that outer `main` reached a named checkpoint.
Use a release note in `docs/releases/` only when preparing an actual semver release.

Quick rule:

- `milestone/v1-*` means checkpoint.
- `v1.0.0` means final Milestone 1 release.

## Current Policy State

- `m1-proof-checklist.md` is the current milestone proof document for the repository.
- `milestone/v1-proof-complete` is the current annotated milestone tag on `main`.
- Future milestone checkpoints should keep using the same annotated-tag rule and namespace.
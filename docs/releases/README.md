# Releases

## Purpose

This directory holds release-note documents for outer-repository semver releases.
In the current v1 plan, releases are gated proof events, not generic version bumps.

## Release Namespace

- Milestone tags live under `milestone/v1-*`.
- Final releases use plain semver tags.
- The final v1 release tag defined by the current plan is `v1.0.0`.
- Milestone tags and release tags must remain distinct.

## Annotated Release Rule

- Release tags must be annotated.
- The final `v1.0.0` tag must be annotated.
- The release note document must exist before the release tag is created.

## What Belongs Here

Use this directory for:

- semver release notes,
- proof-release summaries,
- release evidence indexes that explain why the tagged commit is releasable.

The first release note document is `v1.0.0.md`, and it is the current release note used for the published GitHub release.

## Release Gate For `v1.0.0`

The release note for `v1.0.0` should summarize the proof state that justifies the final annotated release tag:

- 10 stable cycles completed,
- zero unrecoverable failures,
- full logs preserved,
- rollback verified,
- per-cycle diff, score, and decision visibility available,
- reversibility evidence preserved, including branch-and-continue and manual rollback evidence.

If those items are not backed by evidence on outer `main`, `v1.0.0` is not ready.

## Release Workflow

1. Confirm the proof bundle exists on outer `main`.
2. Confirm the matching milestone documentation is already complete.
3. Write or refresh `docs/releases/v1.0.0.md` against the exact `main` commit that the release tag will represent.
4. Create or verify the annotated `v1.0.0` tag from that same `main` commit.

This keeps the release doc, the evidence, and the tagged commit aligned.

## Sandbox Mirror Boundary

Release notes may cite sandbox mirror evidence when it supports the release proof.
Release notes must not pull sandbox Git history into the outer repository workflow.

Practical rules:

- Do not release from a sandbox branch.
- Do not create outer feature branches that mirror sandbox branch-and-continue refs.
- Do not import mirrored sandbox history into the outer repository graph.
- If sandbox work informs the product codebase, restate it as an auditable outer `main` commit and reference the mirrored evidence separately.

## Current Policy State

- `docs/releases/v1.0.0.md` is the current release note document for the repository.
- `v1.0.0` is the current annotated release tag and GitHub Release.
- Future semver releases should keep the same annotated-tag rule and proof-evidence discipline.
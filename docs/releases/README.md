# Releases

## Purpose

This directory holds release-note documents for outer-repository semver releases.
In the current v1 plan, releases are gated proof events, not generic version bumps.

## Release Namespace

- Milestone tags live under `milestone/v1-*`.
- Final releases use plain semver tags.
- The initial proof-backed v1 release tag defined by the current plan is `v1.0.0`.
- Follow-up maintenance releases may advance semver, such as `v1.0.1`, when they stay aligned with the same proof-backed repository discipline.
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

Published release note documents currently include `v1.0.0.md` and `v1.0.1.md`.

## Release Gate For Semver Releases

Each release note should summarize the proof state or maintenance scope that justifies its annotated semver tag:

- 10 stable cycles completed,
- zero unrecoverable failures,
- full logs preserved,
- rollback verified,
- per-cycle diff, score, and decision visibility available,
- reversibility evidence preserved, including branch-and-continue and manual rollback evidence.

If those items are not backed by evidence on outer `main`, the semver release is not ready.

## Release Workflow

1. Confirm the proof bundle exists on outer `main`.
2. Confirm the matching milestone documentation is already complete.
3. Write or refresh the matching file under `docs/releases/` against the exact `main` commit that the release tag will represent.
4. Create or verify the annotated semver tag from that same `main` commit.

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

- `docs/releases/v1.0.0.md` and `docs/releases/v1.0.1.md` are the current published release notes for the repository.
- `v1.0.0` and `v1.0.1` are the current annotated semver release tags.
- Future semver releases should keep the same annotated-tag rule and proof-evidence discipline.
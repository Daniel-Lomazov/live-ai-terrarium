# Live AI Terrarium Sandbox Runtime Contract

## Status

- Audience: developers and operators
- Basis: current implementation in `src/live_ai_terrarium/orchestrator/`, `src/live_ai_terrarium/storage/`, `src/live_ai_terrarium/gateway/`, and `tests/sandbox_contract/test_boundary_export_contract.py`
- Purpose: describe the runtime, boundary, and storage contract that v1 actually enforces today

## Scope

This document is limited to the implemented host-side runtime slice: run registration, sandbox boundary checks, brokered log capture, append-only outbox export, host-controlled storage roots, and the outside-the-sandbox model gateway binding. It does not claim a persistent Docker supervisor beyond the invariants enforced by the current modules.

## Current Runtime Slice

| Module | What it owns today | Contract consequence |
| --- | --- | --- |
| `src/live_ai_terrarium/orchestrator/boundary.py` | `SandboxBoundaryPolicy` and sanctioned path validation | The boundary is fixed to one workspace mount and one outbox egress path. |
| `src/live_ai_terrarium/orchestrator/runtime.py` | `RuntimeRegistration`, `RuntimeSession`, and in-memory lifecycle state | Registration fails closed when the runtime profile violates v1 invariants. |
| `src/live_ai_terrarium/orchestrator/service.py` | Host lifecycle service, audit-composed command execution, export broker, and runtime hooks | Surfaces interact with the host runtime through one orchestrator service layer. |
| `src/live_ai_terrarium/storage/exports.py` | `AppendOnlyExportWriter` | Sandbox artifacts leave only through append-only outbox exports. |
| `src/live_ai_terrarium/storage/log_capture.py` | `LogCaptureBroker` | Full logs are captured on the host in brokered append-only bundles. |
| `src/live_ai_terrarium/storage/run_evidence.py` | Run-start manifest and cycle-to-audit linkage | A run cannot claim proof-grade evidence without immutable manifest and linkage files. |
| `src/live_ai_terrarium/storage/paths.py` | Authoritative host-controlled roots and durable path layout | Records, logs, snapshots, mirrors, exports, and backups live outside the sandbox. |
| `src/live_ai_terrarium/gateway/service.py` | Host model gateway binding | Credentials and allowed-model policy stay outside the sandbox. |

## Frozen Boundary Invariants

| Area | Implemented rule | Code anchor |
| --- | --- | --- |
| Workspace mount target | The only allowed shared mount target is `/workspace`. | `SandboxBoundaryPolicy.workspace_mount_target` |
| Outbox export path | The only sanctioned sandbox-to-host artifact egress root is `/workspace/.gb/outbox`. | `SANCTIONED_OUTBOX_PATH` |
| Shared mounts | Any mount set other than exactly `(/workspace,)` is rejected. | `SandboxBoundaryPolicy.validate_shared_mounts()` |
| Direct host access | Runtime tooling is denied access to host-controlled records, logs, snapshots, mirrors, exports, and backups. | `SandboxBoundaryPolicy.validate_no_direct_host_access()` |
| Host-facing surfaces | `docker_socket`, `host_filesystem`, `dashboard_sinks`, `snapshot_sinks`, and `log_sinks` are treated as blocked host control surfaces. | `HOST_CONTROL_SURFACES` |
| Network | Runtime registration requires `network_mode="none"`. | `RuntimeRegistration.__post_init__()` |
| Published ports | Runtime registration requires zero published ports. | `RuntimeRegistration.__post_init__()` |
| Secrets | The sandbox runtime contract keeps credentials outside the sandbox and binds them per run in the host model gateway. | `GatewayRunBinding`, `HostModelGatewayService.register_run()` |

## Host-Controlled Storage Roots

`StoragePaths.from_local_appdata()` fixes the durable v1 roots to Windows local app data:

| Root | Frozen v1 location | What lives there |
| --- | --- | --- |
| State root | `%LOCALAPPDATA%/LiveAITerrarium/state` | Run records, manifests, cycle records, brokered logs, snapshots, mirrors, incidents, exports, and proof bundles |
| Backup root | `%LOCALAPPDATA%/LiveAITerrarium/backups` | Durable backup copies for recovery and proof bundle preservation |

The sandbox may keep working files under `/workspace`, but those files are never the audit or recovery authority.

## Boundary Crossing Rules

### Artifact egress

- `AppendOnlyExportWriter` accepts only file paths below `/workspace/.gb/outbox`.
- The outbox root itself is not a valid export target; the target must be a file path under the outbox.
- Relative paths, parent traversal, and non-outbox targets are rejected.
- Each `export_id` maps to a new host export directory. Reusing an existing `export_id` fails with an append-only error.
- Every export appends a line to the run manifest at `state/exports/.../items/manifest.jsonl` and writes the host copy under `state/exports/.../items/<export_id>/`.

### Log and evidence capture

- `HostOrchestratorService.hooks_for(run)` exposes two host-side channels: `run-log-capture` and `append-only-export`.
- `RunEvidenceWriteHook` always carries `sandbox_outbox_path=/workspace/.gb/outbox`.
- `LogCaptureBroker` writes `full-log-bundle.jsonl` and companion metadata under `state/logs/projects/<project>/glassboxes/<glassbox>/experiments/<experiment>/runs/<run>/brokered/`.
- `RunEvidenceStore` writes the immutable run-start reproducibility manifest to `state/manifests/.../run-start-reproducibility.json` and refuses in-place manifest rewrite.

### Model access

- The sandbox runtime contract assumes no direct sandbox network access.
- `HostModelGatewayService` registers a `credential_handle` and `allowed_models` tuple per run on the host side.
- Requests are validated against the registered run scope and allowed model list before transport is called.
- This keeps secrets and outbound connectivity outside the sandbox boundary.

## Runtime Registration Contract

`RuntimeRegistration` is the current gate that freezes the per-run runtime profile:

- `container_name` must be non-empty.
- `workspace_volume` must be non-empty.
- `image_digest` must be a pinned `sha256:` digest.
- `runtime_profile_name` defaults to `glassbox-hardened-v1`.
- `network_mode` must remain `none`.
- `published_ports` must remain empty.
- The boundary policy must still validate exactly one shared mount target, `/workspace`.

The current runtime state holder is `InMemoryOrchestratorRuntime`, which tracks lifecycle state, current mode, clone source, rollback target, and restore snapshot in memory. The code enforces the contract and emits lifecycle receipts, but it does not yet persist runtime sessions beyond the process.

## No-Host-Access Rule

`HostOrchestratorService.authorize_runtime_host_path()` is the implemented guard for host-side tool paths:

- A candidate path is allowed only when it resolves outside `%LOCALAPPDATA%/LiveAITerrarium/state` and `%LOCALAPPDATA%/LiveAITerrarium/backups`.
- Any path under the host-controlled roots is rejected before the runtime can use it.
- This is the concrete enforcement behind the human-facing rule that the sandbox has no direct host access.

## Practical Operator Meaning

- The runtime starts in `observation-only` mode.
- The sandbox has no direct network, no secrets, no direct host path access, and no extra shared mount beyond `/workspace`.
- Artifact egress is limited to `/workspace/.gb/outbox` and is mirrored into host-controlled export storage through an append-only writer.
- Durable truth lives under `%LOCALAPPDATA%/LiveAITerrarium/state` and `%LOCALAPPDATA%/LiveAITerrarium/backups`, not inside the sandbox workspace.

These rules are exercised directly by `tests/sandbox_contract/test_boundary_export_contract.py` and by the orchestrator/runtime tests that verify the same registration and hook invariants.
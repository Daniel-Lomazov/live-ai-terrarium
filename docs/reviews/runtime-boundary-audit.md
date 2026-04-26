# Runtime Boundary Audit

## Review Objective

This audit checks whether the reviewed runtime and storage surfaces support the v1 boundary contract:

- one sanctioned export egress rooted at `/workspace/.gb/outbox`,
- no direct sandbox network,
- no direct sandbox-to-host control surfaces,
- host-side gateway separation,
- evidence-first recovery with external mirror storage, and
- proof-consumable audit and run-evidence records.

## Reviewed Runtime Surfaces

- `infra/security/runtime-profile.yaml`
- `infra/security/command-specs.yaml`
- `infra/docker/glassbox/Dockerfile`
- `src/live_ai_terrarium/orchestrator/boundary.py`
- `src/live_ai_terrarium/orchestrator/runtime.py`
- `src/live_ai_terrarium/orchestrator/service.py`
- `src/live_ai_terrarium/storage/exports.py`
- `src/live_ai_terrarium/storage/filesystem.py`
- `src/live_ai_terrarium/storage/paths.py`
- `src/live_ai_terrarium/gateway/service.py`
- `src/live_ai_terrarium/audit/ledger.py`
- `src/live_ai_terrarium/storage/log_capture.py`
- `src/live_ai_terrarium/storage/run_evidence.py`
- `src/live_ai_terrarium/recovery/recovery.py`
- `src/live_ai_terrarium/recovery/snapshots.py`
- `tests/sandbox_contract/test_boundary_export_contract.py`
- `tests/orchestrator/test_service_runtime.py`
- `tests/gateway/test_service.py`
- `tests/storage/test_run_evidence.py`
- `tests/recovery/test_recovery.py`

## Boundary Findings

| Surface | Status | Grounded observation |
| --- | --- | --- |
| Runtime profile | Pass | The runtime profile requires one container, zero published ports, `network.mode: none`, `allow_outbound: false`, `privileged: false`, `allow_privilege_escalation: false`, `cap_drop: [ALL]`, and denies bind mounts, docker socket, host devices, and extra mounts. |
| Container image | Pass | The Dockerfile runs as UID/GID `10001`, uses `tini`, creates `/workspace/.gb/outbox`, and does not define any credential-bearing environment variables. |
| Export egress | Pass | `SandboxBoundaryPolicy` hard-codes `/workspace/.gb/outbox` as the sanctioned outbox, and `AppendOnlyExportWriter` rejects both out-of-outbox paths and in-place rewrites. |
| Additional shared mounts | Pass with note | The reviewed runtime declares one writable named workspace volume at `/workspace` plus tmpfs mounts. No additional bind mount or host-device mount was found. |
| Direct host access | Pass | `HostOrchestratorService.authorize_runtime_host_path` routes runtime tool path authorization through `SandboxBoundaryPolicy.validate_no_direct_host_access`, and the focused orchestrator test verifies host-controlled paths are rejected. |
| Host-side gateway | Pass | Model requests are scoped by `RunScope`, credential handles are held in host-side bindings, and disallowed models are rejected. |
| Observation-only default | Pass | Runtime sessions start in `observation-only`, and dispatcher policy denies control actions without an active, matching mode-switch receipt. |
| Receipt-gated control mutation | Pass | `HostOrchestratorService.execute_command` now composes dispatch, approval, audit emission, and runtime mutation in one backend path, and the focused orchestrator test proves deny-before-receipt plus approved execution flow. |
| Audit chain | Pass | `RunEvidenceStore.lookup_cycle_proof_evidence` now verifies the run audit chain and resolves audit refs against the canonical ledger before returning proof evidence. |
| Log and proof evidence | Pass | Log bundle creation, append-only sequence numbering, immutable manifest creation, cycle linkage, audit-chain verification, and audit-ref resolution are now all implemented and covered by the focused storage tests. |
| Recovery and git separation | Pass | Recovery writes branch evidence to host-controlled mirror storage and records `outer_repo_branch_created: false`, which aligns with the release/tag policy. |

## Positive Evidence

### Runtime hardening already present

The combination of `infra/security/runtime-profile.yaml` and `infra/docker/glassbox/Dockerfile` gives the reviewed implementation a defensible baseline:

- non-root execution,
- zero published ports,
- `network_mode=none`,
- denied bind mounts and docker socket access,
- explicit capability drop, and
- a fixed workspace plus outbox layout.

### Export contract is narrow and append-only

Artifact egress is funneled through `AppendOnlyExportWriter`, which only accepts sandbox paths under `/workspace/.gb/outbox` and raises on rewrite. The corresponding contract test exercises invalid targets and rewrite denial. This part of the boundary is proof-ready.

### Gateway stays outside the sandbox boundary

The gateway service keeps credentials in a run binding rather than in request payloads. The request model rejects extra fields, and tests verify that a caller cannot smuggle `credential_handle` into a generation request. This is consistent with the v1 requirement that model access stays external to the sandbox.

### Recovery preserves evidence without polluting the outer repository

Recovery branch evidence is written under host-controlled mirror storage, not under the tracked repository tree, and the mirror payload records `outer_repo_branch_created: false`. That aligns code, tests, and release policy on the same outer-versus-inner git separation rule.

## Resolved Prior Blockers

### BND-001

Host-path denial is now wired into the reviewed host-side runtime authorization surface via `HostOrchestratorService.authorize_runtime_host_path`. The focused orchestrator test confirms the service allows sandbox-runtime tool paths and denies host-controlled evidence paths.

### CTRL-001

`HostOrchestratorService.execute_command` now provides the required single backend control path. The reviewed flow composes dispatcher policy, approval issuance, audit logging, and runtime mutation, and the focused orchestrator test verifies the path end to end.

### AUD-001

`RunEvidenceStore.lookup_cycle_proof_evidence` now verifies audit-chain integrity and resolves audit refs against the canonical ledger before returning proof inputs. The focused storage tests prove fail-closed behavior for both tampered ledgers and unresolved refs.

## Validation Result

Executed focused contract tests:

```text
c:/Users/lomaz/live-ai-terrarium/.venv/Scripts/python.exe -m pytest tests/sandbox_contract/test_boundary_export_contract.py tests/audit/test_ledger_approval.py tests/control/test_dispatcher.py tests/orchestrator/test_service_runtime.py tests/gateway/test_service.py tests/storage/test_run_evidence.py tests/recovery/test_recovery.py -q
```

Observed result: `35 passed in 7.51s`.

The passing tests support the positive findings above and, in this re-review, directly cover the three formerly blocked integration gaps.

## Audit Outcome

`cleared`

The runtime boundary is now proof-ready for the reviewed scope. Direct host-access denial, approval-to-runtime composition, and audit verification are all enforced in operational proof-facing paths.
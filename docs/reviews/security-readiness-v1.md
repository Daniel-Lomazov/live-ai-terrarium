# Security Readiness Review v1

## Scope

Task `LAT-019` reviewed the v1 proof-critical controls called out by the plan and frozen contracts:

- boundary and export egress,
- direct host-access denial,
- gateway separation,
- observation-only default and mode-switch approval flow,
- audit tamper evidence,
- reproducibility manifest completeness,
- append-only full-log linkage, and
- outer-versus-inner git separation.

Reviewed artifacts:

- `AGENTS.md`
- `docs/v1-architecture-brief.md`
- `docs/specs/v1-system-contract.md`
- `docs/specs/v1-data-contract.md`
- `docs/specs/v1-ops-contract.md`
- `docs/plan/20260426-live-ai-terrarium-v1/plan.yaml`
- `docs/releases/tag-strategy.md`
- `infra/security/runtime-profile.yaml`
- `infra/security/command-specs.yaml`
- `infra/docker/glassbox/Dockerfile`
- `src/live_ai_terrarium/orchestrator/boundary.py`
- `src/live_ai_terrarium/orchestrator/runtime.py`
- `src/live_ai_terrarium/orchestrator/service.py`
- `src/live_ai_terrarium/gateway/service.py`
- `src/live_ai_terrarium/control/commands.py`
- `src/live_ai_terrarium/control/dispatcher.py`
- `src/live_ai_terrarium/control/approval.py`
- `src/live_ai_terrarium/audit/ledger.py`
- `src/live_ai_terrarium/recovery/recovery.py`
- `src/live_ai_terrarium/storage/exports.py`
- `src/live_ai_terrarium/storage/log_capture.py`
- `src/live_ai_terrarium/storage/run_evidence.py`
- `src/live_ai_terrarium/storage/filesystem.py`
- `src/live_ai_terrarium/storage/paths.py`
- `tests/sandbox_contract/test_boundary_export_contract.py`
- `tests/audit/test_ledger_approval.py`
- `tests/control/test_dispatcher.py`
- `tests/orchestrator/test_service_runtime.py`
- `tests/gateway/test_service.py`
- `tests/storage/test_run_evidence.py`
- `tests/recovery/test_recovery.py`

Focused validation command:

```text
c:/Users/lomaz/live-ai-terrarium/.venv/Scripts/python.exe -m pytest tests/sandbox_contract/test_boundary_export_contract.py tests/audit/test_ledger_approval.py tests/control/test_dispatcher.py tests/orchestrator/test_service_runtime.py tests/gateway/test_service.py tests/storage/test_run_evidence.py tests/recovery/test_recovery.py -q
```

Result: `35 passed in 7.51s`.

## Verdict

Proof readiness is `cleared`.

The re-reviewed implementation now closes the three former proof blockers in operational code paths. Host-path denial is exposed through the host-side orchestrator service, controlled actions flow through one auditable backend command path that composes dispatcher, approval, audit, and runtime mutation, and proof evidence lookup now verifies the audit chain and resolves audit refs against the canonical ledger before returning evidence.

No proof-blocking findings remain in the LAT-019 scope.

## Control Matrix

| Control | Status | Grounding | Review note |
| --- | --- | --- | --- |
| One controlled export directory contract | Pass | `src/live_ai_terrarium/orchestrator/boundary.py` fixes the sanctioned outbox at `/workspace/.gb/outbox`; `src/live_ai_terrarium/storage/exports.py` rejects non-outbox targets and denies rewrites; `tests/sandbox_contract/test_boundary_export_contract.py` covers negative paths. | Outbox-only egress is implemented and tested. |
| Absence of extra shared mounts | Pass with note | `infra/security/runtime-profile.yaml` allows one writable volume at `/workspace`, tmpfs at `/tmp` and `/run`, and denies bind mounts, docker socket, host devices, and extra mounts; `src/live_ai_terrarium/orchestrator/boundary.py` accepts only `/workspace` as the mounted workspace target. | The runtime still mounts a named workspace volume at `/workspace`, but no extra host-facing bind mounts were found in the reviewed implementation. |
| Blocked direct host reads or writes | Pass | `src/live_ai_terrarium/orchestrator/service.py` exposes `authorize_runtime_host_path`, which routes candidate paths through `registration.boundary_policy.validate_no_direct_host_access`; `tests/orchestrator/test_service_runtime.py` verifies that sandbox tool paths are accepted while host-controlled records are denied. | The host-path denial rule is now wired into a reviewed host-side runtime authorization path. |
| Host-side gateway separation | Pass | `src/live_ai_terrarium/gateway/service.py` stores `credential_handle` in a host-side binding, scopes allowed models per run, and the request schema forbids extra fields; `tests/gateway/test_service.py` verifies that a request cannot carry a credential handle. | No direct secret injection into sandbox-facing requests was found. |
| No direct sandbox network | Pass | `src/live_ai_terrarium/orchestrator/runtime.py` hard-codes `network_mode="none"` and zero published ports; `infra/security/runtime-profile.yaml` sets `allow_outbound: false`; `infra/docker/glassbox/Dockerfile` runs non-root and exposes no listening service. | The reviewed runtime surfaces support the frozen no-network contract. |
| No secrets in sandbox | Pass | `src/live_ai_terrarium/gateway/service.py` keeps the credential handle outside the request model; `infra/docker/glassbox/Dockerfile` does not inject credentials; `infra/security/runtime-profile.yaml` locates gateway reach outside the sandbox boundary. | No secret-bearing environment variables or sandbox-side credential path were found in the reviewed files. |
| Observation-only default | Pass | `src/live_ai_terrarium/orchestrator/runtime.py` starts sessions in `observation-only`; `src/live_ai_terrarium/control/dispatcher.py` denies control actions without an active receipt; `tests/control/test_dispatcher.py` exercises the deny-by-default behavior. | The default is implemented at the runtime and dispatcher layers. |
| Mode-switch receipt enforcement | Pass | `src/live_ai_terrarium/orchestrator/service.py` now composes `CommandDispatcher`, `ApprovalService`, audit recording, and `_apply_runtime_command` inside `execute_command`; `tests/orchestrator/test_service_runtime.py` verifies deny-before-receipt, approved mode switch, subsequent controlled action enablement, and the full audit event sequence. | The reviewed backend now exposes the single auditable command path required by the frozen system and ops contracts. |
| Audit integrity | Pass | `src/live_ai_terrarium/storage/run_evidence.py` now calls `_resolve_verified_audit_refs` during `lookup_cycle_proof_evidence`, which invokes `AuditLedger.verify_run_chain` and resolves returned refs against the canonical ledger path; `tests/storage/test_run_evidence.py` covers both tampered-chain and unresolved-ref failures. | Proof consumers now fail closed unless audit integrity and audit-ref resolution succeed. |
| Reproducibility manifest completeness | Pass | `src/live_ai_terrarium/storage/run_evidence.py` requires task identity, seed, limits, model version, outer repo SHA, container image digest, runtime profile, and command catalog; `tests/storage/test_run_evidence.py` covers immutability and pre-cycle creation. | The manifest contract is implemented and fail-closed for missing manifests. |
| Append-only full-log linkage | Pass | `src/live_ai_terrarium/storage/log_capture.py` appends sequenced JSONL entries; `src/live_ai_terrarium/storage/run_evidence.py` links cycles to a log bundle ref plus sequence window and now verifies the paired audit evidence during proof lookup; `tests/storage/test_run_evidence.py` validates append-only sequencing plus fail-closed lookup behavior for missing or invalid evidence. | Full-log linkage and its audit-side proof dependency are both enforced in the reviewed implementation. |
| Outer-versus-inner git separation | Pass | `src/live_ai_terrarium/storage/paths.py` places mirrors under host-controlled state; `src/live_ai_terrarium/recovery/recovery.py` writes branch evidence with `outer_repo_branch_created: false`; `tests/recovery/test_recovery.py` asserts the mirror artifact and outer-branch denial; `docs/releases/tag-strategy.md` matches the same discipline. | Reviewed code and docs agree that sandbox branch evidence stays outside outer `main`. |

## Resolved Prior Blockers

### BND-001: Direct host-access denial is now wired into the reviewed runtime boundary path

`HostOrchestratorService.authorize_runtime_host_path` is now the reviewed host-side authorization surface for runtime tooling. It resolves candidate paths through `SandboxBoundaryPolicy.validate_no_direct_host_access`, and the focused orchestrator test proves the service accepts sandbox tool paths while rejecting host-controlled record paths.

### CTRL-001: The shared auditable backend command path now exists and is executable

`HostOrchestratorService.execute_command` now binds `CommandDispatcher` -> `ApprovalService` -> audit events -> runtime mutation in one backend path. The focused orchestrator test shows that a denied control action leaves runtime state unchanged, an approved mode switch emits approval and lifecycle audit events, and subsequent controlled actions execute only after the active receipt exists.

### AUD-001: Proof evidence lookup now verifies audit integrity and resolves audit refs

`RunEvidenceStore.lookup_cycle_proof_evidence` now calls `_resolve_verified_audit_refs`, which verifies the run hash chain and enforces that each returned audit ref resolves against the canonical ledger. The focused storage tests show the lookup now fails closed on both tampered ledgers and unresolved audit references.

## Non-Blocking Strengths

- Runtime hardening is explicitly captured in `infra/security/runtime-profile.yaml` and reflected by `infra/docker/glassbox/Dockerfile`.
- Export writes are append-only and constrained to the sanctioned outbox.
- Gateway credentials remain host-side and run-scoped.
- Run-start manifests are immutable and proof lookups already fail closed for missing manifest, linkage, and log-bundle inputs.
- Recovery writes branch evidence into host-controlled mirror storage and explicitly marks that no outer repository branch was created.

## Clearance Condition

The proof-clearance file can be set to `cleared` for LAT-019. No proof blockers remain in the reviewed boundary, control, audit, and evidence scope.
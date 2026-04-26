# Live AI Terrarium / Glass-Box — Questionnaire Working File v1.0

Status: Completed 
Progress: 45 / 45 questions answered  
Current position: Completed

---

## How this working file will be used

This file is the live answer ledger for the questionnaire. After each answer, it should be updated with:

- the selected option,
- any custom wording or notes,
- a short architectural implication,
- the next current question.

---

# Selected Architecture Summary

- Boundary: Hard boundary: no host access, no shared mounts except a controlled export dir
- Isolation: Docker container per Glass-Box instance
- Evaluation: Core fitness selected: syntax pass, tests pass, no forbidden actions, plus stability and improvement trend
- Observability: Core signals selected: task/diff/score/test/errors, model/prompt/token/latency, and CPU/RAM/disk usage
- Reversibility: Snapshot strategy selected: per-cycle file-level snapshots, periodic full filesystem snapshots with per-cycle diffs, and Git repo inside sandbox with external mirror
- First Milestone: 10 stable cycles with full logs and rollback; dashboard shows diff, score, and decision per cycle

---

# Answer Ledger

## Chapter 1 — Boundary Model

### Q1.1 — What is the isolation layer?
Selected: Docker container per Glass-Box instance  
Notes: Chosen as the v1.0 practical baseline.  
Implication: Each Glass-Box instance should be represented as its own containerized runtime unit, giving clear lifecycle control, reproducibility, and a concrete first isolation boundary without VM-level overhead.

### Q1.2 — What is the boundary definition?
Selected: Hard boundary: no host access, no shared mounts except a controlled export dir  
Notes: Chosen as the v1.0 boundary contract.  
Implication: The sandbox must not directly see or mutate host files. All interaction with the host should pass through an intentionally designed control/export channel.

### Q1.3 — What crosses the boundary?
Selected: Logs, metrics, and diffs via controlled API + artifacts via append-only export channel  
Notes: Full filesystem snapshots and streamed events/pub-sub are explicitly reserved for future expansion.  
Implication: v1.0 should expose structured observability and artifact output without giving the sandbox general host access. The architecture should leave extension points for heavier snapshotting and real-time event streaming later.

Chapter notes: v1.0 boundary model is container-first, hard-isolated, and host-facing only through controlled API output plus append-only artifact export. Future expansion should keep explicit hooks for filesystem snapshots and event streaming.

---

## Chapter 2 — Threat Model

### Q2.1 — Disallowed actions inside Glass-Box
Selected: No host filesystem, no secrets, no network + no process spawning outside approved tools + time/CPU quotas with kill on breach  
Notes: Limited network / model API access is reserved for the external Model Gateway, not for the sandbox itself.  
Implication: The Glass-Box inner runtime should be treated as a constrained execution cell. It can act only through approved local tools, bounded resources, and an external gateway for model interaction.

### Q2.2 — Enforcement mechanism
Selected: Container + seccomp/apparmor + non-root + network egress blocked with allowlist proxy + filesystem ACLs and immutable mounts  
Notes: Runtime policy agent / OPA-like enforcement is reserved for future policy expansion.  
Implication: v1.0 enforcement should be layered but still practical: container hardening, non-root execution, blocked egress, controlled gateway access, and filesystem immutability around host-facing surfaces.

### Q2.3 — Audit guarantees
Selected: Append-only logs that cannot be deleted from inside + external host-controlled log sink + hash-chained logs for tamper evidence  
Notes: Periodic notarized snapshots are reserved for later compliance-grade audit mode.  
Implication: v1.0 audit design should make sandbox history externally visible, non-erasable from inside the sandbox, and tamper-evident without requiring heavyweight notarization infrastructure.

Chapter notes: v1.0 threat model blocks host filesystem access, secrets exposure, direct networking, unapproved process spawning, and runaway resource use. Enforcement is layered through container hardening, blocked egress, controlled gateway access, filesystem protections, and externally controlled tamper-evident logging.

---

## Chapter 3 — Control Philosophy

### Q3.1 — Default mode
Selected: Observation-only as the v1.0 default mode  
Notes: Prepare for controlled intervention as the next maturity step, and pre-prepare the architecture for future autonomous runs with guardrails.  
Implication: The first implementation should prioritize visibility, recording, and inspection without direct action. However, interfaces should not be designed as read-only dead ends; they should have clear extension points for explicit controlled actions and later guarded autonomy.

### Q3.2 — Mode switching
Selected: Explicit command via Glass-Box API + manual dashboard toggle  
Notes: The dashboard toggle should be a UI surface over the same explicit API command path, not a separate control mechanism. Policy-driven switching is reserved for later automation, and time-based schedules are reserved for scheduled experiment mode.  
Implication: v1.0 mode changes should be deliberate, visible, and auditable. Both CLI/API and dashboard actions should produce the same logged command event.

### Q3.3 — Emergency controls
Selected: Immediate pause + snapshot, followed by kill + rollback to last stable when needed  
Notes: Prepare for throttling as a future explicit control, and pre-prepare for quarantine mode as a later safety/security feature.  
Implication: v1.0 emergency handling should preserve state first, then restore safety if the instance cannot continue. The control model should leave clean extension points for non-destructive resource reduction and stronger isolation/quarantine workflows later.

Chapter notes: v1.0 control philosophy is observation-first, deliberately switchable, and emergency-safe. The system starts in observation-only mode, allows explicit API/dashboard mode switching, and responds to emergencies with pause/snapshot first, then kill/rollback when necessary. It should be architected for later controlled intervention, guarded autonomy, throttling, and quarantine.

---

## Chapter 4 — Observability Contract

### Q4.1 — Must-have signals
Selected: Task, diff, score, test result, errors + model, prompt, token usage, latency + resource usage CPU/RAM/disk  
Notes: Behavior tags and anomaly labels are prepared as a later annotation layer.  
Implication: v1.0 observability must capture both operational progress and model/runtime cost. Every cycle should be inspectable by task, change, result, failure mode, model context, latency, token use, and resource footprint.

### Q4.2 — Presentation layer
Selected: Streamlit dashboard + CLI dashboard / rich TUI  
Notes: Web UI / simple SPA is prepared as the long-term UI direction. Notebook-based reports remain optional exported analysis artifacts.  
Implication: v1.0 should expose both a quick visual dashboard and a developer-native terminal interface. Both should read from the same underlying observability records rather than implementing separate state models.

### Q4.3 — Data granularity
Selected: Per-cycle records + aggregated summaries with drill-down  
Notes: Event stream only is prepared for later real-time streaming expansion. Snapshot-only summaries are too coarse for the v1.0 Glass-Box contract.  
Implication: v1.0 should store fine-grained cycle records as the source of truth, then build aggregated dashboard views on top. This keeps reproducibility and inspection intact while making the system usable at a glance.

Chapter notes: v1.0 observability should be cycle-native and dashboard-friendly. The source of truth is detailed per-cycle records containing task, diff, score, tests, errors, model/prompt/token/latency data, and resource usage. Streamlit and CLI/TUI views should aggregate and drill down into the same records. Future expansion should include anomaly tags and real-time event streaming.

---

## Chapter 5 — Reversibility Model

### Q5.1 — Snapshot strategy
Selected: Per-cycle file-level snapshots + periodic full filesystem snapshots with per-cycle diffs + Git repo inside sandbox with external mirror  
Notes: Copy-on-write filesystem snapshots are reserved for future storage optimization.  
Implication: v1.0 reversibility should combine fine-grained cycle reconstruction, periodic full-state recovery points, and Git-based code history mirroring. This creates both operational rollback and human-readable code evolution history without depending on one mechanism alone.

### Q5.2 — Storage location
Selected: Host-controlled external storage + inside-sandbox local copy mirrored externally  
Notes: Remote object store / hybrid local+remote storage are prepared as backup and scaling expansions. Host-controlled storage remains the authoritative recovery and audit location.  
Implication: v1.0 should allow the sandbox to keep local working state for convenience, but durable truth must live outside the sandbox. Mirroring prevents the inner agent from being the sole owner of its own history.

### Q5.3 — Rollback policy
Selected: Manual rollback via Glass-Box command + branch-and-continue  
Notes: Automatic rollback on failed tests/score drops and threshold-based multi-step rollback are prepared for later once scoring is trusted.  
Implication: v1.0 should make rollback deliberate and auditable while preserving divergent paths. Failed or interesting states should be branchable instead of immediately destroyed, allowing investigation without contaminating the stable path.

Chapter notes: v1.0 reversibility combines per-cycle snapshots, periodic full-state snapshots, per-cycle diffs, and Git mirroring. Storage authority stays outside the sandbox, while local sandbox state can exist for convenience. Rollback is manual and command-driven, with branch-and-continue preserving useful divergent states. Automated rollback and copy-on-write storage are future upgrades.

---

## Chapter 6 — Evaluation Model

### Q6.1 — Core fitness signals
Selected: Syntax pass, tests pass, no forbidden actions + stability and improvement trend  
Notes: Code complexity reduction and runtime performance gains are kept as optional task-specific metrics.  
Implication: v1.0 evaluation should have hard safety/correctness gates plus a trend signal. A cycle must not be accepted if it is syntactically broken, fails required tests, or violates policy, and longer runs should be judged by whether they become more stable and improve over time.

### Q6.2 — Scoring method
Selected: Rule-based accept/reject gates + multi-objective Pareto scoring  
Notes: Weighted score with penalties is prepared for later ranking/summary use. Learned evaluator / secondary model is prepared for later evaluator expansion, but not as a first trust anchor.  
Implication: v1.0 evaluation should first decide whether a cycle is allowed through explicit gates, then compare valid candidates across multiple objectives without forcing everything into one premature score. This preserves clarity while supporting richer tradeoff analysis later.

### Q6.3 — Acceptance rule
Selected: Keep if all gates pass + no regression  
Notes: Score-based acceptance is not used as the v1.0 trust anchor. Probabilistic acceptance is reserved for explicit exploration mode, and ensemble decisions are reserved for later evaluator maturity.  
Implication: v1.0 acceptance should be deterministic and safety-first. A cycle is accepted only when required gates pass and no regression is detected, regardless of whether it appears interesting or exploratory.

Chapter notes: v1.0 evaluation is gate-first and regression-resistant. Syntax, tests, forbidden-action checks, stability, and improvement trend are the primary signals. Rule-based gates decide basic validity, while Pareto-style comparison can represent tradeoffs among valid candidates. Weighted scores and learned evaluators are later extensions, not initial trust anchors.

---

## Chapter 7 — Experiment Model

### Q7.1 — Hierarchy
Selected: Project → Glass-Box → Experiment → Run → Cycle → Mutation  
Notes: This is the full explicit hierarchy. A simplified implementation is allowed internally at first, but the conceptual model should preserve all levels.  
Implication: v1.0 should name and store records so they can later scale into a full experimental structure without renaming the world. Even if the first version only uses one project, one Glass-Box, and one experiment, the data model should already understand run/cycle/mutation boundaries.

### Q7.2 — Naming/IDs
Selected: Structured readable IDs + internal UUID with human label  
Notes: Timestamps should be stored as metadata, not used as the primary identity. Hash-based IDs can be used later for content-addressed artifacts.  
Implication: v1.0 should support both human-readable navigation and machine-safe uniqueness. Folders, logs, dashboards, and reports can show structured IDs, while internal records keep UUIDs to avoid collisions and preserve referential integrity.

### Q7.3 — Comparability
Selected: Identical seeds, tasks, and limits across runs + normalized metrics across models  
Notes: Scenario-based comparisons and rolling baselines are prepared for later benchmark and evolution modes.  
Implication: v1.0 comparisons should be controlled enough to be meaningful. Runs should share the same starting conditions and limits where possible, while metrics should be normalized so different models, tools, or configurations can be compared without raw-cost bias.

Chapter notes: v1.0 experiment modeling uses the full conceptual hierarchy Project → Glass-Box → Experiment → Run → Cycle → Mutation, even if the first implementation is simplified. IDs should be both readable and machine-safe. Comparability depends on identical seeds/tasks/limits plus normalized metrics, with later room for benchmark scenarios and rolling baselines.

---

## Chapter 8 — Agent Identity Model

### Q8.1 — Roles
Selected: Orchestrator, Model Gateway, Inner Agent, Evaluator, Dashboard + Observer/Annotator role  
Notes: The Observer/Annotator may be implemented lightly in v1.0 or kept as a formal reserved role boundary, but it belongs in the architecture model from the start.  
Implication: v1.0 role design should separate control, model access, sandbox execution, evaluation, visibility, and behavioral interpretation. This prevents one component from becoming an unclear super-agent and keeps future expansion clean.

### Q8.2 — Separation
Selected: Strict logical separation even if same model + modular code separation  
Notes: Physical service separation is prepared for later extraction. Dynamic role switching is reserved for mature agent orchestration.  
Implication: v1.0 should keep roles conceptually and structurally distinct without forcing microservices too early. Even if components run in one process or use the same underlying model, their prompts, permissions, state, and responsibilities should remain separate.

### Q8.3 — Agent naming
Selected: lait-agent-{type}-{id} + gb-agent-{id} per Glass-Box + role-prefixed IDs + experiment-scoped IDs  
Notes: Naming should combine project identity, Glass-Box identity, role clarity, and experiment/run scope rather than choosing only one flat style.  
Implication: v1.0 should define a composable naming convention. A practical pattern is: lait-gb-{glassbox_id}-{role}-{agent_id}, with experiment/run/cycle IDs stored as scope metadata or appended where useful. This keeps names readable, traceable, and scalable across many boxes, roles, and experiments.

Chapter notes: v1.0 agent identity uses explicit roles: Orchestrator, Model Gateway, Inner Agent, Evaluator, Dashboard, and Observer/Annotator. Roles should be logically and modularly separate even when implemented in the same runtime. Naming should be composable, combining project identity, Glass-Box identity, role, agent ID, and experiment/run scope metadata.

---

## Chapter 9 — Tool Permission Model

### Q9.1 — Allowed tools inside
Selected: Read/write own files, run tests, request model + limited shell via allowlisted commands  
Notes: Plugin-based tool registry is prepared as the future tool architecture. No-shell/API-only mode remains available as a higher-security mode, not the v1.0 default.  
Implication: v1.0 inner agents can operate on their own sandbox files, execute tests, request model calls through the gateway, and use a constrained shell only through explicitly approved commands. Tool access should be useful enough for real codebase work while still being narrow and auditable.

### Q9.2 — Forbidden tools
Selected: Docker/system control, host filesystem, network + editing dashboard/snapshots/log sinks + background daemons + dynamic code download  
Notes: v1.0 forbids all listed tool categories inside the Glass-Box. Any future exception must be explicit, scoped, logged, and routed through controlled outer services.  
Implication: The inner agent cannot control its containment layer, reach the host, rewrite its own audit/recovery surfaces, persist hidden background behavior, or fetch arbitrary code. This preserves containment, auditability, and reproducibility.

### Q9.3 — Tool interface
Selected: Typed API / functions + command spec with validation  
Notes: JSON-RPC tool calls are prepared for later service expansion. Message bus tools are reserved for distributed orchestration.  
Implication: v1.0 should expose tools through explicit function contracts and validated command specifications. This keeps tool calls testable, auditable, and constrained while still allowing practical shell-like workflows where needed.

Chapter notes: v1.0 tool permissions allow practical sandbox work through own-file read/write, tests, gateway-mediated model requests, and allowlisted shell commands. It forbids containment control, host filesystem/network access, editing audit/recovery surfaces, background daemons, and dynamic code download. Tool interfaces should be typed and validated, with later expansion toward JSON-RPC, plugin registries, and distributed message-bus tools.

---

## Chapter 10 — Human Intervention Model

### Q10.1 — Available actions
Selected: View, pause, resume, reset, branch + clone instance  
Notes: Inject task and change scoring are prepared as controlled intervention capabilities. Modify constraints live is not selected for v1.0 and should remain an advanced operator mode.  
Implication: v1.0 human intervention should focus on safe lifecycle and branching controls. The operator can inspect, pause, resume, reset, branch, and clone instances without directly mutating core constraints mid-run. Stronger intervention should be added through explicit, logged control paths later.

### Q10.2 — Interface
Selected: Dashboard controls + CLI commands / gb commands + API endpoints  
Notes: Chat interface is reserved for future conversational control. Dashboard and CLI should call the same API control layer rather than implementing separate control logic.  
Implication: v1.0 should provide visual, terminal, and programmatic control surfaces over one shared command backend. This keeps human control usable while preserving auditability and reducing duplicate logic.

### Q10.3 — Permissions
Selected: Single-user admin + audit-logged approvals  
Notes: Role-based access should be designed into the permission schema for later expansion, but v1.0 can operate as a single-user/admin prototype. Time-limited tokens are reserved for remote or team access.  
Implication: v1.0 can stay simple while still preserving accountability. Sensitive actions such as reset, rollback, scoring changes, task injection, or constraint modification should require explicit logged approvals even if there is only one admin user.

Chapter notes: v1.0 human intervention supports safe lifecycle controls: view, pause, resume, reset, branch, and clone. The interface should include dashboard controls, CLI/gb commands, and API endpoints over a shared backend. Permissions can begin as single-user admin but must audit-log sensitive approvals and leave room for later role-based access.

---

## Chapter 11 — Failure Policy

### Q11.1 — Stop conditions
Selected: Repeated crashes, syntax fail, score drop + forbidden action attempt + resource overuse + log silence  
Notes: All listed stop conditions are selected for v1.0. Forbidden action attempts and log silence should be treated as high-priority safety/visibility failures.  
Implication: v1.0 must stop when reliability, safety, resource control, or observability breaks. A run is not allowed to continue blindly if it crashes repeatedly, produces invalid code, regresses, attempts forbidden actions, exceeds resource bounds, or stops reporting telemetry.

### Q11.2 — Response
Selected: Pause → snapshot → rollback → report + branch failing path + kill → restore last stable  
Notes: The response order should prefer evidence preservation first. Kill/restore is used when the instance is unsafe or unrecoverable. Throttle-and-continue is prepared for later non-dangerous resource-control cases.  
Implication: v1.0 failure handling should not simply erase failed states. It should pause, capture evidence, optionally branch the failing path for investigation, then rollback or kill/restore depending on severity, and finally produce a report.

### Q11.3 — Reporting
Selected: Incident report per failure + aggregated failure dashboard  
Notes: Alert notifications are prepared for long-running/autonomous mode. Weekly summaries are reserved for a later reporting cadence.  
Implication: v1.0 should create a structured report for each failure and also aggregate failures across runs so patterns become visible. This supports both local debugging and system-level improvement.

Chapter notes: v1.0 failure policy stops on reliability failures, safety failures, resource failures, and visibility failures. Responses should preserve evidence first, branch informative failures, roll back or kill/restore depending on severity, and produce both per-failure incident reports and an aggregated failure dashboard.

---

## Chapter 12 — Data Retention Policy

### Q12.1 — What to keep
Selected: Logs, prompts, diffs, metrics, snapshots + model outputs and errors + resource traces + annotations  
Notes: All listed data categories are selected for v1.0 retention.  
Implication: v1.0 should preserve the complete reproducibility and diagnosis package: what was asked, what changed, what happened, what failed, what resources were used, what state can be restored, and what humans/observers noted.

### Q12.2 — Retention period
Selected: Full history, compressed + tiered storage hot/cold  
Notes: Rolling window + key snapshots may be added later as an optional storage-saving mode. Delete-after-export is rejected for the Glass-Box evolution system.  
Implication: v1.0 should preserve complete history for reproducibility and audit, while designing storage tiers so recent data remains easy to inspect and older data can be compressed or archived without deletion.

### Q12.3 — Storage
Selected: Local + backup + versioned filesystem  
Notes: Database + blobs are prepared for structured metadata and querying later. Object storage is prepared for remote scale, durable backup, and append-only storage expansion.  
Implication: v1.0 storage should remain simple, inspectable, and recoverable. A local versioned filesystem gives human-readable artifact/history management, while backup protects against local loss. The design should leave room for databases and object storage when query volume and scale justify them.

Chapter notes: v1.0 data retention keeps the complete reproducibility package: logs, prompts, diffs, metrics, snapshots, model outputs/errors, resource traces, and annotations. The system should keep full compressed history with hot/cold tiering. Storage starts as local + backup on a versioned filesystem, with later expansion toward database/blob indexing and remote object storage.

---

## Chapter 13 — Model Comparison Policy

### Q13.1 — Fairness
Selected: Identical tasks, seeds, and limits + normalized scoring  
Notes: Scenario-based sets are prepared for later benchmark suites. Adaptive tasks are reserved for advanced adaptive evaluation.  
Implication: v1.0 model comparisons should be controlled and fair. Models should receive equivalent tasks, seeds, and limits, while scoring should normalize for differences in cost, latency, token use, and tool behavior.

### Q13.2 — Metrics
Selected: Stability, success rate, improvement + regression frequency + efficiency tokens/time  
Notes: Code quality heuristics are prepared as a secondary quality layer.  
Implication: v1.0 model comparison should measure whether a model is reliable, successful, improving, regression-prone, and efficient. Correctness and stability dominate, while token/time efficiency helps judge practical usability and cost.

### Q13.3 — Reporting
Selected: Side-by-side dashboards + summary tables + trend graphs  
Notes: Narrative reports are prepared for generated review reports and milestone summaries.  
Implication: v1.0 model comparison should support immediate visual comparison, compact decision tables, and time-based trend analysis. Narrative reporting can later convert these structured results into human-readable review documents.

Chapter notes: v1.0 model comparison requires fair controlled inputs, normalized scoring, core reliability metrics, regression tracking, and efficiency measurement. Reporting should include side-by-side dashboards, summary tables, and trend graphs, with narrative review reports prepared as a later reporting layer.

---

## Chapter 14 — Networking Policy

### Q14.1 — Internet access
Selected: None inside Glass-Box + model API via external gateway only  
Notes: Allowlist domains are prepared for later controlled network mode. Full internet access with logging is rejected as the default.  
Implication: v1.0 should preserve the no-direct-network sandbox rule while still allowing model-powered work through a controlled external gateway. The sandbox should never freely browse or call arbitrary services from inside.

### Q14.2 — Gateway
Selected: Centralized model gateway + rate-limited proxy + per-run tokens  
Notes: Local model only is prepared as a future offline/private mode.  
Implication: v1.0 model access should be centralized, audited, rate-limited, and scoped per run. The sandbox should request model work through a controlled gateway rather than holding credentials or direct network access.

### Q14.3 — Security
Selected: No secrets in sandbox  
Notes: Ephemeral credentials are not selected as a sandbox feature for v1.0; any temporary credential handling should remain outside the sandbox in the gateway/controller layer if needed. Vault integration and key rotation are prepared for production-grade security later.  
Implication: v1.0 must enforce a strict zero-secrets sandbox rule. API keys, tokens, credentials, and service secrets belong only in controlled outer layers, never inside the Glass-Box runtime.

Chapter notes: v1.0 networking policy gives the Glass-Box no direct internet access. Model access happens only through a centralized, audited, rate-limited external gateway with per-run scoping. The sandbox must contain no secrets. Later expansion can add controlled domain allowlists, local/offline model mode, vault integration, and key rotation.

---

## Chapter 15 — Minimal First Milestone

### Q15.1 — Target
Selected: 10 stable cycles with full logs and rollback + dashboard shows diff, score, decision per cycle  
Notes: Multi-run comparison and automated reports are prepared for the next milestone after the core loop and inspectability are proven.  
Implication: The first milestone should prove both runtime behavior and visibility. The system must complete 10 stable cycles, preserve full logs, support rollback, and make each cycle inspectable through diff, score, and decision views.

### Q15.2 — Scope
Selected: Single agent, single sandbox + no network, simple tests  
Notes: Multiple agents and complex tasks are reserved for later milestones after the basic loop proves stable.  
Implication: The first milestone should be narrow and testable: one inner agent running in one isolated Glass-Box, with no direct network access and a simple test suite. This reduces moving parts while proving the core cycle architecture.

### Q15.3 — Success criteria
Selected: Zero unrecoverable failures + full observability and reproducibility  
Notes: Measurable improvement and stable long run are reserved as milestone-2 criteria.  
Implication: The first milestone succeeds if the system can run its 10-cycle proof without any unrecoverable failure, and if every accepted cycle can be inspected, explained, restored, and reproduced. Improvement is valuable, but the first proof is reliability plus glass-box visibility.

Chapter notes: v1.0 first milestone is a single-agent, single-sandbox, no-network proof that completes 10 stable cycles with full logs, rollback, and a dashboard showing diff, score, and decision per cycle. Success means zero unrecoverable failures plus full observability and reproducibility. Multi-run comparison, automated reports, measurable improvement, complex tasks, multiple agents, and long-run stability are reserved for later milestones.

---

# Decision Log

- Q1.1: Isolation layer = Docker container per Glass-Box instance.
- Q1.2: Boundary definition = Hard boundary with no host access and no shared mounts except a controlled export directory.
- Q1.3: Boundary crossings = Controlled API for logs/metrics/diffs + append-only artifact export. Future expansion: full filesystem snapshots and streamed events/pub-sub.

- Q2.1: Disallowed actions = No host filesystem, no secrets, no direct network, no unapproved process spawning, and hard time/CPU quotas. Model access belongs to an external Model Gateway.

- Q2.2: Enforcement mechanism = Hardened container with seccomp/apparmor, non-root runtime, blocked network egress with allowlist proxy, filesystem ACLs, and immutable mounts. Runtime policy agent reserved for future expansion.

- Q2.3: Audit guarantees = Append-only logs, external host-controlled log sink, and hash-chained tamper evidence. Periodic notarized snapshots reserved for later compliance-grade audit mode.

- Q3.1: Default mode = Observation-only for v1.0, with preparation for controlled intervention and early architectural preparation for future guarded autonomy.

- Q3.2: Mode switching = Explicit Glass-Box API command plus manual dashboard toggle. Dashboard controls must call the same auditable command path. Policy-driven and scheduled switching are reserved for later.

- Q3.3: Emergency controls = Immediate pause + snapshot, then kill + rollback to last stable when needed. Prepare for throttling; pre-prepare for quarantine mode.

- Q4.1: Must-have signals = Task, diff, score, test result, errors, model, prompt, token usage, latency, and CPU/RAM/disk. Behavior tags/anomalies reserved for later annotation.

- Q4.2: Presentation layer = Streamlit dashboard + CLI/rich TUI. Prepare Web UI/SPA as long-term direction; keep notebook reports as optional exports.

- Q4.3: Data granularity = Per-cycle records plus aggregated summaries with drill-down. Prepare event streaming for later; reject snapshot-only summaries as too coarse for v1.0.

- Q5.1: Snapshot strategy = Per-cycle file-level snapshots + periodic full filesystem snapshots with per-cycle diffs + Git repo inside sandbox with external mirror. Copy-on-write filesystem snapshots reserved for future storage optimization.

- Q5.2: Storage location = Host-controlled external storage plus inside-sandbox local copy mirrored externally. Remote object store / hybrid local+remote reserved for backup and scale expansion.

- Q5.3: Rollback policy = Manual rollback via Glass-Box command + branch-and-continue. Automatic and threshold-based rollback reserved until scoring is trusted.

- Q6.1: Core fitness signals = Syntax pass, tests pass, no forbidden actions, plus stability and improvement trend. Complexity reduction and runtime performance gains remain optional task-specific metrics.

- Q6.2: Scoring method = Rule-based accept/reject gates + multi-objective Pareto scoring. Prepare weighted scores for later ranking/summary use and learned evaluator for later expansion.

- Q6.3: Acceptance rule = Keep if all gates pass + no regression. Probabilistic acceptance reserved for explicit exploration mode; ensemble decisions reserved for later evaluator maturity.

- Q7.1: Experiment hierarchy = Project → Glass-Box → Experiment → Run → Cycle → Mutation. Simplified implementation allowed internally at first, but the full conceptual hierarchy is preserved.

- Q7.2: Naming/IDs = Structured readable IDs plus internal UUID with human label. Timestamps as metadata; hash-based IDs reserved for content-addressed artifacts.

- Q7.3: Comparability = Identical seeds/tasks/limits across runs plus normalized metrics across models. Scenario-based comparisons and rolling baselines reserved for later benchmark/evolution modes.

- Q8.1: Roles = Orchestrator, Model Gateway, Inner Agent, Evaluator, Dashboard, plus Observer/Annotator role in the architecture model.

- Q8.2: Separation = Strict logical separation even if same model + modular code separation. Prepare physical service separation for later; reserve dynamic role switching for mature orchestration.

- Q8.3: Agent naming = Combined convention using lait-agent style, gb-agent per Glass-Box, role-prefixed IDs, and experiment-scoped context. Practical pattern: lait-gb-{glassbox_id}-{role}-{agent_id}, with experiment/run/cycle scope as metadata or suffix where useful.

- Q9.1: Allowed tools inside = Read/write own files, run tests, request model, and limited shell via allowlisted commands. Plugin registry prepared for future; no-shell/API-only kept as high-security mode.

- Q9.2: Forbidden tools = Docker/system control, host filesystem, direct network, editing dashboard/snapshots/log sinks, background daemons, and dynamic code download. Future exceptions must be explicit, scoped, logged, and routed through outer services.

- Q9.3: Tool interface = Typed API/functions plus validated command specifications. JSON-RPC prepared for service expansion; message bus tools reserved for distributed orchestration.

- Q10.1: Available human actions = View, pause, resume, reset, branch, and clone instance. Prepare inject-task/change-scoring as controlled intervention; reserve live constraint modification for advanced operator mode.

- Q10.2: Human interface = Dashboard controls + CLI/gb commands + API endpoints. Chat interface reserved for future conversational control; dashboard and CLI should use the same API layer.

- Q10.3: Permissions = Single-user admin + audit-logged approvals. Design schema for later role-based access; reserve time-limited tokens for remote/team mode.

- Q11.1: Stop conditions = Repeated crashes, syntax fail, score drop, forbidden action attempt, resource overuse, and log silence. Forbidden actions and log silence are high-priority safety/visibility failures.

- Q11.2: Failure response = Pause → snapshot → rollback → report, branch failing path, and kill → restore last stable for unsafe/unrecoverable cases. Prepare throttle-and-continue for non-dangerous resource-control cases.

- Q11.3: Failure reporting = Incident report per failure + aggregated failure dashboard. Prepare alert notifications for long-running/autonomous mode; reserve weekly summaries for later cadence.

- Q12.1: Data to keep = Logs, prompts, diffs, metrics, snapshots, model outputs/errors, resource traces, and annotations.

- Q12.2: Retention period = Full history, compressed, plus tiered hot/cold storage. Rolling window may be added later as storage-saving mode; delete-after-export rejected.

- Q12.3: Storage = Local + backup + versioned filesystem. Prepare database+blobs for structured metadata/querying and object storage for remote scale/backup.

- Q13.1: Model comparison fairness = Identical tasks, seeds, and limits plus normalized scoring. Scenario-based sets prepared for later benchmark suites; adaptive tasks reserved for advanced adaptive evaluation.

- Q13.2: Model comparison metrics = Stability, success rate, improvement, regression frequency, and efficiency tokens/time. Code quality heuristics prepared as secondary quality layer.

- Q13.3: Model comparison reporting = Side-by-side dashboards, summary tables, and trend graphs. Narrative reports prepared for generated reviews and milestone summaries.

- Q14.1: Internet access = None inside Glass-Box + model API via external gateway only. Allowlist domains prepared for later controlled network mode; full access with logging rejected as default.

- Q14.2: Gateway = Centralized model gateway + rate-limited proxy + per-run tokens. Local model only prepared as future offline/private mode.

- Q14.3: Security = No secrets in sandbox. Ephemeral credential handling, if needed, belongs outside the sandbox in the gateway/controller layer. Vault integration and key rotation reserved for production-grade security.

- Q15.1: Minimal first milestone target = 10 stable cycles with full logs and rollback + dashboard showing diff, score, and decision per cycle. Multi-run comparison and automated reports reserved for next milestone.

- Q15.2: Minimal first milestone scope = Single agent, single sandbox, no network, and simple tests. Multiple agents and complex tasks reserved for later milestones.

- Q15.3: Success criteria = Zero unrecoverable failures + full observability and reproducibility. Measurable improvement and stable long run reserved for milestone 2.


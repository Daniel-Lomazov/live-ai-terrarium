from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from live_ai_terrarium.adapters.api.app import create_app
from live_ai_terrarium.contracts.records import ResourceUsage, TokenUsage
from live_ai_terrarium.control.commands import CommandEnvelope, CommandScope, ModeSwitchReceipt
from live_ai_terrarium.control.dispatcher import CommandDispatcher, DispatchContext
from live_ai_terrarium.query.read_models import (
    AuditStatusView,
    CommandReceiptView,
    CycleDetailView,
    ReproducibilityManifestSummary,
    ReversibilityView,
    RunSummaryView,
)


def make_scope(*, run_id: str = "run-stability-baseline") -> CommandScope:
    return CommandScope(
        project_id="project-live-ai-terrarium",
        glass_box_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id=run_id,
    )


def make_command_payload(*, idempotency_key: str) -> dict[str, object]:
    return {
        "scope": make_scope().model_dump(mode="json"),
        "actor_id": "operator-local",
        "actor_role": "operator",
        "occurred_at": "2026-04-26T10:00:00Z",
        "mode_context": "mode-context-1",
        "idempotency_key": idempotency_key,
        "surface_metadata": {"source": "api-test"},
    }


def make_run_summary() -> RunSummaryView:
    receipt = CommandReceiptView(
        action="mode switch",
        status="completed",
        occurred_at="2026-04-26T10:00:03Z",
        actor_id="operator-local",
        actor_role="operator",
        cycle_id=None,
        approval_id=None,
        receipt_id=UUID("11111111-1111-4111-8111-111111111111"),
        target_mode="control-enabled",
        target_cycle_id=None,
        reason=None,
    )
    return RunSummaryView(
        run_id="run-stability-baseline",
        current_mode="observation-only",
        lifecycle_state="active",
        observation_mode_state="observation-only",
        active_mode_switch_receipt=None,
        available_actions=("observe", "mode switch"),
        deny_reason_by_action={
            "pause": "Active mode-switch receipt required for this scope.",
            "resume": "Active mode-switch receipt required for this scope.",
            "branch": "Active mode-switch receipt required for this scope.",
            "clone": "Active mode-switch receipt required for this scope.",
            "reset": "Active mode-switch receipt required for this scope.",
            "rollback": "Active mode-switch receipt required for this scope.",
        },
        audit_status=AuditStatusView(
            latest_command_receipts={"mode switch": receipt},
            timeline=(receipt,),
        ),
        approval_status="not-requested",
        incident_state="clear",
        last_stable_cycle="cycle-0001",
        rollback_target="cycle-0001",
        snapshot_refs=("snapshots/cycles/cycle-0001/manifest.json",),
        branch_clone_refs=(),
        reproducibility_manifest=ReproducibilityManifestSummary(
            created_at="2026-04-26T09:59:59Z",
            task_identity="LAT-024",
            seed=7,
            model_version="gpt-5.4",
            outer_repo_commit_sha="a" * 40,
            container_image_digest="sha256:" + ("b" * 64),
            limits={"max_cycles": 10},
            release_tag="v1.0.1",
            image_name="glassbox:v1",
            runtime_profile_locator="security/runtime-profile.yaml",
            runtime_profile_sha256=None,
            command_catalog_locator="security/command-specs.yaml",
            command_catalog_sha256=None,
        ),
        full_log_bundle_refs=("logs/full-log-bundle.jsonl",),
        cycle_summaries=(),
    )


def make_cycle_detail() -> CycleDetailView:
    receipt = CommandReceiptView(
        action="pause",
        status="denied",
        occurred_at="2026-04-26T10:05:00Z",
        actor_id="operator-local",
        actor_role="operator",
        cycle_id="cycle-0002",
        approval_id=None,
        receipt_id=UUID("22222222-2222-4222-8222-222222222222"),
        target_mode=None,
        target_cycle_id=None,
        reason="pause requires an active mode-switch receipt for the same scope and mode context",
    )
    return CycleDetailView(
        run_id="run-stability-baseline",
        cycle_id="cycle-0002",
        current_mode="observation-only",
        lifecycle_state="active",
        observation_mode_state="observation-only",
        active_mode_switch_receipt=None,
        available_actions=("observe", "mode switch"),
        deny_reason_by_action={
            "pause": "Active mode-switch receipt required for this scope.",
            "resume": "Active mode-switch receipt required for this scope.",
            "branch": "Active mode-switch receipt required for this scope.",
            "clone": "Active mode-switch receipt required for this scope.",
            "reset": "Active mode-switch receipt required for this scope.",
            "rollback": "Active mode-switch receipt required for this scope.",
        },
        approval_status="not-requested",
        gate_decision="rejected",
        score=0.41,
        test_result="failed",
        error_summary="regression detected in smoke tests",
        diff_summary="Updated worker logic for cycle-0002.",
        model_identity="gpt-5.4",
        prompt_ref="prompts/cycle-0002.json",
        token_usage=TokenUsage(input_tokens=102, output_tokens=22, total_tokens=146),
        latency_ms=902,
        resources=ResourceUsage(cpu_percent=44.5, ram_mb=258, disk_mb=1026),
        snapshot_refs=("snapshots/cycles/cycle-0002/manifest.json",),
        audit_event_refs=("audit/cycle-0002/requested.json",),
        full_log_bundle_ref="logs/cycle-0002/full-log-bundle.jsonl",
        audit_timeline=(receipt,),
        reversibility=ReversibilityView(
            incident_state="clear",
            incident_id=None,
            incident_report_ref=None,
            snapshot_ref=None,
            branch_ref=None,
            ordered_steps=(),
            full_log_refs=(),
            last_stable_cycle="cycle-0001",
            rollback_target="cycle-0001",
            recovery_outcome=None,
            restore_manifest_ref=None,
        ),
        reproducibility_manifest=ReproducibilityManifestSummary(
            created_at="2026-04-26T09:59:59Z",
            task_identity="LAT-024",
            seed=7,
            model_version="gpt-5.4",
            outer_repo_commit_sha="a" * 40,
            container_image_digest="sha256:" + ("b" * 64),
            limits={"max_cycles": 10},
            release_tag="v1.0.1",
            image_name="glassbox:v1",
            runtime_profile_locator="security/runtime-profile.yaml",
            runtime_profile_sha256=None,
            command_catalog_locator="security/command-specs.yaml",
            command_catalog_sha256=None,
        ),
    )


@dataclass
class RecordingCommandBackend:
    context: DispatchContext
    calls: list[dict[str, object]] = field(default_factory=list)
    handled_actions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._dispatcher = CommandDispatcher(handler=self._handle)

    def dispatch_command(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        cycle_id: str | None = None,
        reason: str | None = None,
        approval_actor_id: str | None = None,
        approval_actor_role: str | None = None,
        approval_occurred_at: str | None = None,
        approval_reason: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "command": command,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "occurred_at": occurred_at,
                "mode_context": mode_context,
                "cycle_id": cycle_id,
                "reason": reason,
                "approval_actor_id": approval_actor_id,
                "approval_actor_role": approval_actor_role,
                "approval_occurred_at": approval_occurred_at,
                "approval_reason": approval_reason,
            }
        )
        result = self._dispatcher.dispatch(command, self.context)
        return {
            "command": command.model_dump(mode="json"),
            "dispatch_result": result.model_dump(mode="json"),
        }

    def _handle(self, command: CommandEnvelope) -> dict[str, object]:
        self.handled_actions.append(command.action)
        return {
            "handled_action": command.action,
            "run_id": command.scope.run_id,
        }


@dataclass
class RecordingQueryBackend:
    run_summary: RunSummaryView = field(default_factory=make_run_summary)
    cycle_detail: CycleDetailView = field(default_factory=make_cycle_detail)
    run_calls: list[CommandScope] = field(default_factory=list)
    cycle_calls: list[tuple[CommandScope, str]] = field(default_factory=list)

    def observe_run(self, scope: CommandScope) -> RunSummaryView:
        self.run_calls.append(scope)
        return self.run_summary

    def observe_cycle(self, scope: CommandScope, *, cycle_id: str) -> CycleDetailView:
        self.cycle_calls.append((scope, cycle_id))
        return self.cycle_detail


def test_api_routes_canonical_actions_through_shared_backend() -> None:
    unlocked_backend = RecordingCommandBackend(
        context=DispatchContext(
            current_mode="control-enabled",
            mode_context="mode-context-1",
            mode_switch_receipt=ModeSwitchReceipt(
                scope=make_scope(),
                mode_context="mode-context-1",
                target_mode="control-enabled",
                status="active",
            ),
        )
    )
    query_backend = RecordingQueryBackend()
    client = TestClient(create_app(command_backend=unlocked_backend, query_backend=query_backend))

    observe_response = client.get(
        "/api/observe/runs/project-live-ai-terrarium/gb-local-dev/exp-proof-loop/run-stability-baseline"
    )

    assert observe_response.status_code == 200
    assert len(query_backend.run_calls) == 1

    command_paths = {
        "mode switch": "/api/commands/mode-switch",
        "pause": "/api/commands/pause",
        "resume": "/api/commands/resume",
        "branch": "/api/commands/branch",
        "clone": "/api/commands/clone",
        "reset": "/api/commands/reset",
        "rollback": "/api/commands/rollback",
    }

    for action, path in command_paths.items():
        payload = make_command_payload(idempotency_key=f"{action}-once")
        if action == "mode switch":
            payload["target_mode"] = "control-enabled"
        response = client.post(path, json=payload)

        assert response.status_code == 202
        assert response.json()["command"]["action"] == action

    assert unlocked_backend.handled_actions == [
        "mode switch",
        "pause",
        "resume",
        "branch",
        "clone",
        "reset",
        "rollback",
    ]
    assert [call["command"].surface for call in unlocked_backend.calls] == ["api"] * 7


def test_api_returns_deny_receipts_for_control_actions_before_mode_switch() -> None:
    locked_backend = RecordingCommandBackend(
        context=DispatchContext(
            current_mode="observation-only",
            mode_context="mode-context-1",
        )
    )
    client = TestClient(create_app(command_backend=locked_backend, query_backend=RecordingQueryBackend()))

    for action in ("pause", "resume", "branch", "clone", "reset", "rollback"):
        response = client.post(f"/api/commands/{action}", json=make_command_payload(idempotency_key=f"{action}-deny"))

        assert response.status_code == 403
        assert response.json()["command"]["action"] == action
        assert response.json()["dispatch_result"]["status"] == "denied"
        assert response.json()["dispatch_result"]["deny_reason"] == (
            f"{action} requires an active mode-switch receipt for the same scope and mode context"
        )

    assert locked_backend.handled_actions == []


def test_api_observe_routes_passthrough_shared_read_models() -> None:
    query_backend = RecordingQueryBackend()
    client = TestClient(
        create_app(
            command_backend=RecordingCommandBackend(
                context=DispatchContext(
                    current_mode="observation-only",
                    mode_context="mode-context-1",
                )
            ),
            query_backend=query_backend,
        )
    )

    run_response = client.get(
        "/api/observe/runs/project-live-ai-terrarium/gb-local-dev/exp-proof-loop/run-stability-baseline"
    )
    cycle_response = client.get(
        "/api/observe/runs/project-live-ai-terrarium/gb-local-dev/exp-proof-loop/run-stability-baseline/cycles/cycle-0002"
    )

    assert run_response.status_code == 200
    assert cycle_response.status_code == 200
    assert run_response.json() == jsonable_encoder(query_backend.run_summary)
    assert cycle_response.json() == jsonable_encoder(query_backend.cycle_detail)
    assert query_backend.run_calls == [make_scope()]
    assert query_backend.cycle_calls == [(make_scope(), "cycle-0002")]
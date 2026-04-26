from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from live_ai_terrarium.audit.ledger import AuditLedgerEntry
from live_ai_terrarium.contracts.records import ArtifactRef, CycleRecord, IncidentRecord, RunRecord
from live_ai_terrarium.control.commands import CANONICAL_ACTIONS, CONTROL_ACTIONS, CanonicalAction, OBSERVATION_ONLY_MODE
from live_ai_terrarium.orchestrator.runtime import LifecycleReceipt
from live_ai_terrarium.storage.run_evidence import CycleAuditLink, RunStartManifest

from .read_models import (
    ActiveModeSwitchReceiptView,
    ApprovalState,
    AuditStatusView,
    CommandReceiptView,
    CycleDetailView,
    CycleSummaryView,
    IncidentState,
    ObservationModeState,
    ReproducibilityManifestSummary,
    ReversibilityView,
    RunSummaryView,
)

_MODE_SWITCH_REQUESTED_STATUSES = {"requested", "approval_requested"}
_MODE_SWITCH_ACTIVE_STATUSES = {"approved", "started", "completed"}
_RECOVERY_ACTIONS: tuple[CanonicalAction, ...] = ("branch", "clone", "reset", "rollback")
_CONTROL_BLOCK_REASON = "Active mode-switch receipt required for this scope."


class QueryService:
    def build_run_summary(
        self,
        *,
        run_record: RunRecord,
        cycle_records: Sequence[CycleRecord],
        audit_events: Sequence[AuditLedgerEntry],
        lifecycle_receipt: LifecycleReceipt,
        manifest: RunStartManifest,
        cycle_links: Mapping[str, CycleAuditLink],
        incident_records: Sequence[IncidentRecord],
        recovery_reports: Mapping[str, Mapping[str, object]],
    ) -> RunSummaryView:
        sorted_cycles = tuple(sorted(cycle_records, key=self._cycle_sort_key))
        audit_status = self._build_audit_status(audit_events)
        active_receipt = self._active_mode_switch_receipt(audit_events, current_mode=lifecycle_receipt.current_mode)
        approval_status = self._approval_status(audit_status, active_receipt)
        incident_by_cycle = {record.cycle_id.readable_id: record for record in incident_records}
        last_stable_cycle = self._last_stable_cycle(sorted_cycles)
        rollback_target = self._rollback_target(
            lifecycle_receipt=lifecycle_receipt,
            last_stable_cycle=last_stable_cycle,
            recovery_reports=recovery_reports.values(),
        )
        incident_state: IncidentState = "open" if incident_records else "clear"
        observation_mode_state = self._observation_mode_state(
            current_mode=lifecycle_receipt.current_mode,
            lifecycle_receipt=lifecycle_receipt,
            active_mode_switch_receipt=active_receipt,
            audit_status=audit_status,
            incident_state=incident_state,
        )
        available_actions, deny_reason_by_action = self._available_actions(active_receipt)
        cycle_summaries = tuple(
            CycleSummaryView(
                cycle_id=cycle.cycle_id.readable_id,
                gate_decision=cycle.gate_decision,
                score=cycle.score,
                test_result=cycle.test_result,
                error_summary=cycle.error_summary,
                full_log_bundle_ref=self._artifact_locator(cycle_links.get(cycle.cycle_id.readable_id), cycle.full_log_bundle_ref),
                log_sequence_range=self._log_sequence_range(cycle_links.get(cycle.cycle_id.readable_id)),
                has_incident=cycle.cycle_id.readable_id in incident_by_cycle,
            )
            for cycle in sorted_cycles
        )
        reversibility_views = [
            self._reversibility_view(
                incident_record=incident,
                recovery_report=recovery_reports.get(incident.incident_id.readable_id),
                last_stable_cycle=last_stable_cycle,
                rollback_target=rollback_target,
            )
            for incident in incident_records
        ]

        return RunSummaryView(
            run_id=run_record.run_id.readable_id,
            current_mode=lifecycle_receipt.current_mode,
            lifecycle_state=lifecycle_receipt.lifecycle_state,
            observation_mode_state=observation_mode_state,
            active_mode_switch_receipt=active_receipt,
            available_actions=available_actions,
            deny_reason_by_action=deny_reason_by_action,
            audit_status=audit_status,
            approval_status=approval_status,
            incident_state=incident_state,
            last_stable_cycle=last_stable_cycle,
            rollback_target=rollback_target,
            snapshot_refs=self._collect_snapshot_refs(sorted_cycles, incident_records),
            branch_clone_refs=self._collect_branch_refs(reversibility_views),
            reproducibility_manifest=self._manifest_summary(manifest),
            full_log_bundle_refs=self._collect_full_log_bundle_refs(
                run_record=run_record,
                cycle_records=sorted_cycles,
                cycle_links=cycle_links,
                reversibility_views=reversibility_views,
            ),
            cycle_summaries=cycle_summaries,
        )

    def build_cycle_detail(
        self,
        *,
        cycle_record: CycleRecord,
        run_record: RunRecord,
        audit_events: Sequence[AuditLedgerEntry],
        lifecycle_receipt: LifecycleReceipt,
        manifest: RunStartManifest,
        cycle_link: CycleAuditLink,
        incident_record: IncidentRecord | None,
        recovery_report: Mapping[str, object] | None,
    ) -> CycleDetailView:
        audit_status = self._build_audit_status(audit_events)
        active_receipt = self._active_mode_switch_receipt(audit_events, current_mode=lifecycle_receipt.current_mode)
        approval_status = self._approval_status(audit_status, active_receipt)
        observation_mode_state = self._observation_mode_state(
            current_mode=lifecycle_receipt.current_mode,
            lifecycle_receipt=lifecycle_receipt,
            active_mode_switch_receipt=active_receipt,
            audit_status=audit_status,
            incident_state="open" if incident_record is not None else "clear",
        )
        available_actions, deny_reason_by_action = self._available_actions(active_receipt)
        reversibility = self._reversibility_view(
            incident_record=incident_record,
            recovery_report=recovery_report,
            last_stable_cycle=self._last_stable_cycle((cycle_record,)),
            rollback_target=self._rollback_target(
                lifecycle_receipt=lifecycle_receipt,
                last_stable_cycle=self._last_stable_cycle((cycle_record,)),
                recovery_reports=(() if recovery_report is None else (recovery_report,)),
            ),
        )
        if reversibility.last_stable_cycle is None and lifecycle_receipt.target_cycle_id is not None:
            reversibility = ReversibilityView(
                incident_state=reversibility.incident_state,
                incident_id=reversibility.incident_id,
                incident_report_ref=reversibility.incident_report_ref,
                snapshot_ref=reversibility.snapshot_ref,
                branch_ref=reversibility.branch_ref,
                ordered_steps=reversibility.ordered_steps,
                full_log_refs=reversibility.full_log_refs,
                last_stable_cycle=lifecycle_receipt.target_cycle_id,
                rollback_target=reversibility.rollback_target,
                recovery_outcome=reversibility.recovery_outcome,
                restore_manifest_ref=reversibility.restore_manifest_ref,
            )
        return CycleDetailView(
            run_id=run_record.run_id.readable_id,
            cycle_id=cycle_record.cycle_id.readable_id,
            current_mode=lifecycle_receipt.current_mode,
            lifecycle_state=lifecycle_receipt.lifecycle_state,
            observation_mode_state=observation_mode_state,
            active_mode_switch_receipt=active_receipt,
            available_actions=available_actions,
            deny_reason_by_action=deny_reason_by_action,
            approval_status=approval_status,
            gate_decision=cycle_record.gate_decision,
            score=cycle_record.score,
            test_result=cycle_record.test_result,
            error_summary=cycle_record.error_summary,
            diff_summary=cycle_record.diff_summary,
            model_identity=cycle_record.model_identity,
            prompt_ref=cycle_record.prompt_ref.locator,
            token_usage=cycle_record.token_usage,
            latency_ms=cycle_record.latency_ms,
            resources=cycle_record.resources,
            snapshot_refs=tuple(ref.locator for ref in cycle_record.snapshot_refs),
            audit_event_refs=tuple(ref.locator for ref in cycle_link.audit_event_refs),
            full_log_bundle_ref=cycle_link.full_log_bundle_ref.locator,
            audit_timeline=audit_status.timeline,
            reversibility=reversibility,
            reproducibility_manifest=self._manifest_summary(manifest),
        )

    def _build_audit_status(self, audit_events: Sequence[AuditLedgerEntry]) -> AuditStatusView:
        timeline = tuple(self._receipt_view(event) for event in sorted(audit_events, key=lambda item: item.occurred_at))
        latest_command_receipts: dict[CanonicalAction, CommandReceiptView] = {}
        for item in timeline:
            latest_command_receipts[item.action] = item
        return AuditStatusView(latest_command_receipts=latest_command_receipts, timeline=timeline)

    def _receipt_view(self, event: AuditLedgerEntry) -> CommandReceiptView:
        return CommandReceiptView(
            action=event.action,
            status=event.event_type.removeprefix("command."),
            occurred_at=event.occurred_at,
            actor_id=event.actor_id,
            actor_role=event.actor_role,
            cycle_id=event.cycle_id,
            approval_id=event.approval_id,
            receipt_id=event.receipt_id,
            target_mode=self._detail_text(event.details, "target_mode"),
            target_cycle_id=self._detail_text(event.details, "target_cycle_id"),
            reason=self._detail_text(event.details, "reason"),
        )

    def _active_mode_switch_receipt(
        self,
        audit_events: Sequence[AuditLedgerEntry],
        *,
        current_mode: str,
    ) -> ActiveModeSwitchReceiptView | None:
        receipt_groups: dict[object, list[AuditLedgerEntry]] = {}
        for event in sorted(audit_events, key=lambda item: item.occurred_at):
            if event.action != "mode switch" or event.receipt_id is None:
                continue
            receipt_groups.setdefault(event.receipt_id, []).append(event)
        for receipt_id in reversed(tuple(receipt_groups.keys())):
            events = receipt_groups[receipt_id]
            statuses = {event.event_type.removeprefix("command.") for event in events}
            if not statuses.intersection(_MODE_SWITCH_ACTIVE_STATUSES):
                continue
            target_mode = self._first_text(events, "target_mode") or current_mode
            mode_context = self._first_text(events, "mode_context")
            if mode_context is None or target_mode != current_mode:
                continue
            return ActiveModeSwitchReceiptView(receipt_id=receipt_id, target_mode=target_mode, mode_context=mode_context)
        return None

    def _approval_status(
        self,
        audit_status: AuditStatusView,
        active_mode_switch_receipt: ActiveModeSwitchReceiptView | None,
    ) -> ApprovalState:
        if active_mode_switch_receipt is not None:
            return "approved"
        mode_switch_receipt = audit_status.latest_command_receipts.get("mode switch")
        if mode_switch_receipt is None:
            return "not-requested"
        if mode_switch_receipt.status in _MODE_SWITCH_REQUESTED_STATUSES:
            return "requested"
        if mode_switch_receipt.status == "approved":
            return "approved"
        if mode_switch_receipt.status == "rejected":
            return "rejected"
        return "not-requested"

    def _observation_mode_state(
        self,
        *,
        current_mode: str,
        lifecycle_receipt: LifecycleReceipt,
        active_mode_switch_receipt: ActiveModeSwitchReceiptView | None,
        audit_status: AuditStatusView,
        incident_state: IncidentState,
    ) -> ObservationModeState:
        if active_mode_switch_receipt is not None:
            return "mode-switch active"
        mode_switch_receipt = audit_status.latest_command_receipts.get("mode switch")
        if mode_switch_receipt is not None and mode_switch_receipt.status in _MODE_SWITCH_REQUESTED_STATUSES:
            return "mode-switch requested"
        if lifecycle_receipt.lifecycle_state == "paused":
            return "paused"
        recovery_receipt = self._latest_recovery_receipt(audit_status)
        if recovery_receipt is not None and recovery_receipt.status == "started":
            return "recovery executing"
        if recovery_receipt is not None and recovery_receipt.status == "completed":
            return "recovery completed"
        if incident_state == "open":
            return "incident open"
        if current_mode == OBSERVATION_ONLY_MODE:
            return "observation-only"
        return "mode-switch active"

    def _latest_recovery_receipt(self, audit_status: AuditStatusView) -> CommandReceiptView | None:
        for action in reversed(_RECOVERY_ACTIONS):
            receipt = audit_status.latest_command_receipts.get(action)
            if receipt is not None:
                return receipt
        return None

    def _available_actions(
        self,
        active_mode_switch_receipt: ActiveModeSwitchReceiptView | None,
    ) -> tuple[tuple[CanonicalAction, ...], dict[CanonicalAction, str]]:
        if active_mode_switch_receipt is not None:
            return tuple(CANONICAL_ACTIONS), {}
        return (
            ("observe", "mode switch"),
            {action: _CONTROL_BLOCK_REASON for action in CONTROL_ACTIONS},
        )

    def _last_stable_cycle(self, cycle_records: Sequence[CycleRecord]) -> str | None:
        stable_cycles = [cycle.cycle_id.readable_id for cycle in sorted(cycle_records, key=self._cycle_sort_key) if cycle.gate_decision == "accepted"]
        if not stable_cycles:
            return None
        return stable_cycles[-1]

    def _rollback_target(
        self,
        *,
        lifecycle_receipt: LifecycleReceipt,
        last_stable_cycle: str | None,
        recovery_reports: Iterable[Mapping[str, object]],
    ) -> str | None:
        if lifecycle_receipt.target_cycle_id is not None:
            return lifecycle_receipt.target_cycle_id
        for report in recovery_reports:
            recovery = self._mapping(report.get("recovery"))
            rollback_target = self._text(recovery.get("rollback_target"))
            if rollback_target is not None:
                return rollback_target
        return last_stable_cycle

    def _manifest_summary(self, manifest: RunStartManifest) -> ReproducibilityManifestSummary:
        return ReproducibilityManifestSummary(
            created_at=manifest.created_at,
            task_identity=manifest.task_identity,
            seed=manifest.seed,
            model_version=manifest.model_version,
            outer_repo_commit_sha=manifest.outer_repo_commit_sha,
            container_image_digest=manifest.container_image_digest,
            limits=dict(manifest.limits.values),
            release_tag=manifest.supplemental_labels.get("release_tag"),
            image_name=manifest.supplemental_labels.get("image_name"),
            runtime_profile_locator=self._hash_or_snapshot_locator(manifest.runtime_profile),
            runtime_profile_sha256=manifest.runtime_profile.sha256,
            command_catalog_locator=self._hash_or_snapshot_locator(manifest.command_catalog),
            command_catalog_sha256=manifest.command_catalog.sha256,
        )

    def _hash_or_snapshot_locator(self, reference) -> str | None:
        if reference.snapshot_ref is None:
            return None
        return reference.snapshot_ref.locator

    def _collect_snapshot_refs(
        self,
        cycle_records: Sequence[CycleRecord],
        incident_records: Sequence[IncidentRecord],
    ) -> tuple[str, ...]:
        snapshot_refs: list[str] = []
        for cycle in cycle_records:
            snapshot_refs.extend(ref.locator for ref in cycle.snapshot_refs)
        snapshot_refs.extend(
            incident.snapshot_ref.locator
            for incident in incident_records
        )
        return self._unique(snapshot_refs)

    def _collect_branch_refs(self, reversibility_views: Sequence[ReversibilityView]) -> tuple[str, ...]:
        return self._unique(
            view.branch_ref
            for view in reversibility_views
            if view.branch_ref is not None
        )

    def _collect_full_log_bundle_refs(
        self,
        *,
        run_record: RunRecord,
        cycle_records: Sequence[CycleRecord],
        cycle_links: Mapping[str, CycleAuditLink],
        reversibility_views: Sequence[ReversibilityView],
    ) -> tuple[str, ...]:
        refs: list[str] = []
        if run_record.full_log_bundle_ref is not None:
            refs.append(run_record.full_log_bundle_ref.locator)
        for cycle in cycle_records:
            link = cycle_links.get(cycle.cycle_id.readable_id)
            if link is not None:
                refs.append(link.full_log_bundle_ref.locator)
            else:
                refs.append(cycle.full_log_bundle_ref.locator)
        for view in reversibility_views:
            refs.extend(view.full_log_refs)
        return self._unique(refs)

    def _reversibility_view(
        self,
        *,
        incident_record: IncidentRecord | None,
        recovery_report: Mapping[str, object] | None,
        last_stable_cycle: str | None,
        rollback_target: str | None,
    ) -> ReversibilityView:
        report = self._mapping(recovery_report)
        recovery = self._mapping(report.get("recovery"))
        branch = self._mapping(report.get("branch"))
        derived_last_stable = rollback_target or last_stable_cycle
        return ReversibilityView(
            incident_state="open" if incident_record is not None else "clear",
            incident_id=None if incident_record is None else incident_record.incident_id.readable_id,
            incident_report_ref=None if incident_record is None else incident_record.incident_report_ref.locator,
            snapshot_ref=None if incident_record is None else incident_record.snapshot_ref.locator,
            branch_ref=(
                incident_record.branch_ref.locator
                if incident_record is not None and incident_record.branch_ref is not None
                else self._text(branch.get("branch_ref"))
            ),
            ordered_steps=tuple(self._text_list(report.get("ordered_steps"))),
            full_log_refs=tuple(self._text_list(report.get("full_log_refs"))),
            last_stable_cycle=derived_last_stable,
            rollback_target=rollback_target,
            recovery_outcome=(
                incident_record.recovery_outcome
                if incident_record is not None and incident_record.recovery_outcome is not None
                else self._text(recovery.get("outcome"))
            ),
            restore_manifest_ref=self._text(recovery.get("restore_manifest")),
        )

    def _artifact_locator(self, cycle_link: CycleAuditLink | None, fallback: ArtifactRef) -> str:
        if cycle_link is not None:
            return cycle_link.full_log_bundle_ref.locator
        return fallback.locator

    def _log_sequence_range(self, cycle_link: CycleAuditLink | None) -> tuple[int, int] | None:
        if cycle_link is None:
            return None
        return (cycle_link.log_sequence_start, cycle_link.log_sequence_end)

    def _cycle_sort_key(self, cycle_record: CycleRecord) -> tuple[int, str]:
        readable_id = cycle_record.cycle_id.readable_id
        try:
            return (int(readable_id.rsplit("-", 1)[-1]), readable_id)
        except ValueError:
            return (0, readable_id)

    def _detail_text(self, details: Mapping[str, object], key: str) -> str | None:
        return self._text(details.get(key))

    def _first_text(self, audit_events: Sequence[AuditLedgerEntry], key: str) -> str | None:
        for event in reversed(audit_events):
            value = self._detail_text(event.details, key)
            if value is not None:
                return value
        return None

    def _mapping(self, value: object) -> Mapping[str, object]:
        if isinstance(value, Mapping):
            return value
        return {}

    def _text(self, value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return None

    def _text_list(self, value: object) -> tuple[str, ...]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return ()
        items: list[str] = []
        for item in value:
            text = self._text(item)
            if text is not None:
                items.append(text)
        return tuple(items)

    def _unique(self, values: Iterable[str | None]) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value is None or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return tuple(ordered)


__all__ = ["QueryService"]
from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..audit.ledger import AuditLedger, AuditLedgerEntry, AuditMetadataValue, AuditEvent
from .commands import CanonicalAction, CommandEnvelope, ModeSwitchReceipt

ApprovalStatus = Literal["requested", "approved", "rejected"]


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: UUID = Field(default_factory=uuid4)
    command: CommandEnvelope
    status: ApprovalStatus
    requested_at: str
    requested_by: str
    requested_by_role: str
    requested_mode_context: str
    reason: str | None = None
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolved_by_role: str | None = None
    mode_switch_receipt: ModeSwitchReceipt | None = None

    @field_validator(
        "requested_at",
        "requested_by",
        "requested_by_role",
        "requested_mode_context",
    )
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @field_validator("reason", "resolved_at", "resolved_by", "resolved_by_role")
    @classmethod
    def validate_optional_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _require_text(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_state(self) -> ApprovalRecord:
        resolved_fields = (self.resolved_at, self.resolved_by, self.resolved_by_role)
        if self.status == "requested":
            if any(field is not None for field in resolved_fields):
                raise ValueError("requested approvals cannot be resolved")
            if self.mode_switch_receipt is not None:
                raise ValueError("requested approvals cannot carry a mode-switch receipt")
            return self
        if any(field is None for field in resolved_fields):
            raise ValueError("resolved approvals require resolved_at, resolved_by, and resolved_by_role")
        if self.status == "approved" and self.command.action == "mode switch" and self.mode_switch_receipt is None:
            raise ValueError("approved mode switches require an active mode-switch receipt")
        if self.status == "rejected" and self.mode_switch_receipt is not None:
            raise ValueError("rejected approvals cannot carry a mode-switch receipt")
        return self


class ApprovalService:
    def __init__(
        self,
        *,
        ledger: AuditLedger,
        approval_required_actions: tuple[CanonicalAction, ...] = ("mode switch",),
    ) -> None:
        self._ledger = ledger
        self._approval_required_actions = set(approval_required_actions)
        self._records: dict[UUID, ApprovalRecord] = {}

    def requires_approval(self, command: CommandEnvelope) -> bool:
        return command.action in self._approval_required_actions

    def record_request(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        reason: str | None = None,
        cycle_id: str | None = None,
        details: dict[str, AuditMetadataValue] | None = None,
    ) -> ApprovalRecord | None:
        payload_details = dict(details or {})
        if reason is not None:
            payload_details["reason"] = reason
        payload_details["mode_context"] = mode_context
        self._record_event(
            command,
            event_type="command.requested",
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            cycle_id=cycle_id,
            details=payload_details,
        )
        if not self.requires_approval(command):
            return None
        approval = ApprovalRecord(
            command=command,
            status="requested",
            requested_at=occurred_at,
            requested_by=actor_id,
            requested_by_role=actor_role,
            requested_mode_context=mode_context,
            reason=reason,
        )
        self._records[approval.approval_id] = approval
        self._record_event(
            command,
            event_type="command.approval_requested",
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            cycle_id=cycle_id,
            approval_id=approval.approval_id,
            details={"mode_context": mode_context, **({"reason": reason} if reason is not None else {})},
        )
        return approval

    def approve(
        self,
        approval_id: UUID,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        mode_context: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        approval = self._get_record(approval_id)
        if approval.status != "requested":
            raise ValueError("approval is already resolved")
        receipt = self._receipt_for_approval(approval, mode_context=mode_context)
        approved = approval.model_copy(
            update={
                "status": "approved",
                "resolved_at": occurred_at,
                "resolved_by": actor_id,
                "resolved_by_role": actor_role,
                "reason": reason if reason is not None else approval.reason,
                "mode_switch_receipt": receipt,
            }
        )
        self._records[approval_id] = approved
        self._record_event(
            approved.command,
            event_type="command.approved",
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            approval_id=approval_id,
            receipt_id=receipt.receipt_id if receipt is not None else None,
            details={"mode_context": mode_context, **({"reason": reason} if reason is not None else {})},
        )
        return approved

    def reject(
        self,
        approval_id: UUID,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        approval = self._get_record(approval_id)
        if approval.status != "requested":
            raise ValueError("approval is already resolved")
        rejected = approval.model_copy(
            update={
                "status": "rejected",
                "resolved_at": occurred_at,
                "resolved_by": actor_id,
                "resolved_by_role": actor_role,
                "reason": reason if reason is not None else approval.reason,
            }
        )
        self._records[approval_id] = rejected
        self._record_event(
            rejected.command,
            event_type="command.rejected",
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            approval_id=approval_id,
            details={"reason": rejected.reason} if rejected.reason is not None else None,
        )
        return rejected

    def record_started(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        approval_id: UUID | None = None,
        cycle_id: str | None = None,
        details: dict[str, AuditMetadataValue] | None = None,
    ) -> AuditLedgerEntry:
        approved = self._require_approved_record(command, approval_id)
        return self._record_event(
            command,
            event_type="command.started",
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            cycle_id=cycle_id,
            approval_id=approval_id,
            receipt_id=self._receipt_id(approved),
            details=details,
        )

    def record_completed(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        approval_id: UUID | None = None,
        cycle_id: str | None = None,
        details: dict[str, AuditMetadataValue] | None = None,
    ) -> AuditLedgerEntry:
        approved = self._require_approved_record(command, approval_id)
        return self._record_event(
            command,
            event_type="command.completed",
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            cycle_id=cycle_id,
            approval_id=approval_id,
            receipt_id=self._receipt_id(approved),
            details=details,
        )

    def record_failed(
        self,
        command: CommandEnvelope,
        *,
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        approval_id: UUID | None = None,
        cycle_id: str | None = None,
        details: dict[str, AuditMetadataValue] | None = None,
    ) -> AuditLedgerEntry:
        approved = self._require_approved_record(command, approval_id)
        return self._record_event(
            command,
            event_type="command.failed",
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            cycle_id=cycle_id,
            approval_id=approval_id,
            receipt_id=self._receipt_id(approved),
            details=details,
        )

    def _get_record(self, approval_id: UUID) -> ApprovalRecord:
        approval = self._records.get(approval_id)
        if approval is None:
            raise KeyError(f"unknown approval_id: {approval_id}")
        return approval

    def _receipt_for_approval(
        self,
        approval: ApprovalRecord,
        *,
        mode_context: str,
    ) -> ModeSwitchReceipt | None:
        if approval.command.action != "mode switch":
            return None
        target_mode = approval.command.target_mode
        if target_mode is None:
            raise ValueError("mode switch approvals require a target mode")
        return ModeSwitchReceipt(
            scope=approval.command.scope,
            mode_context=mode_context,
            target_mode=target_mode,
            status="active",
        )

    def _require_approved_record(
        self,
        command: CommandEnvelope,
        approval_id: UUID | None,
    ) -> ApprovalRecord | None:
        if not self.requires_approval(command):
            return None
        if approval_id is None:
            raise PermissionError("command lifecycle requires an approved approval record")
        approval = self._get_record(approval_id)
        if approval.command.command_id != command.command_id or approval.status != "approved":
            raise PermissionError("command lifecycle requires an approved approval record")
        return approval

    def _receipt_id(self, approval: ApprovalRecord | None) -> UUID | None:
        if approval is None or approval.mode_switch_receipt is None:
            return None
        return approval.mode_switch_receipt.receipt_id

    def _record_event(
        self,
        command: CommandEnvelope,
        *,
        event_type: Literal[
            "command.requested",
            "command.approval_requested",
            "command.approved",
            "command.rejected",
            "command.started",
            "command.completed",
            "command.failed",
        ],
        actor_id: str,
        actor_role: str,
        occurred_at: str,
        cycle_id: str | None = None,
        approval_id: UUID | None = None,
        receipt_id: UUID | None = None,
        details: dict[str, AuditMetadataValue] | None = None,
    ) -> AuditLedgerEntry:
        return self._ledger.append(
            AuditEvent(
                command_id=command.command_id,
                action=command.action,
                event_type=event_type,
                occurred_at=occurred_at,
                actor_id=actor_id,
                actor_role=actor_role,
                scope=command.scope,
                cycle_id=cycle_id,
                approval_id=approval_id,
                receipt_id=receipt_id,
                details=details or {},
            )
        )


__all__ = ["ApprovalRecord", "ApprovalService", "ApprovalStatus"]
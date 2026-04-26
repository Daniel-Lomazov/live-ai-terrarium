from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from live_ai_terrarium.contracts.records import TokenUsage
from live_ai_terrarium.storage.paths import RunScope


def _require_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


class GatewayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID = Field(default_factory=uuid4)
    run: RunScope
    model: str
    prompt: str
    max_output_tokens: int = Field(gt=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("model", "prompt")
    @classmethod
    def validate_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            _require_text(key, field_name="metadata key"): _require_text(item, field_name=f"metadata[{key}]")
            for key, item in value.items()
        }


class GatewayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: UUID | None = None
    run: RunScope
    model: str
    output_text: str
    usage: TokenUsage | None = None
    stop_reason: str = "completed"

    @field_validator("model", "output_text", "stop_reason")
    @classmethod
    def validate_text(cls, value: str, info) -> str:
        return _require_text(value, field_name=info.field_name)


@dataclass(frozen=True)
class GatewayRunBinding:
    run: RunScope
    credential_handle: str
    allowed_models: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.credential_handle, field_name="credential_handle")
        if not self.allowed_models:
            raise ValueError("allowed_models must not be empty")
        for model in self.allowed_models:
            _require_text(model, field_name="allowed_model")


@dataclass(frozen=True)
class GatewayInvocation:
    request: GatewayRequest
    credential_handle: str
    allowed_models: tuple[str, ...]


class GatewayTransport(Protocol):
    def __call__(self, invocation: GatewayInvocation) -> GatewayResponse: ...


class HostModelGatewayService:
    def __init__(self, *, transport: GatewayTransport) -> None:
        self._transport = transport
        self._bindings: dict[RunScope, GatewayRunBinding] = {}

    def register_run(
        self,
        run: RunScope,
        *,
        credential_handle: str,
        allowed_models: tuple[str, ...],
    ) -> GatewayRunBinding:
        binding = GatewayRunBinding(
            run=run,
            credential_handle=credential_handle,
            allowed_models=tuple(dict.fromkeys(allowed_models)),
        )
        self._bindings[run] = binding
        return binding

    def generate(self, request: GatewayRequest) -> GatewayResponse:
        binding = self._require_binding(request.run)
        if request.model not in binding.allowed_models:
            raise PermissionError(f"model '{request.model}' is not allowed for this run")

        response = self._transport(
            GatewayInvocation(
                request=request,
                credential_handle=binding.credential_handle,
                allowed_models=binding.allowed_models,
            )
        )
        if response.run != request.run:
            raise ValueError("gateway transport must return the same run scope that it received")
        if response.model != request.model:
            raise ValueError("gateway transport must return the same model that it received")
        if response.request_id is None:
            return response.model_copy(update={"request_id": request.request_id})
        return response

    def _require_binding(self, run: RunScope) -> GatewayRunBinding:
        try:
            return self._bindings[run]
        except KeyError as error:
            raise KeyError(f"run scope is not registered for gateway access: {run.run_id}") from error


__all__ = [
    "GatewayInvocation",
    "GatewayRequest",
    "GatewayResponse",
    "GatewayRunBinding",
    "HostModelGatewayService",
]
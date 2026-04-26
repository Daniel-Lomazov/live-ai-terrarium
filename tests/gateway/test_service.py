from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from live_ai_terrarium.contracts.records import TokenUsage
from live_ai_terrarium.gateway.service import GatewayRequest, GatewayResponse, HostModelGatewayService
from live_ai_terrarium.storage.paths import RunScope


def make_run_scope(*, run_id: str = "run-stability-baseline") -> RunScope:
    return RunScope(
        project_id="project-live-ai-terrarium",
        glassbox_id="gb-local-dev",
        experiment_id="exp-proof-loop",
        run_id=run_id,
    )


@dataclass
class RecordingTransport:
    calls: list[object] = field(default_factory=list)

    def __call__(self, invocation) -> GatewayResponse:
        self.calls.append(invocation)
        return GatewayResponse(
            run=invocation.request.run,
            model=invocation.request.model,
            output_text="host-mediated response",
            usage=TokenUsage(input_tokens=5, output_tokens=7, total_tokens=12),
        )


def test_gateway_service_scopes_requests_per_run_and_keeps_credentials_host_side() -> None:
    transport = RecordingTransport()
    service = HostModelGatewayService(transport=transport)
    run_scope = make_run_scope()

    binding = service.register_run(
        run_scope,
        credential_handle="gateway-credential-ref",
        allowed_models=("gpt-5.4",),
    )
    response = service.generate(
        GatewayRequest(
            run=run_scope,
            model="gpt-5.4",
            prompt="Summarize the current cycle.",
            max_output_tokens=128,
        )
    )

    assert binding.run == run_scope
    assert response.run == run_scope
    assert response.model == "gpt-5.4"
    assert response.output_text == "host-mediated response"
    assert transport.calls[0].credential_handle == "gateway-credential-ref"
    assert transport.calls[0].request.prompt == "Summarize the current cycle."


def test_gateway_service_rejects_unregistered_runs_and_disallowed_models() -> None:
    service = HostModelGatewayService(transport=RecordingTransport())
    run_scope = make_run_scope()
    service.register_run(
        run_scope,
        credential_handle="gateway-credential-ref",
        allowed_models=("gpt-5.4",),
    )

    with pytest.raises(KeyError, match="run scope"):
        service.generate(
            GatewayRequest(
                run=make_run_scope(run_id="run-other"),
                model="gpt-5.4",
                prompt="Explain the diff.",
                max_output_tokens=64,
            )
        )

    with pytest.raises(PermissionError, match="allowed for this run"):
        service.generate(
            GatewayRequest(
                run=run_scope,
                model="gpt-4.1",
                prompt="Explain the diff.",
                max_output_tokens=64,
            )
        )


def test_gateway_request_is_secret_free_and_forbids_extra_fields() -> None:
    run_scope = make_run_scope()

    with pytest.raises(ValidationError):
        GatewayRequest(
            run=run_scope,
            model="gpt-5.4",
            prompt="Explain the diff.",
            max_output_tokens=64,
            credential_handle="should-not-be-here",
        )
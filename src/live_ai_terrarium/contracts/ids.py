from __future__ import annotations

import re
from typing import ClassVar, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
READABLE_ID_PATTERN = re.compile(r"^(?P<prefix>[a-z]+)-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$")


def _validate_slug(slug: str) -> str:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("slug must contain lowercase ASCII letters, digits, and hyphens only")
    return slug


class ReadableId(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prefix: ClassVar[str]

    uuid: UUID
    readable_id: str
    label: str | None = None

    @field_validator("readable_id")
    @classmethod
    def validate_readable_id(cls, value: str) -> str:
        match = READABLE_ID_PATTERN.fullmatch(value)
        if match is None:
            raise ValueError("readable_id must match <prefix>-<slug>")
        if match.group("prefix") != cls.prefix:
            raise ValueError(f"readable_id must start with '{cls.prefix}-'")
        return value

    @classmethod
    def from_slug(cls, slug: str, *, uuid: UUID, label: str | None = None) -> Self:
        return cls(uuid=uuid, readable_id=f"{cls.prefix}-{_validate_slug(slug)}", label=label)

    @property
    def slug(self) -> str:
        return self.readable_id.removeprefix(f"{self.prefix}-")


class ProjectId(ReadableId):
    prefix = "project"


class GlassBoxId(ReadableId):
    prefix = "gb"


class ExperimentId(ReadableId):
    prefix = "exp"


class RunId(ReadableId):
    prefix = "run"


class CycleId(ReadableId):
    prefix = "cycle"


class MutationId(ReadableId):
    prefix = "mutation"


class IncidentId(ReadableId):
    prefix = "incident"


class AgentId(ReadableId):
    prefix = "agent"


__all__ = [
    "AgentId",
    "CycleId",
    "ExperimentId",
    "GlassBoxId",
    "IncidentId",
    "MutationId",
    "ProjectId",
    "READABLE_ID_PATTERN",
    "ReadableId",
    "RunId",
    "SLUG_PATTERN",
]
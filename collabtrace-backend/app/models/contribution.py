from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    COMMIT = "COMMIT"
    PULL_REQUEST = "PULL_REQUEST"
    ISSUE = "ISSUE"
    REVIEW = "REVIEW"


class ContributionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    repository: str
    event_type: EventType
    author_login: str | None = None
    title: str
    created_at: datetime | None = None
    github_url: str | None = None
    source_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)

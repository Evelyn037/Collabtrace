from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.contribution import EventType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


def validate_password(value: str) -> str:
    if not value.strip():
        raise ValueError("password must not be blank")
    return value


class UserSummary(ORMModel):
    id: int
    username: str
    display_name: str
    role: UserRole
    email: str | None = None


class LoginRequest(BaseModel):
    identifier: str | None = Field(default=None, min_length=1, max_length=320)
    username: str | None = Field(default=None, min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier", "username")
    @classmethod
    def trim_login_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("login identifier must not be blank")
        return value

    @model_validator(mode="after")
    def require_identifier(self):
        if not self.identifier and not self.username:
            raise ValueError("identifier or legacy username is required")
        return self


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserSummary


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.MEMBER
    email: EmailStr | None = None

    _validate_password = field_validator("password")(validate_password)

    @field_validator("username", "display_name")
    @classmethod
    def trim_user_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def trim_optional_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value


class UserResponse(UserSummary):
    is_active: bool
    created_at: datetime
    email_verified: bool | None = None


class VerificationPurpose(str, Enum):
    REGISTER = "REGISTER"
    LOGIN = "LOGIN"


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    _validate_password = field_validator("password")(validate_password)

    @field_validator("username")
    @classmethod
    def trim_registration_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("username must not be blank")
        return value

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("passwords do not match")
        return self


class RegistrationResponse(UserSummary):
    email: str


class MembershipResponse(BaseModel):
    repository_id: int
    repository_full_name: str
    member_id: int
    display_name: str
    github_username: str


class RepositoryCreate(BaseModel):
    owner: str = Field(min_length=1, max_length=100)
    repo: str = Field(min_length=1, max_length=100)

    @field_validator("owner", "repo")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class RepositoryAnalyzeRequest(BaseModel):
    repository: str = Field(min_length=3, max_length=500)

    @field_validator("repository")
    @classmethod
    def trim_repository(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("repository must not be blank")
        return value


class RepositoryResponse(ORMModel):
    id: int
    owner: str
    name: str
    full_name: str
    github_repo_id: int
    html_url: str
    description: str | None
    default_branch: str
    is_private: bool
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime
    current_user_role: UserRole = UserRole.MEMBER


class RepositoryDetail(RepositoryResponse):
    member_count: int
    event_count: int


class MemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    github_username: str = Field(min_length=1, max_length=100)
    user_id: int | None = None

    @field_validator("display_name", "github_username")
    @classmethod
    def trim_member_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class MemberUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    github_username: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("display_name", "github_username")
    @classmethod
    def trim_optional_member_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class MemberResponse(ORMModel):
    id: int
    repository_id: int
    display_name: str
    github_username: str
    github_user_id: int | None
    user_id: int | None
    created_at: datetime
    updated_at: datetime
    mapped_event_count: int = 0


class MemberMutationResponse(BaseModel):
    member: MemberResponse
    remapped_events: int


class SyncResponse(BaseModel):
    repository_id: int
    repository: str
    status: Literal["SUCCESS", "FAILED", "RUNNING"]
    fetched: int
    inserted: int
    updated: int
    unchanged: int
    mapped: int
    unmapped: int
    started_at: datetime
    finished_at: datetime | None


class SyncRecordResponse(ORMModel):
    id: int
    repository_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    fetched_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    mapped_count: int
    unmapped_count: int
    error_message: str | None


class EventResponse(BaseModel):
    id: int
    event_id: str
    event_type: EventType
    author_login: str | None
    member_id: int | None
    member_display_name: str | None
    title: str
    github_url: str | None
    event_created_at: datetime | None
    metadata: dict[str, Any]


class EventListResponse(BaseModel):
    total: int
    items: list[EventResponse]


class UnmappedContributor(BaseModel):
    github_username: str
    event_count: int


class EventTotals(BaseModel):
    events: int = 0
    commits: int = 0
    pull_requests: int = 0
    issues: int = 0
    reviews: int = 0


class OverviewResponse(BaseModel):
    repository: RepositoryResponse
    totals: EventTotals
    members: int
    mapped_events: int
    unmapped_events: int
    last_sync_at: datetime | None


class MemberStatsResponse(BaseModel):
    member_id: int
    display_name: str
    github_username: str
    total_events: int
    commits: int
    pull_requests: int
    issues: int
    reviews: int


class TimelinePoint(BaseModel):
    date: str
    commits: int
    pull_requests: int
    issues: int
    reviews: int
    total: int


class ContributorStatsResponse(BaseModel):
    github_username: str
    member_id: int | None
    user_id: int | None
    display_name: str
    is_mapped: bool
    is_bot: bool
    rank: int
    total_events: int
    commits: int
    pull_requests: int
    issues: int
    reviews: int


class ContributionDimensions(BaseModel):
    code: float = 0
    pr: float = 0
    issue: float = 0
    review: float = 0


class ContributionRawMetrics(BaseModel):
    effective_commits: int
    raw_commits: int
    filtered_churn: int
    robust_churn: float
    merged_prs: int
    effective_issues: int
    effective_reviews: int


class ContributionIndexContributor(BaseModel):
    github_username: str
    display_name: str
    member_id: int | None
    user_id: int | None
    is_mapped: bool
    is_bot: bool
    total_events: int
    activity_rank: int
    rci: float
    rci_rank: int
    dimension_scores: ContributionDimensions
    composition: ContributionDimensions
    raw_metrics: ContributionRawMetrics
    weighted_contributions: ContributionDimensions


class MetricCoverage(BaseModel):
    code_churn_coverage: float
    pr_status_coverage: float
    issue_state_reason_coverage: float
    review_metadata_coverage: float


class ContributionAnalysisScope(BaseModel):
    description: str
    last_sync_at: datetime | None


class ContributionIndexResponse(BaseModel):
    repository_id: int
    methodology_version: Literal["RCI_V1"]
    mode: Literal["RESEARCH_BASELINE", "CUSTOM_WEIGHTS"]
    requested_weights: ContributionDimensions
    effective_weights: ContributionDimensions
    active_dimensions: list[Literal["code", "pr", "issue", "review"]]
    metric_coverage: MetricCoverage
    analysis_scope: ContributionAnalysisScope
    contributors: list[ContributionIndexContributor]


class AnalysisScope(BaseModel):
    max_pages: int
    max_prs_for_reviews: int
    scope_limited: bool = True


class RepositoryAnalyzeResponse(BaseModel):
    repository: RepositoryResponse
    created: bool
    sync: SyncResponse
    analysis_scope: AnalysisScope


class RepositoryAccessUpdate(BaseModel):
    role: UserRole


class RepositoryAccessResponse(BaseModel):
    user_id: int
    username: str
    display_name: str
    email: str | None
    is_active: bool
    role: UserRole
    explicit: bool

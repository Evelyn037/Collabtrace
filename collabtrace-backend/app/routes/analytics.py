from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.dependencies.auth import CurrentUser, RepositoryAdminUser
from app.models.contribution import EventType
from app.models.schemas import ContributionIndexResponse, ContributorStatsResponse, EventListResponse, MemberStatsResponse, OverviewResponse, TimelinePoint, UnmappedContributor
from app.services.analytics_service import AnalyticsService
from app.services.contribution_index_service import ContributionIndexService

router = APIRouter(prefix="/api/repositories/{repository_id}", tags=["Analytics"])
DB = Annotated[Session, Depends(get_db)]


@router.get("/contributor-stats", response_model=list[ContributorStatsResponse])
def contributor_stats(repository_id: int, db: DB, _: CurrentUser, exclude_bots: bool = True):
    return AnalyticsService(db).contributor_stats(repository_id, exclude_bots)


@router.get("/contribution-index", response_model=ContributionIndexResponse)
def contribution_index(
    repository_id: int, db: DB, _: CurrentUser, exclude_bots: bool = True,
    weight_code: Annotated[float | None, Query(ge=0)] = None,
    weight_pr: Annotated[float | None, Query(ge=0)] = None,
    weight_issue: Annotated[float | None, Query(ge=0)] = None,
    weight_review: Annotated[float | None, Query(ge=0)] = None,
):
    values = {
        "code": weight_code, "pr": weight_pr,
        "issue": weight_issue, "review": weight_review,
    }
    custom = None if all(value is None for value in values.values()) else {
        key: (1.0 if value is None else value) for key, value in values.items()
    }
    try:
        return ContributionIndexService(db).calculate(repository_id, exclude_bots, custom)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/contributors/{username}", response_model=ContributorStatsResponse)
def contributor_detail(repository_id: int, username: str, db: DB, _: CurrentUser):
    return AnalyticsService(db).contributor_detail(repository_id, username)


@router.get("/contributors/{username}/timeline", response_model=list[TimelinePoint])
def contributor_timeline(repository_id: int, username: str, db: DB, _: CurrentUser,
                         granularity: Annotated[str, Query(pattern="^day$")] = "day"):
    return AnalyticsService(db).contributor_timeline(repository_id, username)


@router.get("/events", response_model=EventListResponse)
def events(repository_id: int, db: DB, _: CurrentUser, member_id: int | None = None,
           event_type: EventType | None = None, author_login: str | None = None,
           limit: Annotated[int, Query(ge=1, le=200)] = 50,
           offset: Annotated[int, Query(ge=0)] = 0):
    return AnalyticsService(db).events(
        repository_id, member_id, event_type.value if event_type else None,
        author_login, limit, offset
    )


@router.get("/unmapped-contributors", response_model=list[UnmappedContributor])
def unmapped_contributors(repository_id: int, db: DB, _: RepositoryAdminUser):
    return AnalyticsService(db).unmapped_contributors(repository_id)


@router.get("/overview", response_model=OverviewResponse)
def overview(repository_id: int, db: DB, _: CurrentUser):
    return AnalyticsService(db).overview(repository_id)


@router.get("/member-stats", response_model=list[MemberStatsResponse])
def member_stats(repository_id: int, db: DB, _: CurrentUser):
    return AnalyticsService(db).member_stats(repository_id)


@router.get("/members/{member_id}/timeline", response_model=list[TimelinePoint])
def member_timeline(repository_id: int, member_id: int, db: DB, _: CurrentUser,
                    granularity: Annotated[str, Query(pattern="^day$")] = "day"):
    return AnalyticsService(db).member_timeline(repository_id, member_id)


@router.get("/timeline", response_model=list[TimelinePoint])
def repository_timeline(repository_id: int, db: DB, _: CurrentUser,
                        granularity: Annotated[str, Query(pattern="^day$")] = "day"):
    return AnalyticsService(db).repository_timeline(repository_id)

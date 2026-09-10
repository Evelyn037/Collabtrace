from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.database.models import ContributionEventRecord as Event
from app.database.models import Member, Repository
from app.models.contribution import EventType
from app.services.errors import NotFoundError


TYPE_FIELDS = {
    EventType.COMMIT.value: "commits",
    EventType.PULL_REQUEST.value: "pull_requests",
    EventType.ISSUE.value: "issues",
    EventType.REVIEW.value: "reviews",
}


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def _repository(self, repository_id: int) -> Repository:
        repository = self.db.get(Repository, repository_id)
        if repository is None:
            raise NotFoundError("Repository not found")
        return repository

    def events(self, repository_id: int, member_id: int | None, event_type: str | None,
               author_login: str | None, limit: int, offset: int) -> dict:
        self._repository(repository_id)
        filters = [Event.repository_id == repository_id]
        if member_id is not None:
            filters.append(Event.member_id == member_id)
        if event_type:
            filters.append(Event.event_type == event_type)
        if author_login:
            filters.append(func.lower(Event.author_login) == author_login.strip().lower())
        total = self.db.scalar(select(func.count(Event.id)).where(*filters)) or 0
        rows = self.db.execute(
            select(Event, Member.display_name).outerjoin(Member, Event.member_id == Member.id)
            .where(*filters).order_by(Event.event_created_at.desc(), Event.id.desc())
            .offset(offset).limit(limit)
        ).all()
        return {"total": total, "items": [self._event_dict(event, display_name) for event, display_name in rows]}

    @staticmethod
    def _event_dict(event: Event, member_display_name: str | None) -> dict:
        return {
            "id": event.id, "event_id": event.event_id, "event_type": event.event_type,
            "author_login": event.author_login, "member_id": event.member_id,
            "member_display_name": member_display_name, "title": event.title,
            "github_url": event.github_url, "event_created_at": event.event_created_at,
            "metadata": event.metadata_json or {},
        }

    def unmapped_contributors(self, repository_id: int) -> list[dict]:
        self._repository(repository_id)
        rows = self.db.execute(
            select(func.lower(Event.author_login), func.count(Event.id))
            .where(Event.repository_id == repository_id, Event.member_id.is_(None), Event.author_login.is_not(None))
            .group_by(func.lower(Event.author_login)).order_by(func.count(Event.id).desc())
        ).all()
        return [{"github_username": username, "event_count": count} for username, count in rows]

    def overview(self, repository_id: int) -> dict:
        repository = self._repository(repository_id)
        counts = self._type_counts(repository_id)
        members = self.db.scalar(select(func.count(Member.id)).where(Member.repository_id == repository_id)) or 0
        mapped = self.db.scalar(select(func.count(Event.id)).where(Event.repository_id == repository_id, Event.member_id.is_not(None))) or 0
        unmapped = counts["events"] - mapped
        return {"repository": repository, "totals": counts, "members": members,
                "mapped_events": mapped, "unmapped_events": unmapped, "last_sync_at": repository.last_sync_at}

    def _type_counts(self, repository_id: int) -> dict[str, int]:
        rows = self.db.execute(
            select(Event.event_type, func.count(Event.id)).where(Event.repository_id == repository_id).group_by(Event.event_type)
        ).all()
        counts = {"events": 0, "commits": 0, "pull_requests": 0, "issues": 0, "reviews": 0}
        for event_type, count in rows:
            counts["events"] += count
            if event_type in TYPE_FIELDS:
                counts[TYPE_FIELDS[event_type]] = count
        return counts

    def member_stats(self, repository_id: int) -> list[dict]:
        self._repository(repository_id)
        expressions = [func.count(Event.id).label("total_events")]
        expressions += [func.sum(case((Event.event_type == event_type, 1), else_=0)).label(field)
                        for event_type, field in TYPE_FIELDS.items()]
        rows = self.db.execute(
            select(Member.id.label("member_id"), Member.display_name, Member.github_username, *expressions)
            .outerjoin(Event, Event.member_id == Member.id).where(Member.repository_id == repository_id)
            .group_by(Member.id).order_by(func.count(Event.id).desc(), Member.id)
        ).mappings().all()
        return [dict(row) for row in rows]

    def member_timeline(self, repository_id: int, member_id: int) -> list[dict]:
        self._repository(repository_id)
        if self.db.scalar(select(Member.id).where(Member.id == member_id, Member.repository_id == repository_id)) is None:
            raise NotFoundError("Member not found")
        return self._timeline(repository_id, member_id)

    def repository_timeline(self, repository_id: int) -> list[dict]:
        self._repository(repository_id)
        return self._timeline(repository_id, None)

    def contributor_stats(self, repository_id: int, exclude_bots: bool = True) -> list[dict]:
        self._repository(repository_id)
        username = func.lower(Event.author_login).label("github_username")
        expressions = [func.count(Event.id).label("total_events")]
        expressions += [
            func.sum(case((Event.event_type == event_type, 1), else_=0)).label(field)
            for event_type, field in TYPE_FIELDS.items()
        ]
        rows = self.db.execute(
            select(username, *expressions)
            .where(Event.repository_id == repository_id, Event.author_login.is_not(None))
            .group_by(username)
            .order_by(func.count(Event.id).desc(), username.asc())
        ).mappings().all()
        members = {
            member.github_username.lower(): member
            for member in self.db.scalars(select(Member).where(Member.repository_id == repository_id))
        }
        result = []
        for row in rows:
            github_username = row["github_username"]
            is_bot = github_username.endswith("[bot]")
            if exclude_bots and is_bot:
                continue
            member = members.get(github_username)
            result.append({
                **dict(row),
                "member_id": member.id if member else None,
                "user_id": member.user_id if member else None,
                "display_name": member.display_name if member else github_username,
                "is_mapped": member is not None,
                "is_bot": is_bot,
                "rank": len(result) + 1,
            })
        return result

    def contributor_detail(self, repository_id: int, github_username: str) -> dict:
        normalized = github_username.strip().lower()
        match = next(
            (item for item in self.contributor_stats(repository_id, exclude_bots=False)
             if item["github_username"] == normalized),
            None,
        )
        if match is None:
            raise NotFoundError("Contributor not found")
        return match

    def contributor_timeline(self, repository_id: int, github_username: str) -> list[dict]:
        self.contributor_detail(repository_id, github_username)
        normalized = github_username.strip().lower()
        day = func.date(Event.event_created_at).label("date")
        expressions = [
            func.sum(case((Event.event_type == event_type, 1), else_=0)).label(field)
            for event_type, field in TYPE_FIELDS.items()
        ]
        rows = self.db.execute(
            select(day, func.count(Event.id).label("total"), *expressions)
            .where(
                Event.repository_id == repository_id,
                Event.event_created_at.is_not(None),
                func.lower(Event.author_login) == normalized,
            )
            .group_by(day).order_by(day)
        ).mappings().all()
        return [self._timeline_dict(row) for row in rows]

    @staticmethod
    def _timeline_dict(row) -> dict:
        item = dict(row)
        item["date"] = str(item["date"])
        return item

    def _timeline(self, repository_id: int, member_id: int | None) -> list[dict]:
        day = func.date(Event.event_created_at).label("date")
        filters = [Event.repository_id == repository_id, Event.event_created_at.is_not(None)]
        if member_id is not None:
            filters.append(Event.member_id == member_id)
        expressions = [func.sum(case((Event.event_type == event_type, 1), else_=0)).label(field)
                       for event_type, field in TYPE_FIELDS.items()]
        rows = self.db.execute(select(day, func.count(Event.id).label("total"), *expressions)
                               .where(*filters).group_by(day).order_by(day)).mappings().all()
        return [self._timeline_dict(row) for row in rows]

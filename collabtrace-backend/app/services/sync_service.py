from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ContributionEventRecord, Member, Repository, SyncRecord
from app.github.client import GitHubAPIError
from app.github.service import GitHubService
from app.models.contribution import ContributionEvent
from app.services.errors import NotFoundError


flow_logger = logging.getLogger("collabtrace.flow")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def db_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class SyncService:
    def __init__(self, db: Session):
        self.db = db

    async def sync(
        self, repository_id: int, github: GitHubService, flow_id: str | None = None
    ) -> dict:
        repository = self.db.get(Repository, repository_id)
        if repository is None:
            raise NotFoundError("Repository not found")

        flow_id = flow_id or secrets.token_hex(4)
        flow_logger.info(
            "[FLOW] Sync started flow_id=%s repository=%s repository_id=%s",
            flow_id, repository.full_name, repository.id,
        )

        sync_record = SyncRecord(repository_id=repository_id, status="RUNNING", started_at=utc_now())
        self.db.add(sync_record)
        self.db.commit()
        self.db.refresh(sync_record)
        sync_id = sync_record.id

        try:
            flow_logger.info(
                "[FLOW] GitHub fetch started flow_id=%s repository=%s",
                flow_id, repository.full_name,
            )
            grouped = await github.get_all_contribution_events(repository.owner, repository.name)
            flow_logger.info(
                "[FLOW] GitHub fetch complete flow_id=%s repository=%s commits=%s "
                "pull_requests=%s issues=%s reviews=%s total=%s",
                flow_id, repository.full_name, len(grouped["commits"]),
                len(grouped["pull_requests"]), len(grouped["issues"]),
                len(grouped["reviews"]), len(grouped["all"]),
            )
            events: list[ContributionEvent] = grouped["all"]
            flow_logger.info(
                "[FLOW] Normalization complete flow_id=%s repository=%s total=%s",
                flow_id, repository.full_name, len(events),
            )
            result = self._persist(repository, sync_record, events)
            self.db.commit()
            flow_logger.info(
                "[FLOW] Persistence complete flow_id=%s repository=%s fetched=%s inserted=%s "
                "updated=%s unchanged=%s mapped=%s unmapped=%s",
                flow_id, repository.full_name, result["fetched"], result["inserted"],
                result["updated"], result["unchanged"], result["mapped"], result["unmapped"],
            )
            flow_logger.info(
                "[FLOW] Sync complete flow_id=%s repository=%s status=%s",
                flow_id, repository.full_name, result["status"],
            )
            return result
        except (Exception, asyncio.CancelledError) as exc:
            self.db.rollback()
            failed = self.db.get(SyncRecord, sync_id)
            if failed is not None:
                failed.status = "FAILED"
                failed.finished_at = utc_now()
                failed.error_message = (
                    exc.message if isinstance(exc, GitHubAPIError) else "Synchronization failed"
                )
                self.db.commit()
            flow_logger.warning(
                "[FLOW] Sync failed flow_id=%s repository=%s reason=%s",
                flow_id, repository.full_name, type(exc).__name__,
            )
            raise

    def _persist(
        self, repository: Repository, sync_record: SyncRecord, events: list[ContributionEvent]
    ) -> dict:
        members = {
            member.github_username: member.id
            for member in self.db.scalars(select(Member).where(Member.repository_id == repository.id))
        }
        existing = {
            record.event_id: record
            for record in self.db.scalars(
                select(ContributionEventRecord).where(
                    ContributionEventRecord.repository_id == repository.id
                )
            )
        }
        inserted = updated = unchanged = mapped = unmapped = 0
        for event in events:
            member_id = members.get(event.author_login.lower()) if event.author_login else None
            mapped += member_id is not None
            unmapped += member_id is None
            values = self._event_values(event, member_id)
            record = existing.get(event.event_id)
            if record is None:
                self.db.add(ContributionEventRecord(repository_id=repository.id, **values))
                inserted += 1
            elif self._apply_changes(record, values):
                updated += 1
            else:
                unchanged += 1

        finished_at = utc_now()
        repository.last_sync_at = finished_at
        sync_record.status = "SUCCESS"
        sync_record.finished_at = finished_at
        sync_record.fetched_count = len(events)
        sync_record.inserted_count = inserted
        sync_record.updated_count = updated
        sync_record.unchanged_count = unchanged
        sync_record.mapped_count = mapped
        sync_record.unmapped_count = unmapped
        self.db.flush()
        return {
            "repository_id": repository.id,
            "repository": repository.full_name,
            "status": "SUCCESS",
            "fetched": len(events), "inserted": inserted, "updated": updated,
            "unchanged": unchanged, "mapped": mapped, "unmapped": unmapped,
            "started_at": sync_record.started_at, "finished_at": finished_at,
        }

    @staticmethod
    def _event_values(event: ContributionEvent, member_id: int | None) -> dict:
        return {
            "member_id": member_id,
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "author_login": event.author_login,
            "title": event.title,
            "source_id": event.source_id,
            "github_url": event.github_url,
            "event_created_at": db_datetime(event.created_at),
            "metadata_json": event.metadata,
        }

    @staticmethod
    def _apply_changes(record: ContributionEventRecord, values: dict) -> bool:
        changed = False
        for field, value in values.items():
            current = getattr(record, field)
            if (
                isinstance(current, datetime)
                and isinstance(value, datetime)
                and db_datetime(current) == db_datetime(value)
            ):
                continue
            if current != value:
                setattr(record, field, value)
                changed = True
        return changed

    def history(self, repository_id: int, limit: int) -> list[SyncRecord]:
        if self.db.get(Repository, repository_id) is None:
            raise NotFoundError("Repository not found")
        return list(
            self.db.scalars(
                select(SyncRecord).where(SyncRecord.repository_id == repository_id)
                .order_by(SyncRecord.started_at.desc()).limit(limit)
            )
        )

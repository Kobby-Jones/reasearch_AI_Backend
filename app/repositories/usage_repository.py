from __future__ import annotations

from sqlalchemy import select

from app.models.usage import UsageRecord
from app.repositories.base import BaseRepository


class UsageRepository(BaseRepository[UsageRecord]):
    model = UsageRecord

    def get_or_create(self, user_id: int, metric: str, period: str) -> UsageRecord:
        rec = self.db.scalar(
            select(UsageRecord).where(
                UsageRecord.user_id == user_id,
                UsageRecord.metric == metric,
                UsageRecord.period == period,
            )
        )
        if rec is None:
            rec = UsageRecord(user_id=user_id, metric=metric, period=period, count=0)
            self.db.add(rec)
            self.db.flush()
        return rec

    def totals_for_user(self, user_id: int, period: str) -> dict[str, int]:
        rows = self.db.scalars(
            select(UsageRecord).where(
                UsageRecord.user_id == user_id, UsageRecord.period == period
            )
        ).all()
        return {r.metric: r.count for r in rows}

from __future__ import annotations

from sqlalchemy import select

from app.models.subscription import Subscription
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    def active_for_user(self, user_id: int) -> Subscription | None:
        return self.db.scalar(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status == "active")
            .order_by(Subscription.id.desc())
        )

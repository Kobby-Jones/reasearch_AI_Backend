from __future__ import annotations

from sqlalchemy import select

from app.models.payment import Payment
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    def get_by_reference(self, reference: str) -> Payment | None:
        return self.db.scalar(select(Payment).where(Payment.reference == reference))

    def list_for_user(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> list[Payment]:
        return list(
            self.db.scalars(
                select(Payment)
                .where(Payment.user_id == user_id)
                .order_by(Payment.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )

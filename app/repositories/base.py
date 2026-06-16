from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, obj_id: int) -> ModelT | None:
        return self.db.get(self.model, obj_id)

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def commit(self) -> None:
        self.db.commit()

    def list_all(self) -> list[ModelT]:
        return list(self.db.scalars(select(self.model)).all())

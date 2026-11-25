from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.order import Order


class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, order_id: int):
        return self.db.scalar(select(Order).options(selectinload(Order.lines)).where(Order.id == order_id))

    def list_for_user(self, user_id: int):
        query = select(Order).options(selectinload(Order.lines)).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        return list(self.db.scalars(query))

    def by_idempotency_key(self, user_id: int, key: str):
        return self.db.scalar(select(Order).options(selectinload(Order.lines)).where(Order.user_id == user_id, Order.idempotency_key == key))

from collections import Counter
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.menu_item import MenuItem
from models.order import Order
from models.order_line import OrderLine
from repositories.order_repository import OrderRepository
from schemas.order_schema import OrderCreate


class OrderService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = OrderRepository(db)

    def create(self, user_id: int, data: OrderCreate, idempotency_key: str):
        quantities = Counter()
        for line in data.lines:
            quantities[line.item_id] += line.quantity
        previous = self.repository.by_idempotency_key(user_id, idempotency_key)
        if previous:
            return self._replay(previous, quantities)
        try:
            items = {}
            for item_id, quantity in quantities.items():
                changed = self.db.execute(
                    update(MenuItem)
                    .where(MenuItem.id == item_id, MenuItem.is_active.is_(True), MenuItem.portions >= quantity)
                    .values(portions=MenuItem.portions - quantity)
                )
                if changed.rowcount != 1:
                    raise HTTPException(status_code=409, detail="Item unavailable or insufficient portions")
                items[item_id] = self.db.get(MenuItem, item_id)
            total = sum((items[line.item_id].price * line.quantity for line in data.lines), Decimal("0.00"))
            order = Order(user_id=user_id, status="CONFIRMED", total=total, idempotency_key=idempotency_key)
            self.db.add(order)
            self.db.flush()
            for line in data.lines:
                self.db.add(OrderLine(order_id=order.id, item_id=line.item_id, quantity=line.quantity, unit_price=items[line.item_id].price))
            self.db.commit()
            return self.repository.get(order.id)
        except IntegrityError:
            self.db.rollback()
            previous = self.repository.by_idempotency_key(user_id, idempotency_key)
            if previous:
                return self._replay(previous, quantities)
            raise
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _replay(previous: Order, quantities: Counter):
        existing = Counter()
        for line in previous.lines:
            existing[line.item_id] += line.quantity
        if existing != quantities:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different order")
        return previous

    def get(self, order_id: int, user_id: int, is_admin=False):
        order = self.repository.get(order_id)
        if order is None or (not is_admin and order.user_id != user_id):
            raise HTTPException(status_code=404, detail="Order not found")
        return order

    def list_for_user(self, user_id: int, is_admin=False):
        if is_admin:
            return list(self.db.query(Order).order_by(Order.created_at.desc()).all())
        return self.repository.list_for_user(user_id)

    def cancel(self, order_id: int, user_id: int, is_admin=False):
        order = self.get(order_id, user_id, is_admin)
        if order.status != "CONFIRMED":
            raise HTTPException(status_code=409, detail="Only orders not yet in preparation can be cancelled")
        try:
            claimed = self.db.execute(
                update(Order)
                .where(Order.id == order.id, Order.status == "CONFIRMED")
                .values(status="CANCELLED")
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                self.db.rollback()
                raise HTTPException(status_code=409, detail="Order can no longer be cancelled")
            for line in order.lines:
                self.db.execute(update(MenuItem).where(MenuItem.id == line.item_id).values(portions=MenuItem.portions + line.quantity))
            self.db.commit()
            self.db.expire(order)
            return self.repository.get(order.id)
        except Exception:
            self.db.rollback()
            raise

    def set_status(self, order_id: int, status: str):
        order = self.repository.get(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        allowed = {"CONFIRMED": {"PREPARING"}, "PREPARING": {"READY"}, "READY": {"COMPLETED"}}
        if status not in allowed.get(order.status, set()):
            raise HTTPException(status_code=409, detail="Invalid order status transition")
        order.status = status
        self.db.commit()
        return self.repository.get(order.id)

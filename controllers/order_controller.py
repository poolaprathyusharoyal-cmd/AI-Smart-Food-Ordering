from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.user import User
from schemas.order_schema import OrderCreate, OrderResponse
from security.basic_auth import current_user
from services.order_service import OrderService

router = APIRouter(prefix="/api", tags=["orders"])


def serialize_order(order):
    return OrderResponse(
        id=order.id,
        status=order.status,
        total=order.total,
        created_at=order.created_at,
        lines=[{"item_id": line.item_id, "quantity": line.quantity, "unit_price": line.unit_price, "item_name": line.menu_item.name} for line in order.lines],
    )


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(data: OrderCreate, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return serialize_order(OrderService(db).create(user.id, data, idempotency_key))


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [serialize_order(order) for order in OrderService(db).list_for_user(user.id)]


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return serialize_order(OrderService(db).get(order_id, user.id, user.role == "admin"))


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return serialize_order(OrderService(db).cancel(order_id, user.id, user.role == "admin"))



from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from controllers.order_controller import serialize_order
from schemas.order_schema import OrderResponse, OrderStatusUpdate
from security.basic_auth import require_admin
from services.order_service import OrderService

router = APIRouter(prefix="/api/admin", tags=["administration"])


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
def set_order_status(order_id: int, data: OrderStatusUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return serialize_order(OrderService(db).set_status(order_id, data.status))
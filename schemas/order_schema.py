from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderLineCreate(BaseModel):
    item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=10)


class OrderCreate(BaseModel):
    lines: list[OrderLineCreate] = Field(min_length=1, max_length=20)


class OrderLineResponse(BaseModel):
    item_id: int
    quantity: int
    unit_price: Decimal
    item_name: str


class OrderResponse(BaseModel):
    id: int
    status: str
    total: Decimal
    created_at: datetime
    lines: list[OrderLineResponse]


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(PREPARING|READY|COMPLETED)$")

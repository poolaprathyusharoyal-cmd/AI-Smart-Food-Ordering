from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MenuItemBase(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    category: str = Field(min_length=2, max_length=60)
    is_vegetarian: bool = True
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    portions: int = Field(ge=0, le=10000)


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(MenuItemBase):
    pass


class MenuItemResponse(MenuItemBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

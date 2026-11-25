from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from config.database import get_db
from schemas.catalog_schema import MenuItemCreate, MenuItemResponse, MenuItemUpdate
from security.basic_auth import require_admin
from services.catalog_service import CatalogService

router = APIRouter(prefix="/api/menu_items", tags=["catalog"])


@router.get("", response_model=list[MenuItemResponse])
def list_menu_items(
    category: str | None = None,
    vegetarian: bool | None = None,
    max_price: float | None = Query(default=None, gt=0),
    keyword: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
):
    return CatalogService(db).list_items(category=category, vegetarian=vegetarian, max_price=max_price, keyword=keyword)


@router.get("/{item_id}", response_model=MenuItemResponse)
def get_menu_item(item_id: int, db: Session = Depends(get_db)):
    return CatalogService(db).get_item(item_id)


@router.post("", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(data: MenuItemCreate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return CatalogService(db).create_item(data)


@router.put("/{item_id}", response_model=MenuItemResponse)
def update_menu_item(item_id: int, data: MenuItemUpdate, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    return CatalogService(db).update_item(item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(item_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    CatalogService(db).disable_item(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

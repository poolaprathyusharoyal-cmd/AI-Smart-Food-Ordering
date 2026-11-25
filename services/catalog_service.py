from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.menu_item import MenuItem
from repositories.catalog_repository import CatalogRepository
from schemas.catalog_schema import MenuItemCreate, MenuItemUpdate


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CatalogRepository(db)

    def list_items(self, **filters):
        return self.repository.list_active(**filters)

    def get_item(self, item_id: int):
        item = self.repository.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Menu item not found")
        return item

    def create_item(self, data: MenuItemCreate):
        item = MenuItem(**data.model_dump())
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(self, item_id: int, data: MenuItemUpdate):
        item = self.repository.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Menu item not found")
        for key, value in data.model_dump().items():
            setattr(item, key, value)
        self.db.commit()
        self.db.refresh(item)
        return item

    def disable_item(self, item_id: int):
        item = self.repository.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Menu item not found")
        item.is_active = False
        self.db.commit()

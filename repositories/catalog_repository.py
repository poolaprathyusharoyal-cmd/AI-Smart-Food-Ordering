from sqlalchemy import select
from sqlalchemy.orm import Session

from models.menu_item import MenuItem


class CatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_active(self, category=None, vegetarian=None, max_price=None, keyword=None):
        query = select(MenuItem).where(MenuItem.is_active.is_(True))
        if category:
            query = query.where(MenuItem.category == category)
        if vegetarian is not None:
            query = query.where(MenuItem.is_vegetarian.is_(vegetarian))
        if max_price is not None:
            query = query.where(MenuItem.price <= max_price)
        if keyword:
            query = query.where(MenuItem.name.ilike(f"%{keyword}%"))
        return list(self.db.scalars(query.order_by(MenuItem.category, MenuItem.name)))

    def get(self, item_id: int, active_only=True):
        query = select(MenuItem).where(MenuItem.id == item_id)
        if active_only:
            query = query.where(MenuItem.is_active.is_(True))
        return self.db.scalar(query)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.database import Base, get_db
from main import app
from models.menu_item import MenuItem
from models.user import User
from services.auth_service import hash_password


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False, "timeout": 15})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            User(username="customer1", password_hash=hash_password("Customer123!"), role="customer"),
            User(username="customer2", password_hash=hash_password("Customer123!"), role="customer"),
            User(username="admin", password_hash=hash_password("Admin123!"), role="admin"),
        ])
        db.add_all([
            MenuItem(name="Masala Dosa", description="Rice crepe", category="Breakfast", is_vegetarian=True, price="90.00", portions=4),
            MenuItem(name="Paneer Biryani", description="Rice and paneer", category="Main course", is_vegetarian=True, price="180.00", portions=2),
            MenuItem(name="Test Chicken", description="Fictional chicken dish", category="Main course", is_vegetarian=False, price="150.00", portions=1),
        ])
        db.commit()
    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = override_get_db
    yield factory
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


@pytest.fixture
def client(database):
    with TestClient(app) as test_client:
        yield test_client

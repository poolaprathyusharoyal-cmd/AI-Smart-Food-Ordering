from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.database import Base, SessionLocal, engine
from controllers.catalog_controller import router as catalog_router
from controllers.order_controller import router as order_router
from exceptions.handlers import install_exception_handlers
from models import ChatMessage, ChatSession, Document, MenuItem, Order, OrderLine, PendingAction, ToolRun, User
from controllers.auth_controller import router as auth_router
from controllers.chat_controller import router as chat_router
from controllers.document_controller import router as document_router
from controllers.admin_controller import router as admin_router
from services.auth_service import hash_password


_FOOD = [
    ("Masala Dosa", "Crisp rice crepe with spiced potato", "Breakfast", True, "90.00", 20),
    ("Paneer Biryani", "Fragrant basmati rice with paneer", "Main course", True, "180.00", 10),
    ("Idli Sambar", "Steamed rice cakes with lentil stew", "Breakfast", True, "70.00", 24),
    ("Chole Bhature", "Chickpea curry with fried bread", "Main course", True, "150.00", 12),
    ("Veg Hakka Noodles", "Wok-tossed vegetables and noodles", "Main course", True, "160.00", 14),
    ("Chicken Tikka Roll", "Grilled chicken wrapped with salad", "Snacks", False, "170.00", 9),
    ("Mango Lassi", "Chilled yogurt and mango drink", "Drinks", True, "80.00", 18),
    ("Gulab Jamun", "Warm milk dumplings in rose syrup", "Dessert", True, "60.00", 30),
    ("Palak Paneer", "Paneer in a spinach gravy", "Main course", True, "190.00", 8),
    ("Filter Coffee", "South Indian style filter coffee", "Drinks", True, "45.00", 25),
]


def seed_data():
    db = SessionLocal()
    try:
        for username, password, role in [("customer1", "Customer123!", "customer"), ("customer2", "Customer123!", "customer"), ("admin", "Admin123!", "admin")]:
            if db.query(User).filter_by(username=username).first() is None:
                db.add(User(username=username, password_hash=hash_password(password), role=role))
        db.flush()
        for name, description, category, vegetarian, price, portions in _FOOD:
            if db.query(MenuItem).filter_by(name=name).first() is None:
                db.add(MenuItem(name=name, description=description, category=category, is_vegetarian=vegetarian, price=price, portions=portions))
        db.flush()
        sample_orders = [
            ("customer1", "sample-order-1", [("Masala Dosa", 1)]),
            ("customer1", "sample-order-2", [("Paneer Biryani", 1)]),
            ("customer2", "sample-order-3", [("Idli Sambar", 2)]),
        ]
        for username, key, order_items in sample_orders:
            if db.query(Order).filter_by(idempotency_key=key).first():
                continue
            owner = db.query(User).filter_by(username=username).one()
            order = Order(user_id=owner.id, status="CONFIRMED", total=0, idempotency_key=key)
            db.add(order)
            db.flush()
            total = 0
            for item_name, quantity in order_items:
                item = db.query(MenuItem).filter_by(name=item_name).one()
                order.lines.append(OrderLine(item_id=item.id, quantity=quantity, unit_price=item.price))
                item.portions -= quantity
                total += item.price * quantity
            order.total = total
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_data()
    yield


app = FastAPI(title="AI Smart Food Ordering & Restaurant Assistant", version="1.0.0", lifespan=lifespan, description="Food ordering API with persistent chat, retrieval and confirmation-gated actions.")
install_exception_handlers(app)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:100]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(catalog_router)
app.include_router(order_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(document_router)
app.include_router(admin_router)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse("frontend/index.html")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

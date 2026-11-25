import httpx
import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.orm import Session

from config.settings import settings
from models.pending_action import PendingAction
from rag.retriever import retrieve
from schemas.order_schema import OrderCreate


ALLOWED_TOOLS = {"search_menu_items", "get_menu_item", "check_availability", "create_order", "get_order_status", "cancel_order", "retrieve_policy"}


def _get(path: str, auth: tuple[str, str], params=None):
    with httpx.Client(base_url=settings.internal_api_base_url, auth=auth, timeout=5.0) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()


def _positive_id(value) -> int:
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise ValueError("An item or order ID must be a positive integer")
    return int(value)


def _quantity(value) -> int:
    if isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= 10:
        raise ValueError("Quantity must be an integer between 1 and 10")
    return int(value)


def execute_tool(name: str, arguments: dict, auth: tuple[str, str], db: Session, user_id: int, session_id: int):
    if name not in ALLOWED_TOOLS:
        raise ValueError("Tool is not allowlisted")
    if name == "search_menu_items":
        if arguments.get("max_price") is not None and (not math.isfinite(float(arguments["max_price"])) or float(arguments["max_price"]) <= 0):
            raise ValueError("Maximum price must be a positive number")
        for field in ("category", "keyword"):
            if arguments.get(field) is not None and len(str(arguments[field])) > 120:
                raise ValueError(f"{field} is too long")
        params = {key: value for key, value in arguments.items() if key in {"category", "vegetarian", "max_price", "keyword"} and value is not None}
        return _get("/api/menu_items", auth, params)
    if name == "get_menu_item":
        return _get(f"/api/menu_items/{_positive_id(arguments['item_id'])}", auth)
    if name == "check_availability":
        item_id = _positive_id(arguments["item_id"])
        quantity = _quantity(arguments["quantity"])
        item = _get(f"/api/menu_items/{item_id}", auth)
        return {"item_id": item["id"], "available": quantity <= item["portions"], "requested": quantity, "portions": item["portions"]}
    if name == "get_order_status":
        return _get(f"/api/orders/{_positive_id(arguments['order_id'])}", auth)
    if name == "retrieve_policy":
        question = str(arguments["question"]).strip()
        if not question or len(question) > 4000:
            raise ValueError("Policy question must contain 1-4000 characters")
        results = retrieve(question, 4)
        return {"sources": results, "verified": bool(results)}
    if name == "create_order":
        request = OrderCreate.model_validate(arguments)
        lines = []
        total = 0.0
        for line in request.lines:
            item = _get(f"/api/menu_items/{line.item_id}", auth)
            if item["portions"] < line.quantity:
                raise HTTPException(status_code=409, detail=f"Only {item['portions']} portions of {item['name']} are currently available")
            lines.append({"item_id": item["id"], "item_name": item["name"], "quantity": line.quantity, "unit_price": item["price"]})
            total += float(item["price"]) * line.quantity
        summary = "Place " + ", ".join(f"{line['quantity']} × {line['item_name']} at ₹{line['unit_price']}" for line in lines) + f" (total ₹{total:.2f})?"
        action = PendingAction(session_id=session_id, user_id=user_id, action="CREATE_ORDER", payload={"lines": [line.model_dump() for line in request.lines], "display_lines": lines, "total": f"{total:.2f}", "summary": summary}, status="PENDING", idempotency_key=f"chat-order-{user_id}-{session_id}-{uuid4().hex}", expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10))
        db.add(action)
        db.flush()
        return {"pending_action_id": action.id, "requires_confirmation": True, "summary": summary}
    if name == "cancel_order":
        order = _get(f"/api/orders/{_positive_id(arguments['order_id'])}", auth)
        if order["status"] != "CONFIRMED":
            raise HTTPException(status_code=409, detail="That order is already being prepared and cannot be cancelled")
        summary = f"Cancel order #{order['id']} (₹{order['total']}, currently {order['status']})?"
        action = PendingAction(session_id=session_id, user_id=user_id, action="CANCEL_ORDER", payload={"order_id": order["id"], "total": str(order["total"]), "status": order["status"], "summary": summary}, status="PENDING", idempotency_key=f"chat-cancel-{user_id}-{session_id}-{uuid4().hex}", expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10))
        db.add(action)
        db.flush()
        return {"pending_action_id": action.id, "requires_confirmation": True, "summary": summary}
    raise ValueError("Unsupported tool")

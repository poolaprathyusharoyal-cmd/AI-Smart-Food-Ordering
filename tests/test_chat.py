from models.chat_session import ChatSession
from models.menu_item import MenuItem
from models.order import Order
from models.pending_action import PendingAction
from models.user import User


def test_chat_history_persists_and_is_owner_scoped(client):
    auth = ("customer1", "Customer123!")
    session = client.post("/api/chat/sessions", auth=auth, json={"title": "Dinner help"}).json()
    answer = client.post(f"/api/chat/sessions/{session['id']}/messages", auth=auth, json={"content": "What allergens are listed for Masala Dosa?"})
    assert answer.status_code == 200
    assert answer.json()["mode"] == "RAG"
    history = client.get(f"/api/chat/sessions/{session['id']}/messages", auth=auth).json()
    assert [message["role"] for message in history["messages"]] == ["user", "assistant"]
    assert history["messages"][1]["metadata_json"]["citations"]
    assert client.get(f"/api/chat/sessions/{session['id']}/messages", auth=("customer2", "Customer123!")).status_code == 404


def test_rejected_pending_action_is_persisted_without_order(client, database):
    with database() as db:
        user = db.query(User).filter_by(username="customer1").one()
        session = ChatSession(user_id=user.id, title="Confirmation")
        db.add(session)
        db.flush()
        action = PendingAction(session_id=session.id, user_id=user.id, action="CREATE_ORDER", payload={"lines": [{"item_id": 1, "quantity": 1}], "summary": "Place one dish?"}, status="PENDING", idempotency_key="pending-reject-test")
        db.add(action)
        db.commit()
        session_id, action_id = session.id, action.id
    result = client.post(f"/api/chat/actions/{action_id}/confirm", auth=("customer1", "Customer123!"), json={"confirm": False})
    assert result.status_code == 200
    assert result.json()["metadata_json"]["result"]["status"] == "REJECTED"
    history = client.get(f"/api/chat/sessions/{session_id}/messages", auth=("customer1", "Customer123!")).json()
    assert history["messages"][-1]["content"] == "No change was made."
    assert client.get("/api/orders", auth=("customer1", "Customer123!")).json() == []


def test_confirmed_action_creates_once_and_replays_result(client, database):
    with database() as db:
        user = db.query(User).filter_by(username="customer1").one()
        item = db.query(MenuItem).filter_by(name="Masala Dosa").one()
        session = ChatSession(user_id=user.id, title="Order confirmation")
        db.add(session)
        db.flush()
        action = PendingAction(session_id=session.id, user_id=user.id, action="CREATE_ORDER", payload={"lines": [{"item_id": item.id, "quantity": 1}], "display_lines": [{"item_id": item.id, "item_name": item.name, "quantity": 1, "unit_price": "90.00"}], "summary": "Place one Masala Dosa?"}, status="PENDING", idempotency_key="pending-confirm-test")
        db.add(action)
        db.commit()
        action_id = action.id
    url = f"/api/chat/actions/{action_id}/confirm"
    auth = ("customer1", "Customer123!")
    first = client.post(url, auth=auth, json={"confirm": True})
    second = client.post(url, auth=auth, json={"confirm": True})
    assert first.status_code == second.status_code == 200
    assert first.json()["metadata_json"]["result"]["order_id"] == second.json()["metadata_json"]["result"]["order_id"]
    with database() as db:
        assert db.query(Order).count() == 1


def test_confirmation_rejects_a_changed_price(client, database):
    with database() as db:
        user = db.query(User).filter_by(username="customer1").one()
        item = db.query(MenuItem).filter_by(name="Masala Dosa").one()
        session = ChatSession(user_id=user.id, title="Stale quote")
        db.add(session)
        db.flush()
        action = PendingAction(session_id=session.id, user_id=user.id, action="CREATE_ORDER", payload={"lines": [{"item_id": item.id, "quantity": 1}], "display_lines": [{"item_id": item.id, "item_name": item.name, "quantity": 1, "unit_price": "90.00"}], "summary": "Place one Masala Dosa?"}, status="PENDING", idempotency_key="pending-stale-test")
        db.add(action)
        item.price = "91.00"
        db.commit()
        action_id = action.id
    result = client.post(f"/api/chat/actions/{action_id}/confirm", auth=("customer1", "Customer123!"), json={"confirm": True})
    assert result.status_code == 200
    assert result.json()["metadata_json"]["result"]["status"] == "EXPIRED"
    with database() as db:
        assert db.query(Order).count() == 0


def test_openai_failure_is_saved_as_safe_chat_response(client, monkeypatch):
    import agents.single_agent as agent_module
    monkeypatch.setattr(agent_module.settings, "openai_api_key", "test-key")
    def fail_client(**kwargs):
        raise RuntimeError("upstream failure")
    monkeypatch.setattr("openai.OpenAI", fail_client)
    auth = ("customer1", "Customer123!")
    session = client.post("/api/chat/sessions", auth=auth, json={"title": "Failure handling"}).json()
    response = client.post(f"/api/chat/sessions/{session['id']}/messages", auth=auth, json={"content": "Tell me something about dinner"})
    assert response.status_code == 200
    assert "temporarily unavailable" in response.json()["content"]
    history = client.get(f"/api/chat/sessions/{session['id']}/messages", auth=auth).json()["messages"]
    assert len(history) == 2

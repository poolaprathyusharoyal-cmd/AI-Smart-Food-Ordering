import json
from types import SimpleNamespace

from agents.single_agent import SingleAgent
from agents.tools import execute_tool
from models.pending_action import PendingAction
from models.user import User


def test_create_order_tool_only_creates_pending_confirmation(database, monkeypatch):
    from agents import tools
    monkeypatch.setattr(tools, "_get", lambda path, auth, params=None: {"id": 1, "name": "Masala Dosa", "price": "90.00", "portions": 4})
    with database() as db:
        user = db.query(User).filter_by(username="customer1").one()
        result = execute_tool("create_order", {"lines": [{"item_id": 1, "quantity": 1}]}, ("customer1", "Customer123!"), db, user.id, 77)
        assert result["requires_confirmation"] is True
        action = db.query(PendingAction).filter_by(id=result["pending_action_id"]).one()
        assert action.status == "PENDING"
        assert "₹90.00" in action.payload["summary"]
        assert db.query(__import__("models.order", fromlist=["Order"]).Order).count() == 0


def test_agent_tool_arguments_are_validated_before_http_calls(monkeypatch):
    from agents import tools
    monkeypatch.setattr(tools, "_get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("HTTP should not be called")))
    with __import__("sqlalchemy").orm.Session(bind=__import__("sqlalchemy").create_engine("sqlite://")) as db:
        try:
            execute_tool("check_availability", {"item_id": 1, "quantity": 11}, ("customer1", "Customer123!"), db, 1, 1)
        except ValueError as error:
            assert "between 1 and 10" in str(error)
        else:
            raise AssertionError("Invalid quantity was accepted")


def test_openai_tool_call_is_allowlisted_and_returns_actual_tool_result(monkeypatch):
    import agents.single_agent as agent_module
    monkeypatch.setattr(agent_module.settings, "openai_api_key", "test-key")
    calls = {"count": 0}
    class FakeMessage:
        def __init__(self, tool_calls=None, content=None):
            self.tool_calls, self.content = tool_calls, content
        def model_dump(self, exclude_none=True):
            return {"role": "assistant", "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "retrieve_policy", "arguments": json.dumps({"question": "Masala Dosa ingredients"})}}]}
    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def create(self, **kwargs):
            calls["count"] += 1
            message = FakeMessage([SimpleNamespace(id="call-1", function=SimpleNamespace(name="retrieve_policy", arguments='{"question":"Masala Dosa ingredients"}'))]) if calls["count"] == 1 else FakeMessage(content="The document lists ingredients.")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
    monkeypatch.setattr("openai.OpenAI", FakeClient)
    with __import__("sqlalchemy").orm.Session(bind=__import__("sqlalchemy").create_engine("sqlite://")) as db:
        result = SingleAgent().run("What is in Masala Dosa?", [], ("customer1", "Customer123!"), db, 1, 1)
    assert result["content"] == "The document lists ingredients."
    assert result["mode"] == "RAG"
    assert result["citations"]
    assert result["tool_runs"][0]["tool_name"] == "retrieve_policy"

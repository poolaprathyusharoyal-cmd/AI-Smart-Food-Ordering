from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from agents.single_agent import SingleAgent
from models.chat_message import ChatMessage
from models.chat_session import ChatSession
from models.menu_item import MenuItem
from models.pending_action import PendingAction
from models.tool_run import ToolRun
from models.user import User
from services.order_service import OrderService


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: int, title: str):
        session = ChatSession(user_id=user_id, title=title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, user_id: int):
        return list(self.db.query(ChatSession).filter_by(user_id=user_id).order_by(ChatSession.updated_at.desc()).all())

    def _owned_session(self, session_id: int, user_id: int):
        session = self.db.query(ChatSession).filter_by(id=session_id, user_id=user_id).first()
        if session is None:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session

    def messages(self, session_id: int, user_id: int):
        session = self._owned_session(session_id, user_id)
        return list(self.db.query(ChatMessage).filter_by(session_id=session.id).order_by(ChatMessage.seq_no).all())

    def respond(self, session_id: int, user: User, content: str, auth: tuple[str, str]):
        session = self._owned_session(session_id, user.id)
        previous = list(self.db.query(ChatMessage).filter_by(session_id=session.id).order_by(ChatMessage.seq_no.desc()).limit(8).all())
        next_seq = (self.db.query(func.max(ChatMessage.seq_no)).filter_by(session_id=session.id).scalar() or 0) + 1
        user_message = ChatMessage(session_id=session.id, seq_no=next_seq, role="user", content=content, mode="GENERAL", metadata_json={})
        self.db.add(user_message)
        self.db.commit()
        history = [{"role": message.role, "content": message.content} for message in reversed(previous)]
        try:
            result = SingleAgent().run(content, history, auth, self.db, user.id, session.id)
        except Exception:
            result = {"content": "The AI assistant is temporarily unavailable. Your message has been saved; please try again shortly.", "mode": "GENERAL", "citations": [], "pending_action": None, "tool_runs": []}
        seq = next_seq + 1
        pending = result.get("pending_action")
        metadata = {"citations": result.get("citations", [])}
        if pending:
            metadata["pending_action"] = pending
        answer = ChatMessage(session_id=session.id, seq_no=seq, role="assistant", content=result["content"], mode=result.get("mode", "GENERAL"), metadata_json=metadata)
        self.db.add(answer)
        self.db.flush()
        for record in result.get("tool_runs", []):
            self.db.add(ToolRun(message_id=answer.id, tool_name=record["tool_name"], arguments=record.get("arguments", {}), result=record.get("result", {}), status=record.get("status", "SUCCESS")))
        session.title = content[:60] if session.title == "New conversation" else session.title
        self.db.commit()
        self.db.refresh(answer)
        return answer

    def confirm_action(self, action_id: int, user: User, confirm: bool):
        action = self.db.query(PendingAction).filter_by(id=action_id, user_id=user.id).with_for_update().first()
        if action is None:
            raise HTTPException(status_code=404, detail="Pending action not found")
        if action.status in {"CONFIRMED", "REJECTED"}:
            return action.payload.get("result", {"status": action.status, "message": "This action has already been processed."})
        if action.status != "PENDING":
            raise HTTPException(status_code=409, detail="This action is already being processed")
        if action.expires_at and action.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            result = {"status": "EXPIRED", "message": "This confirmation expired. Please request a fresh proposal."}
            action.status = "EXPIRED"
            action.payload = {**action.payload, "result": result}
            self._save_action_message(action, result)
            self.db.commit()
            return result
        if not confirm:
            action.status = "REJECTED"
            action.payload = {**action.payload, "result": {"status": "REJECTED", "message": "No change was made."}}
            self._save_action_message(action, action.payload["result"])
            self.db.commit()
            return action.payload["result"]
        action.status = "PROCESSING"
        self.db.commit()
        try:
            if action.action == "CREATE_ORDER":
                from schemas.order_schema import OrderCreate
                snapshots = {line["item_id"]: line for line in action.payload["display_lines"]}
                for line in action.payload["lines"]:
                    item = self.db.query(MenuItem).filter_by(id=line["item_id"], is_active=True).with_for_update().first()
                    snapshot = snapshots.get(line["item_id"])
                    if item is None or item.portions < line["quantity"] or snapshot is None or Decimal(str(item.price)) != Decimal(str(snapshot["unit_price"])):
                        result = {"status": "EXPIRED", "message": "The price or availability changed. Nothing was ordered; please request a fresh proposal."}
                        action.status = "EXPIRED"
                        action.payload = {**action.payload, "result": result}
                        self._save_action_message(action, result)
                        self.db.commit()
                        return result
                order = OrderService(self.db).create(user.id, OrderCreate.model_validate({"lines": action.payload["lines"]}), action.idempotency_key)
                result = {"status": order.status, "order_id": order.id, "total": str(order.total), "message": f"Order #{order.id} is confirmed."}
            elif action.action == "CANCEL_ORDER":
                order = OrderService(self.db).cancel(action.payload["order_id"], user.id)
                result = {"status": order.status, "order_id": order.id, "message": f"Order #{order.id} has been cancelled."}
            else:
                raise HTTPException(status_code=400, detail="Unsupported action")
            action.status = "CONFIRMED"
            action.payload = {**action.payload, "result": result}
            self._save_action_message(action, result)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            action = self.db.query(PendingAction).filter_by(id=action_id, user_id=user.id).first()
            if action and action.status == "PROCESSING":
                action.status = "PENDING"
                self.db.commit()
            raise

    def _save_action_message(self, action: PendingAction, result: dict):
        next_seq = (self.db.query(func.max(ChatMessage.seq_no)).filter_by(session_id=action.session_id).scalar() or 0) + 1
        self.db.add(ChatMessage(session_id=action.session_id, seq_no=next_seq, role="assistant", content=result["message"], mode="AGENT", metadata_json={"action_result": result}))

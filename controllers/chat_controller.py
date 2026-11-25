from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from config.database import get_db
from models.user import User
from models.pending_action import PendingAction
from schemas.chat_schema import ChatMessageCreate, ChatSessionCreate, ConfirmAction
from security.basic_auth import current_user
from services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])
_basic = HTTPBasic()


def _message_payload(message):
    return {"id": message.id, "seq_no": message.seq_no, "role": message.role, "content": message.content, "mode": message.mode, "metadata_json": message.metadata_json}


@router.post("/sessions", status_code=201)
def create_session(data: ChatSessionCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = ChatService(db).create_session(user.id, data.title)
    return {"id": session.id, "title": session.title, "created_at": session.created_at}


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{"id": session.id, "title": session.title, "created_at": session.created_at, "updated_at": session.updated_at} for session in ChatService(db).list_sessions(user.id)]


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    service = ChatService(db)
    messages = service.messages(session_id, user.id)
    pending = db.query(PendingAction).filter_by(session_id=session_id, user_id=user.id, status="PENDING").order_by(PendingAction.id.desc()).first()
    return {"messages": [_message_payload(message) for message in messages], "pending_action": ({"id": pending.id, "summary": pending.payload.get("summary", "Please confirm this action.")} if pending else None)}


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: int, data: ChatMessageCreate, credentials: HTTPBasicCredentials = Depends(_basic), db: Session = Depends(get_db), user: User = Depends(current_user)):
    message = ChatService(db).respond(session_id, user, data.content, (credentials.username, credentials.password))
    pending = message.metadata_json.get("pending_action")
    return {**_message_payload(message), "pending_action": pending}


@router.post("/actions/{action_id}/confirm")
def confirm_action(action_id: int, data: ConfirmAction, db: Session = Depends(get_db), user: User = Depends(current_user)):
    result = ChatService(db).confirm_action(action_id, user, data.confirm)
    return {"id": action_id, "seq_no": 0, "role": "assistant", "content": result.get("message", "Action processed."), "mode": "AGENT", "metadata_json": {"result": result}}

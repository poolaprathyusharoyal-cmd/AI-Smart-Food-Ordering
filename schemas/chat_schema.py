from typing import Any

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=160)


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatMessageResponse(BaseModel):
    id: int
    seq_no: int
    role: str
    content: str
    mode: str
    metadata_json: dict[str, Any]


class ConfirmAction(BaseModel):
    confirm: bool

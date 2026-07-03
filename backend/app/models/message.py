from typing import Dict, List, Optional
from pydantic import Field, model_validator
from enum import Enum

from app.models.base import BaseDocument, PyObjectId


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"


class Message(BaseDocument):
    room_id: PyObjectId = Field(...)
    sender_id: PyObjectId = Field(...)
    content: Optional[str] = Field(None, max_length=5000)
    message_type: MessageType = Field(default=MessageType.TEXT)
    file_url: Optional[str] = None
    reactions: Dict[str, List[PyObjectId]] = Field(default_factory=dict)
    read_by: List[PyObjectId] = Field(default_factory=list)
    is_deleted: bool = Field(default=False)

    @model_validator(mode="after")
    def set_default_read_by(self) -> "Message":
        # If read_by is empty, populate it with sender_id
        if not self.read_by and self.sender_id:
            self.read_by = [self.sender_id]
        return self

    class Config:
        collection_name = "messages"

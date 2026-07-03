from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime

from app.models.base import PyObjectId
from app.models.message import MessageType


class MessageCreate(BaseModel):
    room_id: PyObjectId
    content: Optional[str] = Field(None, max_length=5000)
    message_type: MessageType = Field(default=MessageType.TEXT)
    file_url: Optional[str] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class MessageUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class ReactionRequest(BaseModel):
    emoji: str = Field(..., min_length=1, max_length=10)

class MessageResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    room_id: PyObjectId
    sender_id: PyObjectId
    content: Optional[str] = None
    message_type: MessageType
    file_url: Optional[str] = None
    reactions: Dict[str, List[PyObjectId]] = Field(default_factory=dict)
    read_by: List[PyObjectId]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def mask_deleted_content(self) -> "MessageResponse":
        if self.is_deleted:
            self.content = "[message deleted]"
            self.file_url = None
            self.reactions = {}
        return self

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

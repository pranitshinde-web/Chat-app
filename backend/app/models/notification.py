from typing import Optional
from pydantic import Field
from enum import Enum

from app.models.base import BaseDocument, PyObjectId


class NotificationType(str, Enum):
    NEW_MESSAGE = "new_message"
    MENTION = "mention"
    ROOM_INVITE = "room_invite"


class Notification(BaseDocument):
    user_id: PyObjectId = Field(..., description="Recipient user ID")
    type: NotificationType = Field(...)
    room_id: Optional[PyObjectId] = Field(None)
    message_id: Optional[PyObjectId] = Field(None)
    is_read: bool = Field(default=False)

    class Config:
        collection_name = "notifications"

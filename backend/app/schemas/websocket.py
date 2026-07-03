from enum import Enum
from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class WSEventType(str, Enum):
    MESSAGE_SEND = "message.send"
    MESSAGE_NEW = "message.new"
    MESSAGE_SENT = "message.sent"
    MESSAGE_UPDATED = "message.updated"
    MESSAGE_DELETED = "message.deleted"
    MESSAGE_REACTION = "message.reaction"
    TYPING_START = "typing.start"
    TYPING_STOP = "typing.stop"
    PRESENCE_JOIN = "presence.join"
    PRESENCE_LEAVE = "presence.leave"
    MESSAGE_READ = "message.read"
    MESSAGE_READ_RECEIPT = "message.read_receipt"
    ROOM_READ_ALL = "room.read_all"
    NOTIFICATIONS_PENDING = "notifications.pending"
    ERROR = "error"


class WSEvent(BaseModel):
    event: WSEventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    room_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        use_enum_values=True
    )

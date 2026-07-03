from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from app.models.base import PyObjectId
from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    user_id: PyObjectId
    type: NotificationType
    room_id: Optional[PyObjectId] = None
    message_id: Optional[PyObjectId] = None
    is_read: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    unread_count: int

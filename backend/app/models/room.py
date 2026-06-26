from typing import List, Optional
from pydantic import Field
from enum import Enum

from app.models.base import BaseDocument, PyObjectId


class RoomType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    DIRECT = "direct"


class Room(BaseDocument):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    type: RoomType = Field(default=RoomType.PUBLIC)
    created_by: PyObjectId = Field(...)
    members: List[PyObjectId] = Field(default_factory=list)

    class Config:
        collection_name = "rooms"

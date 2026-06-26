from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from app.models.base import PyObjectId
from app.models.room import RoomType


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    type: RoomType = Field(default=RoomType.PUBLIC)
    members: List[PyObjectId] = Field(default_factory=list)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    type: Optional[RoomType] = None
    members: Optional[List[PyObjectId]] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class RoomResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    description: Optional[str] = None
    type: RoomType
    created_by: PyObjectId
    members: List[PyObjectId]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

from bson import ObjectId
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional


class PyObjectId(ObjectId):
    """
    Custom type that lets Pydantic work with MongoDB ObjectIds.
    """
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError(f"Invalid ObjectId: {v}")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema):
        schema.update(type="string")
        return schema


class BaseDocument(BaseModel):
    """
    Base class for all MongoDB documents.
    Provides id, created_at, updated_at out of the box.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
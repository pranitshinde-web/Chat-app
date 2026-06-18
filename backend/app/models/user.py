from typing import Optional
from pydantic import Field, EmailStr
from app.models.base import BaseDocument


class User(BaseDocument):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    hashed_password: str
    avatar_url: Optional[str] = None
    is_active: bool = True

    class Config:
        collection_name = "users"

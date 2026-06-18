from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.base_repository import BaseRepository
from app.core.config import settings


class UserRepository(BaseRepository):
    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database, settings.USERS_COLLECTION)

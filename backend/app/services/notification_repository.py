from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.base_repository import BaseRepository
from app.core.config import settings


class NotificationRepository(BaseRepository):
    def __init__(self, database: AsyncIOMotorDatabase):
        super().__init__(database, settings.NOTIFICATIONS_COLLECTION)

    async def find_unread_for_user(self, user_id: str) -> List[dict]:
        """Return all unread notifications for a user, newest first."""
        if not ObjectId.is_valid(user_id):
            return []
        return await self.find_many(
            filter={"user_id": ObjectId(user_id), "is_read": False},
            sort=[("created_at", -1)],
            limit=100,
        )

    async def mark_one_read(self, notification_id: str, user_id: str) -> Optional[dict]:
        """
        Mark a single notification as read. Scopes by user_id to prevent
        users from marking other users' notifications.
        Returns the updated document or None if not found / not owned.
        """
        if not ObjectId.is_valid(notification_id) or not ObjectId.is_valid(user_id):
            return None
        return await self.update_one(
            {
                "_id": ObjectId(notification_id),
                "user_id": ObjectId(user_id),
            },
            {"$set": {"is_read": True}},
            return_document=True,
        )

    async def mark_all_read(self, user_id: str) -> int:
        """
        Bulk-mark every unread notification as read for a user.
        Returns the count of modified documents.
        """
        if not ObjectId.is_valid(user_id):
            return 0
        return await self.update_many(
            {"user_id": ObjectId(user_id), "is_read": False},
            {"$set": {"is_read": True}},
        )

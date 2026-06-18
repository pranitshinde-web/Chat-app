from typing import Any, Dict, List, Optional, Type, TypeVar
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from datetime import datetime, timezone
from pymongo import ReturnDocument

from app.core.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class BaseRepository:
    """
    Generic async repository providing standard CRUD operations
    for any MongoDB collection. All specific repositories extend this.
    """

    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str):
        self.db = database
        self.collection_name = collection_name

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return self.db[self.collection_name]

    # ── Create ────────────────────────────────────────────────────────────────

    async def insert_one(self, document: Dict[str, Any]) -> Optional[str]:
        """
        Insert a single document. Returns the inserted _id as string.
        """
        try:
            document["created_at"] = datetime.now(timezone.utc)
            document["updated_at"] = datetime.now(timezone.utc)
            result = await self.collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(
                f"insert_one failed | "
                f"collection={self.collection_name} | {e}"
            )
            raise

    async def insert_many(self, documents: List[Dict[str, Any]]) -> List[str]:
        """
        Insert multiple documents. Returns list of inserted _ids.
        """
        try:
            now = datetime.now(timezone.utc)
            for doc in documents:
                doc.setdefault("created_at", now)
                doc.setdefault("updated_at", now)
            result = await self.collection.insert_many(documents)
            return [str(i) for i in result.inserted_ids]
        except Exception as e:
            logger.error(
                f"insert_many failed | "
                f"collection={self.collection_name} | {e}"
            )
            raise

    # ── Read ──────────────────────────────────────────────────────────────────

    async def find_one(
        self,
        filter: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find and return a single document matching the filter.
        Returns None if not found.
        """
        try:
            return await self.collection.find_one(filter, projection)
        except Exception as e:
            logger.error(
                f"find_one failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise

    async def find_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """
        Find a document by its MongoDB _id string.
        Returns None if id is invalid or document not found.
        """
        try:
            if not ObjectId.is_valid(id):
                return None
            return await self.collection.find_one({"_id": ObjectId(id)})
        except Exception as e:
            logger.error(
                f"find_by_id failed | "
                f"collection={self.collection_name} | id={id} | {e}"
            )
            raise

    async def find_many(
        self,
        filter: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
        sort: Optional[List] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find multiple documents with optional sorting and pagination.
        """
        try:
            cursor = self.collection.find(filter, projection)
            if sort:
                cursor = cursor.sort(sort)
            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(
                f"find_many failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise

    async def count(self, filter: Dict[str, Any]) -> int:
        """
        Return the count of documents matching the filter.
        """
        try:
            return await self.collection.count_documents(filter)
        except Exception as e:
            logger.error(
                f"count failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise

    # ── Update ────────────────────────────────────────────────────────────────

    async def update_one(
        self,
        filter: Dict[str, Any],
        update: Dict[str, Any],
        return_document: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a single document.
        Automatically sets updated_at timestamp.
        If return_document=True, returns the updated document.
        """
        try:
            if "$set" in update:
                update["$set"]["updated_at"] = datetime.now(timezone.utc)
            else:
                update["$set"] = {"updated_at": datetime.now(timezone.utc)}

            if return_document:
                return await self.collection.find_one_and_update(
                    filter,
                    update,
                    return_document=ReturnDocument.AFTER,
                )
            await self.collection.update_one(filter, update)
            return None
        except Exception as e:
            logger.error(
                f"update_one failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise

    async def update_many(
        self,
        filter: Dict[str, Any],
        update: Dict[str, Any],
    ) -> int:
        """
        Update all documents matching the filter.
        Returns the count of modified documents.
        """
        try:
            if "$set" in update:
                update["$set"]["updated_at"] = datetime.now(timezone.utc)
            else:
                update["$set"] = {"updated_at": datetime.now(timezone.utc)}

            result = await self.collection.update_many(filter, update)
            return result.modified_count
        except Exception as e:
            logger.error(
                f"update_many failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_one(self, filter: Dict[str, Any]) -> bool:
        """
        Delete a single document matching the filter.
        Returns True if a document was deleted.
        """
        try:
            result = await self.collection.delete_one(filter)
            return result.deleted_count > 0
        except Exception as e:
            logger.error(
                f"delete_one failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise

    async def delete_many(self, filter: Dict[str, Any]) -> int:
        """
        Delete all documents matching the filter.
        Returns count of deleted documents.
        """
        try:
            result = await self.collection.delete_many(filter)
            return result.deleted_count
        except Exception as e:
            logger.error(
                f"delete_many failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def exists(self, filter: Dict[str, Any]) -> bool:
        """
        Returns True if at least one document matches the filter.
        More efficient than find_one as it uses count_documents with limit=1.
        """
        try:
            count = await self.collection.count_documents(filter, limit=1)
            return count > 0
        except Exception as e:
            logger.error(
                f"exists failed | "
                f"collection={self.collection_name} | filter={filter} | {e}"
            )
            raise
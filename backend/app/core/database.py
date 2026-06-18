from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


mongodb = MongoDB()


async def connect_to_mongo() -> None:
    """
    Opens the MongoDB connection and stores the client
    and database on the module-level mongodb object.
    Called once on application startup.
    """
    logger.info("Connecting to MongoDB...")
    try:
        mongodb.client = AsyncIOMotorClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
        )

        # Force a real connection to verify the server is reachable
        await mongodb.client.admin.command("ping")

        mongodb.db = mongodb.client[settings.MONGO_DB_NAME]

        logger.info(
            f"Connected to MongoDB | "
            f"Database: {settings.MONGO_DB_NAME}"
        )

        # Create all indexes after confirming connection
        await create_indexes()

    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def disconnect_from_mongo() -> None:
    """
    Closes the MongoDB connection cleanly.
    Called once on application shutdown.
    """
    if mongodb.client:
        mongodb.client.close()
        logger.info("Disconnected from MongoDB")


def get_database() -> AsyncIOMotorDatabase:
    """
    Returns the active database instance.
    Use this as a FastAPI dependency in routers.
    """
    if mongodb.db is None:
        raise RuntimeError(
            "Database not initialized. "
            "Ensure connect_to_mongo() was called on startup."
        )
    return mongodb.db

async def create_indexes() -> None:
    """
    Creates all MongoDB indexes on startup.
    Uses background=True so existing data is not locked
    during index creation on a running application.
    """
    db = mongodb.db
    logger.info("Creating MongoDB indexes...")

    try:
        # ── Users Collection ─────────────────────────────────────────────
        await db[settings.USERS_COLLECTION].create_indexes([
            IndexModel(
                [("email", ASCENDING)],
                unique=True,
                name="unique_email",
                background=True,
            ),
            IndexModel(
                [("username", ASCENDING)],
                unique=True,
                name="unique_username",
                background=True,
            ),
            IndexModel(
                [("created_at", DESCENDING)],
                name="users_created_at",
                background=True,
            ),
        ])
        logger.info("Indexes created: users")

        # ── Rooms Collection ─────────────────────────────────────────────
        await db[settings.ROOMS_COLLECTION].create_indexes([
            IndexModel(
                [("type", ASCENDING)],
                name="rooms_type",
                background=True,
            ),
            IndexModel(
                [("members", ASCENDING)],
                name="rooms_members",
                background=True,
            ),
            IndexModel(
                [("created_by", ASCENDING)],
                name="rooms_created_by",
                background=True,
            ),
            IndexModel(
                [("name", ASCENDING)],
                name="rooms_name",
                background=True,
            ),
            IndexModel(
                [("created_at", DESCENDING)],
                name="rooms_created_at",
                background=True,
            ),
        ])
        logger.info("Indexes created: rooms")

        # ── Messages Collection ───────────────────────────────────────────
        await db[settings.MESSAGES_COLLECTION].create_indexes([
            # Primary query pattern: fetch messages for a room sorted by time
            IndexModel(
                [("room_id", ASCENDING), ("created_at", DESCENDING)],
                name="messages_room_created",
                background=True,
            ),
            IndexModel(
                [("sender_id", ASCENDING)],
                name="messages_sender",
                background=True,
            ),
            IndexModel(
                [("read_by", ASCENDING)],
                name="messages_read_by",
                background=True,
            ),
            # Supports cursor-based pagination by _id
            IndexModel(
                [("room_id", ASCENDING), ("_id", DESCENDING)],
                name="messages_room_id_cursor",
                background=True,
            ),
        ])
        logger.info("Indexes created: messages")

        # ── Notifications Collection ──────────────────────────────────────
        await db[settings.NOTIFICATIONS_COLLECTION].create_indexes([
            IndexModel(
                [("user_id", ASCENDING), ("is_read", ASCENDING)],
                name="notifications_user_unread",
                background=True,
            ),
            IndexModel(
                [("created_at", DESCENDING)],
                name="notifications_created_at",
                background=True,
            ),
        ])
        logger.info("Indexes created: notifications")

        logger.info("All MongoDB indexes created successfully")

    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        raise
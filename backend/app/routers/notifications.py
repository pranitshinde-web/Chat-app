from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationListResponse
from app.services.notification_repository import NotificationRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ── GET /api/notifications ────────────────────────────────────────────────────

@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List unread notifications",
    description="Returns all unread notifications for the authenticated user, newest first.",
)
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> NotificationListResponse:
    repo = NotificationRepository(db)
    docs = await repo.find_unread_for_user(str(current_user.id))
    notifications = [NotificationResponse(**doc) for doc in docs]
    return NotificationListResponse(
        notifications=notifications,
        unread_count=len(notifications),
    )


# ── PUT /api/notifications/{id}/read ─────────────────────────────────────────

@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
)
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> NotificationResponse:
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification ID format.",
        )

    repo = NotificationRepository(db)
    updated = await repo.mark_one_read(notification_id, str(current_user.id))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or does not belong to you.",
        )

    return NotificationResponse(**updated)


# ── PUT /api/notifications/read-all ──────────────────────────────────────────

@router.put(
    "/read-all",
    summary="Mark all notifications as read",
    description="Bulk-marks every unread notification for the current user as read in a single DB operation.",
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict:
    repo = NotificationRepository(db)
    modified_count = await repo.mark_all_read(str(current_user.id))
    logger.info(f"Marked {modified_count} notifications as read for user {current_user.id}")
    return {"marked_read": modified_count}

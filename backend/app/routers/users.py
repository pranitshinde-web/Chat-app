from fastapi import APIRouter, Depends, status, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.common import ErrorResponse, HTTPValidationError
from app.services.user_service import UserService
from app.core.security import get_current_user
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user profile.
    """
    return current_user


@router.put("/me")
async def update_my_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update current user profile.
    """
    try:
        user_service = UserService(db)
        return await user_service.update_user(str(current_user.id), user_update)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_my_profile endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating profile",
        )

from fastapi import APIRouter, Depends, status, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_database
from app.core.logging_config import get_logger
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.auth import AuthResponse, Token, TokenRefreshRequest
from app.schemas.common import ErrorResponse, HTTPValidationError
from app.services.user_service import UserService
from app.core.security import get_current_user
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register(
    user_in: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Register a new user.
    """
    try:
        user_service = UserService(db)
        return await user_service.register_user(user_in)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in register endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration",
        )


@router.post("/login")
async def login(
    login_data: UserLogin,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Authenticate user and return access token.
    """
    try:
        user_service = UserService(db)
        return await user_service.authenticate_user(login_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in login endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login",
        )


@router.post("/refresh")
async def refresh_token(
    refresh_data: TokenRefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Refresh access token using a refresh token.
    """
    try:
        user_service = UserService(db)
        return await user_service.refresh_access_token(refresh_data.refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in refresh_token endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during token refresh",
        )


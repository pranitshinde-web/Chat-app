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


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": AuthResponse, "description": "User successfully registered"},
        400: {"model": ErrorResponse, "description": "Bad request (e.g., email already exists)"},
        422: {"model": HTTPValidationError, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
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


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={
        200: {"model": AuthResponse, "description": "Successfully logged in"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account inactive"},
        422: {"model": HTTPValidationError, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
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


@router.post(
    "/refresh",
    response_model=Token,
    responses={
        200: {"model": Token, "description": "Tokens successfully refreshed"},
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
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


from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.room import RoomCreate, RoomResponse, RoomUpdate
from app.schemas.common import ErrorResponse, HTTPValidationError
from app.services.room_service import RoomService

logger = get_logger(__name__)
router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.post(
    "/",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_room(
    room_in: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Create a new room (public, private, or direct).
    Creator is automatically added as a member.
    """
    try:
        room_service = RoomService(db)
        return await room_service.create_room(room_in, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_room endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the room",
        )


@router.get(
    "/my",
    response_model=List[RoomResponse]
)
async def get_my_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get all rooms where the current user is a member.
    """
    try:
        room_service = RoomService(db)
        return await room_service.list_my_rooms(current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_my_rooms endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving your rooms",
        )


@router.get(
    "/",
    response_model=List[RoomResponse]
)
async def list_public_rooms(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get a paginated list of public rooms. Supports search by name.
    """
    try:
        room_service = RoomService(db)
        return await room_service.list_public_rooms(skip=skip, limit=limit, search=search)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_public_rooms endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing rooms",
        )


@router.post(
    "/{room_id}/join",
    response_model=RoomResponse
)
async def join_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Join a room by room_id.
    """
    try:
        room_service = RoomService(db)
        return await room_service.join_room(room_id, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in join_room endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while joining the room",
        )


@router.post(
    "/{room_id}/leave",
    response_model=RoomResponse
)
async def leave_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Leave a room by room_id.
    """
    try:
        room_service = RoomService(db)
        return await room_service.leave_room(room_id, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in leave_room endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while leaving the room",
        )


@router.get(
    "/{room_id}",
    response_model=RoomResponse
)
async def get_room_details(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get detailed information about a room. Only accessible to members.
    """
    try:
        room_service = RoomService(db)
        return await room_service.get_room_details(room_id, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_room_details endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving room details",
        )


@router.put(
    "/{room_id}"
)
async def update_room(
    room_id: str,
    room_update: RoomUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update room details (name and description). Only accessible to the creator.
    """
    try:
        room_service = RoomService(db)
        return await room_service.update_room(room_id, room_update, current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_room endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the room details",
        )

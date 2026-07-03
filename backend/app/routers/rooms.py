from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.room import RoomCreate, RoomResponse, RoomUpdate
from app.schemas.common import ErrorResponse, HTTPValidationError
from app.schemas.message import MessageResponse
from app.services.room_service import RoomService
from app.core.redis_client import get_set_members
from app.services.room_repository import RoomRepository
from app.services.user_repository import UserRepository
from app.services.message_repository import MessageRepository

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


@router.get(
    "/{room_id}/presence",
    response_model=List[dict],
    summary="Get online members in a room"
)
async def get_room_presence(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Returns a list of currently online members in a room.
    Each entry contains user_id and username.
    Only accessible to room members.
    """
    if not ObjectId.is_valid(room_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room ID format."
        )

    room_repo = RoomRepository(db)
    room = await room_repo.find_by_id(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found."
        )

    user_oid = ObjectId(current_user.id)
    if user_oid not in room.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this room."
        )

    # Retrieve all user IDs currently marked online in this room
    online_user_ids = await get_set_members(f"room:{room_id}:online")

    if not online_user_ids:
        return []

    # Enrich with username from MongoDB (batch lookup)
    user_repo = UserRepository(db)
    result = []
    for uid in online_user_ids:
        user_dict = await user_repo.find_by_id(uid)
        if user_dict:
            result.append({
                "user_id": uid,
                "username": user_dict.get("username", uid),
                "avatar_url": user_dict.get("avatar_url"),
            })
        else:
            result.append({"user_id": uid, "username": uid, "avatar_url": None})

    return result

@router.get(
    "/{room_id}/messages",
    response_model=List[MessageResponse]
)
async def get_room_messages(
    room_id: str,
    limit: int = 50,
    before: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get paginated message history for a room, sorted by created_at descending.
    Only accessible to room members.
    Supports cursor-based pagination using before (message_id).
    """
    if not ObjectId.is_valid(room_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room ID format."
        )
    
    # Check if room exists and user is a member
    room_repo = RoomRepository(db)
    room = await room_repo.find_by_id(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found."
        )
    
    user_oid = ObjectId(current_user.id)
    if user_oid not in room.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this room."
        )
        
    query = {"room_id": ObjectId(room_id)}
    if before:
        if not ObjectId.is_valid(before):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid before cursor ID format."
            )
        query["_id"] = {"$lt": ObjectId(before)}
        
    msg_repo = MessageRepository(db)
    messages = await msg_repo.find_many(
        filter=query,
        sort=[("_id", -1)],
        limit=limit
    )
    
    return [MessageResponse(**msg) for msg in messages]


@router.post(
    "/{room_id}/messages/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bulk mark all room messages as read"
)
async def mark_room_messages_read(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Marks all non-deleted messages in the room as read by the current user
    using a single bulk $addToSet operation.
    Broadcasts a room.read_all WebSocket event so connected clients can
    immediately clear unread indicators for this user.
    Only accessible to room members.
    """
    if not ObjectId.is_valid(room_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room ID format."
        )

    room_repo = RoomRepository(db)
    room = await room_repo.find_by_id(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found."
        )

    user_oid = ObjectId(current_user.id)
    if user_oid not in room.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this room."
        )

    msg_repo = MessageRepository(db)

    # Single bulk operation: add user to read_by for every non-deleted message
    # in the room where they are not already listed.
    # $addToSet is a no-op per document where user_oid is already present.
    modified_count = await msg_repo.update_many(
        filter={
            "room_id": ObjectId(room_id),
            "is_deleted": {"$ne": True},
            "read_by": {"$ne": user_oid},
        },
        update={
            "$addToSet": {"read_by": user_oid},
            "$set": {},   # triggers updated_at injection in BaseRepository
        },
    )

    logger.info(
        f"Bulk read: user {current_user.id} marked {modified_count} messages "
        f"as read in room {room_id}"
    )

    # Broadcast room.read_all so all connected members can update their UI
    from app.services.connection_manager import manager
    from app.schemas.websocket import WSEvent, WSEventType

    read_all_event = WSEvent(
        event=WSEventType.ROOM_READ_ALL,
        payload={
            "user_id": str(current_user.id),
            "username": current_user.username,
            "messages_marked": modified_count,
        },
        room_id=room_id,
    )
    await manager.broadcast_to_room(read_all_event.model_dump(mode="json"), room_id)

    # 204 No Content — nothing to return
    return None

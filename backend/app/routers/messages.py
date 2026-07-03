from fastapi import APIRouter, Depends, status, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.message import MessageUpdate, MessageResponse, ReactionRequest
from app.services.message_repository import MessageRepository
from app.services.room_repository import RoomRepository
from app.services.connection_manager import manager
from app.schemas.websocket import WSEvent, WSEventType

logger = get_logger(__name__)
router = APIRouter(prefix="/messages", tags=["Messages"])


@router.put(
    "/{message_id}",
    response_model=MessageResponse
)
async def edit_message(
    message_id: str,
    message_update: MessageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Edit a message's content. Only accessible to the original sender.
    Broadcasts message.updated event via WebSocket to the room.
    """
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format."
        )
        
    msg_repo = MessageRepository(db)
    message = await msg_repo.find_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found."
        )
        
    if message.get("is_deleted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit a deleted message."
        )
        
    # Verify sender
    if str(message.get("sender_id")) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only the original sender can edit this message."
        )
        
    # Update message content
    updated_doc = await msg_repo.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"content": message_update.content}},
        return_document=True
    )
    
    if not updated_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message."
        )
        
    response = MessageResponse(**updated_doc)
    
    # Broadcast message.updated WebSocket event to the room
    event = WSEvent(
        event=WSEventType.MESSAGE_UPDATED,
        payload=response.model_dump(mode="json"),
        room_id=str(updated_doc["room_id"])
    )
    await manager.broadcast_to_room(event.model_dump(mode="json"), str(updated_doc["room_id"]))
    
    return response


@router.delete(
    "/{message_id}",
    response_model=MessageResponse
)
async def delete_message(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Soft delete a message by setting is_deleted: true. Only accessible to the original sender.
    Broadcasts message.deleted event via WebSocket to the room.
    """
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format."
        )
        
    msg_repo = MessageRepository(db)
    message = await msg_repo.find_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found."
        )
        
    # Verify sender
    if str(message.get("sender_id")) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only the original sender can delete this message."
        )
        
    # Soft delete update
    updated_doc = await msg_repo.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"is_deleted": True}},
        return_document=True
    )
    
    if not updated_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message."
        )
        
    response = MessageResponse(**updated_doc)
    
    # Broadcast message.deleted WebSocket event to the room
    event = WSEvent(
        event=WSEventType.MESSAGE_DELETED,
        payload=response.model_dump(mode="json"),
        room_id=str(updated_doc["room_id"])
    )
    await manager.broadcast_to_room(event.model_dump(mode="json"), str(updated_doc["room_id"]))
    
    return response

@router.put(
    "/{message_id}/react",
    response_model=MessageResponse,
    summary="Toggle a reaction on a message",
    description=(
        "Add or remove an emoji reaction. Sending the same emoji twice toggles it off. "
        "Any room member can react. Broadcasts a message.reaction event to the room."
    ),
)
async def react_to_message(
    message_id: str,
    reaction: ReactionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> MessageResponse:
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format.",
        )

    msg_repo = MessageRepository(db)
    message = await msg_repo.find_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    if message.get("is_deleted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot react to a deleted message.",
        )

    # Verify the reactor is a member of the room
    room_id_str = str(message["room_id"])
    room_repo = RoomRepository(db)
    room = await room_repo.find_by_id(room_id_str)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )
    user_oid = ObjectId(str(current_user.id))
    if user_oid not in room.get("members", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of this room.",
        )

    emoji = reaction.emoji
    reaction_key = f"reactions.{emoji}"

    # Determine toggle direction: is the user already in this emoji's reactor list?
    existing_reactors = message.get("reactions", {}).get(emoji, [])
    already_reacted = user_oid in existing_reactors

    if already_reacted:
        # Remove the user from this emoji's list; if list becomes empty MongoDB
        # keeps the key as [] — we clean that up with $pull only.
        updated_doc = await msg_repo.update_one(
            {"_id": ObjectId(message_id)},
            {"$pull": {reaction_key: user_oid}},
            return_document=True,
        )
    else:
        # Add user to this emoji's list (creates the key if it doesn't exist yet)
        updated_doc = await msg_repo.update_one(
            {"_id": ObjectId(message_id)},
            {"$addToSet": {reaction_key: user_oid}},
            return_document=True,
        )

    if not updated_doc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update reaction.",
        )

    response = MessageResponse(**updated_doc)

    # Broadcast message.reaction to the whole room
    # Payload is minimal: only the changed fields so clients can patch in-place.
    reaction_event = WSEvent(
        event=WSEventType.MESSAGE_REACTION,
        payload={
            "message_id": message_id,
            "emoji": emoji,
            "user_id": str(current_user.id),
            "action": "removed" if already_reacted else "added",
            "reactions": response.model_dump(mode="json")["reactions"],
        },
        room_id=room_id_str,
    )
    await manager.broadcast_to_room(reaction_event.model_dump(mode="json"), room_id_str)

    logger.info(
        f"User {current_user.id} {'removed' if already_reacted else 'added'} "
        f"reaction '{emoji}' on message {message_id}"
    )
    return response

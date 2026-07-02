from fastapi import APIRouter, Depends, status, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.message import MessageUpdate, MessageResponse
from app.services.message_repository import MessageRepository
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

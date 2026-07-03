import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.core.database import get_database
from app.core.logging_config import get_logger
from app.core.security import decode_access_token
from app.services.user_repository import UserRepository
from app.services.room_repository import RoomRepository
from app.services.connection_manager import manager
from app.models.user import User
from app.schemas.websocket import WSEvent, WSEventType
from app.core.redis_client import (
    set_with_expiry, delete_key,
    add_to_set, remove_from_set, refresh_expiry,
)
from app.models.message import Message, MessageType
from app.services.message_repository import MessageRepository
from app.schemas.message import MessageResponse

logger = get_logger(__name__)
router = APIRouter(tags=["WebSockets"])

# ── Presence constants ────────────────────────────────────────────────────────
PRESENCE_TTL = 30        # seconds before a presence key auto-expires
KEEPALIVE_INTERVAL = 20  # seconds between keepalive refreshes
TYPING_TTL = 5           # seconds before a typing indicator auto-expires


# ─── WebSocket Event Handlers ─────────────────────────────────────────────────

async def handle_message_send(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    logger.info(f"Routing to handle_message_send for user {user_id} in room {event.room_id}")
    
    # 1. Validate sender is a room member
    room_repo = RoomRepository(db)
    room = await room_repo.find_by_id(event.room_id)
    if not room:
        error_event = WSEvent(
            event=WSEventType.ERROR,
            payload={"detail": f"Room {event.room_id} not found"},
            room_id=event.room_id
        )
        await websocket.send_json(error_event.model_dump(mode="json"))
        return
        
    user_oid = ObjectId(user_id)
    if user_oid not in room.get("members", []):
        logger.warning(f"Message send rejected: User {user_id} is not a member of room {event.room_id}")
        error_event = WSEvent(
            event=WSEventType.ERROR,
            payload={"detail": f"Forbidden: You are not a member of room {event.room_id}"},
            room_id=event.room_id
        )
        await websocket.send_json(error_event.model_dump(mode="json"))
        return

    # 2. Persist message to MongoDB
    content = event.payload.get("content") or event.payload.get("text")
    msg_type_str = event.payload.get("message_type", "text")
    try:
        msg_type = MessageType(msg_type_str)
    except ValueError:
        msg_type = MessageType.TEXT
        
    file_url = event.payload.get("file_url")
    
    message_doc = Message(
        room_id=ObjectId(event.room_id),
        sender_id=user_oid,
        content=content,
        message_type=msg_type,
        file_url=file_url
    )
    
    # Construct database document using native ObjectIds
    db_doc = {
        "room_id": message_doc.room_id,
        "sender_id": message_doc.sender_id,
        "content": message_doc.content,
        "message_type": message_doc.message_type.value,
        "file_url": message_doc.file_url,
        "read_by": message_doc.read_by,
        "is_deleted": message_doc.is_deleted
    }
    if message_doc.id:
        db_doc["_id"] = message_doc.id

    message_repo = MessageRepository(db)
    inserted_id = await message_repo.insert_one(db_doc)
    
    # Retrieve the inserted message to get full database state with timestamps
    inserted_msg = await message_repo.find_by_id(inserted_id)
    if not inserted_msg:
        logger.error(f"Failed to retrieve inserted message {inserted_id} from MongoDB")
        error_event = WSEvent(
            event=WSEventType.ERROR,
            payload={"detail": "Internal server error: failed to save message"},
            room_id=event.room_id
        )
        await websocket.send_json(error_event.model_dump(mode="json"))
        return

    # 3. Broadcast message.new event to all connected room members
    msg_response = MessageResponse(**inserted_msg)
    new_event = WSEvent(
        event=WSEventType.MESSAGE_NEW,
        payload=msg_response.model_dump(mode="json"),
        room_id=event.room_id
    )
    await manager.broadcast_to_room(new_event.model_dump(mode="json"), event.room_id)

    # 4. Return message.sent acknowledgement to sender
    sent_event = WSEvent(
        event=WSEventType.MESSAGE_SENT,
        payload={
            "message_id": inserted_id,
            "status": "sent"
        },
        room_id=event.room_id
    )
    await websocket.send_json(sent_event.model_dump(mode="json"))


async def handle_typing_start(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    """Set a Redis TTL key so typing state auto-expires, then broadcast to the room."""
    logger.info(f"typing.start from user {user_id} in room {event.room_id}")

    # Fetch username for the broadcast payload
    user_repo = UserRepository(db)
    user_dict = await user_repo.find_by_id(user_id)
    username = user_dict.get("username", user_id) if user_dict else user_id

    # Persist typing state in Redis with auto-expiry (handles dropped connections)
    await set_with_expiry(f"typing:{event.room_id}:{user_id}", "1", TYPING_TTL)

    # Broadcast to every other member currently in the room
    broadcast_event = WSEvent(
        event=WSEventType.TYPING_START,
        payload={"user_id": user_id, "username": username},
        room_id=event.room_id
    )
    await manager.broadcast_to_room_except(
        broadcast_event.model_dump(mode="json"), event.room_id, exclude_user_id=user_id
    )


async def handle_typing_stop(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    """Delete the Redis typing key and broadcast typing.stop to the room."""
    logger.info(f"typing.stop from user {user_id} in room {event.room_id}")

    user_repo = UserRepository(db)
    user_dict = await user_repo.find_by_id(user_id)
    username = user_dict.get("username", user_id) if user_dict else user_id

    await delete_key(f"typing:{event.room_id}:{user_id}")

    broadcast_event = WSEvent(
        event=WSEventType.TYPING_STOP,
        payload={"user_id": user_id, "username": username},
        room_id=event.room_id
    )
    await manager.broadcast_to_room_except(
        broadcast_event.model_dump(mode="json"), event.room_id, exclude_user_id=user_id
    )


async def handle_message_read(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    """
    Mark a message as read by the current user via $addToSet (idempotent),
    then broadcast the updated read_by list to the whole room.
    """
    logger.info(f"message.read from user {user_id} in room {event.room_id}")

    message_id = event.payload.get("message_id")
    if not message_id or not ObjectId.is_valid(message_id):
        error_event = WSEvent(
            event=WSEventType.ERROR,
            payload={"detail": "message.read requires a valid message_id in payload."},
            room_id=event.room_id,
        )
        await websocket.send_json(error_event.model_dump(mode="json"))
        return

    msg_repo = MessageRepository(db)
    message = await msg_repo.find_by_id(message_id)
    if not message:
        error_event = WSEvent(
            event=WSEventType.ERROR,
            payload={"detail": f"Message {message_id} not found."},
            room_id=event.room_id,
        )
        await websocket.send_json(error_event.model_dump(mode="json"))
        return

    # Atomically add user to read_by — $addToSet guarantees no duplicates
    user_oid = ObjectId(user_id)
    updated_doc = await msg_repo.update_one(
        {"_id": ObjectId(message_id)},
        {
            "$addToSet": {"read_by": user_oid},
            "$set": {},  # triggers updated_at injection in BaseRepository
        },
        return_document=True,
    )

    if not updated_doc:
        # Fallback: fetch the document as-is (already up-to-date from a race)
        updated_doc = message

    # Broadcast read_receipt with the fresh read_by list
    read_by_strs = [str(uid) for uid in updated_doc.get("read_by", [])]
    receipt_event = WSEvent(
        event=WSEventType.MESSAGE_READ_RECEIPT,
        payload={
            "message_id": message_id,
            "read_by": read_by_strs,
            "reader_id": user_id,
        },
        room_id=event.room_id,
    )
    await manager.broadcast_to_room(receipt_event.model_dump(mode="json"), event.room_id)


# Dispatcher map for client-initiated events
EVENT_HANDLERS = {
    WSEventType.MESSAGE_SEND: handle_message_send,
    WSEventType.TYPING_START: handle_typing_start,
    WSEventType.TYPING_STOP: handle_typing_stop,
    WSEventType.MESSAGE_READ: handle_message_read,
}


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    token = websocket.query_params.get("token")
    if not token:
        logger.warning(f"WebSocket connection rejected: token missing query parameter for room {room_id}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("WebSocket connection rejected: invalid sub claim in token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception as e:
        logger.warning(f"WebSocket connection rejected: token decode failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify user exists in the database
    user_repo = UserRepository(db)
    user_dict = await user_repo.find_by_id(user_id)
    if not user_dict:
        logger.warning(f"WebSocket connection rejected: user {user_id} not found in database")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    current_user = User(**user_dict)

    # Verify room exists
    room_repo = RoomRepository(db)
    room = await room_repo.find_by_id(room_id)
    if not room:
        logger.warning(f"WebSocket connection rejected: room {room_id} not found")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify membership
    user_oid = ObjectId(user_id)
    if user_oid not in room.get("members", []):
        logger.warning(f"WebSocket connection rejected: user {user_id} is not a member of room {room_id}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept and register connection
    await manager.connect(websocket, room_id, user_id)

    # Store user as online in Redis with TTL — will auto-expire if keepalive stops
    await set_with_expiry(f"user:{user_id}:status", "online", PRESENCE_TTL)
    await add_to_set("online_users", user_id)
    await add_to_set(f"room:{room_id}:online", user_id)

    # Broadcast presence.join to the room (except the joining user)
    join_event = WSEvent(
        event=WSEventType.PRESENCE_JOIN,
        payload={"user_id": user_id, "username": current_user.username},
        room_id=room_id
    )
    await manager.broadcast_to_room_except(join_event.model_dump(mode="json"), room_id, exclude_user_id=user_id)

    # ── Keepalive task: refreshes presence TTL every KEEPALIVE_INTERVAL seconds ──
    async def _keepalive():
        try:
            while True:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                await refresh_expiry(f"user:{user_id}:status", PRESENCE_TTL)
                logger.debug(f"Keepalive refreshed for user {user_id} in room {room_id}")
        except asyncio.CancelledError:
            pass  # Normal cancellation on disconnect

    keepalive_task = asyncio.create_task(_keepalive())

    try:
        while True:
            raw_data = await websocket.receive_text()
            logger.info(f"Received raw data from user {user_id} in room {room_id}: {raw_data}")

            # 1. Parse JSON
            import json
            try:
                data_dict = json.loads(raw_data)
            except json.JSONDecodeError as json_err:
                error_event = WSEvent(
                    event=WSEventType.ERROR,
                    payload={"detail": f"Invalid JSON format: {str(json_err)}"},
                    room_id=room_id
                )
                await websocket.send_json(error_event.model_dump(mode="json"))
                continue

            # 2. Validate against WSEvent model
            try:
                # Ensure room_id matches the path room_id
                if "room_id" not in data_dict:
                    data_dict["room_id"] = room_id
                event_msg = WSEvent(**data_dict)
            except Exception as val_err:
                error_event = WSEvent(
                    event=WSEventType.ERROR,
                    payload={"detail": f"Validation failed: {str(val_err)}"},
                    room_id=room_id
                )
                await websocket.send_json(error_event.model_dump(mode="json"))
                continue

            # Dispatch event to correct handler
            handler = EVENT_HANDLERS.get(event_msg.event)
            if not handler:
                error_event = WSEvent(
                    event=WSEventType.ERROR,
                    payload={"detail": f"Event type '{event_msg.event}' has no handler or is not dispatchable from client."},
                    room_id=room_id
                )
                await websocket.send_json(error_event.model_dump(mode="json"))
                continue

            try:
                await handler(event_msg, user_id, websocket, db)
            except Exception as handler_err:
                logger.error(f"Handler for event {event_msg.event} failed: {handler_err}", exc_info=True)
                error_event = WSEvent(
                    event=WSEventType.ERROR,
                    payload={"detail": f"Internal handler error: {str(handler_err)}"},
                    room_id=room_id
                )
                await websocket.send_json(error_event.model_dump(mode="json"))
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id} in room {room_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id} in room {room_id}: {e}", exc_info=True)
    finally:
        # Stop the keepalive heartbeat
        keepalive_task.cancel()
        # Clean up connection manager registry
        manager.disconnect(websocket, room_id, user_id)

        # Check remaining connections for user in this room
        room_connections = sum(
            1 for u_id, _ in manager.active_connections.get(room_id, []) if u_id == user_id
        )

        # Check remaining connections for user globally
        global_connections = sum(
            1
            for conn_list in manager.active_connections.values()
            for u_id, _ in conn_list
            if u_id == user_id
        )

        async def perform_redis_cleanup():
            # Clear any stale typing indicator for this user in this room
            await delete_key(f"typing:{room_id}:{user_id}")
            # If no connections left in the room, remove from room online set and broadcast leave
            if room_connections == 0:
                await remove_from_set(f"room:{room_id}:online", user_id)
                leave_event = WSEvent(
                    event=WSEventType.PRESENCE_LEAVE,
                    payload={"user_id": user_id, "username": current_user.username},
                    room_id=room_id
                )
                await manager.broadcast_to_room_except(
                    leave_event.model_dump(mode="json"), room_id, exclude_user_id=user_id
                )

            # If no connections left globally, mark status offline
            if global_connections == 0:
                await delete_key(f"user:{user_id}:status")
                await remove_from_set("online_users", user_id)

        try:
            await asyncio.shield(perform_redis_cleanup())
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error during WebSocket presence cleanup: {e}", exc_info=True)

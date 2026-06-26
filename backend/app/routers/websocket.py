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
from app.core.redis_client import set_value, delete_key, add_to_set, remove_from_set

logger = get_logger(__name__)
router = APIRouter(tags=["WebSockets"])


# ─── WebSocket Event Handlers (Stubs) ─────────────────────────────────────────

async def handle_message_send(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    logger.info(f"Routing to handle_message_send for user {user_id} in room {event.room_id}")
    # Echo back message.new confirming receipt
    confirm_event = WSEvent(
        event=WSEventType.MESSAGE_NEW,
        payload={
            "text": event.payload.get("text"),
            "sender_id": user_id,
            "status": "received_by_server"
        },
        room_id=event.room_id
    )
    await websocket.send_json(confirm_event.model_dump(mode="json"))


async def handle_typing_start(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    logger.info(f"Routing to handle_typing_start for user {user_id} in room {event.room_id}")
    confirm_event = WSEvent(
        event=WSEventType.TYPING_START,
        payload={"user_id": user_id, "status": "typing_started_confirm"},
        room_id=event.room_id
    )
    await websocket.send_json(confirm_event.model_dump(mode="json"))


async def handle_typing_stop(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    logger.info(f"Routing to handle_typing_stop for user {user_id} in room {event.room_id}")
    confirm_event = WSEvent(
        event=WSEventType.TYPING_STOP,
        payload={"user_id": user_id, "status": "typing_stopped_confirm"},
        room_id=event.room_id
    )
    await websocket.send_json(confirm_event.model_dump(mode="json"))


async def handle_message_read(event: WSEvent, user_id: str, websocket: WebSocket, db: AsyncIOMotorDatabase):
    logger.info(f"Routing to handle_message_read for user {user_id} in room {event.room_id}")
    confirm_event = WSEvent(
        event=WSEventType.MESSAGE_READ,
        payload={"message_id": event.payload.get("message_id"), "user_id": user_id, "status": "read_confirm"},
        room_id=event.room_id
    )
    await websocket.send_json(confirm_event.model_dump(mode="json"))


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

    # Store user as online in Redis
    await set_value(f"user:{user_id}:status", "online")
    await add_to_set("online_users", user_id)
    await add_to_set(f"room:{room_id}:online", user_id)

    # Broadcast presence.join to the room (except the joining user)
    join_event = WSEvent(
        event=WSEventType.PRESENCE_JOIN,
        payload={"user_id": user_id},
        room_id=room_id
    )
    await manager.broadcast_to_room_except(join_event.model_dump(mode="json"), room_id, exclude_user_id=user_id)

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
        # Clean up connection manager registry
        manager.disconnect(websocket, room_id, user_id)

        # Check remaining connections for user in this room
        room_connections = 0
        if room_id in manager.active_connections:
            for u_id, ws in manager.active_connections[room_id]:
                if u_id == user_id:
                    room_connections += 1

        # Check remaining connections for user globally
        global_connections = 0
        for r_id, conn_list in manager.active_connections.items():
            for u_id, ws in conn_list:
                if u_id == user_id:
                    global_connections += 1

        import asyncio

        async def perform_redis_cleanup():
            # If no connections left in the room, remove from room online set and broadcast leave
            if room_connections == 0:
                await remove_from_set(f"room:{room_id}:online", user_id)
                leave_event = WSEvent(
                    event=WSEventType.PRESENCE_LEAVE,
                    payload={"user_id": user_id},
                    room_id=room_id
                )
                await manager.broadcast_to_room_except(leave_event.model_dump(mode="json"), room_id, exclude_user_id=user_id)

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

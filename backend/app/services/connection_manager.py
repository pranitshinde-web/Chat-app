import json
from typing import Dict, List, Tuple
from fastapi import WebSocket

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        # Registry: room_id -> list of Tuple[user_id, websocket]
        self.active_connections: Dict[str, List[Tuple[str, WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str):
        """
        Accepts a WebSocket connection and registers it under the given room_id.
        """
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append((user_id, websocket))
        logger.info(f"User {user_id} connected to room {room_id}. Active users in room: {len(self.active_connections[room_id])}")

    def disconnect(self, websocket: WebSocket, room_id: str, user_id: str):
        """
        Removes a WebSocket connection from the registry.
        """
        if room_id in self.active_connections:
            connections = self.active_connections[room_id]
            # Remove the connection matching both user_id and websocket reference
            self.active_connections[room_id] = [
                (u_id, ws) for u_id, ws in connections if ws != websocket
            ]
            
            # Clean up empty room registry entry
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
                logger.info(f"Room {room_id} is now empty. Cleaned up registry entry.")
            else:
                logger.info(f"User {user_id} disconnected from room {room_id}. Active users left: {len(self.active_connections[room_id])}")

    async def send_to_user(self, message: dict, room_id: str, user_id: str):
        """
        Sends a JSON message to a specific user in a specific room.
        """
        if room_id in self.active_connections:
            for u_id, ws in self.active_connections[room_id]:
                if u_id == user_id:
                    try:
                        await ws.send_json(message)
                    except Exception as e:
                        logger.error(f"Error sending message to user {user_id} in room {room_id}: {e}")
                        # Auto disconnect if client connection is broken
                        self.disconnect(ws, room_id, user_id)

    async def broadcast_to_room(self, message: dict, room_id: str):
        """
        Broadcasts a JSON message to all connected users in a specific room.
        """
        if room_id in self.active_connections:
            # We copy the list to avoid modification-during-iteration issues if disconnect is triggered
            connections = list(self.active_connections[room_id])
            for u_id, ws in connections:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to user {u_id} in room {room_id}: {e}")
                    self.disconnect(ws, room_id, u_id)

    async def broadcast_to_room_except(self, message: dict, room_id: str, exclude_user_id: str):
        """
        Broadcasts a JSON message to all connected users in a room except the specified user.
        """
        if room_id in self.active_connections:
            connections = list(self.active_connections[room_id])
            for u_id, ws in connections:
                if u_id != exclude_user_id:
                    try:
                        await ws.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to user {u_id} (except path) in room {room_id}: {e}")
                        self.disconnect(ws, room_id, u_id)


# Singleton connection manager instance for application-wide use
manager = ConnectionManager()

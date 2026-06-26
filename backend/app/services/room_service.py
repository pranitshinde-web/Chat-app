from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import List, Optional

from app.services.room_repository import RoomRepository
from app.services.user_repository import UserRepository
from app.schemas.room import RoomCreate, RoomResponse, RoomUpdate
from app.models.room import Room, RoomType


class RoomService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.room_repo = RoomRepository(db)
        self.user_repo = UserRepository(db)

    async def create_room(self, room_in: RoomCreate, creator_id: ObjectId) -> RoomResponse:
        """
        Creates a room. Creator is automatically added to members.
        For direct type, validates that exactly two members are provided,
        and no duplicate DM room already exists.
        """
        # Ensure creator is in the members set
        members_set = {ObjectId(m) for m in room_in.members}
        members_set.add(creator_id)
        members_list = list(members_set)

        # Validation for RoomType.DIRECT
        if room_in.type == RoomType.DIRECT:
            if len(members_set) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A direct chat must have exactly two unique members."
                )
            
            # Check for duplicate DM room with exactly these two members
            duplicate_exists = await self.room_repo.exists({
                "type": RoomType.DIRECT,
                "members": {
                    "$all": members_list,
                    "$size": 2
                }
            })
            if duplicate_exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A direct message room already exists between these users."
                )

        # Validate that all member IDs exist in the database (optional but recommended)
        for member_id in members_list:
            if member_id != creator_id:
                member_exists = await self.user_repo.exists({"_id": member_id})
                if not member_exists:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User with ID {member_id} does not exist."
                    )

        # Construct the room document to be saved
        room_doc = {
            "name": room_in.name,
            "description": room_in.description,
            "type": room_in.type,
            "created_by": creator_id,
            "members": members_list
        }

        # Insert room
        inserted_id = await self.room_repo.insert_one(room_doc)
        
        # Retrieve the created room
        created_room = await self.room_repo.find_by_id(inserted_id)
        if not created_room:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve the created room."
            )

        return RoomResponse(**created_room)

    async def list_public_rooms(self, skip: int = 0, limit: int = 20, search: Optional[str] = None) -> List[RoomResponse]:
        """
        Returns a paginated list of public rooms, with optional search by name.
        """
        query = {"type": RoomType.PUBLIC}
        if search:
            # Escape regex special characters or just pass it directly
            query["name"] = {"$regex": search, "$options": "i"}

        rooms = await self.room_repo.find_many(
            filter=query,
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit
        )
        return [RoomResponse(**r) for r in rooms]

    async def list_my_rooms(self, user_id: ObjectId) -> List[RoomResponse]:
        """
        Returns all rooms the user is a member of.
        """
        query = {"members": user_id}
        rooms = await self.room_repo.find_many(
            filter=query,
            sort=[("updated_at", -1)],
            limit=100  # Fetch up to 100 rooms
        )
        return [RoomResponse(**r) for r in rooms]

    async def join_room(self, room_id: str, user_id: ObjectId) -> RoomResponse:
        """
        Adds the user to the room's members list.
        """
        if not ObjectId.is_valid(room_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room ID format."
            )

        room = await self.room_repo.find_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found."
            )

        if room.get("type") == RoomType.DIRECT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot join a direct message room."
            )

        updated_room = await self.room_repo.update_one(
            {"_id": ObjectId(room_id)},
            {"$addToSet": {"members": user_id}},
            return_document=True
        )
        return RoomResponse(**updated_room)

    async def leave_room(self, room_id: str, user_id: ObjectId) -> RoomResponse:
        """
        Removes the user from the room's members list.
        """
        if not ObjectId.is_valid(room_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room ID format."
            )

        room = await self.room_repo.find_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found."
            )

        # Check if the user is a member
        if user_id not in room.get("members", []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are not a member of this room."
            )

        updated_room = await self.room_repo.update_one(
            {"_id": ObjectId(room_id)},
            {"$pull": {"members": user_id}},
            return_document=True
        )
        return RoomResponse(**updated_room)

    async def get_room_details(self, room_id: str, user_id: ObjectId) -> RoomResponse:
        """
        Returns room details. Only accessible to members of the room.
        """
        if not ObjectId.is_valid(room_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room ID format."
            )

        room = await self.room_repo.find_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found."
            )

        # Check membership
        if user_id not in room.get("members", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You are not a member of this room."
            )

        return RoomResponse(**room)

    async def update_room(self, room_id: str, room_update: RoomUpdate, user_id: ObjectId) -> RoomResponse:
        """
        Allows the creator to update the room's name and description.
        """
        if not ObjectId.is_valid(room_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid room ID format."
            )

        room = await self.room_repo.find_by_id(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found."
            )

        # Verify creator
        if room.get("created_by") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only the room creator can update details."
            )

        # Extract only name and description for update
        update_dict = room_update.model_dump(exclude_unset=True)
        filtered_update = {k: v for k, v in update_dict.items() if k in ["name", "description"]}

        if not filtered_update:
            return RoomResponse(**room)

        updated_room = await self.room_repo.update_one(
            {"_id": ObjectId(room_id)},
            {"$set": filtered_update},
            return_document=True
        )
        return RoomResponse(**updated_room)

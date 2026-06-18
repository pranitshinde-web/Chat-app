from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from app.services.user_repository import UserRepository
from app.schemas.user import UserCreate, UserResponse, UserLogin, UserUpdate
from app.core.security import (
    hash_password, 
    verify_password, 
    generate_access_token, 
    generate_refresh_token,
    decode_refresh_token
)
from app.models.user import User


from pymongo.errors import DuplicateKeyError
from app.schemas.auth import AuthResponse, Token


class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repo = UserRepository(db)

    async def register_user(self, user_in: UserCreate) -> AuthResponse:
        # Initial check for uniqueness
        if await self.repo.exists({"email": user_in.email}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        if await self.repo.exists({"username": user_in.username}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

        hashed_password = hash_password(user_in.password)
        user_dict = user_in.model_dump(exclude={"password"})
        user_dict["hashed_password"] = hashed_password
        
        try:
            inserted_id = await self.repo.insert_one(user_dict)
        except DuplicateKeyError as e:
            if "email" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            if "username" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists",
            )
        
        created_user = await self.repo.find_by_id(inserted_id)
        user_id = str(created_user["_id"])
        
        access_token = generate_access_token({"sub": user_id})
        refresh_token = generate_refresh_token({"sub": user_id})
        
        return AuthResponse(
            user=UserResponse(**created_user),
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    async def authenticate_user(self, login_data: UserLogin) -> AuthResponse:
        """
        Authenticates a user and returns their profile and tokens.
        """
        user_dict = await self.repo.find_one({"email": login_data.email})
        
        unauthorized_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if not user_dict:
            raise unauthorized_exception

        if not verify_password(login_data.password, user_dict["hashed_password"]):
            raise unauthorized_exception

        if not user_dict.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        user_id = str(user_dict["_id"])
        access_token = generate_access_token({"sub": user_id})
        refresh_token = generate_refresh_token({"sub": user_id})

        return AuthResponse(
            user=UserResponse(**user_dict),
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    async def refresh_access_token(self, refresh_token: str) -> Token:
        """
        Validates refresh token and returns new access and refresh tokens.
        """
        payload = decode_refresh_token(refresh_token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
            
        user_dict = await self.repo.find_by_id(user_id)
        if not user_dict or not user_dict.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
            
        new_access_token = generate_access_token({"sub": user_id})
        new_refresh_token = generate_refresh_token({"sub": user_id})
        
        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )

    async def update_user(self, user_id: str, user_update: UserUpdate) -> UserResponse:
        """
        Updates a user's profile information.
        """
        update_data = user_update.model_dump(exclude_unset=True)
        if not update_data:
             user_dict = await self.repo.find_by_id(user_id)
             return UserResponse(**user_dict)

        if "username" in update_data:
            existing_user = await self.repo.find_one({"username": update_data["username"]})
            if existing_user and str(existing_user["_id"]) != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

        updated_user = await self.repo.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
            
        return UserResponse(**updated_user)

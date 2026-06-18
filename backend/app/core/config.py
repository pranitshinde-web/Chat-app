from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "ChatApp"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8001
    DEBUG: bool = False

    # MongoDB
    MONGO_URI: str
    MONGO_DB_NAME: str = "chatapp"
    USERS_COLLECTION: str = "users"
    ROOMS_COLLECTION: str = "rooms"
    MESSAGES_COLLECTION: str = "messages"
    NOTIFICATIONS_COLLECTION: str = "notifications"

    # Redis
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_SOCKET_TIMEOUT: int = 5

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads"

    # CORS
    ALLOWED_ORIGINS:str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
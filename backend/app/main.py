from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger
from app.core.database import connect_to_mongo, disconnect_from_mongo
from app.core.redis_client import connect_to_redis, disconnect_from_redis
from app.routers import auth, users, rooms, websocket, messages, upload, notifications

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(f"Starting {settings.APP_NAME} [{settings.APP_ENV}]")
    await connect_to_mongo()
    await connect_to_redis()
    logger.info("All connections established. App is ready.")
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down. Closing connections...")
    await disconnect_from_mongo()
    await disconnect_from_redis()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Real-time chat application backend built with FastAPI and WebSockets",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(websocket.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }
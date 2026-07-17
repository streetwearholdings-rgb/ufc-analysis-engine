import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.calculations import router as calculations_router
from app.api.context import admin_router as context_admin_router
from app.api.context import router as context_router
from app.api.events import router as events_router
from app.api.fighters import router as fighters_router
from app.api.health import router as health_router
from app.api.matchups import router as matchups_router
from app.config import get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
app = FastAPI(title="UFC Analysis Engine", version=settings.model_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(calculations_router)
app.include_router(fighters_router)
app.include_router(matchups_router)
app.include_router(events_router)
app.include_router(context_router)
app.include_router(context_admin_router)

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.analysis import router as analysis_router
from app.api.calculations import router as calculations_router
from app.api.context import admin_router as context_admin_router
from app.api.context import router as context_router
from app.api.events import router as events_router
from app.api.fighters import router as fighters_router
from app.api.health import router as health_router
from app.api.ingestion import router as ingestion_router
from app.api.matchups import router as matchups_router
from app.config import get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
app = FastAPI(title="UFC Analysis Engine", version=settings.model_version)


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logging.getLogger(__name__).error(
        "database_operation_failed method=%s path=%s error_type=%s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "database_error",
            "message": "The analysis service could not complete the database operation.",
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(ingestion_router)
app.include_router(calculations_router)
app.include_router(fighters_router)
app.include_router(matchups_router)
app.include_router(events_router)
app.include_router(context_router)
app.include_router(context_admin_router)

"""
FastAPI application factory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api.routes import health, video, events, analytics, alerts
from app.utils.helpers import ensure_dirs
from app.utils.logger import get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    log.info("Starting %s (%s)", settings.app_name, settings.app_env)
    ensure_dirs(settings.video_dir, settings.frames_dir, settings.export_dir, "data/db")
    init_db()
    yield
    log.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AisleIQ API",
        description="AI-powered CCTV analytics: person tracking, event streaming, anomaly detection",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error: %s %s", request.method, request.url)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Routers
    app.include_router(health.router)
    app.include_router(video.router)
    app.include_router(events.router)
    app.include_router(analytics.router)
    app.include_router(alerts.router)

    return app


app = create_app()

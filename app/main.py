"""FastAPI application entry point for RAI-Core."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import RAIError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to boot with insecure defaults in production.
    problems = settings.production_problems()
    if problems:
        raise RuntimeError(
            "Refusing to start: insecure production configuration:\n  - "
            + "\n  - ".join(problems)
        )
    # Dev convenience: auto-create tables when enabled. Production uses Alembic.
    if settings.auto_create_tables:
        init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "AI-powered academic research platform backend. "
        "Statistics are computed deterministically (pandas/scipy/statsmodels); "
        "the language model only reasons and writes prose."
    ),
    lifespan=lifespan,
)

_cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Per the CORS spec, credentials cannot be combined with a "*" origin, and
    # browsers reject that pairing. Only allow credentials with an explicit list.
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RAIError)
async def rai_error_handler(_: Request, exc: RAIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "ai_provider": settings.ai_provider,
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_prefix)

"""OpportunityOS API — production-ready FastAPI application."""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings

# ── Logging configuration ────────────────────────────────────────────────

def _configure_logging() -> None:
    """Configure structured logging for production use."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Production format: timestamp level module message
    # Development format: time level module message
    fmt = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=date_fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Quiet noisy libraries in production
    if not settings.debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger("app").setLevel(log_level)


_configure_logging()
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan — startup and shutdown hooks."""
    settings = get_settings()
    logger.info(
        "OpportunityOS API starting (env=%s, debug=%s)",
        settings.environment,
        settings.debug,
    )

    # Start automation scheduler if enabled
    if settings.automation_enabled:
        from app.automation.scheduler import start_scheduler
        start_scheduler()
        logger.info("Automation scheduler started")
    else:
        logger.info("Automation scheduler disabled")

    yield

    logger.info("OpportunityOS API shutting down")

    if settings.automation_enabled:
        from app.automation.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("Automation scheduler stopped")


# ── Application factory ──────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title="OpportunityOS API",
    version="0.1.0",
    lifespan=lifespan,
    # In production, disable detailed docs
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ── CORS ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
logger.info("CORS configured: origins=%s", settings.cors_origins_list)


# ── Request ID middleware ────────────────────────────────────────────────

@app.middleware("http")
async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Attach a unique request ID for tracing. Does not log sensitive data."""
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    # Log non-health requests for observability
    if not request.url.path.startswith("/health"):
        logger.info(
            "[%s] %s %s → %d (%.0fms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


# ── Global exception handler ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):  # type: ignore[no-untyped-def]
    """Catch-all handler: logs the full error, returns safe response."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "[%s] Unhandled exception: %s: %s",
        request_id,
        type(exc).__name__,
        exc,
        exc_info=True,
    )
    # Never expose stack traces or internal details to the client
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


# ── Health endpoints ─────────────────────────────────────────────────────

@app.get("/health")
def health_liveness() -> dict[str, str]:
    """Liveness: Is the application process running?"""
    return {
        "status": "ok",
        "service": "opportunityos-api",
        "version": "0.1.0",
    }


@app.get("/health/ready")
def health_readiness() -> dict[str, str]:
    """Readiness: Can the application reach its database?"""
    try:
        from app.db.session import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
        }
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "disconnected",
            },
        )


# ── Route registration ───────────────────────────────────────────────────

from app.api.routes.ai_insight import router as ai_insight_router
from app.api.routes.applications import router as applications_router
from app.api.routes.automation import router as automation_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.campaigns_enhanced import router as campaigns_enhanced_router
from app.api.routes.companies import router as companies_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.exports import router as exports_router
from app.api.routes.leads import router as leads_router
from app.api.routes.matching import router as matching_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.opportunities import router as opportunities_router
from app.api.routes.followups import router as followups_router
from app.api.routes.outreach import router as outreach_router
from app.api.routes.planning import router as planning_router
from app.api.routes.planning_enhanced import router as planning_enhanced_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.profiles import router as profiles_router

app.include_router(profiles_router)
app.include_router(companies_router)
app.include_router(leads_router)
app.include_router(planning_router)  # Before opportunities to avoid /opportunities/planning vs /{id} conflict
app.include_router(applications_router)
app.include_router(opportunities_router)
app.include_router(discovery_router)
app.include_router(matching_router)
app.include_router(ai_insight_router)
app.include_router(outreach_router)
app.include_router(followups_router)
app.include_router(campaigns_router)
app.include_router(campaigns_enhanced_router)
app.include_router(exports_router)
app.include_router(automation_router)
app.include_router(planning_enhanced_router)
app.include_router(analytics_router)
app.include_router(dashboard_router)
app.include_router(notifications_router)
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import logging
import sys
from contextlib import asynccontextmanager

from backend.config import settings
from backend.models import init_db, get_engine, get_session_factory
from backend.routers import health, ingest, metrics, sleep, activity, export, sync, coach, calendar, correlation, leaderboard

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Database
engine = get_engine(settings.database_url)
SessionLocal = get_session_factory(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Helios API...")
    init_db(engine)
    logger.info("Database initialized")

    # TODO: Start background schedulers (APScheduler)
    # TODO: Initialize Ollama client check

    yield

    # Shutdown
    logger.info("Shutting down Helios API...")
    engine.dispose()


app = FastAPI(
    title="Helios API",
    description="Helio Ring/Strap Health Analytics Platform with AI Coaching & Stress Calendar Correlation",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom OpenAPI to include security schemes
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Helios API",
        version="0.1.0",
        description="Helio Ring/Strap Health Analytics Platform with AI Coaching & Stress Calendar Correlation",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_code": 500}
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["Ingest"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])
app.include_router(sleep.router, prefix="/api/v1/sleep", tags=["Sleep"])
app.include_router(activity.router, prefix="/api/v1/activity", tags=["Activity"])
app.include_router(export.router, prefix="/api/v1/export", tags=["Export"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["Sync"])
app.include_router(coach.router, prefix="/api/v1/coach", tags=["Coach"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["Calendar"])
app.include_router(correlation.router, prefix="/api/v1/correlation", tags=["Correlation"])
app.include_router(leaderboard.router, prefix="/api/v1/leaderboard", tags=["Leaderboard"])


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Helios API",
        "version": "0.1.0",
        "description": "Helio Ring/Strap Health Analytics Platform",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
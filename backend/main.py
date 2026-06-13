from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
import logging
import sys
from contextlib import asynccontextmanager
import os

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

def get_helios_index_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="Helios - Helio Ring/Strap Health Analytics with AI Coaching & Stress Calendar Correlation" />
  <meta name="theme-color" content="#0ea5e9" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
  <meta name="apple-mobile-web-app-title" content="Helios" />
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
  <link rel="manifest" href="/manifest.webmanifest" />
  <title>Helios - Helio Health Analytics</title>
  <script>
    (function() {
      try {
        var theme = localStorage.getItem('theme');
        var systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (theme === 'dark' || (!theme && systemDark)) {
          document.documentElement.classList.add('dark');
        }
      } catch (e) {}
    })();
  </script>
</head>
<body class="min-h-screen bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-50 antialiased">
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>"""

# Static file serving for frontend
DIST_DIR = os.path.join(os.path.dirname(__file__), "dist")
if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
    
    @app.get("/")
    async def serve_index():
        from fastapi.responses import HTMLResponse
        response = HTMLResponse(content=get_helios_index_html())
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Skip API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Serve static files
        file_path = os.path.join(DIST_DIR, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # SPA fallback - serve index.html
        index_path = os.path.join(DIST_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail="Not found")

# Root endpoint (API info)
@app.get("/api")
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
        port=9000,
        reload=settings.debug
    )
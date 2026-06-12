from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.main import get_db
from backend.config import settings
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "helios-api",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.app_env
    }


@router.get("/health/db")
async def health_db(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
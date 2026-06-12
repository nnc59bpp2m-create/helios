from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from backend.main import get_db
from backend.models import SensorReading

router = APIRouter()


class ActivitySession(BaseModel):
    id: str
    activity_type: str  # run, walk, cycle, swim, workout, other
    start_ms: int
    end_ms: int
    duration_min: int
    avg_hr: Optional[float]
    max_hr: Optional[float]
    hrv_avg: Optional[float]
    calories: Optional[int]
    strain_score: Optional[float]
    distance_km: Optional[float]
    hr_zones: Optional[dict]


class ActivitySessionsResponse(BaseModel):
    sessions: List[ActivitySession]
    total_sessions: int
    total_active_min: int


@router.get("/sessions", response_model=ActivitySessionsResponse)
async def get_activity_sessions(
    days: int = Query(30, ge=1, le=365),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get auto-detected activity sessions.
    Detection based on: HR elevation + accelerometer magnitude + duration
    """
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    # Query for activity detection markers
    # This is a placeholder - real implementation would use:
    # - Continuous HR + accelerometer fusion
    # - ML model or rule-based detection
    # - Minimum duration threshold (10 min)

    # For now, return empty structure
    return ActivitySessionsResponse(
        sessions=[],
        total_sessions=0,
        total_active_min=0
    )


@router.get("/zones")
async def get_hr_zones(
    days: int = Query(30, ge=1, le=365),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get heart rate zone distribution for activities"""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    # Query HR readings during detected activity periods
    # Placeholder
    zones = {
        "zone_1": {"name": "Recovery", "range": "50-60% max", "minutes": 0},
        "zone_2": {"name": "Aerobic", "range": "60-70% max", "minutes": 0},
        "zone_3": {"name": "Tempo", "range": "70-80% max", "minutes": 0},
        "zone_4": {"name": "Threshold", "range": "80-90% max", "minutes": 0},
        "zone_5": {"name": "VO2 Max", "range": "90-100% max", "minutes": 0}
    }

    return {"zones": zones, "max_hr_estimate": None}


@router.get("/strain")
async def get_strain_trend(
    days: int = Query(30, ge=1, le=90),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get daily strain score trend"""
    # Placeholder - would compute from HR + duration + intensity
    return {
        "daily_strain": [],
        "weekly_avg": 0,
        "trend": "stable"
    }
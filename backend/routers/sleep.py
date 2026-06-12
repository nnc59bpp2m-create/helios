from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from backend.main import get_db
from backend.models import SensorReading

router = APIRouter()


class SleepStage(BaseModel):
    stage: str  # wake, light, deep, rem
    start_ms: int
    end_ms: int
    duration_min: int


class SleepStagesResponse(BaseModel):
    date: str
    hypnogram: List[SleepStage]
    total_sleep_min: int
    deep_min: int
    rem_min: int
    light_min: int
    awake_min: int
    efficiency: float
    latency_min: Optional[int]
    consistency_score: Optional[float]


@router.get("/stages", response_model=SleepStagesResponse)
async def get_sleep_stages(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get sleep hypnogram for a specific date.
    Note: This requires sleep stage data from the device.
    The Helio Ring/Strap provides sleep staging via Zepp OS.
    """
    # Parse date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"error": "Invalid date format"}

    start_ms = int(target_date.timestamp() * 1000)
    end_ms = int((target_date + timedelta(days=1)).timestamp() * 1000)

    # Query sleep stage data (metric_type = sleep_stage with value encoding)
    # This is a placeholder - actual implementation depends on how sleep stages are stored
    stages_query = db.query(SensorReading).filter(
        SensorReading.metric_type == "sleep_stage",
        SensorReading.timestamp_ms >= start_ms,
        SensorReading.timestamp_ms < end_ms
    )
    if device_id:
        stages_query = stages_query.filter(SensorReading.device_id == device_id)

    stages = stages_query.order_by(SensorReading.timestamp_ms).all()

    if not stages:
        # Return empty structure
        return SleepStagesResponse(
            date=date,
            hypnogram=[],
            total_sleep_min=0,
            deep_min=0,
            rem_min=0,
            light_min=0,
            awake_min=0,
            efficiency=0.0,
            latency_min=None,
            consistency_score=None
        )

    # Convert to hypnogram (assuming value encodes stage: 0=wake, 1=light, 2=deep, 3=rem)
    stage_map = {0: "wake", 1: "light", 2: "deep", 3: "rem"}
    hypnogram = []
    for s in stages:
        stage_name = stage_map.get(int(s.value), "unknown")
        # For simplicity, assume 30-min epochs
        hypnogram.append(SleepStage(
            stage=stage_name,
            start_ms=s.timestamp_ms,
            end_ms=s.timestamp_ms + 1800000,
            duration_min=30
        ))

    # Calculate totals
    stage_durations = {}
    for h in hypnogram:
        stage_durations[h.stage] = stage_durations.get(h.stage, 0) + h.duration_min

    total_sleep = sum(v for k, v in stage_durations.items() if k != "wake")
    time_in_bed = sum(stage_durations.values())
    efficiency = (total_sleep / time_in_bed * 100) if time_in_bed > 0 else 0

    return SleepStagesResponse(
        date=date,
        hypnogram=hypnogram,
        total_sleep_min=total_sleep,
        deep_min=stage_durations.get("deep", 0),
        rem_min=stage_durations.get("rem", 0),
        light_min=stage_durations.get("light", 0),
        awake_min=stage_durations.get("wake", 0),
        efficiency=round(efficiency, 1),
        latency_min=None,  # Would need wake onset detection
        consistency_score=None  # Would need multi-day comparison
    )


@router.get("/consistency")
async def get_sleep_consistency(
    days: int = Query(30, ge=7, le=365),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get sleep consistency metrics over a period"""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    # This would aggregate sleep stages across days
    # Placeholder response
    return {
        "period_days": days,
        "avg_bedtime": "23:15",
        "avg_wake_time": "07:30",
        "consistency_score": 78,
        "total_nights": days,
        "nights_with_data": 0
    }
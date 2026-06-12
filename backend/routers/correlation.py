from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from backend.main import get_db
from backend.models import CalendarEvent, EventStressScore, SensorReading, StressBaseline, Device

router = APIRouter()


class EventStressDetail(BaseModel):
    event: dict
    stress_score: Optional[dict]
    sensor_evidence: dict


class CorrelationEventsResponse(BaseModel):
    events: List[EventStressDetail]
    total: int
    period_start: int
    period_end: int


@router.get("/events", response_model=CorrelationEventsResponse)
async def get_correlated_events(
    start: Optional[str] = None,
    end: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get events with their stress scores"""
    query = db.query(CalendarEvent).options(joinedload(CalendarEvent.stress_scores))

    if start:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        query = query.filter(CalendarEvent.start_ms >= int(start_dt.timestamp() * 1000))

    if end:
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        query = query.filter(CalendarEvent.end_ms <= int(end_dt.timestamp() * 1000))

    if category:
        query = query.filter(CalendarEvent.category == category)

    events = query.order_by(CalendarEvent.start_ms.desc()).limit(limit).all()

    results = []
    for event in events:
        score = event.stress_scores[0] if event.stress_scores else None

        # Apply score filters
        if min_score is not None and (score is None or score.score is None or score.score < min_score):
            continue
        if max_score is not None and (score is None or score.score is None or score.score > max_score):
            continue

        # Get sensor evidence for this event
        sensor_evidence = _get_sensor_evidence(db, event)

        results.append(EventStressDetail(
            event={
                "id": event.id,
                "ical_uid": event.ical_uid,
                "title": event.title,
                "organizer_email": event.organizer_email,
                "attendee_emails": event.attendee_emails,
                "start_ms": event.start_ms,
                "end_ms": event.end_ms,
                "start_iso": datetime.fromtimestamp(event.start_ms / 1000).isoformat(),
                "end_iso": datetime.fromtimestamp(event.end_ms / 1000).isoformat(),
                "category": event.category,
                "provider": event.provider
            },
            stress_score={
                "score": score.score,
                "eda_component": score.eda_component,
                "hrv_component": score.hrv_component,
                "hr_component": score.hr_component,
                "temp_component": score.temp_component,
                "sensor_data_points": score.sensor_data_points
            } if score else None,
            sensor_evidence=sensor_evidence
        ))

    return CorrelationEventsResponse(
        events=results,
        total=len(results),
        period_start=int(start_dt.timestamp() * 1000) if start else 0,
        period_end=int(end_dt.timestamp() * 1000) if end else int(datetime.utcnow().timestamp() * 1000)
    )


def _get_sensor_evidence(db: Session, event: CalendarEvent) -> dict:
    """Get sensor readings around an event for evidence display"""
    window_start = event.start_ms - 1800000  # -30 min
    window_end = event.end_ms + 1800000  # +30 min

    evidence = {}
    for metric in ["eda", "hrv_sdnn", "hr", "skin_temp"]:
        readings = db.query(SensorReading).filter(
            SensorReading.metric_type == metric,
            SensorReading.timestamp_ms >= window_start,
            SensorReading.timestamp_ms <= window_end
        ).order_by(SensorReading.timestamp_ms).all()

        if readings:
            values = [r.value for r in readings]
            evidence[metric] = {
                "count": len(readings),
                "mean": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "timestamps": [r.timestamp_ms for r in readings[::max(1, len(readings)//20)]],  # Sample for chart
                "values": [r.value for r in readings[::max(1, len(readings)//20)]]
            }
        else:
            evidence[metric] = {"count": 0}

    return evidence


@router.get("/event/{event_uid}", response_model=EventStressDetail)
async def get_event_correlation(
    event_uid: str,
    db: Session = Depends(get_db)
):
    """Get detailed correlation for a specific event"""
    event = db.query(CalendarEvent).options(joinedload(CalendarEvent.stress_scores)).filter(
        CalendarEvent.ical_uid == event_uid
    ).first()

    if not event:
        raise HTTPException(404, "Event not found")

    score = event.stress_scores[0] if event.stress_scores else None
    sensor_evidence = _get_sensor_evidence(db, event)

    return EventStressDetail(
        event={
            "id": event.id,
            "ical_uid": event.ical_uid,
            "title": event.title,
            "organizer_email": event.organizer_email,
            "attendee_emails": event.attendee_emails,
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "start_iso": datetime.fromtimestamp(event.start_ms / 1000).isoformat(),
            "end_iso": datetime.fromtimestamp(event.end_ms / 1000).isoformat(),
            "category": event.category,
            "provider": event.provider,
            "description": event.description,
            "location": event.location,
            "recurrence_rule": event.recurrence_rule
        },
        stress_score={
            "score": score.score,
            "eda_component": score.eda_component,
            "hrv_component": score.hrv_component,
            "hr_component": score.hr_component,
            "temp_component": score.temp_component,
            "sensor_data_points": score.sensor_data_points,
            "computed_at": score.computed_at.isoformat() if score else None
        } if score else None,
        sensor_evidence=sensor_evidence
    )


@router.post("/recompute")
async def recompute_correlations(
    start: Optional[str] = None,
    end: Optional[str] = None,
    device_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Trigger recomputation of stress scores (e.g., after baseline updates)"""
    # This would be a background task in production
    from backend.services.correlation.engine import recompute_all_scores

    count = await recompute_all_scores(db, start, end, device_id)
    return {"recomputed": count, "message": f"Recomputed stress scores for {count} events"}


@router.get("/baselines")
async def get_stress_baselines(
    device_id: Optional[str] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get current stress baselines"""
    query = db.query(StressBaseline)

    if device_id:
        query = query.filter(StressBaseline.device_id == device_id)

    if date:
        target_date = datetime.fromisoformat(date.replace("Z", "+00:00")).date()
        query = query.filter(func.date(StressBaseline.computed_date) == target_date)
    else:
        # Latest baselines
        subquery = db.query(
            StressBaseline.device_id,
            StressBaseline.metric_type,
            StressBaseline.hour_of_day,
            func.max(StressBaseline.computed_date).label("max_date")
        ).group_by(
            StressBaseline.device_id,
            StressBaseline.metric_type,
            StressBaseline.hour_of_day
        ).subquery()

        query = query.join(subquery, and_(
            StressBaseline.device_id == subquery.c.device_id,
            StressBaseline.metric_type == subquery.c.metric_type,
            StressBaseline.hour_of_day == subquery.c.hour_of_day,
            StressBaseline.computed_date == subquery.c.max_date
        ))

    baselines = query.all()

    result = {}
    for b in baselines:
        key = f"{b.device_id}:{b.metric_type}"
        if key not in result:
            result[key] = {
                "device_id": b.device_id,
                "metric_type": b.metric_type,
                "hourly": {}
            }
        result[key]["hourly"][b.hour_of_day] = {
            "mean": b.mean_value,
            "std": b.std_value,
            "samples": b.sample_count
        }

    return {"baselines": list(result.values())}
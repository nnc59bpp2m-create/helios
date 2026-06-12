from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from backend.main import get_db
from backend.models import CalendarEvent, EventStressScore, Device

router = APIRouter()


class PersonLeaderboardEntry(BaseModel):
    person_id: str
    name: str
    email: str
    avg_stress_score: float
    event_count: int
    trend: str  # up, down, stable
    trend_pct: float
    top_stressors: List[str]  # Event titles with highest scores
    org_domain: str


class SeriesLeaderboardEntry(BaseModel):
    series_id: str
    title: str
    avg_stress_score: float
    event_count: int
    frequency: str  # daily, weekly, monthly
    attendees: List[str]
    trend: str


class TimeSlotLeaderboardEntry(BaseModel):
    hour: int
    day_of_week: int  # 0-6
    avg_stress_score: float
    event_count: int
    label: str  # "Mon 9am", "Fri 3pm"


class CategoryLeaderboardEntry(BaseModel):
    category: str
    avg_stress_score: float
    event_count: int
    total_duration_min: int


class LeaderboardResponse(BaseModel):
    people: List[PersonLeaderboardEntry]
    series: List[SeriesLeaderboardEntry]
    time_slots: List[TimeSlotLeaderboardEntry]
    categories: List[CategoryLeaderboardEntry]
    generated_at: datetime
    period_days: int


@router.get("/people", response_model=List[PersonLeaderboardEntry])
async def get_people_leaderboard(
    days: int = Query(30, ge=7, le=365),
    min_events: int = Query(3, ge=1),
    db: Session = Depends(get_db)
):
    """Get leaderboard of most stressful people (by attendee email)"""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    # Join events with stress scores
    events_query = db.query(
        CalendarEvent,
        EventStressScore
    ).join(
        EventStressScore, CalendarEvent.id == EventStressScore.event_id
    ).filter(
        CalendarEvent.start_ms >= start_ms,
        CalendarEvent.end_ms <= end_ms,
        EventStressScore.score.isnot(None)
    )

    # Aggregate by attendee email
    person_scores = defaultdict(list)
    for event, score in events_query.all():
        if event.attendee_emails:
            for email in event.attendee_emails:
                person_scores[email.lower()].append({
                    "score": score.score,
                    "title": event.title,
                    "start": event.start_ms,
                    "organizer": event.organizer_email
                })

    # Filter by minimum events and compute stats
    leaderboard = []
    for email, scores in person_scores.items():
        if len(scores) >= min_events:
            avg_score = sum(s["score"] for s in scores) / len(scores)
            # Trend: compare first half vs second half
            sorted_scores = sorted(scores, key=lambda x: x["start"])
            mid = len(sorted_scores) // 2
            first_half = sum(s["score"] for s in sorted_scores[:mid]) / max(1, mid)
            second_half = sum(s["score"] for s in sorted_scores[mid:]) / max(1, len(sorted_scores) - mid)
            trend_pct = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
            trend = "up" if trend_pct > 10 else "down" if trend_pct < -10 else "stable"

            # Top stressors
            top_events = sorted(scores, key=lambda x: x["score"], reverse=True)[:3]
            top_stressors = [f'{e["title"]} ({e["score"]:.0f})' for e in top_events]

            # Extract name from email (simple)
            name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
            org_domain = email.split("@")[1] if "@" in email else ""

            leaderboard.append(PersonLeaderboardEntry(
                person_id=email,
                name=name,
                email=email,
                avg_stress_score=round(avg_score, 1),
                event_count=len(scores),
                trend=trend,
                trend_pct=round(trend_pct, 1),
                top_stressors=top_stressors,
                org_domain=org_domain
            ))

    # Sort by avg stress score descending
    leaderboard.sort(key=lambda x: x.avg_stress_score, reverse=True)
    return leaderboard[:20]


@router.get("/series", response_model=List[SeriesLeaderboardEntry])
async def get_series_leaderboard(
    days: int = Query(30, ge=7, le=365),
    min_events: int = Query(2, ge=1),
    db: Session = Depends(get_db)
):
    """Get leaderboard of most stressful meeting series"""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    events_query = db.query(
        CalendarEvent,
        EventStressScore
    ).join(
        EventStressScore, CalendarEvent.id == EventStressScore.event_id
    ).filter(
        CalendarEvent.start_ms >= start_ms,
        CalendarEvent.end_ms <= end_ms,
        EventStressScore.score.isnot(None),
        CalendarEvent.recurrence_rule.isnot(None)
    )

    # Group by recurrence rule (series ID)
    series_scores = defaultdict(list)
    for event, score in events_query.all():
        series_id = event.recurrence_rule or event.title
        series_scores[series_id].append({
            "score": score.score,
            "title": event.title,
            "start": event.start_ms,
            "attendees": event.attendee_emails or [],
            "organizer": event.organizer_email
        })

    leaderboard = []
    for series_id, scores in series_scores.items():
        if len(scores) >= min_events:
            avg_score = sum(s["score"] for s in scores) / len(scores)
            # Determine frequency
            if len(scores) >= 4:
                freq = "weekly"
            elif len(scores) >= 2:
                freq = "bi-weekly"
            else:
                freq = "monthly"

            # All unique attendees
            all_attendees = set()
            for s in scores:
                all_attendees.update(s["attendees"])

            # Trend
            sorted_scores = sorted(scores, key=lambda x: x["start"])
            mid = len(sorted_scores) // 2
            first_half = sum(s["score"] for s in sorted_scores[:mid]) / max(1, mid)
            second_half = sum(s["score"] for s in sorted_scores[mid:]) / max(1, len(sorted_scores) - mid)
            trend_pct = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
            trend = "up" if trend_pct > 10 else "down" if trend_pct < -10 else "stable"

            leaderboard.append(SeriesLeaderboardEntry(
                series_id=series_id,
                title=scores[0]["title"],
                avg_stress_score=round(avg_score, 1),
                event_count=len(scores),
                frequency=freq,
                attendees=list(all_attendees)[:10],
                trend=trend
            ))

    leaderboard.sort(key=lambda x: x.avg_stress_score, reverse=True)
    return leaderboard[:20]


@router.get("/time-slots", response_model=List[TimeSlotLeaderboardEntry])
async def get_time_slot_leaderboard(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Get leaderboard of most stressful time slots"""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    events_query = db.query(
        CalendarEvent,
        EventStressScore
    ).join(
        EventStressScore, CalendarEvent.id == EventStressScore.event_id
    ).filter(
        CalendarEvent.start_ms >= start_ms,
        CalendarEvent.end_ms <= end_ms,
        EventStressScore.score.isnot(None)
    )

    # Bucket by day of week and hour
    slot_scores = defaultdict(list)
    for event, score in events_query.all():
        dt = datetime.fromtimestamp(event.start_ms / 1000)
        key = (dt.weekday(), dt.hour)
        slot_scores[key].append(score.score)

    leaderboard = []
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for (dow, hour), scores in slot_scores.items():
        if len(scores) >= 2:
            avg_score = sum(scores) / len(scores)
            leaderboard.append(TimeSlotLeaderboardEntry(
                hour=hour,
                day_of_week=dow,
                avg_stress_score=round(avg_score, 1),
                event_count=len(scores),
                label=f"{day_names[dow]} {hour:02d}:00"
            ))

    leaderboard.sort(key=lambda x: x.avg_stress_score, reverse=True)
    return leaderboard


@router.get("/categories", response_model=List[CategoryLeaderboardEntry])
async def get_category_leaderboard(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Get leaderboard by event category"""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    events_query = db.query(
        CalendarEvent,
        EventStressScore
    ).join(
        EventStressScore, CalendarEvent.id == EventStressScore.event_id
    ).filter(
        CalendarEvent.start_ms >= start_ms,
        CalendarEvent.end_ms <= end_ms,
        EventStressScore.score.isnot(None),
        CalendarEvent.category.isnot(None)
    )

    cat_scores = defaultdict(list)
    cat_durations = defaultdict(int)
    for event, score in events_query.all():
        cat_scores[event.category].append(score.score)
        duration = (event.end_ms - event.start_ms) / 60000  # minutes
        cat_durations[event.category] += duration

    leaderboard = []
    for category, scores in cat_scores.items():
        if scores:
            avg_score = sum(scores) / len(scores)
            leaderboard.append(CategoryLeaderboardEntry(
                category=category,
                avg_stress_score=round(avg_score, 1),
                event_count=len(scores),
                total_duration_min=round(cat_durations[category])
            ))

    leaderboard.sort(key=lambda x: x.avg_stress_score, reverse=True)
    return leaderboard


@router.get("/", response_model=LeaderboardResponse)
async def get_full_leaderboard(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Get complete leaderboard with all dimensions"""
    people = await get_people_leaderboard(days, 3, db)
    series = await get_series_leaderboard(days, 2, db)
    time_slots = await get_time_slot_leaderboard(days, db)
    categories = await get_category_leaderboard(days, db)

    return LeaderboardResponse(
        people=people,
        series=series,
        time_slots=time_slots,
        categories=categories,
        generated_at=datetime.utcnow(),
        period_days=days
    )


@router.get("/export")
async def export_leaderboard(
    format: str = Query("csv", pattern=r"^(csv|json)$"),
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Export leaderboard data"""
    full = await get_full_leaderboard(days, db)

    if format == "csv":
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["type", "id", "name", "avg_stress_score", "event_count", "trend", "trend_pct", "details"])
        for p in full.people:
            writer.writerow(["person", p.person_id, p.name, p.avg_stress_score, p.event_count, p.trend, p.trend_pct, "; ".join(p.top_stressors)])
        for s in full.series:
            writer.writerow(["series", s.series_id, s.title, s.avg_stress_score, s.event_count, s.trend, "", f"freq:{s.frequency} attendees:{len(s.attendees)}"])
        for t in full.time_slots:
            writer.writerow(["time_slot", f"{t.day_of_week}:{t.hour}", t.label, t.avg_stress_score, t.event_count, "", "", ""])
        for c in full.categories:
            writer.writerow(["category", c.category, c.category, c.avg_stress_score, c.event_count, "", "", f"duration:{c.total_duration_min}min"])

        from fastapi.responses import StreamingResponse
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=helios_leaderboard_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )
    else:
        import json
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            io.BytesIO(json.dumps(full.model_dump(), indent=2, default=str).encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=helios_leaderboard_{datetime.utcnow().strftime('%Y%m%d')}.json"}
        )
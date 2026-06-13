import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from collections import defaultdict
import statistics

from backend.models import CalendarEvent, EventStressScore, Device
from backend.config import settings

logger = logging.getLogger(__name__)


async def build_people_leaderboard(
    db: Session,
    days: int = 30,
    min_events: int = 3
) -> List[Dict[str, Any]]:
    """Build leaderboard of most stressful people (by attendee email)"""
    
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
    person_names = {}
    person_domains = {}
    
    for event, score in events_query.all():
        if event.attendee_emails:
            for email in event.attendee_emails:
                email_lower = email.lower()
                person_scores[email_lower].append({
                    "score": score.score,
                    "title": event.title,
                    "start": event.start_ms,
                    "organizer": event.organizer_email
                })
                # Extract name from email
                if email_lower not in person_names:
                    name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
                    person_names[email_lower] = name
                    person_domains[email_lower] = email.split("@")[1] if "@" in email else ""
    
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
            
            leaderboard.append({
                "person_id": email,
                "name": person_names.get(email, email.split("@")[0]),
                "email": email,
                "avg_stress_score": round(avg_score, 1),
                "event_count": len(scores),
                "trend": trend,
                "trend_pct": round(trend_pct, 1),
                "top_stressors": top_stressors,
                "org_domain": person_domains.get(email, "")
            })
    
    # Sort by avg stress score descending
    leaderboard.sort(key=lambda x: x["avg_stress_score"], reverse=True)
    return leaderboard[:20]


async def build_series_leaderboard(
    db: Session,
    days: int = 30,
    min_events: int = 2
) -> List[Dict[str, Any]]:
    """Build leaderboard of most stressful meeting series"""
    
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
            
            leaderboard.append({
                "series_id": series_id,
                "title": scores[0]["title"],
                "avg_stress_score": round(avg_score, 1),
                "event_count": len(scores),
                "frequency": freq,
                "attendees": list(all_attendees)[:10],
                "trend": trend
            })
    
    leaderboard.sort(key=lambda x: x["avg_stress_score"], reverse=True)
    return leaderboard[:20]


async def build_time_slot_leaderboard(
    db: Session,
    days: int = 30
) -> List[Dict[str, Any]]:
    """Build leaderboard of most stressful time slots"""
    
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
            leaderboard.append({
                "hour": hour,
                "day_of_week": dow,
                "avg_stress_score": round(avg_score, 1),
                "event_count": len(scores),
                "label": f"{day_names[dow]} {hour:02d}:00"
            })
    
    leaderboard.sort(key=lambda x: x["avg_stress_score"], reverse=True)
    return leaderboard


async def build_category_leaderboard(
    db: Session,
    days: int = 30
) -> List[Dict[str, Any]]:
    """Build leaderboard by event category"""
    
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
            leaderboard.append({
                "category": category,
                "avg_stress_score": round(avg_score, 1),
                "event_count": len(scores),
                "total_duration_min": round(cat_durations[category])
            })
    
    leaderboard.sort(key=lambda x: x["avg_stress_score"], reverse=True)
    return leaderboard


async def get_full_leaderboard(db: Session, days: int = 30) -> Dict[str, Any]:
    """Get complete leaderboard with all dimensions"""
    people = await build_people_leaderboard(db, days, 3)
    series = await build_series_leaderboard(db, days, 2)
    time_slots = await build_time_slot_leaderboard(db, days)
    categories = await build_category_leaderboard(db, days)
    
    return {
        "people": people,
        "series": series,
        "time_slots": time_slots,
        "categories": categories,
        "generated_at": datetime.utcnow().isoformat(),
        "period_days": days
    }


async def export_leaderboard(db: Session, days: int = 30, format: str = "csv") -> bytes:
    """Export leaderboard data"""
    full = await get_full_leaderboard(db, days)
    
    if format == "csv":
        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["type", "id", "name", "avg_stress_score", "event_count", "trend", "trend_pct", "details"])
        for p in full["people"]:
            writer.writerow(["person", p["person_id"], p["name"], p["avg_stress_score"], p["event_count"], p["trend"], p["trend_pct"], "; ".join(p["top_stressors"])])
        for s in full["series"]:
            writer.writerow(["series", s["series_id"], s["title"], s["avg_stress_score"], s["event_count"], s["trend"], "", f"freq:{s['frequency']} attendees:{len(s['attendees'])}"])
        for t in full["time_slots"]:
            writer.writerow(["time_slot", f"{t['day_of_week']}:{t['hour']}", t["label"], t["avg_stress_score"], t["event_count"], "", "", ""])
        for c in full["categories"]:
            writer.writerow(["category", c["category"], c["category"], c["avg_stress_score"], c["event_count"], "", "", f"duration:{c['total_duration_min']}min"])
        
        return output.getvalue().encode()
    else:
        import json
        return json.dumps(full, indent=2, default=str).encode()
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime
import csv
import io
import json

from backend.main import get_db
from backend.models import SensorReading, CorrelationExport
from backend.config import settings

router = APIRouter()


@router.get("/")
async def export_data(
    format: str = Query("csv", pattern=r"^(csv|json|sqlite)$"),
    metrics: str = Query("hr,hrv_sdnn,hrv_rmssd,spo2,skin_temp,eda"),
    start: Optional[str] = Query(None, description="ISO date or timestamp"),
    end: Optional[str] = Query(None, description="ISO date or timestamp"),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Export sensor data as CSV, JSON, or SQLite.
    """
    metric_list = [m.strip() for m in metrics.split(",")]

    # Parse time range
    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start_ms = int(start_dt.timestamp() * 1000)
        except ValueError:
            try:
                start_ms = int(start)
            except ValueError:
                raise HTTPException(400, "Invalid start date format")
    else:
        start_ms = 0

    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            end_ms = int(end_dt.timestamp() * 1000)
        except ValueError:
            try:
                end_ms = int(end)
            except ValueError:
                raise HTTPException(400, "Invalid end date format")
    else:
        end_ms = int(datetime.utcnow().timestamp() * 1000)

    query = db.query(SensorReading).filter(
        SensorReading.metric_type.in_(metric_list),
        SensorReading.timestamp_ms >= start_ms,
        SensorReading.timestamp_ms <= end_ms
    )
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)

    readings = query.order_by(SensorReading.timestamp_ms).all()

    if format == "csv":
        return _export_csv(readings, metric_list)
    elif format == "json":
        return _export_json(readings)
    elif format == "sqlite":
        return _export_sqlite(readings, start_ms, end_ms, device_id)
    else:
        raise HTTPException(400, "Unsupported format")


def _export_csv(readings: List[SensorReading], metrics: List[str]):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["device_id", "metric_type", "value", "timestamp_ms", "timestamp_iso", "source"])

    for r in readings:
        ts_iso = datetime.fromtimestamp(r.timestamp_ms / 1000).isoformat()
        writer.writerow([r.device_id, r.metric_type, r.value, r.timestamp_ms, ts_iso, r.source])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=helios_export_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
    )


def _export_json(readings: List[SensorReading]):
    data = []
    for r in readings:
        data.append({
            "device_id": r.device_id,
            "metric_type": r.metric_type,
            "value": r.value,
            "timestamp_ms": r.timestamp_ms,
            "timestamp_iso": datetime.fromtimestamp(r.timestamp_ms / 1000).isoformat(),
            "source": r.source,
            "raw_json": r.raw_json
        })

    return StreamingResponse(
        io.BytesIO(json.dumps(data, indent=2).encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=helios_export_{datetime.utcnow().strftime('%Y%m%d')}.json"}
    )


def _export_sqlite(readings: List[SensorReading], start_ms: int, end_ms: int, device_id: Optional[str]):
    import sqlite3
    import tempfile
    import os

    # Create temporary SQLite file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                source TEXT NOT NULL,
                raw_json TEXT
            )
        """)

        cursor.execute("CREATE INDEX idx_device_metric_time ON sensor_readings(device_id, metric_type, timestamp_ms)")

        for r in readings:
            cursor.execute(
                "INSERT INTO sensor_readings (device_id, metric_type, value, timestamp_ms, source, raw_json) VALUES (?, ?, ?, ?, ?, ?)",
                (r.device_id, r.metric_type, r.value, r.timestamp_ms, r.source, json.dumps(r.raw_json) if r.raw_json else None)
            )

        # Add metadata table
        cursor.execute("""
            CREATE TABLE export_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("INSERT INTO export_metadata VALUES (?, ?)", ("exported_at", datetime.utcnow().isoformat()))
        cursor.execute("INSERT INTO export_metadata VALUES (?, ?)", ("start_ms", str(start_ms)))
        cursor.execute("INSERT INTO export_metadata VALUES (?, ?)", ("end_ms", str(end_ms)))
        if device_id:
            cursor.execute("INSERT INTO export_metadata VALUES (?, ?)", ("device_id", device_id))
        cursor.execute("INSERT INTO export_metadata VALUES (?, ?)", ("row_count", str(len(readings))))

        conn.commit()
        conn.close()

        def iterfile():
            with open(tmp_path, "rb") as f:
                yield from f
            os.unlink(tmp_path)

        return StreamingResponse(
            iterfile(),
            media_type="application/x-sqlite3",
            headers={"Content-Disposition": f"attachment; filename=helios_export_{datetime.utcnow().strftime('%Y%m%d')}.db"}
        )
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


@router.get("/correlation")
async def export_correlation(
    format: str = Query("csv", pattern=r"^(csv|json)$"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Export event-stress correlation dataset"""
    from backend.models import CalendarEvent, EventStressScore
    from sqlalchemy.orm import joinedload

    query = db.query(CalendarEvent).options(joinedload(CalendarEvent.stress_scores))

    if start:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        query = query.filter(CalendarEvent.start_ms >= int(start_dt.timestamp() * 1000))

    if end:
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        query = query.filter(CalendarEvent.start_ms <= int(end_dt.timestamp() * 1000))

    events = query.all()

    rows = []
    for event in events:
        score = event.stress_scores[0] if event.stress_scores else None
        rows.append({
            "event_uid": event.ical_uid,
            "title": event.title,
            "organizer": event.organizer_email,
            "attendees": ",".join(event.attendee_emails) if event.attendee_emails else "",
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "category": event.category,
            "stress_score": score.score if score else None,
            "eda_component": score.eda_component if score else None,
            "hrv_component": score.hrv_component if score else None,
            "hr_component": score.hr_component if score else None,
            "temp_component": score.temp_component if score else None,
        })

    if format == "csv":
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=helios_correlation_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
        )
    else:
        return StreamingResponse(
            io.BytesIO(json.dumps(rows, indent=2).encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=helios_correlation_{datetime.utcnow().strftime('%Y%m%d')}.json"}
        )
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import math

from backend.main import get_db
from backend.models import SensorReading, Device

router = APIRouter()


class KPIResponse(BaseModel):
    resting_hr: Optional[float]
    hrv_trend: Optional[Dict[str, Any]]
    spo2_avg: Optional[float]
    skin_temp_baseline: Optional[float]
    recovery_score: Optional[float]
    sleep_quality: Optional[float]


class TimeSeriesPoint(BaseModel):
    timestamp_ms: int
    value: float
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None


class TimeSeriesResponse(BaseModel):
    metric: str
    interval: str
    points: List[TimeSeriesPoint]


class CorrelationResponse(BaseModel):
    x_metric: str
    y_metric: str
    points: List[Dict[str, float]]
    regression: Optional[Dict[str, float]]
    correlation_coefficient: Optional[float]


def get_time_range(days: int = 30):
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def downsample_points(points: List[tuple], interval_ms: int) -> List[TimeSeriesPoint]:
    """Downsample raw points to interval buckets (max/avg/min)"""
    if not points:
        return []

    buckets = {}
    for ts, val in points:
        bucket = (ts // interval_ms) * interval_ms
        if bucket not in buckets:
            buckets[bucket] = {"sum": 0, "count": 0, "min": val, "max": val}
        b = buckets[bucket]
        b["sum"] += val
        b["count"] += 1
        b["min"] = min(b["min"], val)
        b["max"] = max(b["max"], val)

    result = []
    for ts in sorted(buckets.keys()):
        b = buckets[ts]
        result.append(TimeSeriesPoint(
            timestamp_ms=ts,
            value=b["sum"] / b["count"],
            min=b["min"],
            max=b["max"],
            avg=b["sum"] / b["count"]
        ))
    return result


@router.get("/kpi", response_model=KPIResponse)
async def get_kpis(
    days: int = Query(30, ge=1, le=365),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    start_ms, end_ms = get_time_range(days)

    # Base query
    query = db.query(SensorReading).filter(
        SensorReading.timestamp_ms >= start_ms,
        SensorReading.timestamp_ms <= end_ms
    )
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)

    # Resting HR - minimum HR during sleep hours (0-6 AM)
    hr_readings = query.filter(SensorReading.metric_type == "hr").all()
    resting_hr = None
    if hr_readings:
        # Filter for sleep hours (approximate)
        sleep_hrs = [r.value for r in hr_readings if (datetime.fromtimestamp(r.timestamp_ms / 1000).hour >= 0 and datetime.fromtimestamp(r.timestamp_ms / 1000).hour <= 6)]
        if sleep_hrs:
            resting_hr = round(min(sleep_hrs), 1)

    # HRV Trend - last 7 days SDNN daily average
    hrv_readings = query.filter(SensorReading.metric_type == "hrv_sdnn").all()
    hrv_trend = {"direction": "stable", "change_pct": 0, "current": None, "previous": None}
    if hrv_readings:
        # Group by day
        daily_hrv = {}
        for r in hrv_readings:
            day = datetime.fromtimestamp(r.timestamp_ms / 1000).date()
            if day not in daily_hrv:
                daily_hrv[day] = []
            daily_hrv[day].append(r.value)

        daily_avgs = {d: sum(v)/len(v) for d, v in daily_hrv.items()}
        sorted_days = sorted(daily_avgs.keys())
        if len(sorted_days) >= 2:
            current = daily_avgs[sorted_days[-1]]
            previous = daily_avgs[sorted_days[-2]]
            change_pct = ((current - previous) / previous) * 100
            direction = "up" if change_pct > 5 else "down" if change_pct < -5 else "stable"
            hrv_trend = {"direction": direction, "change_pct": round(change_pct, 1), "current": round(current, 1), "previous": round(previous, 1)}

    # SpO2 Average - nocturnal (10 PM - 6 AM)
    spo2_readings = query.filter(SensorReading.metric_type == "spo2").all()
    spo2_avg = None
    if spo2_readings:
        nocturnal = [r.value for r in spo2_readings if datetime.fromtimestamp(r.timestamp_ms / 1000).hour >= 22 or datetime.fromtimestamp(r.timestamp_ms / 1000).hour <= 6]
        if nocturnal:
            spo2_avg = round(sum(nocturnal) / len(nocturnal), 1)

    # Skin Temp Baseline - circadian, average over 28 days
    temp_readings = query.filter(SensorReading.metric_type == "skin_temp").all()
    skin_temp_baseline = None
    if temp_readings:
        skin_temp_baseline = round(sum(r.value for r in temp_readings) / len(temp_readings), 2)

    # Recovery Score - weighted: HRV (40%), Sleep (30%), Temp (15%), Strain (15%)
    # Simplified for now
    recovery_score = None
    if hrv_trend["current"] and spo2_avg:
        hrv_score = min(100, max(0, (hrv_trend["current"] / 60) * 100))
        spo2_score = min(100, max(0, ((spo2_avg - 90) / 10) * 100))
        recovery_score = round(0.4 * hrv_score + 0.3 * spo2_score + 0.3 * 70, 1)  # placeholder temp/strain

    # Sleep Quality - from sleep stages (placeholder)
    sleep_quality = None  # Would need sleep stage data

    return KPIResponse(
        resting_hr=resting_hr,
        hrv_trend=hrv_trend,
        spo2_avg=spo2_avg,
        skin_temp_baseline=skin_temp_baseline,
        recovery_score=recovery_score,
        sleep_quality=sleep_quality
    )


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    metric: str = Query(..., pattern=r"^(hr|hrv_sdnn|hrv_rmssd|spo2|skin_temp|eda)$"),
    days: int = Query(30, ge=1, le=365),
    device_id: Optional[str] = Query(None),
    interval: str = Query("1h", pattern=r"^(1m|5m|15m|1h|6h|1d)$"),
    db: Session = Depends(get_db)
):
    start_ms, end_ms = get_time_range(days)

    interval_map = {"1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000, "6h": 21600000, "1d": 86400000}
    interval_ms = interval_map[interval]

    query = db.query(SensorReading.timestamp_ms, SensorReading.value).filter(
        SensorReading.metric_type == metric,
        SensorReading.timestamp_ms >= start_ms,
        SensorReading.timestamp_ms <= end_ms
    )
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)

    points = query.order_by(SensorReading.timestamp_ms).all()
    downsampled = downsample_points(points, interval_ms)

    return TimeSeriesResponse(metric=metric, interval=interval, points=downsampled)


@router.get("/correlation", response_model=CorrelationResponse)
async def get_correlation(
    x: str = Query(..., pattern=r"^(hr|hrv_sdnn|hrv_rmssd|spo2|skin_temp|eda)$"),
    y: str = Query(..., pattern=r"^(hr|hrv_sdnn|hrv_rmssd|spo2|skin_temp|eda)$"),
    days: int = Query(90, ge=7, le=365),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    start_ms, end_ms = get_time_range(days)

    # Get daily averages for both metrics
    def get_daily_avg(metric_type: str):
        query = db.query(
            func.date(func.datetime(SensorReading.timestamp_ms / 1000, "unixepoch")).label("day"),
            func.avg(SensorReading.value).label("avg")
        ).filter(
            SensorReading.metric_type == metric_type,
            SensorReading.timestamp_ms >= start_ms,
            SensorReading.timestamp_ms <= end_ms
        )
        if device_id:
            query = query.filter(SensorReading.device_id == device_id)
        return {row.day: row.avg for row in query.group_by("day").all()}

    x_daily = get_daily_avg(x)
    y_daily = get_daily_avg(y)

    # Align by day
    common_days = set(x_daily.keys()) & set(y_daily.keys())
    if len(common_days) < 3:
        return CorrelationResponse(x_metric=x, y_metric=y, points=[], regression=None, correlation_coefficient=None)

    x_vals = [x_daily[d] for d in sorted(common_days)]
    y_vals = [y_daily[d] for d in sorted(common_days)]

    # Linear regression
    n = len(x_vals)
    sum_x = sum(x_vals)
    sum_y = sum(y_vals)
    sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
    sum_x2 = sum(x * x for x in x_vals)
    sum_y2 = sum(y * y for y in y_vals)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
    intercept = (sum_y - slope * sum_x) / n if n != 0 else 0

    # Correlation coefficient
    numerator = n * sum_xy - sum_x * sum_y
    denominator = math.sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y))
    corr = numerator / denominator if denominator != 0 else 0

    points = [{"x": xv, "y": yv} for xv, yv in zip(x_vals, y_vals)]

    return CorrelationResponse(
        x_metric=x,
        y_metric=y,
        points=points,
        regression={"slope": round(slope, 4), "intercept": round(intercept, 4)},
        correlation_coefficient=round(corr, 4)
    )


@router.get("/devices")
async def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).all()
    return [{"device_id": d.device_id, "name": d.name, "type": d.device_type, "active": d.is_active} for d in devices]
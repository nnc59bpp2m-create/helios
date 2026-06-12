from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

from backend.main import get_db
from backend.models import SensorReading, Device
from backend.config import settings

router = APIRouter()


class ReadinessFactors(BaseModel):
    hrv: Dict[str, Any]
    sleep: Dict[str, Any]
    temperature: Dict[str, Any]
    strain: Dict[str, Any]


class ReadinessResponse(BaseModel):
    score: int  # 0-100
    label: str  # optimal, good, fair, needs_recovery
    factors: ReadinessFactors
    recommendations: List[str]
    computed_at: datetime


class Insight(BaseModel):
    type: str  # trend, anomaly, milestone, recommendation
    severity: str  # info, warning, critical
    title: str
    description: str
    metric: Optional[str]
    value: Optional[float]
    change_pct: Optional[float]
    timestamp: datetime


class InsightsResponse(BaseModel):
    insights: List[Insight]
    generated_at: datetime


class ChatMessage(BaseModel):
    role: str  # user, assistant
    content: str
    timestamp: datetime


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    citations: List[Dict[str, Any]] = []


@router.get("/readiness", response_model=ReadinessResponse)
async def get_readiness(
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get daily readiness score with factor breakdown"""
    end = datetime.utcnow()
    start = end - timedelta(days=30)

    # Get latest device if not specified
    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        if device:
            device_id = device.device_id

    if not device_id:
        return ReadinessResponse(
            score=0,
            label="no_data",
            factors=ReadinessFactors(hrv={}, sleep={}, temperature={}, strain={}),
            recommendations=["No device data available. Pair your Helio Ring/Strap."],
            computed_at=datetime.utcnow()
        )

    # HRV Factor (40% weight)
    hrv_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type.in_(["hrv_sdnn", "hrv_rmssd"]),
        SensorReading.timestamp_ms >= int((end - timedelta(days=7)).timestamp() * 1000)
    ).all()

    hrv_factor = {"score": 0, "current": None, "baseline": None, "trend": "stable", "weight": 0.4}
    if hrv_readings:
        current_hrv = sum(r.value for r in hrv_readings if r.metric_type == "hrv_sdnn") / max(1, len([r for r in hrv_readings if r.metric_type == "hrv_sdnn"]))
        # Baseline: 28-day average
        baseline_readings = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == "hrv_sdnn",
            SensorReading.timestamp_ms >= int((end - timedelta(days=28)).timestamp() * 1000)
        ).all()
        baseline_hrv = sum(r.value for r in baseline_readings) / max(1, len(baseline_readings)) if baseline_readings else current_hrv

        # Score: percentage of baseline, capped at 100
        hrv_score = min(100, max(0, (current_hrv / baseline_hrv * 100) if baseline_hrv > 0 else 50))
        trend = "up" if current_hrv > baseline_hrv * 1.05 else "down" if current_hrv < baseline_hrv * 0.95 else "stable"

        hrv_factor = {
            "score": round(hrv_score),
            "current": round(current_hrv, 1),
            "baseline": round(baseline_hrv, 1),
            "trend": trend,
            "weight": 0.4
        }

    # Sleep Factor (30% weight) - placeholder
    sleep_factor = {"score": 70, "quality": "good", "duration_hours": 7.5, "efficiency": 85, "weight": 0.3}

    # Temperature Factor (15% weight)
    temp_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type == "skin_temp",
        SensorReading.timestamp_ms >= int((end - timedelta(days=7)).timestamp() * 1000)
    ).all()

    temp_factor = {"score": 80, "current": None, "baseline": None, "deviation": 0, "weight": 0.15}
    if temp_readings:
        current_temp = sum(r.value for r in temp_readings) / len(temp_readings)
        baseline_readings = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == "skin_temp",
            SensorReading.timestamp_ms >= int((end - timedelta(days=28)).timestamp() * 1000)
        ).all()
        baseline_temp = sum(r.value for r in baseline_readings) / max(1, len(baseline_readings)) if baseline_readings else current_temp

        deviation = current_temp - baseline_temp
        # Score decreases with deviation > 0.5°C
        temp_score = max(0, 100 - abs(deviation) * 50)
        temp_factor = {
            "score": round(temp_score),
            "current": round(current_temp, 2),
            "baseline": round(baseline_temp, 2),
            "deviation": round(deviation, 2),
            "weight": 0.15
        }

    # Strain Factor (15% weight) - placeholder
    strain_factor = {"score": 75, "weekly_load": 0, "acute_chronic_ratio": 1.0, "weight": 0.15}

    # Weighted total
    total_score = round(
        hrv_factor["score"] * hrv_factor["weight"] +
        sleep_factor["score"] * sleep_factor["weight"] +
        temp_factor["score"] * temp_factor["weight"] +
        strain_factor["score"] * strain_factor["weight"]
    )

    # Label
    if total_score >= 85:
        label = "optimal"
    elif total_score >= 70:
        label = "good"
    elif total_score >= 55:
        label = "fair"
    else:
        label = "needs_recovery"

    # Recommendations
    recommendations = []
    if hrv_factor["trend"] == "down":
        recommendations.append("HRV is below baseline — prioritize sleep and active recovery")
    if temp_factor["deviation"] > 0.5:
        recommendations.append("Elevated skin temperature — consider illness or overtraining")
    if sleep_factor["efficiency"] < 80:
        recommendations.append("Sleep efficiency is low — optimize sleep hygiene")
    if not recommendations:
        recommendations.append("All metrics trending well — maintain current routine")

    return ReadinessResponse(
        score=total_score,
        label=label,
        factors=ReadinessFactors(
            hrv=hrv_factor,
            sleep=sleep_factor,
            temperature=temp_factor,
            strain=strain_factor
        ),
        recommendations=recommendations,
        computed_at=datetime.utcnow()
    )


@router.get("/insights", response_model=InsightsResponse)
async def get_insights(
    days: int = Query(7, ge=1, le=30),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get AI-generated insights for the period"""
    insights = []

    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        if device:
            device_id = device.device_id

    if not device_id:
        return InsightsResponse(insights=[], generated_at=datetime.utcnow())

    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)

    # HRV trend insight
    hrv_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type == "hrv_sdnn",
        SensorReading.timestamp_ms >= start_ms
    ).all()
    if hrv_readings:
        daily_avg = {}
        for r in hrv_readings:
            day = datetime.fromtimestamp(r.timestamp_ms / 1000).date()
            daily_avg.setdefault(day, []).append(r.value)
        daily_avgs = {d: sum(v)/len(v) for d, v in daily_avg.items()}
        sorted_days = sorted(daily_avgs.keys())
        if len(sorted_days) >= 2:
            change = ((daily_avgs[sorted_days[-1]] - daily_avgs[sorted_days[-2]]) / daily_avgs[sorted_days[-2]]) * 100
            if abs(change) > 10:
                insights.append(Insight(
                    type="trend",
                    severity="warning" if change < 0 else "info",
                    title=f"HRV {'dropped' if change < 0 else 'increased'} {abs(change):.0f}%",
                    description=f"Your 7-day HRV average has {'decreased' if change < 0 else 'improved'} significantly",
                    metric="hrv_sdnn",
                    value=daily_avgs[sorted_days[-1]],
                    change_pct=round(change, 1),
                    timestamp=datetime.utcnow()
                ))

    # Temperature anomaly
    temp_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type == "skin_temp",
        SensorReading.timestamp_ms >= start_ms
    ).all()
    if temp_readings:
        baseline = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == "skin_temp",
            SensorReading.timestamp_ms >= int((end - timedelta(days=28)).timestamp() * 1000)
        ).all()
        if baseline:
            baseline_avg = sum(r.value for r in baseline) / len(baseline)
            recent_avg = sum(r.value for r in temp_readings) / len(temp_readings)
            if recent_avg - baseline_avg > 0.5:
                insights.append(Insight(
                    type="anomaly",
                    severity="warning",
                    title="Elevated skin temperature",
                    description=f"Skin temperature {recent_avg - baseline_avg:.1f}°C above 28-day baseline",
                    metric="skin_temp",
                    value=recent_avg,
                    change_pct=((recent_avg - baseline_avg) / baseline_avg) * 100,
                    timestamp=datetime.utcnow()
                ))

    # SpO2 dips
    spo2_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type == "spo2",
        SensorReading.timestamp_ms >= start_ms
    ).all()
    if spo2_readings:
        low_spo2 = [r for r in spo2_readings if r.value < 90]
        if low_spo2:
            insights.append(Insight(
                type="anomaly",
                severity="critical",
                title=f"{len(low_spo2)} nocturnal SpO2 dips detected",
                description="Blood oxygen dropped below 90% during sleep — consider sleep apnea screening",
                metric="spo2",
                value=min(r.value for r in low_spo2),
                change_pct=None,
                timestamp=datetime.utcnow()
            ))

    return InsightsResponse(insights=insights, generated_at=datetime.utcnow())


@router.post("/chat", response_model=ChatResponse)
async def coach_chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    AI Coach chat endpoint - streams response from local LLM (Ollama).
    Uses RAG over user's recent health data.
    """
    # This will be implemented with Ollama integration
    # For now, return structured placeholder

    # Get recent data for context
    device_id = request.context.get("device_id") if request.context else None
    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        device_id = device.device_id if device else None

    context_data = {}
    if device_id:
        # Get last 7 days summary
        end = datetime.utcnow()
        start = end - timedelta(days=7)
        start_ms = int(start.timestamp() * 1000)

        for metric in ["hr", "hrv_sdnn", "spo2", "skin_temp", "eda"]:
            readings = db.query(SensorReading).filter(
                SensorReading.device_id == device_id,
                SensorReading.metric_type == metric,
                SensorReading.timestamp_ms >= start_ms
            ).all()
            if readings:
                context_data[metric] = {
                    "avg": round(sum(r.value for r in readings) / len(readings), 2),
                    "min": round(min(r.value for r in readings), 2),
                    "max": round(max(r.value for r in readings), 2),
                    "points": len(readings)
                }

    # Placeholder response
    return ChatResponse(
        response=f"I can see your recent health data. "
                 f"Your 7-day average HRV is {context_data.get('hrv_sdnn', {}).get('avg', 'N/A')}ms. "
                 f"Resting HR: {context_data.get('hr', {}).get('avg', 'N/A')}bpm. "
                 f"Ask me about your recovery, training load, or sleep patterns.",
        citations=[
            {"metric": k, "summary": v} for k, v in context_data.items()
        ]
    )


@router.get("/projections")
async def get_projections(
    days: int = Query(30, ge=7, le=90),
    device_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get 30/60/90 day trend projections with confidence intervals"""
    # Placeholder - would use statistical forecasting (ARIMA, Prophet, or simple linear)
    return {
        "hrv": {
            "30d": {"mean": 45, "ci_lower": 38, "ci_upper": 52},
            "60d": {"mean": 47, "ci_lower": 37, "ci_upper": 57},
            "90d": {"mean": 48, "ci_lower": 35, "ci_upper": 61}
        },
        "resting_hr": {
            "30d": {"mean": 58, "ci_lower": 54, "ci_upper": 62},
            "60d": {"mean": 57, "ci_lower": 52, "ci_upper": 62},
            "90d": {"mean": 56, "ci_lower": 50, "ci_upper": 62}
        },
        "skin_temp": {
            "30d": {"mean": 35.2, "ci_lower": 34.9, "ci_upper": 35.5},
            "60d": {"mean": 35.2, "ci_lower": 34.8, "ci_upper": 35.6},
            "90d": {"mean": 35.1, "ci_lower": 34.7, "ci_upper": 35.5}
        }
    }
import asyncio
import logging
import httpx
import json
import statistics
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from backend.models import SensorReading, Device, EventStressScore
from backend.config import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)
    
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Generate text from Ollama"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": temperature}
        }
        
        try:
            async with self.client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                
                if stream:
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if "message" in data and "content" in data["message"]:
                                    yield data["message"]["content"]
                                if data.get("done"):
                                    break
                            except json.JSONDecodeError:
                                pass
                else:
                    data = await response.json()
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                        
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            yield f"[Error: {str(e)}]"
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings for RAG"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text}
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []

    async def close(self):
        await self.client.aclose()


# Global client instance
_ollama_client: Optional[OllamaClient] = None

def get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client


# Readiness scoring
async def compute_readiness_score(db: Session, device_id: Optional[str] = None) -> Dict[str, Any]:
    """Compute daily readiness score with factor breakdown"""
    
    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        if not device:
            return {"score": 0, "label": "no_data", "factors": {}, "recommendations": ["No device data available"]}
        device_id = device.device_id
    
    end = datetime.utcnow()
    
    # HRV Factor (40% weight)
    hrv_factor = await _compute_hrv_factor(db, device_id, end)
    
    # Sleep Factor (30% weight)
    sleep_factor = await _compute_sleep_factor(db, device_id, end)
    
    # Temperature Factor (15% weight)
    temp_factor = await _compute_temp_factor(db, device_id, end)
    
    # Strain Factor (15% weight)
    strain_factor = await _compute_strain_factor(db, device_id, end)
    
    # Weighted total
    total_score = round(
        hrv_factor["score"] * 0.4 +
        sleep_factor["score"] * 0.3 +
        temp_factor["score"] * 0.15 +
        strain_factor["score"] * 0.15
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
    if strain_factor["acute_chronic_ratio"] > 1.3:
        recommendations.append("Acute training load high — consider deload week")
    if not recommendations:
        recommendations.append("All metrics trending well — maintain current routine")
    
    return {
        "score": total_score,
        "label": label,
        "factors": {
            "hrv": hrv_factor,
            "sleep": sleep_factor,
            "temperature": temp_factor,
            "strain": strain_factor
        },
        "recommendations": recommendations,
        "computed_at": datetime.utcnow().isoformat()
    }


async def _compute_hrv_factor(db: Session, device_id: str, end: datetime) -> Dict[str, Any]:
    start = end - timedelta(days=7)
    start_ms = int(start.timestamp() * 1000)
    
    hrv_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type.in_(["hrv_sdnn", "hrv_rmssd"]),
        SensorReading.timestamp_ms >= start_ms
    ).all()
    
    factor = {"score": 50, "current": None, "baseline": None, "trend": "stable", "weight": 0.4}
    
    if hrv_readings:
        current_hrv = sum(r.value for r in hrv_readings if r.metric_type == "hrv_sdnn") / max(1, len([r for r in hrv_readings if r.metric_type == "hrv_sdnn"]))
        
        # Baseline: 28-day average
        baseline_start = end - timedelta(days=28)
        baseline_readings = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == "hrv_sdnn",
            SensorReading.timestamp_ms >= int(baseline_start.timestamp() * 1000)
        ).all()
        baseline_hrv = sum(r.value for r in baseline_readings) / max(1, len(baseline_readings)) if baseline_readings else current_hrv
        
        hrv_score = min(100, max(0, (current_hrv / baseline_hrv * 100) if baseline_hrv > 0 else 50))
        trend = "up" if current_hrv > baseline_hrv * 1.05 else "down" if current_hrv < baseline_hrv * 0.95 else "stable"
        
        factor = {
            "score": round(hrv_score),
            "current": round(current_hrv, 1),
            "baseline": round(baseline_hrv, 1),
            "trend": trend,
            "weight": 0.4
        }
    
    return factor


async def _compute_sleep_factor(db: Session, device_id: str, end: datetime) -> Dict[str, Any]:
    # Placeholder - would query sleep stage data
    return {
        "score": 70,
        "quality": "good",
        "duration_hours": 7.5,
        "efficiency": 85,
        "weight": 0.3
    }


async def _compute_temp_factor(db: Session, device_id: str, end: datetime) -> Dict[str, Any]:
    start = end - timedelta(days=7)
    start_ms = int(start.timestamp() * 1000)
    
    temp_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type == "skin_temp",
        SensorReading.timestamp_ms >= start_ms
    ).all()
    
    factor = {"score": 80, "current": None, "baseline": None, "deviation": 0, "weight": 0.15}
    
    if temp_readings:
        current_temp = sum(r.value for r in temp_readings) / len(temp_readings)
        
        baseline_start = end - timedelta(days=28)
        baseline_readings = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == "skin_temp",
            SensorReading.timestamp_ms >= int(baseline_start.timestamp() * 1000)
        ).all()
        baseline_temp = sum(r.value for r in baseline_readings) / max(1, len(baseline_readings)) if baseline_readings else current_temp
        
        deviation = current_temp - baseline_temp
        temp_score = max(0, 100 - abs(deviation) * 50)
        
        factor = {
            "score": round(temp_score),
            "current": round(current_temp, 2),
            "baseline": round(baseline_temp, 2),
            "deviation": round(deviation, 2),
            "weight": 0.15
        }
    
    return factor


async def _compute_strain_factor(db: Session, device_id: str, end: datetime) -> Dict[str, Any]:
    # Placeholder - would compute from activity data
    return {
        "score": 75,
        "weekly_load": 0,
        "acute_chronic_ratio": 1.0,
        "weight": 0.15
    }


# Insights generation
async def generate_insights(db: Session, device_id: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
    """Generate AI insights for the period"""
    insights = []
    
    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        if not device:
            return insights
        device_id = device.device_id
    
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
                insights.append({
                    "type": "trend",
                    "severity": "warning" if change < 0 else "info",
                    "title": f"HRV {'dropped' if change < 0 else 'increased'} {abs(change):.0f}%",
                    "description": f"Your 7-day HRV average has {'decreased' if change < 0 else 'improved'} significantly",
                    "metric": "hrv_sdnn",
                    "value": daily_avgs[sorted_days[-1]],
                    "change_pct": round(change, 1),
                    "timestamp": datetime.utcnow().isoformat()
                })
    
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
                insights.append({
                    "type": "anomaly",
                    "severity": "warning",
                    "title": "Elevated skin temperature",
                    "description": f"Skin temperature {recent_avg - baseline_avg:.1f}°C above 28-day baseline",
                    "metric": "skin_temp",
                    "value": recent_avg,
                    "change_pct": ((recent_avg - baseline_avg) / baseline_avg) * 100,
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    # SpO2 dips
    spo2_readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type == "spo2",
        SensorReading.timestamp_ms >= start_ms
    ).all()
    
    if spo2_readings:
        low_spo2 = [r for r in spo2_readings if r.value < 90]
        if low_spo2:
            insights.append({
                "type": "anomaly",
                "severity": "critical",
                "title": f"{len(low_spo2)} nocturnal SpO2 dips detected",
                "description": "Blood oxygen dropped below 90% during sleep — consider sleep apnea screening",
                "metric": "spo2",
                "value": min(r.value for r in low_spo2),
                "change_pct": None,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    return insights


# RAG Chat
async def coach_chat(
    message: str,
    db: Session,
    device_id: Optional[str] = None,
    context: Optional[Dict] = None
) -> AsyncGenerator[str, None]:
    """AI Coach chat with RAG over user's health data"""
    
    client = get_ollama_client()
    
    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        device_id = device.device_id if device else None
    
    # Retrieve relevant health data
    context_data = {}
    if device_id:
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
    
    # Build system prompt with health context
    health_summary = "\n".join([
        f"- {k}: avg={v['avg']}, min={v['min']}, max={v['max']} ({v['points']} readings)"
        for k, v in context_data.items()
    ])
    
    system_prompt = f"""You are Helios, an AI health coach for the Helio Ring/Strap user.
    
    Current health context (last 7 days):
    {health_summary}
    
    Provide personalized, evidence-based coaching. Be concise and actionable.
    Reference specific metrics when relevant. Use encouraging tone.
    """
    
    async for chunk in client.generate(message, system_prompt=system_prompt, stream=True):
        yield chunk


# Projections
async def get_projections(db: Session, device_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
    """Get trend projections with confidence intervals"""
    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        if not device:
            return {}
        device_id = device.device_id
    
    # Simple linear projection based on recent trend
    projections = {}
    metrics = ["hrv_sdnn", "hr", "skin_temp"]
    
    for metric in metrics:
        recent = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == metric,
            SensorReading.timestamp_ms >= int((datetime.utcnow() - timedelta(days=30)).timestamp() * 1000)
        ).order_by(SensorReading.timestamp_ms).all()
        
        if len(recent) < 10:
            continue
        
        values = [r.value for r in recent]
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values) if len(values) > 1 else 0
        
        # Simple projection: assume trend continues
        projections[metric] = {
            "30d": {"mean": round(mean_val, 1), "ci_lower": round(mean_val - 1.96 * std_val, 1), "ci_upper": round(mean_val + 1.96 * std_val, 1)},
            "60d": {"mean": round(mean_val, 1), "ci_lower": round(mean_val - 1.96 * std_val * 1.2, 1), "ci_upper": round(mean_val + 1.96 * std_val * 1.2, 1)},
            "90d": {"mean": round(mean_val, 1), "ci_lower": round(mean_val - 1.96 * std_val * 1.4, 1), "ci_upper": round(mean_val + 1.96 * std_val * 1.4, 1)}
        }
    
    return projections
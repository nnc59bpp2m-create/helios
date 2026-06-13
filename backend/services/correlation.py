import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import statistics

from backend.models import SensorReading, CalendarEvent, EventStressScore, StressBaseline, Device
from backend.config import settings

logger = logging.getLogger(__name__)

# Stress score weights (sum = 1.0)
STRESS_WEIGHTS = {
    'eda': 0.40,      # Most specific to sympathetic activation
    'hrv': 0.30,      # Gold standard for autonomic balance
    'hr': 0.20,       # Secondary confirmer
    'temp': 0.10      # Tertiary confirmer
}

WINDOW_MINUTES = 30  # ±30 min around event


async def compute_event_stress_score(
    db: Session,
    event: CalendarEvent,
    device_id: Optional[str] = None
) -> Optional[EventStressScore]:
    """Compute stress score for a single calendar event"""
    
    window_start = event.start_ms - (WINDOW_MINUTES * 60000)
    window_end = event.end_ms + (WINDOW_MINUTES * 60000)
    
    # Get device if not specified
    if not device_id:
        device = db.query(Device).filter(Device.is_active == True).first()
        device_id = device.device_id if device else None
    
    if not device_id:
        return None
    
    # Query sensor data in window
    sensor_data = {}
    for metric in ['eda', 'hrv_sdnn', 'hr', 'skin_temp']:
        readings = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == metric,
            SensorReading.timestamp_ms >= window_start,
            SensorReading.timestamp_ms <= window_end
        ).all()
        
        if readings:
            values = [r.value for r in readings]
            sensor_data[metric] = {
                'values': values,
                'count': len(values),
                'mean': statistics.mean(values),
                'min': min(values),
                'max': max(values),
                'stdev': statistics.stdev(values) if len(values) > 1 else 0
            }
        else:
            sensor_data[metric] = {'count': 0}
    
    # Need minimum data points
    total_points = sum(s.get('count', 0) for s in sensor_data.values())
    if total_points < 5:
        return None
    
    # Get baselines for comparison
    baselines = {}
    for metric in ['eda', 'hrv_sdnn', 'hr', 'skin_temp']:
        baseline = get_baseline_for_event(db, device_id, metric, event)
        baselines[metric] = baseline
    
    # Compute component scores (0-100 each)
    component_scores = {}
    
    # EDA: Higher = more stress
    eda = sensor_data.get('eda', {})
    if eda.get('count', 0) > 0:
        baseline_eda = baselines.get('eda', {}).get('mean', eda['mean'])
        # Z-score relative to baseline
        z_score = (eda['mean'] - baseline_eda) / max(baselines.get('eda', {}).get('std', 1), 0.1)
        component_scores['eda'] = max(0, min(100, 50 + z_score * 25))
    else:
        component_scores['eda'] = None
    
    # HRV: Lower = more stress (inverted)
    hrv = sensor_data.get('hrv_sdnn', {})
    hrv_rmssd = sensor_data.get('hrv_rmssd', {})
    hrv_data = hrv if hrv.get('count', 0) > 0 else hrv_rmssd
    if hrv_data.get('count', 0) > 0:
        baseline_hrv = baselines.get('hrv_sdnn', {}).get('mean', hrv_data['mean'])
        z_score = (baseline_hrv - hrv_data['mean']) / max(baselines.get('hrv_sdnn', {}).get('std', 1), 1)
        component_scores['hrv'] = max(0, min(100, 50 + z_score * 25))
    else:
        component_scores['hrv'] = None
    
    # HR: Higher = more stress
    hr = sensor_data.get('hr', {})
    if hr.get('count', 0) > 0:
        baseline_hr = baselines.get('hr', {}).get('mean', hr['mean'])
        z_score = (hr['mean'] - baseline_hr) / max(baselines.get('hr', {}).get('std', 1), 1)
        component_scores['hr'] = max(0, min(100, 50 + z_score * 25))
    else:
        component_scores['hr'] = None
    
    # Temperature: Higher = more stress
    temp = sensor_data.get('skin_temp', {})
    if temp.get('count', 0) > 0:
        baseline_temp = baselines.get('skin_temp', {}).get('mean', temp['mean'])
        z_score = (temp['mean'] - baseline_temp) / max(baselines.get('skin_temp', {}).get('std', 0.1), 0.05)
        component_scores['temp'] = max(0, min(100, 50 + z_score * 25))
    else:
        component_scores['temp'] = None
    
    # Weighted composite score
    valid_components = {k: v for k, v in component_scores.items() if v is not None}
    if not valid_components:
        return None
    
    total_weight = sum(STRESS_WEIGHTS[k] for k in valid_components.keys())
    weighted_score = sum(
        valid_components[k] * STRESS_WEIGHTS[k] / total_weight 
        for k in valid_components
    )
    
    # Create or update stress score
    existing = db.query(EventStressScore).filter(
        EventStressScore.event_id == event.id
    ).first()
    
    if existing:
        existing.score = round(weighted_score, 1)
        existing.eda_component = round(valid_components.get('eda')) if valid_components.get('eda') else None
        existing.hrv_component = round(valid_components.get('hrv')) if valid_components.get('hrv') else None
        existing.hr_component = round(valid_components.get('hr')) if valid_components.get('hr') else None
        existing.temp_component = round(valid_components.get('temp')) if valid_components.get('temp') else None
        existing.baseline_hrv = baselines.get('hrv_sdnn', {}).get('mean')
        existing.baseline_hr = baselines.get('hr', {}).get('mean')
        existing.baseline_eda = baselines.get('eda', {}).get('mean')
        existing.baseline_temp = baselines.get('skin_temp', {}).get('mean')
        existing.sensor_data_points = total_points
        existing.recomputed_at = datetime.utcnow()
    else:
        existing = EventStressScore(
            event_id=event.id,
            score=round(weighted_score, 1),
            eda_component=round(valid_components.get('eda')) if valid_components.get('eda') else None,
            hrv_component=round(valid_components.get('hrv')) if valid_components.get('hrv') else None,
            hr_component=round(valid_components.get('hr')) if valid_components.get('hr') else None,
            temp_component=round(valid_components.get('temp')) if valid_components.get('temp') else None,
            baseline_hrv=baselines.get('hrv_sdnn', {}).get('mean'),
            baseline_hr=baselines.get('hr', {}).get('mean'),
            baseline_eda=baselines.get('eda', {}).get('mean'),
            baseline_temp=baselines.get('skin_temp', {}).get('mean'),
            sensor_data_points=total_points
        )
        db.add(existing)
    
    db.commit()
    db.refresh(existing)
    
    return existing


def get_baseline_for_event(
    db: Session, 
    device_id: str, 
    metric: str, 
    event: CalendarEvent
) -> Dict[str, float]:
    """Get baseline for event time (hour of day)"""
    event_hour = datetime.fromtimestamp(event.start_ms / 1000).hour
    
    baseline = db.query(StressBaseline).filter(
        StressBaseline.device_id == device_id,
        StressBaseline.metric_type == metric,
        StressBaseline.hour_of_day == event_hour
    ).order_by(StressBaseline.computed_date.desc()).first()
    
    if baseline:
        return {'mean': baseline.mean_value, 'std': baseline.std_value}
    
    # Fallback: overall average
    metric_map = {'hrv_sdnn': 'hrv_sdnn', 'hrv_rmssd': 'hrv_rmssd', 'hr': 'hr', 'eda': 'eda', 'skin_temp': 'skin_temp'}
    readings = db.query(SensorReading).filter(
        SensorReading.device_id == device_id,
        SensorReading.metric_type == metric_map.get(metric, metric)
    ).limit(1000).all()
    
    if readings:
        values = [r.value for r in readings]
        return {'mean': statistics.mean(values), 'std': statistics.stdev(values) if len(values) > 1 else 0}
    
    return {'mean': 0, 'std': 1}


async def recompute_all_scores(
    db: Session,
    start: Optional[str] = None,
    end: Optional[str] = None,
    device_id: Optional[str] = None
) -> int:
    """Recompute stress scores for all events in range"""
    
    query = db.query(CalendarEvent).filter(
        CalendarEvent.category.notin_(['personal', 'focus'])  # Exclude personal categories
    )
    
    if start:
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        query = query.filter(CalendarEvent.start_ms >= int(start_dt.timestamp() * 1000))
    
    if end:
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        query = query.filter(CalendarEvent.end_ms <= int(end_dt.timestamp() * 1000))
    
    events = query.all()
    count = 0
    
    for event in events:
        try:
            result = await compute_event_stress_score(db, event, device_id)
            if result:
                count += 1
        except Exception as e:
            logger.error(f"Failed to compute stress for event {event.id}: {e}")
    
    return count


async def update_stress_baselines(db: Session, device_id: str):
    """Update rolling 28-day baselines for a device"""
    from datetime import timedelta
    
    end = datetime.utcnow()
    start = end - timedelta(days=28)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    
    metric_types = ['hrv_sdnn', 'hrv_rmssd', 'hr', 'eda', 'skin_temp']
    
    for metric_type in metric_types:
        for hour in range(24):
            # Create hourly windows across 28 days
            hourly_values = []
            
            for day_offset in range(28):
                day_start = start_ms + (day_offset * 86400000) + (hour * 3600000)
                day_end = day_start + 3600000
                
                readings = db.query(SensorReading.value).filter(
                    SensorReading.device_id == device_id,
                    SensorReading.metric_type == metric_type,
                    SensorReading.timestamp_ms >= day_start,
                    SensorReading.timestamp_ms < day_end
                ).all()
                
                hourly_values.extend([r.value for r in readings])
            
            if len(hourly_values) >= 10:
                mean_val = statistics.mean(hourly_values)
                std_val = statistics.stdev(hourly_values) if len(hourly_values) > 1 else 0
                
                baseline = StressBaseline(
                    device_id=device_id,
                    metric_type=metric_type,
                    hour_of_day=hour,
                    mean_value=mean_val,
                    std_value=std_val,
                    sample_count=len(hourly_values),
                    computed_date=end
                )
                db.merge(baseline)
    
    db.commit()
    logger.info(f"Updated baselines for {device_id}")


# Anomaly detection
async def detect_anomalies(
    db: Session,
    device_id: str,
    days: int = 7
) -> List[Dict[str, Any]]:
    """Detect anomalous readings using z-score"""
    from datetime import timedelta
    
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    
    anomalies = []
    metric_types = ['hr', 'hrv_sdnn', 'spo2', 'skin_temp', 'eda']
    
    for metric in metric_types:
        readings = db.query(SensorReading).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == metric,
            SensorReading.timestamp_ms >= start_ms,
            SensorReading.timestamp_ms <= end_ms
        ).all()
        
        if len(readings) < 20:
            continue
        
        values = [r.value for r in readings]
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values)
        
        # Check for z-score > 2.5
        for r in readings:
            z = abs(r.value - mean_val) / std_val if std_val > 0 else 0
            if z > 2.5:
                anomalies.append({
                    'metric': metric,
                    'timestamp_ms': r.timestamp_ms,
                    'value': r.value,
                    'z_score': z,
                    'mean': mean_val,
                    'std': std_val
                })
    
    return anomalies
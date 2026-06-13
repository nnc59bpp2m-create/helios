import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from backend.models import SensorReading, Device
from backend.config import settings

logger = logging.getLogger(__name__)

async def reconcile_devices(db: Session, window_minutes: int = 5) -> Dict[str, Any]:
    """Reconcile overlapping readings from multiple devices (Ring + Strap)"""
    
    devices = db.query(Device).filter(Device.is_active == True).all()
    if len(devices) < 2:
        return {"reconciled": 0, "message": "Less than 2 active devices"}
    
    window_ms = window_minutes * 60000
    end = datetime.utcnow()
    start = end - timedelta(hours=24)  # Reconcile last 24 hours
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    
    total_merged = 0
    total_gaps_filled = 0
    
    # For each metric type, merge overlapping readings
    metric_types = ['hr', 'hrv_sdnn', 'hrv_rmssd', 'spo2', 'skin_temp', 'eda']
    
    for metric in metric_types:
        # Get readings from all devices in time window
        all_readings = []
        for device in devices:
            readings = db.query(SensorReading).filter(
                SensorReading.device_id == device.device_id,
                SensorReading.metric_type == metric,
                SensorReading.timestamp_ms >= start_ms,
                SensorReading.timestamp_ms <= end_ms
            ).order_by(SensorReading.timestamp_ms).all()
            
            for r in readings:
                all_readings.append({
                    'device_id': device.device_id,
                    'device_type': device.device_type,
                    'value': r.value,
                    'timestamp_ms': r.timestamp_ms,
                    'source': r.source,
                    'id': r.id
                })
        
        if len(all_readings) < 2:
            continue
        
        # Sort by timestamp
        all_readings.sort(key=lambda x: x['timestamp_ms'])
        
        # Merge overlapping time windows
        merged = merge_readings(all_readings, window_ms, metric)
        
        # Apply merged readings (update existing)
        for m in merged:
            if m.get('merged_from'):
                # Update the primary reading with merged value
                primary_id = m['primary_id']
                reading = db.query(SensorReading).filter(SensorReading.id == primary_id).first()
                if reading:
                    reading.value = m['merged_value']
                    reading.raw_json = {**reading.raw_json, 'merged_from': m['merged_from']} if reading.raw_json else {'merged_from': m['merged_from']}
                    total_merged += 1
    
    # Fill gaps via interpolation
    gaps_filled = await fill_gaps(db, devices, metric_types, start_ms, end_ms)
    total_gaps_filled = gaps_filled
    
    db.commit()
    
    return {
        "reconciled": total_merged,
        "gaps_filled": total_gaps_filled,
        "devices": [d.device_id for d in devices],
        "period": f"{window_minutes}min window, last 24h"
    }


def merge_readings(readings: List[Dict], window_ms: int, metric: str) -> List[Dict]:
    """Merge readings within time window, preferring higher fidelity"""
    if len(readings) < 2:
        return []
    
    merged = []
    i = 0
    
    while i < len(readings):
        current = readings[i]
        window_start = current['timestamp_ms']
        window_end = window_start + window_ms
        
        # Find all readings in this window
        window_readings = [current]
        j = i + 1
        while j < len(readings) and readings[j]['timestamp_ms'] <= window_end:
            window_readings.append(readings[j])
            j += 1
        
        if len(window_readings) > 1:
            # Determine primary (fidelity: ring > strap > others)
            fidelity_order = {'ring': 3, 'strap': 2, 'other': 1}
            window_readings.sort(key=lambda x: fidelity_order.get(x['device_type'], 1), reverse=True)
            primary = window_readings[0]
            
            # Weighted average
            total_weight = sum(fidelity_order.get(r['device_type'], 1) for r in window_readings)
            weighted_value = sum(r['value'] * fidelity_order.get(r['device_type'], 1) for r in window_readings) / total_weight
            
            merged.append({
                'primary_id': primary['id'],
                'merged_value': weighted_value,
                'merged_from': [r['id'] for r in window_readings[1:]],
                'metric': metric,
                'timestamp_ms': primary['timestamp_ms']
            })
        
        i = j
    
    return merged


async def fill_gaps(db: Session, devices: List[Device], metric_types: List[str], start_ms: int, end_ms: int) -> int:
    """Fill small gaps in time series via linear interpolation"""
    gaps_filled = 0
    max_gap_ms = 300000  # 5 minutes max gap to interpolate
    
    for device in devices:
        for metric in metric_types:
            readings = db.query(SensorReading).filter(
                SensorReading.device_id == device.device_id,
                SensorReading.metric_type == metric,
                SensorReading.timestamp_ms >= start_ms,
                SensorReading.timestamp_ms <= end_ms
            ).order_by(SensorReading.timestamp_ms).all()
            
            if len(readings) < 2:
                continue
            
            for i in range(len(readings) - 1):
                current = readings[i]
                next_reading = readings[i + 1]
                gap = next_reading.timestamp_ms - current.timestamp_ms
                
                if gap > 60000 and gap <= max_gap_ms:  # Gap between 1-5 minutes
                    # Interpolate
                    num_points = gap // 60000  # 1-minute intervals
                    if num_points > 1:
                        for j in range(1, num_points):
                            interp_ts = current.timestamp_ms + (j * gap // num_points)
                            interp_val = current.value + (next_reading.value - current.value) * (j / num_points)
                            
                            # Check if reading already exists
                            existing = db.query(SensorReading).filter(
                                SensorReading.device_id == device.device_id,
                                SensorReading.metric_type == metric,
                                SensorReading.timestamp_ms == interp_ts
                            ).first()
                            
                            if not existing:
                                interp_reading = SensorReading(
                                    device_id=device.device_id,
                                    metric_type=metric,
                                    value=interp_val,
                                    timestamp_ms=interp_ts,
                                    source='interpolated',
                                    raw_json={'interpolated': True, 'source_readings': [current.id, next_reading.id]}
                                )
                                db.add(interp_reading)
                                gaps_filled += 1
    
    return gaps_filled


async def get_device_status(db: Session) -> List[Dict]:
    """Get status of all devices"""
    devices = db.query(Device).all()
    status = []
    
    for device in devices:
        # Get latest reading
        latest = db.query(SensorReading).filter(
            SensorReading.device_id == device.device_id
        ).order_by(SensorReading.timestamp_ms.desc()).first()
        
        # Count readings in last hour
        hour_ago = int((datetime.utcnow() - timedelta(hours=1)).timestamp() * 1000)
        recent_count = db.query(SensorReading).filter(
            SensorReading.device_id == device.device_id,
            SensorReading.timestamp_ms >= hour_ago
        ).count()
        
        status.append({
            'device_id': device.device_id,
            'name': device.name,
            'type': device.device_type,
            'is_active': device.is_active,
            'latest_reading': {
                'metric': latest.metric_type if latest else None,
                'value': latest.value if latest else None,
                'timestamp': datetime.fromtimestamp(latest.timestamp_ms / 1000).isoformat() if latest else None
            },
            'recent_count_1h': recent_count,
            'last_seen': datetime.fromtimestamp(latest.timestamp_ms / 1000).isoformat() if latest else None
        })
    
    return status
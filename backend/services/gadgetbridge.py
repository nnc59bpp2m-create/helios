import asyncio
import logging
import sqlite3
import os
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.models import SensorReading, Device, GadgetbridgeImport
from backend.config import settings

logger = logging.getLogger(__name__)

# Gadgetbridge table names for Helio Ring/Strap
GB_TABLES = {
    'heart_rate': 'HEART_RATE',
    'hrv': 'HRV',
    'spo2': 'SPO2',
    'temperature': 'TEMPERATURE',
    'activity': 'MI_BAND_ACTIVITY_SAMPLE',
    'sleep': 'SLEEP',
    'steps': 'MI_BAND_ACTIVITY_SAMPLE',  # Same table
    'eda': None,  # Not in standard GB for Helio yet
    'accel': None
}

async def parse_gadgetbridge_db(db: Session, file_path: str, device_id: str) -> int:
    """Parse Gadgetbridge SQLite database and ingest readings"""
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Gadgetbridge DB not found: {file_path}")
    
    conn = sqlite3.connect(file_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    total_ingested = 0
    
    try:
        # Get or create device
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            device = Device(device_id=device_id, device_type="ring")
            db.add(device)
            db.flush()
        
        # Parse heart rate
        if await _table_exists(cursor, GB_TABLES['heart_rate']):
            count = await _parse_heart_rate(cursor, db, device_id)
            total_ingested += count
            logger.info(f"Parsed {count} heart rate readings")
        
        # Parse HRV
        if await _table_exists(cursor, GB_TABLES['hrv']):
            count = await _parse_hrv(cursor, db, device_id)
            total_ingested += count
            logger.info(f"Parsed {count} HRV readings")
        
        # Parse SpO2
        if await _table_exists(cursor, GB_TABLES['spo2']):
            count = await _parse_spo2(cursor, db, device_id)
            total_ingested += count
            logger.info(f"Parsed {count} SpO2 readings")
        
        # Parse temperature
        if await _table_exists(cursor, GB_TABLES['temperature']):
            count = await _parse_temperature(cursor, db, device_id)
            total_ingested += count
            logger.info(f"Parsed {count} temperature readings")
        
        # Parse sleep
        if await _table_exists(cursor, GB_TABLES['sleep']):
            count = await _parse_sleep(cursor, db, device_id)
            total_ingested += count
            logger.info(f"Parsed {count} sleep readings")
        
        # Parse activity/steps
        if await _table_exists(cursor, GB_TABLES['activity']):
            count = await _parse_activity(cursor, db, device_id)
            total_ingested += count
            logger.info(f"Parsed {count} activity readings")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Gadgetbridge parse error: {e}")
        db.rollback()
        raise
    finally:
        conn.close()
    
    return total_ingested


async def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    if not table_name:
        return False
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


async def _parse_heart_rate(cursor: sqlite3.Cursor, db: Session, device_id: str) -> int:
    """Parse HEART_RATE table from Gadgetbridge"""
    # Gadgetbridge HEART_RATE table: timestamp, value, ...
    cursor.execute(f"""
        SELECT timestamp, value FROM {GB_TABLES['heart_rate']}
        ORDER BY timestamp
    """)
    
    count = 0
    for row in cursor.fetchall():
        try:
            timestamp = row['timestamp']  # Unix timestamp in seconds
            value = row['value']
            
            # Handle millisecond vs second timestamps
            if timestamp > 1e12:
                timestamp_ms = timestamp
            else:
                timestamp_ms = int(timestamp * 1000)
            
            reading = SensorReading(
                device_id=device_id,
                metric_type='hr',
                value=float(value),
                timestamp_ms=timestamp_ms,
                source='gadgetbridge'
            )
            db.merge(reading)
            count += 1
            
            if count % 1000 == 0:
                db.flush()
        except Exception as e:
            logger.warning(f"Failed to parse HR row: {e}")
    
    return count


async def _parse_hrv(cursor: sqlite3.Cursor, db: Session, device_id: str) -> int:
    """Parse HRV table from Gadgetbridge"""
    cursor.execute(f"""
        SELECT timestamp, sdnn, rmssd FROM {GB_TABLES['hrv']}
        ORDER BY timestamp
    """)
    
    count = 0
    for row in cursor.fetchall():
        try:
            timestamp = row['timestamp']
            timestamp_ms = timestamp if timestamp > 1e12 else int(timestamp * 1000)
            
            if row['sdnn'] is not None:
                reading = SensorReading(
                    device_id=device_id,
                    metric_type='hrv_sdnn',
                    value=float(row['sdnn']),
                    timestamp_ms=timestamp_ms,
                    source='gadgetbridge'
                )
                db.merge(reading)
                count += 1
            
            if row['rmssd'] is not None:
                reading = SensorReading(
                    device_id=device_id,
                    metric_type='hrv_rmssd',
                    value=float(row['rmssd']),
                    timestamp_ms=timestamp_ms,
                    source='gadgetbridge'
                )
                db.merge(reading)
                count += 1
                
            if count % 1000 == 0:
                db.flush()
        except Exception as e:
            logger.warning(f"Failed to parse HRV row: {e}")
    
    return count


async def _parse_spo2(cursor: sqlite3.Cursor, db: Session, device_id: str) -> int:
    """Parse SPO2 table from Gadgetbridge"""
    cursor.execute(f"""
        SELECT timestamp, value FROM {GB_TABLES['spo2']}
        ORDER BY timestamp
    """)
    
    count = 0
    for row in cursor.fetchall():
        try:
            timestamp = row['timestamp']
            timestamp_ms = timestamp if timestamp > 1e12 else int(timestamp * 1000)
            
            reading = SensorReading(
                device_id=device_id,
                metric_type='spo2',
                value=float(row['value']),
                timestamp_ms=timestamp_ms,
                source='gadgetbridge'
            )
            db.merge(reading)
            count += 1
            
            if count % 1000 == 0:
                db.flush()
        except Exception as e:
            logger.warning(f"Failed to parse SpO2 row: {e}")
    
    return count


async def _parse_temperature(cursor: sqlite3.Cursor, db: Session, device_id: str) -> int:
    """Parse TEMPERATURE table from Gadgetbridge"""
    cursor.execute(f"""
        SELECT timestamp, value FROM {GB_TABLES['temperature']}
        ORDER BY timestamp
    """)
    
    count = 0
    for row in cursor.fetchall():
        try:
            timestamp = row['timestamp']
            timestamp_ms = timestamp if timestamp > 1e12 else int(timestamp * 1000)
            
            # Temperature often in 0.01°C units in Gadgetbridge
            temp_value = float(row['value'])
            if temp_value > 100:  # Likely in centi-degrees
                temp_value = temp_value / 100
            
            reading = SensorReading(
                device_id=device_id,
                metric_type='skin_temp',
                value=temp_value,
                timestamp_ms=timestamp_ms,
                source='gadgetbridge'
            )
            db.merge(reading)
            count += 1
            
            if count % 1000 == 0:
                db.flush()
        except Exception as e:
            logger.warning(f"Failed to parse temperature row: {e}")
    
    return count


async def _parse_sleep(cursor: sqlite3.Cursor, db: Session, device_id: str) -> int:
    """Parse SLEEP table from Gadgetbridge"""
    cursor.execute(f"""
        SELECT timestamp, duration, deep_sleep, light_sleep, rem_sleep, awake
        FROM {GB_TABLES['sleep']}
        ORDER BY timestamp
    """)
    
    count = 0
    for row in cursor.fetchall():
        try:
            timestamp = row['timestamp']
            timestamp_ms = timestamp if timestamp > 1e12 else int(timestamp * 1000)
            
            # Store sleep stages as separate readings
            stages = {
                'sleep_deep': row.get('deep_sleep'),
                'sleep_light': row.get('light_sleep'),
                'sleep_rem': row.get('rem_sleep'),
                'sleep_awake': row.get('awake')
            }
            
            for stage, value in stages.items():
                if value is not None:
                    reading = SensorReading(
                        device_id=device_id,
                        metric_type=stage,
                        value=float(value),
                        timestamp_ms=timestamp_ms,
                        source='gadgetbridge'
                    )
                    db.merge(reading)
                    count += 1
            
            if count % 1000 == 0:
                db.flush()
        except Exception as e:
            logger.warning(f"Failed to parse sleep row: {e}")
    
    return count


async def _parse_activity(cursor: sqlite3.Cursor, db: Session, device_id: str) -> int:
    """Parse MI_BAND_ACTIVITY_SAMPLE table for steps and activity"""
    # This table has: timestamp, steps, distance, calories, activity_kind, heart_rate
    cursor.execute(f"""
        SELECT timestamp, steps, heart_rate FROM {GB_TABLES['activity']}
        WHERE steps IS NOT NULL AND steps > 0
        ORDER BY timestamp
    """)
    
    count = 0
    for row in cursor.fetchall():
        try:
            timestamp = row['timestamp']
            timestamp_ms = timestamp if timestamp > 1e12 else int(timestamp * 1000)
            
            # Steps
            reading = SensorReading(
                device_id=device_id,
                metric_type='steps',
                value=float(row['steps']),
                timestamp_ms=timestamp_ms,
                source='gadgetbridge'
            )
            db.merge(reading)
            count += 1
            
            # Heart rate during activity
            if row.get('heart_rate'):
                hr_reading = SensorReading(
                    device_id=device_id,
                    metric_type='hr',
                    value=float(row['heart_rate']),
                    timestamp_ms=timestamp_ms,
                    source='gadgetbridge'
                )
                db.merge(hr_reading)
                count += 1
            
            if count % 1000 == 0:
                db.flush()
        except Exception as e:
            logger.warning(f"Failed to parse activity row: {e}")
    
    return count


async def create_gadgetbridge_import_record(db: Session, device_id: str, file_path: str) -> int:
    """Create import record for tracking"""
    import_record = GadgetbridgeImport(
        device_id=device_id,
        file_path=file_path,
        status='pending'
    )
    db.add(import_record)
    db.commit()
    return import_record.id


async def update_import_status(db: Session, import_id: int, status: str, row_count: int = 0, error: str = None):
    """Update import record status"""
    record = db.query(GadgetbridgeImport).filter(GadgetbridgeImport.id == import_id).first()
    if record:
        record.status = status
        record.row_count = row_count
        record.error_message = error
        if status in ['completed', 'failed']:
            record.completed_at = datetime.utcnow()
        db.commit()
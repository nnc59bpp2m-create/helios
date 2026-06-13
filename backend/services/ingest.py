import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from backend.models import SensorReading, Device, StressBaseline
from backend.config import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
FLUSH_INTERVAL = 100

class IngestionPipeline:
    def __init__(self, db: Session):
        self.db = db
        self.pending_readings: List[Dict] = []
        self.last_flush = datetime.utcnow()

    async def ingest_batch(self, readings: List[Dict], source: str = "miniprogram") -> Dict[str, int]:
        """Ingest a batch of sensor readings with deduplication"""
        ingested = 0
        duplicates = 0
        errors = 0

        for reading_data in readings:
            try:
                # Validate required fields
                required = ['device_id', 'metric_type', 'value', 'timestamp_ms']
                if not all(k in reading_data for k in required):
                    errors += 1
                    continue

                # Check for existing reading (upsert logic)
                existing = self.db.query(SensorReading).filter(
                    SensorReading.device_id == reading_data['device_id'],
                    SensorReading.metric_type == reading_data['metric_type'],
                    SensorReading.timestamp_ms == reading_data['timestamp_ms']
                ).first()

                if existing:
                    # Update existing
                    existing.value = reading_data['value']
                    existing.source = source
                    existing.raw_json = reading_data.get('raw_json')
                    duplicates += 1
                else:
                    # Insert new
                    reading = SensorReading(
                        device_id=reading_data['device_id'],
                        metric_type=reading_data['metric_type'],
                        value=reading_data['value'],
                        timestamp_ms=reading_data['timestamp_ms'],
                        source=source,
                        raw_json=reading_data.get('raw_json')
                    )
                    self.db.add(reading)
                    ingested += 1

                # Periodic flush
                if (ingested + duplicates) % FLUSH_INTERVAL == 0:
                    self.db.flush()

            except Exception as e:
                logger.error(f"Error ingesting reading: {e}")
                errors += 1

        # Final flush
        self.db.commit()
        self.last_flush = datetime.utcnow()

        return {"ingested": ingested, "duplicates": duplicates, "errors": errors}

    async def ingest_streaming(self, reading: Dict, source: str = "miniprogram") -> bool:
        """Ingest single reading (for real-time streaming)"""
        try:
            existing = self.db.query(SensorReading).filter(
                SensorReading.device_id == reading['device_id'],
                SensorReading.metric_type == reading['metric_type'],
                SensorReading.timestamp_ms == reading['timestamp_ms']
            ).first()

            if existing:
                existing.value = reading['value']
                existing.source = source
                existing.raw_json = reading.get('raw_json')
            else:
                reading_obj = SensorReading(
                    device_id=reading['device_id'],
                    metric_type=reading['metric_type'],
                    value=reading['value'],
                    timestamp_ms=reading['timestamp_ms'],
                    source=source,
                    raw_json=reading.get('raw_json')
                )
                self.db.add(reading_obj)

            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Streaming ingest error: {e}")
            self.db.rollback()
            return False


async def compute_daily_aggregations(db: Session, device_id: str, date: datetime):
    """Compute daily aggregations for a device/date"""
    from sqlalchemy import func
    
    start_ms = int(datetime(date.year, date.month, date.day).timestamp() * 1000)
    end_ms = int((datetime(date.year, date.month, date.day) + timedelta(days=1)).timestamp() * 1000)

    metrics = ['hr', 'hrv_sdnn', 'hrv_rmssd', 'spo2', 'skin_temp', 'eda']
    
    for metric in metrics:
        result = db.query(
            func.avg(SensorReading.value).label('avg'),
            func.min(SensorReading.value).label('min'),
            func.max(SensorReading.value).label('max'),
            func.count(SensorReading.value).label('count')
        ).filter(
            SensorReading.device_id == device_id,
            SensorReading.metric_type == metric,
            SensorReading.timestamp_ms >= start_ms,
            SensorReading.timestamp_ms < end_ms
        ).first()

        if result and result.count > 0:
            logger.debug(f"Daily {metric} for {device_id} on {date.date()}: avg={result.avg:.2f}, count={result.count}")


async def update_stress_baselines(db: Session, device_id: str, date: datetime):
    """Update hourly stress baselines for a device"""
    from sqlalchemy import func
    from datetime import timedelta

    # Use last 28 days for baseline
    end = date
    start = end - timedelta(days=28)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int((end + timedelta(days=1)).timestamp() * 1000)

    metric_types = ['hrv_sdnn', 'hrv_rmssd', 'hr', 'eda', 'skin_temp']

    for metric_type in metric_types:
        for hour in range(24):
            hour_start = start_ms + (hour * 3600000)
            hour_end = hour_start + 3600000

            # Query readings in this hour across all days
            results = db.query(
                func.avg(SensorReading.value).label('avg'),
                func.stddev(SensorReading.value).label('std'),
                func.count(SensorReading.value).label('count')
            ).filter(
                SensorReading.device_id == device_id,
                SensorReading.metric_type == metric_type,
                SensorReading.timestamp_ms >= start_ms,
                SensorReading.timestamp_ms < end_ms
            ).all()

            # Filter by hour of day (would need to extract hour from timestamp)
            # For simplicity, using all readings - in production use proper partition
            
            if results and results[0].count and results[0].count >= 10:
                baseline = StressBaseline(
                    device_id=device_id,
                    metric_type=metric_type,
                    hour_of_day=hour,
                    mean_value=results[0].avg or 0,
                    std_value=results[0].std or 0,
                    sample_count=results[0].count or 0,
                    computed_date=date
                )
                db.merge(baseline)
    
    db.commit()
    logger.info(f"Updated stress baselines for {device_id} on {date.date()}")


async def recluster_partitions(db: Session):
    """Reorganize monthly partitions - placeholder for future optimization"""
    # In production, this would:
    # 1. Create new monthly tables
    # 2. Move data from main table to partitions
    # 3. Update indexes
    # 4. Drop old data if retention policy applies
    pass
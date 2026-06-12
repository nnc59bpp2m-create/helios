from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

from backend.main import get_db
from backend.models import SensorReading, Device

router = APIRouter()


class SensorReadingIn(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    metric_type: str = Field(..., pattern=r"^(hr|hrv_sdnn|hrv_rmssd|spo2|skin_temp|eda|accel_x|accel_y|accel_z|gyro_x|gyro_y|gyro_z)$")
    value: float
    timestamp_ms: int
    source: str = Field(..., pattern=r"^(miniprogram|huami|gadgetbridge|ble_direct)$")
    raw_json: Optional[dict] = None


class SensorBatchIn(BaseModel):
    readings: List[SensorReadingIn]


class IngestResponse(BaseModel):
    ingested: int
    duplicates: int
    errors: List[str]
    ingestion_id: str


@router.post("/telemetry", response_model=IngestResponse)
async def ingest_telemetry(
    payload: SensorBatchIn,
    db: Session = Depends(get_db)
):
    ingestion_id = str(uuid.uuid4())[:8]
    ingested = 0
    duplicates = 0
    errors = []

    for reading in payload.readings:
        try:
            # Check for existing device
            device = db.query(Device).filter(Device.device_id == reading.device_id).first()
            if not device:
                device = Device(
                    device_id=reading.device_id,
                    device_type="ring" if "ring" in reading.device_id.lower() else "strap"
                )
                db.add(device)
                db.flush()

            # Upsert reading (check for duplicate)
            existing = db.query(SensorReading).filter(
                SensorReading.device_id == reading.device_id,
                SensorReading.metric_type == reading.metric_type,
                SensorReading.timestamp_ms == reading.timestamp_ms
            ).first()

            if existing:
                # Update existing
                existing.value = reading.value
                existing.source = reading.source
                existing.raw_json = reading.raw_json
                duplicates += 1
            else:
                # Insert new
                new_reading = SensorReading(
                    device_id=reading.device_id,
                    metric_type=reading.metric_type,
                    value=reading.value,
                    timestamp_ms=reading.timestamp_ms,
                    source=reading.source,
                    raw_json=reading.raw_json
                )
                db.add(new_reading)
                ingested += 1

        except Exception as e:
            errors.append(f"Reading {reading.metric_type}@{reading.timestamp_ms}: {str(e)}")

    db.commit()
    return IngestResponse(
        ingested=ingested,
        duplicates=duplicates,
        errors=errors,
        ingestion_id=ingestion_id
    )


@router.post("/batch", response_model=IngestResponse)
async def ingest_batch(
    payload: SensorBatchIn,
    db: Session = Depends(get_db)
):
    """Alias for /telemetry with batch semantics"""
    return await ingest_telemetry(payload, db)
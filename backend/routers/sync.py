from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from backend.main import get_db
from backend.models import SyncState, SensorReading, Device, GadgetbridgeImport

router = APIRouter()


class SyncStatusResponse(BaseModel):
    source: str
    device_id: str
    last_sync_at: Optional[datetime]
    last_success_at: Optional[datetime]
    error_count: int
    last_error: Optional[str]
    is_syncing: bool


class HistoricalSyncRequest(BaseModel):
    source: str = "huami"  # huami, gadgetbridge
    device_id: str
    days: int = 90
    xiaomi_token: Optional[str] = None  # For Huami


@router.post("/historical")
async def start_historical_sync(
    request: HistoricalSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start historical data backfill from cloud source"""
    sync_state = db.query(SyncState).filter(
        SyncState.source == request.source,
        SyncState.device_id == request.device_id
    ).first()

    if not sync_state:
        sync_state = SyncState(
            source=request.source,
            device_id=request.device_id
        )
        db.add(sync_state)
        db.commit()

    # Check if already syncing
    if sync_state.error_count < 0:  # Using negative as "in progress" flag
        raise HTTPException(409, "Sync already in progress")

    # Mark as in progress
    sync_state.error_count = -1
    db.commit()

    # Start background task
    if request.source == "huami":
        background_tasks.add_task(_huami_backfill_task, request.device_id, request.days, request.xiaomi_token)
    elif request.source == "gadgetbridge":
        background_tasks.add_task(_gadgetbridge_import_task, request.device_id)
    else:
        sync_state.error_count = 0
        sync_state.last_error = f"Unknown source: {request.source}"
        db.commit()
        raise HTTPException(400, f"Unsupported source: {request.source}")

    return {"status": "started", "sync_id": sync_state.id}


@router.get("/status", response_model=List[SyncStatusResponse])
async def get_sync_status(
    device_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(SyncState)
    if device_id:
        query = query.filter(SyncState.device_id == device_id)
    states = query.all()

    return [SyncStatusResponse(
        source=s.source,
        device_id=s.device_id,
        last_sync_at=s.last_sync_at,
        last_success_at=s.last_success_at,
        error_count=max(0, s.error_count),
        last_error=s.last_error,
        is_syncing=s.error_count < 0
    ) for s in states]


@router.post("/gadgetbridge")
async def import_gadgetbridge(
    device_id: str = Form(...),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Import Gadgetbridge SQLite database export"""
    if not file.filename.endswith((".db", ".sqlite", ".sqlite3")):
        raise HTTPException(400, "File must be a SQLite database")

    # Save uploaded file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Create import record
    import_record = GadgetbridgeImport(
        device_id=device_id,
        file_path=tmp_path,
        status="pending",
        row_count=0
    )
    db.add(import_record)
    db.commit()

    # Process in background
    background_tasks.add_task(_process_gadgetbridge_import, import_record.id, tmp_path, device_id)

    return {"status": "accepted", "import_id": import_record.id}


@router.get("/gadgetbridge/history")
async def get_gadgetbridge_history(
    device_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(GadgetbridgeImport)
    if device_id:
        query = query.filter(GadgetbridgeImport.device_id == device_id)
    imports = query.order_by(GadgetbridgeImport.created_at.desc()).limit(20).all()

    return [{
        "id": i.id,
        "device_id": i.device_id,
        "status": i.status,
        "row_count": i.row_count,
        "error": i.error_message,
        "created_at": i.created_at,
        "completed_at": i.completed_at
    } for i in imports]


# Placeholder background tasks - will be implemented in services
async def _huami_backfill_task(device_id: str, days: int, xiaomi_token: Optional[str]):
    from backend.services.huami_client import backfill_historical
    from backend.main import SessionLocal
    db = SessionLocal()
    try:
        await backfill_historical(db, device_id, days, xiaomi_token)
    finally:
        db.close()


async def _gadgetbridge_import_task(device_id: str):
    pass  # Handled by upload endpoint


async def _process_gadgetbridge_import(import_id: int, file_path: str, device_id: str):
    from backend.services.gadgetbridge import parse_gadgetbridge_db
    from backend.main import SessionLocal
    import os

    db = SessionLocal()
    try:
        import_record = db.query(GadgetbridgeImport).filter(GadgetbridgeImport.id == import_id).first()
        if not import_record:
            return

        import_record.status = "processing"
        db.commit()

        count = await parse_gadgetbridge_db(db, file_path, device_id)

        import_record.status = "completed"
        import_record.row_count = count
        import_record.completed_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        import_record = db.query(GadgetbridgeImport).filter(GadgetbridgeImport.id == import_id).first()
        if import_record:
            import_record.status = "failed"
            import_record.error_message = str(e)
            db.commit()
    finally:
        db.close()
        if os.path.exists(file_path):
            os.unlink(file_path)
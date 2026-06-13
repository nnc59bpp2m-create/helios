from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, Index,
    ForeignKey, Boolean, BigInteger, JSON, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from datetime import datetime
from typing import Optional
import json

Base = declarative_base()


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("devices.device_id"), nullable=False, index=True)
    metric_type = Column(String(32), nullable=False, index=True)  # hr, hrv_sdnn, hrv_rmssd, spo2, skin_temp, eda, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z
    value = Column(Float, nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False, index=True)
    source = Column(String(32), nullable=False)  # miniprogram, huami, gadgetbridge, ble_direct
    raw_json = Column(SQLiteJSON, nullable=True)

    __table_args__ = (
        Index("idx_sensor_device_metric_time", "device_id", "metric_type", "timestamp_ms"),
        Index("idx_sensor_time", "timestamp_ms"),
    )


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=True)
    device_type = Column(String(32), nullable=True)  # ring, strap
    mac_address = Column(String(32), nullable=True)
    firmware_version = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    readings = relationship("SensorReading", backref="device", lazy="dynamic")


class SyncState(Base):
    __tablename__ = "sync_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(32), nullable=False, index=True)  # huami, gadgetbridge, miniprogram
    device_id = Column(String(64), nullable=False, index=True)
    cursor = Column(Text, nullable=True)  # syncToken, deltaLink, last_timestamp
    last_sync_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "device_id", name="uq_sync_source_device"),
    )


class CalendarAccount(Base):
    __tablename__ = "calendar_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False)  # google, outlook, ios
    account_email = Column(String(256), nullable=False)
    display_name = Column(String(256), nullable=True)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    sync_token = Column(Text, nullable=True)  # Google syncToken, Graph deltaLink
    is_active = Column(Boolean, default=True)
    selected_calendars = Column(SQLiteJSON, nullable=True)  # list of calendar IDs to sync
    excluded_categories = Column(SQLiteJSON, nullable=True)  # categories to exclude from correlation
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "account_email", name="uq_calendar_provider_email"),
    )


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("calendar_accounts.id"), nullable=False)
    ical_uid = Column(String(256), nullable=False, index=True)  # unique across providers
    provider = Column(String(32), nullable=False, index=True)
    title = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    organizer_email = Column(String(256), nullable=True, index=True)
    attendee_emails = Column(SQLiteJSON, nullable=True)  # list of emails
    start_ms = Column(BigInteger, nullable=False, index=True)
    end_ms = Column(BigInteger, nullable=False, index=True)
    location = Column(String(512), nullable=True)
    recurrence_rule = Column(Text, nullable=True)
    recurrence_id = Column(BigInteger, nullable=True)  # for specific instances
    category = Column(String(32), nullable=True, index=True)  # 1:1, team, all-hands, external, focus, personal
    is_all_day = Column(Boolean, default=False)
    raw_data = Column(SQLiteJSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_cal_event_time", "start_ms", "end_ms"),
        Index("idx_cal_event_organizer", "organizer_email"),
        UniqueConstraint("account_id", "ical_uid", name="uq_cal_event_account_uid"),
    )

    account = relationship("CalendarAccount", backref="events")
    stress_scores = relationship("EventStressScore", backref="event", lazy="dynamic")


class EventStressScore(Base):
    __tablename__ = "event_stress_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("calendar_events.id"), nullable=False, index=True)
    score = Column(Float, nullable=True)  # 0-100, null if no sensor data
    eda_component = Column(Float, nullable=True)
    hrv_component = Column(Float, nullable=True)
    hr_component = Column(Float, nullable=True)
    temp_component = Column(Float, nullable=True)
    baseline_hrv = Column(Float, nullable=True)
    baseline_hr = Column(Float, nullable=True)
    baseline_eda = Column(Float, nullable=True)
    baseline_temp = Column(Float, nullable=True)
    sensor_data_points = Column(Integer, default=0)
    computed_at = Column(DateTime, default=datetime.utcnow)
    recomputed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_stress_score_score", "score"),
        Index("idx_stress_score_computed", "computed_at"),
    )


class StressBaseline(Base):
    __tablename__ = "stress_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, index=True)
    metric_type = Column(String(32), nullable=False, index=True)  # hrv_sdnn, hrv_rmssd, hr_resting, eda, skin_temp
    hour_of_day = Column(Integer, nullable=False, index=True)  # 0-23
    mean_value = Column(Float, nullable=False)
    std_value = Column(Float, nullable=False)
    sample_count = Column(Integer, default=0)
    computed_date = Column(DateTime, nullable=False, index=True)  # date this baseline was computed for
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("device_id", "metric_type", "hour_of_day", "computed_date", name="uq_baseline_device_metric_hour_date"),
    )


class CorrelationExport(Base):
    __tablename__ = "correlation_exports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_format = Column(String(16), nullable=False)  # csv, json
    date_start = Column(BigInteger, nullable=False)
    date_end = Column(BigInteger, nullable=False)
    file_path = Column(String(512), nullable=True)
    status = Column(String(16), default="pending")  # pending, completed, failed
    row_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class GadgetbridgeImport(Base):
    __tablename__ = "gadgetbridge_imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, index=True)
    file_path = Column(String(512), nullable=True)
    status = Column(String(16), default="pending")  # pending, processing, completed, failed
    row_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# Database connection
def get_engine(database_url: str):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )


def get_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db(engine):
    Base.metadata.create_all(engine)
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime, timedelta
from urllib.parse import urlencode

from backend.models import SyncState
from backend.config import settings

logger = logging.getLogger(__name__)

HUAMI_AUTH_URL = "https://auth.huami.com"
HUAMI_API_URL = "https://api-user.huami.com"
# Alternative: api-watch.huami.com, api-mifit.huami.com

class HuamiClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def exchange_token(self, xiaomi_token: str) -> Dict[str, Any]:
        """Exchange Xiaomi token for Huami access token"""
        url = f"{HUAMI_AUTH_URL}/oauth2/exchange_access_token_by_xiaomi_token"
        
        data = {
            "app_id": settings.huami_app_id,
            "app_secret": settings.huami_app_secret,
            "xiaomi_token": xiaomi_token,
            "grant_type": "xiaomi_token"
        }
        
        response = await self.client.post(url, data=data)
        response.raise_for_status()
        
        result = response.json()
        self.access_token = result.get("access_token")
        self.refresh_token = result.get("refresh_token")
        expires_in = result.get("expires_in", 1800)
        self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        logger.info("Huami token exchange successful")
        return result

    async def refresh_access_token(self) -> bool:
        """Refresh expired access token"""
        if not self.refresh_token:
            return False
            
        url = f"{HUAMI_AUTH_URL}/oauth2/refresh_token"
        data = {
            "app_id": settings.huami_app_id,
            "app_secret": settings.huami_app_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            response = await self.client.post(url, data=data)
            response.raise_for_status()
            
            result = response.json()
            self.access_token = result.get("access_token")
            self.refresh_token = result.get("refresh_token", self.refresh_token)
            expires_in = result.get("expires_in", 1800)
            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            logger.info("Huami token refreshed")
            return True
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return False

    async def _ensure_valid_token(self):
        """Ensure access token is valid, refresh if needed"""
        if not self.access_token or (self.token_expires_at and datetime.utcnow() >= self.token_expires_at - timedelta(minutes=5)):
            await self.refresh_access_token()

    async def _request(self, method: str, endpoint: str, params: Dict = None, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to Huami API"""
        await self._ensure_valid_token()
        
        url = f"{HUAMI_API_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            **kwargs.pop("headers", {})
        }
        
        response = await self.client.request(method, url, headers=headers, params=params, **kwargs)
        
        if response.status_code == 401:
            # Token expired, try refresh once
            if await self.refresh_access_token():
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await self.client.request(method, url, headers=headers, params=params, **kwargs)
            else:
                raise Exception("Token expired and refresh failed")
        
        response.raise_for_status()
        return response.json()

    # Core Health Data APIs
    
    async def get_profile(self) -> Dict[str, Any]:
        """Get user profile"""
        return await self._request("GET", "/users/-/profile")

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Get user devices"""
        result = await self._request("GET", "/users/-/devices")
        return result.get("devices", [])

    async def get_heart_rates(
        self, 
        start_time: int, 
        end_time: int,
        limit: int = 1000
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get heart rate data (paginated)"""
        params = {
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit
        }
        
        while True:
            result = await self._request("GET", "/users/-/heartrates", params=params)
            data = result.get("data", [])
            
            for item in data:
                yield item
            
            # Check for pagination
            next_token = result.get("next_token")
            if not next_token or len(data) < limit:
                break
            params["next_token"] = next_token

    async def get_sleep_data(
        self,
        start_time: int,
        end_time: int,
        limit: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get sleep data (paginated)"""
        params = {
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit
        }
        
        while True:
            result = await self._request("GET", "/users/-/sleep", params=params)
            data = result.get("data", [])
            
            for item in data:
                yield item
            
            next_token = result.get("next_token")
            if not next_token or len(data) < limit:
                break
            params["next_token"] = next_token

    async def get_activities(
        self,
        start_time: int,
        end_time: int,
        limit: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get activity/workout data"""
        params = {
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit
        }
        
        while True:
            result = await self._request("GET", "/users/-/activities", params=params)
            data = result.get("data", [])
            
            for item in data:
                yield item
            
            next_token = result.get("next_token")
            if not next_token or len(data) < limit:
                break
            params["next_token"] = next_token

    async def get_raw_sensor_data(
        self,
        start_time: int,
        end_time: int,
        sensor_type: str = "all",
        limit: int = 1000
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get raw sensor data (EDA, temperature, etc.)"""
        params = {
            "start_time": start_time,
            "end_time": end_time,
            "sensor_type": sensor_type,
            "limit": limit
        }
        
        while True:
            result = await self._request("GET", "/users/-/sensor", params=params)
            data = result.get("data", [])
            
            for item in data:
                yield item
            
            next_token = result.get("next_token")
            if not next_token or len(data) < limit:
                break
            params["next_token"] = next_token

    async def get_pai_summary(self, start_time: int, end_time: int) -> Dict[str, Any]:
        """Get PAI (Personal Activity Intelligence) summary"""
        params = {"start_time": start_time, "end_time": end_time}
        return await self._request("GET", "/users/-/paisummary", params=params)

    async def get_vo2max(self) -> Dict[str, Any]:
        """Get VO2 Max data"""
        return await self._request("GET", "/users/-/paivo2max")

    async def get_ecg_data(self, start_time: int, end_time: int) -> AsyncGenerator[Dict[str, Any], None]:
        """Get ECG data"""
        params = {"start_time": start_time, "end_time": end_time, "limit": 100}
        
        while True:
            result = await self._request("GET", "/users/-/ecg", params=params)
            data = result.get("data", [])
            
            for item in data:
                yield item
            
            next_token = result.get("next_token")
            if not next_token or len(data) < 100:
                break
            params["next_token"] = next_token

    async def close(self):
        await self.client.aclose()


# Sync orchestrator
async def backfill_historical(
    db,
    device_id: str,
    days: int = 90,
    xiaomi_token: Optional[str] = None
):
    """Backfill historical data from Huami API"""
    from backend.models import SensorReading, Device, SyncState
    from sqlalchemy.orm import Session
    
    client = HuamiClient()
    
    try:
        if xiaomi_token:
            await client.exchange_token(xiaomi_token)
        else:
            # TODO: Load stored tokens from SyncState
            pass
        
        # Get or create device
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            device = Device(device_id=device_id, device_type="ring")
            db.add(device)
            db.flush()
        
        # Get sync state
        sync_state = db.query(SyncState).filter(
            SyncState.source == "huami",
            SyncState.device_id == device_id
        ).first()
        
        if not sync_state:
            sync_state = SyncState(source="huami", device_id=device_id)
            db.add(sync_state)
        
        end_time = int(datetime.utcnow().timestamp() * 1000)
        start_time = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
        
        total_ingested = 0
        
        # Heart Rate
        logger.info(f"Backfilling heart rate for {device_id}")
        async for hr in client.get_heart_rates(start_time // 1000, end_time // 1000):
            reading = SensorReading(
                device_id=device_id,
                metric_type="hr",
                value=hr.get("value", hr.get("heart_rate", 0)),
                timestamp_ms=hr.get("timestamp", hr.get("time", 0)) * 1000,
                source="huami",
                raw_json=hr
            )
            db.merge(reading)
            total_ingested += 1
            
            # Flush periodically
            if total_ingested % 1000 == 0:
                db.commit()
                logger.info(f"  Ingested {total_ingested} HR readings...")
        
        # Sleep
        logger.info(f"Backfilling sleep for {device_id}")
        async for sleep in client.get_sleep_data(start_time // 1000, end_time // 1000):
            # Store sleep stages
            stages = sleep.get("stages", [])
            for stage in stages:
                reading = SensorReading(
                    device_id=device_id,
                    metric_type="sleep_stage",
                    value=stage.get("stage", 0),
                    timestamp_ms=stage.get("start_time", 0) * 1000,
                    source="huami",
                    raw_json=stage
                )
                db.merge(reading)
                total_ingested += 1
        
        # Activities
        logger.info(f"Backfilling activities for {device_id}")
        async for activity in client.get_activities(start_time // 1000, end_time // 1000):
            reading = SensorReading(
                device_id=device_id,
                metric_type="activity",
                value=1,
                timestamp_ms=activity.get("start_time", 0) * 1000,
                source="huami",
                raw_json=activity
            )
            db.merge(reading)
            total_ingested += 1
        
        # Raw sensors (EDA, temperature, etc.)
        logger.info(f"Backfilling raw sensors for {device_id}")
        async for sensor in client.get_raw_sensor_data(start_time // 1000, end_time // 1000):
            sensor_type = sensor.get("type", "unknown")
            metric_map = {
                "eda": "eda",
                "temperature": "skin_temp",
                "spo2": "spo2"
            }
            metric = metric_map.get(sensor_type)
            if metric:
                reading = SensorReading(
                    device_id=device_id,
                    metric_type=metric,
                    value=sensor.get("value", 0),
                    timestamp_ms=sensor.get("timestamp", 0) * 1000,
                    source="huami",
                    raw_json=sensor
                )
                db.merge(reading)
                total_ingested += 1
        
        # Update sync state
        sync_state.last_sync_at = datetime.utcnow()
        sync_state.last_success_at = datetime.utcnow()
        sync_state.error_count = 0
        sync_state.last_error = None
        
        db.commit()
        logger.info(f"Backfill complete for {device_id}: {total_ingested} readings")
        
        return total_ingested
        
    except Exception as e:
        logger.error(f"Backfill failed for {device_id}: {e}")
        sync_state.error_count += 1
        sync_state.last_error = str(e)
        sync_state.last_sync_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        await client.close()


# Incremental sync (run periodically)
async def incremental_sync(db, device_id: str):
    """Sync only new data since last sync"""
    from backend.models import SyncState
    
    sync_state = db.query(SyncState).filter(
        SyncState.source == "huami",
        SyncState.device_id == device_id
    ).first()
    
    if not sync_state or not sync_state.last_success_at:
        # Full backfill needed
        return await backfill_historical(db, device_id, days=90)
    
    # Incremental from last success
    days_since = (datetime.utcnow() - sync_state.last_success_at).days + 1
    return await backfill_historical(db, device_id, days=days_since)
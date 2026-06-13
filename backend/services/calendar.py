import asyncio
import logging
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import base64
import json

from backend.models import CalendarAccount, CalendarEvent, CalendarSyncState
from backend.config import settings

logger = logging.getLogger(__name__)

class CalendarProvider:
    """Base class for calendar providers"""
    
    async def list_events(self, since: Optional[datetime] = None) -> List[Dict]:
        raise NotImplementedError
    
    async def get_event(self, uid: str) -> Optional[Dict]:
        raise NotImplementedError
    
    async def watch_changes(self, callback):
        raise NotImplementedError


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self, account: CalendarAccount, db: Session):
        self.account = account
        self.db = db
        self.base_url = "https://www.googleapis.com/calendar/v3"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def _get_headers(self) -> Dict[str, str]:
        # Decrypt token (placeholder - implement proper encryption)
        access_token = base64.b64decode(self.account.access_token_encrypted).decode()
        return {"Authorization": f"Bearer {access_token}"}
    
    async def _refresh_token(self) -> bool:
        if not self.account.refresh_token_encrypted:
            return False
        
        refresh_token = base64.b64decode(self.account.refresh_token_encrypted).decode()
        
        data = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            response = await self.client.post(
                "https://oauth2.googleapis.com/token",
                data=data
            )
            response.raise_for_status()
            tokens = response.json()
            
            self.account.access_token_encrypted = base64.b64encode(tokens["access_token"].encode()).decode()
            if "refresh_token" in tokens:
                self.account.refresh_token_encrypted = base64.b64encode(tokens["refresh_token"].encode()).decode()
            self.account.token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Google token refresh failed: {e}")
            return False
    
    async def list_events(self, since: Optional[datetime] = None) -> List[Dict]:
        headers = await self._get_headers()
        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 2500
        }
        
        if since:
            params["timeMin"] = since.isoformat() + "Z"
        if self.account.sync_token:
            params["syncToken"] = self.account.sync_token
        
        all_events = []
        page_token = None
        
        while True:
            if page_token:
                params["pageToken"] = page_token
            
            try:
                response = await self.client.get(
                    f"{self.base_url}/calendars/primary/events",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 401:
                    await self._refresh_token()
                    headers = await self._get_headers()
                    response = await self.client.get(
                        f"{self.base_url}/calendars/primary/events",
                        headers=headers,
                        params=params
                    )
                
                response.raise_for_status()
                data = response.json()
                
                for item in data.get("items", []):
                    if item.get("status") != "cancelled":
                        all_events.append(self._normalize_event(item))
                
                page_token = data.get("nextPageToken")
                if not page_token:
                    # Save sync token for next incremental sync
                    if "nextSyncToken" in data:
                        self.account.sync_token = data["nextSyncToken"]
                        self.db.commit()
                    break
                    
            except Exception as e:
                logger.error(f"Google Calendar list_events error: {e}")
                break
        
        return all_events
    
    def _normalize_event(self, item: Dict) -> Dict:
        start = item.get("start", {})
        end = item.get("end", {})
        
        start_ms = int(datetime.fromisoformat(start.get("dateTime", start.get("date")).replace('Z', '+00:00')).timestamp() * 1000)
        end_ms = int(datetime.fromisoformat(end.get("dateTime", end.get("date")).replace('Z', '+00:00')).timestamp() * 1000)
        
        attendees = []
        for a in item.get("attendees", []):
            if a.get("email") and not a.get("self"):
                attendees.append(a["email"])
        
        return {
            "ical_uid": item["id"],
            "title": item.get("summary"),
            "description": item.get("description"),
            "organizer_email": item.get("organizer", {}).get("email"),
            "attendee_emails": attendees,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "location": item.get("location"),
            "recurrence_rule": item.get("recurrence", [None])[0] if item.get("recurrence") else None,
            "is_all_day": "date" in start,
            "raw_data": item
        }
    
    async def get_event(self, uid: str) -> Optional[Dict]:
        headers = await self._get_headers()
        try:
            response = await self.client.get(
                f"{self.base_url}/calendars/primary/events/{uid}",
                headers=headers
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self._normalize_event(response.json())
        except Exception:
            return None


class OutlookCalendarProvider(CalendarProvider):
    def __init__(self, account: CalendarAccount, db: Session):
        self.account = account
        self.db = db
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def _get_headers(self) -> Dict[str, str]:
        access_token = base64.b64decode(self.account.access_token_encrypted).decode()
        return {"Authorization": f"Bearer {access_token}"}
    
    async def _refresh_token(self) -> bool:
        # Device code flow refresh handled separately
        # For regular OAuth, use refresh_token
        if not self.account.refresh_token_encrypted:
            return False
        
        refresh_token = base64.b64decode(self.account.refresh_token_encrypted).decode()
        
        data = {
            "client_id": settings.ms_graph_client_id,
            "client_secret": settings.ms_graph_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": settings.ms_graph_scopes
        }
        
        try:
            response = await self.client.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data=data
            )
            response.raise_for_status()
            tokens = response.json()
            
            self.account.access_token_encrypted = base64.b64encode(tokens["access_token"].encode()).decode()
            if "refresh_token" in tokens:
                self.account.refresh_token_encrypted = base64.b64encode(tokens["refresh_token"].encode()).decode()
            self.account.token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Outlook token refresh failed: {e}")
            return False
    
    async def list_events(self, since: Optional[datetime] = None) -> List[Dict]:
        headers = await self._get_headers()
        params = {
            "$orderby": "start/dateTime",
            "$top": 1000,
            "$select": "id,subject,bodyPreview,organizer,attendees,start,end,location,recurrence,isAllDay"
        }
        
        if since:
            params["$filter"] = f"end/dateTime ge '{since.isoformat()}Z'"
        
        if self.account.sync_token:
            params["$deltaToken"] = self.account.sync_token
        
        all_events = []
        next_url = f"{self.base_url}/me/events"
        next_params = params
        
        while next_url:
            try:
                response = await self.client.get(next_url, headers=headers, params=next_params)
                
                if response.status_code == 401:
                    await self._refresh_token()
                    headers = await self._get_headers()
                    response = await self.client.get(next_url, headers=headers, params=next_params)
                
                response.raise_for_status()
                data = response.json()
                
                for item in data.get("value", []):
                    if item.get("@removed"):
                        continue
                    all_events.append(self._normalize_event(item))
                
                next_url = data.get("@odata.nextLink")
                next_params = None  # Params included in nextLink
                
                if "@odata.deltaLink" in data:
                    self.account.sync_token = data["@odata.deltaLink"]
                    self.db.commit()
                    
            except Exception as e:
                logger.error(f"Outlook Calendar list_events error: {e}")
                break
        
        return all_events
    
    def _normalize_event(self, item: Dict) -> Dict:
        start = item.get("start", {})
        end = item.get("end", {})
        
        start_ms = int(datetime.fromisoformat(start.get("dateTime", "").replace('Z', '+00:00')).timestamp() * 1000)
        end_ms = int(datetime.fromisoformat(end.get("dateTime", "").replace('Z', '+00:00')).timestamp() * 1000)
        
        attendees = []
        for a in item.get("attendees", []):
            if a.get("emailAddress", {}).get("address") and not a.get("emailAddress", {}).get("address").endswith("#EXT#"):
                attendees.append(a["emailAddress"]["address"])
        
        organizer = item.get("organizer", {}).get("emailAddress", {}).get("address")
        
        return {
            "ical_uid": item["id"],
            "title": item.get("subject"),
            "description": item.get("bodyPreview"),
            "organizer_email": organizer,
            "attendee_emails": attendees,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "location": item.get("location", {}).get("displayName"),
            "recurrence_rule": json.dumps(item.get("recurrence", {}).get("pattern", {})) if item.get("recurrence") else None,
            "is_all_day": item.get("isAllDay", False),
            "raw_data": item
        }
    
    async def get_event(self, uid: str) -> Optional[Dict]:
        headers = await self._get_headers()
        try:
            response = await self.client.get(
                f"{self.base_url}/me/events/{uid}",
                headers=headers
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self._normalize_event(response.json())
        except Exception:
            return None


class IOSCalendarProvider(CalendarProvider):
    """iOS EventKit provider - communicates via Capacitor bridge"""
    
    def __init__(self, account: CalendarAccount, db: Session):
        self.account = account
        self.db = db
        # No direct API - uses Capacitor plugin on device
        # This provider receives events pushed from mobile app
    
    async def list_events(self, since: Optional[datetime] = None) -> List[Dict]:
        # Events are synced from mobile app via API
        # This is a placeholder - real sync happens from mobile
        query = self.db.query(CalendarEvent).filter(
            CalendarEvent.account_id == self.account.id
        )
        if since:
            query = query.filter(CalendarEvent.start_ms >= int(since.timestamp() * 1000))
        
        events = query.all()
        return [
            {
                "ical_uid": e.ical_uid,
                "title": e.title,
                "description": e.description,
                "organizer_email": e.organizer_email,
                "attendee_emails": e.attendee_emails,
                "start_ms": e.start_ms,
                "end_ms": e.end_ms,
                "location": e.location,
                "recurrence_rule": e.recurrence_rule,
                "is_all_day": e.is_all_day
            }
            for e in events
        ]
    
    async def get_event(self, uid: str) -> Optional[Dict]:
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.account_id == self.account.id,
            CalendarEvent.ical_uid == uid
        ).first()
        
        if not event:
            return None
            
        return {
            "ical_uid": event.ical_uid,
            "title": event.title,
            "description": event.description,
            "organizer_email": event.organizer_email,
            "attendee_emails": event.attendee_emails,
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "location": event.location,
            "recurrence_rule": event.recurrence_rule,
            "is_all_day": event.is_all_day
        }


def categorize_event(event: Dict) -> str:
    """Categorize event based on metadata"""
    title = (event.get("title") or "").lower()
    attendees = event.get("attendee_emails", [])
    organizer = event.get("organizer_email", "")
    
    # Focus time
    if any(kw in title for kw in ["focus", "deep work", "block", "no meeting"]):
        return "focus"
    
    # 1:1
    if len(attendees) == 1 and organizer:
        return "1:1"
    
    # All-hands / large meetings
    if len(attendees) >= 10 or any(kw in title for kw in ["all hands", "all-hands", "town hall", "standup", "stand-up"]):
        return "all-hands"
    
    # Team meeting
    if len(attendees) >= 3:
        return "team"
    
    # External
    if organizer and attendees:
        org_domain = organizer.split("@")[-1] if "@" in organizer else ""
        attendee_domains = set(a.split("@")[-1] for a in attendees if "@" in a)
        if org_domain and not any(d == org_domain for d in attendee_domains):
            return "external"
    
    # Personal
    if any(kw in title for kw in ["personal", "doctor", "dentist", "therapy", "gym", "workout", "lunch", "break", "appointment"]):
        return "personal"
    
    return "team"


async def sync_calendar_account(db: Session, account_id: int) -> Dict[str, Any]:
    """Sync a single calendar account"""
    from backend.models import CalendarAccount, CalendarEvent
    
    account = db.query(CalendarAccount).filter(CalendarAccount.id == account_id).first()
    if not account or not account.is_active:
        return {"events_synced": 0, "events_updated": 0, "events_deleted": 0, "errors": ["Account not found or inactive"]}
    
    # Select provider
    provider_map = {
        "google": GoogleCalendarProvider,
        "outlook": OutlookCalendarProvider,
        "ios": IOSCalendarProvider
    }
    
    provider_class = provider_map.get(account.provider)
    if not provider_class:
        return {"events_synced": 0, "events_updated": 0, "events_deleted": 0, "errors": [f"Unknown provider: {account.provider}"]}
    
    provider = provider_class(account, db)
    errors = []
    synced = 0
    updated = 0
    
    try:
        # Get events since last sync
        since = None
        if account.sync_token:
            # For incremental sync, we use the sync token directly
            since = None
        elif account.last_sync_at:
            since = account.last_sync_at - timedelta(days=1)  # Overlap by 1 day
        
        events = await provider.list_events(since)
        
        for event_data in events:
            # Categorize
            event_data["category"] = categorize_event(event_data)
            
            # Check excluded categories
            excluded = account.excluded_categories or []
            if event_data["category"] in excluded:
                continue
            
            # Upsert event
            existing = db.query(CalendarEvent).filter(
                CalendarEvent.account_id == account.id,
                CalendarEvent.ical_uid == event_data["ical_uid"]
            ).first()
            
            if existing:
                # Update
                for key, value in event_data.items():
                    if key != "raw_data":
                        setattr(existing, key, value)
                existing.raw_data = event_data.get("raw_data")
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                # Create
                new_event = CalendarEvent(
                    account_id=account.id,
                    ical_uid=event_data["ical_uid"],
                    provider=account.provider,
                    title=event_data["title"],
                    description=event_data.get("description"),
                    organizer_email=event_data.get("organizer_email"),
                    attendee_emails=event_data.get("attendee_emails"),
                    start_ms=event_data["start_ms"],
                    end_ms=event_data["end_ms"],
                    location=event_data.get("location"),
                    recurrence_rule=event_data.get("recurrence_rule"),
                    category=event_data["category"],
                    is_all_day=event_data.get("is_all_day", False),
                    raw_data=event_data.get("raw_data")
                )
                db.add(new_event)
                synced += 1
        
        account.last_sync_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Calendar sync failed for account {account_id}: {e}")
        errors.append(str(e))
    
    return {"events_synced": synced, "events_updated": updated, "events_deleted": 0, "errors": errors}


async def sync_all_calendars(db: Session):
    """Sync all active calendar accounts"""
    from backend.models import CalendarAccount
    
    accounts = db.query(CalendarAccount).filter(CalendarAccount.is_active == True).all()
    results = {}
    
    for account in accounts:
        result = await sync_calendar_account(db, account.id)
        results[account.id] = result
    
    return results
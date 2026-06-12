from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from backend.main import get_db
from backend.models import CalendarAccount, CalendarEvent
from backend.config import settings

router = APIRouter()


class CalendarAccountCreate(BaseModel):
    provider: str  # google, outlook, ios
    account_email: str
    display_name: Optional[str] = None


class CalendarAccountResponse(BaseModel):
    id: int
    provider: str
    account_email: str
    display_name: Optional[str]
    is_active: bool
    selected_calendars: List[str] = []
    excluded_categories: List[str] = []
    created_at: datetime


class CalendarEventResponse(BaseModel):
    id: int
    account_id: int
    ical_uid: str
    provider: str
    title: Optional[str]
    organizer_email: Optional[str]
    attendee_emails: List[str]
    start_ms: int
    end_ms: int
    start_iso: str
    end_iso: str
    location: Optional[str]
    recurrence_rule: Optional[str]
    category: Optional[str]
    is_all_day: bool


class CalendarSyncResponse(BaseModel):
    account_id: int
    events_synced: int
    events_updated: int
    events_deleted: int
    errors: List[str]


@router.get("/accounts", response_model=List[CalendarAccountResponse])
async def list_calendar_accounts(db: Session = Depends(get_db)):
    accounts = db.query(CalendarAccount).filter(CalendarAccount.is_active == True).all()
    return [CalendarAccountResponse(
        id=a.id,
        provider=a.provider,
        account_email=a.account_email,
        display_name=a.display_name,
        is_active=a.is_active,
        selected_calendars=a.selected_calendars or [],
        excluded_categories=a.excluded_categories or [],
        created_at=a.created_at
    ) for a in accounts]


@router.post("/accounts", response_model=CalendarAccountResponse)
async def create_calendar_account(
    account: CalendarAccountCreate,
    db: Session = Depends(get_db)
):
    """Create a new calendar account connection"""
    # Check if already exists
    existing = db.query(CalendarAccount).filter(
        CalendarAccount.provider == account.provider,
        CalendarAccount.account_email == account.account_email
    ).first()

    if existing:
        raise HTTPException(409, "Calendar account already connected")

    new_account = CalendarAccount(
        provider=account.provider,
        account_email=account.account_email,
        display_name=account.display_name,
        is_active=True
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)

    return CalendarAccountResponse(
        id=new_account.id,
        provider=new_account.provider,
        account_email=new_account.account_email,
        display_name=new_account.display_name,
        is_active=new_account.is_active,
        selected_calendars=[],
        excluded_categories=[],
        created_at=new_account.created_at
    )


@router.get("/connect/{provider}")
async def get_oauth_url(
    provider: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None
):
    """Get OAuth authorization URL for calendar provider"""
    if provider == "google":
        from urllib.parse import urlencode
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri or settings.google_redirect_uri,
            "response_type": "code",
            "scope": settings.google_scopes,
            "access_type": "offline",
            "prompt": "consent"
        }
        if state:
            params["state"] = state
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return {"provider": "google", "auth_url": url}

    elif provider == "outlook":
        from urllib.parse import urlencode
        params = {
            "client_id": settings.ms_graph_client_id,
            "redirect_uri": redirect_uri or settings.ms_graph_redirect_uri,
            "response_type": "code",
            "scope": settings.ms_graph_scopes,
        }
        if state:
            params["state"] = state
        url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"
        return {"provider": "outlook", "auth_url": url}

    elif provider == "ios":
        # iOS EventKit doesn't use OAuth - handled via Capacitor plugin
        return {"provider": "ios", "message": "Use Capacitor EventKit plugin on device"}

    else:
        raise HTTPException(400, f"Unsupported provider: {provider}")


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Handle OAuth callback from calendar providers"""
    if error:
        raise HTTPException(400, f"OAuth error: {error}")

    if provider == "google":
        return await _handle_google_callback(code, db)
    elif provider == "outlook":
        return await _handle_outlook_callback(code, db)
    else:
        raise HTTPException(400, f"Unsupported provider: {provider}")


async def _handle_google_callback(code: str, db: Session):
    import httpx
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.google_redirect_uri
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(token_url, data=data)
        if resp.status_code != 200:
            raise HTTPException(400, f"Token exchange failed: {resp.text}")
        tokens = resp.json()

    # Get user info
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        user_info = resp.json()

    # Save or update account
    account = db.query(CalendarAccount).filter(
        CalendarAccount.provider == "google",
        CalendarAccount.account_email == user_info["email"]
    ).first()

    if not account:
        account = CalendarAccount(
            provider="google",
            account_email=user_info["email"],
            display_name=user_info.get("name")
        )
        db.add(account)

    # Encrypt and store tokens
    account.access_token_encrypted = _encrypt_token(tokens["access_token"])
    if "refresh_token" in tokens:
        account.refresh_token_encrypted = _encrypt_token(tokens["refresh_token"])
    account.token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    account.is_active = True

    db.commit()

    return {"status": "connected", "account_email": user_info["email"]}


async def _handle_outlook_callback(code: str, db: Session):
    import httpx
    # Exchange code for tokens
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": settings.ms_graph_client_id,
        "client_secret": settings.ms_graph_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.ms_graph_redirect_uri,
        "scope": settings.ms_graph_scopes
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(token_url, data=data)
        if resp.status_code != 200:
            raise HTTPException(400, f"Token exchange failed: {resp.text}")
        tokens = resp.json()

    # Get user info
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        user_info = resp.json()

    # Save or update account
    account = db.query(CalendarAccount).filter(
        CalendarAccount.provider == "outlook",
        CalendarAccount.account_email == user_info["mail"] or user_info["userPrincipalName"]
    ).first()

    if not account:
        account = CalendarAccount(
            provider="outlook",
            account_email=user_info["mail"] or user_info["userPrincipalName"],
            display_name=user_info.get("displayName")
        )
        db.add(account)

    account.access_token_encrypted = _encrypt_token(tokens["access_token"])
    if "refresh_token" in tokens:
        account.refresh_token_encrypted = _encrypt_token(tokens["refresh_token"])
    account.token_expires_at = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
    account.is_active = True

    db.commit()

    return {"status": "connected", "account_email": user_info["mail"] or user_info["userPrincipalName"]}


def _encrypt_token(token: str) -> str:
    """Encrypt token for storage - placeholder"""
    # In production, use proper encryption (AES-GCM with user-derived key)
    import base64
    return base64.b64encode(token.encode()).decode()


def _decrypt_token(encrypted: str) -> str:
    import base64
    return base64.b64decode(encrypted.encode()).decode()


@router.post("/accounts/{account_id}/sync", response_model=CalendarSyncResponse)
async def sync_calendar(
    account_id: int,
    db: Session = Depends(get_db)
):
    """Trigger calendar sync for an account"""
    account = db.query(CalendarAccount).filter(CalendarAccount.id == account_id).first()
    if not account:
        raise HTTPException(404, "Account not found")

    # This will be implemented in the calendar sync service
    # For now, return placeholder
    return CalendarSyncResponse(
        account_id=account_id,
        events_synced=0,
        events_updated=0,
        events_deleted=0,
        errors=["Sync service not yet implemented"]
    )


@router.get("/events", response_model=List[CalendarEventResponse])
async def list_calendar_events(
    account_id: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List calendar events with optional filters"""
    query = db.query(CalendarEvent)

    if account_id:
        query = query.filter(CalendarEvent.account_id == account_id)

    if start:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        query = query.filter(CalendarEvent.start_ms >= int(start_dt.timestamp() * 1000))

    if end:
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        query = query.filter(CalendarEvent.end_ms <= int(end_dt.timestamp() * 1000))

    events = query.order_by(CalendarEvent.start_ms.desc()).limit(limit).all()

    return [CalendarEventResponse(
        id=e.id,
        account_id=e.account_id,
        ical_uid=e.ical_uid,
        provider=e.provider,
        title=e.title,
        organizer_email=e.organizer_email,
        attendee_emails=e.attendee_emails or [],
        start_ms=e.start_ms,
        end_ms=e.end_ms,
        start_iso=datetime.fromtimestamp(e.start_ms / 1000).isoformat(),
        end_iso=datetime.fromtimestamp(e.end_ms / 1000).isoformat(),
        location=e.location,
        recurrence_rule=e.recurrence_rule,
        category=e.category,
        is_all_day=e.is_all_day
    ) for e in events]


@router.post("/accounts/{account_id}/categorize")
async def categorize_events(
    account_id: int,
    rules: List[dict],  # List of {pattern: str, category: str}
    db: Session = Depends(get_db)
):
    """Apply categorization rules to events"""
    # Placeholder
    return {"updated": 0, "message": "Categorization not yet implemented"}
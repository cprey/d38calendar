"""Google Calendar data source.

Fetches events from a Google Calendar via a service account and normalizes
them into plain `Event` objects. Rendering/template code (see render.py)
depends only on `Event` and never touches the raw Google API response shape,
so the two can be changed independently.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


@dataclass
class Event:
    summary: str
    location: str
    description: str
    all_day: bool
    start: datetime
    end: datetime
    pdf_url: str = ""  # link to the first attached PDF, if any
    # "Key: value" lines from the description, keys lowercased,
    # e.g. {"club": "OTB", "format": "Hare & Hound"}
    details: dict[str, str] = field(default_factory=dict)


class CalendarFetchError(RuntimeError):
    """Raised when events can't be retrieved from Google Calendar."""


def _resolve_bounds(start_date: str, end_date: str, tz_name: str) -> tuple[ZoneInfo, datetime, datetime]:
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError(f"Unknown timezone: {tz_name}") from exc

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=tz)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=tz) + timedelta(days=1)
    except ValueError as exc:
        raise ValueError("start/end must be in YYYY-MM-DD format") from exc

    if end_dt <= start_dt:
        raise ValueError("end must be on or after start")

    return tz, start_dt, end_dt


_DETAIL_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z ]{0,30}?)\s*:\s*(.+?)\s*$")


def _description_to_text(description: str) -> str:
    """Google Calendar may store descriptions as HTML; convert to plain text lines."""
    text = re.sub(r"<br\s*/?>|</(p|div|li)>", "\n", description, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).replace("\xa0", " ")


def _parse_details(description: str) -> dict[str, str]:
    """Pull "Key: value" lines (e.g. "Club: OTB") out of an event description."""
    details = {}
    for line in _description_to_text(description).splitlines():
        match = _DETAIL_LINE.match(line)
        if match:
            details[match.group(1).strip().lower()] = match.group(2)
    return details


def _normalize(raw: dict, tz: ZoneInfo) -> Event:
    start_field = raw.get("start", {})
    end_field = raw.get("end", {})
    all_day = "date" in start_field

    if all_day:
        start = datetime.strptime(start_field["date"], "%Y-%m-%d").replace(tzinfo=tz)
        end = datetime.strptime(end_field["date"], "%Y-%m-%d").replace(tzinfo=tz)
    else:
        start = datetime.fromisoformat(start_field["dateTime"]).astimezone(tz)
        end = datetime.fromisoformat(end_field["dateTime"]).astimezone(tz)

    pdf_url = next(
        (a.get("fileUrl", "") for a in raw.get("attachments", []) if a.get("mimeType") == "application/pdf"),
        "",
    )

    return Event(
        summary=raw.get("summary", "(No title)"),
        location=raw.get("location", ""),
        description=raw.get("description", ""),
        all_day=all_day,
        start=start,
        end=end,
        pdf_url=pdf_url,
        details=_parse_details(raw.get("description", "")),
    )


def fetch_events(
    calendar_id: str,
    credentials_path: Path,
    start_date: str,
    end_date: str,
    timezone: str = "UTC",
) -> list[Event]:
    """Fetch and normalize events from `calendar_id` between start_date and end_date (inclusive).

    Raises ValueError for bad input and CalendarFetchError for API/auth problems.
    """
    tz, start_dt, end_dt = _resolve_bounds(start_date, end_date, timezone)

    creds = service_account.Credentials.from_service_account_file(str(credentials_path), scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)

    raw_events = []
    page_token = None
    try:
        while True:
            response = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_dt.isoformat(),
                    timeMax=end_dt.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                )
                .execute()
            )
            raw_events.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except HttpError as exc:
        if exc.resp.status == 404:
            raise CalendarFetchError(f"Calendar not found: {calendar_id}") from exc
        if exc.resp.status == 403:
            raise CalendarFetchError(
                f"Access denied to calendar: {calendar_id}. Share it with the "
                "service account's client_email (see the credentials JSON file) "
                "and try again."
            ) from exc
        raise CalendarFetchError(str(exc)) from exc

    return [_normalize(raw, tz) for raw in raw_events]

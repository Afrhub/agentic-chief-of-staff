from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth import default
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class CalendarAdapter:
    """Adapter for Google Calendar integration."""

    def __init__(self, token: str, refresh_token: str = None):
        self.token = token
        self.refresh_token = refresh_token
        self.service = self._build_service()

    def _build_service(self):
        """Build Google Calendar API service."""
        try:
            creds = Credentials(
                token=self.token,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
            )
            return build("calendar", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Failed to build Calendar service: {e}")
            return None

    def get_upcoming_meetings(self, days_ahead: int = 7) -> list:
        """Get upcoming meetings in next N days."""
        if not self.service:
            return []

        try:
            now = datetime.utcnow().isoformat() + "Z"
            end = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"

            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=now,
                timeMax=end,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            events = events_result.get("items", [])
            meetings = []

            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                meetings.append({
                    "id": event["id"],
                    "summary": event.get("summary", ""),
                    "start": start,
                    "attendees": [a.get("email", "") for a in event.get("attendees", [])],
                    "description": event.get("description", "")
                })

            return meetings

        except Exception as e:
            logger.error(f"Failed to fetch upcoming meetings: {e}")
            return []

    def get_free_blocks(self, hours_ahead: int = 48) -> list:
        """Find free time blocks for deep work or decision-making."""
        if not self.service:
            return []

        try:
            meetings = self.get_upcoming_meetings(days_ahead=hours_ahead // 24 + 1)

            # Build busy times from meetings
            busy_times = []
            for meeting in meetings:
                busy_times.append({
                    "start": datetime.fromisoformat(meeting["start"].replace("Z", "+00:00")),
                    "end": datetime.fromisoformat(meeting["start"].replace("Z", "+00:00")) + timedelta(hours=1)
                })

            busy_times.sort(key=lambda x: x["start"])

            # Find gaps
            free_blocks = []
            current_time = datetime.utcnow()
            end_time = current_time + timedelta(hours=hours_ahead)

            for busy in busy_times:
                if busy["start"] > current_time + timedelta(minutes=30):
                    gap_duration = (busy["start"] - current_time).total_seconds() / 3600
                    if gap_duration >= 0.5:  # At least 30 minutes
                        free_blocks.append({
                            "start": current_time.isoformat(),
                            "end": busy["start"].isoformat(),
                            "duration_hours": gap_duration
                        })
                current_time = max(current_time, busy["end"])

            if current_time < end_time:
                final_gap = (end_time - current_time).total_seconds() / 3600
                if final_gap >= 0.5:
                    free_blocks.append({
                        "start": current_time.isoformat(),
                        "end": end_time.isoformat(),
                        "duration_hours": final_gap
                    })

            return free_blocks

        except Exception as e:
            logger.error(f"Failed to find free blocks: {e}")
            return []

    def get_recent_key_person_meetings(self, key_people: list) -> list:
        """Get recent meetings with key people (investors, board members, etc.)."""
        if not self.service:
            return []

        try:
            meetings = self.get_upcoming_meetings(days_ahead=30)

            key_meetings = []
            for meeting in meetings:
                attendees_lower = [a.lower() for a in meeting["attendees"]]
                if any(person.lower() in attendees_lower for person in key_people):
                    key_meetings.append(meeting)

            return key_meetings

        except Exception as e:
            logger.error(f"Failed to fetch key person meetings: {e}")
            return []

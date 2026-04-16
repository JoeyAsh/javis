# Feature Spec: Google Calendar Integration

## Summary
Enable JARVIS to manage Google Calendar events via voice: list upcoming events, create new events from natural language, update event times, and delete/cancel events.

## Goals
- List events for today/tomorrow/this week via voice
- Create events from natural language ("meeting with Bob tomorrow at 2pm")
- Update event times/details
- Delete/cancel events
- Establish CalendarProvider protocol for multi-provider support

## Non-Goals
- Recurring event creation (MVP: single events only)
- Invitation management (accept/decline)
- Multiple Google accounts
- Calendar sharing/permissions
- Video conferencing link generation

---

## Technical Design

### Dependencies
Requires `google-oauth-shared.md` to be implemented first.

### File Structure
```
src/integrations/calendar/
  __init__.py
  base.py               # CalendarProvider protocol + CalendarEvent (this spec)

src/integrations/google/
  calendar_client.py    # Google Calendar API wrapper (this spec)

src/brain/agents/
  calendar_agent.py     # Calendar agent (this spec)
```

### CalendarProvider Protocol

```python
# src/integrations/calendar/base.py

from typing import Protocol, runtime_checkable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class CalendarProviderType(Enum):
    GOOGLE = "google"
    # ICLOUD = "icloud"  # REMOVED (iCloud dropped in Revision 3)

@dataclass
class CalendarInfo:
    """Represents a calendar."""
    id: str
    name: str
    provider: CalendarProviderType
    is_primary: bool = False
    color: str | None = None
    writable: bool = True

@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    id: str
    calendar_id: str
    title: str
    start: datetime
    end: datetime
    provider: CalendarProviderType
    all_day: bool = False
    location: str | None = None
    description: str | None = None
    attendees: list[str] = field(default_factory=list)
    is_recurring: bool = False
    recurrence_rule: str | None = None

    @property
    def duration_minutes(self) -> int:
        """Calculate event duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)

    def to_voice_string(self, language: str = "en") -> str:
        """Format event for voice output."""
        time_str = self.start.strftime("%I:%M %p").lstrip("0")
        if language == "de":
            time_str = self.start.strftime("%H:%M")
            return f"{time_str} Uhr, {self.title}"
        return f"At {time_str}, {self.title}"

@runtime_checkable
class CalendarProvider(Protocol):
    """Protocol for calendar providers (Google only in MVP; iCloud dropped)."""

    @property
    def provider_type(self) -> CalendarProviderType:
        """Return the provider type."""
        ...

    async def list_calendars(self) -> list[CalendarInfo]:
        """List available calendars.

        Returns:
            List of CalendarInfo objects
        """
        ...

    async def list_events(
        self,
        calendar_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        max_results: int = 20,
    ) -> list[CalendarEvent]:
        """List events in time range.

        Args:
            calendar_id: Specific calendar (None = primary)
            start: Start of time range (default: now)
            end: End of time range (default: 7 days from now)
            max_results: Maximum events to return

        Returns:
            List of CalendarEvent objects sorted by start time
        """
        ...

    async def get_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> CalendarEvent:
        """Get a single event by ID.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event ID

        Returns:
            CalendarEvent object

        Raises:
            EventNotFoundError: If event doesn't exist
        """
        ...

    async def create_event(
        self,
        calendar_id: str,
        title: str,
        start: datetime,
        end: datetime,
        location: str | None = None,
        description: str | None = None,
        attendees: list[str] | None = None,
    ) -> CalendarEvent:
        """Create a new event.

        Args:
            calendar_id: Target calendar
            title: Event title
            start: Start datetime
            end: End datetime
            location: Optional location
            description: Optional description
            attendees: Optional list of attendee emails

        Returns:
            Created CalendarEvent object
        """
        ...

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        location: str | None = None,
        description: str | None = None,
    ) -> CalendarEvent:
        """Update an existing event.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event to update
            **kwargs: Fields to update (None = keep existing)

        Returns:
            Updated CalendarEvent object
        """
        ...

    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> bool:
        """Delete an event.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event to delete

        Returns:
            True if deleted successfully
        """
        ...
```

### GoogleCalendarClient

```python
# src/integrations/google/calendar_client.py

from integrations.calendar.base import (
    CalendarProvider,
    CalendarProviderType,
    CalendarInfo,
    CalendarEvent,
)
from integrations.google.oauth import GoogleOAuthService

class GoogleCalendarClient(CalendarProvider):
    """Google Calendar API client implementing CalendarProvider."""

    def __init__(self, oauth_service: GoogleOAuthService) -> None:
        """Initialize Google Calendar client.

        Args:
            oauth_service: Shared Google OAuth service
        """
        self.oauth = oauth_service
        self._service = None

    @property
    def provider_type(self) -> CalendarProviderType:
        return CalendarProviderType.GOOGLE

    async def _get_service(self):
        """Get or create Google Calendar API service."""
        if self._service is None:
            creds = await self.oauth.get_credentials()
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    async def list_calendars(self) -> list[CalendarInfo]:
        """List user's calendars."""
        service = await self._get_service()
        result = service.calendarList().list().execute()

        calendars = []
        for item in result.get("items", []):
            calendars.append(CalendarInfo(
                id=item["id"],
                name=item.get("summary", "Untitled"),
                provider=CalendarProviderType.GOOGLE,
                is_primary=item.get("primary", False),
                color=item.get("backgroundColor"),
                writable=item.get("accessRole") in ("owner", "writer"),
            ))
        return calendars

    async def list_events(
        self,
        calendar_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        max_results: int = 20,
    ) -> list[CalendarEvent]:
        """List events in time range."""
        service = await self._get_service()

        calendar_id = calendar_id or "primary"
        start = start or datetime.now()
        end = end or start + timedelta(days=7)

        result = service.events().list(
            calendarId=calendar_id,
            timeMin=start.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for item in result.get("items", []):
            events.append(self._parse_event(item, calendar_id))
        return events

    def _parse_event(self, item: dict, calendar_id: str) -> CalendarEvent:
        """Parse Google Calendar API event to CalendarEvent."""
        # Handle all-day vs timed events
        start_data = item.get("start", {})
        end_data = item.get("end", {})

        if "date" in start_data:
            # All-day event
            start = datetime.fromisoformat(start_data["date"])
            end = datetime.fromisoformat(end_data["date"])
            all_day = True
        else:
            start = datetime.fromisoformat(
                start_data["dateTime"].replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                end_data["dateTime"].replace("Z", "+00:00")
            )
            all_day = False

        return CalendarEvent(
            id=item["id"],
            calendar_id=calendar_id,
            title=item.get("summary", "Untitled"),
            start=start,
            end=end,
            provider=CalendarProviderType.GOOGLE,
            all_day=all_day,
            location=item.get("location"),
            description=item.get("description"),
            attendees=[a.get("email") for a in item.get("attendees", [])],
            is_recurring="recurrence" in item,
            recurrence_rule=item.get("recurrence", [None])[0],
        )

    async def create_event(
        self,
        calendar_id: str,
        title: str,
        start: datetime,
        end: datetime,
        location: str | None = None,
        description: str | None = None,
        attendees: list[str] | None = None,
    ) -> CalendarEvent:
        """Create a new event."""
        service = await self._get_service()

        event_body = {
            "summary": title,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }

        if location:
            event_body["location"] = location
        if description:
            event_body["description"] = description
        if attendees:
            event_body["attendees"] = [{"email": e} for e in attendees]

        result = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
        ).execute()

        return self._parse_event(result, calendar_id)

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        location: str | None = None,
        description: str | None = None,
    ) -> CalendarEvent:
        """Update an existing event."""
        service = await self._get_service()

        # Get existing event
        existing = service.events().get(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()

        # Update fields
        if title is not None:
            existing["summary"] = title
        if start is not None:
            existing["start"] = {"dateTime": start.isoformat(), "timeZone": "UTC"}
        if end is not None:
            existing["end"] = {"dateTime": end.isoformat(), "timeZone": "UTC"}
        if location is not None:
            existing["location"] = location
        if description is not None:
            existing["description"] = description

        result = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=existing,
        ).execute()

        return self._parse_event(result, calendar_id)

    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> bool:
        """Delete an event."""
        service = await self._get_service()
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()
        return True
```

### CalendarAgent

```python
# src/brain/agents/calendar_agent.py

from datetime import datetime, timedelta
from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from integrations.calendar.base import CalendarProvider, CalendarEvent

class CalendarAgent(BaseAgent):
    """Agent for calendar operations."""

    def __init__(
        self,
        claude_client: ClaudeClient,
        providers: list[CalendarProvider],
    ) -> None:
        """Initialize calendar agent.

        Args:
            claude_client: Claude client for NL parsing
            providers: List of calendar providers (Google only; via OpenClaw)
        """
        super().__init__()
        self.claude_client = claude_client
        self.providers = providers
        self._recent_events: list[CalendarEvent] = []  # For "delete the 2pm meeting"

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Execute calendar action."""
        action = params.get("action", "list")

        if action == "list":
            return await self._handle_list(task, params, language)
        elif action == "create":
            return await self._handle_create(task, params, language)
        elif action == "update":
            return await self._handle_update(task, params, language)
        elif action == "delete":
            return await self._handle_delete(task, params, language)
        else:
            return await self._handle_list(task, params, language)

    async def _handle_list(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Handle listing events."""
        # Determine time range
        start, end = self._parse_time_range(params)

        # Gather events from all providers
        all_events: list[CalendarEvent] = []
        for provider in self.providers:
            events = await provider.list_events(start=start, end=end)
            all_events.extend(events)

        # Sort by start time
        all_events.sort(key=lambda e: e.start)
        self._recent_events = all_events  # Cache for reference

        if not all_events:
            return AgentResult(
                spoken_response=self._no_events_response(start, end, language),
                success=True,
                data={"count": 0},
            )

        # Generate voice response
        response = self._generate_list_response(all_events, language)

        return AgentResult(
            spoken_response=response,
            success=True,
            data={"count": len(all_events)},
        )

    async def _handle_create(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Handle creating an event from natural language."""
        # Use Claude to parse natural language into event details
        parsed = await self._parse_event_from_nl(task, language)

        if not parsed.get("title") or not parsed.get("start"):
            return AgentResult(
                spoken_response=self._clarify_response(parsed, language),
                success=False,
                data={"needs_clarification": True, "parsed": parsed},
            )

        # Use first writable provider (Google by default)
        provider = self._get_default_provider()
        calendar_id = params.get("calendar_id", "primary")

        event = await provider.create_event(
            calendar_id=calendar_id,
            title=parsed["title"],
            start=parsed["start"],
            end=parsed.get("end", parsed["start"] + timedelta(hours=1)),
            location=parsed.get("location"),
        )

        return AgentResult(
            spoken_response=self._create_confirmation(event, language),
            success=True,
            data={"event_id": event.id},
        )

    async def _parse_event_from_nl(
        self,
        text: str,
        language: str,
    ) -> dict[str, Any]:
        """Use Claude to parse natural language into event details."""
        now = datetime.now()

        prompt = f"""Parse this calendar request into structured data.
Current datetime: {now.isoformat()}

User request: "{text}"

Return JSON with:
- title: event title (required)
- start: ISO datetime string (required)
- end: ISO datetime string (optional, default 1 hour after start)
- location: string (optional)
- attendees: list of names/emails (optional)

Examples:
- "meeting with Bob tomorrow at 2pm" -> {{"title": "Meeting with Bob", "start": "2024-01-16T14:00:00"}}
- "dentist appointment Friday 10am for 2 hours" -> {{"title": "Dentist appointment", "start": "2024-01-19T10:00:00", "end": "2024-01-19T12:00:00"}}

Return only valid JSON, no explanation."""

        response = await self.claude_client.complete(
            prompt=prompt,
            max_tokens=150,
            temperature=0.3,
        )

        try:
            # Parse JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1].lstrip("json\n")
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw": text}

    def _generate_list_response(
        self,
        events: list[CalendarEvent],
        language: str,
    ) -> str:
        """Generate spoken response for event list."""
        # Group by day
        by_day: dict[str, list[CalendarEvent]] = {}
        for event in events:
            day_key = event.start.strftime("%A")  # "Monday", "Tuesday", etc.
            by_day.setdefault(day_key, []).append(event)

        parts = []
        for day, day_events in by_day.items():
            if language == "de":
                day_intro = f"Am {day} haben Sie {len(day_events)} Termine."
            else:
                day_intro = f"On {day} you have {len(day_events)} event{'s' if len(day_events) > 1 else ''}."

            event_strs = [e.to_voice_string(language) for e in day_events[:3]]
            parts.append(f"{day_intro} {', '.join(event_strs)}")

        return " ".join(parts)
```

### Intent Parser Updates

Add to `Intent` enum:
```python
class Intent(Enum):
    # ... existing ...
    CALENDAR_LIST = "calendar_list"
    CALENDAR_CREATE = "calendar_create"
    CALENDAR_UPDATE = "calendar_update"
    CALENDAR_DELETE = "calendar_delete"
```

Add to `INTENT_KEYWORDS`:
```python
Intent.CALENDAR_LIST: {
    "en": [
        r"\b(what('s| is)|show|check|list)\s+(on\s+)?(my\s+)?(calendar|schedule)\b",
        r"\b(my\s+)?(appointments?|events?|meetings?)\s+(today|tomorrow|this week)\b",
        r"\bwhat\s+(do\s+)?i\s+have\s+(today|tomorrow|this week|scheduled)\b",
        r"\b(any|next)\s+(appointments?|meetings?|events?)\b",
    ],
    "de": [
        r"\b(was\s+)?(steht|ist)\s+(auf|in)\s+(meinem\s+)?kalender\b",
        r"\b(meine?\s+)?(termine?|meetings?)\s+(heute|morgen|diese woche)\b",
        r"\bwas\s+habe?\s+ich\s+(heute|morgen|geplant)\b",
        r"\b(welche|nächste[rn]?)\s+termine?\b",
    ],
},
Intent.CALENDAR_CREATE: {
    "en": [
        r"\b(schedule|create|add|book|set\s+up)\s+(a\s+)?(meeting|appointment|event)\b",
        r"\bput\s+(something\s+)?on\s+(my\s+)?calendar\b",
        r"\bblock\s+(off\s+)?time\b",
        r"\bremind\s+me\s+(to|about)\b",
    ],
    "de": [
        r"\b(erstelle?|trag\s+ein|plane?|buche?)\s+(einen?\s+)?(termin|meeting|event)\b",
        r"\b(trag|schreib)\s+(etwas\s+)?in\s+(meinen?\s+)?kalender\b",
        r"\bzeit\s+blockieren\b",
        r"\berinner(e|n)\s+mich\s+(an|dass)\b",
    ],
},
Intent.CALENDAR_UPDATE: {
    "en": [
        r"\b(move|reschedule|change|update)\s+(my\s+)?(meeting|appointment|event)\b",
        r"\bpush\s+(back|forward)\s+(my\s+)?\b",
        r"\bchange\s+the\s+time\b",
    ],
    "de": [
        r"\b(verschieb|verleg|änder)\s+(meinen?\s+)?(termin|meeting)\b",
        r"\b(zeit|uhrzeit)\s+(ändern|verschieben)\b",
    ],
},
Intent.CALENDAR_DELETE: {
    "en": [
        r"\b(cancel|delete|remove)\s+(my\s+)?(meeting|appointment|event)\b",
        r"\btake\s+off\s+(my\s+)?calendar\b",
        r"\bclear\s+(my\s+)?(schedule|calendar)\b",
    ],
    "de": [
        r"\b(lösch|absagen?|streich|entfern)\s+(meinen?\s+)?(termin|meeting)\b",
        r"\btermin\s+(absagen|löschen|streichen)\b",
        r"\bkalender\s+leeren\b",
    ],
},
```

---

## Voice UX Design

### Listing Events
**User:** "What's on my calendar tomorrow?"
**JARVIS:** "Tomorrow you have 3 events. At 9 AM, weekly standup. At 2 PM, design review with the frontend team. At 4 PM, one-on-one with Sarah."

### Creating Events
**User:** "Schedule a meeting with Bob tomorrow at 2pm"
**JARVIS:** "I'll create a meeting with Bob tomorrow at 2 PM for one hour. Should I proceed, sir?"
**User:** "Yes"
**JARVIS:** "Done. Meeting with Bob scheduled for tomorrow at 2 PM."

### Updating Events
**User:** "Move my 2pm meeting to 3pm"
**JARVIS:** "I've moved your meeting with Bob from 2 PM to 3 PM, sir."

### Deleting Events
**User:** "Cancel my 4pm meeting"
**JARVIS:** "I've cancelled your 4 PM one-on-one with Sarah, sir."

### Ambiguous Cases
**User:** "Cancel my meeting"
**JARVIS:** "You have 2 meetings today. Which one should I cancel: the 2 PM design review or the 4 PM one-on-one?"

---

## Configuration

### config.yaml additions
```yaml
calendar:
  enabled: true
  providers:
    google:
      enabled: true
      default_calendar_id: "primary"
  default_lookahead_days: 7
  max_events_per_query: 20
  default_event_duration_minutes: 60
```

---

## Error Handling

| Error | User-Facing Response |
|-------|---------------------|
| OAuth not configured | "Calendar access is not configured. Please set up Google authentication." |
| No calendars found | "I couldn't find any calendars in your account." |
| Event not found | "I couldn't find that event on your calendar." |
| Conflict detected | "That time conflicts with an existing event. Should I schedule anyway?" |
| Past date | "That date has already passed. Did you mean next week?" |

---

## Testing Strategy

### Unit Tests
| Test Case | Description |
|-----------|-------------|
| `test_list_events_single_day` | Returns events for today |
| ~~`test_list_events_multi_provider`~~ | ~~Merges Google + iCloud events~~ — REMOVED (single provider) |
| `test_create_event_basic` | Creates event with title + time |
| `test_update_event_time` | Updates event start/end |
| `test_delete_event` | Deletes event |
| `test_nl_parse_meeting_tomorrow` | "meeting tomorrow 2pm" -> correct datetime |
| `test_nl_parse_duration` | "2 hour meeting" -> correct end time |
| `test_intent_parser_list` | "what's on my calendar" -> CALENDAR_LIST |
| `test_intent_parser_create` | "schedule a meeting" -> CALENDAR_CREATE |

### Integration Tests
| Test Case | Description |
|-----------|-------------|
| `test_full_flow_list_today` | Intent -> agent -> spoken response |
| `test_full_flow_create` | Natural language -> create event -> confirmation |
| `test_oauth_refresh` | 401 triggers token refresh |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/integrations/calendar/__init__.py` | Package init |
| `src/integrations/calendar/base.py` | CalendarProvider protocol + CalendarEvent |
| `src/integrations/google/calendar_client.py` | Google Calendar client |
| `src/brain/agents/calendar_agent.py` | Calendar agent |
| `tests/integrations/calendar/test_base.py` | Protocol tests |
| `tests/integrations/google/test_calendar_client.py` | Client tests |
| `tests/brain/agents/test_calendar_agent.py` | Agent tests |

## Files Modified

| File | Change |
|------|--------|
| `src/brain/intent_parser.py` | Add CALENDAR_* intents + keywords |
| `src/brain/orchestrator.py` | Register CalendarAgent |
| `config/config.yaml` | Add calendar section |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | "what's on my calendar tomorrow" returns events for tomorrow | Integration test |
| 2 | "schedule a meeting with X tomorrow at Y" creates event | Integration test verifying API payload |
| 3 | Events sorted by start time in voice output | Unit test |
| 4 | German phrases work: "was steht morgen an" | Intent parser test |
| 5 | Natural language parsing handles "2pm", "14:00", "this afternoon" | Claude parsing tests |
| 6 | Update modifies correct event | Integration test |
| 7 | Delete removes event | Integration test verifying API call |
| 8 | CalendarProvider protocol satisfied by GoogleCalendarClient | mypy type check |

---

## Dependencies

- ~~**Upstream:** google-oauth-shared.md~~ — REMOVED (OpenClaw handles OAuth)
- ~~**Downstream:** icloud-calendar-integration.md~~ — DELETED (iCloud dropped)
- **NEW Prerequisite:** `openclaw-integration.md`

---

## Revision 2 — 2026-04-16

### Summary of Changes
~~This revision implements dual-write default for event creation across Google and iCloud calendars.~~

**SUPERSEDED by Revision 3:** Dual-write logic removed. iCloud dropped. Google Calendar via OpenClaw only.

---

**Status:** Planned — awaiting implementation authorization

---

## Revision 3 — Full OpenClaw Adoption (2026-04-16)

### Decisions Applied
1. **iCloud CalDAV dropped entirely** — No dual-provider, no dual-write
2. **OpenClaw as full backbone** — Google Calendar via OpenClaw only

### Integration Assessment
**OpenClaw FULLY replaces this spec's core functionality.**

### OpenClaw Coverage
| Feature | OpenClaw Capability | Coverage |
|---------|---------------------|----------|
| List events | Calendar integration | Full |
| Create event | Calendar integration | Full |
| Update event | Calendar integration | Full |
| Delete event | Calendar integration | Full |
| Natural language parsing | OpenClaw agent | Full |
| OAuth handling | OpenClaw internal | Full |

### What JARVIS-Native Retains
1. **AgendaPanel** — HUD visualization of calendar events
2. **Voice UX** — Confirmation dialogs, ambiguity resolution, spoken responses
3. **CalendarEvent dataclass** — For HUD panel rendering (no protocol needed)

### What Is REMOVED (This Spec)
- ~~CalendarProvider protocol~~ — REMOVED (single provider via OpenClaw)
- ~~GoogleCalendarClient~~ — REMOVED (OpenClaw handles)
- ~~CalendarAgent~~ — REMOVED (queries go to OpenClaw)
- ~~Dual-write logic~~ — REMOVED (iCloud dropped)
- ~~UnifiedCalendarService~~ — REMOVED (single source)
- ~~google-oauth-shared.md dependency~~ — REMOVED (OpenClaw handles OAuth)

### Migration Path
1. All calendar voice commands route to OpenClaw via `query_agent()`
2. OpenClaw returns structured event data
3. JARVIS maps response to `CalendarEvent` for AgendaPanel
4. No JARVIS-side service client implementation

### Simplified Architecture
```
Voice: "What's on my calendar tomorrow?"
       ↓
[Intent Parser] → CALENDAR_LIST intent
       ↓
[Orchestrator] → Forward to OpenClaw
       ↓
[OpenClaw Google Calendar skill]
       ↓
[Response] → Map to CalendarEvent for HUD + spoken output
```

### Files Created — REDUCED
| File | Purpose | Status |
|------|---------|--------|
| `src/integrations/calendar/__init__.py` | Package init | SKIP (no client) |
| `src/integrations/calendar/base.py` | CalendarEvent dataclass only | KEEP (HUD needs) |
| `src/integrations/google/calendar_client.py` | Google Calendar client | SKIP (OpenClaw) |
| `src/brain/agents/calendar_agent.py` | Calendar agent | SKIP (OpenClaw) |

### Files Modified — REDUCED
| File | Change | Status |
|------|--------|--------|
| `src/brain/intent_parser.py` | Add CALENDAR_* intents | KEEP |
| `src/brain/orchestrator.py` | Route to OpenClaw | MODIFIED |
| `config/config.yaml` | Calendar section (provider: openclaw) | SIMPLIFIED |

### Implementation Reduction
**Original estimate:** 6-8 hours
**With OpenClaw:** 2-3 hours (HUD panel + intent routing only)
**Reduction:** ~60%

### Prerequisites
- `openclaw-integration.md` — REQUIRED (handles all calendar operations)

### Cross-References Updated
- ~~`icloud-calendar-integration.md`~~ — DELETED (iCloud dropped)
- ~~`google-oauth-shared.md`~~ — SKIP (OpenClaw handles OAuth)

# Feature: Google Calendar Integration

## Status
Planned — awaiting implementation authorization

## Goal
Give JARVIS live read and write access to the user's Google Calendar: list upcoming events
(today / this week), create events from natural-language voice commands, update and delete
existing events with verbal confirmation, and surface the next event proactively 10, 5, and
1 minute before it begins. The AgendaPanel currently renders mock data; this feature wires it
to real events pushed by a backend poller.

## Scope
### In scope
- `src/integrations/google/calendar_client.py` — `GoogleCalendarClient` lazy singleton
  (mirrors `GmailClient` / `get_gmail_client` factory pattern; uses
  `get_google_oauth_service().build_service("calendar", "v3", scopes=...)`)
- `CalendarEvent` dataclass in `src/integrations/google/calendar_client.py` (no
  `CalendarProvider` protocol — Google-only, no abstraction needed)
- Intent parser additions: `CALENDAR_LIST`, `CALENDAR_CREATE`, `CALENDAR_UPDATE`,
  `CALENDAR_DELETE` (en + de keywords)
- Orchestrator calendar context injection (`_build_calendar_context`) for the four
  calendar intents, mirroring `_build_email_context`
- `src/api/ws_server.py` additions:
  - `broadcast_calendar_state(events, date_label)` broadcaster
  - `_start_calendar_poller(poll_interval)` background coroutine (60 s default)
  - `_handle_calendar_confirm(ws, text)` — confirmation gate for create/update/delete
  - `get_calendar_client()` lazy proxy (mirrors `get_gmail_client()`)
  - Per-connection `pending_calendar_op` state (mirrors `pending_email_send`)
- `CalendarEventConfirmPreviewPayload` and `CalendarOpDonePayload` WS message types
  added to `frontend/src/types.ts`; `WsIncoming` union extended with
  `calendar_state`, `calendar_op_preview`, `calendar_op_done`
- `subscribeCalendarState`, `subscribeCalendarOpPreview`, `subscribeCalendarOpDone`
  added to `useWebSocket`
- `AgendaPanel.tsx` wired to live `calendar_state` events (drop `agendaMock` default)
- ProactiveScheduler integration: calendar poller publishes
  `calendar_event_approaching` events (at 10, 5, 1 minutes before start) to
  `EventBus`; existing `_handle_calendar_event` in `ProactiveScheduler` handles them
  (no changes to `proactive.py`)
- Natural-language date parsing via `dateparser` library for create/update intents
  (delta expressions: "tomorrow 2pm", "in 3 hours", "Friday 10am")
- All-day event support (API `date` vs `dateTime` field handling)
- `config/config.yaml` — new `calendar:` section
- `requirements.txt` — add `dateparser` if not already present
- Tests: `tests/integrations/google/test_calendar_client.py`,
  `tests/api/test_calendar_poller.py`, `tests/brain/test_calendar_intent.py`,
  `frontend/src/hooks/__tests__/useWebSocket.calendar.test.ts`

### Out of scope
- iCloud / CalDAV integration (explicitly dropped; no `CalendarProvider` protocol)
- Recurring event creation (MVP: single events only)
- Invitation accept / decline
- Multiple Google accounts
- Video conferencing link insertion
- CalDAV self-hosted calendars
- Natural-language duration parsing beyond "for N hours / N minutes" at MVP
- Free-busy conflict detection

## User Flow

**List events**
1. User says "What's on my calendar today?" or "Was steht morgen an?"
2. Orchestrator detects `CALENDAR_LIST`, calls `_build_calendar_context`, fetches
   next 24–48 h of events from `GoogleCalendarClient.list_events`.
3. OpenClaw turns the structured context into a natural spoken summary.
4. Simultaneously the frontend's AgendaPanel already shows live events from the
   last poller push.

**Create event (with confirmation)**
1. User says "Schedule a meeting with Bob tomorrow at 2pm."
2. Orchestrator detects `CALENDAR_CREATE`. `dateparser` parses "tomorrow at 2pm" →
   `datetime`. End time defaults to start + 1 h.
3. Backend broadcasts `calendar_op_preview` (type, title, start, end) to frontend
   HUD and speaks: "Create 'Meeting with Bob' tomorrow at 14:00 for one hour. Confirm?"
4. `pending_calendar_op` is set on the connection with a 60 s TTL.
5. Next utterance passes through `_handle_calendar_confirm`:
   - Confirm word → `GoogleCalendarClient.create_event()` fires, `calendar_op_done`
     broadcast, `calendar_state` refresh broadcast, JARVIS speaks confirmation.
   - Cancel word → op discarded, `calendar_op_done{success:false}` broadcast.
   - Timeout → state cleared, notification broadcast, turn processed normally.
6. AgendaPanel refreshes from next poll (or immediately from the forced re-broadcast
   after the confirmed write).

**Update event**
Same flow as create: JARVIS reads back the target event (resolved from
`_build_calendar_context` using the connection's last-known event list), proposes
the change, waits for confirmation, then calls `update_event`.

**Delete event**
Same flow: resolves event, speaks "Delete 'X' at 14:00 tomorrow. Confirm?", waits,
calls `delete_event` on confirm.

**Proactive reminder**
1. Calendar poller runs every 60 s. After each successful fetch it computes
   `minutes_until_start` for all events in the next 12 h.
2. At exactly 10, 5, and 1 minutes before any event, it publishes
   `Event(type="calendar_event_approaching", payload={"title": ..., "starts_in_minutes": N})`
   to the `EventBus`.
3. `ProactiveScheduler._handle_calendar_event` (already wired) fires TTS and the
   HUD notification. No changes to `proactive.py`.

## Architecture

### Modules touched
- Backend:
  - `src/integrations/google/calendar_client.py` (new)
  - `src/integrations/google/__init__.py` (export `GoogleCalendarClient`,
    `CalendarEvent`, `CalendarClientError`, `get_calendar_client`)
  - `src/brain/intent_parser.py` (add four `CALENDAR_*` intents + keywords)
  - `src/brain/orchestrator.py` (add `_build_calendar_context`,
    extend `_EMAIL_INTENTS`-pattern to `_CALENDAR_INTENTS`)
  - `src/api/ws_server.py` (add broadcaster, poller, confirm handler, lazy proxy,
    per-connection state)
- Frontend:
  - `frontend/src/types.ts` (new payload types + union variants)
  - `frontend/src/hooks/useWebSocket.ts` (three new subscribers)
  - `frontend/src/components/panels/AgendaPanel.tsx` (drop `agendaMock`, accept live
    data via prop; caller in `App.tsx` provides data from `subscribeCalendarState`)
- Config:
  - `config/config.yaml` — `calendar:` section (see Interfaces)
- Env:
  - No new env vars; OAuth reuses `GOOGLE_OAUTH_CLIENT_ID`,
    `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_TOKEN_CACHE`

### Data flow

```
[Google Calendar API]
       ↑ (every 60 s via asyncio.to_thread)
[GoogleCalendarClient.list_events]
       |
       ├─→ broadcast_calendar_state(events) ──→ [WS: calendar_state] ──→ AgendaPanel
       |
       └─→ EventBus.publish(calendar_event_approaching) at 10/5/1 min
                   ↓
           [ProactiveScheduler._handle_calendar_event]
                   ↓
           TTS + broadcast_notification

Voice turn (CALENDAR_CREATE / _UPDATE / _DELETE):
[STT transcript]
       ↓
[_handle_calendar_confirm] ← checks pending_calendar_op on connection
       ↓ (not pending — fresh command)
[IntentParser] → CALENDAR_LIST / _CREATE / _UPDATE / _DELETE
       ↓
[Orchestrator._build_calendar_context] → GoogleCalendarClient.list_events
       ↓
[OpenClaw chat (context-injected)] → generates spoken summary OR extract op params
       ↓
   if mutating op:
       ↓
[ws_server] sets pending_calendar_op, broadcasts calendar_op_preview, speaks confirm prompt
       ↓
[next STT turn → _handle_calendar_confirm]
       ↓ confirm
[GoogleCalendarClient.create/update/delete_event]
       ↓
broadcast_calendar_state (refresh) + broadcast_calendar_op_done + TTS
```

### Interfaces

**Python — `src/integrations/google/calendar_client.py`**

```python
CALENDAR_SCOPES: list[str]  # ["https://www.googleapis.com/auth/calendar",
                             #  "https://www.googleapis.com/auth/calendar.events"]

@dataclass
class CalendarEvent:
    id: str
    calendar_id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str | None
    description: str | None
    attendees: list[str]
    is_recurring: bool

class CalendarClientError(Exception):
    spoken_message: str

class GoogleCalendarClient:
    def __init__(self, oauth_service: GoogleOAuthService) -> None: ...
    async def _get_service(self) -> Any: ...  # lazy, asyncio.Lock guarded
    async def list_events(
        self,
        calendar_id: str = "primary",
        start: datetime | None = None,
        end: datetime | None = None,
        max_results: int = 20,
    ) -> list[CalendarEvent]: ...
    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
        location: str | None = None,
        description: str | None = None,
    ) -> CalendarEvent: ...
    async def update_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        title: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        location: str | None = None,
    ) -> CalendarEvent: ...
    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> None: ...

_calendar_client: GoogleCalendarClient | None  # module-level singleton

def get_calendar_client() -> GoogleCalendarClient: ...
```

**Python — `src/api/ws_server.py` additions**

```python
def get_calendar_client() -> Any: ...  # proxy to integrations.google.calendar_client.get_calendar_client

async def broadcast_calendar_state(
    events: list[dict[str, Any]],
    date_label: str,
) -> None: ...

async def broadcast_calendar_op_preview(payload: dict[str, Any]) -> None: ...
async def broadcast_calendar_op_done(payload: dict[str, Any]) -> None: ...

async def _handle_calendar_confirm(ws: web.WebSocketResponse, text: str) -> bool: ...
async def _start_calendar_poller(poll_interval: int) -> None: ...
```

**Python — `src/brain/intent_parser.py` additions**

```python
class Intent(Enum):
    # ... existing ...
    CALENDAR_LIST   = "calendar_list"
    CALENDAR_CREATE = "calendar_create"
    CALENDAR_UPDATE = "calendar_update"
    CALENDAR_DELETE = "calendar_delete"
```

**WebSocket messages (new)**

`calendar_state` — pushed by poller every 60 s and after any successful write:
```json
{
  "type": "calendar_state",
  "payload": {
    "events": [
      {
        "id": "abc123",
        "title": "Standup",
        "start": "2026-04-18T09:00:00+02:00",
        "end":   "2026-04-18T09:30:00+02:00",
        "allDay": false,
        "location": null,
        "calendar": "primary"
      }
    ],
    "dateLabel": "Today"
  }
}
```

`calendar_op_preview` — broadcast before waiting for voice confirmation:
```json
{
  "type": "calendar_op_preview",
  "payload": {
    "op": "create",
    "title": "Meeting with Bob",
    "start": "2026-04-19T14:00:00+02:00",
    "end":   "2026-04-19T15:00:00+02:00",
    "confirm_prompt": "Create 'Meeting with Bob' tomorrow at 14:00 for one hour. Confirm?"
  }
}
```

`calendar_op_done` — broadcast after the confirmation resolves:
```json
{
  "type": "calendar_op_done",
  "payload": {
    "op": "create",
    "success": true,
    "event_id": "abc123",
    "error": null
  }
}
```

**TypeScript — `frontend/src/types.ts` additions**

```typescript
export interface CalendarStatePayload {
  events: AgendaEvent[];   // reuses existing AgendaEvent shape
  dateLabel: string;
}

export interface CalendarOpPreviewPayload {
  op: 'create' | 'update' | 'delete';
  title: string;
  start: string;   // ISO
  end: string;     // ISO
  confirm_prompt: string;
}

export interface CalendarOpDonePayload {
  op: 'create' | 'update' | 'delete';
  success: boolean;
  event_id?: string;
  error?: string;
}
```

`WsIncoming` union extensions:
```typescript
| { type: 'calendar_state'; payload: CalendarStatePayload }
| { type: 'calendar_op_preview'; payload: CalendarOpPreviewPayload }
| { type: 'calendar_op_done'; payload: CalendarOpDonePayload }
```

**`useWebSocket` additions**

```typescript
export type CalendarStateListener = (payload: CalendarStatePayload) => void;
export type CalendarOpPreviewListener = (payload: CalendarOpPreviewPayload) => void;
export type CalendarOpDoneListener = (payload: CalendarOpDonePayload) => void;

// Added to UseWebSocketReturn:
subscribeCalendarState: (listener: CalendarStateListener) => () => void;
subscribeCalendarOpPreview: (listener: CalendarOpPreviewListener) => () => void;
subscribeCalendarOpDone: (listener: CalendarOpDoneListener) => () => void;
```

**`config/config.yaml` additions**

```yaml
calendar:
  enabled: true
  poll_interval_seconds: 60
  lookahead_hours: 12          # window for proactive reminder checks
  max_events_per_query: 20
  default_event_duration_minutes: 60
  op_confirm_timeout_seconds: 60
  scopes:
    - "https://www.googleapis.com/auth/calendar"
    - "https://www.googleapis.com/auth/calendar.events"
```

### External dependencies
- `dateparser>=1.2.0` — natural-language date parsing; add to `requirements.txt`
- `google-api-python-client>=2.127.0` — already in `requirements.txt`
- No new npm packages

## Edge Cases & Failure Modes

- **OAuth not configured / no token** → `GoogleOAuthError` caught in poller and
  `_build_calendar_context`; poller backs off (same 3-failure backoff as mail poller);
  context returns `None`, OpenClaw responds without calendar data; no crash.
- **Calendar API 403 (insufficient scope)** → `CalendarClientError` with
  `spoken_message="Calendar access is not authorized. Please re-authenticate."`;
  poller backs off; orchestrator context returns `None`.
- **Calendar API 404 (event not found during update/delete)** → spoken: "I couldn't
  find that event. It may have already been removed."
- **`dateparser` fails to parse date expression** → spoken: "I couldn't understand
  that date. Could you say it differently, for example 'tomorrow at 2pm'?"; no write
  attempted.
- **`dateparser` resolves date in the past** → spoken: "That time has already passed.
  Did you mean next week?" Confirmation gate not opened.
- **All-day event** → `start.date` / `end.date` fields in API response (no `dateTime`);
  `all_day=True` on `CalendarEvent`; frontend renders without time, only date.
- **`pending_calendar_op` TTL expires** → same pattern as `pending_email_send`: state
  cleared, `calendar_op_done{success:false}` broadcast, notification emitted, next
  utterance processed as fresh turn.
- **Ambiguous delete** ("cancel my meeting" with 2+ meetings today) → orchestrator
  context lists all events; OpenClaw asks for disambiguation ("Which one — the 2pm or
  the 4pm?"); `pending_calendar_op` not yet set until user specifies.
- **Poller network timeout** → wrapped in `try/except` with backoff; consecutive
  failure counter; after 3 failures interval triples; resets on next success.
- **Concurrent create + immediate list** → poller runs again after confirmed write
  to force a fresh `calendar_state` broadcast before the user can see stale data.
- **Recurring event** → `is_recurring=True` on `CalendarEvent`; update/delete are
  applied only to the single instance (`instances()` API endpoint not used; spec notes
  this is instance-only and cannot modify the series — spoken: "Note: this only affects
  this occurrence, not the full series.").
- **No events returned** → `calendar_state` broadcast with `events: []`; AgendaPanel
  shows "Keine Termine heute" (existing compact fallback).
- **Raspberry Pi / low memory** → `dateparser` is a moderate dependency; verify import
  time is acceptable in smoke test; `asyncio.to_thread` keeps event loop unblocked.
- **User speaks "yes" for something else while `pending_calendar_op` is set** →
  `_handle_calendar_confirm` is invoked first; only CONFIRM or CANCEL words consume
  the turn; other words leave `pending` intact and return `False` — pipeline falls
  through to normal processing (turn is interpreted as regular speech, not consumed).
- **Multiple connected clients** → `broadcast_*` sends to all; `pending_calendar_op`
  is per-connection `id(ws)` keyed state so each connection has its own confirmation
  window independently.

## Acceptance Criteria

1. `GoogleCalendarClient.list_events("primary")` returns correctly typed `CalendarEvent`
   objects for an account with known events; mock test asserts field mapping for both
   timed (`dateTime`) and all-day (`date`) API responses.
2. `GoogleCalendarClient.create_event(title, start, end)` calls
   `service.events().insert()` with correct JSON body; returned object's `id` matches
   the mock API response.
3. `GoogleCalendarClient.update_event(event_id, start=...)` performs a patch-style
   update via `events().update()` and returns the updated `CalendarEvent`.
4. `GoogleCalendarClient.delete_event(event_id)` calls `events().delete()` exactly
   once; raises `CalendarClientError` (not an unhandled exception) when the API
   returns 404.
5. `_start_calendar_poller` broadcasts `calendar_state` within 60 s of startup;
   backs off to 180 s after 3 consecutive API failures without crashing.
6. Calendar poller publishes `calendar_event_approaching` to `EventBus` with correct
   `starts_in_minutes` values (10, 5, 1) for an event exactly 10 minutes away in a
   unit test with a mocked clock.
7. `_handle_calendar_confirm` with `pending_calendar_op` set: confirm word consumes
   the turn (returns `True`), triggers `create_event`, broadcasts `calendar_op_done
   {success:true}`, and clears `pending_calendar_op`.
8. `_handle_calendar_confirm` with `pending_calendar_op` set: cancel word discards
   the op, broadcasts `calendar_op_done{success:false}`, clears state, returns `True`.
9. `_handle_calendar_confirm` with `pending_calendar_op` set past 60 s TTL: clears
   state, broadcasts `calendar_op_done{success:false}`, returns `False` so the
   utterance proceeds as a normal turn.
10. Intent parser classifies "What's on my calendar tomorrow?" → `CALENDAR_LIST`
    and "schedule a team standup Friday at 10am" → `CALENDAR_CREATE` with
    confidence ≥ 0.7 in both en and de variants.
11. `dateparser.parse("tomorrow 2pm")` in orchestrator context produces a `datetime`
    within 1 s of the expected value; "in 3 hours" and "Friday 10am" likewise resolve
    correctly (mock `datetime.now`).
12. `AgendaPanel` renders an injected `CalendarEvent` list (no mock import); compact
    mode shows next event title and "in N min"; expanded mode shows up to 4 events
    with formatted time ranges. Vitest snapshot test passes.
13. `subscribeCalendarState` in `useWebSocket` fires its listener when a
    `calendar_state` WS message is received; `subscribeCalendarOpDone` fires on
    `calendar_op_done`. Verified in Vitest hook test.
14. `get_calendar_client()` returns the same singleton on repeated calls; a fresh
    import after module reset constructs a new instance (mirrors `get_gmail_client`
    test).

## Implementation Plan

1. `backend-dev` → create `src/integrations/google/calendar_client.py` with
   `CalendarEvent` dataclass, `CalendarClientError`, `GoogleCalendarClient` (lazy
   `_get_service` with `asyncio.Lock`, `list_events`, `create_event`, `update_event`,
   `delete_event`, `_parse_event` helper), and `get_calendar_client()` factory.
2. `backend-dev` → update `src/integrations/google/__init__.py` to export
   `GoogleCalendarClient`, `CalendarEvent`, `CalendarClientError`,
   `get_calendar_client`.
3. `backend-dev` → add `dateparser>=1.2.0` to `requirements.txt`; add `calendar:`
   section to `config/config.yaml` per the schema above.
4. `backend-dev` → add `CALENDAR_LIST`, `CALENDAR_CREATE`, `CALENDAR_UPDATE`,
   `CALENDAR_DELETE` to `Intent` enum and `INTENT_KEYWORDS` dict (en + de patterns)
   in `src/brain/intent_parser.py`.
5. `backend-dev` → add `_CALENDAR_INTENTS` frozenset and `_build_calendar_context`
   method to `src/brain/orchestrator.py`; wire it into the main dispatch path
   alongside the existing `_EMAIL_INTENTS` pattern.
6. `backend-dev` → add to `src/api/ws_server.py`:
   - `get_calendar_client()` lazy proxy
   - `broadcast_calendar_state`, `broadcast_calendar_op_preview`,
     `broadcast_calendar_op_done` broadcaster functions
   - `_CALENDAR_CONFIRM_RE` / `_CALENDAR_CANCEL_RE` compiled patterns
   - `_handle_calendar_confirm(ws, text)` confirmation gate (mirrors
     `_handle_email_confirm` structure exactly; uses `pending_calendar_op` in
     `_connection_state`)
   - `_start_calendar_poller(poll_interval)` coroutine (60 s normal, 3× backoff,
     `_first_client_event` wait, EventBus publish for approaching events)
   - Hook poller startup into `start_ws_server` (mirrors `_start_mail_poller` call)
   - Call `_handle_calendar_confirm` from `_run_voice_pipeline_body` before intent
     parsing (after existing `_handle_email_confirm` call)
7. `frontend-dev` → add `CalendarStatePayload`, `CalendarOpPreviewPayload`,
   `CalendarOpDonePayload` types and extend `WsIncoming` union in
   `frontend/src/types.ts`.
8. `frontend-dev` → add `CalendarStateListener`, `CalendarOpPreviewListener`,
   `CalendarOpDoneListener` types; implement `subscribeCalendarState`,
   `subscribeCalendarOpPreview`, `subscribeCalendarOpDone` in
   `frontend/src/hooks/useWebSocket.ts` (mirror existing `subscribeMailState` pattern).
9. `frontend-dev` → update `frontend/src/components/panels/AgendaPanel.tsx` to
   remove the `agendaMock` default and accept live data exclusively; update the
   caller in `frontend/src/App.tsx` to pass `calendarEvents` state fed by
   `subscribeCalendarState`.
10. `tester` → write `tests/integrations/google/test_calendar_client.py`: mock
    `googleapiclient.discovery.build`; cover `list_events` (timed + all-day),
    `create_event` body, `update_event` patch, `delete_event` 204 + 404 error,
    `get_calendar_client` singleton behaviour.
11. `tester` → write `tests/api/test_calendar_poller.py`: mock `get_calendar_client`,
    `asyncio.sleep`, `EventBus`; assert `broadcast_calendar_state` called on success;
    assert backoff after 3 failures; assert `calendar_event_approaching` published at
    correct thresholds with mocked clock.
12. `tester` → write `tests/brain/test_calendar_intent.py`: assert each of the four
    new intents classifies correctly in en + de; assert confidence ≥ 0.7; assert
    negative examples do not match.
13. `tester` → write `tests/api/test_calendar_confirm.py`: assert confirm-word path,
    cancel-word path, TTL-expiry path, ambiguous-word pass-through path.
14. `tester` → write `frontend/src/hooks/__tests__/useWebSocket.calendar.test.ts`
    (Vitest + RTL): inject `calendar_state` and `calendar_op_done` WS messages via
    mock WebSocket; assert subscriber callbacks fire with correct payloads.
15. `tester` → write `frontend/src/components/panels/__tests__/AgendaPanel.test.tsx`
    (Vitest + RTL): render with empty, compact, and 4-event prop sets; assert no
    `agendaMock` import present; snapshot the expanded view.
16. `reviewer` → review entire batch (steps 1–15) against this spec; issue
    `PASS` or `NEEDS_CHANGES`.

## Manual Verification

```bash
# 1. Start backend
PYTHONPATH=src .venv/bin/python -m main

# 2. Confirm calendar poller appears in logs within 60 s
#    Expected: "Calendar poller started (interval=60s)"

# 3. Open frontend (http://localhost:5173) — AgendaPanel should show real events
#    or "Keine Termine heute" if calendar is empty

# 4. Speak: "What's on my calendar today?"
#    Expected: spoken summary of today's events; calendar context visible in
#    loguru DEBUG output under "orchestrator"

# 5. Speak: "Schedule a standup call tomorrow at 9am"
#    Expected: JARVIS reads back the proposed event, AgendaPanel flashes
#    calendar_op_preview; after saying "yes" event appears in Google Calendar
#    within 5 s and AgendaPanel refreshes

# 6. Wait 10 min before a real calendar event (or fake one close to now)
#    Expected: TTS interjection "Sir, your meeting '...' begins in 10 minutes."

# 7. Speak: "Cancel my 9am standup"
#    Expected: JARVIS asks for confirmation; after "yes", event deleted from
#    Google Calendar and AgendaPanel updates on next poll

# 8. Inspect WS frames in browser DevTools → Network → WS:
#    Should see calendar_state frames arriving every ~60 s
```

## Open Questions

1. **Proactive reminder dedup** — if the user barge-ins or the poller fires twice
   within the 5-minute `interjection_cooldown_seconds` window, the 1-minute reminder
   will be suppressed. Is that acceptable, or should meeting reminders bypass the
   global cooldown (like `severity=urgent` already does)? Recommend: treat the 1-min
   reminder as `severity="urgent"` to bypass cooldown. Needs user sign-off.
2. **`dateparser` locale** — `dateparser.parse` defaults to English; for German
   expressions ("morgen um 14 Uhr") it needs `PREFER_LOCALE_DATE_ORDER` or an explicit
   `settings={"PREFER_DAY_OF_MONTH": "first", "DATE_ORDER": "DMY"}`. Confirm whether
   auto-detection via `langdetect` (already available?) is sufficient or if language
   must be pinned from `IntentResult.language`.
3. **Calendar write scope for HUD-only read** — the poller only reads; the
   `calendar.events` write scope is only needed for create/update/delete. Should the
   client request both scopes upfront (simpler, single OAuth flow) or split into
   read-only vs read-write based on whether mutating ops are enabled? Recommend:
   always request both; note this in the consent screen.
4. **`AgendaPanel` date window** — the poller fetches the next 12 h by default
   (`lookahead_hours: 12`). Should the panel show only today's events, or also
   tomorrow's when it's past 6pm? Recommend: always show the next 12 h regardless of
   time of day, so the compact view always has a non-empty "next event." Needs user
   decision.

---

## Revision 4 — 2026-04-18

### Summary of Changes
Complete rewrite of the spec in the required structured format. All previous free-form
sections (Revisions 1–3) are superseded. Key deltas vs Revision 3:

- **Dropped OpenClaw-as-backbone assumption** — Revision 3 concluded OpenClaw would
  handle all calendar CRUD. The upstream constraint has changed: Google OAuth is now a
  JARVIS-native shared foundation (`get_google_oauth_service().build_service(...)`) and
  Gmail already sets the pattern. Calendar follows the same pattern directly.
- **`CalendarProvider` protocol dropped** — Google-only; no abstraction needed.
- **ProactiveScheduler integration concretized** — poller publishes `EventBus` events;
  `proactive.py` itself requires zero changes.
- **Confirmation flow added** — mirrors `_handle_email_confirm` exactly; per-connection
  `pending_calendar_op` state.
- **AgendaPanel wiring added** — `agendaMock` removed; `subscribeCalendarState` hook.
- **dateparser added** — explicit dependency for NL date parsing.
- **14 testable acceptance criteria** added (was 8 in Revision 3, unmeasurable).
- **16-step implementation plan** with exactly one file per step.
- **aiohttp confirmed** — all FastAPI references removed.

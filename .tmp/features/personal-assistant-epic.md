# Feature Spec: Personal Assistant Epic

## Summary
Transform JARVIS into a full personal assistant with email (Gmail) and calendar (Google Calendar) capabilities. This epic coordinates the implementation of child features and defines shared architectural decisions. iCloud CalDAV has been dropped from scope (user decision: security/complexity concerns).

## Goals
- Enable voice-driven email management: read summaries, search by sender/subject, dictate drafts
- Enable Google Calendar management: list events, create/update/delete, natural language scheduling
- Maintain JARVIS's async-first architecture and clean separation of concerns
- Support both desktop and headless (Raspberry Pi) deployments

## Non-Goals
- Sending emails (read-only for Phase A; write capability deferred to Phase B pending user confirmation)
- Calendar sharing or invitation management
- Microsoft 365 / Exchange integration
- Real-time push notifications (polling-based for MVP)

---

## Architectural Decisions

### 1. Agent Structure: Split Agents
**Decision:** Two new agents: `EmailAgent` and `CalendarAgent`

**Rationale:**
- Follows existing pattern (pc_agent, smart_home_agent, search_agent are single-domain)
- Keeps agent complexity manageable
- Allows independent testing and development
- Clear separation of OAuth scopes and error handling

**Implementation:**
```
src/brain/agents/
  email_agent.py      # Gmail operations
  calendar_agent.py   # Unified calendar (Google + iCloud)
```

### 2. Integration Layer Pattern
**Decision:** New `src/integrations/` directory with provider-specific clients

**Structure:**
```
src/integrations/
  __init__.py
  google/
    __init__.py
    oauth.py            # Shared OAuth2 (used by Gmail + GCal)
    gmail_client.py     # Gmail API wrapper
    calendar_client.py  # Google Calendar API wrapper
```

**Rationale:**
- Agents (`src/brain/agents/`) stay thin: orchestration only
- Integration clients handle API specifics, auth, retries
- With OpenClaw adoption, these clients are REPLACED by OpenClaw skills (see Revision 3)

### 3. CalendarProvider Protocol — REMOVED
**Status:** Removed in Revision 3

With iCloud dropped and OpenClaw handling Google Calendar, the multi-provider CalendarProvider protocol adds no value. All calendar operations route through OpenClaw's built-in Google Calendar skill.

The `CalendarEvent` dataclass is retained as a JARVIS-internal representation for HUD AgendaPanel rendering, but is populated from OpenClaw responses, not from a JARVIS-native provider protocol.

### 4. Headless OAuth Strategy — HANDLED BY OPENCLAW
**Status:** Superseded in Revision 3

With OpenClaw as the backbone, OAuth flows for Google services (Gmail, Calendar) are handled internally by OpenClaw. JARVIS does not manage Google OAuth tokens.

For headless (RPi) setup, OpenClaw's onboarding flow handles authentication. If OpenClaw is not authenticated, JARVIS speaks: "Sir, I cannot reach your Google services. Please run openclaw onboard on the terminal."

### 5. Intent Taxonomy
**New Intent enum values:**

| Intent | Keywords (EN) | Keywords (DE) |
|--------|--------------|---------------|
| `EMAIL_READ` | email, mail, inbox, unread, messages | email, post, posteingang, ungelesen, nachrichten |
| `EMAIL_SEARCH` | email from, mail about, message from | email von, nachricht von, mail über |
| `CALENDAR_LIST` | calendar, schedule, appointments, what's on, events | kalender, termine, was steht an |
| `CALENDAR_CREATE` | schedule, add event, create meeting, book | termin erstellen, eintragen, meeting anlegen |
| `CALENDAR_UPDATE` | move meeting, reschedule, change event | termin verschieben, verlegen, ändern |
| `CALENDAR_DELETE` | cancel meeting, delete event, remove appointment | termin absagen, löschen, streichen |

**Routing:**
- `EMAIL_*` intents -> `email` agent
- `CALENDAR_*` intents -> `calendar` agent

### 6. Orchestrator Updates — SIMPLIFIED
**Status:** Updated in Revision 3

With OpenClaw as the backbone, EMAIL_* and CALENDAR_* intents route directly to OpenClaw rather than JARVIS-native agents. The Orchestrator becomes a thin router:

```python
# Intents routed to OpenClaw
OPENCLAW_INTENTS = {
    Intent.EMAIL_READ, Intent.EMAIL_SEARCH, Intent.EMAIL_COMPOSE,
    Intent.CALENDAR_LIST, Intent.CALENDAR_CREATE, Intent.CALENDAR_UPDATE, Intent.CALENDAR_DELETE,
}

# In process():
if intent in OPENCLAW_INTENTS:
    return await openclaw_client.query_agent(text)
```

No JARVIS-native `EmailAgent` or `CalendarAgent` is required.

---

## Voice UX Patterns

### Email Summaries
Emails are long. Pattern:
1. Summarize to 2-3 sentences max
2. Offer drill-down: "Would you like me to read the full message?"
3. For lists: "You have 3 unread emails. First, from John about the project deadline..."

### Calendar Events
1. Group by day: "Tomorrow you have 2 meetings. At 10am, weekly standup. At 2pm, design review."
2. For creation, confirm: "I'll schedule a meeting with Sarah tomorrow at 3pm for one hour. Should I proceed?"
3. Natural language parsing via Claude: "lunch with Bob next Tuesday" -> parsed datetime + title

### Error Handling
- Auth expired: "I need you to re-authenticate with Google. Please check the terminal."
- API error: "I couldn't access your calendar. Would you like me to try again?"
- Ambiguous: "Which calendar should I add this to: Work or Personal?"

---

## Configuration Schema

### config.yaml additions
```yaml
email:
  enabled: true
  provider: "openclaw"  # OpenClaw handles Gmail
  max_unread_summary: 5
  summary_length: 100  # chars per email summary

calendar:
  enabled: true
  provider: "openclaw"  # OpenClaw handles Google Calendar
  default_lookahead_days: 7
  max_events_per_query: 20
```

### .env.example additions
```bash
# Google OAuth handled by OpenClaw - no JARVIS-side credentials needed
# OpenClaw uses its own authentication via `openclaw onboard`
```

---

## Dependencies Between Child Specs

```
openclaw-integration.md  <-- PREREQUISITE FOR ALL
       |
       +---> gmail-integration.md (voice routing + HUD only)
       |
       +---> google-calendar-integration.md (voice routing + HUD only)
```

**Implementation Order:**
1. `openclaw-integration.md` - must be first (OpenClaw is the backbone)
2. `gmail-integration.md` - voice UX + MailPanel only (OpenClaw handles API)
3. `google-calendar-integration.md` - voice UX + AgendaPanel only (OpenClaw handles API)

**Removed from scope:**
- `google-oauth-shared.md` - SKIP (OpenClaw handles OAuth)
- `icloud-calendar-integration.md` - DELETED (user decision)

---

## Acceptance Criteria (Epic Level)

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | User says "check my email" -> receives spoken summary of top 5 unread | Integration test with mocked Gmail API |
| 2 | User says "what's on my calendar tomorrow" -> receives spoken event list | Integration test with mocked GCal API |
| 3 | User says "schedule a meeting with Bob tomorrow at 2pm" -> event created in Google Calendar | Integration test verifying API call payload |
| 4 | User says "cancel my 3pm meeting" -> event deleted | Integration test verifying delete call |
| 5 | Both German and English trigger phrases work | Unit tests on intent_parser |
| 6 | OAuth device flow completes successfully on headless device | Manual test on RPi |
| ~~7~~ | ~~iCloud events appear in unified calendar view~~ | REMOVED — iCloud dropped |
| 8 | Expired token triggers re-auth flow without crash | Integration test simulating 401 |

---

## Open Questions — ALL RESOLVED

1. **Email write access:** ✓ RESOLVED — Sending allowed with strict voice-confirmation flow (see `gmail-integration.md` Revision 2)

2. **iCloud priority:** ✓ RESOLVED (Revision 3) — iCloud Calendar DROPPED from scope (user decision: security/complexity concerns)

3. **Calendar merge default:** ✓ RESOLVED (Revision 3) — N/A, single provider (Google via OpenClaw)

4. **Event creation default calendar:** ✓ RESOLVED (Revision 3) — Google Calendar only (via OpenClaw)

---

## Revision 2 — 2026-04-16

### Summary of Changes
This revision incorporates user decisions on email sending, iCloud priority, and dual-write defaults.

### Email Write Access — NOW IN SCOPE

Email sending is allowed but strictly gated by a multi-step voice-confirmation flow:

1. JARVIS drafts email based on user request
2. Draft renders in HUD for visual preview
3. JARVIS asks "Shall I send this, Sir?"
4. User must say explicit confirmation (e.g., "ja senden", "yes send")
5. Only then does JARVIS send

See `gmail-integration.md` Revision 2 for full implementation details.

### Non-Goals — Updated
Remove from Non-Goals:
- ~~Sending emails (read-only for Phase A)~~ — NOW IN SCOPE with gated confirmation

### ~~iCloud Calendar — MVP CONFIRMED~~ — SUPERSEDED
See Revision 3: iCloud Calendar dropped from scope.

### ~~Calendar Merge Default~~ — SUPERSEDED
See Revision 3: Single provider (Google via OpenClaw).

### ~~Event Creation: Dual-Write Default~~ — SUPERSEDED
See Revision 3: Google Calendar only via OpenClaw.

### Cross-References
- `gmail-integration.md` — Email send flow details (voice UX layer only)
- `google-calendar-integration.md` — Calendar voice UX layer only
- ~~`icloud-calendar-integration.md`~~ — DELETED
- `jarvis-memory-db.md` — Event logging for calendar operations
- `openclaw-integration.md` — Backend for Gmail + Calendar

---

**Status:** Planned — awaiting implementation authorization

---

## Revision 3 — 2026-04-16

### Summary of Changes
This revision implements two major user decisions:
1. **Drop iCloud CalDAV entirely** — user decision: security/community-skill concerns
2. **Full OpenClaw adoption** — OpenClaw is the complete backbone for Gmail + Google Calendar

### iCloud Calendar — REMOVED FROM SCOPE

**User Decision:** "iCloud raus — will ich nicht wenn unsicher / community-skill"

**Actions Taken:**
- `icloud-calendar-integration.md` spec file DELETED
- All iCloud references removed from this epic
- Dual-write logic removed (no longer needed with single provider)
- CalendarProvider protocol REMOVED (no multi-provider abstraction needed)

### OpenClaw as Full Backbone — COMMITTED

**User Decision:** "JARVIS soll auf jeden Fall alles von OpenClaw benutzen können"

OpenClaw handles ALL Gmail and Google Calendar operations. JARVIS has NO direct API client code for these services.

### What OpenClaw Handles (100%)
| Feature | OpenClaw Skill | Notes |
|---------|----------------|-------|
| Gmail read/search | Built-in Gmail | Full coverage |
| Gmail send | Built-in Gmail | Full coverage |
| Gmail drafts | Built-in Gmail | Full coverage |
| Google Calendar CRUD | Built-in Calendar | Full coverage |
| OAuth flows | OpenClaw internal | No JARVIS OAuth needed |

### What Stays JARVIS-Native
1. **Voice intent detection** — routing user speech to the right OpenClaw skill with params
2. **HUD Panels** — AgendaPanel, MailPanel (React visualization layer)
3. **Voice UX** — Email send-confirmation flow, calendar ambiguity resolution, spoken responses
4. **WebSocket protocol** — Frontend receives data via JARVIS WebSocket, not OpenClaw directly

### Implementation Plan — Updated

| Spec | Status | Notes |
|------|--------|-------|
| `google-oauth-shared.md` | SKIP | OpenClaw handles OAuth |
| `gmail-integration.md` | Voice routing + MailPanel only | No JARVIS-side Gmail client |
| `google-calendar-integration.md` | Voice routing + AgendaPanel only | No JARVIS-side Calendar client |
| `icloud-calendar-integration.md` | DELETED | User decision |
| CalendarProvider protocol | REMOVED | Single provider, no abstraction needed |

### Prerequisite
- `openclaw-integration.md` MUST be implemented FIRST

### Estimated Implementation Reduction
- Original plan (pre-OpenClaw): ~10-14 hours
- With OpenClaw backbone: ~4-6 hours (voice UX + HUD panels only)
- **Reduction: ~55-60%**

---

## Files Modified (Epic Level) — Updated for OpenClaw

| File | Change |
|------|--------|
| `src/brain/intent_parser.py` | Add 6 new Intent enum values + keyword patterns |
| `src/brain/orchestrator.py` | Route EMAIL_* and CALENDAR_* intents to OpenClaw |
| `config/config.yaml` | Add email + calendar sections (provider: "openclaw") |
| `.env.example` | No new credentials (OpenClaw handles auth) |

## Files Created (Epic Level) — Dramatically Reduced

| File | Purpose |
|------|---------|
| `frontend/src/components/panels/AgendaPanel.tsx` | Calendar HUD panel |
| `frontend/src/components/panels/MailPanel.tsx` | Email HUD panel |
| `frontend/src/hooks/useAgenda.ts` | Agenda state hook |
| `frontend/src/hooks/useMail.ts` | Mail state hook |

**Files NOT Created (OpenClaw handles):**
- ~~`src/integrations/google/oauth.py`~~ — OpenClaw handles
- ~~`src/integrations/google/gmail_client.py`~~ — OpenClaw handles
- ~~`src/integrations/google/calendar_client.py`~~ — OpenClaw handles
- ~~`src/integrations/icloud/`~~ — iCloud dropped
- ~~`src/integrations/calendar/`~~ — No multi-provider abstraction needed
- ~~`src/brain/agents/email_agent.py`~~ — OpenClaw handles
- ~~`src/brain/agents/calendar_agent.py`~~ — OpenClaw handles

---

## Implementation Plan — Updated for OpenClaw

Implement in this order:

1. **openclaw-integration.md** (PREREQUISITE)
   - Must be implemented first
   - See that spec for details

2. **gmail-integration.md** (est. 1-2 hours)
   - Voice intent routing to OpenClaw
   - MailPanel HUD component
   - Email send-confirmation voice UX
   - Intent parser updates for EMAIL_*

3. **google-calendar-integration.md** (est. 1-2 hours)
   - Voice intent routing to OpenClaw
   - AgendaPanel HUD component
   - Calendar ambiguity resolution voice UX
   - Intent parser updates for CALENDAR_*

**Removed from implementation:**
- ~~google-oauth-shared.md~~ — SKIP (OpenClaw handles)
- ~~icloud-calendar-integration.md~~ — DELETED

**Total estimated implementation: 4-6 hours** (down from 10-14 hours)

---

## References

- Prerequisite: `.tmp/features/openclaw-integration.md`
- Child spec: `.tmp/features/gmail-integration.md`
- Child spec: `.tmp/features/google-calendar-integration.md`
- ~~Child spec: `.tmp/features/google-oauth-shared.md`~~ — SKIP (OpenClaw handles OAuth)
- ~~Child spec: `.tmp/features/icloud-calendar-integration.md`~~ — DELETED

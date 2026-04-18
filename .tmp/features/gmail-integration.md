# Feature: Gmail Integration

## Status
Planned — awaiting implementation authorization

**What is already built (pre-condition):**
- `src/integrations/google/oauth.py` — `GoogleOAuthService` singleton with `get_credentials()`,
  `is_authenticated()`, `revoke()`, and `build_service()` is DONE (Batch 1).
- `frontend/src/components/panels/MailPanel.tsx` — renders `MailMessage[]` with compact/expanded
  modes; currently wired to `mailMock`. Live wiring via WS is part of this batch.

**What this batch (Batch 2) delivers:**
- `src/integrations/google/gmail_client.py` — Gmail API wrapper (read + send via drafts).
- Intent keywords for EMAIL_READ, EMAIL_SEARCH, EMAIL_COMPOSE in `src/brain/intent_parser.py`.
- Orchestrator passthrough so email intents hit the OpenClaw chat path (no separate agent class).
- WS message types for mail state push and gated send confirmation flow.
- Live `MailPanel.tsx` wired to `mail_state` WS messages.
- Polling coroutine in `ws_server.py` (120 s default, unread count only).
- Full test coverage with mocked `googleapiclient.discovery.Resource`.

---

## Goal
Let users read unread email summaries, search by sender or subject, and send emails — all by
voice — with the HUD MailPanel showing live unread state. Sending is strictly gated: JARVIS reads
back the draft preview and waits for explicit verbal confirmation before executing the send.

## Scope

### In scope
- List and summarise unread emails (up to 5 by default, configurable).
- Search emails by sender name or subject keyword.
- Read a full message body on demand (summarised to ~100 words via OpenClaw).
- Compose and send emails via a gated two-step voice confirmation flow.
- Draft creation, preview broadcast to HUD, explicit "ja senden" / "yes send it" confirmation
  before the actual Gmail API send call.
- Silent abort if no confirmation within 10 s or user says anything other than a whitelisted
  confirm phrase.
- Polling unread count every 120 s, pushed to frontend via `mail_state` WS message.
- Live wiring of `MailPanel.tsx` to `mail_state` WS messages (replaces mock data).
- VIP sender flag: configurable sender list; VIP messages shown with accent colour in panel.

### Out of scope
- Attachment handling.
- Label / folder management.
- Push/webhook notifications (polling only for this batch).
- Mark-as-read side effects on the Gmail side (reading a mail via voice does not change
  its unread flag).
- Multi-account support.
- Auto-reply or any send path not triggered by explicit user voice command.

---

## User Flow

### Read flow
1. User says "Check my email" or "Zeig meine E-Mails".
2. Intent parser classifies `EMAIL_READ`; orchestrator falls through to OpenClaw chat path.
3. `GmailClient.list_unread()` is called; results passed as context to the OpenClaw prompt.
4. OpenClaw generates a concise spoken summary (max 5 emails, ~2 sentences each).
5. JARVIS speaks the summary and offers drill-down. HUD MailPanel already shows live state
   from polling.

### Search flow
1. User says "Do I have emails from Sarah?" or "E-Mails von Sarah suchen".
2. Intent parser classifies `EMAIL_SEARCH` and extracts `sender` parameter.
3. `GmailClient.search()` called with assembled Gmail query; results summarised via OpenClaw.
4. JARVIS speaks the result. Offers "Soll ich eine davon vorlesen?" follow-up.

### Send flow (gated confirmation — REQUIRED)
1. User says "Send an email to Sarah about tomorrow's meeting".
2. Intent parser classifies `EMAIL_COMPOSE`.
3. Orchestrator passes intent + text to OpenClaw, which drafts `to`, `subject`, `body`.
4. Backend calls `GmailClient.create_draft()` and broadcasts `email_draft_preview` WS message.
5. JARVIS speaks: "Hier der Entwurf: An Sarah Johnson, Betreff 'Treffen morgen', […preview…].
   Soll ich das senden, Sir?"
6. Backend enters a 10 s confirmation wait, listening for the next STT turn.
7. User says "Ja, senden." — matched against whitelist → `GmailClient.send_draft()` called.
   JARVIS speaks: "Gesendet, Sir." `email_send_done` broadcast to HUD.
8. If user says anything else or 10 s elapse without input → draft deleted,
   JARVIS speaks: "Abgebrochen, Sir." `email_send_done` broadcast with `success: false`.

---

## Architecture

### Modules touched
- Backend:
  - `src/integrations/google/gmail_client.py` (new)
  - `src/brain/intent_parser.py` (add `EMAIL_READ`, `EMAIL_SEARCH`, `EMAIL_COMPOSE` intents
    and keyword patterns; add `_extract_email_params()` helper)
  - `src/brain/orchestrator.py` (add `EMAIL_*` intents to `_LOCAL_INTENTS`? — see Open
    Questions; for now email intents fall through to the OpenClaw chat path, which is the
    current default for anything not in `_LOCAL_INTENTS`)
  - `src/api/ws_server.py` (add `_start_mail_poller()` background task; add
    `_handle_email_confirm()` turn handler; add `broadcast_mail_state()` helper)
- Frontend:
  - `frontend/src/types.ts` (add `MailStatePayload`, `EmailDraftPreviewPayload`,
    `EmailSendDonePayload` to `WsIncoming`)
  - `frontend/src/components/panels/MailPanel.tsx` (replace `mailMock` default with WS-driven
    state passed from `App.tsx` or a hook; add draft-preview sub-view)
  - `frontend/src/hooks/useWebSocket.ts` (handle new `mail_state`, `email_draft_preview`,
    `email_send_done` message types)
- Config: new `gmail:` section in `config/config.yaml`
- Env: no new vars (OAuth already covered by `GOOGLE_OAUTH_CLIENT_ID` /
  `GOOGLE_OAUTH_CLIENT_SECRET`)

### Data flow

```
[User voice] "Check my email"
      │
[STT] → text
      │
[IntentParser] → EMAIL_READ / EMAIL_SEARCH / EMAIL_COMPOSE
      │
[Orchestrator.process_stream()]
      │
      ├─ EMAIL_READ / EMAIL_SEARCH / (EMAIL_COMPOSE draft phase)
      │     → OpenClaw chat path (current default for non-local intents)
      │       OpenClaw calls GmailClient helpers as context-building tools
      │       or ws_server injects gmail results into the prompt text
      │
      └─ EMAIL_COMPOSE (confirm phase — 10 s window)
            → ws_server._handle_email_confirm() intercepts next STT turn
            → whitelist match → GmailClient.send_draft()
            → broadcast email_send_done + TTS spoken confirmation

Polling (background, 120 s):
[ws_server._start_mail_poller()]
      → GmailClient.get_unread_count()
      → broadcast_mail_state({messages: [...], unread_count: N})
      → MailPanel.tsx re-renders with live data
```

### Interfaces

**Python — `src/integrations/google/gmail_client.py`**

```
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND_SCOPE     = "https://www.googleapis.com/auth/gmail.send"


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    subject: str
    sender: str          # display name
    sender_email: str
    recipient: str
    received_at: datetime
    snippet: str         # Gmail 100-char preview
    body_text: str | None   # loaded on demand
    is_unread: bool
    is_vip: bool         # True if sender_email in config vip_senders list


@dataclass
class EmailDraft:
    id: str
    to: str
    subject: str
    body: str
    created_at: datetime


class GmailClientError(Exception):
    spoken_message: str


class GmailClient:
    def __init__(self, oauth_service: GoogleOAuthService, vip_senders: list[str]) -> None: ...

    async def list_unread(
        self,
        max_results: int = 5,
        sender: str | None = None,
    ) -> list[EmailMessage]: ...

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[EmailMessage]: ...

    async def get_message(
        self,
        message_id: str,
        include_body: bool = True,
    ) -> EmailMessage: ...

    async def get_unread_count(self) -> int: ...
        # Lightweight: messages().list(labelIds=["UNREAD"], maxResults=1, fields="resultSizeEstimate")

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> EmailDraft: ...

    async def send_draft(self, draft_id: str) -> str: ...
        # Returns sent message ID. Raises GmailClientError on failure.

    async def delete_draft(self, draft_id: str) -> bool: ...
```

**WebSocket messages — additions to `WsIncoming` in `frontend/src/types.ts`**

| Type | Direction | Payload |
|------|-----------|---------|
| `mail_state` | BE → FE | `{ messages: MailMessage[]; unread_count: number }` |
| `email_draft_preview` | BE → FE | `{ draft_id: string; to: string; subject: string; body_preview: string; created_at: string }` |
| `email_send_done` | BE → FE | `{ draft_id: string; success: boolean; message_id?: string; error?: string }` |

`MailMessage` already exists in `frontend/src/types.ts` — no shape change needed; `is_vip` maps
to the existing `isVip` field. The `mail_state` payload uses camelCase keys matching the
existing type.

**aiohttp broadcast helpers — `src/api/ws_server.py`**

```
async def broadcast_mail_state(messages: list[dict], unread_count: int) -> None: ...
async def broadcast_email_draft_preview(payload: dict) -> None: ...
async def broadcast_email_send_done(payload: dict) -> None: ...
```

No new HTTP endpoints — all communication is over the existing aiohttp WS on `:8765`.

### External dependencies

No new pip packages. `google-api-python-client`, `google-auth`, `google-auth-oauthlib` are
already present from Batch 1.

No new npm packages.

---

## Edge Cases & Failure Modes

- **OAuth not yet completed (first run)** → `get_credentials()` raises `GoogleOAuthFlowError`;
  `GmailClient` catches it, JARVIS speaks "Ich brauche Zugriff auf Gmail — bitte
  authentifiziere dich im Terminal." Poller skips the cycle and retries next interval.
- **Token expired, refresh fails** → `GoogleOAuthTokenError` propagated; same spoken fallback.
  Poller backs off to 5-minute interval after three consecutive failures.
- **Gmail API rate limit (429)** → `GmailClientError` with spoken "Gmail ist gerade nicht
  erreichbar, bitte kurz warten." Poller backs off.
- **Network error during list / search** → `GmailClientError`; JARVIS speaks fallback and
  continues. Poller does not crash.
- **Empty inbox / zero results** → `list_unread()` returns `[]`; spoken response "Keine
  ungelesenen E-Mails, Sir."
- **Compose: OpenClaw returns incomplete draft fields** (`to` missing) → `GmailClient` raises
  before creating the draft; JARVIS asks user to repeat the request with more detail.
- **Compose: user says "senden" before draft preview has been read back** → the 10 s
  confirmation window is not yet open; the word "senden" is not on the active confirmation
  whitelist, so it routes as a new intent. JARVIS clarifies before proceeding.
- **Confirmation window expires (10 s silence)** → `_handle_email_confirm()` resolves with
  timeout; backend calls `delete_draft()`, broadcasts `email_send_done` with `success: false`.
  JARVIS speaks "Abgebrochen, Sir."
- **User says non-confirm phrase during window** → same abort path as timeout.
- **`send_draft()` fails after confirmation** → `GmailClientError`; JARVIS speaks "Senden
  fehlgeschlagen, Sir. Die Nachricht wurde nicht gesendet." `email_send_done` broadcast with
  `success: false, error: <message>`.
- **`delete_draft()` fails on abort** → logged as warning; non-fatal. Draft may remain as
  orphan in Gmail — acceptable for this scope (no label management in scope).
- **MailPanel receives `mail_state` while draft preview is open** → draft preview sub-view
  takes precedence; the mail list update is applied silently in state, re-rendered when
  the draft view is dismissed.
- **Raspberry Pi / headless** → no display-specific code in this batch; headless OAuth path
  already handled by Batch 1.
- **Max results exceeds Gmail API page size (500)** → cap `max_results` at 50 in
  `GmailClient`; documented constraint.
- **VIP list is empty** → `is_vip` is always `False`; no change in rendering logic needed.

---

## Acceptance Criteria

1. `GmailClient.list_unread(max_results=5)` returns a list of `EmailMessage` objects with
   correct `id`, `subject`, `sender_email`, `is_unread=True`, using a mocked
   `googleapiclient.discovery.Resource` — verified by unit test.
2. `GmailClient.search(query="from:sarah")` calls
   `service.users().messages().list(userId="me", q="from:sarah", ...)` — verified by
   asserting the mock call arguments in unit test.
3. `GmailClient.get_unread_count()` executes a single API call and returns an integer —
   verified by unit test with mocked `.execute()` returning `{"resultSizeEstimate": 7}`.
4. `GmailClient.create_draft()` calls `service.users().drafts().create()` with a base64-encoded
   RFC 2822 message and returns an `EmailDraft` — verified by unit test.
5. `GmailClient.send_draft(draft_id)` calls `service.users().drafts().send()` — verified by
   unit test asserting the mock call and correct draft_id in request body.
6. `GmailClient.delete_draft(draft_id)` calls `service.users().drafts().delete()` — unit test.
7. Intent parser classifies "check my email" as `EMAIL_READ` with confidence ≥ 0.8 — unit test.
8. Intent parser classifies "zeig meine E-Mails" as `EMAIL_READ` with confidence ≥ 0.8 — unit test.
9. Intent parser classifies "email from Sarah" as `EMAIL_SEARCH` and extracts
   `params["sender"] == "Sarah"` — unit test.
10. Intent parser classifies "send an email to John about the project" as `EMAIL_COMPOSE`
    and extracts a non-empty `params["to"]` hint — unit test.
11. The polling coroutine in `ws_server.py` calls `GmailClient.get_unread_count()` and
    broadcasts a `mail_state` WS message at the configured interval — verified by async unit
    test with mocked `GmailClient` and mocked `broadcast_mail_state`.
12. Backend broadcasts `email_draft_preview` WS message synchronously after `create_draft()`
    succeeds — verified by integration test asserting the message is in the WS queue before
    JARVIS speaks the read-back.
13. Backend does NOT call `send_draft()` if no confirmation arrives within 10 s; calls
    `delete_draft()` and broadcasts `email_send_done` with `success: false` — async unit test.
14. Backend calls `send_draft()` when the next STT turn matches a whitelisted confirm phrase
    ("ja senden", "yes send it", "confirm", "go ahead", "senden", "send it") — async unit test.
15. Backend does NOT call `send_draft()` when the next STT turn is a non-confirm phrase
    ("nein", "cancel", "stop") — async unit test.
16. `MailPanel.tsx` renders live `MailMessage` data received via `mail_state` WS message
    instead of `mailMock` when the WS connection is active — Vitest + RTL component test
    asserting mock-data sender names are absent and live-data sender names are present.
17. `MailPanel.tsx` renders a draft-preview sub-view when an `email_draft_preview` WS message
    arrives — Vitest + RTL component test asserting `to` and `subject` text are visible.
18. `GoogleOAuthError` during `GmailClient` initialisation does not crash the server; the
    polling task logs the error and skips the cycle — async unit test.

---

## Implementation Plan

1. `backend-dev` → add `gmail:` section to `config/config.yaml` with keys:
   `enabled: true`, `max_unread_summary: 5`, `poll_interval_seconds: 120`,
   `send_confirm_timeout_seconds: 10`, `vip_senders: []`.

2. `backend-dev` → create `src/integrations/google/gmail_client.py` implementing
   `EmailMessage`, `EmailDraft`, `GmailClientError`, and `GmailClient` with the six async
   public methods specified in the Interfaces section. Use
   `get_google_oauth_service().build_service("gmail", "v1", scopes=[GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE])`
   as the sole client factory. All Gmail API calls wrapped in `asyncio.to_thread`.

3. `backend-dev` → add `EMAIL_READ`, `EMAIL_SEARCH`, `EMAIL_COMPOSE` to `Intent` enum in
   `src/brain/intent_parser.py`; add EN + DE keyword patterns; add `_extract_email_params()`
   private helper that extracts `sender`, `subject`, and a `to` hint from the raw text.

4. `backend-dev` → add `broadcast_mail_state()`, `broadcast_email_draft_preview()`,
   `broadcast_email_send_done()` helper functions to `src/api/ws_server.py` following the
   existing `broadcast_*` pattern (JSON-serialise payload, call `_broadcast()`).

5. `backend-dev` → add `_start_mail_poller()` background coroutine to `src/api/ws_server.py`.
   On each cycle: call `GmailClient.list_unread(max_results=5)`, call
   `broadcast_mail_state(messages, unread_count)`. Handle `GmailClientError` and
   `GoogleOAuthError` with backoff (triple interval after 3 consecutive failures). Register
   the task in `start_ws_server()` alongside the existing metrics task.

6. `backend-dev` → add `_handle_email_confirm()` coroutine to `src/api/ws_server.py`. Called
   from the voice pipeline after JARVIS reads back a draft preview. Opens a 10 s window
   waiting on the next STT result (use an `asyncio.Event` set by the existing audio handler).
   On whitelist match → `send_draft()`; on timeout or non-match → `delete_draft()`. Broadcasts
   `email_send_done` in both paths. Speaks confirmation via `broadcast_audio`.

7. `frontend-dev` → add `MailStatePayload`, `EmailDraftPreviewPayload`, `EmailSendDonePayload`
   types to `frontend/src/types.ts` and add the three new message variants to `WsIncoming`.

8. `frontend-dev` → update `frontend/src/hooks/useWebSocket.ts` to handle `mail_state`,
   `email_draft_preview`, and `email_send_done` message types; expose `mailMessages`,
   `unreadCount`, `draftPreview` from the hook.

9. `frontend-dev` → update `frontend/src/components/panels/MailPanel.tsx` to accept live
   `messages` and `draftPreview` via props (remove `mailMock` as default); add a
   `DraftPreview` sub-component rendered when `draftPreview` is non-null, showing `to`,
   `subject`, `body_preview` in the existing HUD design language.

10. `tester` → create `tests/integrations/google/test_gmail_client.py` covering acceptance
    criteria 1–6 and 18. Mock via `unittest.mock.MagicMock`: construct the mock as
    `mock_service = MagicMock()` and patch `googleapiclient.discovery.build` to return it;
    chain calls as `mock_service.users().messages().list().execute.return_value = {...}`.

11. `tester` → create `tests/brain/test_intent_parser_email.py` covering acceptance criteria
    7–10. Use the live `IntentParser` instance; no mocking needed.

12. `tester` → create `tests/api/test_mail_poller.py` covering acceptance criterion 11.
    Use `pytest-asyncio`; mock `GmailClient` and `broadcast_mail_state`.

13. `tester` → create `tests/api/test_email_confirm.py` covering acceptance criteria 12–15.
    Use `pytest-asyncio`; mock `GmailClient.send_draft`, `GmailClient.delete_draft`, and
    `broadcast_*` helpers.

14. `tester` → create `frontend/src/hooks/__tests__/useWebSocket.mailMessages.test.ts`
    covering acceptance criterion 16 (hook emits live `mailMessages` on `mail_state` message).
    Use Vitest + RTL `renderHook`; supply a mock WS server via `msw` or direct event dispatch.

15. `tester` → create `frontend/src/components/panels/__tests__/MailPanel.test.tsx` covering
    acceptance criteria 16–17. Render `MailPanel` with live props and with a `draftPreview`
    prop; assert mock-data names are absent, live names present, draft sub-view visible.

16. `reviewer` → review all new/modified files in this batch against this spec.
    Verdict: `PASS` or `NEEDS_CHANGES`.

---

## Manual Verification

After implementation, run the following in order:

```bash
# 1. Unit and integration tests
PYTHONPATH=src .venv/bin/pytest tests/integrations/google/test_gmail_client.py \
    tests/brain/test_intent_parser_email.py \
    tests/api/test_mail_poller.py \
    tests/api/test_email_confirm.py -v
# expect: all green

# 2. Full backend suite — no regressions
PYTHONPATH=src .venv/bin/pytest --tb=short
# expect: all previously passing tests still pass

# 3. Frontend tests
cd frontend && npm test -- --reporter=verbose
# expect: all green

# 4. Live smoke test (requires real Google credentials in .env)
PYTHONPATH=src .venv/bin/python -m main &
cd frontend && npm run dev &
# Open http://localhost:5173, open MailPanel — should show live unread count within 120 s.

# 5. Voice read test
# Say "Check my email" → JARVIS should speak unread summary.

# 6. Voice send test (gated confirmation)
# Say "Send an email to <real address> about testing" →
#   JARVIS reads back draft → say "ja senden" → confirm email arrives.
# Repeat and say "nein" → JARVIS aborts, email is NOT sent.
```

---

## Open Questions

1. **Orchestrator routing for EMAIL_* intents**: the current `_LOCAL_INTENTS` set contains
   only `PC_CONTROL`, `SMART_HOME`, and `SYSTEM`. Email intents therefore fall through to the
   OpenClaw chat path, which is the intended behaviour for read/search (OpenClaw can call
   `GmailClient` methods as context or the prompt injects the results). For the
   `EMAIL_COMPOSE` confirmation phase, `ws_server._handle_email_confirm()` must intercept
   the *next* STT turn before it reaches the orchestrator. The exact intercept mechanism
   (e.g. a per-connection `asyncio.Event` + flag, or a dedicated confirmation queue) needs
   to align with how the existing audio pipeline in `ws_server.py` sequences turns — confirm
   with `backend-dev` before step 6.

2. **GmailClient initialisation point**: should `GmailClient` be instantiated once in
   `start_ws_server()` alongside `_orchestrator` and `_intent_parser`, or lazily on first
   voice command? Singleton is cleaner for the poller; lazy construction avoids startup
   delay for users who never use Gmail. Decide before step 5.

3. **How gmail read context reaches OpenClaw**: for EMAIL_READ / EMAIL_SEARCH turns, the
   orchestrator sends text to OpenClaw. The GmailClient results must be prepended to the
   prompt (e.g. "Context — unread emails: …\n\nUser: Check my email") OR the orchestrator
   must call `GmailClient` before dispatching. The preferred injection point should be
   decided before step 3 so the intent params and orchestrator changes are consistent.

4. **`email_send_done` on frontend**: currently `MailPanel.tsx` has no toast or status
   indicator. Should `email_send_done` trigger a HUD notification (reusing the existing
   `notification` WS message type) in addition to the TTS spoken confirmation, or is the
   `email_send_done` WS type intended solely to dismiss the draft-preview sub-view? Clarify
   before step 7.

# Feature Spec: Gmail Integration

## Summary
Enable JARVIS to read and search Gmail messages, delivering email summaries via voice. Users can ask for unread emails, search by sender/subject, and request full message details.

## Goals
- Read unread email summaries via voice
- Search emails by sender, subject, or keywords
- Summarize long emails to 2-3 sentences using Claude
- Follow JARVIS voice UX patterns (concise, offer drill-down)

## Non-Goals
- ~~Sending emails (deferred to Phase B)~~ — NOW IN SCOPE with gated confirmation (see Revision 2)
- Attachment handling
- Label/folder management
- Push notifications (polling only)

---

## Technical Design

### Dependencies
Requires `google-oauth-shared.md` to be implemented first.

Additional dependencies: None beyond google-api-python-client (already in OAuth spec).

### File Structure
```
src/integrations/google/
  gmail_client.py     # Gmail API wrapper (this spec)

src/brain/agents/
  email_agent.py      # Agent for email intents (this spec)
```

### GmailClient Class

```python
# src/integrations/google/gmail_client.py

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass
class EmailMessage:
    """Represents a Gmail message."""
    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    recipient: str
    date: datetime
    snippet: str  # Gmail's 100-char preview
    body_text: str | None  # Full plain text body (loaded on demand)
    body_html: str | None  # Full HTML body (loaded on demand)
    is_unread: bool
    labels: list[str]

@dataclass
class EmailThread:
    """Represents a Gmail thread."""
    id: str
    subject: str
    participants: list[str]
    message_count: int
    messages: list[EmailMessage]
    last_date: datetime

class GmailClient:
    """Async Gmail API client."""

    def __init__(self, oauth_service: GoogleOAuthService) -> None:
        """Initialize Gmail client.

        Args:
            oauth_service: Shared Google OAuth service
        """
        ...

    async def list_unread(
        self,
        max_results: int = 10,
        sender: str | None = None,
    ) -> list[EmailMessage]:
        """List unread messages.

        Args:
            max_results: Maximum messages to return
            sender: Filter by sender email/name (optional)

        Returns:
            List of unread EmailMessage objects (without full body)
        """
        ...

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[EmailMessage]:
        """Search messages using Gmail query syntax.

        Args:
            query: Gmail search query (e.g., "from:boss subject:urgent")
            max_results: Maximum messages to return

        Returns:
            List of matching EmailMessage objects
        """
        ...

    async def get_message(
        self,
        message_id: str,
        include_body: bool = True,
    ) -> EmailMessage:
        """Get a single message by ID.

        Args:
            message_id: Gmail message ID
            include_body: Whether to fetch full body text

        Returns:
            Complete EmailMessage object
        """
        ...

    async def get_thread(self, thread_id: str) -> EmailThread:
        """Get all messages in a thread.

        Args:
            thread_id: Gmail thread ID

        Returns:
            EmailThread with all messages
        """
        ...

    async def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read.

        Args:
            message_id: Gmail message ID

        Returns:
            True if successful
        """
        ...
```

### Gmail API Query Building

```python
def _build_query(
    self,
    is_unread: bool | None = None,
    sender: str | None = None,
    subject: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    has_attachment: bool | None = None,
) -> str:
    """Build Gmail search query string."""
    parts = []
    if is_unread:
        parts.append("is:unread")
    if sender:
        parts.append(f"from:{sender}")
    if subject:
        parts.append(f"subject:{subject}")
    if after:
        parts.append(f"after:{after.strftime('%Y/%m/%d')}")
    if before:
        parts.append(f"before:{before.strftime('%Y/%m/%d')}")
    if has_attachment:
        parts.append("has:attachment")
    return " ".join(parts)
```

### EmailAgent Class

```python
# src/brain/agents/email_agent.py

from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from integrations.google.gmail_client import GmailClient, EmailMessage

class EmailAgent(BaseAgent):
    """Agent for email operations."""

    def __init__(
        self,
        claude_client: ClaudeClient,
        gmail_client: GmailClient,
    ) -> None:
        """Initialize email agent.

        Args:
            claude_client: Claude client for summarization
            gmail_client: Gmail API client
        """
        super().__init__()
        self.claude_client = claude_client
        self.gmail_client = gmail_client
        self._current_messages: list[EmailMessage] = []  # For drill-down

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Execute email action.

        Args:
            task: Task description
            params: Action parameters (action, sender, query, etc.)
            language: Response language

        Returns:
            AgentResult with spoken response
        """
        action = params.get("action", "list_unread")

        if action == "list_unread":
            return await self._handle_list_unread(params, language)
        elif action == "search":
            return await self._handle_search(params, language)
        elif action == "read_detail":
            return await self._handle_read_detail(params, language)
        else:
            return await self._handle_list_unread(params, language)

    async def _handle_list_unread(
        self,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Handle listing unread emails."""
        max_results = params.get("max_results", 5)
        sender = params.get("sender")

        messages = await self.gmail_client.list_unread(
            max_results=max_results,
            sender=sender,
        )

        self._current_messages = messages  # Cache for drill-down

        if not messages:
            return AgentResult(
                spoken_response=self._no_emails_response(language),
                success=True,
                data={"count": 0},
            )

        # Generate spoken summary
        response = await self._generate_summary(messages, language)

        return AgentResult(
            spoken_response=response,
            success=True,
            data={"count": len(messages), "messages": [m.id for m in messages]},
        )

    async def _generate_summary(
        self,
        messages: list[EmailMessage],
        language: str,
    ) -> str:
        """Generate spoken summary of emails using Claude."""
        # Build context for Claude
        email_list = "\n".join([
            f"- From: {m.sender} ({m.sender_email}), "
            f"Subject: {m.subject}, "
            f"Preview: {m.snippet}"
            for m in messages
        ])

        prompt = f"""Summarize these {len(messages)} emails for voice output.
Keep it concise (1-2 sentences per email, max 3 emails detailed).
{self._get_language_instruction(language)}

Emails:
{email_list}

End with: "Would you like me to read any of these in full?" (in {language})"""

        summary = await self.claude_client.complete(
            prompt=prompt,
            max_tokens=200,
            temperature=0.5,
        )

        return summary

    def _no_emails_response(self, language: str) -> str:
        if language == "de":
            return "Sie haben keine ungelesenen E-Mails, Sir."
        return "You have no unread emails, sir."
```

### Intent Parser Updates

Add to `Intent` enum:
```python
class Intent(Enum):
    # ... existing ...
    EMAIL_READ = "email_read"
    EMAIL_SEARCH = "email_search"
```

Add to `INTENT_KEYWORDS`:
```python
Intent.EMAIL_READ: {
    "en": [
        r"\b(check|read|show|get)\s+(my\s+)?(email|mail|inbox)\b",
        r"\bunread\s+(email|mail|message)s?\b",
        r"\b(any\s+)?(new\s+)?(email|mail)s?\b",
        r"\bwhat('s| is)\s+in\s+my\s+inbox\b",
    ],
    "de": [
        r"\b(zeig|lies|check|hol)\s+(meine?\s+)?(email|mail|post)\b",
        r"\bungelesene?\s+(email|mail|nachricht)en?\b",
        r"\b(neue?\s+)?(email|mail|post)\b",
        r"\bwas\s+(ist|liegt)\s+in\s+meinem\s+posteingang\b",
    ],
},
Intent.EMAIL_SEARCH: {
    "en": [
        r"\b(email|mail)\s+(from|about|regarding)\b",
        r"\bfind\s+(email|mail|message)s?\s+(from|about)\b",
        r"\bsearch\s+(my\s+)?(email|mail|inbox)\b",
        r"\bmessages?\s+from\b",
    ],
    "de": [
        r"\b(email|mail)\s+(von|über|betreff)\b",
        r"\bfinde?\s+(email|mail|nachricht)en?\s+(von|über)\b",
        r"\bsuche?\s+(in\s+)?(meine[mr]?\s+)?(email|mail|posteingang)\b",
        r"\bnachrichten?\s+von\b",
    ],
},
```

Add parameter extraction:
```python
def _extract_email_params(self, text: str) -> dict[str, Any]:
    """Extract parameters for email intents."""
    params: dict[str, Any] = {"action": "list_unread"}

    # Check for search patterns
    if re.search(r"\b(from|von)\s+(\w+)", text):
        params["action"] = "search"
        match = re.search(r"\b(from|von)\s+(\w+[\w\s]*)", text)
        if match:
            params["sender"] = match.group(2).strip()

    if re.search(r"\b(about|regarding|über|betreff)\s+", text):
        params["action"] = "search"
        match = re.search(r"\b(about|regarding|über|betreff)\s+(.+)", text)
        if match:
            params["subject"] = match.group(2).strip()

    return params
```

---

## Voice UX Design

### Unread Email Summary
**User:** "Check my email"
**JARVIS:** "You have 3 unread emails, sir. First, from John Smith about the project deadline - he's asking for an update by Friday. Second, from Amazon confirming your order shipment. Third, from your bank with a security alert. Would you like me to read any of these in full?"

### Email Search
**User:** "Do I have any emails from my boss?"
**JARVIS:** "You have 2 recent emails from Sarah Johnson. The most recent, from yesterday, is about the Q4 budget review. The earlier one from Monday discusses team restructuring. Would you like details on either?"

### Drill-Down
**User:** "Read the first one"
**JARVIS:** "The email from John Smith, received today at 2:15 PM, says: [full body summarized to ~100 words]. End of message."

### No Results
**User:** "Check my email"
**JARVIS:** "Your inbox is clear, sir. No unread emails."

---

## Configuration

### config.yaml additions
```yaml
email:
  enabled: true
  provider: "gmail"
  max_unread_summary: 5      # Max emails in voice summary
  summary_max_chars: 150     # Max chars per email in summary
  full_read_max_chars: 500   # Max chars when reading full email
```

---

## Error Handling

| Error | User-Facing Response |
|-------|---------------------|
| OAuth not configured | "Email access is not configured. Please set up Google authentication." |
| Token expired, refresh failed | "I need you to re-authenticate with Google. Please check the terminal." |
| API rate limit | "Gmail is temporarily unavailable. Please try again in a moment." |
| Network error | "I couldn't reach Gmail. Please check your internet connection." |
| No results | "I couldn't find any emails matching that criteria." |

---

## Testing Strategy

### Unit Tests
| Test Case | Description |
|-----------|-------------|
| `test_list_unread_returns_messages` | Mocked API returns correct EmailMessage objects |
| `test_list_unread_empty` | Handles empty inbox gracefully |
| `test_search_by_sender` | Builds correct query for sender filter |
| `test_search_by_subject` | Builds correct query for subject filter |
| `test_get_message_with_body` | Fetches and parses full message body |
| `test_summary_generation` | Claude produces valid voice-friendly summary |
| `test_intent_parser_email_read` | "check my email" -> EMAIL_READ intent |
| `test_intent_parser_email_search` | "email from boss" -> EMAIL_SEARCH with sender param |

### Integration Tests (with mocked Gmail API)
| Test Case | Description |
|-----------|-------------|
| `test_full_flow_list_unread` | End-to-end: intent -> agent -> spoken response |
| `test_full_flow_search` | End-to-end: search query -> results -> summary |
| `test_oauth_refresh_on_401` | 401 response triggers token refresh |

### Mocking Gmail API
```python
@pytest.fixture
def mock_gmail_service():
    with patch("integrations.google.gmail_client.build") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service

async def test_list_unread_returns_messages(mock_gmail_service):
    mock_gmail_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}]
    }
    mock_gmail_service.users().messages().get().execute.return_value = {
        "id": "msg1",
        "payload": {...},
        "snippet": "Preview text...",
    }
    # ... test assertions
```

---

## Files Created

| File | Purpose |
|------|---------|
| `src/integrations/google/gmail_client.py` | Gmail API client |
| `src/brain/agents/email_agent.py` | Email agent |
| `tests/integrations/google/test_gmail_client.py` | Gmail client unit tests |
| `tests/brain/agents/test_email_agent.py` | Email agent unit tests |

## Files Modified

| File | Change |
|------|--------|
| `src/brain/intent_parser.py` | Add EMAIL_READ, EMAIL_SEARCH intents + keywords |
| `src/brain/orchestrator.py` | Register EmailAgent, update system prompt |
| `config/config.yaml` | Add email section |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | "check my email" returns spoken summary of up to 5 unread emails | Integration test |
| 2 | "email from [name]" filters results to that sender | Unit test on query building |
| 3 | Empty inbox returns friendly "no unread emails" response | Unit test |
| 4 | Each email summary is <= 2 sentences | Verify Claude prompt constraints |
| 5 | German trigger phrases work: "zeig meine emails" | Intent parser unit test |
| 6 | OAuth error triggers re-auth prompt without crash | Integration test |
| 7 | API rate limit returns retry message, does not crash | Error handling test |
| 8 | Orchestrator routes EMAIL_* intents to email agent | Routing test |

---

## Dependencies

- **Upstream:** google-oauth-shared.md
- **Downstream:** None (independent feature)

---

## Revision 2 — 2026-04-16

### Summary of Changes
This revision adds email sending capability with a strictly gated voice-confirmation flow.

### Email Sending — NOW IN SCOPE

Email sending is allowed but strictly gated by a multi-step confirmation flow to prevent accidental sends.

### Email Send Flow (Gated Confirmation)

#### Flow Steps
1. **Draft Creation**: JARVIS drafts the email (body + subject + recipient) based on user's voice request
2. **Visual Preview**: Draft renders in HUD via `email_draft_preview` WS message (modal or dedicated EmailDraftPanel)
3. **Voice Confirmation Request**: JARVIS asks by voice:
   - English: "Shall I send this, Sir?"
   - German: "Soll ich das senden, Sir?"
4. **Explicit Verbal Confirmation Required**: User must say one of the whitelisted confirmations:
   - German: "ja senden", "ja schick es", "senden", "abschicken", "ja"
   - English: "yes send", "send it", "go ahead", "confirm", "yes"
5. **Send Execution**: ONLY on explicit verbal confirmation → `email_send_request_confirmed` WS message sent, backend executes send
6. **Abort on Non-Confirmation**: Any other response OR silence >10 seconds → abort send, draft stays visible for editing
7. **Completion Notification**: `email_send_done` WS message with success/fail status; JARVIS speaks confirmation

#### WebSocket Message Types (New)

| Type | Direction | Payload |
|------|-----------|---------|
| `email_draft_preview` | BE → FE | `{ draft_id: string, to: string, subject: string, body_preview: string, created_at: ISO8601 }` |
| `email_send_request_confirmed` | FE → BE | `{ draft_id: string }` |
| `email_send_done` | BE → FE | `{ draft_id: string, success: bool, message_id?: string, error?: string }` |

### GmailClient Interface — Extended

Add the following methods:

```python
@dataclass
class EmailDraft:
    """Email draft."""
    id: str
    to: str
    subject: str
    body: str
    created_at: datetime

class GmailClient:
    # ... existing methods ...

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> EmailDraft:
        """Create a draft email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text)

        Returns:
            Created EmailDraft object
        """
        ...

    async def send_draft(self, draft_id: str) -> str:
        """Send an existing draft.

        Args:
            draft_id: Draft ID from create_draft

        Returns:
            Sent message ID

        Raises:
            GmailSendError: If send fails
        """
        ...

    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft.

        Args:
            draft_id: Draft ID to delete

        Returns:
            True if deleted
        """
        ...
```

### EmailAgent — Extended

Add send flow handling:

```python
async def _handle_compose(
    self,
    params: dict[str, Any],
    language: str,
) -> AgentResult:
    """Handle email composition request."""
    to = params.get("to")
    subject = params.get("subject")
    body = params.get("body")

    # Create draft
    draft = await self.gmail_client.create_draft(to, subject, body)

    # Broadcast preview to frontend
    await self._ws_broadcaster("email_draft_preview", {
        "draft_id": draft.id,
        "to": draft.to,
        "subject": draft.subject,
        "body_preview": draft.body[:200],
        "created_at": draft.created_at.isoformat(),
    })

    # Ask for confirmation
    confirm_msg = (
        "Soll ich das senden, Sir?" if language == "de"
        else "Shall I send this, Sir?"
    )

    return AgentResult(
        spoken_response=confirm_msg,
        success=True,
        data={"draft_id": draft.id, "awaiting_confirmation": True},
    )
```

### Intent Parser — Extended

Add compose/send intents:

```python
Intent.EMAIL_COMPOSE: {
    "en": [
        r"\b(write|compose|draft|send)\s+(an?\s+)?(email|mail)\b",
        r"\bemail\s+\w+\s+(about|regarding)\b",
        r"\bsend\s+(an?\s+)?(email|message)\s+to\b",
    ],
    "de": [
        r"\b(schreib|verfass|send)[e]?\s+(eine?\s+)?(email|mail|nachricht)\b",
        r"\bemail\s+an\s+\w+\b",
        r"\bschick\s+(eine?\s+)?(email|nachricht)\s+an\b",
    ],
},
```

### OAuth Scopes — Updated

Gmail compose scope required:
- Add `https://www.googleapis.com/auth/gmail.compose` to required scopes
- Update `google-oauth-shared.md` DEFAULT_SCOPES

### Acceptance Criteria — Extended

| # | Criterion | Verification |
|---|-----------|--------------|
| 9 | "Send an email to John about the meeting" creates draft | Integration test |
| 10 | Draft preview appears in HUD | Visual inspection |
| 11 | "ja senden" sends the email | Integration test |
| 12 | "nein" / silence aborts send, draft remains | Integration test |
| 13 | `email_send_done` message received on completion | Unit test |

### Voice UX — Send Flow Example

**User:** "Send an email to Sarah about tomorrow's meeting"

**JARVIS:** "I'll draft that for you, Sir."
*[Draft appears in HUD preview panel]*

**JARVIS:** "Here's the draft: To Sarah Johnson, subject 'Tomorrow's Meeting', body: 'Hi Sarah, I wanted to confirm our meeting tomorrow. Looking forward to it. Best regards.' Shall I send this, Sir?"

**User:** "Yes, send it"

**JARVIS:** "Done. Email sent to Sarah Johnson, Sir."

---

**Status:** Planned — awaiting implementation authorization

---

## Revision 3 — Full OpenClaw Adoption (2026-04-16)

### Decisions Applied
1. **OpenClaw as full backbone** — Gmail via OpenClaw only
2. **No JARVIS-side service client** — All Gmail operations via OpenClaw

### Integration Assessment
**OpenClaw FULLY replaces this spec's core functionality.**

### OpenClaw Coverage
| Feature | OpenClaw Capability | Coverage |
|---------|---------------------|----------|
| List unread emails | Gmail integration | Full |
| Search by sender/subject | Gmail integration | Full |
| Read full message | Gmail integration | Full |
| Create draft | Gmail integration | Full |
| Send email | Gmail integration | Full |
| OAuth/auth | Handled by OpenClaw | Full |

### What JARVIS-Native Retains
1. **MailPanel** — HUD visualization of email state
2. **Voice UX** — Email summary formatting, confirmation flow for sending
3. **Email draft preview** — WebSocket message flow to frontend
4. **VIP mail detection** — Proactive alert triggers (configured sender whitelist)
5. **EmailMessage dataclass** — For HUD panel rendering

### What Is REMOVED (This Spec)
- ~~GmailClient~~ — REMOVED (OpenClaw handles)
- ~~EmailAgent~~ — REMOVED (queries go to OpenClaw)
- ~~google-oauth-shared.md dependency~~ — REMOVED (OpenClaw handles OAuth)
- ~~All Gmail API wrapper code~~ — REMOVED

### Migration Path
1. All email voice commands route to OpenClaw via `query_agent()`
2. OpenClaw returns email data
3. JARVIS maps response to `EmailMessage` for MailPanel
4. Send confirmation flow: OpenClaw draft → HUD preview → voice confirm → OpenClaw send

### Simplified Architecture
```
Voice: "Check my email"
       ↓
[Intent Parser] → EMAIL_READ intent
       ↓
[Orchestrator] → Forward to OpenClaw
       ↓
[OpenClaw Gmail skill]
       ↓
[Response] → Map to EmailMessage for HUD + spoken summary
```

### Send Flow with OpenClaw
```
Voice: "Send an email to Sarah about the meeting"
       ↓
[OpenClaw] → Creates draft, returns draft_id + preview
       ↓
[JARVIS WS] → email_draft_preview to frontend
       ↓
[JARVIS TTS] → "Shall I send this, Sir?"
       ↓
[User] → "Yes, send it"
       ↓
[JARVIS] → Confirm to OpenClaw → OpenClaw sends
```

### Files Created — REDUCED
| File | Purpose | Status |
|------|---------|--------|
| `src/integrations/google/gmail_client.py` | Gmail API client | SKIP (OpenClaw) |
| `src/brain/agents/email_agent.py` | Email agent | SKIP (OpenClaw) |
| `src/integrations/email/models.py` | EmailMessage dataclass | KEEP (HUD needs) |

### Files Modified — REDUCED
| File | Change | Status |
|------|--------|--------|
| `src/brain/intent_parser.py` | Add EMAIL_* intents | KEEP |
| `src/brain/orchestrator.py` | Route to OpenClaw | MODIFIED |
| `src/api/ws_server.py` | Bridge OpenClaw email events | KEEP |
| `config/config.yaml` | Email section (provider: openclaw) | SIMPLIFIED |

### Config — Simplified
```yaml
email:
  enabled: true
  provider: "openclaw"
  vip_senders: []  # Sender whitelist for proactive alerts
```

### Implementation Reduction
**Original estimate:** 6-8 hours
**With OpenClaw:** 2-3 hours (HUD panel + voice UX only)
**Reduction:** ~60%

### Prerequisites
- `openclaw-integration.md` — REQUIRED (handles all email operations)

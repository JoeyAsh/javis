"""Google integration package for JARVIS — OpenClaw/gog shim (ADR-0001).

All Google API calls are delegated to the ``gog`` CLI binary.  The exception
hierarchy and public dataclasses are re-exported here for backwards
compatibility with ``ws_server.py`` and ``orchestrator.py``.

Authentication is managed exclusively by ``gog auth add <email>`` on the
OpenClaw host — JARVIS no longer owns a token cache.
"""

from __future__ import annotations

from integrations.google.calendar_client import (
    CalendarClientError,
    CalendarEvent,
    GoogleCalendarClient,
    get_calendar_client,
)
from integrations.google.drive_client import (
    DriveClient,
    DriveClientError,
    DriveFile,
    get_drive_client,
)
from integrations.google.gmail_client import (
    EmailDraft,
    EmailMessage,
    GmailClient,
    GmailClientError,
    get_gmail_client,
)
from integrations.google.oauth import (
    GoogleOAuthError,
    GoogleOAuthFlowError,
    GoogleOAuthRevokeError,
    GoogleOAuthService,
    GoogleOAuthTokenError,
    get_google_oauth_service,
)

__all__ = [
    "GoogleOAuthService",
    "GoogleOAuthError",
    "GoogleOAuthFlowError",
    "GoogleOAuthTokenError",
    "GoogleOAuthRevokeError",
    "get_google_oauth_service",
    # Gmail
    "GmailClient",
    "GmailClientError",
    "EmailMessage",
    "EmailDraft",
    "get_gmail_client",
    # Calendar
    "GoogleCalendarClient",
    "CalendarClientError",
    "CalendarEvent",
    "get_calendar_client",
    # Drive
    "DriveClient",
    "DriveClientError",
    "DriveFile",
    "get_drive_client",
]

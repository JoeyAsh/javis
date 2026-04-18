"""Google integration package for JARVIS.

Exports the shared OAuth service and its exception hierarchy so downstream
integrations (Gmail, Calendar, Drive) can consume them without importing
from the implementation module directly.
"""

from __future__ import annotations

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
]

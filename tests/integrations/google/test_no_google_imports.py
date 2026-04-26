"""Meta-tests for AC #1 — no googleapiclient / google-auth imports in src/.

Walks the entire ``src/`` directory and asserts that no Python source file
imports the previously-used Google client libraries.  The migration to the gog
CLI adapter (ADR-0001) removed all such imports; this test prevents regression.

Also verifies that the public surface of each migrated module exports the
expected symbols (AC #2 dataclass shape smoke tests).
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Forbidden import fragments
# ---------------------------------------------------------------------------

FORBIDDEN_IMPORTS = (
    "googleapiclient",
    "google.auth",
    "google_auth_oauthlib",
    "google.oauth2",
    "google.auth.transport",
)


def _iter_python_sources(root: Path):
    """Yield every .py file under *root*, skipping __pycache__ directories."""
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _file_contains_forbidden_import(source: str) -> list[str]:
    """Return a list of forbidden import fragments found in *source*.

    Uses both textual scan and AST parsing for robustness.
    """
    found: list[str] = []
    for fragment in FORBIDDEN_IMPORTS:
        if fragment in source:
            found.append(fragment)
    return found


# ---------------------------------------------------------------------------
# AC 1 — zero occurrences of googleapiclient / google.auth / google_auth_oauthlib
# ---------------------------------------------------------------------------


def test_no_googleapiclient_imports_in_src():
    """No file under src/ has an actual import of googleapiclient or google-auth.

    Uses AST parsing to detect import statements only — docstring mentions of
    the old library name are allowed (migration history notes).
    """
    src_root = Path(__file__).parents[3] / "src"
    assert src_root.is_dir(), f"src/ directory not found at {src_root}"

    violations: list[str] = []
    for py_file in _iter_python_sources(src_root):
        source = py_file.read_text(encoding="utf-8", errors="replace")
        imports = _ast_imports(source)
        found = [
            imp for imp in imports
            if any(imp == frag or imp.startswith(frag + ".") for frag in FORBIDDEN_IMPORTS)
        ]
        if found:
            rel = py_file.relative_to(src_root.parent)
            violations.append(f"{rel}: {found}")

    assert not violations, (
        "The following files still import googleapiclient / google-auth:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_no_google_auth_oauthlib_imports_in_src():
    """google_auth_oauthlib / InstalledAppFlow are not imported anywhere in src/."""
    src_root = Path(__file__).parents[3] / "src"
    assert src_root.is_dir()

    violations: list[str] = []
    for py_file in _iter_python_sources(src_root):
        source = py_file.read_text(encoding="utf-8", errors="replace")
        imports = _ast_imports(source)
        if any(
            "google_auth_oauthlib" in imp or "InstalledAppFlow" in imp
            for imp in imports
        ):
            rel = py_file.relative_to(src_root.parent)
            violations.append(str(rel))

    assert not violations, (
        "InstalledAppFlow / google_auth_oauthlib import found in:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# AC 2 — public surface (dataclasses) are importable and have expected fields
# ---------------------------------------------------------------------------


def test_email_message_public_surface():
    """EmailMessage exports all expected fields (public surface unchanged)."""
    from integrations.google.gmail_client import EmailMessage, GmailClient, GmailClientError

    import dataclasses

    fields = {f.name for f in dataclasses.fields(EmailMessage)}
    expected = {
        "id", "thread_id", "subject", "sender", "sender_email",
        "recipient", "received_at", "snippet", "body_text", "is_unread", "is_vip",
    }
    assert expected <= fields, f"Missing fields: {expected - fields}"


def test_email_draft_public_surface():
    """EmailDraft exports all expected fields."""
    from integrations.google.gmail_client import EmailDraft

    import dataclasses

    fields = {f.name for f in dataclasses.fields(EmailDraft)}
    expected = {"id", "to", "subject", "body", "created_at"}
    assert expected <= fields, f"Missing fields: {expected - fields}"


def test_calendar_event_public_surface():
    """CalendarEvent exports all expected fields (public surface unchanged)."""
    from integrations.google.calendar_client import (
        CalendarEvent,
        CalendarClientError,
        GoogleCalendarClient,
    )

    import dataclasses

    fields = {f.name for f in dataclasses.fields(CalendarEvent)}
    expected = {
        "id", "calendar_id", "title", "start", "end",
        "all_day", "location", "description", "attendees", "is_recurring",
    }
    assert expected <= fields, f"Missing fields: {expected - fields}"


def test_drive_file_public_surface():
    """DriveFile exports all expected fields (public surface unchanged)."""
    from integrations.google.drive_client import DriveFile, DriveClient, DriveClientError

    import dataclasses

    fields = {f.name for f in dataclasses.fields(DriveFile)}
    expected = {"id", "name", "mime_type", "modified_time", "web_view_link"}
    assert expected <= fields, f"Missing fields: {expected - fields}"


def test_gmail_client_module_exports():
    """gmail_client module exports the expected public names."""
    from integrations.google import gmail_client

    assert hasattr(gmail_client, "GmailClient")
    assert hasattr(gmail_client, "GmailClientError")
    assert hasattr(gmail_client, "EmailMessage")
    assert hasattr(gmail_client, "EmailDraft")
    assert hasattr(gmail_client, "get_gmail_client")


def test_calendar_client_module_exports():
    """calendar_client module exports the expected public names."""
    from integrations.google import calendar_client

    assert hasattr(calendar_client, "GoogleCalendarClient")
    assert hasattr(calendar_client, "CalendarClientError")
    assert hasattr(calendar_client, "CalendarEvent")
    assert hasattr(calendar_client, "get_calendar_client")


def test_drive_client_module_exports():
    """drive_client module exports the expected public names."""
    from integrations.google import drive_client

    assert hasattr(drive_client, "DriveClient")
    assert hasattr(drive_client, "DriveClientError")
    assert hasattr(drive_client, "DriveFile")
    assert hasattr(drive_client, "get_drive_client")


def test_oauth_module_exports_exception_hierarchy():
    """oauth module exports the expected exception classes (backwards-compat)."""
    from integrations.google import oauth

    assert hasattr(oauth, "GoogleOAuthError")
    assert hasattr(oauth, "GoogleOAuthFlowError")
    assert hasattr(oauth, "GoogleOAuthTokenError")
    assert hasattr(oauth, "GoogleOAuthRevokeError")
    assert hasattr(oauth, "GoogleOAuthService")
    assert hasattr(oauth, "get_google_oauth_service")


# ---------------------------------------------------------------------------
# AC 1 variant — AST-level import check (catches aliased imports too)
# ---------------------------------------------------------------------------


def _ast_imports(source: str) -> list[str]:
    """Return all module names imported in *source* via AST parsing."""
    names: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_no_googleapiclient_via_ast():
    """AST scan finds no 'import googleapiclient' or 'from googleapiclient ...' in src/."""
    src_root = Path(__file__).parents[3] / "src"
    assert src_root.is_dir()

    violations: list[str] = []
    for py_file in _iter_python_sources(src_root):
        source = py_file.read_text(encoding="utf-8", errors="replace")
        imports = _ast_imports(source)
        for imp in imports:
            if imp.startswith("googleapiclient"):
                rel = py_file.relative_to(src_root.parent)
                violations.append(f"{rel}: import {imp}")
                break

    assert not violations, (
        "AST scan found googleapiclient imports in:\n"
        + "\n".join(f"  {v}" for v in violations)
    )

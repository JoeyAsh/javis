"""One-shot Google OAuth login for JARVIS.

Run once to authorise JARVIS against Gmail + Calendar + Drive. Opens
the browser, lets you click through the consent screen, caches the
token to ~/.jarvis/google_token.json, and exits. After this, all
JARVIS integrations (Gmail, Calendar, Drive) work without further
prompts.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/google_login.py
"""
from __future__ import annotations

import asyncio
import sys

from integrations.google.oauth import get_google_oauth_service
from utils.config_loader import get_config
from utils.logger import setup_logger


async def main() -> int:
    """Run the OAuth flow for all Gmail + Calendar + Drive scopes."""
    setup_logger()

    cfg = get_config()
    gmail_scopes: list[str] = (cfg.get_section("gmail") or {}).get("scopes", [])
    cal_scopes: list[str] = (cfg.get_section("calendar") or {}).get("scopes", [])
    drive_scopes: list[str] = (cfg.get_section("drive") or {}).get("scopes", [])

    all_scopes = list({*gmail_scopes, *cal_scopes, *drive_scopes})
    if not all_scopes:
        print("ERROR: no Google scopes found in config/config.yaml", file=sys.stderr)
        return 2

    print("Starting Google OAuth login flow for JARVIS...")
    print(f"Scopes: {', '.join(sorted(all_scopes))}")
    print("Your browser will open in a moment. Click 'Continue' → 'Advanced' →")
    print("'Go to JARVIS (unsafe)' to proceed past the unverified-app warning.\n")

    service = get_google_oauth_service()

    if await service.is_authenticated(all_scopes):
        print("Already authenticated — token cache is valid for all requested scopes.")
        return 0

    try:
        creds = await service.get_credentials(all_scopes)
    except Exception as exc:
        print(f"\nOAuth flow failed: {exc}", file=sys.stderr)
        return 1

    print("\n✓ Authenticated successfully.")
    print(f"  Valid: {creds.valid}")
    print(f"  Scopes granted: {', '.join(sorted(creds.scopes or []))}")
    print("  Token cached at ~/.jarvis/google_token.json")
    print("\nYou can now use Gmail / Calendar / Drive voice commands in JARVIS.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

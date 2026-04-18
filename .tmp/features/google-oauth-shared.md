# Feature: Google OAuth Shared Foundation

## Status
Planned — awaiting implementation authorization

## Goal
Provide a single, reusable authentication layer that all Google-service integrations (Gmail,
Calendar, Drive) can consume. The service handles the full OAuth 2.0 desktop flow — interactive
browser consent on first use, silent token refresh thereafter, scope-incremental re-consent, and
cache-backed persistence — so that no downstream integration needs to think about credentials at
all.

## Scope

### In scope
- `src/integrations/google/` package (`__init__.py` + `oauth.py`)
- `GoogleOAuthService` class with four async public methods:
  `get_credentials`, `is_authenticated`, `revoke`, `build_service`
- `InstalledAppFlow.run_local_server(port=0)` wrapped in `asyncio.to_thread` (non-blocking)
- Headless-machine fallback: `run_console` flow when `DISPLAY` / `WAYLAND_DISPLAY` are absent
- Scope-incremental consent: if cached token covers a subset of requested scopes, force re-auth
- Token cache persisted to `~/.jarvis/google_token.json` (path configurable)
- Custom `GoogleOAuthError` exception hierarchy with spoken-fallback-friendly messages
- `google:` section in `config/config.yaml`
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_TOKEN_CACHE` env vars
  (env wins over config)
- Unit tests for every public method; `InstalledAppFlow` and `google.oauth2.credentials`
  fully mocked — no live network calls
- Lazy initialisation: service does nothing until a feature calls `get_credentials` or
  `build_service`

### Out of scope
- Gmail client (`gmail_client.py`) — separate batch
- Calendar client — separate batch
- Drive client — separate batch
- Any aiohttp HTTP endpoint for OAuth callback (not needed: `run_local_server` handles its own
  loopback listener internally)
- Multi-user / multi-account scenarios
- Service-account credentials
- Frontend HUD indicators for auth state

## User Flow

1. User speaks a command that requires a Google service (e.g. "Read my latest emails").
2. The relevant integration (e.g. `GmailClient`) calls
   `google_oauth_service.get_credentials(scopes=[...])`.
3. If a valid cached token exists and covers the requested scopes, `get_credentials` returns
   immediately.
4. If the token is expired but a refresh token is stored, `get_credentials` silently refreshes
   and returns.
5. If no token exists (first use) or the cached scopes are insufficient, the service detects the
   display environment:
   - **GUI available**: opens the default browser to the Google consent screen. The user grants
     access. The loopback redirect is caught by `InstalledAppFlow.run_local_server`. JARVIS
     speaks "I've opened Google sign-in in your browser — please grant access."
   - **Headless**: prints the auth URL to the terminal and waits for the user to paste the
     authorisation code. JARVIS speaks "I need your authorisation — please check the terminal."
6. Credentials are persisted to the token cache file.
7. `get_credentials` returns; the calling integration proceeds.
8. On user request to "sign out of Google", `revoke()` is called: token is revoked via the
   Google revocation endpoint, the cache file is deleted, and JARVIS confirms verbally.

## Architecture

### Modules touched
- Backend:
  - `src/integrations/google/__init__.py` (new — package init, exports `GoogleOAuthService`)
  - `src/integrations/google/oauth.py` (new — primary implementation)
- Frontend: none
- Config: new top-level `google:` section in `config/config.yaml`
- Env: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_TOKEN_CACHE`
  (already present in `.env.example` as stubs)

### Data flow

```
Downstream integration (e.g. GmailClient)
  │
  └─► GoogleOAuthService.get_credentials(scopes)
          │
          ├─[cache hit, valid, superset scopes]──────────────► return Credentials
          │
          ├─[cache hit, expired, refresh_token present]
          │     google.auth.transport.requests.Request.refresh()
          │     persist updated token
          │                                                   ► return Credentials
          │
          └─[no cache / insufficient scopes]
                detect headless (env vars DISPLAY / WAYLAND_DISPLAY)
                │
                ├─[GUI] InstalledAppFlow.run_local_server(port=0)
                │         wrapped in asyncio.to_thread
                │
                └─[headless] InstalledAppFlow.run_console()
                              wrapped in asyncio.to_thread
                │
                persist Credentials to token_cache_path
                                                            ► return Credentials
```

### Interfaces

**Python — `src/integrations/google/oauth.py`**

```
class GoogleOAuthError(Exception):
    """Base exception for Google OAuth failures."""
    spoken_message: str  # voice-friendly text for TTS fallback

class GoogleOAuthFlowError(GoogleOAuthError):
    """Raised when the interactive OAuth flow fails or is cancelled."""

class GoogleOAuthTokenError(GoogleOAuthError):
    """Raised when token refresh fails and no interactive flow is possible."""

class GoogleOAuthRevokeError(GoogleOAuthError):
    """Raised when token revocation fails."""

class GoogleOAuthService:
    def __init__(self, config: dict[str, Any]) -> None: ...
        # config: merged dict of google: section from config.yaml;
        # env vars override individual keys at construction time.

    async def get_credentials(self, scopes: list[str]) -> google.oauth2.credentials.Credentials:
        """Return valid credentials covering all requested scopes.

        Runs interactive flow if needed, refreshes expired tokens silently,
        triggers re-auth if cached scopes are insufficient.

        Args:
            scopes: OAuth scope strings, e.g.
                ["https://www.googleapis.com/auth/gmail.readonly"].

        Returns:
            A valid, non-expired Credentials object.

        Raises:
            GoogleOAuthFlowError: Flow was cancelled or failed.
            GoogleOAuthTokenError: Refresh failed and no browser is available.
        """

    async def is_authenticated(self, scopes: list[str]) -> bool:
        """Return True if a cached, valid token covering all scopes exists.

        Does NOT trigger the interactive flow.

        Args:
            scopes: Scope strings to check coverage for.

        Returns:
            True if authenticated and token is not expired, False otherwise.
        """

    async def revoke(self) -> None:
        """Revoke the stored token and delete the cache file.

        Calls Google's token revocation endpoint, then removes the local
        token file regardless of revocation outcome.

        Raises:
            GoogleOAuthRevokeError: If revocation request fails with a
                non-recoverable HTTP error.
        """

    async def build_service(
        self,
        api_name: str,
        api_version: str,
        scopes: list[str],
    ) -> googleapiclient.discovery.Resource:
        """Return a ready-to-use Google API Resource object.

        Calls get_credentials internally; callers do not need to handle
        credentials directly.

        Args:
            api_name: e.g. "gmail"
            api_version: e.g. "v1"
            scopes: Required scopes for this service.

        Returns:
            Authenticated googleapiclient.discovery.Resource.

        Raises:
            GoogleOAuthFlowError: Propagated from get_credentials.
            GoogleOAuthTokenError: Propagated from get_credentials.
        """
```

**WebSocket messages:** none — this is a pure backend infrastructure layer.

**REST endpoints:** none.

### External dependencies

New pip packages (to be added to `requirements.txt`):

| Package | Minimum version | Purpose |
|---|---|---|
| `google-auth` | 2.x | Credentials, refresh, revocation |
| `google-auth-oauthlib` | 1.x | InstalledAppFlow |
| `google-api-python-client` | 2.x | `build()` / Resource |

No npm packages. No OS-level deps beyond a default browser for the interactive flow (headless
fallback is supported when none is available).

## Edge Cases & Failure Modes

- **Token cache directory does not exist** → `GoogleOAuthService.__init__` resolves the path and
  calls `Path.parent.mkdir(parents=True, exist_ok=True)` at construction time; no runtime error.
- **Token cache file is corrupt / malformed JSON** → `get_credentials` catches the parse
  exception, logs a warning, discards the file, and triggers fresh interactive flow.
- **Refresh token revoked by user in Google account settings** → `google.auth.exceptions.
  RefreshError` is caught; re-raises as `GoogleOAuthTokenError` with spoken message "I couldn't
  refresh my Google access. Please re-authenticate."
- **Interactive flow: user closes browser without granting access** → `run_local_server` raises
  or returns `None`; `get_credentials` raises `GoogleOAuthFlowError` with spoken message "Google
  sign-in was cancelled. Please try again."
- **Interactive flow: loopback port already in use** → `port=0` lets the OS pick a free port, so
  port conflicts cannot occur with `run_local_server`.
- **Headless machine, DISPLAY not set** → service detects absence of `DISPLAY` and
  `WAYLAND_DISPLAY` env vars and switches to `run_console` flow. If stdin is not a tty (e.g.
  Docker), `run_console` will fail; `GoogleOAuthFlowError` is raised with message "Google
  sign-in requires either a display or an interactive terminal."
- **`asyncio.to_thread` wrapping `run_local_server`** → the blocking call runs in the default
  thread pool executor; the event loop remains responsive. Timeout is enforced by the caller
  (see `timeout_seconds` config key); if exceeded, the thread is abandoned and
  `GoogleOAuthFlowError` is raised.
- **Flow timeout** → if the user does not complete consent within `timeout_seconds`, the
  `asyncio.wait_for` wrapper raises `asyncio.TimeoutError`, caught and re-raised as
  `GoogleOAuthFlowError` with spoken message "Google sign-in timed out. Please try again."
- **`build_service` called concurrently by two features** → `get_credentials` must be safe for
  concurrent calls. Use an `asyncio.Lock` on the flow execution path (not on cache reads) to
  prevent two interactive flows from opening simultaneously.
- **Revoke when no cache file exists** → `revoke` is a no-op if the cache file is absent; logs
  info, does not raise.
- **Network unavailable during revocation** → `GoogleOAuthRevokeError` is raised; local cache
  file is still deleted so JARVIS is in a clean state.
- **Raspberry Pi (headless, no browser)** → same as headless path above; `run_console` is the
  supported path. Document this in the manual verification section.
- **Clock skew** → `google-auth` checks expiry against system time. If the system clock is
  wrong, tokens may appear expired prematurely. Log a hint if `RefreshError` mentions clock
  issues.
- **Scope string normalisation** → callers may pass short-form scopes (e.g.
  `"gmail.readonly"`) or full URIs. The service must normalise to full URIs
  (`"https://www.googleapis.com/auth/gmail.readonly"`) before comparing with cached scopes,
  to avoid spurious re-auth.

## Acceptance Criteria

1. `GoogleOAuthService.is_authenticated(scopes)` returns `False` when no token cache file
   exists, without raising any exception and without opening a browser.
2. `GoogleOAuthService.get_credentials(scopes)` returns a `Credentials` object (mocked) when
   a valid, non-expired token covering all requested scopes exists in the cache — without
   triggering the interactive flow.
3. `get_credentials` silently refreshes an expired token when a valid refresh token is present
   in the cache, updates the cache file, and returns valid credentials.
4. `get_credentials` triggers the interactive `InstalledAppFlow` (mocked) when no token file
   exists, saves the resulting credentials to the cache, and returns them.
5. `get_credentials` triggers re-auth (mocked `InstalledAppFlow`) when the cached token covers
   only a subset of the requested scopes, even if the cached token is not expired.
6. The interactive flow is called via `asyncio.to_thread` — verified by asserting that the
   event loop was not blocked (mock confirms `to_thread` was used, not a direct call).
7. `get_credentials` raises `GoogleOAuthFlowError` when the interactive flow times out
   (simulated with `asyncio.TimeoutError`); the error's `spoken_message` attribute is
   non-empty.
8. `get_credentials` raises `GoogleOAuthTokenError` when token refresh fails with
   `google.auth.exceptions.RefreshError`; spoken message is non-empty.
9. A corrupt token cache file is silently discarded; `get_credentials` proceeds to the
   interactive flow without raising an unhandled exception.
10. `revoke()` calls the Google revocation endpoint (mocked), deletes the cache file, and
    returns without error.
11. `revoke()` when no cache file exists completes without raising any exception.
12. `build_service(api_name, api_version, scopes)` calls `get_credentials` internally and
    returns a `googleapiclient.discovery.Resource` (mocked); no credentials handling is needed
    by the caller.
13. `GoogleOAuthService` constructor reads `GOOGLE_OAUTH_CLIENT_ID` and
    `GOOGLE_OAUTH_CLIENT_SECRET` from env vars and env values take precedence over any values
    in the config dict.
14. `config/config.yaml` parses without error after the `google:` section is added; all
    existing tests still pass.
15. `requirements.txt` includes `google-auth`, `google-auth-oauthlib`, and
    `google-api-python-client`; `pip install -r requirements.txt` succeeds in a clean venv.
16. Headless detection: when `DISPLAY` and `WAYLAND_DISPLAY` are both absent from the
    environment, `get_credentials` routes to `run_console` (mocked) instead of
    `run_local_server`.
17. Concurrent calls to `get_credentials` with the same scopes do not open two browser windows
    (only one `InstalledAppFlow` mock call is made for two simultaneous coroutine invocations).

## Implementation Plan

1. `backend-dev` — add `google-auth`, `google-auth-oauthlib`, and `google-api-python-client`
   to `requirements.txt`.

2. `backend-dev` — add the `google:` section to `config/config.yaml` with keys:
   `token_cache_path` (default `~/.jarvis/google_token.json`) and `timeout_seconds`
   (default `120`). Do not add any other keys in this batch.

3. `backend-dev` — create `src/integrations/google/__init__.py` exporting
   `GoogleOAuthService`, `GoogleOAuthError`, `GoogleOAuthFlowError`,
   `GoogleOAuthTokenError`, `GoogleOAuthRevokeError`.

4. `backend-dev` — implement `src/integrations/google/oauth.py` containing the full
   `GoogleOAuthService` class and the four exception types as specified in the Interfaces
   section. Implement all four public async methods, the `asyncio.to_thread` wrapping,
   headless detection, scope normalisation, concurrent-flow lock, and token cache I/O.
   No Gmail/Calendar/Drive code in this file.

5. `tester` — create `tests/integrations/google/__init__.py` (empty).

6. `tester` — create `tests/integrations/google/test_oauth.py` covering all seventeen
   acceptance criteria via unit tests. Mock `google_auth_oauthlib.flow.InstalledAppFlow`,
   `google.oauth2.credentials.Credentials`, `googleapiclient.discovery.build`, and
   `google.auth.transport.requests.Request`. No live network calls, no real file I/O
   (use `tmp_path` pytest fixture for the token cache path).

7. `reviewer` — review `src/integrations/google/oauth.py`,
   `src/integrations/google/__init__.py`, and `tests/integrations/google/test_oauth.py`
   against this spec. Verdict: `PASS` or `NEEDS_CHANGES`.

## Manual Verification

After implementation, the developer should run the following in order:

```
# 1. Confirm new packages install cleanly
cd /path/to/Jarvis
python -m venv .venv-test && .venv-test/bin/pip install -r requirements.txt
# expect: no errors

# 2. Run the new unit tests in isolation
PYTHONPATH=src .venv/bin/pytest tests/integrations/google/test_oauth.py -v
# expect: all tests green

# 3. Run the full test suite to confirm no regressions
PYTHONPATH=src .venv/bin/pytest --tb=short
# expect: all previously passing tests still pass

# 4. Smoke-test is_authenticated without credentials (interactive-free check)
PYTHONPATH=src .venv/bin/python - <<'EOF'
import asyncio, os
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "dummy")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "dummy")
from integrations.google import GoogleOAuthService
svc = GoogleOAuthService({"token_cache_path": "/tmp/no-such-file.json", "timeout_seconds": 30})
result = asyncio.run(svc.is_authenticated(["https://www.googleapis.com/auth/gmail.readonly"]))
print("is_authenticated:", result)  # must print False
EOF

# 5. Verify config.yaml parses and includes the google section
PYTHONPATH=src .venv/bin/python - <<'EOF'
import yaml
with open("config/config.yaml") as f:
    cfg = yaml.safe_load(f)
assert "google" in cfg, "google: section missing from config.yaml"
assert "token_cache_path" in cfg["google"]
assert "timeout_seconds" in cfg["google"]
print("config.yaml OK:", cfg["google"])
EOF

# 6. (Optional, requires real credentials) Full interactive flow smoke test
#    Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env, then:
PYTHONPATH=src .venv/bin/python - <<'EOF'
import asyncio
from dotenv import load_dotenv
load_dotenv()
from integrations.google import GoogleOAuthService
svc = GoogleOAuthService({})
creds = asyncio.run(svc.get_credentials(["https://www.googleapis.com/auth/gmail.readonly"]))
print("Token valid:", creds.valid)
EOF
# expect: browser opens, user grants access, "Token valid: True" printed,
#         ~/.jarvis/google_token.json created.
```

On a headless machine (RPi), export `DISPLAY=` (empty) and `WAYLAND_DISPLAY=` (empty) before
step 6. The console URL flow should activate, printing a URL to stdout for manual browser
completion.

## Open Questions

1. The `.env.example` contains a commented-out `GOOGLE_OAUTH_REDIRECT_URI` key. With
   `run_local_server(port=0)`, no redirect URI registration is needed. Should the key be
   removed from `.env.example`, or kept as a no-op comment for documentation purposes?

2. `timeout_seconds` in the `google:` config section — should this control only the interactive
   flow timeout, or also the token refresh network timeout? Clarify before implementation to
   avoid ambiguity in step 4.

3. Should `GoogleOAuthService` be instantiated once at JARVIS startup (singleton, held by the
   orchestrator) or constructed fresh by each downstream integration? A singleton is cleaner
   for lock sharing, but the caller pattern needs to be decided before the Gmail/Calendar
   specs proceed to implementation.

4. The headless console flow (`run_console`) requires stdin to be a tty. In Docker deployments
   (no tty, no display), neither flow works. Should a "pre-authorise" CLI helper script be
   planned to generate the token file on a GUI machine and copy it to the container, or is
   Docker with Google services officially out of scope for this project?

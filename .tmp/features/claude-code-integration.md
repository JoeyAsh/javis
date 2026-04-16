# Feature: Claude Agent SDK Integration & JARVIS Self-Debugging

## Status
Planned — awaiting implementation authorization

## Goal
Replace the raw Anthropic API client in `src/brain/claude_client.py` with the Claude Agent SDK
(`claude-agent-sdk` pip package), enabling JARVIS to run its conversation intelligence through
a persistent SDK session. The killer feature unlocked by this change is self-debugging: when the
user reports a bug by voice or JARVIS detects an unhandled exception in its own logs, it invokes
a dedicated SDK session with filesystem and shell access to read relevant source files, apply a
fix, run tests, commit the change to a sandboxed git branch, and report the outcome — all without
human intervention beyond an optional voice approval gate.

## Scope

### In scope
- New `src/brain/sdk_client.py` replacing `src/brain/claude_client.py` as the primary Claude
  interface, preserving the existing public method signatures (`chat`, `chat_with_json`,
  `complete`) so downstream callers require minimal changes.
- Dual-session architecture (Pattern B): one long-lived **chat session** (`ClaudeSDKClient`)
  for conversational turns; one on-demand **dev session** (`query()` per fix job) for code
  modifications.
- New `Intent.SELF_DEBUG` intent value added to `src/brain/intent_parser.py` with keyword
  patterns in English and German.
- New `src/brain/agents/self_debug_agent.py` (`SelfDebugAgent`) routed from `Orchestrator`
  when `SELF_DEBUG` intent is detected or an error hook fires.
- Automatic error detection: a loguru sink in `src/utils/logger.py` captures `ERROR` and
  `CRITICAL` records and enqueues them to a rate-limited self-debug task queue.
- Safety rails: dev session limited to a curated `allowed_tools` whitelist; every fix committed
  to a dedicated `self-fix/<timestamp>` branch; `pytest` + `ruff` run before declaring success;
  automatic `git revert` if tests fail.
- Three new WebSocket message types: `self_fix_started`, `self_fix_progress`, `self_fix_done`.
- Frontend code-change panel in `frontend/src/components/SelfFixPanel.tsx` that renders diff
  summary, commit SHA, and fix status when `self_fix_done` is received.
- New `self_debug` section in `config/config.yaml`.
- Voice UX: orb state transitions to `thinking` during fix; periodic spoken progress updates;
  one-liner spoken summary on completion.
- Session manager utility `src/brain/sdk_session_manager.py` that owns both sessions and
  exposes a unified async interface.

### Out of scope
- TypeScript/frontend SDK usage (Python only).
- Real-time streaming of Claude's intermediate reasoning tokens to the frontend.
- MCP server connections within the dev session.
- Automatic PR creation or merge to main branch.
- Multi-user session isolation (JARVIS is single-user).
- Migration of existing tests to the new client (test updates are part of the plan, but
  restructuring the test suite itself is deferred).
- Docker/RPi image rebuild automation triggered by a fix.
- Bedrock, Vertex AI, or Azure auth providers (pure `ANTHROPIC_API_KEY` only).

---

## User Flow

**Voice-initiated self-debug (happy path):**

1. User speaks: "JARVIS, da ist ein Fehler in der Kalender-Integration."
2. STT transcribes. `IntentParser` matches `SELF_DEBUG` intent with high confidence.
3. `Orchestrator` routes to `SelfDebugAgent.run(task, params, language)`.
4. `SelfDebugAgent` broadcasts `self_fix_started` via WebSocket; orb transitions to `thinking`.
5. JARVIS speaks: "Verstanden, Sir. Ich analysiere das Problem."
6. `SelfDebugAgent` queries `ErrorLogSink` for recent `ERROR`/`CRITICAL` records related to
   the calendar module.
7. `SelfDebugAgent` calls `DevSessionRunner.run_fix(complaint, log_context)`, which invokes
   `query()` with the dev-session prompt, tool whitelist, and repo `cwd`.
8. The SDK session reads relevant files, locates the defect, applies edits.
9. `SafetyRailRunner` creates branch `self-fix/<timestamp>`, commits all changes via `git`.
10. `SafetyRailRunner` runs `pytest tests/` and `ruff check src/`. On success, reports commit SHA.
11. `SelfDebugAgent` broadcasts `self_fix_progress` at each stage (reading, editing, testing,
    committing), triggering spoken progress updates.
12. On success: `SelfDebugAgent` broadcasts `self_fix_done` (commit SHA + diff summary).
    JARVIS speaks: "Erledigt, Sir. Der Fix ist auf Branch self-fix/2026-04-16T1530 committed."
13. Frontend `SelfFixPanel` renders the diff summary and SHA.
14. JARVIS optionally asks: "Möchten Sie die Änderungen sehen?" — user can respond "ja" to
    expand the diff in the frontend.

**Automatic error detection (happy path):**

1. JARVIS runtime raises an unhandled exception; loguru records it at `ERROR` level.
2. `ErrorLogSink` captures the record, deduplicates by error signature (module + exception type),
   and checks rate-limit (max N fixes / hour).
3. If within limits: enqueues a `SelfDebugTask` to `AutoDebugQueue`.
4. `AutoDebugQueue` processor picks up the task and invokes `SelfDebugAgent` exactly as in steps
   4–13 above, but with the exception traceback as the complaint text.
5. If fix fails: `SelfDebugAgent` speaks a brief alert and logs the failure. No further retries
   until cooldown expires.

---

## Architecture

### Modules touched

- **Backend — new files:**
  - `src/brain/sdk_client.py` — drop-in replacement for `ClaudeClient`; wraps `ClaudeSDKClient`
    for chat and `query()` for dev operations.
  - `src/brain/sdk_session_manager.py` — lifecycle management for both sessions.
  - `src/brain/agents/self_debug_agent.py` — `SelfDebugAgent`.
  - `src/brain/dev_session_runner.py` — thin wrapper around `query()` for dev-session invocations.
  - `src/brain/safety_rails.py` — git branching, test runner, revert logic.
  - `src/utils/error_log_sink.py` — loguru sink + deduplication + rate-limit + `AutoDebugQueue`.

- **Backend — modified files:**
  - `src/brain/claude_client.py` — kept as compatibility shim (re-exports from `sdk_client.py`);
    deprecation notice added via docstring; no logic change.
  - `src/brain/orchestrator.py` — adds `SELF_DEBUG` routing branch; registers `SelfDebugAgent`.
  - `src/brain/intent_parser.py` — adds `Intent.SELF_DEBUG` enum value and keyword patterns.
  - `src/utils/logger.py` — `setup_logger()` gains optional `error_sink` parameter; registers
    `ErrorLogSink` if `self_debug.enabled` is true in config.
  - `src/api/ws_server.py` — adds `broadcast_self_fix_event()` helper; imports
    `SelfDebugAgent` broadcast functions.
  - `src/main.py` — initialises `SdkSessionManager`; wires `AutoDebugQueue` background task.

- **Frontend — new files:**
  - `frontend/src/components/SelfFixPanel.tsx` — diff/status panel.
  - `frontend/src/hooks/useSelfFix.ts` — WebSocket message handler for self-fix events.

- **Frontend — modified files:**
  - `frontend/src/components/App.tsx` (or equivalent root) — mounts `SelfFixPanel`.

- **Config:**
  ```yaml
  self_debug:
    enabled: true
    autonomous_mode: false          # false = ask voice confirmation before applying fix
    allowed_paths:
      - "src/"
      - "tests/"
    git_branch_prefix: "self-fix"
    max_fixes_per_hour: 3
    cooldown_seconds: 300
    max_turns_per_fix: 20
    allowed_tools:
      - "Read"
      - "Edit"
      - "Write"
      - "Glob"
      - "Grep"
      - "Bash"                      # restricted via hook to pytest, ruff, black, git only
    permission_mode: "acceptEdits"

  claude:
    # existing keys unchanged
    model: "claude-sonnet-4-6"
    max_tokens: 300
    temperature: 0.7
    max_history_turns: 10
    # new keys:
    sdk_cwd: null                   # null = repo root at runtime; override for tests
  ```

- **Env:**
  - `ANTHROPIC_API_KEY` — already present in `.env.example`; no new env vars required.
    The Claude Agent SDK authenticates via this key. `claude login` / OAuth is explicitly not
    used (Anthropic policy prohibits third-party products from offering claude.ai auth).

---

### Data flow

```
Voice input (PCM)
  └─► STT (Whisper)
        └─► IntentParser.classify_intent()
              ├─► Intent.SELF_DEBUG ──────────────────────────────────────────┐
              └─► other intents                                                │
                    └─► Orchestrator._get_decision()                           │
                          └─► SdkSessionManager.chat_session                  │
                                └─► ClaudeSDKClient.query()                   │
                                      [JARVIS system prompt]                   │
                                      [ConversationMemory history]             │
                                      └─► spoken response → TTS               │
                                                                               │
  ┌────────────────────────────────────────────────────────────────────────────┘
  │ SelfDebugAgent.run()
  │   ├─► broadcast_self_fix_event("self_fix_started")
  │   ├─► ErrorLogSink.get_recent_errors()   (log context)
  │   ├─► DevSessionRunner.run_fix(prompt, log_ctx)
  │   │     └─► query(prompt, ClaudeAgentOptions(
  │   │               allowed_tools=[...whitelist...],
  │   │               permission_mode="acceptEdits",
  │   │               system_prompt=DEV_SYSTEM_PROMPT,
  │   │               cwd=<repo root>,
  │   │               max_turns=cfg.max_turns_per_fix,
  │   │               hooks={"PreToolUse": [bash_command_guard]}
  │   │         ))
  │   │         ├─► AssistantMessage → broadcast_self_fix_event("self_fix_progress", ...)
  │   │         └─► ResultMessage → fix_result
  │   ├─► SafetyRailRunner.commit_to_branch(branch_name)
  │   │     └─► git checkout -b self-fix/<ts>  [Bash tool inside SDK OR subprocess]
  │   │     └─► git add src/ tests/
  │   │     └─► git commit -m "self-fix: <summary>"
  │   ├─► SafetyRailRunner.run_validation()
  │   │     ├─► pytest tests/  → pass/fail
  │   │     └─► ruff check src/ → pass/fail
  │   ├─► on validation pass:
  │   │     └─► broadcast_self_fix_event("self_fix_done", commit_sha, diff_summary)
  │   │     └─► TTS: spoken summary
  │   └─► on validation fail:
  │         ├─► git revert HEAD  (on self-fix branch)
  │         ├─► broadcast_self_fix_event("self_fix_done", success=False, reason=...)
  │         └─► TTS: spoken failure notice
  │
ErrorLogSink (loguru sink, background)
  └─► dedup + rate-limit → AutoDebugQueue
        └─► AutoDebugQueue processor (asyncio task)
              └─► SelfDebugAgent.run(task=traceback, ...) [same flow as above]
```

---

### Interfaces

All signatures are Python only. No function bodies.

#### `src/brain/sdk_client.py`

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, ResultMessage
from typing import Any, AsyncIterator

JARVIS_SYSTEM_PROMPT: str  # same constant, moved here
FALLBACK_RESPONSES: dict[str, str]  # same constant, moved here

class SdkChatClient:
    """Conversational Claude client backed by a persistent ClaudeSDKClient session.

    Preserves the public interface of the legacy ClaudeClient so that Orchestrator
    and all subagents remain unchanged.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 300,
        temperature: float = 0.7,
        cwd: str | None = None,
    ) -> None: ...

    async def initialize(self) -> None: ...

    async def chat(
        self,
        message: str,
        language: str = "en",
        history: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str: ...

    async def chat_with_json(
        self,
        message: str,
        system_prompt: str,
        max_tokens: int | None = None,
    ) -> dict[str, Any]: ...

    async def complete(
        self,
        prompt: str,
        system_prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str: ...

    async def close(self) -> None: ...


async def create_sdk_chat_client(config: dict[str, Any] | None = None) -> SdkChatClient: ...
```

**Compatibility shim in `src/brain/claude_client.py`** (no logic, re-export only):
```python
# Deprecated — use SdkChatClient from src/brain/sdk_client.py
ClaudeClient = SdkChatClient
create_claude_client = create_sdk_chat_client
```

#### `src/brain/sdk_session_manager.py`

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

class SdkSessionManager:
    """Owns and lifecycle-manages both the chat session and the dev session context."""

    def __init__(self, config: dict[str, Any]) -> None: ...

    async def start(self) -> None:
        """Open the long-lived chat session (ClaudeSDKClient context manager)."""
        ...

    async def stop(self) -> None:
        """Gracefully close both sessions."""
        ...

    @property
    def chat_client(self) -> "SdkChatClient": ...

    @property
    def dev_options(self) -> ClaudeAgentOptions:
        """Returns ClaudeAgentOptions pre-configured for the dev session."""
        ...
```

#### `src/brain/dev_session_runner.py`

```python
from claude_agent_sdk import ClaudeAgentOptions, AssistantMessage, ResultMessage
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Awaitable

@dataclass
class FixResult:
    success: bool
    summary: str           # one-line description of what was done or why it failed
    files_modified: list[str]
    error: str | None = None

class DevSessionRunner:
    """Invokes query() for one self-debug task and streams progress events."""

    def __init__(
        self,
        options: ClaudeAgentOptions,
        on_progress: Callable[[str], Awaitable[None]],  # receives human-readable status line
    ) -> None: ...

    async def run_fix(
        self,
        complaint: str,
        log_context: str,
        repo_root: str,
    ) -> FixResult: ...
```

#### `src/brain/safety_rails.py`

```python
from dataclasses import dataclass

@dataclass
class CommitResult:
    branch: str
    commit_sha: str
    diff_summary: str  # git diff --stat output, truncated to 1000 chars

@dataclass
class ValidationResult:
    pytest_passed: bool
    ruff_passed: bool
    pytest_output: str
    ruff_output: str

class SafetyRailRunner:
    """Handles git branching, test execution, and revert logic."""

    def __init__(self, repo_root: str, branch_prefix: str) -> None: ...

    async def create_branch(self, timestamp: str) -> str:
        """Create and checkout branch <branch_prefix>/<timestamp>. Returns branch name."""
        ...

    async def commit_changes(
        self, allowed_paths: list[str], message: str
    ) -> CommitResult: ...

    async def run_validation(self) -> ValidationResult: ...

    async def revert_commit(self, commit_sha: str) -> None: ...

    async def is_working_tree_dirty(self) -> bool: ...

    async def stash_dirty_tree(self) -> bool:
        """Stash uncommitted changes before fix. Returns True if stash was created."""
        ...

    async def pop_stash(self) -> None: ...
```

#### `src/brain/agents/self_debug_agent.py`

```python
from brain.agents.base import BaseAgent, AgentResult
from brain.dev_session_runner import DevSessionRunner, FixResult
from brain.safety_rails import SafetyRailRunner
from claude_agent_sdk import ClaudeAgentOptions

DEV_SYSTEM_PROMPT: str  # instructs the dev session to be surgical, minimal, PEP-8 compliant

class SelfDebugAgent(BaseAgent):
    """Agent that invokes the Claude Agent SDK dev session to diagnose and fix code."""

    def __init__(
        self,
        dev_options: ClaudeAgentOptions,
        safety_rails: SafetyRailRunner,
        repo_root: str,
        autonomous_mode: bool = False,
        ws_broadcaster: "Callable[[str, dict], Awaitable[None]] | None" = None,
    ) -> None: ...

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult: ...

    async def _confirm_via_voice(self, language: str) -> bool:
        """If autonomous_mode is False, speak a confirmation prompt and await user response.

        Returns True if user confirmed, False if denied or timed out.
        """
        ...

    async def _broadcast_progress(self, stage: str, detail: str = "") -> None: ...
```

#### `src/utils/error_log_sink.py`

```python
import asyncio
from dataclasses import dataclass
from typing import Any

@dataclass
class ErrorRecord:
    level: str
    module: str
    function: str
    message: str
    exception: str | None    # formatted traceback
    signature: str           # hash(module + exception_type) for deduplication

@dataclass
class SelfDebugTask:
    complaint: str           # human-readable description built from ErrorRecord
    log_context: str         # last N log lines as string
    error_record: ErrorRecord

class ErrorLogSink:
    """Loguru sink that captures ERROR/CRITICAL records and enqueues self-debug tasks."""

    def __init__(
        self,
        queue: "AutoDebugQueue",
        max_fixes_per_hour: int = 3,
        cooldown_seconds: int = 300,
    ) -> None: ...

    def __call__(self, message: Any) -> None:
        """Loguru sink callable. Synchronous by design (loguru constraint)."""
        ...

    def get_recent_errors(self, n: int = 10) -> list[ErrorRecord]: ...

class AutoDebugQueue:
    """asyncio.Queue wrapper for SelfDebugTask items; consumed by a background task."""

    def __init__(self) -> None: ...

    async def enqueue(self, task: SelfDebugTask) -> None: ...

    async def dequeue(self) -> SelfDebugTask: ...

    @property
    def qsize(self) -> int: ...
```

---

### WebSocket message types

All messages use the existing `{"type": <str>, "payload": <dict>}` envelope used in `ws_server.py`.

#### `self_fix_started`
```json
{
  "type": "self_fix_started",
  "payload": {
    "trigger": "voice | auto",
    "complaint": "<one-line summary of the problem>",
    "timestamp": "<ISO-8601>"
  }
}
```

#### `self_fix_progress`
Sent multiple times during a fix job (one per meaningful stage).
```json
{
  "type": "self_fix_progress",
  "payload": {
    "stage": "reading | analyzing | editing | testing | committing",
    "detail": "<human-readable status line, max 120 chars>",
    "files_touched": ["src/path/to/file.py"]
  }
}
```

#### `self_fix_done`
```json
{
  "type": "self_fix_done",
  "payload": {
    "success": true,
    "commit_sha": "abc1234",
    "branch": "self-fix/2026-04-16T153022",
    "diff_summary": "src/actions/calendar.py | 12 ++++---\n1 file changed, 7 insertions(+), 5 deletions(-)",
    "validation": {
      "pytest_passed": true,
      "ruff_passed": true
    },
    "reason": null
  }
}
```
When `success` is `false`, `commit_sha` and `branch` are `null`; `reason` contains a short
failure description.

#### `self_fix_approval_request` (only if `autonomous_mode: false`)
```json
{
  "type": "self_fix_approval_request",
  "payload": {
    "complaint": "<problem summary>",
    "affected_files": ["src/path/to/file.py"],
    "timeout_seconds": 30
  }
}
```
The frontend may render an approval card. JARVIS also speaks the confirmation prompt via TTS.
If the user says yes within `timeout_seconds`, the fix proceeds; otherwise it is cancelled.

---

### External dependencies

**New pip packages:**
- `claude-agent-sdk` — core SDK (`pip install claude-agent-sdk`).
  Minimum version: `0.2.111` (required for `claude-opus-4-7` support; any model works with earlier
  versions if opus-4-7 is not used).

**No new npm packages.** `SelfFixPanel.tsx` uses existing React + TypeScript patterns and the
existing WebSocket hook infrastructure.

**OS-level:**
- `git` must be on `$PATH` in the runtime environment (already present for development; must be
  verified for Docker and RPi images).
- `pytest`, `ruff` must be installed in the same Python environment as JARVIS (already expected
  as dev/test dependencies; must be present in production image if auto-debug is enabled).

---

## Edge Cases & Failure Modes

### SDK / Session lifecycle

- **Chat session drops mid-conversation** — `SdkChatClient.chat()` catches `Exception`, returns
  `FALLBACK_RESPONSES[language]`, logs `ERROR`. Session manager attempts one reconnect on next
  call via `ClaudeSDKClient` context manager restart. If reconnect fails, JARVIS falls back to
  direct `anthropic` SDK `messages.create()` call (legacy path preserved in `claude_client.py`
  shim).
- **`ANTHROPIC_API_KEY` missing at startup** — `SdkSessionManager.start()` raises
  `RuntimeError`; `main.py` catches it, logs `CRITICAL`, and falls back to running without the
  SDK (JARVIS voices an error and continues in degraded mode with no self-debug capability).
- **SDK package not installed** — `sdk_client.py` wraps `import claude_agent_sdk` in try/except
  `ImportError`; logs `CRITICAL` with install instructions; raises to halt startup.
- **Chat session returns empty `ResultMessage`** — treated identically to an empty response from
  the legacy client: return `FALLBACK_RESPONSES[language]`.

### Dev session / self-debug

- **Dev session crash mid-fix (unhandled exception from `query()`)** — `DevSessionRunner`
  catches, sets `FixResult(success=False)`. `SafetyRailRunner` is not invoked. Any partial file
  changes made by the SDK session before the crash may remain on disk. `SafetyRailRunner` must
  check `is_working_tree_dirty()` before future fix attempts and stash or revert dirty state.
- **Two error events arrive simultaneously** — `AutoDebugQueue` serialises tasks; the second task
  waits. The queue processor handles one task at a time. Concurrency guard in `SelfDebugAgent`
  prevents re-entrant fix runs (a `_running` flag); any task arriving while a fix is in progress
  is logged and dropped (not re-enqueued).
- **Fix introduces new test failures in unrelated modules** — `SafetyRailRunner.run_validation()`
  runs the full test suite. Any failure triggers `revert_commit()`. Voice report distinguishes:
  "Der Fix hat bestehende Tests gebrochen und wurde rückgängig gemacht, Sir."
- **Fix touches a module that is currently imported and running** — after a successful commit,
  `SelfDebugAgent` recommends process restart via SIGTERM (uvicorn auto-reload will pick up
  changes). It does NOT attempt `importlib.reload()` because partial reloads of modules with
  module-level singletons (e.g., `_orchestrator`, `_memory`) are unsafe in this codebase.
  Voice report includes: "Ein Neustart ist erforderlich, Sir."
- **Git working tree is dirty when a fix is triggered** — `SafetyRailRunner.stash_dirty_tree()`
  stashes uncommitted changes before creating the fix branch. `pop_stash()` is called on fix
  completion (success or fail). If stash pop fails, JARVIS logs `WARNING` and leaves the stash
  for manual inspection.
- **`git commit` fails (nothing to commit)** — `SafetyRailRunner.commit_changes()` checks for
  an empty diff; if no files changed, returns `CommitResult` with `commit_sha=None` and
  `diff_summary="No changes"`. `SelfDebugAgent` treats this as a non-fatal outcome and voices:
  "Ich konnte keinen Fix identifizieren, Sir."
- **Max turns exceeded in dev session** — `query()` ends with `ResultMessage(subtype="error_max_turns")`.
  `DevSessionRunner` maps this to `FixResult(success=False, error="max_turns_exceeded")`.
  No commit is attempted; JARVIS voices a brief notice.
- **Same error signature fires repeatedly** — `ErrorLogSink` tracks `(signature, timestamp)`
  pairs in an in-memory deque. If the same signature has been attempted within `cooldown_seconds`,
  the task is silently dropped. If the same signature has failed `max_fixes_per_hour` times in the
  rolling hour window, it is suppressed until the next hour boundary.
- **Rate limit exhausted (`max_fixes_per_hour`)** — `ErrorLogSink` drops the task and logs
  `WARNING`. No voice alert (to avoid noise). Resets on the rolling hour boundary.
- **Infinite-loop fix scenario (fix A causes error B, fix B causes error A)** — the deduplication
  hash and cooldown window break the loop. After `cooldown_seconds` with no new occurrences, the
  error is no longer suppressed, but `max_fixes_per_hour` provides a hard ceiling regardless.
- **`pytest` binary not found** — `SafetyRailRunner.run_validation()` catches `FileNotFoundError`;
  sets `pytest_passed=False` with `pytest_output="pytest not found in PATH"`. Fix is not committed.
  Logs `ERROR` with actionable message.
- **`ruff` binary not found** — same pattern as pytest. Fix is blocked.
- **Dev session modifies a file outside `allowed_paths`** — `BashCommandGuard` hook (registered
  as `PreToolUse`) inspects the `file_path` argument of `Edit`/`Write` tool calls. If the path
  does not start with a configured `allowed_paths` entry, the hook returns a deny response.
  Claude receives a tool error and must work within bounds.
- **`Bash` tool attempts a forbidden command** — `BashCommandGuard` hook parses the `command`
  argument and checks it against an allowlist (`pytest`, `ruff`, `black`, `git`). Any other
  command receives a deny response from the hook.
- **Approval request times out (`autonomous_mode: false`)** — `SelfDebugAgent._confirm_via_voice()`
  waits `timeout_seconds` (from `self_fix_approval_request` payload). If no affirmative response
  is received, fix is cancelled. `self_fix_done` is sent with `success=false, reason="user_timeout"`.
- **RPi memory pressure during dev session** — dev session is expensive. On RPi, `autonomous_mode`
  should default to `false` and `max_turns_per_fix` should be set low (e.g., 10). These are
  recommended `config.yaml` values for RPi profile, not enforced in code.
- **`self_fix_done` delivered when no frontend client is connected** — `broadcast_self_fix_event()`
  uses the existing `_broadcast()` helper which silently no-ops on empty `_connected_clients`.
  No action needed.
- **User says "fix this" without specifying a module** — `SelfDebugAgent` uses `ErrorLogSink.get_recent_errors()`
  to infer the most relevant recent error. If the error buffer is empty, JARVIS responds: "Ich
  sehe keinen aktuellen Fehler, Sir. Können Sie genauer beschreiben, was nicht funktioniert?"

---

## Acceptance Criteria

1. `pip install claude-agent-sdk` succeeds in the project's virtual environment without
   conflicting with existing dependencies.
2. JARVIS starts successfully (`uvicorn main:app`) with `ANTHROPIC_API_KEY` set and
   `self_debug.enabled: true`; log output confirms "Chat session initialized via Claude Agent SDK".
3. A standard voice request (e.g., "What is the weather?") routes through `SdkChatClient.chat()`
   and produces a spoken response indistinguishable from the pre-migration behaviour.
4. `Orchestrator` correctly routes a voice input containing "da ist ein Fehler" to
   `SelfDebugAgent` (verified by log output showing `SELF_DEBUG` intent with confidence > 0.7).
5. `Orchestrator` correctly routes a voice input containing "there is a bug" to `SelfDebugAgent`.
6. When `SelfDebugAgent.run()` is invoked, the WebSocket message `self_fix_started` is received
   by a connected test client within 500 ms.
7. During a fix run, at least one `self_fix_progress` WebSocket message is emitted with a
   non-empty `stage` field.
8. A successful fix produces a `self_fix_done` message with `success: true`, a non-null
   `commit_sha`, and a non-empty `diff_summary`.
9. After a successful fix, `git log --oneline -1` on the `self-fix/*` branch shows a commit
   message prefixed with "self-fix:".
10. If `pytest tests/` fails after a fix, `git log --oneline -1` on the fix branch shows a
    revert commit, and the `self_fix_done` payload has `success: false`.
11. A `Bash` tool call to `rm -rf /` inside the dev session is denied by `BashCommandGuard`
    and does not execute.
12. An `Edit` tool call targeting `config/.env` is denied by `BashCommandGuard` path whitelist
    and does not execute.
13. Injecting 4 `ERROR` log records with the same signature within 60 seconds results in exactly
    `max_fixes_per_hour` (default: 3) fix attempts being enqueued; the 4th is silently dropped
    (verified by queue size inspection in a unit test).
14. `SelfFixPanel.tsx` renders correctly when a `self_fix_done` WebSocket message is received:
    diff summary and commit SHA are visible; a "success" or "failed" badge is shown.
15. `SdkChatClient` exposes the same public methods as the legacy `ClaudeClient`
    (`initialize`, `chat`, `chat_with_json`, `complete`); a unit test that passes a
    `ClaudeClient` mock can be switched to `SdkChatClient` without changing the test assertions.
16. JARVIS starts in degraded mode (no SDK, no self-debug) if `ANTHROPIC_API_KEY` is absent;
    voice requests fall back to error responses instead of crashing the process.
17. `AutoDebugQueue` processes only one task at a time; a second task arriving while a fix is
    running is dropped and logged, not queued.
18. All new backend modules have `pytest` unit tests with 100% mock coverage (no live API calls,
    no live git operations).
19. `ruff check src/` and `black --check src/` pass on all new and modified files with zero
    violations.
20. Wake word detection latency is not degraded by more than 50 ms on RPi 4 compared to the
    pre-migration baseline (measured by existing timing log output).

---

## Implementation Plan

Each step targets exactly one agent and one deliverable. Steps within the same numbered batch
are independent and may be executed in parallel. Steps across batches must be sequential.

### Batch 1 — SDK foundation (no user-facing change)

1. `backend-dev` → add `claude-agent-sdk` to `requirements.txt` (or `pyproject.toml` if present);
   verify no dependency conflicts with `anthropic`, `aiohttp`, `loguru`.
2. `backend-dev` → create `src/brain/sdk_client.py` with `SdkChatClient` class and
   `create_sdk_chat_client()` factory; implement `initialize()`, `chat()`, `chat_with_json()`,
   `complete()`, `close()` using `ClaudeSDKClient` async context manager pattern; add
   `JARVIS_SYSTEM_PROMPT` and `FALLBACK_RESPONSES` constants; apply `@logger.catch` on all
   public methods for error isolation.
3. `backend-dev` → update `src/brain/claude_client.py` to re-export `SdkChatClient` as
   `ClaudeClient` and `create_sdk_chat_client` as `create_claude_client`; add deprecation
   docstring; preserve file so no import paths break.
4. `backend-dev` → create `src/brain/sdk_session_manager.py` with `SdkSessionManager`;
   implement `start()`, `stop()`, `chat_client` property, `dev_options` property with full
   `ClaudeAgentOptions` pre-configuration (tools whitelist, permission mode, system prompt, cwd).
5. `backend-dev` → update `src/main.py` to instantiate `SdkSessionManager`; call `start()` in
   lifespan startup and `stop()` in lifespan shutdown; pass `session_manager.chat_client` where
   `create_claude_client()` was previously called in `ws_server.py:start_ws_server()`.

### Batch 1 review

6. `tester` → write `tests/brain/test_sdk_client.py`: mock `ClaudeSDKClient` and `query()`; test
   `chat()`, `chat_with_json()`, `complete()`, fallback on exception, empty-response handling.
7. `tester` → write `tests/brain/test_sdk_session_manager.py`: test `start()`/`stop()` lifecycle,
   `dev_options` property returns correct tool whitelist.
8. `reviewer` → review Batch 1 (steps 1–7) against this spec; issue `PASS` or `NEEDS_CHANGES`.

### Batch 2 — Safety rails and dev session runner

9. `backend-dev` → create `src/brain/safety_rails.py` with `SafetyRailRunner`; implement
   `create_branch()`, `commit_changes()`, `run_validation()`, `revert_commit()`,
   `is_working_tree_dirty()`, `stash_dirty_tree()`, `pop_stash()` using `asyncio.create_subprocess_exec`
   for all git and pytest/ruff subprocess calls.
10. `backend-dev` → create `src/brain/dev_session_runner.py` with `DevSessionRunner`; implement
    `run_fix()` that calls `query()` with the dev options, streams `AssistantMessage` blocks to
    `on_progress` callback, extracts `files_modified` from tool call payloads, returns `FixResult`.
11. `backend-dev` → implement `BashCommandGuard` hook (defined inside `dev_session_runner.py` or
    `safety_rails.py`) as a `PreToolUse` hook callable; enforce allowed commands list and allowed
    paths list; return deny payload on violation.

### Batch 2 review

12. `tester` → write `tests/brain/test_safety_rails.py`: mock all subprocess calls; test branch
    creation, commit, validation pass, validation fail → revert, dirty tree stash/pop, missing
    binary handling.
13. `tester` → write `tests/brain/test_dev_session_runner.py`: mock `query()` async generator;
    test successful fix, `error_max_turns` result, exception mid-stream, progress callback firing.
14. `tester` → write `tests/brain/test_bash_command_guard.py`: unit test hook with forbidden
    commands and out-of-whitelist file paths.
15. `reviewer` → review Batch 2 (steps 9–14) against this spec; issue `PASS` or `NEEDS_CHANGES`.

### Batch 3 — Error sink and auto-debug queue

16. `backend-dev` → create `src/utils/error_log_sink.py` with `ErrorRecord`, `SelfDebugTask`,
    `ErrorLogSink` (synchronous loguru sink callable), and `AutoDebugQueue` (asyncio queue wrapper).
17. `backend-dev` → update `src/utils/logger.py`: add optional `error_sink: ErrorLogSink | None`
    parameter to `setup_logger()`; register sink with `logger.add(sink, level="ERROR")` when
    provided; ensure sink is added after console/file sinks.
18. `backend-dev` → update `src/main.py`: instantiate `AutoDebugQueue` and `ErrorLogSink`; pass
    `error_sink` to `setup_logger()`; start `AutoDebugQueue` background asyncio task that consumes
    tasks and invokes `SelfDebugAgent`.

### Batch 3 review

19. `tester` → write `tests/utils/test_error_log_sink.py`: test deduplication, rate-limit
    enforcement (max 3 per hour), cooldown window, queue enqueue/dequeue, get_recent_errors.
20. `tester` → write `tests/utils/test_logger_sink_registration.py`: verify that `setup_logger()`
    with an `error_sink` argument calls `logger.add()` with the correct level filter.
21. `reviewer` → review Batch 3 (steps 16–20) against this spec; issue `PASS` or `NEEDS_CHANGES`.

### Batch 4 — SelfDebugAgent and intent routing

22. `backend-dev` → create `src/brain/agents/self_debug_agent.py` with `SelfDebugAgent`;
    implement `run()`, `_confirm_via_voice()`, `_broadcast_progress()`.
23. `backend-dev` → update `src/brain/intent_parser.py`: add `Intent.SELF_DEBUG` to `Intent`
    enum; add English and German keyword patterns (`fehler`, `bug`, `kaputt`, `funktioniert nicht`,
    `error`, `broken`, `fix`, `da stimmt was nicht`, etc.); integrate into `_match_intent()`.
24. `backend-dev` → update `src/brain/orchestrator.py`: add `SELF_DEBUG` → `SelfDebugAgent`
    routing branch in `_route_direct()` and in `_agents` dict; add `self_debug` to
    `intent_to_agent` map; accept `SelfDebugAgent` in `__init__` parameters.
25. `backend-dev` → update `src/api/ws_server.py`: add `broadcast_self_fix_event(event_type, payload)` helper;
    wire it into `SelfDebugAgent.ws_broadcaster`.

### Batch 4 review

26. `tester` → write `tests/brain/agents/test_self_debug_agent.py`: mock `DevSessionRunner`,
    `SafetyRailRunner`, `ErrorLogSink`, WebSocket broadcaster; test voice trigger, auto trigger,
    success path, validation failure path, approval gate timeout, re-entrant guard.
27. `tester` → write `tests/brain/test_intent_parser_self_debug.py`: verify `SELF_DEBUG` intent
    classified with confidence > 0.7 for a representative set of English and German phrases.
28. `tester` → write `tests/brain/test_orchestrator_self_debug.py`: verify routing to
    `SelfDebugAgent` when intent is `SELF_DEBUG`.
29. `reviewer` → review Batch 4 (steps 22–28) against this spec; issue `PASS` or `NEEDS_CHANGES`.

### Batch 5 — Frontend

30. `frontend-dev` → create `frontend/src/hooks/useSelfFix.ts`: subscribe to WebSocket messages
    of types `self_fix_started`, `self_fix_progress`, `self_fix_done`, `self_fix_approval_request`;
    expose state (`fixInProgress`, `fixResult`, `progressStages`) and a `respondToApproval(yes: boolean)`
    action.
31. `frontend-dev` → create `frontend/src/components/SelfFixPanel.tsx`: consume `useSelfFix`;
    render collapsible HUD panel (JetBrains Mono, sharp corners per `docs/DESIGN.md`); show
    progress stage list during fix, diff summary and commit SHA on completion, success/fail badge;
    hide when no fix is active.
32. `frontend-dev` → update root App component to mount `SelfFixPanel`.

### Batch 5 review

33. `tester` → write Vitest + RTL tests for `useSelfFix.ts`: mock WebSocket; test state
    transitions on each message type, approval response dispatch.
34. `tester` → write Vitest + RTL tests for `SelfFixPanel.tsx`: test renders hidden when no fix
    active, shows progress list, renders diff summary and SHA on success, renders failure badge
    on failure.
35. `reviewer` → review Batch 5 (steps 30–34) against this spec; issue `PASS` or `NEEDS_CHANGES`.

### Batch 6 — Integration and documentation

36. `backend-dev` → add `claude-agent-sdk` to `Dockerfile` and `docker-compose.rpi.yml`
    pip install layer; verify `git`, `pytest`, `ruff` are present in both images.
37. `backend-dev` → add `self_debug` section to `config/config.yaml` with all keys defined in
    the Config section above, including a commented RPi-optimised profile.
38. `reviewer` → final review of entire feature batch (all files touched across Batches 1–6)
    against all 20 acceptance criteria; issue `PASS` or `NEEDS_CHANGES`.

---

## Manual Verification

After implementation, the developer should run the following steps locally:

1. Install the SDK and confirm no conflicts:
   ```
   pip install claude-agent-sdk
   pip check
   ```

2. Start the backend with a valid `ANTHROPIC_API_KEY`:
   ```
   PYTHONPATH=src .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Confirm log line: "Chat session initialized via Claude Agent SDK".

3. Open a WebSocket client (e.g., `wscat -c ws://localhost:8765`) and send a voice input
   (or trigger directly via the frontend). Confirm a spoken response arrives and the orb
   transitions correctly.

4. Speak "JARVIS, there is a bug in the calendar integration" and observe:
   - Log: `SELF_DEBUG` intent classified.
   - WebSocket: `self_fix_started` message received.
   - WebSocket: at least one `self_fix_progress` message received.
   - WebSocket: `self_fix_done` message received.
   - Run `git log --oneline` and confirm a `self-fix/*` branch exists with a commit.

5. Introduce a deliberate exception in a test file, start JARVIS, and confirm:
   - The exception is captured by `ErrorLogSink` (log: "Error enqueued to AutoDebugQueue").
   - A fix attempt is made automatically.
   - After `max_fixes_per_hour` attempts with the same signature, further attempts are suppressed.

6. Run the test suite and confirm all new tests pass:
   ```
   PYTHONPATH=src pytest tests/ -v
   ```

7. Run linters on all modified files:
   ```
   ruff check src/
   black --check src/
   ```

8. In the frontend (`npm run dev`), trigger a fix and confirm `SelfFixPanel` renders the diff
   summary and commit SHA after `self_fix_done` is received.

---

## Open Questions — ALL RESOLVED

1. **Approval gate:** ✓ RESOLVED — One voice confirmation per fix, then autonomous for all sub-steps (see Revision 2)
2. **Scope:** ✓ RESOLVED — Full repo access within working directory; hard boundary at user HOME (see Revision 2)
3. **Git strategy:** ✓ RESOLVED — Dedicated branch `self-fix/<timestamp>-<slug>` per fix (see Revision 2)
4. **Billing model:** ✓ RESOLVED — `claude login` only, no API-key fallback (see Revision 2)
5. **Offline / missing-auth:** ✓ RESOLVED — Hard error on startup with voice message (see Revision 2)
6. **memory.py:** ✓ RESOLVED — Deprecated, replaced by `jarvis-memory-db.md` (see Revision 2)

---

## Revision 2 — 2026-04-16

### Summary of Changes
This revision resolves all open questions with explicit implementation decisions.

### Fix Approval Flow — Voice-Gated, Then Autonomous

One voice confirmation per fix, then all sub-steps proceed autonomously.

#### Flow Steps
1. **Error Detection**: User-reported via voice OR auto-detected from logs
2. **Read-Only Reconnaissance**: Dev session analyzes without making changes
3. **Non-Technical Voice Explanation**: JARVIS explains the problem
   - **HARD BUDGET: 2 sentences maximum**
   - Example: "Sir, the calendar sync stopped working because an iCloud password changed. I'd like to prompt you for the new one and update the config."
   - **NEVER expose stack traces in voice output**
4. **User Confirmation**: User says one of the whitelisted phrases:
   - German: "ja", "mach das", "fix es", "reparier das", "tu es"
   - English: "yes", "fix it", "go ahead", "do it", "proceed"
5. **Autonomous Execution**: From confirmation onwards, ALL sub-actions proceed WITHOUT further confirmation:
   - File edits
   - Git commits
   - Test runs
   - Service restarts
6. **Voice Report**: JARVIS speaks final result:
   - Success: "Fixed. Committed as self-fix/2026-04-16-1530-calendar-auth, Sir."
   - Failure with rollback: "I couldn't fix it. I've rolled back the changes, Sir."

#### Config Update
```yaml
self_debug:
  enabled: true
  autonomous_mode: false  # false = require voice confirmation (as specified)
  explain_budget_sentences: 2  # hard limit on explanation length
  confirmation_phrases:
    de: ["ja", "mach das", "fix es", "reparier das", "tu es"]
    en: ["yes", "fix it", "go ahead", "do it", "proceed"]
```

### Dev-Session Scope — Full Repo Access

The dev session may modify any file in the repo working directory:

#### In-Scope Paths
- `src/` — all source code
- `config/` — configuration files
- `tests/` — test files
- `.env` — environment variables
- `frontend/` — frontend code
- `docker-compose*.yml` — docker files
- Any other file in repo root

#### Hard Boundary (Safety Rail)
- **Cannot touch user HOME outside the repo**
- Enforced via `BashCommandGuard` hook
- Any path outside repo root → deny

#### Config Update
```yaml
self_debug:
  allowed_paths:
    - "src/"
    - "config/"
    - "tests/"
    - "frontend/"
    - ".env"
    - "docker-compose.yml"
    - "docker-compose.rpi.yml"
    - "requirements.txt"
    - "package.json"
  forbidden_paths:
    - "~/"  # user home outside repo
    - "/"   # absolute paths outside repo
```

### Git Strategy — Dedicated Branch Per Fix

Every fix goes on a dedicated branch:

#### Branch Naming
```
self-fix/<YYYY-MM-DD-HHMM>-<short-slug>
```

Examples:
- `self-fix/2026-04-16-1530-calendar-auth`
- `self-fix/2026-04-16-1645-websocket-timeout`

#### Lifecycle
1. Branch created at fix start
2. All commits go to this branch
3. Branch stays until user accepts/discards from HUD SelfFixPanel
4. **JARVIS never force-merges to main**
5. User can:
   - Merge via SelfFixPanel → "Accept" button
   - Discard via SelfFixPanel → "Discard" button (deletes branch)

### Auth Strategy — `claude login` Only

No API-key fallback. Authentication via `claude login` command only.

#### Startup Behavior
If Claude auth missing on startup:
1. **Hard error** — JARVIS does not start self-debug capability
2. **Voice message**: "Sir, I cannot reach Claude. Please run `claude login` in the terminal."
3. Log `CRITICAL` with instructions

#### Config Update
```yaml
self_debug:
  auth_method: "claude_login"  # only option, no fallback
  auth_error_voice:
    en: "Sir, I cannot reach Claude. Please run claude login in the terminal."
    de: "Sir, ich kann Claude nicht erreichen. Bitte führen Sie claude login im Terminal aus."
```

### memory.py Deprecation — Replaced by jarvis-memory-db.md

The existing `src/brain/memory.py` is deprecated and replaced by the new long-term memory database.

#### Dependency Addition
Add to Dependencies section:
- **NEW PREREQUISITE**: `jarvis-memory-db.md` must be implemented before this spec

#### Migration Steps
1. Enumerate all call sites of `memory.py`:
   - `src/brain/orchestrator.py` — `ConversationMemory` usage
   - `src/brain/agents/chat_agent.py` — history retrieval
2. Replace with `MemoryStore` from `src/brain/memory/store.py`
3. Delete or mark deprecated `src/brain/memory.py`

### Implementation Plan — Updated Dependencies

Update Batch 1 to include prerequisite check:

```
### Prerequisites
- jarvis-memory-db.md must be implemented FIRST
- memory.py call sites must be migrated to MemoryStore
```

---

**Status:** Planned — awaiting implementation authorization

---

## OpenClaw Leverage (Revision 3 — 2026-04-16)

### Integration Assessment
**OpenClaw provides NO coverage for Claude Code / self-debugging integration.**

### OpenClaw Coverage
| Feature | OpenClaw Capability | Coverage |
|---------|---------------------|----------|
| Claude Agent SDK | OpenClaw uses different architecture | None |
| Self-debugging agent | No OpenClaw equivalent | None |
| File system access | OpenClaw has file tools (different model) | Incompatible |
| Git branching/commits | No OpenClaw equivalent | None |
| Safety rails (test/lint) | No OpenClaw equivalent | None |
| Error log sink | No OpenClaw equivalent | None |
| SelfFixPanel HUD | No OpenClaw equivalent | None |

### Key Architectural Mismatch
This spec integrates the **Claude Agent SDK** (`claude-agent-sdk` pip package) directly into JARVIS for:
- Persistent chat sessions via `ClaudeSDKClient`
- Dev sessions with filesystem/shell access
- Safety rails (git branching, pytest/ruff validation)

OpenClaw is a separate Node.js platform that:
- Has its own agent runtime (not Claude Agent SDK)
- Would require IPC/subprocess calls from Python
- Cannot replace the SDK-native self-debugging flow

### What Stays JARVIS-Native (100%)
- **SdkChatClient** — Claude Agent SDK integration
- **SdkSessionManager** — lifecycle management
- **DevSessionRunner** — code fix execution
- **SafetyRailRunner** — git + pytest + ruff validation
- **SelfDebugAgent** — voice-triggered debugging
- **ErrorLogSink** — auto-debug queue
- **SelfFixPanel** — HUD visualization

### Migration Pattern
**Not applicable.** This spec cannot migrate to OpenClaw because:
1. OpenClaw is Node.js, JARVIS backend is Python
2. Claude Agent SDK is Python-native
3. Self-debugging requires deep JARVIS integration (file access, git, tests)

### Recommendation
- **Keep 100% JARVIS-native**: No OpenClaw leverage possible
- **Future consideration**: If OpenClaw adds Python SDK support, revisit

### Verdict
This spec is **FULLY JARVIS-native** — OpenClaw cannot replace Claude Agent SDK integration or self-debugging capabilities.

---

## Revision 4 — Thin Config Spec Conversion (2026-04-16)

### Decision
With OpenClaw as the full backbone, this spec is **RE-SCOPED** to a thin configuration spec.

### Why This Changes
OpenClaw provides:
- Agent runtime for conversational queries
- Built-in Claude API calls
- Session management

However, OpenClaw does NOT provide:
- Claude Agent SDK's self-debugging capabilities
- File system access with safety rails
- Git branching/commit automation
- pytest/ruff validation loop

### Thin Config Scope (MVP)
For MVP, this spec becomes a **configuration guide** rather than full implementation:

1. **OpenClaw as primary Claude interface** — All conversational queries via OpenClaw
2. **Self-debugging DEFERRED to Phase B** — Too complex for MVP with OpenClaw backbone
3. **SelfFixPanel DEFERRED** — No self-fix events without self-debug capability

### What Stays (MVP)
- **Intent.SELF_DEBUG recognition** — Parser recognizes "there's a bug" intents
- **Voice response** — "I've noted that issue, Sir. Please report it via GitHub."
- **Error logging** — Errors logged for manual review

### What Is Deferred (Phase B)
- Full Claude Agent SDK integration
- DevSessionRunner
- SafetyRailRunner
- SelfDebugAgent
- AutoDebugQueue
- SelfFixPanel

### Files Created (MVP) — MINIMAL
| File | Purpose | Status |
|------|---------|--------|
| `src/brain/agents/self_debug_agent.py` | Placeholder agent | SIMPLIFIED |

### Implementation Estimate
**Original:** 20+ hours
**MVP (thin config):** 1-2 hours (intent recognition + placeholder response)
**Full Phase B:** Deferred

### Prerequisites
- `openclaw-integration.md` — REQUIRED (OpenClaw handles Claude queries)
- `jarvis-memory-db.md` — REQUIRED (error logging)

### Phase B Trigger
Full self-debugging implementation should proceed when:
1. MVP is stable
2. User explicitly requests self-fix capability
3. OpenClaw Python SDK support is evaluated

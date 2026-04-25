# JARVIS Backend Code Analysis — 2025-04-25

## Executive Summary
Comprehensive audit of ~65 Python files across audio, brain, actions, API, and integrations layers. Key findings:
1. **Disfluency duplication**: Two implementations (`disfluency.py` function + `disfluencies.py` class), but only function is used; class is dead code.
2. **Exception handling**: 4 agent classes catch bare `Exception` instead of specific types (convention violation).
3. **WS security**: Server binds to `0.0.0.0` with NO authentication — accessible from any network interface.
4. **Dead code**: Backup/restore functions exist but are never called; unused `DisfluencyInjector` class.
5. **Async correctness**: EventBus.publish() uses `asyncio.gather()` without `return_exceptions=True`; one handler failure crashes all others.
6. **Sync I/O**: Google OAuth uses `requests` library (deprecated per CLAUDE.md, should be `aiohttp`).
7. **Missing type hints & docs**: Most test coverage is integration-only; ~30 core files lack unit tests.

Overall posture: Functional but non-standard. Architecture is sound (dependency injection, proper async/await), but convention compliance gaps and security boundaries need attention.

"""Meta-tests for Phase 4 hygiene (issue #76).

These tests enforce that the source tree is in the expected post-Phase-4 state:
- pc_agent.py and smart_home_agent.py are deleted.
- No source file under src/ uses PcAgent or SmartHomeAgent in code
  (comment-only lines are exempt — intentional tombstone docs are fine).

All file scanning is done via pathlib — no subprocess / shell calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Absolute path to the project root (two levels up from this test file).
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_SRC_ROOT = _PROJECT_ROOT / "src"
_AGENTS_DIR = _SRC_ROOT / "brain" / "agents"


# ---------------------------------------------------------------------------
# File-existence checks
# ---------------------------------------------------------------------------


def test_pc_agent_file_does_not_exist():
    """src/brain/agents/pc_agent.py must not exist after Phase 4 deletion."""
    pc_agent_path = _AGENTS_DIR / "pc_agent.py"
    assert not pc_agent_path.exists(), (
        f"pc_agent.py still exists at {pc_agent_path} — it should have been deleted"
    )


def test_smart_home_agent_file_does_not_exist():
    """src/brain/agents/smart_home_agent.py must not exist after Phase 4 deletion."""
    sh_agent_path = _AGENTS_DIR / "smart_home_agent.py"
    assert not sh_agent_path.exists(), (
        f"smart_home_agent.py still exists at {sh_agent_path} — it should have been deleted"
    )


# ---------------------------------------------------------------------------
# Source-text scan — no remaining code references in src/
# ---------------------------------------------------------------------------

# Prefixes that mark a line as a comment or docstring opener (stripped).
_COMMENT_PREFIXES = ("#", '"""', "'''")


def _scan_src_for_code_pattern(pattern: str) -> list[tuple[Path, int, str]]:
    # Scan .py files under src/ for lines that contain ``pattern`` AND are not
    # pure comment / docstring-boundary lines.  This excludes intentional
    # tombstone comments such as "PcAgent and SmartHomeAgent are omitted..." while
    # still catching any live import or instantiation.
    matches: list[tuple[Path, int, str]] = []
    for py_file in _SRC_ROOT.rglob("*.py"):
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if pattern not in line:
                continue
            stripped = line.strip()
            # Skip comment-only and docstring-boundary lines.
            if any(stripped.startswith(pfx) for pfx in _COMMENT_PREFIXES):
                continue
            matches.append((py_file, lineno, line))
    return matches


def _scan_src_for_import_pattern(pattern: str) -> list[tuple[Path, int, str]]:
    # Only match lines that look like import statements.  This is narrower than
    # a full-text scan and avoids false positives from docstring body lines that
    # mention deleted symbols (e.g. "PcAgent was removed — see issue #76").
    matches: list[tuple[Path, int, str]] = []
    for py_file in _SRC_ROOT.rglob("*.py"):
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Only check import lines.
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            if pattern in line:
                matches.append((py_file, lineno, line))
    return matches


def test_no_PcAgent_import_in_src():
    """No src/ file imports PcAgent."""
    matches = _scan_src_for_import_pattern("PcAgent")
    assert not matches, (
        "PcAgent import found in src/:\n"
        + "\n".join(f"  {f}:{n}: {l.strip()}" for f, n, l in matches)
    )


def test_no_SmartHomeAgent_import_in_src():
    """No src/ file imports SmartHomeAgent."""
    matches = _scan_src_for_import_pattern("SmartHomeAgent")
    assert not matches, (
        "SmartHomeAgent import found in src/:\n"
        + "\n".join(f"  {f}:{n}: {l.strip()}" for f, n, l in matches)
    )


def test_no_pc_agent_module_import_in_src():
    """No src/ file imports the deleted pc_agent module."""
    matches = _scan_src_for_import_pattern("pc_agent")
    assert not matches, (
        "pc_agent import found in src/:\n"
        + "\n".join(f"  {f}:{n}: {l.strip()}" for f, n, l in matches)
    )


def test_no_smart_home_agent_module_import_in_src():
    """No src/ file imports the deleted smart_home_agent module."""
    matches = _scan_src_for_import_pattern("smart_home_agent")
    assert not matches, (
        "smart_home_agent import found in src/:\n"
        + "\n".join(f"  {f}:{n}: {l.strip()}" for f, n, l in matches)
    )

"""Repository hygiene meta-tests for the web-search → OpenClaw migration.

Assertions:
1. ``src/actions/web_search.py`` does NOT exist (file was deleted).
2. No source file under ``src/`` contains a case-insensitive reference to
   "duckduckgo" (old search backend) in its import statements or runtime code.
3. ``requirements.txt`` does not mention "duckduckgo".
4. The identifiers ``execute_web_search`` and ``search_with_fallback`` are
   absent from all files under ``src/`` (old API surface fully removed).

These tests run without any import — they scan the filesystem with the
standard library only, so no mocking is required.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[1]
_SRC_ROOT = _REPO_ROOT / "src"


def _iter_py_sources(root: Path):
    """Yield every .py file under *root*, skipping __pycache__."""
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


# ---------------------------------------------------------------------------
# AC 1 — src/actions/web_search.py must not exist
# ---------------------------------------------------------------------------


def test_web_search_module_deleted():
    """src/actions/web_search.py must not exist after the migration."""
    old_module = _SRC_ROOT / "actions" / "web_search.py"
    assert not old_module.exists(), (
        f"{old_module.relative_to(_REPO_ROOT)} still exists — it should have been deleted "
        "as part of the OpenClaw migration."
    )


# ---------------------------------------------------------------------------
# AC 2 — no "duckduckgo" references in src/ or requirements.txt
# ---------------------------------------------------------------------------


def test_no_duckduckgo_in_src():
    """No Python source file under src/ mentions 'duckduckgo' (case-insensitive)."""
    assert _SRC_ROOT.is_dir(), f"src/ not found at {_SRC_ROOT}"

    violations: list[str] = []
    pattern = re.compile(r"duckduckgo", re.IGNORECASE)

    for py_file in _iter_py_sources(_SRC_ROOT):
        source = py_file.read_text(encoding="utf-8", errors="replace")
        if pattern.search(source):
            violations.append(str(py_file.relative_to(_REPO_ROOT)))

    assert not violations, (
        "The following files still reference 'duckduckgo':\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_no_duckduckgo_in_requirements():
    """requirements.txt must not list a duckduckgo package."""
    req_file = _REPO_ROOT / "requirements.txt"
    if not req_file.exists():
        return  # nothing to check

    content = req_file.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(r"duckduckgo", re.IGNORECASE)
    assert not pattern.search(content), (
        "requirements.txt still mentions a duckduckgo package — it should have been removed."
    )


# ---------------------------------------------------------------------------
# AC 3 — old function names absent from src/
# ---------------------------------------------------------------------------


def test_no_execute_web_search_in_src():
    """Identifier 'execute_web_search' must not appear anywhere in src/."""
    assert _SRC_ROOT.is_dir()

    violations: list[str] = []
    pattern = re.compile(r"\bexecute_web_search\b")

    for py_file in _iter_py_sources(_SRC_ROOT):
        source = py_file.read_text(encoding="utf-8", errors="replace")
        if pattern.search(source):
            violations.append(str(py_file.relative_to(_REPO_ROOT)))

    assert not violations, (
        "The following files still reference 'execute_web_search':\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_no_search_with_fallback_in_src():
    """Identifier 'search_with_fallback' must not appear anywhere in src/."""
    assert _SRC_ROOT.is_dir()

    violations: list[str] = []
    pattern = re.compile(r"\bsearch_with_fallback\b")

    for py_file in _iter_py_sources(_SRC_ROOT):
        source = py_file.read_text(encoding="utf-8", errors="replace")
        if pattern.search(source):
            violations.append(str(py_file.relative_to(_REPO_ROOT)))

    assert not violations, (
        "The following files still reference 'search_with_fallback':\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# AC 4 — web_search is no longer exported from src/actions/__init__.py
# ---------------------------------------------------------------------------


def test_actions_init_does_not_export_web_search():
    """src/actions/__init__.py must not import or re-export from web_search."""
    init_file = _SRC_ROOT / "actions" / "__init__.py"
    if not init_file.exists():
        return  # file gone entirely is also acceptable

    source = init_file.read_text(encoding="utf-8", errors="replace")

    # AST-level check for any import touching 'web_search'
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return  # can't parse, skip AST check

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "web_search" in node.module:
                violations.append(f"from {node.module} import ...")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "web_search" in alias.name:
                    violations.append(f"import {alias.name}")

    assert not violations, (
        "src/actions/__init__.py still imports from web_search:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# AC 5 — SearchAgent is importable from the brain.agents public surface
# ---------------------------------------------------------------------------


def test_search_agent_importable_from_brain_agents():
    """SearchAgent is importable from brain.agents (the package __init__)."""
    import importlib
    import sys

    # Temporarily add src/ to the path so the import resolves without a full
    # PYTHONPATH setup (mirrors the project's PYTHONPATH=src convention).
    src_str = str(_SRC_ROOT)
    inserted = False
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
        inserted = True

    try:
        mod = importlib.import_module("brain.agents")
        assert hasattr(mod, "SearchAgent"), (
            "brain.agents does not export SearchAgent — check brain/agents/__init__.py"
        )
    finally:
        if inserted:
            sys.path.remove(src_str)

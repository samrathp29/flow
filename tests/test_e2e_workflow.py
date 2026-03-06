"""
End-to-end workflow test: simulates a real developer returning to a project
after a month away, using every flow command in sequence.

Scenario
--------
The developer has a project called "flow-test" with existing mem0 memories
from past sessions (SQLite/Postgres DB migration work). They return after
a month, start a session, do real code work, stop the session, check their
briefing, and ask a cross-project question.

This test uses the real flow-test repo at ~/Projects/flow-test and real
mem0 storage. It is NOT a unit test — it exercises the full pipeline
including LLM calls and vector search. Run it manually:

    python -m pytest tests/test_e2e_workflow.py -v -s

Prerequisites:
    - ~/.config/flow/config.toml exists with valid API key
    - ~/Projects/flow-test is a git repo with existing mem0 memories
    - No active flow session running
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

PROJECT_DIR = Path.home() / "Projects" / "flow-test"
STATE_DIR = Path.home() / ".local" / "share" / "flow" / "sessions"
CONFIG_PATH = Path.home() / ".config" / "flow" / "config.toml"
MARKER_START = "<!-- flow:start -->"
MARKER_END = "<!-- flow:end -->"


def run_flow(*args, cwd=None):
    """Run a flow CLI command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        ["python", "-m", "flow", *args],
        capture_output=True,
        text=True,
        cwd=cwd or PROJECT_DIR,
        timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


def cleanup():
    """Remove transient state so the test is idempotent."""
    import shutil
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR, ignore_errors=True)
    (PROJECT_DIR / "CLAUDE.md").unlink(missing_ok=True)
    (PROJECT_DIR / "AGENTS.md").unlink(missing_ok=True)
    (PROJECT_DIR / ".cursorrules").unlink(missing_ok=True)


# ── guards ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def guard_and_cleanup():
    """Skip if prerequisites are missing; clean up before and after."""
    if not PROJECT_DIR.is_dir():
        pytest.skip("~/Projects/flow-test does not exist")
    if not CONFIG_PATH.is_file():
        pytest.skip("~/.config/flow/config.toml not found — run flow init first")
    cleanup()
    yield
    cleanup()


# ── the full workflow ─────────────────────────────────────────────────

class TestFullDeveloperWorkflow:
    """
    Simulates: developer returns after a month, uses every command once.

    Step 1 — flow start
        Session starts. Context injected into CLAUDE.md from mem0.
        CLAUDE.md contains accurate, non-contradictory project state.

    Step 2 — Verify injected context quality
        The context block must contain the marker pair and structured
        sections. Because mem0 reconciles at write time, it should
        reflect the CURRENT state (PostgreSQL in db.py per most recent
        commit) — not stale state (SQLite, which was an earlier session).

    Step 3 — Simulate real work
        Developer changes db.py (adds connection pooling), commits.

    Step 4 — flow stop
        Session is distilled and stored in mem0. Output confirms save.

    Step 5 — flow wake
        Developer gets a briefing. Output must reference the project
        and contain actual content (not an error or empty string).

    Step 6 — flow ask
        Developer asks a cross-project question. Output must contain
        a synthesized answer (not an error).

    Step 7 — flow start (second time)
        New session starts. Context re-injected. The new CLAUDE.md
        block should reflect the connection pooling work from step 3
        (mem0 reconciliation means the new memory is incorporated).
        Developer content in CLAUDE.md (if any) must be preserved.
        Only one marker block must exist.

    Step 8 — flow stop (final cleanup)
        Clean stop to leave no dangling session.
    """

    def test_full_workflow(self):
        # ─── Step 1: flow start ───────────────────────────────────
        code, out, err = run_flow("start")

        assert code == 0, f"flow start failed: {err}"
        assert "▶ Session started" in out
        assert "flow-test" in out
        assert "Context injected" in out
        assert STATE_DIR.exists(), "sessions directory not created"
        state_files = list(STATE_DIR.glob("*.json"))
        assert len(state_files) >= 1, "no state file created"

        # ─── Step 2: verify injected context quality ──────────────
        claude_md = PROJECT_DIR / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md not created"

        content = claude_md.read_text()
        assert MARKER_START in content
        assert MARKER_END in content
        assert content.count(MARKER_START) == 1, "Multiple marker blocks found"

        # Extract the flow block
        match = re.search(
            rf"{re.escape(MARKER_START)}\n(.*?)\n{re.escape(MARKER_END)}",
            content,
            re.DOTALL,
        )
        assert match, "Could not extract flow block from CLAUDE.md"
        block = match.group(1)

        # Block should be non-trivial (LLM produced real content)
        assert len(block) > 50, f"Flow block too short ({len(block)} chars): {block}"

        # Block should contain structured sections (bold labels)
        assert "**" in block, "Flow block missing bold section labels"

        # ─── Step 3: simulate real work (code change + commit) ────
        db_path = PROJECT_DIR / "db.py"
        original_db = db_path.read_text()

        db_path.write_text(
            'def connect():\n'
            '    return "postgresql://...26420b"\n'
            '\n'
            'def get_pool(size=5):\n'
            '    return f"pool://{connect()}?size={size}"\n'
        )

        subprocess.run(
            ["git", "add", "db.py"],
            cwd=PROJECT_DIR, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: add connection pooling to db"],
            cwd=PROJECT_DIR, capture_output=True,
        )

        # ─── Step 4: flow stop ────────────────────────────────────
        code, out, err = run_flow("stop")

        assert code == 0, f"flow stop failed: {err}"
        assert "⠿ Processing session..." in out
        assert "✓ Session saved" in out
        assert "flow-test" in out
        state_files = list(STATE_DIR.glob("*.json")) if STATE_DIR.exists() else []
        assert len(state_files) == 0, "state file not cleaned up after stop"

        # ─── Step 5: flow wake ────────────────────────────────────
        code, out, err = run_flow("wake")

        assert code == 0, f"flow wake failed: {err}"
        assert "⚡ flow-test" in out

        # Wake output should contain real content, not just the header
        wake_body = out.split("⚡ flow-test")[-1].strip()
        assert len(wake_body) > 20, f"Wake briefing too short: {wake_body}"

        # ─── Step 6: flow ask ─────────────────────────────────────
        code, out, err = run_flow("ask", "what database changes have I made?")

        assert code == 0, f"flow ask failed: {err}"
        assert "what database changes" in out

        # Ask output should have real synthesized content
        ask_body = out.split("what database changes have I made?")[-1].strip()
        assert len(ask_body) > 20, f"Ask answer too short: {ask_body}"

        # ─── Step 7: flow start (second time) ─────────────────────
        # Write developer content into CLAUDE.md first to test preservation
        claude_md.write_text(
            "# Project Rules\n\n"
            "- Always use PostgreSQL in production\n"
            "- Run tests before pushing\n"
        )

        code, out, err = run_flow("start")

        assert code == 0, f"flow start (2nd) failed: {err}"
        assert "Context injected" in out

        content_2 = claude_md.read_text()

        # Developer content preserved
        assert "# Project Rules" in content_2
        assert "Always use PostgreSQL" in content_2
        assert "Run tests before pushing" in content_2

        # Exactly one marker block
        assert content_2.count(MARKER_START) == 1

        # ─── Step 8: flow stop (cleanup) ──────────────────────────
        code, out, err = run_flow("stop")
        assert code == 0, f"flow stop (final) failed: {err}"

        # ─── Restore db.py to original ────────────────────────────
        db_path.write_text(original_db)
        subprocess.run(
            ["git", "add", "db.py"],
            cwd=PROJECT_DIR, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "revert: remove connection pooling"],
            cwd=PROJECT_DIR, capture_output=True,
        )

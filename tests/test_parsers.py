"""Unit tests for all log parsers."""

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from flow.parsers.base import ParserUnavailable
from flow.parsers.claude_code import ClaudeCodeParser
from flow.parsers.codex import CodexParser
from flow.parsers.cursor import CursorParser, CHAT_KEY
from flow.session import Turn

FIXTURES = Path(__file__).parent / "fixtures"
# Session window: 2025-03-04T09:00:00Z — anything before is filtered out
SINCE = datetime(2025, 3, 4, 9, 0, 0, tzinfo=timezone.utc)


# ---------- Claude Code Parser ----------


class TestClaudeCodeParser:
    """Tests for ClaudeCodeParser reading JSONL fixture."""

    @pytest.fixture(autouse=True)
    def setup_fixture(self, tmp_path):
        """Set up a fake Claude project dir with the JSONL fixture."""
        project_path = "/Users/dev/project"
        encoded = project_path.replace("/", "-")
        project_dir = tmp_path / ".claude" / "projects" / encoded
        project_dir.mkdir(parents=True)
        shutil.copy(FIXTURES / "claude_code_session.jsonl", project_dir / "session.jsonl")

        self.parser = ClaudeCodeParser()
        self.project_path = project_path
        self.project_dir = project_dir
        self.tmp_path = tmp_path

    def _patch_home(self):
        return patch.object(
            ClaudeCodeParser, "_project_dir", return_value=self.project_dir
        )

    def test_read_filters_by_timestamp(self):
        """Only turns after `since` should be returned."""
        with self._patch_home():
            turns = self.parser.read(self.project_path, SINCE)
        # The fixture has 4 user/assistant messages after 10:00, 1 before 08:00
        assert len(turns) == 4
        assert all(t.timestamp >= "2025-03-04T10:00:00" for t in turns)

    def test_read_extracts_correct_roles(self):
        with self._patch_home():
            turns = self.parser.read(self.project_path, SINCE)
        roles = [t.role for t in turns]
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_read_skips_tool_use_and_thinking(self):
        """tool_use records and thinking blocks should be excluded."""
        with self._patch_home():
            turns = self.parser.read(self.project_path, SINCE)
        contents = " ".join(t.content for t in turns)
        assert "tool call" not in contents
        assert "Let me think" not in contents

    def test_extract_text_array_format(self):
        """Content as [{type: text, text: ...}] should be joined."""
        with self._patch_home():
            turns = self.parser.read(self.project_path, SINCE)
        # Second turn has array content
        assert "session token" in turns[1].content

    def test_read_returns_sorted(self):
        with self._patch_home():
            turns = self.parser.read(self.project_path, SINCE)
        timestamps = [t.timestamp for t in turns]
        assert timestamps == sorted(timestamps)

    def test_unavailable_when_no_dir(self):
        """Parser should raise ParserUnavailable when project dir doesn't exist."""
        parser = ClaudeCodeParser()
        with pytest.raises(ParserUnavailable):
            parser.read("/nonexistent/project", SINCE)

    def test_is_available_false_when_no_dir(self):
        parser = ClaudeCodeParser()
        assert parser.is_available("/nonexistent/project/path") is False


# ---------- Codex Parser ----------


class TestCodexParser:
    """Tests for CodexParser reading JSONL fixture."""

    @pytest.fixture(autouse=True)
    def setup_fixture(self, tmp_path):
        """Set up a fake Codex sessions dir with date-sharded files."""
        sessions_root = tmp_path / ".codex" / "sessions"
        day_dir = sessions_root / "2025" / "03" / "04"
        day_dir.mkdir(parents=True)
        shutil.copy(FIXTURES / "codex_session.jsonl", day_dir / "rollout-001.jsonl")

        self.parser = CodexParser()
        self.parser.SESSIONS_ROOT = sessions_root  # override class attr
        self.tmp_path = tmp_path

    def test_read_filters_by_timestamp(self):
        turns = self.parser.read("/any/project", SINCE)
        # 2 user + 2 assistant within window; 1 old user + 1 system msg filtered
        assert len(turns) == 4

    def test_read_extracts_correct_roles(self):
        turns = self.parser.read("/any/project", SINCE)
        roles = [t.role for t in turns]
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_read_skips_non_assistant_response_items(self):
        """response_item with role != 'assistant' should be skipped."""
        turns = self.parser.read("/any/project", SINCE)
        contents = " ".join(t.content for t in turns)
        assert "System message" not in contents

    def test_read_returns_sorted(self):
        turns = self.parser.read("/any/project", SINCE)
        timestamps = [t.timestamp for t in turns]
        assert timestamps == sorted(timestamps)

    def test_unavailable_when_no_dir(self):
        parser = CodexParser()
        parser.SESSIONS_ROOT = Path("/nonexistent/codex/sessions")
        with pytest.raises(ParserUnavailable):
            parser.read("/any/project", SINCE)

    def test_is_available_false(self):
        parser = CodexParser()
        parser.SESSIONS_ROOT = Path("/nonexistent/codex/sessions")
        assert parser.is_available("/any") is False


# ---------- Cursor Parser ----------

# For Cursor: 2024-03-04T09:00:00Z as since (the fixture timestamps are in 2024)
CURSOR_SINCE = datetime(2024, 3, 4, 9, 0, 0, tzinfo=timezone.utc)


class TestCursorParser:
    """Tests for CursorParser reading SQLite fixture."""

    @pytest.fixture(autouse=True)
    def setup_fixture(self, tmp_path):
        """Set up a fake workspace storage dir with the SQLite fixture."""
        workspace_dir = tmp_path / "workspaceStorage" / "abc123"
        workspace_dir.mkdir(parents=True)
        shutil.copy(
            FIXTURES / "cursor_workspace" / "state.vscdb",
            workspace_dir / "state.vscdb",
        )
        self.parser = CursorParser()
        self.workspace_dir = tmp_path / "workspaceStorage"
        self.tmp_path = tmp_path

    def _patch_storage(self):
        return patch(
            "flow.parsers.cursor.WORKSPACE_STORAGE", self.workspace_dir
        )

    def test_read_filters_by_timestamp(self):
        with self._patch_storage():
            turns = self.parser.read("/Users/dev/project", CURSOR_SINCE)
        # 3 messages (2 user + 1 ai) after 10:00; 1 user at 08:00 filtered
        assert len(turns) == 3

    def test_read_extracts_correct_roles(self):
        with self._patch_storage():
            turns = self.parser.read("/Users/dev/project", CURSOR_SINCE)
        roles = [t.role for t in turns]
        assert roles == ["user", "assistant", "user"]

    def test_delegate_field_priority(self):
        """User text with delegate.a should prefer delegate.a over text field."""
        with self._patch_storage():
            turns = self.parser.read("/Users/dev/project", CURSOR_SINCE)
        # Third turn has delegate.a = "Also add connection pooling"
        user_turns = [t for t in turns if t.role == "user"]
        assert user_turns[1].content == "Also add connection pooling"

    def test_no_match_returns_empty(self):
        with self._patch_storage():
            turns = self.parser.read("/nonexistent/project", CURSOR_SINCE)
        assert turns == []

    def test_unavailable_when_no_dir(self):
        with patch("flow.parsers.cursor.WORKSPACE_STORAGE", Path("/nonexistent")):
            with pytest.raises(ParserUnavailable):
                self.parser.read("/any/project", CURSOR_SINCE)

    def test_is_available_false(self):
        with patch("flow.parsers.cursor.WORKSPACE_STORAGE", Path("/nonexistent")):
            assert self.parser.is_available("/any") is False

    def test_read_returns_sorted(self):
        with self._patch_storage():
            turns = self.parser.read("/Users/dev/project", CURSOR_SINCE)
        timestamps = [t.timestamp for t in turns]
        assert timestamps == sorted(timestamps)

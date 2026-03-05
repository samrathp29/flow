"""Unit tests for proactive context injection."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from flow.context import (
    CONTEXT_QUERIES,
    FORMATTING_PROMPT,
    MARKER_END,
    MARKER_START,
    ContextInjector,
)
from flow.llm import LLMError


def _make_injector():
    """Create a ContextInjector with mocked FlowMemory and LLM."""
    mock_config = MagicMock()
    with patch("flow.context.FlowMemory"), patch("flow.context.LLM"):
        injector = ContextInjector(mock_config)
    injector.flow_memory = MagicMock()
    injector.llm = MagicMock()
    return injector


# ---------- _gather_memories ----------


class TestGatherMemories:
    def test_runs_three_queries(self):
        injector = _make_injector()
        injector.flow_memory.search.return_value = ["memory one"]

        injector._gather_memories("my-project")

        assert injector.flow_memory.search.call_count == 3
        for i, query in enumerate(CONTEXT_QUERIES):
            actual_call = injector.flow_memory.search.call_args_list[i]
            assert actual_call == call("my-project", query, limit=3)

    def test_deduplicates_by_string(self):
        injector = _make_injector()
        # All 3 queries return the same memory
        injector.flow_memory.search.return_value = ["duplicate fact"]

        result = injector._gather_memories("proj")

        assert result == ["duplicate fact"]

    def test_aggregates_unique_results(self):
        injector = _make_injector()
        injector.flow_memory.search.side_effect = [
            ["fact A", "fact B"],
            ["fact B", "fact C"],  # B is duplicate
            ["fact D"],
        ]

        result = injector._gather_memories("proj")

        assert result == ["fact A", "fact B", "fact C", "fact D"]

    def test_returns_empty_when_no_memories(self):
        injector = _make_injector()
        injector.flow_memory.search.return_value = []

        result = injector._gather_memories("proj")

        assert result == []


# ---------- _format_context ----------


class TestFormatContext:
    def test_empty_memories_returns_empty(self):
        injector = _make_injector()

        result = injector._format_context([])

        assert result == ""
        injector.llm.call.assert_not_called()

    def test_calls_llm_with_formatting_prompt(self):
        injector = _make_injector()
        injector.llm.call.return_value = "**Current state:** building auth"

        result = injector._format_context(["building auth", "tried JWT"])

        assert result == "**Current state:** building auth"
        system_prompt, user_msg = injector.llm.call.call_args[0]
        assert system_prompt == FORMATTING_PROMPT
        assert "- building auth" in user_msg
        assert "- tried JWT" in user_msg

    def test_returns_empty_on_llm_error(self):
        injector = _make_injector()
        injector.llm.call.side_effect = LLMError("fail")

        result = injector._format_context(["some memory"])

        assert result == ""


# ---------- _detect_target_files ----------


class TestDetectTargetFiles:
    def test_always_includes_claude_md(self, tmp_path):
        injector = _make_injector()

        targets = injector._detect_target_files(tmp_path)

        assert "CLAUDE.md" in targets

    def test_includes_agents_md_when_exists(self, tmp_path):
        (tmp_path / "AGENTS.md").touch()
        injector = _make_injector()

        targets = injector._detect_target_files(tmp_path)

        assert "AGENTS.md" in targets

    def test_excludes_agents_md_when_absent(self, tmp_path):
        injector = _make_injector()

        targets = injector._detect_target_files(tmp_path)

        assert "AGENTS.md" not in targets

    def test_includes_cursorrules_when_cursor_dir_exists(self, tmp_path):
        (tmp_path / ".cursor").mkdir()
        injector = _make_injector()

        targets = injector._detect_target_files(tmp_path)

        assert ".cursorrules" in targets

    def test_excludes_cursorrules_when_no_cursor_dir(self, tmp_path):
        injector = _make_injector()

        targets = injector._detect_target_files(tmp_path)

        assert ".cursorrules" not in targets


# ---------- _write_file / _inject_or_replace ----------


class TestWriteFile:
    def test_creates_new_file_with_header_and_markers(self, tmp_path):
        injector = _make_injector()
        target = tmp_path / "CLAUDE.md"

        injector._write_file(target, "context block")

        content = target.read_text()
        assert "auto-generated context" in content
        assert MARKER_START in content
        assert MARKER_END in content
        assert "context block" in content

    def test_injects_into_existing_file_preserving_content(self, tmp_path):
        injector = _make_injector()
        target = tmp_path / "CLAUDE.md"
        target.write_text("# My Project Notes\n\nDo not delete this.\n")

        injector._write_file(target, "context block")

        content = target.read_text()
        assert "# My Project Notes" in content
        assert "Do not delete this." in content
        assert MARKER_START in content
        assert "context block" in content

    def test_replaces_existing_marker_block(self, tmp_path):
        injector = _make_injector()
        target = tmp_path / "CLAUDE.md"
        target.write_text(
            f"# Notes\n\n{MARKER_START}\nold context\n{MARKER_END}\n\n## More notes\n"
        )

        injector._write_file(target, "new context")

        content = target.read_text()
        assert "old context" not in content
        assert "new context" in content
        assert "# Notes" in content
        assert "## More notes" in content

    def test_second_injection_replaces_first(self, tmp_path):
        injector = _make_injector()
        target = tmp_path / "CLAUDE.md"

        injector._write_file(target, "first context")
        injector._write_file(target, "second context")

        content = target.read_text()
        assert "first context" not in content
        assert "second context" in content
        assert content.count(MARKER_START) == 1
        assert content.count(MARKER_END) == 1


# ---------- inject (integration) ----------


class TestInject:
    def test_returns_empty_when_no_memories(self, tmp_path):
        injector = _make_injector()
        injector.flow_memory.search.return_value = []

        result = injector.inject("proj", str(tmp_path))

        assert result == []
        injector.llm.call.assert_not_called()

    def test_returns_empty_when_format_fails(self, tmp_path):
        injector = _make_injector()
        injector.flow_memory.search.return_value = ["some memory"]
        injector.llm.call.side_effect = LLMError("fail")

        result = injector.inject("proj", str(tmp_path))

        assert result == []
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_writes_claude_md_by_default(self, tmp_path):
        injector = _make_injector()
        injector.flow_memory.search.return_value = ["building auth"]
        injector.llm.call.return_value = "**Current state:** building auth"

        result = injector.inject("proj", str(tmp_path))

        assert result == ["CLAUDE.md"]
        assert (tmp_path / "CLAUDE.md").exists()
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "building auth" in content

    def test_writes_multiple_files_when_detected(self, tmp_path):
        (tmp_path / "AGENTS.md").touch()
        (tmp_path / ".cursor").mkdir()
        injector = _make_injector()
        injector.flow_memory.search.return_value = ["memory"]
        injector.llm.call.return_value = "formatted context"

        result = injector.inject("proj", str(tmp_path))

        assert "CLAUDE.md" in result
        assert "AGENTS.md" in result
        assert ".cursorrules" in result

    def test_continues_on_single_file_write_failure(self, tmp_path):
        injector = _make_injector()
        injector.flow_memory.search.return_value = ["memory"]
        injector.llm.call.return_value = "formatted context"

        # Make CLAUDE.md path a directory so write fails
        (tmp_path / "CLAUDE.md").mkdir()
        (tmp_path / "AGENTS.md").touch()

        result = injector.inject("proj", str(tmp_path))

        # CLAUDE.md write fails, but AGENTS.md should succeed
        assert "CLAUDE.md" not in result
        assert "AGENTS.md" in result

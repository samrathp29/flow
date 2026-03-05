"""Unit tests for the Formatter class."""

from flow.formatter import Formatter
from flow.session import RawSessionData, Turn


def _make_data(**overrides):
    defaults = {
        "project_name": "test-project",
        "project_path": "/fake/test-project",
        "started_at": "2025-03-04T10:00:00+00:00",
        "ended_at": "2025-03-04T12:00:00+00:00",
        "duration_mins": 120,
        "turns": [],
        "git_diff": "",
        "git_log": "",
    }
    defaults.update(overrides)
    return RawSessionData(**defaults)


def _make_turns(n):
    """Generate n alternating user/assistant turns."""
    turns = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        turns.append(Turn(role=role, content=f"Message {i}", timestamp=f"2025-03-04T10:{i:02d}:00+00:00"))
    return turns


class TestFormatterEmptySession:
    def test_empty_session_returns_single_chunk(self):
        data = _make_data()
        chunks = Formatter().format(data)
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1
        assert "no recorded AI activity" in chunks[0].messages[0]["content"]

    def test_empty_session_includes_project_name(self):
        data = _make_data(project_name="my-app")
        chunks = Formatter().format(data)
        assert "my-app" in chunks[0].messages[0]["content"]


class TestFormatterGitOnly:
    def test_git_only_returns_single_chunk(self):
        data = _make_data(
            git_log="abc123 Initial commit",
            git_diff="diff --git a/foo.py b/foo.py\n+print('hello')",
        )
        chunks = Formatter().format(data)
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert "foo.py" in chunks[0].messages[0]["content"]
        assert "Initial commit" in chunks[0].messages[0]["content"]


class TestFormatterShortSession:
    def test_short_session_fits_in_one_chunk(self):
        turns = _make_turns(5)
        data = _make_data(turns=turns, git_log="abc123 Add feature")
        chunks = Formatter().format(data)
        assert len(chunks) == 1
        assert chunks[0].total_chunks == 1
        # First message is git context, then 5 conversation messages
        assert len(chunks[0].messages) == 6
        assert "[Session context]" in chunks[0].messages[0]["content"]

    def test_git_preamble_prepended_to_first_chunk(self):
        turns = _make_turns(3)
        data = _make_data(turns=turns, git_log="abc123 Fix bug")
        chunks = Formatter().format(data)
        first_msg = chunks[0].messages[0]
        assert first_msg["role"] == "user"
        assert "Fix bug" in first_msg["content"]


class TestFormatterChunking:
    def test_chunks_25_turns_into_3(self):
        turns = _make_turns(25)
        data = _make_data(turns=turns)
        chunks = Formatter().format(data)
        # 25 turns / 10 per chunk = 3 chunks
        assert len(chunks) == 3
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == 3

    def test_first_chunk_has_git_context(self):
        turns = _make_turns(25)
        data = _make_data(turns=turns, git_log="abc123 Some commit")
        chunks = Formatter().format(data)
        assert "[Session context]" in chunks[0].messages[0]["content"]

    def test_later_chunks_no_git_context(self):
        turns = _make_turns(25)
        data = _make_data(turns=turns)
        chunks = Formatter().format(data)
        for chunk in chunks[1:]:
            for msg in chunk.messages:
                assert "[Session context]" not in msg["content"]


class TestFormatterTruncation:
    def test_long_assistant_message_truncated(self):
        long_content = "x" * 5000
        turns = [Turn(role="assistant", content=long_content, timestamp="2025-03-04T10:00:00+00:00")]
        data = _make_data(turns=turns)
        chunks = Formatter().format(data)
        # Find the assistant message (skip git context)
        assistant_msgs = [m for m in chunks[0].messages if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert len(assistant_msgs[0]["content"]) < 5000
        assert "[...truncated]" in assistant_msgs[0]["content"]

    def test_short_assistant_message_not_truncated(self):
        turns = [Turn(role="assistant", content="Short reply", timestamp="2025-03-04T10:00:00+00:00")]
        data = _make_data(turns=turns)
        chunks = Formatter().format(data)
        assistant_msgs = [m for m in chunks[0].messages if m["role"] == "assistant"]
        assert assistant_msgs[0]["content"] == "Short reply"

    def test_user_messages_never_truncated(self):
        long_content = "x" * 5000
        turns = [Turn(role="user", content=long_content, timestamp="2025-03-04T10:00:00+00:00")]
        data = _make_data(turns=turns)
        chunks = Formatter().format(data)
        user_msgs = [m for m in chunks[0].messages if "[Session context]" not in m.get("content", "")]
        # The user message with long content should be preserved
        original_user = [m for m in user_msgs if len(m["content"]) > 4000]
        assert len(original_user) == 1
        assert "[...truncated]" not in original_user[0]["content"]


class TestFormatterDiffExtraction:
    def test_extracts_file_paths(self):
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "+print('hello')\n"
            "diff --git a/tests/test_main.py b/tests/test_main.py\n"
            "--- a/tests/test_main.py\n"
            "+++ b/tests/test_main.py\n"
            "+assert True\n"
        )
        result = Formatter._summarize_diff(diff)
        assert "src/main.py" in result
        assert "tests/test_main.py" in result

    def test_empty_diff(self):
        result = Formatter._summarize_diff("")
        assert "no file paths parsed" in result

    def test_diff_truncation_in_preamble(self):
        long_diff = "diff --git a/f.py b/f.py\n" + ("+" * 5000)
        data = _make_data(git_diff=long_diff)
        chunks = Formatter().format(data)
        content = chunks[0].messages[0]["content"]
        assert "truncated" in content

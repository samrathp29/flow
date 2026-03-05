"""Integration tests for CLI commands with mocked LLM + mem0."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flow.cli import cli
from flow.session import SessionManager, SessionState


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_state(tmp_path):
    """Patch SessionManager.STATE_PATH to use tmp dir."""
    state_path = tmp_path / "state.json"
    with patch.object(SessionManager, "STATE_PATH", state_path):
        yield state_path


@pytest.fixture
def mock_detect():
    """Mock _detect_project to avoid needing a real git repo."""
    with patch.object(
        SessionManager, "_detect_project",
        return_value=("test-project", "/fake/test-project"),
    ):
        yield


# ---------- flow start ----------


class TestStartCommand:
    def test_start_success(self, runner, tmp_state, mock_detect):
        result = runner.invoke(cli, ["start"])
        assert result.exit_code == 0
        assert "▶ Session started" in result.output
        assert "test-project" in result.output
        assert tmp_state.exists()

    def test_start_no_git_repo(self, runner, tmp_state):
        with patch.object(
            SessionManager, "_detect_project",
            side_effect=__import__("flow.session", fromlist=["SessionError"]).SessionError(
                "No git repository found. Navigate to your project directory first."
            ),
        ):
            result = runner.invoke(cli, ["start"])
        assert result.exit_code == 1
        assert "✗" in result.output

    def test_start_injects_context(self, runner, tmp_state, mock_detect):
        mock_config = MagicMock()
        mock_injector = MagicMock()
        mock_injector.inject.return_value = ["CLAUDE.md"]

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.context.ContextInjector", return_value=mock_injector):
            result = runner.invoke(cli, ["start"])

        assert result.exit_code == 0
        assert "▶ Session started" in result.output
        assert "Context injected into CLAUDE.md" in result.output
        mock_injector.inject.assert_called_once()
        mock_injector.close.assert_called_once()

    def test_start_silent_when_no_config(self, runner, tmp_state, mock_detect):
        with patch(
            "flow.config.FlowConfig.load",
            side_effect=__import__("flow.config", fromlist=["ConfigNotFound"]).ConfigNotFound(),
        ):
            result = runner.invoke(cli, ["start"])

        assert result.exit_code == 0
        assert "▶ Session started" in result.output
        assert "Context injected" not in result.output

    def test_start_silent_when_no_memories(self, runner, tmp_state, mock_detect):
        mock_config = MagicMock()
        mock_injector = MagicMock()
        mock_injector.inject.return_value = []

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.context.ContextInjector", return_value=mock_injector):
            result = runner.invoke(cli, ["start"])

        assert result.exit_code == 0
        assert "▶ Session started" in result.output
        assert "Context injected" not in result.output

    def test_start_survives_injector_crash(self, runner, tmp_state, mock_detect):
        mock_config = MagicMock()

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.context.ContextInjector", side_effect=RuntimeError("boom")):
            result = runner.invoke(cli, ["start"])

        assert result.exit_code == 0
        assert "▶ Session started" in result.output


# ---------- flow stop ----------


class TestStopCommand:
    def test_stop_no_session(self, runner, tmp_state):
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code == 1
        assert "No active session" in result.output

    def test_stop_success(self, runner, tmp_state, mock_detect):
        # Start a session first
        runner.invoke(cli, ["start"])

        mock_config = MagicMock()
        mock_config.llm_provider = "anthropic"
        mock_config.llm_model = "claude-haiku-4-5-20251001"
        mock_config.api_key = "sk-test"
        mock_config.data_dir = Path("/tmp/flow-test")

        mock_collector_instance = MagicMock()
        mock_collector_instance.collect.return_value = MagicMock(
            project_name="test-project",
            project_path="/fake/test-project",
            started_at="2025-03-04T10:00:00+00:00",
            ended_at="2025-03-04T12:00:00+00:00",
            duration_mins=120,
            turns=[],
            git_diff="",
            git_log="abc123 Initial commit",
        )

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.collector.Collector", return_value=mock_collector_instance), \
             patch("flow.formatter.Formatter") as mock_formatter_cls, \
             patch("flow.memory.FlowMemory") as mock_memory_cls:

            mock_formatter_cls.return_value.format.return_value = [
                MagicMock(messages=[{"role": "user", "content": "test"}], chunk_index=0, total_chunks=1),
            ]
            mock_memory_cls.return_value.add_chunks.return_value = 1

            result = runner.invoke(cli, ["stop"])

        assert result.exit_code == 0
        assert "⠿ Processing session..." in result.output
        assert "✓ Session saved" in result.output
        assert "2h" in result.output

    def test_stop_partial_chunk_failure(self, runner, tmp_state, mock_detect):
        runner.invoke(cli, ["start"])

        mock_config = MagicMock()
        mock_config.data_dir = Path("/tmp/flow-test")

        mock_collector_instance = MagicMock()
        mock_collector_instance.collect.return_value = MagicMock(
            project_name="test-project",
            project_path="/fake/test-project",
            started_at="2025-03-04T10:00:00+00:00",
            ended_at="2025-03-04T12:00:00+00:00",
            duration_mins=120,
            turns=[],
            git_diff="",
            git_log="",
        )

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.collector.Collector", return_value=mock_collector_instance), \
             patch("flow.formatter.Formatter") as mock_formatter_cls, \
             patch("flow.memory.FlowMemory") as mock_memory_cls:

            mock_formatter_cls.return_value.format.return_value = [
                MagicMock(messages=[{"role": "user", "content": "chunk1"}], chunk_index=0, total_chunks=3),
                MagicMock(messages=[{"role": "user", "content": "chunk2"}], chunk_index=1, total_chunks=3),
                MagicMock(messages=[{"role": "user", "content": "chunk3"}], chunk_index=2, total_chunks=3),
            ]
            mock_memory_cls.return_value.add_chunks.return_value = 1  # only 1 of 3 succeeded

            result = runner.invoke(cli, ["stop"])

        assert result.exit_code == 0
        assert "2/3 chunks failed" in result.output


# ---------- flow wake ----------


class TestWakeCommand:
    def test_wake_no_git_repo(self, runner):
        with patch.object(
            SessionManager, "_detect_project",
            side_effect=__import__("flow.session", fromlist=["SessionError"]).SessionError(
                "No git repository found. Navigate to your project directory first."
            ),
        ):
            result = runner.invoke(cli, ["wake"])
        assert result.exit_code == 1
        assert "✗" in result.output
        assert "No git repository found" in result.output

    def test_wake_success(self, runner, mock_detect):
        mock_config = MagicMock()
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.wake.return_value = "You were working on auth flow."

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.retriever.Retriever", return_value=mock_retriever_instance):
            result = runner.invoke(cli, ["wake"])

        assert result.exit_code == 0
        assert "⚡ test-project" in result.output
        assert "You were working on auth flow." in result.output


# ---------- flow ask ----------


class TestAskCommand:
    def test_ask_success(self, runner):
        mock_config = MagicMock()
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.flow_memory.search_all_projects.return_value = [
            {"memory": "Built JWT auth", "agent_id": "auth-service", "metadata": {"session_date": "2025-07-01"}},
        ]
        mock_retriever_instance.synthesize.return_value = "In auth-service you implemented JWT auth."

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.retriever.Retriever", return_value=mock_retriever_instance):
            result = runner.invoke(cli, ["ask", "how did I handle auth?"])

        assert result.exit_code == 0
        assert "how did I handle auth?" in result.output
        assert "In auth-service you implemented JWT auth." in result.output
        mock_retriever_instance.flow_memory.search_all_projects.assert_called_once_with(
            "how did I handle auth?", limit=10,
        )
        mock_retriever_instance.flow_memory.close.assert_called_once()

    def test_ask_no_config(self, runner):
        with patch(
            "flow.config.FlowConfig.load",
            side_effect=__import__("flow.config", fromlist=["ConfigNotFound"]).ConfigNotFound(),
        ):
            result = runner.invoke(cli, ["ask", "anything"])

        assert result.exit_code == 1
        assert "✗" in result.output

    def test_ask_no_memories(self, runner):
        mock_config = MagicMock()
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.flow_memory.search_all_projects.return_value = []
        mock_retriever_instance.synthesize.return_value = "No relevant memories found across your projects."

        with patch("flow.config.FlowConfig.load", return_value=mock_config), \
             patch("flow.retriever.Retriever", return_value=mock_retriever_instance):
            result = runner.invoke(cli, ["ask", "anything"])

        assert result.exit_code == 0
        assert "No relevant memories" in result.output

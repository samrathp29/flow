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
             patch("flow.distiller.Distiller") as mock_distiller_cls, \
             patch("flow.memory.FlowMemory") as mock_memory_cls:

            mock_distiller_cls.return_value.distill.return_value = "Distilled session text."
            mock_memory_cls.return_value.add = MagicMock()

            result = runner.invoke(cli, ["stop"])

        assert result.exit_code == 0
        assert "⠿ Distilling session..." in result.output
        assert "✓ Session saved" in result.output
        assert "2h" in result.output


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

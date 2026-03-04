"""Unit tests for SessionManager: start, stop, stale detection."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from flow.session import SessionError, SessionManager, SessionState


@pytest.fixture
def sm(tmp_path):
    """Provide a SessionManager with STATE_PATH pointing to tmp."""
    manager = SessionManager()
    manager.STATE_PATH = tmp_path / "state.json"
    return manager


@pytest.fixture
def mock_detect(sm):
    """Mock _detect_project to return a fake project."""
    return patch.object(
        sm, "_detect_project", return_value=("test-project", "/fake/test-project")
    )


class TestSessionStart:
    def test_start_creates_state_file(self, sm, mock_detect):
        with mock_detect:
            state = sm.start()
        assert sm.STATE_PATH.exists()
        data = json.loads(sm.STATE_PATH.read_text())
        assert data["project_name"] == "test-project"
        assert data["project_path"] == "/fake/test-project"
        assert "started_at" in data
        assert data["pid"] == os.getpid()

    def test_start_returns_session_state(self, sm, mock_detect):
        with mock_detect:
            state = sm.start()
        assert isinstance(state, SessionState)
        assert state.project_name == "test-project"

    def test_start_raises_if_session_active(self, sm, mock_detect):
        with mock_detect:
            sm.start()
        with mock_detect, pytest.raises(SessionError, match="already active"):
            sm.start()

    def test_start_cleans_stale_session(self, sm, mock_detect):
        """If the existing session PID is dead, it should be cleaned up."""
        sm.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        sm.STATE_PATH.write_text(json.dumps({
            "project_name": "old-project",
            "project_path": "/fake/old",
            "started_at": "2025-01-01T00:00:00+00:00",
            "pid": 99999999,  # very unlikely to be a real PID
        }))
        with mock_detect:
            state = sm.start()
        assert state.project_name == "test-project"


class TestSessionStop:
    def test_stop_returns_state_and_deletes_file(self, sm, mock_detect):
        with mock_detect:
            sm.start()
        state = sm.stop()
        assert isinstance(state, SessionState)
        assert state.project_name == "test-project"
        assert not sm.STATE_PATH.exists()

    def test_stop_raises_if_no_session(self, sm):
        with pytest.raises(SessionError, match="No active session"):
            sm.stop()


class TestGetActive:
    def test_returns_none_if_no_file(self, sm):
        assert sm.get_active() is None

    def test_returns_state_if_file_exists(self, sm, mock_detect):
        with mock_detect:
            sm.start()
        state = sm.get_active()
        assert state is not None
        assert state.project_name == "test-project"

    def test_cleans_up_corrupt_state(self, sm):
        sm.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        sm.STATE_PATH.write_text("not valid json{{{")
        assert sm.get_active() is None
        assert not sm.STATE_PATH.exists()


class TestIsStale:
    def test_current_process_not_stale(self, sm):
        state = SessionState(
            project_name="test", project_path="/fake",
            started_at="2025-01-01T00:00:00+00:00", pid=os.getpid(),
        )
        assert sm._is_stale(state) is False

    def test_dead_pid_is_stale(self, sm):
        state = SessionState(
            project_name="test", project_path="/fake",
            started_at="2025-01-01T00:00:00+00:00", pid=99999999,
        )
        assert sm._is_stale(state) is True

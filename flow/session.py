"""Session state, data models, and session management for flow."""

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SessionState:
    project_name: str       # git root directory name, e.g. "auth-service"
    project_path: str       # absolute git root path
    started_at: str         # ISO-8601 timestamp
    pid: int                # flow process PID (for stale state detection)
    base_commit: str = ""   # HEAD commit hash when session started


@dataclass
class Turn:
    role: str        # "user" | "assistant"
    content: str     # message text, tool calls stripped
    timestamp: str   # ISO-8601, used for session window filtering


@dataclass
class RawSessionData:
    project_name: str
    project_path: str
    started_at: str
    ended_at: str
    duration_mins: int
    turns: list[Turn] = field(default_factory=list)
    git_diff: str = ""
    git_log: str = ""


class SessionError(Exception):
    """Raised for session-related errors."""


class SessionManager:
    STATE_PATH = Path.home() / ".local" / "share" / "flow" / "state.json"

    def _detect_project(self) -> tuple[str, str]:
        """Detect project via git root. Returns (name, path)."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise SessionError("No git repository found. Navigate to your project directory first.")
        path = result.stdout.strip()
        name = Path(path).name
        return name, path

    def get_active(self) -> SessionState | None:
        """Return active session state, or None if no session is active."""
        if not self.STATE_PATH.exists():
            return None
        try:
            data = json.loads(self.STATE_PATH.read_text())
            return SessionState(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            self.STATE_PATH.unlink(missing_ok=True)
            return None

    def _is_stale(self, state: SessionState) -> bool:
        """Check if the PID from state is still alive."""
        try:
            os.kill(state.pid, 0)
            return False
        except (OSError, ProcessLookupError):
            return True

    def start(self) -> SessionState:
        """Begin a session. Writes state.json and returns the state."""
        name, path = self._detect_project()

        existing = self.get_active()
        if existing:
            if self._is_stale(existing):
                self.STATE_PATH.unlink(missing_ok=True)
            else:
                raise SessionError(
                    f"Session already active for {existing.project_name} "
                    f"(started {existing.started_at}). Run `flow stop` first."
                )

        # Capture HEAD hash as the baseline for diffing at stop time
        base_commit = self._get_head(path)

        state = SessionState(
            project_name=name,
            project_path=path,
            started_at=datetime.now(timezone.utc).isoformat(),
            pid=os.getpid(),
            base_commit=base_commit,
        )

        self.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.STATE_PATH.write_text(json.dumps({
            "project_name": state.project_name,
            "project_path": state.project_path,
            "started_at": state.started_at,
            "pid": state.pid,
            "base_commit": state.base_commit,
        }))

        return state

    def stop(self) -> SessionState:
        """End a session. Reads and deletes state.json, returns the state."""
        state = self.get_active()
        if not state:
            raise SessionError("No active session. Run `flow start` first.")
        self.STATE_PATH.unlink()
        return state

    @staticmethod
    def _get_head(project_path: str) -> str:
        """Return current HEAD commit hash, or empty string for new repos."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=project_path,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

"""Session state, data models, and session management for flow."""

import hashlib
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
    project_id: str         # unique id: "{name}-{path_hash}" for mem0 agent_id
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


@dataclass
class MessageChunk:
    """A group of messages ready for mem0.add()."""

    messages: list[dict] = field(default_factory=list)
    chunk_index: int = 0
    total_chunks: int = 1


class SessionError(Exception):
    """Raised for session-related errors."""


class SessionManager:
    # Per-project state files live under sessions/
    STATE_DIR = Path.home() / ".local" / "share" / "flow" / "sessions"
    # Legacy single-file path (for migration)
    _LEGACY_STATE_PATH = Path.home() / ".local" / "share" / "flow" / "state.json"

    def __init__(self):
        self._migrate_legacy_state()

    def _migrate_legacy_state(self) -> None:
        """One-time migration: move old state.json into sessions/ directory."""
        if not self._LEGACY_STATE_PATH.exists():
            return
        try:
            data = json.loads(self._LEGACY_STATE_PATH.read_text())
            # Add project_id if missing (old format)
            if "project_id" not in data:
                data["project_id"] = self._make_project_id(data.get("project_path", ""))
            self.STATE_DIR.mkdir(parents=True, exist_ok=True)
            dest = self.STATE_DIR / f"{data['project_id']}.json"
            dest.write_text(json.dumps(data))
            self._LEGACY_STATE_PATH.unlink()
        except Exception:
            pass  # don't block on migration failure

    @staticmethod
    def _make_project_id(project_path: str) -> str:
        """Stable, unique project identifier from absolute path.

        Format: "{dirname}-{hash8}" e.g. "auth-service-a1b2c3d4"
        """
        path_hash = hashlib.sha256(project_path.encode()).hexdigest()[:8]
        name = Path(project_path).name
        return f"{name}-{path_hash}"

    def _state_path(self, project_id: str) -> Path:
        return self.STATE_DIR / f"{project_id}.json"

    def _detect_project(self) -> tuple[str, str, str]:
        """Detect project via git root. Returns (name, path, project_id)."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise SessionError("No git repository found. Navigate to your project directory first.")
        path = result.stdout.strip()
        name = Path(path).name
        project_id = self._make_project_id(path)
        return name, path, project_id

    def get_active(self, project_id: str) -> SessionState | None:
        """Return active session state for a specific project, or None."""
        state_path = self._state_path(project_id)
        if not state_path.exists():
            return None
        try:
            data = json.loads(state_path.read_text())
            # Handle legacy state files missing project_id
            if "project_id" not in data:
                data["project_id"] = self._make_project_id(data.get("project_path", ""))
            return SessionState(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            state_path.unlink(missing_ok=True)
            return None

    def get_any_active(self) -> SessionState | None:
        """Return any active session (for backward-compat error messages)."""
        if not self.STATE_DIR.exists():
            return None
        for f in self.STATE_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if "project_id" not in data:
                    data["project_id"] = self._make_project_id(data.get("project_path", ""))
                return SessionState(**data)
            except Exception:
                continue
        return None

    def _is_stale(self, state: SessionState) -> bool:
        """Check if the PID from state is still alive."""
        try:
            os.kill(state.pid, 0)
            return False
        except (OSError, ProcessLookupError):
            return True

    def start(self) -> SessionState:
        """Begin a session. Writes per-project state file and returns the state."""
        name, path, project_id = self._detect_project()

        existing = self.get_active(project_id)
        if existing:
            if self._is_stale(existing):
                # Return the stale state for recovery before cleaning up
                self._state_path(project_id).unlink(missing_ok=True)
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
            project_id=project_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            pid=os.getppid(),
            base_commit=base_commit,
        )

        self.STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._state_path(project_id).write_text(json.dumps({
            "project_name": state.project_name,
            "project_path": state.project_path,
            "project_id": state.project_id,
            "started_at": state.started_at,
            "pid": state.pid,
            "base_commit": state.base_commit,
        }))

        return state

    def stop(self) -> SessionState:
        """End a session. Reads and deletes state file for current project."""
        name, path, project_id = self._detect_project()
        state = self.get_active(project_id)
        if not state:
            raise SessionError("No active session. Run `flow start` first.")
        self._state_path(project_id).unlink()
        return state

    def clean_stale(self, project_id: str) -> SessionState | None:
        """Remove a stale session's state file and return the state for recovery."""
        state = self.get_active(project_id)
        if state and self._is_stale(state):
            self._state_path(project_id).unlink(missing_ok=True)
            return state
        return None

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

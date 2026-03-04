"""Collector — aggregates parser output and git data into RawSessionData."""

import logging
import subprocess
from datetime import datetime, timezone

from flow.parsers.base import ParserUnavailable
from flow.parsers.claude_code import ClaudeCodeParser
from flow.parsers.codex import CodexParser
from flow.parsers.cursor import CursorParser
from flow.session import RawSessionData, SessionState

logger = logging.getLogger(__name__)


class Collector:
    """Orchestrates all parsers and git operations for a session."""

    PARSERS = [ClaudeCodeParser, CursorParser, CodexParser]

    def collect(self, state: SessionState) -> RawSessionData:
        """Collect all session data: parser turns + git diff/log."""
        since = datetime.fromisoformat(state.started_at)

        turns = []
        for parser_cls in self.PARSERS:
            try:
                parser = parser_cls()
                turns.extend(parser.read(state.project_path, since))
            except ParserUnavailable:
                continue
            except Exception:
                logger.warning("Parser %s failed", parser_cls.__name__, exc_info=True)

        turns.sort(key=lambda t: t.timestamp)

        ended_at = datetime.now(timezone.utc).isoformat()
        started = datetime.fromisoformat(state.started_at)
        duration_mins = int((datetime.now(timezone.utc) - started).total_seconds() / 60)

        return RawSessionData(
            project_name=state.project_name,
            project_path=state.project_path,
            started_at=state.started_at,
            ended_at=ended_at,
            duration_mins=duration_mins,
            turns=turns,
            git_diff=self._git_diff(state.project_path),
            git_log=self._git_log(state.project_path),
        )

    def _git_diff(self, project_path: str) -> str:
        """Run git diff and return the output."""
        try:
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True, text=True, cwd=project_path,
            )
            return result.stdout.strip()
        except Exception:
            logger.warning("git diff failed", exc_info=True)
            return ""

    def _git_log(self, project_path: str, limit: int = 10) -> str:
        """Run git log --oneline and return the output."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-n{limit}"],
                capture_output=True, text=True, cwd=project_path,
            )
            return result.stdout.strip()
        except Exception:
            logger.warning("git log failed", exc_info=True)
            return ""

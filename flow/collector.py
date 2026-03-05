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
            git_diff=self._git_diff(state.project_path, state.base_commit),
            git_log=self._git_log(state.project_path, since=state.started_at),
        )

    def _git_diff(self, project_path: str, base_commit: str) -> str:
        """Diff all changes made during the session (committed + uncommitted)."""
        try:
            if base_commit:
                # Diff from the commit at session start to current working tree
                result = subprocess.run(
                    ["git", "diff", base_commit],
                    capture_output=True, text=True, cwd=project_path,
                )
            else:
                # No base commit (brand new repo) -- diff against the empty tree
                result = subprocess.run(
                    ["git", "diff", "4b825dc642cb6eb9a060e54bf899d8b965cf8e6f", "HEAD"],
                    capture_output=True, text=True, cwd=project_path,
                )
                # Also include any staged but uncommitted changes
                staged = subprocess.run(
                    ["git", "diff", "--cached"],
                    capture_output=True, text=True, cwd=project_path,
                )
                if staged.stdout.strip():
                    return (result.stdout.strip() + "\n" + staged.stdout.strip()).strip()
            return result.stdout.strip()
        except Exception:
            logger.warning("git diff failed", exc_info=True)
            return ""

    def _git_log(self, project_path: str, limit: int = 10, since: str = "") -> str:
        """Run git log --oneline filtered to the session window."""
        try:
            cmd = ["git", "log", "--oneline", f"-n{limit}"]
            if since:
                cmd.append(f"--since={since}")
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, cwd=project_path,
            )
            return result.stdout.strip()
        except Exception:
            logger.warning("git log failed", exc_info=True)
            return ""

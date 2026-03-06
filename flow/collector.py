"""Collector — aggregates parser output and git data into RawSessionData."""

import logging
import subprocess
from datetime import datetime, timezone

from flow.parsers.base import ParserUnavailable
from flow.parsers.claude_code import ClaudeCodeParser
from flow.parsers.codex import CodexParser
from flow.parsers.cursor import CursorParser
from flow.session import RawSessionData, SessionState, Turn

logger = logging.getLogger(__name__)


class Collector:
    """Orchestrates all parsers and git operations for a session."""

    PARSERS = [ClaudeCodeParser, CursorParser, CodexParser]
    DEDUP_WINDOW_SECONDS = 60  # same-role turns within this window are checked

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
        turns = self._deduplicate_turns(turns)

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

    def _deduplicate_turns(self, turns: list[Turn]) -> list[Turn]:
        """Remove near-duplicate turns from different tools within a time window."""
        if not turns:
            return turns

        result: list[Turn] = [turns[0]]
        for turn in turns[1:]:
            prev = result[-1]
            if prev.role == turn.role:
                try:
                    t1 = datetime.fromisoformat(prev.timestamp.replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(turn.timestamp.replace("Z", "+00:00"))
                    gap = abs((t2 - t1).total_seconds())
                except (ValueError, AttributeError):
                    gap = float("inf")

                if gap < self.DEDUP_WINDOW_SECONDS and self._similar(prev.content, turn.content):
                    continue  # skip duplicate
            result.append(turn)
        return result

    @staticmethod
    def _similar(a: str, b: str) -> bool:
        """Check if two strings are near-identical (>90% character overlap)."""
        if a == b:
            return True
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if not longer:
            return True
        # Quick length check: if lengths differ by >20%, not similar
        if len(shorter) / len(longer) < 0.8:
            return False
        # Count matching characters (order-preserving)
        matches = sum(1 for c1, c2 in zip(shorter, longer) if c1 == c2)
        return matches / len(longer) > 0.9

    def _git_diff(self, project_path: str, base_commit: str) -> str:
        """Diff all changes made during the session (committed + uncommitted)."""
        try:
            if base_commit:
                # Diff from the commit at session start to current working tree
                result = subprocess.run(
                    ["git", "diff", base_commit],
                    capture_output=True, text=True, cwd=project_path,
                )
                # Fallback if base_commit no longer exists (rebase/force-push)
                if result.returncode != 0:
                    logger.warning(
                        "base_commit %s not found (rebase?), falling back to HEAD~20",
                        base_commit,
                    )
                    result = subprocess.run(
                        ["git", "diff", "HEAD~20"],
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

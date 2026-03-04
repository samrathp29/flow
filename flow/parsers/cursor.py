"""Cursor IDE SQLite chat log parser."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flow.parsers.base import BaseParser, ParserUnavailable
from flow.session import Turn

logger = logging.getLogger(__name__)

# macOS path; Linux would differ
WORKSPACE_STORAGE = (
    Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
)

CHAT_KEY = "workbench.panel.aichat.view.aichat.chatdata"


class CursorParser(BaseParser):
    def is_available(self, project_path: str) -> bool:
        return WORKSPACE_STORAGE.exists()

    def read(self, project_path: str, since: datetime) -> list[Turn]:
        if not WORKSPACE_STORAGE.exists():
            raise ParserUnavailable("Cursor workspace storage not found")

        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)

        try:
            for db_path in self._find_all_dbs():
                if self._matches_project(db_path, project_path):
                    return self._extract_turns(db_path, since_utc)
        except Exception:
            logger.warning("Cursor parser failed", exc_info=True)
            return []

        return []

    def _find_all_dbs(self) -> list[Path]:
        return sorted(WORKSPACE_STORAGE.glob("*/state.vscdb"))

    def _matches_project(self, db_path: Path, project_path: str) -> bool:
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            row = con.execute(
                "SELECT value FROM ItemTable WHERE [key] = ?", (CHAT_KEY,)
            ).fetchone()
            con.close()
            if not row:
                return False
            return project_path in str(row[0])
        except Exception:
            return False

    def _extract_turns(self, db_path: Path, since: datetime) -> list[Turn]:
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            row = con.execute(
                "SELECT value FROM ItemTable WHERE [key] = ?", (CHAT_KEY,)
            ).fetchone()
            con.close()
        except Exception:
            logger.warning("Failed to read Cursor DB: %s", db_path, exc_info=True)
            return []

        if not row:
            return []

        try:
            data = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return []

        turns = []
        for tab in data.get("tabs", []):
            for bubble in tab.get("bubbles", []):
                ts_ms = bubble.get("createdAt") or tab.get("timestamp", 0)
                if not ts_ms:
                    continue
                try:
                    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                except (ValueError, OSError, OverflowError):
                    continue
                if ts < since:
                    continue

                btype = bubble.get("type", "")
                if btype == "user":
                    text = self._extract_user_text(bubble)
                    role = "user"
                elif btype == "ai":
                    text = bubble.get("rawText", "")
                    role = "assistant"
                else:
                    continue

                if text.strip():
                    turns.append(Turn(
                        role=role,
                        content=text,
                        timestamp=ts.isoformat(),
                    ))

        return sorted(turns, key=lambda t: t.timestamp)

    def _extract_user_text(self, bubble: dict) -> str:
        """Extract user text, trying fields in priority order."""
        # Priority 1: delegate.a
        delegate = bubble.get("delegate")
        if isinstance(delegate, dict) and delegate.get("a"):
            return delegate["a"]
        # Priority 2: text
        if bubble.get("text"):
            return bubble["text"]
        # Priority 3: rawText
        if bubble.get("rawText"):
            return bubble["rawText"]
        return ""

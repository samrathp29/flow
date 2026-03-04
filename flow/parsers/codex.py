"""Codex CLI JSONL log parser."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from flow.parsers.base import BaseParser, ParserUnavailable
from flow.session import Turn

logger = logging.getLogger(__name__)


class CodexParser(BaseParser):
    SESSIONS_ROOT = Path.home() / ".codex" / "sessions"

    def is_available(self, project_path: str) -> bool:
        return self.SESSIONS_ROOT.exists()

    def read(self, project_path: str, since: datetime) -> list[Turn]:
        if not self.SESSIONS_ROOT.exists():
            raise ParserUnavailable("Codex sessions directory not found")

        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        turns = []

        try:
            for jsonl_file in self._files_since(since_utc):
                for line in jsonl_file.read_text(errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts_str = record.get("timestamp", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                    if ts < since_utc:
                        continue

                    turn = self._parse_record(record, ts_str)
                    if turn:
                        turns.append(turn)
        except Exception:
            logger.warning("Codex parser failed", exc_info=True)
            return []

        return sorted(turns, key=lambda t: t.timestamp)

    def _parse_record(self, record: dict, ts_str: str) -> Turn | None:
        rtype = record.get("type")
        payload = record.get("payload", {})

        if rtype == "event_msg" and payload.get("type") == "user_message":
            message = payload.get("message", "")
            if message.strip():
                return Turn(role="user", content=message, timestamp=ts_str)

        elif rtype == "response_item":
            ptype = payload.get("type")
            if ptype == "message" and payload.get("role") == "assistant":
                text = self._extract_assistant_text(payload)
                if text.strip():
                    return Turn(role="assistant", content=text, timestamp=ts_str)

        return None

    def _extract_assistant_text(self, payload: dict) -> str:
        parts = []
        for block in payload.get("content", []):
            if isinstance(block, dict) and block.get("type") in ("text", "input_text"):
                parts.append(block.get("text", ""))
        return "\n".join(parts)

    def _files_since(self, since: datetime) -> list[Path]:
        """Walk YYYY/MM/DD directories and return files within session window."""
        files = []
        if not self.SESSIONS_ROOT.exists():
            return files

        for year_dir in sorted(self.SESSIONS_ROOT.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            if int(year_dir.name) < since.year:
                continue
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                for day_dir in sorted(month_dir.iterdir()):
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue
                    try:
                        dir_date = datetime(
                            int(year_dir.name), int(month_dir.name), int(day_dir.name),
                            tzinfo=timezone.utc,
                        )
                    except ValueError:
                        continue
                    # Include the day if it's the same day or after since
                    if dir_date.date() >= since.date():
                        files.extend(sorted(day_dir.glob("*.jsonl")))
        return files

"""Claude Code JSONL log parser."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from flow.parsers.base import BaseParser, ParserUnavailable
from flow.session import Turn

logger = logging.getLogger(__name__)


class ClaudeCodeParser(BaseParser):
    def _project_dir(self, project_path: str) -> Path:
        encoded = project_path.replace("/", "-")
        return Path.home() / ".claude" / "projects" / encoded

    def is_available(self, project_path: str) -> bool:
        project_dir = self._project_dir(project_path)
        if not project_dir.exists():
            return False
        return any(project_dir.glob("*.jsonl"))

    def read(self, project_path: str, since: datetime) -> list[Turn]:
        project_dir = self._project_dir(project_path)
        if not project_dir.exists():
            raise ParserUnavailable("Claude Code project directory not found")

        since_utc = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        turns = []

        try:
            for jsonl_file in project_dir.glob("*.jsonl"):
                for line in jsonl_file.read_text(errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    record_type = record.get("type")
                    if record_type not in ("user", "assistant"):
                        continue

                    ts_str = record.get("timestamp")
                    if not ts_str:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                    if ts < since_utc:
                        continue

                    message = record.get("message", {})
                    content = self._extract_text(message.get("content", ""))
                    if not content.strip():
                        continue

                    turns.append(Turn(
                        role=record_type,
                        content=content,
                        timestamp=ts_str,
                    ))
        except Exception:
            logger.warning("Claude Code parser failed", exc_info=True)
            return []

        return sorted(turns, key=lambda t: t.timestamp)

    def _extract_text(self, content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        continue  # skip tool results
                    elif block.get("type") == "thinking":
                        continue  # skip thinking blocks
            return "\n".join(parts)
        return ""

"""Retriever — searches mem0 and generates a wake briefing via LLM."""

import logging
import subprocess
from datetime import datetime, timezone

from flow.config import FlowConfig
from flow.llm import LLM, LLMError
from flow.memory import FlowMemory

logger = logging.getLogger(__name__)

BRIEFING_PROMPT = """\
A developer is returning to a project after {days_away} days.
Write a 3-5 sentence briefing in second person that tells them:
- What they were working on
- What was unresolved or blocked
- What to do first

Be direct. Use past tense for what was done, present tense for what's needed.
No headers, no bullets. Sound like a knowledgeable colleague, not a status report."""


class Retriever:
    """Searches project memories and generates a wake briefing."""

    def __init__(self, config: FlowConfig):
        self.flow_memory = FlowMemory(config)
        self.llm = LLM(config)

    def wake(self, project_name: str, project_path: str) -> str:
        """Generate a wake briefing for the given project."""
        memories = self.flow_memory.search(
            project_name=project_name,
            query="what was I working on, what was blocked, what comes next",
            limit=5,
        )

        if not memories:
            return f"No sessions recorded for {project_name} yet."

        days_away = self._days_since_last_session()
        git_log = self._git_log(project_path, limit=5)
        context = "\n".join(f"- {m}" for m in memories)

        prompt = BRIEFING_PROMPT.format(days_away=days_away)
        user_content = f"""\
Project memory:
{context}

Recent git activity:
{git_log}"""

        try:
            return self.llm.call(prompt, user_content)
        except LLMError:
            logger.warning("LLM briefing failed, returning raw memories", exc_info=True)
            return "Recent session memories:\n" + context

    def _days_since_last_session(self) -> int:
        """Estimate days since the last session from mem0 search results.

        Uses the most recent mem0 created_at timestamp. Falls back to 0
        if metadata is unavailable.
        """
        try:
            results = self.flow_memory.memory.search(
                query="last session",
                user_id="flow",
                limit=1,
            )
            entries = results.get("results", [])
            if entries and "created_at" in entries[0]:
                created = datetime.fromisoformat(entries[0]["created_at"])
                now = datetime.now(timezone.utc)
                return max(0, (now - created).days)
        except Exception:
            logger.warning("Could not determine days since last session", exc_info=True)
        return 0

    def _git_log(self, project_path: str, limit: int = 5) -> str:
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

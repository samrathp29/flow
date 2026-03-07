"""Retriever — searches mem0 and generates a wake briefing via LLM."""

import hashlib
import json
import logging
import subprocess
from datetime import datetime, timezone

from flow.config import FlowConfig
from flow.llm import LLM, LLMError
from flow.memory import FlowMemory

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """\
You are answering a developer's question using only memories from their
own past projects. Each memory is tagged with a project name and date.

Answer the question by synthesizing what the developer actually did and
decided across their projects — not general best practice. Be specific
about which project, when, and what the outcome was. Where their approach
evolved across projects, note that evolution explicitly.

If the memories don't contain a relevant answer, say so directly.
Do not speculate beyond what the memories contain."""

# Tiered briefing prompts based on absence length
SHORT_ABSENCE_PROMPT = """\
A developer is returning to a project after {days_away} days.
Write a 2-3 sentence briefing in second person. Focus on:
- What to do next (pick up where they left off)

CRITICAL: If a task is marked COMPLETED in the memories, do NOT suggest
continuing or extending it unless a specific follow-up was noted. Acknowledge
completed work briefly, then focus on what is actually unfinished or next.

Be direct. No headers, no bullets. Sound like a knowledgeable colleague.
Prioritize the most recent memories over older ones."""

MEDIUM_ABSENCE_PROMPT = """\
A developer is returning to a project after {days_away} days.
Write a 3-5 sentence briefing in second person that tells them:
- What they were working on
- What was unresolved or blocked (ONLY IF APPLICABLE)
- What to do first (only if clear)

CRITICAL: If a task is marked COMPLETED in the memories, do NOT suggest
continuing or extending it unless a specific follow-up was noted. Acknowledge
completed work briefly ("X is done"), then focus on what is actually unfinished
or blocked.

Be direct. No headers, no bullets. Sound like a knowledgeable colleague.
Prioritize the most recent memories. Mention older context only if
directly relevant to resuming work."""

LONG_ABSENCE_PROMPT = """\
A developer is returning to a project after {days_away} days — a significant gap.
Write a 5-7 sentence briefing in second person that helps them rebuild context:
- What the project was about / where it was headed
- What was actively being worked on last
- Key decisions that were made and why
- What was unresolved or blocked
- The most logical next step

CRITICAL: If a task is marked COMPLETED in the memories, do NOT suggest
continuing or extending it unless a specific follow-up was noted. Acknowledge
completed work briefly ("X is done"), then focus on what is actually unfinished
or blocked.

Be direct and specific. No headers, no bullets. Sound like a knowledgeable
colleague catching them up. Prioritize recent memories but include older
context that's essential for understanding the project state."""

COLD_START_PROMPT = """\
A developer is looking at a project with no stored session memories.
Using only the git commit history below, write a 3-5 sentence summary
in second person that tells them:
- What the project appears to be about
- What was recently worked on (based on commit messages)
- A reasonable first action

Be concise. This is a best-effort briefing from commits alone."""


class Retriever:
    """Searches project memories and generates a wake briefing."""

    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, config: FlowConfig):
        self.flow_memory = FlowMemory(config)
        self.llm = LLM(config)
        self._cache_path = config.data_dir / "wake_cache.json"

    def synthesize(self, query: str, memories: list[dict]) -> str:
        """Synthesize an answer from cross-project memories."""
        if not memories:
            return "No relevant memories found across your projects."

        context_lines = []
        for m in memories:
            project = m.get("agent_id", "unknown")
            date = m.get("metadata", {}).get("session_date", "unknown date")
            context_lines.append(f"- [{project}, {date}] {m['memory']}")
        context = "\n".join(context_lines)

        user_content = f"Question: {query}\n\nMemories:\n{context}"

        try:
            return self.llm.call(SYNTHESIS_PROMPT, user_content)
        except LLMError:
            logger.warning("LLM synthesis failed, returning raw memories", exc_info=True)
            return "Relevant memories:\n" + context

    def wake(self, project_name: str, project_path: str) -> str:
        """Generate a wake briefing for the given project."""
        memories = self.flow_memory.search(
            project_name=project_name,
            query="what was I working on, what was blocked, what comes next",
            limit=8,
        )

        if not memories:
            return self._cold_start_briefing(project_path, project_name)

        # Check cache before making LLM call
        memory_hash = hashlib.md5("".join(memories).encode()).hexdigest()
        cached = self._read_cache(project_name, memory_hash)
        if cached:
            return cached

        days_away = self._days_since_last_session()
        git_limit = 15 if days_away > 30 else 5
        git_log = self._git_log(project_path, limit=git_limit)

        # Tag recent memories for the prompt
        context_lines = []
        for i, m in enumerate(memories):
            tag = "[recent] " if i < 2 else ""
            context_lines.append(f"- {tag}{m}")
        context = "\n".join(context_lines)

        # Select prompt tier based on absence length
        prompt = self._select_prompt(days_away)

        user_content = f"""\
Project memory:
{context}

Recent git activity:
{git_log}"""

        try:
            briefing = self.llm.call(prompt, user_content)
            self._write_cache(project_name, memory_hash, briefing)
            return briefing
        except LLMError:
            logger.warning("LLM briefing failed, returning raw memories", exc_info=True)
            return "Recent session memories:\n" + context

    def _select_prompt(self, days_away: int) -> str:
        """Select the appropriate briefing prompt based on absence length."""
        if days_away <= 3:
            return SHORT_ABSENCE_PROMPT.format(days_away=days_away)
        elif days_away <= 30:
            return MEDIUM_ABSENCE_PROMPT.format(days_away=days_away)
        else:
            return LONG_ABSENCE_PROMPT.format(days_away=days_away)

    def _cold_start_briefing(self, project_path: str, project_name: str) -> str:
        """Generate a briefing from git history alone (no mem0 memories)."""
        git_log = self._git_log(project_path, limit=20)
        if not git_log:
            return f"No sessions recorded for {project_name} yet."

        user_content = f"Project: {project_name}\n\nRecent commits:\n{git_log}"

        try:
            return self.llm.call(COLD_START_PROMPT, user_content)
        except LLMError:
            logger.warning("Cold start briefing failed", exc_info=True)
            return f"No session memories for {project_name} yet.\n\nRecent commits:\n{git_log}"

    def _days_since_last_session(self) -> int:
        """Estimate days since the last session from mem0 search results."""
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

    # ------------------------------------------------------------------
    # Wake cache (avoids redundant LLM calls within 5 minutes)
    # ------------------------------------------------------------------

    def _read_cache(self, project_name: str, memory_hash: str) -> str | None:
        """Return cached briefing if it exists and is fresh."""
        try:
            if not self._cache_path.exists():
                return None
            cache = json.loads(self._cache_path.read_text())
            entry = cache.get(project_name)
            if not entry or entry.get("memory_hash") != memory_hash:
                return None
            cached_at = datetime.fromisoformat(entry["timestamp"])
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age > self.CACHE_TTL_SECONDS:
                return None
            return entry["briefing"]
        except Exception:
            return None

    def _write_cache(self, project_name: str, memory_hash: str, briefing: str) -> None:
        """Write briefing to cache file."""
        try:
            cache = {}
            if self._cache_path.exists():
                cache = json.loads(self._cache_path.read_text())
            cache[project_name] = {
                "briefing": briefing,
                "memory_hash": memory_hash,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(cache))
        except Exception:
            logger.warning("Failed to write wake cache", exc_info=True)

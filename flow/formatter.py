"""Formatter — formatting of RawSessionData into mem0-ready chunks.

Includes an optional LLM-powered diff summarization step that replaces
raw unified diffs with semantic summaries before mem0 ingestion.
"""

from __future__ import annotations

import logging
import re

from flow.session import MessageChunk, RawSessionData, Turn

logger = logging.getLogger(__name__)

# Patterns for common secret formats — applied before mem0 ingestion
SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"ghp_[A-Za-z0-9_]{36,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"gho_[A-Za-z0-9_]{36,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    ), "[REDACTED_JWT]"),
]


DIFF_SUMMARY_PROMPT = """\
You are a senior developer reviewing a git diff from a coding session.
Produce a concise summary that another LLM can use to extract factual memories.

For each file changed:
- State what was added, modified, or deleted and WHY (infer intent from context).
- Assess whether the change appears COMPLETE or IN PROGRESS (look for TODOs, stubs,
  partial implementations, commented-out code, or missing error handling).

End with a one-line overall status: "Overall: all changes appear complete." or
"Overall: the following items appear incomplete: ..."

Be concise. No code blocks. No diff syntax. Plain English only."""


class Formatter:
    """Formats raw session data into chunked messages for mem0 ingestion."""

    MAX_ASSISTANT_LENGTH = 2000  # truncate long code dumps / error traces
    MAX_CHUNK_MESSAGES = 10  # aligns with mem0's internal sliding window
    MAX_CHUNKS = 10  # cap total chunks to limit LLM calls per session
    MAX_DIFF_LENGTH = 4000  # for the git context preamble
    MAX_DIFF_FOR_LLM = 8000  # truncate diff before sending to summarization LLM

    def format(
        self, data: RawSessionData, diff_summary: str = ""
    ) -> list[MessageChunk]:
        """Format raw session data into mem0-ready message chunks.

        Returns empty list if the session has no meaningful content.
        If *diff_summary* is provided, it replaces the raw diff in the
        git preamble (the mechanical file list is still included).
        """
        if not data.turns and not data.git_diff and not data.git_log:
            return []

        git_preamble = self._build_git_preamble(data, diff_summary=diff_summary)
        cleaned_turns = self._truncate_turns(data.turns)

        # Cap total turns to avoid excessive mem0 LLM calls.
        # Keep the most recent turns (developer cares most about where they ended).
        max_turns = self.MAX_CHUNKS * self.MAX_CHUNK_MESSAGES
        if len(cleaned_turns) > max_turns:
            cleaned_turns = cleaned_turns[-max_turns:]

        messages = [{"role": t.role, "content": t.content} for t in cleaned_turns]
        return self._chunk_messages(messages, git_preamble, data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_git_preamble(
        self, data: RawSessionData, diff_summary: str = ""
    ) -> str:
        """Create a concise git context string for the session preamble."""
        parts = [f"Project: {data.project_name} | Duration: {data.duration_mins}min"]

        if data.git_log:
            parts.append(f"Commits during session:\n{data.git_log}")

        if data.git_diff:
            file_summary = self._summarize_diff(data.git_diff)
            parts.append(f"Files changed:\n{file_summary}")

            if diff_summary:
                # Use the LLM-generated semantic summary instead of raw diff
                parts.append(f"Change summary:\n{diff_summary}")
            elif len(data.git_diff) > self.MAX_DIFF_LENGTH:
                parts.append(
                    f"Diff excerpt (truncated):\n"
                    f"{data.git_diff[: self.MAX_DIFF_LENGTH]}..."
                )
            else:
                parts.append(f"Diff:\n{data.git_diff}")

        return "\n\n".join(parts)

    @staticmethod
    def _summarize_diff(diff: str) -> str:
        """Extract changed file paths from a git diff. Pure string parsing."""
        files: list[str] = []
        for line in diff.splitlines():
            if line.startswith("diff --git"):
                parts = line.split(" b/", 1)
                if len(parts) == 2:
                    files.append(parts[1])
        return (
            "\n".join(f"  - {f}" for f in files)
            if files
            else "(no file paths parsed)"
        )

    def summarize_diff_with_llm(
        self, git_diff: str, git_log: str, llm: "LLM"
    ) -> str:
        """Semantically summarize a git diff using an LLM.

        Returns a plain-English summary describing what changed, why, and
        whether each change appears complete. Falls back to empty string
        on LLM failure (caller will use raw diff instead).

        The *llm* parameter is a ``flow.llm.LLM`` instance (imported lazily
        to avoid circular imports and keep Formatter usable without LLM deps
        in tests).
        """
        if not git_diff:
            return ""

        from flow.llm import LLMError

        truncated = git_diff[: self.MAX_DIFF_FOR_LLM]
        if len(git_diff) > self.MAX_DIFF_FOR_LLM:
            truncated += "\n[...diff truncated]"

        user_msg = ""
        if git_log:
            user_msg += f"Commits:\n{git_log}\n\n"
        user_msg += f"Diff:\n{truncated}"

        try:
            return llm.call(DIFF_SUMMARY_PROMPT, user_msg)
        except LLMError:
            logger.warning("Diff summarization failed, falling back to raw diff")
            return ""

    def _truncate_turns(self, turns: list[Turn]) -> list[Turn]:
        """Truncate long assistant messages and redact secrets from all turns."""
        result: list[Turn] = []
        for t in turns:
            content = self._redact_secrets(t.content)
            if t.role == "assistant" and len(content) > self.MAX_ASSISTANT_LENGTH:
                content = content[: self.MAX_ASSISTANT_LENGTH] + "\n[...truncated]"
            result.append(Turn(role=t.role, content=content, timestamp=t.timestamp))
        return result

    @staticmethod
    def _redact_secrets(text: str) -> str:
        """Replace common secret patterns with redaction markers."""
        for pattern, replacement in SECRET_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    def _chunk_messages(
        self,
        messages: list[dict],
        git_preamble: str,
        data: RawSessionData,
    ) -> list[MessageChunk]:
        """Split messages into chunks, prepending git context to first chunk."""
        if not messages:
            # No conversation turns — git data only.
            # Frame explicitly so the extraction prompt knows to work with git data.
            content = (
                "[Git-only session — no AI conversation logs available]\n"
                "Extract facts from the commit messages and file changes below.\n\n"
                f"{git_preamble}"
            )
            return [
                MessageChunk(
                    messages=[{"role": "user", "content": content}],
                    chunk_index=0,
                    total_chunks=1,
                )
            ]

        # Split into groups of MAX_CHUNK_MESSAGES
        raw_chunks: list[list[dict]] = []
        for i in range(0, len(messages), self.MAX_CHUNK_MESSAGES):
            raw_chunks.append(messages[i : i + self.MAX_CHUNK_MESSAGES])

        total = len(raw_chunks)
        result: list[MessageChunk] = []

        for idx, chunk_msgs in enumerate(raw_chunks):
            # Prepend git context to the first chunk
            if idx == 0:
                context_msg = {
                    "role": "user",
                    "content": (
                        f"[Session context]\n{git_preamble}\n\n"
                        "[Conversation follows]"
                    ),
                }
                chunk_msgs = [context_msg] + chunk_msgs
            elif chunk_msgs[0]["role"] == "assistant":
                # mem0 expects user-first; prepend a continuation marker
                continuation = {
                    "role": "user",
                    "content": (
                        f"[Continuation of session in {data.project_name}, "
                        f"chunk {idx + 1}/{total}]"
                    ),
                }
                chunk_msgs = [continuation] + chunk_msgs

            result.append(
                MessageChunk(
                    messages=chunk_msgs,
                    chunk_index=idx,
                    total_chunks=total,
                )
            )

        return result

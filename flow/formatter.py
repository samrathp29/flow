"""Formatter — mechanical formatting of RawSessionData into mem0-ready chunks.

No LLM calls. All operations are string manipulation and list slicing.
mem0 handles the intelligence (fact extraction, deduplication, embedding).
"""

from __future__ import annotations

from flow.session import MessageChunk, RawSessionData, Turn


class Formatter:
    """Formats raw session data into chunked messages for mem0 ingestion."""

    MAX_ASSISTANT_LENGTH = 2000  # truncate long code dumps / error traces
    MAX_CHUNK_MESSAGES = 10  # aligns with mem0's internal sliding window
    MAX_DIFF_LENGTH = 4000  # for the git context preamble

    def format(self, data: RawSessionData) -> list[MessageChunk]:
        """Format raw session data into mem0-ready message chunks."""
        if not data.turns and not data.git_diff and not data.git_log:
            return [
                MessageChunk(
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Session of {data.duration_mins} minutes in "
                                f"{data.project_name} with no recorded AI "
                                "activity or file changes."
                            ),
                        }
                    ],
                    chunk_index=0,
                    total_chunks=1,
                )
            ]

        git_preamble = self._build_git_preamble(data)
        cleaned_turns = self._truncate_turns(data.turns)
        messages = [{"role": t.role, "content": t.content} for t in cleaned_turns]
        return self._chunk_messages(messages, git_preamble, data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_git_preamble(self, data: RawSessionData) -> str:
        """Create a concise git context string (pure formatting, no LLM)."""
        parts = [f"Project: {data.project_name} | Duration: {data.duration_mins}min"]

        if data.git_log:
            parts.append(f"Commits during session:\n{data.git_log}")

        if data.git_diff:
            file_summary = self._summarize_diff(data.git_diff)
            parts.append(f"Files changed:\n{file_summary}")

            if len(data.git_diff) > self.MAX_DIFF_LENGTH:
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

    def _truncate_turns(self, turns: list[Turn]) -> list[Turn]:
        """Truncate assistant messages that are too long (code dumps, etc.)."""
        result: list[Turn] = []
        for t in turns:
            if t.role == "assistant" and len(t.content) > self.MAX_ASSISTANT_LENGTH:
                truncated = (
                    t.content[: self.MAX_ASSISTANT_LENGTH] + "\n[...truncated]"
                )
                result.append(Turn(role=t.role, content=truncated, timestamp=t.timestamp))
            else:
                result.append(t)
        return result

    def _chunk_messages(
        self,
        messages: list[dict],
        git_preamble: str,
        data: RawSessionData,
    ) -> list[MessageChunk]:
        """Split messages into chunks, prepending git context to first chunk."""
        if not messages:
            # No conversation turns, but we have git data
            return [
                MessageChunk(
                    messages=[{"role": "user", "content": git_preamble}],
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

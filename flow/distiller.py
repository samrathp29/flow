"""Distiller — converts RawSessionData into a compact memory paragraph via LLM."""

from flow.config import FlowConfig
from flow.llm import LLM
from flow.session import RawSessionData, Turn

DISTILLATION_PROMPT = """\
You are processing a developer's coding session into a compact memory entry.
Extract only what the developer would need to re-enter this project after
an extended absence. Be ruthlessly concise.

Output a single paragraph (3-6 sentences) covering:
1. What was being built or changed
2. Any key decisions made (include the reasoning if it was discussed)
3. What was attempted and didn't work (if any)
4. Unresolved questions or blockers (if any)
5. The clearest logical next step

Ignore: AI back-and-forth that led nowhere, dependency installs,
formatting changes, code style discussions, tool errors and retries.
If a decision was reversed, only record the final state.
Do not use bullet points. Write in past tense."""


class Distiller:
    """Distills a raw coding session into a compact memory entry."""

    def __init__(self, config: FlowConfig):
        self.llm = LLM(config)

    def distill(self, data: RawSessionData) -> str:
        """Distill session data into a single paragraph via LLM."""
        if not data.turns and not data.git_diff:
            return (
                f"Session of {data.duration_mins} minutes with no recorded "
                "AI activity or file changes."
            )

        conversation = self._format_turns(data.turns)
        user_content = (
            f"SESSION: {data.project_name} | {data.duration_mins} minutes\n\n"
            f"AI CONVERSATION:\n{conversation}\n\n"
            f"GIT DIFF (files changed):\n{data.git_diff[:8000]}\n\n"
            f"RECENT COMMITS:\n{data.git_log}"
        )

        return self.llm.call(DISTILLATION_PROMPT, user_content)

    def _format_turns(self, turns: list[Turn]) -> str:
        """Format turns into a readable conversation string."""
        return "\n".join(f"{t.role}: {t.content}" for t in turns)

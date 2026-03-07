"""Proactive Context Injection — queries mem0, formats for AI agents, writes context files."""

import logging
import re
from pathlib import Path

from flow.config import FlowConfig
from flow.llm import LLM, LLMError
from flow.memory import FlowMemory

logger = logging.getLogger(__name__)

MARKER_START = "<!-- flow:start -->"
MARKER_END = "<!-- flow:end -->"

CONTEXT_QUERIES = [
    "what is currently in progress and actively being built",
    "decisions made and approaches that were abandoned or failed",
    "open questions blockers and what comes next",
]

FORMATTING_PROMPT = """\
You are writing a context file that will be read by an AI coding agent
at the start of a session. The agent has no prior knowledge of this project.

Using only the memories provided, write a compact context block covering:
1. CURRENT STATE: what is actively in progress right now
2. DECISIONS: key choices made and why (include what was rejected)
3. DEAD ENDS: approaches tried that didn't work — the agent must not re-suggest these
4. NEXT: the single most logical next action

Rules:
- Be specific and technical. Vague context is useless to an agent.
- Dead ends section is mandatory. An agent re-suggesting a rejected
  approach wastes the entire session.
- Total length must stay under 300 tokens. Every word must earn its place.
- Write for an agent, not a human. No narrative. Precise, actionable facts.
- Use **bold** labels for each section (e.g. **Current state:**).
- If memories are insufficient to fill a section, omit that section rather than guessing."""


class ContextInjector:
    """Queries project memory, formats for AI agent consumption, writes context files."""

    def __init__(self, config: FlowConfig):
        self.flow_memory = FlowMemory(config)
        self.llm = LLM(config)

    def inject(self, project_name: str, project_path: str) -> list[str]:
        """Main entry point. Returns list of filenames written (empty if nothing to inject)."""
        project_path_obj = Path(project_path)

        memories = self._gather_memories(project_name)
        if not memories:
            return []

        formatted = self._format_context(memories)
        if not formatted:
            return []

        targets = self._detect_target_files(project_path_obj)
        written = []
        for filename in targets:
            target = project_path_obj / filename
            try:
                self._write_file(target, formatted)
                written.append(filename)
            except OSError:
                logger.warning("Failed to write context to %s", target, exc_info=True)

        return written

    def _gather_memories(self, project_name: str) -> list[str]:
        """Run 3 targeted mem0 searches, deduplicate by string value."""
        seen: set[str] = set()
        all_memories: list[str] = []
        for query in CONTEXT_QUERIES:
            hits = self.flow_memory.search(project_name, query, limit=3)
            for memory_text in hits:
                if memory_text not in seen:
                    seen.add(memory_text)
                    all_memories.append(memory_text)
        return all_memories

    def _format_context(self, memories: list[str]) -> str:
        """LLM call to shape memories into a structured context block."""
        if not memories:
            return ""

        context_text = "\n".join(f"- {m}" for m in memories)
        user_message = f"Project memories:\n{context_text}"

        try:
            return self.llm.call(FORMATTING_PROMPT, user_message).strip()
        except LLMError:
            logger.warning("Context formatting LLM call failed", exc_info=True)
            return ""

    def _detect_target_files(self, project_path: Path) -> list[str]:
        """Determine which context files to write based on what's present."""
        targets = ["CLAUDE.md"]
        if (project_path / "AGENTS.md").exists():
            targets.append("AGENTS.md")
        if (project_path / ".cursor").exists():
            # Support new Cursor Project Rules format (.mdc)
            targets.append(".cursor/rules/flow.mdc")
        return targets

    def _write_file(self, target: Path, block: str) -> None:
        """Write or update a single context file with marker-delimited block."""
        replacement = f"{MARKER_START}\n{block}\n{MARKER_END}"

        if not target.exists():
            # Create parent directories if needed (e.g. .cursor/rules/)
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.suffix == ".mdc":
                # Cursor Project Rules format requires a YAML header
                header = "---\ndescription: \"Project context and recent activity from Flow\"\nglobs: \"**/*\"\nalwaysApply: true\n---\n\n"
            else:
                header = "<!-- flow: auto-generated context — do not edit this block -->\n\n"
            
            target.write_text(f"{header}{replacement}\n")
        else:
            self._inject_or_replace(target, replacement)

    def _inject_or_replace(self, target: Path, block: str) -> None:
        """Replace content between markers, or append if no markers exist yet."""
        existing = target.read_text()
        pattern = re.compile(
            rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
            re.DOTALL,
        )

        if pattern.search(existing):
            updated = pattern.sub(block, existing)
        else:
            updated = existing.rstrip("\n") + f"\n\n{block}\n"

        target.write_text(updated)

    def close(self) -> None:
        """Close the underlying FlowMemory / Qdrant client."""
        self.flow_memory.close()

"""Memory layer — stores and retrieves distilled sessions via mem0 + Qdrant."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from mem0 import Memory

from flow.config import FlowConfig
from flow.session import MessageChunk

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are extracting developer re-entry facts from a raw coding session \
conversation between a developer and an AI assistant.

Extract ONLY facts that help the developer resume work after an extended absence:
- What feature, bug fix, or refactor was actively being worked on
- Architectural or implementation decisions made (include reasoning if stated)
- Approaches tried that failed or were abandoned (and why)
- Open questions, blockers, or unresolved technical issues
- The next concrete step to take
- Files or components that were the focus of changes

STRICTLY IGNORE:
- Code snippets, diffs, and implementation details (extract the decision, not the code)
- AI explanations of how code works (unless a decision was made based on it)
- Dependency installation, import errors, tool retries, build output
- Formatting, linting, style discussions
- General programming knowledge or best-practice explanations
- File contents that were read or displayed
- Tool invocations and their raw output

When you see git diff information, extract WHAT changed and WHY, not the diff itself.
When a decision was reversed during the session, only record the final state.
Each fact should be a single concise sentence. Prefer specificity over breadth.

Return a json object with a single key "facts" containing a list of short fact strings.
Example: {"facts": ["Switched from REST to GraphQL for the user API due to nested data requirements", \
"JWT refresh endpoint is broken - returns 401 instead of new token", \
"Next step: add rate limiting middleware to the /api/auth routes"]}"""

UPDATE_PROMPT = """\
You are managing a developer's project memory. Your goal is to keep \
the memory store **converged** — a concise, current-state knowledge base, \
not an append-only log.

Compare each new fact against ALL existing memories. For each new fact, decide:

1. **UPDATE** (preferred): When a new fact supersedes, refines, or evolves an \
existing memory. Merge them into ONE memory that captures the current state. \
Examples:
   - Old: "Using Redis for caching" + New: "Abandoned Redis, switched to Memcached" \
→ UPDATE to: "Switched from Redis to Memcached for caching (Redis was too complex)"
   - Old: "JWT auth is broken" + New: "Fixed JWT auth by correcting the refresh endpoint" \
→ UPDATE to: "JWT auth is working after fixing the refresh endpoint"

2. **DELETE**: When an existing memory is fully contradicted and the new fact \
already captures the change via an UPDATE. Use sparingly.

3. **ADD**: ONLY when the fact is genuinely novel — not a variation, evolution, \
or correction of any existing memory. Before choosing ADD, re-check every \
existing memory for overlap.

4. **DISCARD**: When the fact is already captured in existing memory.

**Bias strongly toward UPDATE over ADD.** Two memories about the same topic \
(e.g., caching, auth, database choice) should almost always be merged into one."""


class FlowMemory:
    """Manages session memory storage and retrieval via mem0."""

    def __init__(self, config: FlowConfig):
        self.data_dir = config.data_dir
        embedder_config = {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
            },
        }
        # Pass the API key to the embedder when using OpenAI as the LLM provider
        if config.llm_provider == "openai":
            embedder_config["config"]["api_key"] = config.api_key

        mem0_config = {
            "llm": {
                "provider": config.llm_provider,
                "config": {
                    "model": config.llm_model,
                    "api_key": config.api_key,
                    "temperature": 0.1,
                },
            },
            "embedder": embedder_config,
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "flow_sessions",
                    "path": str(config.data_dir / "mem0" / "qdrant"),
                    "on_disk": True,
                },
            },
            "custom_fact_extraction_prompt": EXTRACTION_PROMPT,
            "custom_update_memory_prompt": UPDATE_PROMPT,
            "version": "v1.1",
        }
        self.memory = Memory.from_config(mem0_config)

    def add(self, distilled: str, project_name: str, metadata: dict) -> None:
        """Store a distilled session paragraph. Falls back to file on failure."""
        try:
            self.memory.add(
                messages=[{"role": "user", "content": distilled}],
                user_id="flow",
                agent_id=project_name,
                metadata=metadata,
            )
        except Exception:
            logger.warning("mem0 add failed, writing to fallback", exc_info=True)
            self._write_fallback(distilled, project_name)

    def add_chunks(
        self,
        chunks: list[MessageChunk],
        project_name: str,
        metadata: dict,
    ) -> int:
        """Store session chunks via mem0. Returns count of successfully stored chunks.

        Continues processing remaining chunks if one fails.
        Falls back to file on total failure.
        """
        success_count = 0
        for chunk in chunks:
            try:
                self.memory.add(
                    messages=chunk.messages,
                    user_id="flow",
                    agent_id=project_name,
                    metadata={
                        **metadata,
                        "chunk_index": chunk.chunk_index,
                        "total_chunks": chunk.total_chunks,
                    },
                )
                success_count += 1
            except Exception:
                logger.warning(
                    "mem0 add failed for chunk %d/%d",
                    chunk.chunk_index + 1,
                    chunk.total_chunks,
                    exc_info=True,
                )

        if success_count == 0 and chunks:
            combined = "\n\n---\n\n".join(
                "\n".join(f"{m['role']}: {m['content']}" for m in c.messages)
                for c in chunks
            )
            self._write_fallback(combined, project_name)

        return success_count

    def search(self, project_name: str, query: str, limit: int = 5) -> list[str]:
        """Search memories for a project. Returns list of memory strings."""
        try:
            results = self.memory.search(
                query=query,
                user_id="flow",
                agent_id=project_name,
                limit=limit,
            )
            return [r["memory"] for r in results.get("results", [])]
        except Exception:
            logger.warning("mem0 search failed", exc_info=True)
            return []

    def search_all_projects(self, query: str, limit: int = 10) -> list[dict]:
        """Search memories across all projects. Returns list of result dicts."""
        try:
            results = self.memory.search(
                query=query,
                user_id="flow",
                limit=limit,
            )
            return results.get("results", [])
        except Exception:
            logger.warning("mem0 cross-project search failed", exc_info=True)
            return []

    def close(self) -> None:
        """Close the underlying vector store client to flush data to disk."""
        try:
            self.memory.vector_store.client.close()
        except Exception:
            logger.warning("Failed to close vector store client", exc_info=True)

    def _write_fallback(self, distilled: str, project_name: str) -> None:
        """Write distilled text to failed/ directory for manual recovery."""
        failed_dir = self.data_dir / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = failed_dir / f"{project_name}_{timestamp}.txt"
        path.write_text(distilled)
        logger.info("Fallback written to %s", path)

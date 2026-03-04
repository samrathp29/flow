"""Memory layer — stores and retrieves distilled sessions via mem0 + Qdrant."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from mem0 import Memory

from flow.config import FlowConfig

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
Extract facts a developer would need to re-enter a project after weeks away.
Capture only:
- What was actively being built or changed
- Architectural or implementation decisions made (and why, if stated)
- Bugs or approaches that were tried and failed
- Open questions, blockers, or unresolved decisions
- The next concrete step

Ignore: general chatter, tool usage logs, code explanations that \
don't involve a decision, dependency management, formatting.

Return the extracted facts as a json object."""


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
                },
            },
            "custom_fact_extraction_prompt": EXTRACTION_PROMPT,
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

    def _write_fallback(self, distilled: str, project_name: str) -> None:
        """Write distilled text to failed/ directory for manual recovery."""
        failed_dir = self.data_dir / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = failed_dir / f"{project_name}_{timestamp}.txt"
        path.write_text(distilled)
        logger.info("Fallback written to %s", path)

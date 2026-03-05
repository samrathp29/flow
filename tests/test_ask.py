"""Unit tests for flow ask: search_all_projects and synthesize."""

from unittest.mock import MagicMock, patch

from flow.llm import LLMError
from flow.retriever import Retriever, SYNTHESIS_PROMPT


class TestSearchAllProjects:
    def test_returns_full_result_dicts(self):
        mock_config = MagicMock()
        with patch("flow.memory.Memory.from_config") as mock_mem0:
            mock_mem0.return_value.search.return_value = {
                "results": [
                    {"memory": "Built auth", "agent_id": "proj-a", "metadata": {"session_date": "2025-01-01"}},
                    {"memory": "Added caching", "agent_id": "proj-b", "metadata": {"session_date": "2025-02-01"}},
                ]
            }
            from flow.memory import FlowMemory
            fm = FlowMemory(mock_config)
            results = fm.search_all_projects("auth", limit=5)

        assert len(results) == 2
        assert results[0]["memory"] == "Built auth"
        assert results[0]["agent_id"] == "proj-a"
        assert results[1]["metadata"]["session_date"] == "2025-02-01"

    def test_no_agent_id_filter(self):
        mock_config = MagicMock()
        with patch("flow.memory.Memory.from_config") as mock_mem0:
            mock_mem0.return_value.search.return_value = {"results": []}
            from flow.memory import FlowMemory
            fm = FlowMemory(mock_config)
            fm.search_all_projects("query")

            call_kwargs = mock_mem0.return_value.search.call_args.kwargs
            assert "agent_id" not in call_kwargs
            assert call_kwargs["user_id"] == "flow"

    def test_returns_empty_on_failure(self):
        mock_config = MagicMock()
        with patch("flow.memory.Memory.from_config") as mock_mem0:
            mock_mem0.return_value.search.side_effect = RuntimeError("boom")
            from flow.memory import FlowMemory
            fm = FlowMemory(mock_config)
            results = fm.search_all_projects("query")

        assert results == []


class TestSynthesize:
    def _make_retriever(self):
        mock_config = MagicMock()
        with patch("flow.retriever.FlowMemory"):
            r = Retriever(mock_config)
        r.llm = MagicMock()
        return r

    def test_empty_memories(self):
        r = self._make_retriever()
        result = r.synthesize("anything", [])
        assert "No relevant memories" in result
        r.llm.call.assert_not_called()

    def test_formats_memories_and_calls_llm(self):
        r = self._make_retriever()
        r.llm.call.return_value = "Synthesized answer."
        memories = [
            {"memory": "Built JWT auth", "agent_id": "auth-svc", "metadata": {"session_date": "2025-07-01"}},
            {"memory": "Added Redis caching", "agent_id": "payments", "metadata": {"session_date": "2025-09-15"}},
        ]

        result = r.synthesize("how did I handle auth?", memories)

        assert result == "Synthesized answer."
        call_args = r.llm.call.call_args
        assert call_args[0][0] == SYNTHESIS_PROMPT
        user_msg = call_args[0][1]
        assert "how did I handle auth?" in user_msg
        assert "[auth-svc, 2025-07-01]" in user_msg
        assert "[payments, 2025-09-15]" in user_msg

    def test_fallback_on_llm_failure(self):
        r = self._make_retriever()
        r.llm.call.side_effect = LLMError("fail")
        memories = [
            {"memory": "Built auth", "agent_id": "proj", "metadata": {"session_date": "2025-01-01"}},
        ]

        result = r.synthesize("question", memories)

        assert "Relevant memories:" in result
        assert "Built auth" in result

    def test_missing_metadata_handled(self):
        r = self._make_retriever()
        r.llm.call.return_value = "Answer."
        memories = [{"memory": "Some fact"}]

        result = r.synthesize("question", memories)

        assert result == "Answer."
        user_msg = r.llm.call.call_args[0][1]
        assert "[unknown, unknown date]" in user_msg

## `flow ask` — Technical Description

### What it does

`flow ask` is a cross-project semantic query against the full mem0 memory store accumulated across all of a developer's projects. It answers questions grounded exclusively in the developer's own recorded history — not general knowledge.

```
$ flow ask "how have I handled authentication across my projects?"

In auth-service (8 months ago) you implemented JWT with absolute expiry
after abandoning sliding expiry — session proliferation on mobile clients
made sliding untenable. In payments-api (4 months ago) you went stateless
using short-lived access tokens with a Redis-backed refresh store, noting
it was overkill for the scale but the infra was already there. In
dashboard-app (6 weeks ago) you punted on auth entirely and delegated to
Clerk, which you noted was the right call for a side project.
```

The answer is not advice. It is recall — surfaced from the developer's own decisions, filtered by semantic relevance, synthesized into a coherent response.

---

### How it works

```python
@cli.command()
@click.argument("query")
def ask(query: str):
    memories = flow_memory.search_all_projects(query, limit=10)
    response = retriever.synthesize(query, memories)
    print(response)
```

**The key difference from `flow wake`:** no `agent_id` filter is applied to the mem0 search. The query runs across the entire store.

```python
def search_all_projects(self, query: str, limit: int = 10) -> list[dict]:
    results = self.memory.search(
        query=query,
        user_id="flow",
        # agent_id deliberately omitted — full cross-project search
        limit=limit
    )
    return results["results"]  # each result includes memory + metadata
```

Each result carries its `metadata` — the project name, session date, duration — so the synthesizing LLM can attribute which project each memory came from and when, giving the response temporal and contextual grounding.

The briefing prompt instructs the LLM to be attributive:

```python
SYNTHESIS_PROMPT = """
You are answering a developer's question using only memories from their
own past projects. Each memory is tagged with a project name and date.

Answer the question by synthesizing what the developer actually did and
decided across their projects — not general best practice. Be specific
about which project, when, and what the outcome was. Where their approach
evolved across projects, note that evolution explicitly.

If the memories don't contain a relevant answer, say so directly.
Do not speculate beyond what the memories contain.
"""
```

---

### Where mem0 makes this unparalleled

Most memory layers are semantically searchable append-only stores. You write entries, you retrieve them by vector similarity. The store grows indefinitely and contains every entry you ever wrote, including outdated, superseded, and contradictory ones. The retrieval quality degrades as the store grows because noise accumulates at the same rate as signal.

**mem0 is not an append-only store.**

Every time `memory.add()` is called, mem0 runs an `ADD / UPDATE / DELETE / NONE` decision for each incoming fact against all existing memories. This is its core architectural differentiator — the memory store is a living, self-correcting record of current understanding, not a historical log.

Applied to `flow ask`, this has a specific and powerful consequence:

If a developer tried Redis for session caching on project A, abandoned it, tried it again on project B with a different outcome, and then settled on a different approach entirely on project C — mem0 doesn't store three conflicting entries. It reconciles them into a memory that reflects the evolved understanding: *this developer has tried Redis for session caching in multiple contexts, with these outcomes under these conditions, and has settled on this approach.* The semantic search then returns this reconciled fact rather than three contradictory raw entries.

No other memory framework does this at the storage layer. Every competing approach — raw vector stores (Pinecone, Chroma, Qdrant used directly), LangChain memory, Zep, custom RAG pipelines — is append-only. They retrieve *everything that was ever stored and is semantically similar to the query*, including the outdated and the superseded. You either manage deduplication yourself, which is a hard unsolved problem, or you accept degrading retrieval quality over time.

mem0 solves this with its custom update memory prompt — the LLM-powered reconciliation layer that runs on every write. For `flow ask`, this means:

- The more sessions a developer logs, the **more accurate** the answers get, not the noisier
- A developer's evolved understanding of a problem is reflected in current memories, not buried under historical attempts
- Cross-project synthesis is coherent rather than contradictory, because conflicting memories from different projects have already been reconciled at write time

The result is that `flow ask` becomes meaningfully more powerful the longer it's used — which is the opposite of how most retrieval systems behave in practice. After a year of sessions across ten projects, the memory store isn't ten times noisier. It's ten times richer, with a self-maintained index of the developer's current best knowledge across every technical problem they've encountered and every decision they've made.

That compounding, self-correcting, cross-project knowledge layer is what no other tool on the market provides — and it's what makes `flow ask` not just a useful feature but the long-term reason a developer would never stop using flow.
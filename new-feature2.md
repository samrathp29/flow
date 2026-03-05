## Proactive Context Injection — Technical Description

### What it does

Every time a developer runs `flow start`, before watching begins, flow queries mem0 for the current reconciled state of that project and writes it to the AI tool's context file — `CLAUDE.md` for Claude Code, `AGENTS.md` for Codex, `.cursorrules` for Cursor (all in project directory, not home directory). The AI agent that opens in that session reads the file automatically on its first prompt and arrives with full project context, requiring zero re-explanation from the developer.

The file isn't a log. It isn't a history. It's a precise, compact snapshot of current project understanding — what's in progress, what was decided and why, what was abandoned, what comes next. It gets rewritten fresh on every `flow start`, so it always reflects where things actually stand.

---

### The user experience

Without flow, a developer returning to a project after three weeks opens Claude Code and types something like:

> *"I'm working on an OAuth implementation. I was using Passport.js after abandoning a hand-rolled approach. The Google provider works but GitHub is failing silently on the callback. I think it's a scope issue. Can you help me debug?"*

That paragraph is pure re-orientation overhead. The developer already knows all of it. They're just feeding context to a blank-slate agent before any real work can begin. This happens at the start of every new session — not just after long absences. Every time context bloat forces a new session, the tax is paid again.

With flow, the developer runs `flow start`, opens Claude Code, and types:

> *"Let's fix the GitHub OAuth callback."*

The agent already knows what that means, why it matters, what was tried, and what the current hypothesis is. The first message is productive. The re-orientation overhead is zero.

This compounds significantly for developers who create new sessions frequently to avoid context bloat — which is exactly the behaviour Claude Code, Codex, and Cursor encourage. The more aggressively a developer manages context windows, the more re-explanation overhead they currently pay. Flow inverts this: frequent session creation becomes costless because context is restored automatically on every start.

---

### How it works

```
flow start
    │
    ├── mem0.search(project, queries, limit=8)    ← cross-session retrieval
    │       │
    │       └── returns reconciled facts about current project state
    │
    ├── LLM formatting call                        ← shape for AI consumption
    │       │
    │       └── produces compact structured markdown
    │
    ├── detect which AI tools are present          ← CLAUDE.md / AGENTS.md / .cursorrules
    │
    └── write context file(s)                      ← overwrites on every start
```

**Retrieval — three targeted queries, not one:**

A single broad query ("what's going on with this project") returns whatever is most semantically similar, which is often the most recent session rather than the most relevant state. Instead, flow runs three parallel mem0 searches against the same project store:

```python
CONTEXT_QUERIES = [
    "what is currently in progress and actively being built",
    "decisions made and approaches that were abandoned or failed",
    "open questions blockers and what comes next"
]

def build_context(self, project_name: str) -> list[dict]:
    results = []
    for query in CONTEXT_QUERIES:
        hits = self.memory.search(
            query=query,
            user_id="flow",
            agent_id=project_name,
            limit=3
        )
        results += hits["results"]
    return self._deduplicate(results)
```

This produces a structured retrieval that maps directly to what an AI agent needs to be useful from its first prompt: current state, constraints, and direction.

**Formatting — shaped for agent consumption, not human reading:**

The retrieved memories are passed to a formatting LLM call with a prompt specifically designed to produce output that an AI coding agent can act on rather than just read:

```python
FORMATTING_PROMPT = """
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
"""
```

The dead ends section is the most important part. Without it, an agent will independently arrive at the same rejected approaches — not because it's unintelligent, but because those approaches are often generically reasonable. The agent doesn't know they were already tried and failed in *this specific project* for *this specific reason*. Writing that constraint explicitly into the context file eliminates an entire class of wasted prompts.

**File detection and writing:**

```python
CONTEXT_FILES = {
    "CLAUDE.md":    lambda p: (p / "CLAUDE.md").exists() or True,
    "AGENTS.md":    lambda p: (p / "AGENTS.md").exists(),
    ".cursorrules": lambda p: (p / ".cursor").exists(),
}

def write_context_files(self, project_path: Path, content: str) -> list[str]:
    written = []
    header = "<!-- flow: auto-generated context — do not edit -->\n\n"
    marker_start = "<!-- flow:start -->"
    marker_end   = "<!-- flow:end -->"
    block = f"{marker_start}\n{content}\n{marker_end}"

    for filename, should_write in CONTEXT_FILES.items():
        if not should_write(project_path):
            continue
        target = project_path / filename
        if target.exists():
            self._inject_or_replace_block(target, block, header)
        else:
            target.write_text(f"{header}{block}\n")
        written.append(filename)
    return written
```

If `CLAUDE.md` already exists with developer-written content, flow injects the context block between markers without touching anything else. On the next `flow start`, it replaces only what's between the markers. Developer notes and project instructions are never clobbered.

The written output looks like this:

```markdown
<!-- flow:start -->
**Current state:** Implementing OAuth via Passport.js. Google provider
works end-to-end. GitHub callback fails silently — no error thrown,
redirects to / without authenticating.

**Decisions:** Switched from hand-rolled JWT auth at session 3 —
token refresh logic became unmanageable. Passport chosen for strategy
abstraction. Absolute expiry chosen over sliding after mobile session
proliferation in a prior project.

**Dead ends:** Do not suggest hand-rolled token refresh. Do not suggest
sliding expiry. Scope configuration on GitHub app was already verified
correct — issue is elsewhere.

**Next:** Add debug logging to GitHub strategy. Check if callback URL
in GitHub OAuth app settings matches the registered redirect URI exactly.
<!-- flow:end -->
```

---

### Where mem0 makes this unparalleled

The file above looks simple. The reason it's accurate, compact, and non-contradictory — rather than a bloated dump of session history — is entirely due to mem0's architecture.

Every other approach to this problem stores raw data. If you tried to build this with a plain vector store, a SQLite session log, or an append-only memory layer, you would face an unavoidable problem: **the store grows monotonically, and retrieval quality degrades as it grows.** Session 1 says "using hand-rolled auth." Session 3 says "switched to Passport.js." Session 5 says "tried sliding expiry." A raw retrieval over this store returns all three. The formatting LLM has to reason about which is current. Over 20 sessions it becomes increasingly difficult to produce a clean, accurate context block — and increasingly likely to inject contradictory or outdated facts into the agent's context window.

Outdated context injected into an agent is worse than no context. An agent told that the project uses hand-rolled auth when it actually uses Passport.js will actively produce wrong suggestions. The failure mode of naive memory injection isn't neutral — it's negative.

**mem0 eliminates this failure mode at the storage layer.**

When session 3 records "switched from hand-rolled auth to Passport.js," mem0's reconciliation pass runs `DELETE` on the hand-rolled auth memory and `ADD` on the Passport.js memory. When session 5 records "tried sliding expiry, rejected it," mem0 stores the rejection, not just the attempt. By the time `flow start` queries the store at session 20, it retrieves a set of non-contradictory, current facts — because conflicting and superseded memories were resolved the moment they were written.

The context file that gets injected into the AI tool's session is therefore always coherent, always current, and stays compact regardless of how many sessions have been logged. It doesn't grow over time. It stays accurate over time. Those are opposite behaviours, and the difference is mem0's write-time reconciliation — something no other memory framework does.

The practical consequence is that the AI agent operating in a flow-enabled project gets progressively better context the longer the developer uses the tool — not progressively noisier context. That's the property that makes this feature not just useful but structurally unbeatable by any approach that doesn't have a self-correcting memory layer at its core.


## Traditional compaction vs Mem0
### What compaction does and where it fails

Claude Code's built-in compaction is **intra-session lossy compression**. When the context window fills up, it summarizes the conversation so far — replacing earlier messages with a compressed version — and continues. This solves the immediate problem of context overflow, but it has three structural limitations that mem0 doesn't share.

**First, compaction preserves noise.** The compaction mechanism summarizes *everything that happened* — the back-and-forth that went nowhere, the tool errors and retries, the approaches Claude suggested that you rejected. It compresses by volume and recency, not by developer-re-entry relevance. The output is a smaller version of everything, not a precise extraction of what matters.

**Second, compaction is ephemeral.** The compacted summary lives inside the context window of the current session. When the session ends — whether you close it or start a new one to avoid further bloat — the compacted context is gone. The next session starts blank. Compaction solves context overflow *within* a session but does nothing for continuity *across* sessions. These are two different problems, and built-in compaction only addresses one.

**Third, compaction is write-once.** The summary is generated at the moment compaction triggers and stays static. It doesn't update as the session continues. It doesn't reconcile with what happened afterward. It's a snapshot of a particular moment, not a living record.

---

### What mem0 does differently

mem0 is not compression. It's **selective extraction with write-time reconciliation.** The distinction matters enormously.

When flow calls `memory.add()` at the end of a session, mem0 doesn't compress what happened — it extracts only the facts that match the custom extraction prompt: decisions, dead ends, blockers, next steps. Everything else is discarded at the point of storage, not summarized. The signal-to-noise ratio of what gets preserved is categorically higher than any compression of the full conversation.

More importantly, every `add()` call runs the `ADD / UPDATE / DELETE / NONE` reconciliation pass against the existing store. This is the property compaction has no equivalent of. If session 5 reverses a decision made in session 2, mem0 deletes the session 2 memory and replaces it with the current understanding. The store doesn't accumulate the history of the decision — it holds the current state of it.

Applied to the compaction problem specifically, this means:

**mem0 prevents context bloat from re-entering the session.** When `flow start` writes the context file, it writes a reconciled, compact snapshot of current project state — typically under 300 tokens. The AI tool's context window starts the session with precise, non-contradictory facts rather than starting blank. A session that begins with high-quality injected context takes far longer to require compaction in the first place, because the agent isn't spending context tokens re-establishing ground truth through conversation.

**When compaction does eventually trigger, what it's compressing is cleaner.** The early part of a flow-enabled session contains purposeful work rather than re-orientation overhead. The compaction summary of that conversation is therefore higher quality — it summarizes decisions and progress rather than "developer spent first 15 messages re-explaining the project to the agent."

**What survives session end is extracted, not compressed.** When the session ends and `flow stop` runs, mem0 stores the session's meaningful output — not a summary of the full conversation including compacted sections, but a precise extraction of what changed, what was decided, what was learned. That extracted memory then feeds back into the next session's context injection, completing the loop.

---

### The structural difference in one sentence

Claude Code's compaction asks: **"how do I fit what happened into a smaller space?"**

mem0 asks: **"of everything that happened, what actually needs to survive?"**

These produce fundamentally different outputs. Compression preserves structure and reduces size. Extraction discards structure and preserves only signal. For the purpose of developer re-entry and AI agent orientation, extraction is the right operation — and it's the only one that compounds in value over time rather than degrading as history accumulates.

The compaction built into Claude Code is solving a context window management problem. mem0 is solving a knowledge continuity problem. They're not competing — but mem0's approach to knowledge continuity happens to make the context window management problem significantly less severe as a side effect.
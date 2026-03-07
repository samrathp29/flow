# Flow

Flow is a CLI that watches your coding session and tells you where you left off. Reclaim your context and reach flow state instantly. It tracks your AI tool chat logs (Claude Code, Cursor, Codex) and git activity, distilling it into concise project context using an LLM and Mem0.

## Installation

Requires Python 3.11+.

Install the package from the project root:

```bash
git clone https://github.com/samrathp29/flow.git
cd flow
pip install -e .
```

Dependencies: `click`, `mem0ai`, `anthropic`, `openai`, `qdrant-client`.

## Setup

Run the initialization command to configure your LLM provider and API key.

```bash
flow init
```

This interactive prompt will set up your provider (Anthropic or OpenAI), default models, and initialize the local storage directory at `~/.local/share/flow`. Configuration is stored in `~/.config/flow/config.toml`.

## Usage

Flow operates alongside your normal git workflow. All commands are run from inside a git repository.

### Start a Session

Begin tracking a coding session in your current git repository. If previous sessions exist, Flow automatically queries your project's memory and injects a compact context block into your AI tool's rules file: `CLAUDE.md` for Claude Code, `AGENTS.md` for Codex, `.cursorrules` for Cursor. The AI agent reads this on its first prompt and arrives with full project context: what's in progress, key decisions, dead ends to avoid, and what to do next.

```bash
flow start
# ▶ Session started — watching my-project
# ⟳ Context injected into CLAUDE.md
```

Developer-written content in existing rules files is never overwritten. Flow injects between `<!-- flow:start -->` / `<!-- flow:end -->` markers and replaces only that block on each start.

If a previous session crashed or was never stopped, Flow automatically recovers it on the next `flow start`.

### Stop a Session

End the current session. Flow collates logs from Claude Code, Cursor, Codex, and Git, then formats them into chunked messages, redacts secrets, and stores the result in local vector memory via Mem0.

```bash
flow stop
```

Any previously failed sessions are retried automatically during stop.

### Wake

Get a situational briefing on what you were last working on in this project. The briefing adapts its detail based on how long you've been away (short absences get a quick recap, longer ones get more context).

```bash
flow wake
```

If no memories exist yet (cold start), Flow falls back to generating a briefing from git history alone.



## How It Works

### Pipeline Overview

```
flow start
───────────────────────────────────────────────────────────────────────
 detect git root
       │
       ▼
 stale session? ──yes──▶ recover: collect → format → mem0.add_chunks
       │                          │
       │                  clean stale state
       │◀─────────────────────────┘
       ▼
 record HEAD commit + timestamp + PID
 write state to sessions/{project_id}.json
 write PID to pids/{project_id}.pid
       │
       ▼
 prior memories? ──no──▶ done
       │
      yes
       │
       ▼
 3 targeted mem0 searches (deduplicated)
   • "what is currently in progress and actively being built"
   • "decisions made and approaches that were abandoned or failed"
   • "open questions blockers and what comes next"
       │
       ▼
 LLM compresses into <300 token context block
       │
       ▼
 inject between <!-- flow:start/end --> markers
 → CLAUDE.md (always)
 → AGENTS.md (if exists)
 → .cursorrules (if .cursor/ exists)


flow stop
───────────────────────────────────────────────────────────────────────
 read + delete state file
       │
       ▼
 retry failed sessions (~/…/flow/failed/*.txt → mem0)
       │
       ▼
 collect session data
 ┌─────────────────────────────────────────────────────┐
 │  Claude Code   ~/.claude/projects/{path}/*.jsonl    │
 │  Cursor        ~/…/Cursor/…/workspaceStorage/       │
 │                  */state.vscdb (SQLite)              │
 │  Codex         ~/.codex/sessions/YYYY/MM/DD/*.jsonl │
 │                                                     │
 │  all turns sorted by timestamp                      │
 │  deduplicate: same role, <60s apart, >90% overlap   │
 │                                                     │
 │  git diff      base_commit → working tree           │
 │                 (excludes CLAUDE.md, AGENTS.md,      │
 │                  .cursorrules, .flow.pid)            │
 │  git log       --oneline --since={started_at}       │
 └─────────────────────────────────────────────────────┘
       │
       ▼
 empty session? (no turns, no diff, no log) ──▶ skip, cleanup
       │
       ▼
 LLM diff summarization (if diff exists)
   diff truncated to 8000 chars → LLM → semantic summary
   (falls back to raw diff on LLM failure)
       │
       ▼
 format into chunks
 ┌─────────────────────────────────────────────────────┐
 │  redact secrets (API keys, AWS keys, GitHub         │
 │    tokens, JWTs) from all turns                     │
 │  truncate assistant messages to 2000 chars          │
 │  cap at 100 most recent turns (10 chunks × 10 msgs)│
 │  prepend git preamble to first chunk:               │
 │    project name, duration, commits, files changed,  │
 │    LLM diff summary (or raw diff excerpt)           │
 │  if no turns: single git-only chunk                 │
 │  ensure each chunk starts with user role            │
 └─────────────────────────────────────────────────────┘
       │
       ▼
 mem0.add_chunks (per chunk)
 ┌─────────────────────────────────────────────────────┐
 │  mem0 internally:                                   │
 │    1. extract facts (custom extraction prompt)      │
 │    2. compare each fact against all existing         │
 │       memories (custom update prompt)               │
 │    3. UPDATE / ADD / DELETE / DISCARD per fact       │
 │    4. embed via text-embedding-3-small → Qdrant     │
 └─────────────────────────────────────────────────────┘
       │
       ▼
 all chunks failed? → write to ~/…/flow/failed/ for retry
       │
       ▼
 cleanup PID file


flow wake
───────────────────────────────────────────────────────────────────────
 detect git root
       │
       ▼
 mem0 search: "what was I working on, what was blocked,
               what comes next" (limit 8)
       │
       ▼
 no memories? ──▶ cold start: git log -n20 → LLM briefing
       │
      yes
       │
       ▼
 check wake cache (5min TTL, keyed by project + memory hash)
   hit? → return cached briefing
       │
       ▼
 estimate days since last session (from mem0 created_at)
       │
       ▼
 select prompt tier:
   ≤3 days  → SHORT  (2-3 sentences)
   4-30     → MEDIUM (3-5 sentences)
   >30      → LONG   (5-7 sentences)
       │
       ▼
 tag first 2 memories as [recent]
 fetch git log (5 commits, or 15 if >30 days away)
       │
       ▼
 LLM generates briefing from memories + git log
 (falls back to raw memories on LLM failure)
       │
       ▼
 cache briefing → display
```

### Session Lifecycle

1. `flow start` records the current HEAD commit and timestamp, and writes a PID file. The shell prompt hook (installed by `flow init`) detects the PID and shows a `(flow)` indicator in your terminal.
2. You work normally. Flow does not run in the foreground; it snapshots state at start/stop.
3. `flow stop` collects all activity since the session started:
   - Parses conversation logs from Claude Code, Cursor, and Codex.
   - Runs `git diff` from the base commit and `git log` for the session window.
   - Summarizes the raw diff with an LLM into a semantic description of what changed and why, so Mem0 extracts meaningful facts instead of parsing hunks.
   - Deduplicates near-identical turns across tools.
   - Redacts secrets (API keys, tokens, JWTs) before storage.
   - Chunks the formatted messages and stores them in Mem0.

### Proactive Context Injection

On `flow start`, if the project has prior memories, Flow runs three targeted searches against Mem0 (current work, decisions/dead ends, blockers/next steps), then uses an LLM to compress the results into a structured context block under 300 tokens. This block is injected into your AI tool's rules file so the agent starts every session fully informed.

### Memory Architecture

- **Storage**: Mem0 with a local Qdrant vector store (persisted to `~/.local/share/flow/mem0/qdrant`).
- **Embeddings**: OpenAI `text-embedding-3-small`.
- **LLM**: Anthropic (Claude) or OpenAI (GPT), configurable via `flow init`.
- **Fallback**: If Mem0 ingestion fails, distilled text is written to `~/.local/share/flow/failed/` for retry on the next `flow stop`.

## Why Mem0

Mem0 is the layer that transforms Flow from a log parser into a system with genuine memory. Without it, Flow would just dump session transcripts into files — growing endlessly, impossible to query, and useless after a few weeks. Mem0 solves three problems that make Flow fundamentally better:

### Automatic Fact Extraction

Raw coding sessions are noisy: tool retries, import errors, verbose diffs, tangential explanations. Mem0's extraction pipeline distills this down to the facts that actually matter for re-entry — what was built, what decisions were made, what failed, and what's next. Flow feeds Mem0 a custom extraction prompt tuned specifically for developer context (completion status, dead ends, next steps), so the memories it produces are immediately actionable rather than generic summaries.

### Convergent Memory, Not an Append-Only Log

This is the key differentiator. Most session-tracking tools just append — every session adds more text, and older entries rot into noise. Mem0's update mechanism compares each new fact against every existing memory and *merges* them. If you switched from Redis to Memcached three sessions ago, you don't have three contradictory memories — you have one that reflects the current state. Flow reinforces this with a custom update prompt that biases strongly toward merging over adding, keeping the memory store compact and current even after months of use.

### Semantic Search Over Your History

Vector embeddings mean you can query your past work by *meaning*, not keywords. When Flow runs `flow start`, it doesn't grep through files — it fires three targeted semantic searches against Mem0 ("what's in progress", "decisions and dead ends", "blockers and next steps") and synthesizes the results into a context block for your AI agent. The same capability powers `flow wake`, where the query "what was I working on, what was blocked, what comes next" retrieves the right memories regardless of how they were originally worded. This is what makes Flow useful across long gaps — the memories are indexed by meaning, not by date.

### The Result

Mem0 gives Flow three properties no file-based approach can match: memories that stay current instead of accumulating, retrieval by intent instead of keyword, and a storage footprint that converges rather than grows. It's what makes the difference between "here are your last 50 session logs" and "here's exactly where you left off."

## Why Not Just Ask Your AI Tool?

A reasonable question: why not just start a new Claude Code session and ask "look at the codebase and tell me where I left off"? The AI agent can read files, run `git log`, scan TODOs — why do you need Flow at all?

Because what's in your codebase is not the same as what you were doing.

### The codebase only shows the present state, not the journey

An AI agent scanning your code sees *what exists*. It doesn't see the three approaches you tried and abandoned before arriving at the current implementation. It doesn't know you chose Qdrant over Pinecone because of local-first constraints, or that the current auth flow is a workaround for a bug you haven't fixed yet. Code is the *output* of decisions — Flow stores the decisions themselves.

### Dead ends leave no trace in code

This is the most expensive gap. If you spent a session trying to use WebSockets before switching to SSE, the codebase only shows SSE. Without Flow, your next AI session might suggest WebSockets as an "improvement" — sending you down a path you already explored and rejected. Flow's memory explicitly tracks what failed and why, and the context injection pipeline puts that directly into the agent's rules file so it never re-suggests a dead end.

### AI tools have no cross-session memory

Claude Code, Cursor, and Codex all start every session with zero context about prior sessions. They're stateless — each conversation is independent. An agent can read your files, but it can't know that yesterday you decided to refactor the parser module, or that you're blocked on an upstream API issue. Flow bridges this gap by persisting structured memories across sessions and injecting them before the agent sees its first prompt.

### Codebase scanning doesn't scale with history

An AI agent can read `git log` and diff recent commits, but this is a static, brute-force retrieval. It doesn't know which commits matter for your current task. It can't distinguish a meaningful architectural change from a formatting cleanup. And as your project grows, the signal-to-noise ratio of raw git history gets worse. Flow's Mem0-backed memory uses semantic search — retrieval by meaning, not by recency — so the right context surfaces regardless of when it was created. Mem0's two-phase pipeline (extract facts, then compare and merge against existing memories) means the memory store stays compact and current-state rather than accumulating stale entries. A raw `git log` from 6 months ago is noise; a Mem0 memory that has been updated across 50 sessions is signal.

### What Flow actually provides that codebase scanning can't

| | Codebase scan | Flow + Mem0 |
|---|---|---|
| Current file contents | Yes | — |
| What you were actively working on | No | Yes |
| Decisions and their reasoning | No | Yes |
| Dead ends and abandoned approaches | No | Yes |
| Cross-session continuity | No | Yes |
| Scales with project age | Degrades | Converges |
| Retrieval method | File read / keyword | Semantic search |
| Context delivered proactively | No | Yes (injected at session start) |

The short version: your codebase tells an AI agent *what your code does*. Flow tells it *what you were doing, what you decided, what didn't work, and what to do next*.

## Supported Tools

Flow can parse conversation logs from:

- **Claude Code**: Reads JSONL project logs from `~/.claude/projects/`.
- **Cursor**: Reads the Cursor workspace storage SQLite databases.
- **Codex**: Reads JSONL session logs from `~/.codex/sessions/`.

## Project Structure

```
flow/
  cli.py          # Click entrypoint: start, stop, wake, init commands
  session.py      # Session state management, data models, stale detection
  collector.py    # Aggregates parser output and git data into RawSessionData
  formatter.py    # Formats sessions into chunked messages, redacts secrets
  memory.py       # Mem0/Qdrant storage and retrieval layer
  retriever.py    # Generates wake briefings
  context.py      # Proactive context injection into AI rules files
  llm.py          # Provider-agnostic LLM wrapper (Anthropic/OpenAI)
  config.py       # Configuration loading from ~/.config/flow/config.toml
  parsers/
    base.py       # Base parser interface
    claude_code.py
    cursor.py
    codex.py
scripts/
  patch_mem0.py   # Utility to patch mem0 for Qdrant validation issues
tests/
  test_commands.py
  test_session.py
  test_context.py
  test_formatter.py
  test_parsers.py
  test_ask.py
  test_e2e_workflow.py
  eval_wake.py    # Wake briefing quality evaluation
  fixtures/       # Test fixture generators
```

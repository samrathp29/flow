# Flow

Flow is a CLI that watches your coding session and tells you where you left off. Reclaim your context and reach flow state instantly. It tracks your terminal commands, IDE chat logs, and git activity, distilling it into concise project context using an LLM and Mem0.

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
# ▶ Session started: watching my-project
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

### Session Lifecycle

1. `flow start` records the current HEAD commit and timestamp, writes a PID file, and installs a shell prompt hook (`(flow)` indicator in your terminal).
2. You work normally. Flow does not run in the foreground; it snapshots state at start/stop.
3. `flow stop` collects all activity since the session started:
   - Parses conversation logs from Claude Code, Cursor, and Codex.
   - Runs `git diff` from the base commit and `git log` for the session window.
   - Deduplicates near-identical turns across tools.
   - Redacts secrets (API keys, tokens, JWTs) before storage.
   - Chunks the formatted messages and stores them in Mem0.

### Proactive Context Injection

On `flow start`, if the project has prior memories, Flow runs three targeted searches against Mem0 (current work, decisions/dead ends, blockers/next steps), then uses an LLM to compress the results into a structured context block under 300 tokens. This block is injected into your AI tool's rules file so the agent starts every session fully informed.

### Memory Architecture

- **Storage**: Mem0 with a local Qdrant vector store (persisted to `~/.local/share/flow/qdrant`).
- **Embeddings**: OpenAI `text-embedding-3-small`.
- **LLM**: Anthropic (Claude) or OpenAI (GPT), configurable via `flow init`.
- **Fallback**: If Mem0 ingestion fails, distilled text is written to `~/.local/share/flow/failed/` for retry on the next `flow stop`.

## Supported Tools

Flow can parse conversation logs from:

- **Claude Code**: Reads JSONL project logs from `~/.claude/projects/`.
- **Cursor**: Reads the Cursor workspace storage SQLite databases.
- **Codex**: Reads JSONL session logs from `~/.codex/sessions/`.

## Project Structure

```
flow/
  cli.py          # Click entrypoint: start, stop, wake, ask, init commands
  session.py      # Session state management, data models, stale detection
  collector.py    # Aggregates parser output and git data into RawSessionData
  formatter.py    # Formats sessions into chunked messages, redacts secrets
  memory.py       # Mem0/Qdrant storage and retrieval layer
  retriever.py    # Generates wake briefings and cross-project answers
  context.py      # Proactive context injection into AI rules files
  llm.py          # Provider-agnostic LLM wrapper (Anthropic/OpenAI)
  config.py       # Configuration loading from ~/.config/flow/config.toml
  parsers/
    base.py       # Base parser interface
    claude_code.py
    cursor.py
    codex.py
tests/
  test_commands.py
  test_session.py
  test_context.py
  test_formatter.py
  test_parsers.py
  test_ask.py
  test_e2e_workflow.py
```

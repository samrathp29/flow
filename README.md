# Flow

Flow is a CLI that watches your coding session and tells you where you left off. Reclaim your context and reach flow state instantly. It tracks your terminal commands, IDE chat logs, and git activity, distilling it into concise project context using an LLM and Mem0.

## Installation

Install the package manually from the project root:

```bash
pip install -e .
```

## Setup

Run the initialization command to configure your LLM provider and API key.

```bash
flow init
```

This interactive prompt will set up your provider (Anthropic or OpenAI), default models, and initialize the local storage directory. 

## Usage

Flow operates alongside your normal git workflow.

### Start a Session

Begin tracking a coding session in your current git repository. If previous sessions exist, Flow automatically queries your project's memory and injects a compact context block into your AI tool's rules file — `CLAUDE.md` for Claude Code, `AGENTS.md` for Codex, `.cursorrules` for Cursor. The AI agent reads this on its first prompt and arrives with full project context: what's in progress, key decisions, dead ends to avoid, and what to do next.

```bash
flow start
# ▶ Session started — watching my-project
# ⟳ Context injected into CLAUDE.md
```

Developer-written content in existing rules files is never overwritten. Flow injects between `<!-- flow:start -->` / `<!-- flow:end -->` markers and replaces only that block on each start.

### Stop a Session

End the current session. Flow collates logs from Claude Code, Cursor, Codex, and Git, then distills the session and stores the summary in local vector memory.

```bash
flow stop
```

### Wake

Get a situational briefing on what you were last working on in this project.

```bash
flow wake
```

### Ask

Ask a question across all your projects. Flow searches your entire memory store and synthesizes an answer from your own history.

```bash
flow ask "how did I handle auth?"
```

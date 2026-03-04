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

Begin tracking a coding session in your current git repository.

```bash
flow start
```

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

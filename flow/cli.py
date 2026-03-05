"""Click entrypoint for flow CLI."""

import os
import sys
from pathlib import Path

import click

PID_FILE = ".flow.pid"

from flow.session import SessionError, SessionManager


@click.group()
def cli():
    """A CLI that watches your coding session and helps you reclaim your context to reach flow state instantly."""
    pass


@cli.command()
def start():
    """Begin a flow session in the current project."""
    sm = SessionManager()
    try:
        state = sm.start()
    except SessionError as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)
    click.echo(f"▶ Session started — watching {state.project_name}")

    # Write PID file so the shell hook can show (flow) in the prompt
    pid_path = Path(state.project_path) / PID_FILE
    pid_path.write_text(str(os.getppid()))

    # Proactive context injection: query mem0, format for AI agent, write context files.
    # Graceful — never blocks or fails the session start.
    from flow.config import ConfigNotFound, FlowConfig

    try:
        config = FlowConfig.load()
    except ConfigNotFound:
        return

    try:
        from flow.context import ContextInjector

        injector = ContextInjector(config)
        written = injector.inject(state.project_name, state.project_path)
        injector.close()
        if written:
            click.echo(f"⟳ Context injected into {', '.join(written)}")
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "Context injection failed", exc_info=True
        )


@cli.command()
def stop():
    """End the session and store to memory."""
    from flow.collector import Collector
    from flow.config import ConfigNotFound, FlowConfig
    from flow.formatter import Formatter
    from flow.memory import FlowMemory

    sm = SessionManager()
    try:
        state = sm.stop()
    except SessionError as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)

    try:
        config = FlowConfig.load()
    except ConfigNotFound as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)

    click.echo("⠿ Processing session...")

    collector = Collector()
    data = collector.collect(state)

    duration = _format_duration(data.duration_mins)
    metadata = {
        "session_date": data.started_at[:10],
        "duration_mins": data.duration_mins,
    }

    # Format into chunks (no LLM call — pure formatting)
    chunks = Formatter().format(data)

    # Store via mem0 (mem0 handles fact extraction internally)
    try:
        mem = FlowMemory(config)
        stored = mem.add_chunks(chunks, data.project_name, metadata)
        mem.close()
        if stored < len(chunks):
            click.echo(
                f"⚠ {len(chunks) - stored}/{len(chunks)} chunks failed to store",
                err=True,
            )
    except Exception:
        from datetime import datetime as _dt, timezone as _tz

        failed_dir = config.data_dir / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        ts = _dt.now(_tz.utc).strftime("%Y%m%dT%H%M%S")
        fallback_path = failed_dir / f"{data.project_name}_{ts}.txt"
        combined = "\n\n---\n\n".join(
            "\n".join(f"{m['role']}: {m['content']}" for m in c.messages)
            for c in chunks
        )
        fallback_path.write_text(combined)
        click.echo(f"⚠ Memory storage failed — session saved to {fallback_path}", err=True)

    # Remove PID file
    pid_path = Path(state.project_path) / PID_FILE
    pid_path.unlink(missing_ok=True)

    click.echo(f"✓ Session saved ({data.project_name} · {duration})")


@cli.command()
def wake():
    """Get a briefing on where you left off."""
    from flow.config import ConfigNotFound, FlowConfig
    from flow.retriever import Retriever

    sm = SessionManager()
    try:
        name, path = sm._detect_project()
    except SessionError as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)

    try:
        config = FlowConfig.load()
    except ConfigNotFound as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)

    retriever = Retriever(config)
    briefing = retriever.wake(name, path)
    retriever.flow_memory.close()

    click.echo(f"\n⚡ {name}\n")
    click.echo(briefing)


@cli.command()
@click.argument("question")
def ask(question):
    """Ask a question across all your projects."""
    from flow.config import ConfigNotFound, FlowConfig
    from flow.retriever import Retriever

    try:
        config = FlowConfig.load()
    except ConfigNotFound as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)

    retriever = Retriever(config)
    memories = retriever.flow_memory.search_all_projects(question, limit=10)
    answer = retriever.synthesize(question, memories)
    retriever.flow_memory.close()

    click.echo(f"\n🔍 {question}\n")
    click.echo(answer)


DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4.1-mini",
}


@cli.command()
def init():
    """One-time setup: configure LLM provider and API key."""
    config_path = Path.home() / ".config" / "flow" / "config.toml"
    data_dir = Path.home() / ".local" / "share" / "flow"

    if config_path.exists():
        if not click.confirm("⚠ Config already exists. Overwrite?", default=False):
            click.echo("Aborted.")
            return

    # Prompt for provider
    provider = click.prompt(
        "LLM provider",
        type=click.Choice(["anthropic", "openai"], case_sensitive=False),
        default="anthropic",
    )

    # Prompt for API key
    api_key = click.prompt("API key", hide_input=True)
    if not api_key.strip():
        click.echo("✗ API key cannot be empty.", err=True)
        sys.exit(1)

    model = DEFAULT_MODELS[provider]

    # Write config.toml
    config_content = (
        "[llm]\n"
        f'provider = "{provider}"\n'
        f'model    = "{model}"\n'
        f'api_key  = "{api_key.strip()}"\n'
        "\n"
        "[storage]\n"
        f'data_dir = "~/.local/share/flow"\n'
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_content)

    # Create data directory
    data_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"\n✓ Config written to {config_path}")
    click.echo(f"  Provider: {provider}")
    click.echo(f"  Model:    {model}")
    click.echo(f"  Data dir: {data_dir}")

    # Shell integration
    _install_shell_hook()

    # Claude Code reminder
    click.echo(
        "\n💡 If you use Claude Code, add this to ~/.claude/settings.json "
        "to prevent log deletion:\n"
        '   "maxStorageAgeInDays": 999'
    )


SHELL_HOOK_MARKER = "# flow shell integration"
SHELL_HOOK = """\
# flow shell integration
_flow_prompt() {
    if [[ -f .flow.pid ]] && kill -0 $(cat .flow.pid) 2>/dev/null; then
        if [[ "$PROMPT" != *"(flow) "* ]]; then
            PROMPT="(flow) $PROMPT"
        fi
    else
        if [[ "$PROMPT" == *"(flow) "* ]]; then
            PROMPT="${PROMPT//(flow) /}"
        fi
    fi
}
autoload -Uz add-zsh-hook
add-zsh-hook precmd _flow_prompt
"""


def _install_shell_hook():
    """Append the flow prompt hook to ~/.zshrc if not already present."""
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists() and SHELL_HOOK_MARKER in zshrc.read_text():
        click.echo("\n✓ Shell integration already installed")
        return

    with zshrc.open("a") as f:
        f.write("\n" + SHELL_HOOK)

    click.echo("✓ Shell integration added to ~/.zshrc (restart terminal or run: source ~/.zshrc)")


def _format_duration(minutes: int) -> str:
    """Format minutes into a human-readable duration string."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins:02d}m"

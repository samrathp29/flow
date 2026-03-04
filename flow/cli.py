"""Click entrypoint for flow CLI."""

import sys

import click

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


@cli.command()
def stop():
    """End the session, distill it, and store to memory."""
    from flow.collector import Collector
    from flow.config import ConfigNotFound, FlowConfig
    from flow.distiller import Distiller
    from flow.llm import LLMError
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

    click.echo("⠿ Distilling session...")

    collector = Collector()
    data = collector.collect(state)

    duration = _format_duration(data.duration_mins)
    metadata = {
        "session_date": data.started_at[:10],
        "duration_mins": data.duration_mins,
    }

    try:
        distilled = Distiller(config).distill(data)
    except LLMError:
        # LLM already retried once internally — store raw git log as fallback
        distilled = (
            f"Session of {data.duration_mins} minutes. "
            f"LLM distillation failed. Raw git log:\n{data.git_log}"
        )
        click.echo("⚠ LLM distillation failed — saving raw git log as fallback", err=True)

    try:
        mem = FlowMemory(config)
        mem.add(distilled, data.project_name, metadata)
    except Exception:
        # mem0 init or add failed — write distilled text to fallback directory
        from pathlib import Path

        failed_dir = config.data_dir / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime as _dt, timezone as _tz

        ts = _dt.now(_tz.utc).strftime("%Y%m%dT%H%M%S")
        fallback_path = failed_dir / f"{data.project_name}_{ts}.txt"
        fallback_path.write_text(distilled)
        click.echo(f"⚠ Memory storage failed — distilled text saved to {fallback_path}", err=True)

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

    click.echo(f"\n⚡ {name}\n")
    click.echo(briefing)


DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4.1-mini",
}


@cli.command()
def init():
    """One-time setup: configure LLM provider and API key."""
    from pathlib import Path

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

    # Claude Code reminder
    click.echo(
        "\n💡 If you use Claude Code, add this to ~/.claude/settings.json "
        "to prevent log deletion:\n"
        '   "maxStorageAgeInDays": 999'
    )


def _format_duration(minutes: int) -> str:
    """Format minutes into a human-readable duration string."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins:02d}m"

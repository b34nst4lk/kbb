"""CLI adapter for Knowledge Base Builder.

Thin layer that parses CLI arguments and delegates to KBPEngine.
Uses Typer for command definitions and Rich for output formatting.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import Optional

import click
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from kbb.engine import KBPEngine
from kbb.models import KBBConfig, LLMProviderName, QuestionTopic

app = typer.Typer(
    name="kbb",
    help="Knowledge Base Builder — extract and document your knowledge on a schedule.",
    no_args_is_help=True,
)
console = Console()

# Global state for --data-dir option
_state = {"data_dir": None}


@app.callback()
def main(
    data_dir: Path = typer.Option(
        None,
        "--data-dir",
        envvar="KBB_DATA_DIR",
        help="Path to the knowledge base data directory (required).",
    ),
) -> None:
    """Knowledge Base Builder — extract and document your knowledge on a schedule."""
    _state["data_dir"] = data_dir


def _get_engine() -> KBPEngine:
    """Load config and create engine. Requires --data-dir or KBB_DATA_DIR."""
    import os

    data_dir = _state.get("data_dir")
    if not data_dir:
        console.print(
            "[red]Data directory is required. "
            "Use --data-dir /path/to/data or set KBB_DATA_DIR.[/red]"
        )
        raise typer.Exit(1)

    provider_str = os.getenv("KBB_LLM_PROVIDER", "anthropic")
    try:
        provider = LLMProviderName(provider_str)
    except ValueError:
        console.print(
            f"[red]Unknown provider '{provider_str}'. Supported: anthropic, openai, ollama.[/red]"
        )
        raise typer.Exit(1)

    # Default model depends on provider
    default_models = {
        LLMProviderName.ANTHROPIC: "claude-sonnet-4-20250514",
        LLMProviderName.OPENAI: "gpt-4o",
        LLMProviderName.OLLAMA: "llama3",
    }

    config = KBBConfig(
        data_dir=data_dir,
        llm_provider=provider,
        llm_model=os.getenv("KBB_LLM_MODEL", default_models.get(provider, "gpt-4o")),
        llm_api_key=os.getenv(
            "KBB_API_KEY", os.getenv("ANTHROPIC_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        ),
        llm_base_url=os.getenv("KBB_LLM_BASE_URL", ""),
    )
    return KBPEngine(config)


# --- Init command ---


@app.command()
def init() -> None:
    """Initialize a new knowledge base (creates data directory structure)."""
    engine = _get_engine()
    # Engine constructor calls MarkdownStore which creates dirs
    console.print(f"[green]Knowledge base initialized at {engine._config.data_dir}/[/green]")
    console.print("\nNext steps:")
    console.print("  1. Set [bold]KBB_API_KEY[/bold] (or ANTHROPIC_API_KEY / OPENAI_API_KEY)")
    console.print("  2. Run [bold]kbb profile-setup[/bold] to tell the system about yourself")
    console.print("  3. Run [bold]kbb daily-respond[/bold] each day to extract knowledge")
    console.print(
        "\n[dim]To use Ollama: set KBB_LLM_PROVIDER=ollama and KBB_LLM_MODEL=<model>[/dim]"
    )


# --- Profile commands ---


@app.command(name="profile-setup")
def profile_setup() -> None:
    """Set up your user profile (education, work, life experience)."""
    console.print("[bold]Knowledge Base Builder — Profile Setup[/bold]\n")

    # Interactive name prompt
    try:
        name = typer.prompt("Your name", default="", show_default=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(1)
    if not name:
        name = ""

    console.print(
        "\nWrite freely about your education, work experience, life experience, and interests.\n"
    )
    data_dir = _state.get("data_dir", "data")
    console.print(
        f"[dim]This will be saved to {data_dir}/profile.md. You can edit it anytime.[/dim]\n"
    )

    # Pre-fill editor with a structured template including the name
    template_lines = []
    if name:
        template_lines.append(f"# {name}'s Profile\n")
    template_lines.append("# Write about yourself below...")
    template_lines.append("#")
    template_lines.append("# Education:")
    template_lines.append("# Work experience:")
    template_lines.append("# Life experience:")
    template_lines.append("# Interests:")
    template_lines.append("#")
    template_lines.append("# (Delete these prompts and write freely)\n")

    raw_text = click.edit("\n".join(template_lines))
    if not raw_text:
        console.print("[yellow]Cancelled — no changes saved.[/yellow]")
        raise typer.Exit()
    if not raw_text.strip():
        console.print("[yellow]No profile text provided.[/yellow]")
        raise typer.Exit()

    # Strip comment lines for storage, but keep the content
    cleaned = raw_text.strip()

    engine = _get_engine()
    try:
        with console.status("[bold green]Structuring your profile...[/bold green]"):
            profile = asyncio.run(engine.setup_profile_from_text(cleaned))
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(1)

    # If the LLM didn't pick up a name but the user provided one, inject it
    if name and not profile.name:
        profile.name = name
        from kbb.storage.markdown_store import MarkdownStore

        store = MarkdownStore(engine._config.data_dir)
        store.write_structured_profile(profile)

    console.print(Panel(Markdown(engine.get_raw_profile()), title="Profile Saved"))
    console.print(
        f"\n[green]Profile structured and saved: {profile.name or name or 'Unknown'}[/green]"
    )


@app.command(name="profile-show")
def profile_show() -> None:
    """Display your current profile."""
    engine = _get_engine()
    raw = engine.get_raw_profile()
    if raw:
        console.print(Panel(Markdown(raw), title="Your Profile"))
    else:
        console.print("[yellow]No profile found. Run 'kbb profile-setup' first.[/yellow]")


@app.command(name="profile-refresh")
def profile_refresh() -> None:
    """Re-parse your profile after manual edits to profile.md."""
    engine = _get_engine()
    try:
        with console.status("[bold green]Re-parsing your profile...[/bold green]"):
            profile = asyncio.run(engine.refresh_profile())
        console.print(f"[green]Profile re-parsed and updated: {profile.name or 'Unknown'}[/green]")
    except ValueError as e:
        console.print(f"[yellow]{e}[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(1)


# --- Knowledge commands ---


@app.command(name="knowledge-list")
def knowledge_list() -> None:
    """List all knowledge entries."""
    engine = _get_engine()
    entries = engine.get_knowledge_entries()
    if not entries:
        console.print("[yellow]No knowledge entries yet.[/yellow]")
        return
    console.print(f"[bold]Knowledge Entries ({len(entries)})[/bold]\n")
    for e in entries:
        console.print(f"  [{e.topic.value}] {e.title} [dim]({e.source}, {e.created_at})[/dim]")


@app.command(name="knowledge-import")
def knowledge_import(
    file: Path = typer.Argument(..., help="Path to markdown file to import", exists=True),
    topic: QuestionTopic = typer.Option("general", help="Knowledge topic category"),
) -> None:
    """Import a markdown file as a knowledge entry."""
    engine = _get_engine()
    try:
        with console.status("[bold green]Importing knowledge...[/bold green]"):
            entry = asyncio.run(engine.import_knowledge(file, topic))
        console.print(f"[green]Imported: {entry.title} [{entry.topic.value}][/green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(1)


# --- Daily commands ---


@app.command(name="daily-question")
def daily_question() -> None:
    """Generate and display today's question."""
    engine = _get_engine()

    # Check for an existing pending question first
    pending = engine.get_pending_question()
    if pending:
        console.print("[dim]Using previously generated question.[/dim]")
        question = pending
    else:
        try:
            with console.status("[bold green]Generating today's question...[/bold green]"):
                question = asyncio.run(engine.generate_daily_question())
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold]{question.text}[/bold]\n\n"
            f"[dim]Topic: {question.topic.value}\n"
            f"Rationale: {question.rationale}[/dim]",
            title="Today's Question",
        )
    )
    console.print("\n[dim]Run [bold]kbb daily-respond[/bold] to answer this question.[/dim]")


@app.command(name="daily-respond")
def daily_respond() -> None:
    """Generate a question and record your response."""
    engine = _get_engine()

    # Check for an existing pending question first
    pending = engine.get_pending_question()
    if pending:
        console.print("[dim]Using previously generated question.[/dim]")
        question = pending
    else:
        try:
            with console.status("[bold green]Generating today's question...[/bold green]"):
                question = asyncio.run(engine.generate_daily_question())
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold]{question.text}[/bold]\n\n"
            f"[dim]Topic: {question.topic.value} | {question.rationale}[/dim]",
            title="Today's Question",
        )
    )

    # Get response via editor with the question embedded
    editor_content = (
        f"# Question: {question.text}\n"
        f"# (Topic: {question.topic.value} — {question.rationale})\n"
        f"#\n"
        f"# Write your response below. Delete these comment lines if you wish.\n"
        f"\n"
    )
    try:
        response = click.edit(editor_content)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(1)

    if not response:
        console.print("[yellow]Cancelled — no changes saved.[/yellow]")
        console.print(
            "[dim]The question has been saved. Run [bold]kbb daily-respond[/bold] again to answer it.[/dim]"
        )
        return
    if not response.strip():
        console.print("[yellow]No response provided. Skipping.[/yellow]")
        console.print(
            "[dim]The question has been saved. Run [bold]kbb daily-respond[/bold] again to answer it.[/dim]"
        )
        return

    # Strip comment lines from the response before recording
    cleaned_response = "\n".join(
        line for line in response.strip().split("\n") if not line.strip().startswith("#")
    ).strip()

    if not cleaned_response:
        console.print("[yellow]No response content after removing comments. Skipping.[/yellow]")
        console.print(
            "[dim]The question has been saved. Run [bold]kbb daily-respond[/bold] again to answer it.[/dim]"
        )
        return

    # Record the response
    try:
        with console.status("[bold green]Recording your response...[/bold green]"):
            asyncio.run(engine.record_response(question, cleaned_response))
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(1)

    console.print("\n[green]Recorded! Log saved.[/green]")


@app.command(name="daily-log")
def daily_log(
    date_str: Optional[str] = typer.Argument(None, help="Date (YYYY-MM-DD), defaults to today"),
) -> None:
    """View daily log(s) for a given date."""
    engine = _get_engine()
    if date_str:
        d = date.fromisoformat(date_str)
    else:
        d = date.today()

    logs = engine.find_daily_logs_by_date(d)
    if not logs:
        console.print(f"[yellow]No logs found for {d.isoformat()}[/yellow]")
        return
    for log in logs:
        console.print(log.to_markdown())
        console.print()


# --- Status command ---


@app.command()
def status() -> None:
    """Show current knowledge base status."""
    engine = _get_engine()
    profile = engine.get_profile()
    entries = engine.get_knowledge_entries()
    logs = engine.get_all_daily_logs()
    pending = engine.get_pending_question()

    console.print("[bold]Knowledge Base Status[/bold]\n")
    console.print(f"  Data dir: {engine._config.data_dir}")
    console.print(
        f"  Profile: {'Set (' + profile.name + ')' if profile.name else 'Not configured'}"
    )
    console.print(f"  Knowledge entries: {len(entries)}")
    console.print(f"  Daily logs: {len(logs)}")
    if pending:
        console.print(f"\n  [bold]Pending question:[/bold] {pending.text}")
        console.print("  [dim]Run 'kbb daily-respond' to answer it.[/dim]")


if __name__ == "__main__":
    app()

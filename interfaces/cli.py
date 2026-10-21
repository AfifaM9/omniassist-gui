"""DEPRECATED: legacy in-repo terminal interface for OmniAssist GUI.

The browser GUI is the supported interface for this project, and the
standalone OmniAssist project (https://github.com/AfifaM9/omniassist)
already ships the canonical CLI. This module is kept only for backward
compatibility and may be removed in a future release.
"""

import re
import readline  # noqa: F401  # side-effect import; enables arrow-key input history
import sys
import warnings

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from core.agent import OmniAssist

console = Console()

QUIT_PATTERN = re.compile(r'^(exit|quit|q)$', re.IGNORECASE)
SLASH_COMMAND_PATTERN = re.compile(r'^/(\w+)')

def show_help():
    """Display help information for available commands."""
    console.print(Panel.fit(
        "[bold cyan]OmniAssist Commands[/bold cyan]\n"
        "[italic]Type a slash command or chat normally with the agent.[/italic]",
        border_style="cyan"
    ))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Command", style="cyan", width=15)
    table.add_column("Description")

    table.add_row("/help", "Show this help message")
    table.add_row("/memory", "Show long-term memory backend, path, count, and recent notes")
    table.add_row("/tools", "List registered MCP tools")

    console.print(table)
    console.print()


def show_memory(agent):
    """Displays the long-term semantic memory backend, path, and recent notes."""
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", width=16)
    table.add_column("Value")
    table.add_row("Backend", agent.memory.backend)
    table.add_row("Storage", agent.memory.storage_path)
    table.add_row("Documents", str(len(agent.memory)))
    table.add_row("Enabled", "yes" if agent.memory_enabled else "no")
    console.print(table)

    recent = agent.memory.recent(5)
    if recent:
        console.print("[dim]Recent notes:[/dim]")
        for r in recent:
            console.print(f"  [cyan]{r['doc_id']}[/cyan]: {r['text'].splitlines()[0][:100]}")
    console.print()


def show_tools(agent):
    """Lists every tool the MCP registry discovered."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Tool", style="cyan", width=20)
    table.add_column("Description")
    for entry in agent.tool_registry.describe():
        table.add_row(entry["name"], entry["description"] or "-")
    console.print(table)
    for module, error in (agent.tool_registry.load_errors or {}).items():
        console.print(f"[yellow]Skipped {module}: {error}[/yellow]")
    console.print()

def main():
    """Interactive CLI rendering responses cleanly using Rich Markdown panels."""
    warnings.warn(
        "interfaces.cli is deprecated; use the browser GUI (python main.py) or the "
        "standalone OmniAssist CLI instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    console.print(
        "[bold yellow]Deprecated:[/bold yellow] this in-repo terminal CLI will be removed. "
        "Use the browser GUI ([cyan]python main.py[/cyan]) or the standalone OmniAssist CLI."
    )
    console.print(Panel.fit(
        "[bold cyan]OmniAssist[/bold cyan]\n"
        "[italic]Operationalized Multi-Agent Networked Intelligence & "
        "Autonomous System Services Integration Toolkit — the CLI of OmniAssist, "
        "sister agent of OmniAssist GUI (v2026.7 \"Eton Mess\")[/italic]",
        border_style="cyan"
    ))
    console.print("[dim]Type '/help' for commands or 'exit', 'quit', 'q' to terminate session.[/dim]\n")

    try:
        agent = OmniAssist()
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        sys.exit(1)

    if agent.offline:
        console.print(
            "[yellow]Offline mode:[/yellow] no GEMINI_API_KEY found, so replies are "
            "simulated. Set the key in .env to use a real model.\n"
        )

    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
            if not user_input:
                continue
            if QUIT_PATTERN.match(user_input):
                console.print("[yellow]Exiting OmniAssist CLI. Goodbye![/yellow]")
                break

            # Check for slash commands
            slash_match = SLASH_COMMAND_PATTERN.match(user_input)
            if slash_match:
                command = slash_match.group(1).lower()
                if command == "help":
                    show_help()
                    continue
                if command == "memory":
                    show_memory(agent)
                    continue
                if command == "tools":
                    show_tools(agent)
                    continue
                console.print(
                    f"[yellow]Unknown command: /{command}. "
                    "Type '/help' for available commands.[/yellow]\n"
                )
                continue

            response = ""
            for event in agent.run_stream(user_input):
                if event.type == "plan":
                    console.print(f"[dim]{event.content}[/dim]")
                elif event.type == "tool_call":
                    console.print(f"[magenta]=> {event.content}[/magenta]")
                elif event.type == "tool_result":
                    console.print(f"[dim]   <- {event.content[:300]}[/dim]")
                elif event.type in ("final", "error"):
                    response = event.content

            # Restored full Rich Markdown panel rendering for agent outputs
            console.print(Panel(
                Markdown(str(response)),
                title="[bold cyan]OmniAssist[/bold cyan]",
                border_style="blue",
                expand=False
            ))
            console.print()

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session interrupted. Type '/help' for commands or 'exit', 'quit', 'q' to quit properly.[/yellow]")
            continue
        except Exception as cli_err:
            console.print(f"\n[bold red]CLI Trapped Error:[/bold red] {cli_err}\n")
            continue

if __name__ == "__main__":
    main()

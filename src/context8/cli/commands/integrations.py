from __future__ import annotations

import click

from ...config import SUPPORTED_AGENTS
from ..ui import console

AGENT_ALIASES = {
    "claude": "claude-code",
    "desktop": "claude-desktop",
    "code": "vscode",
    "vs-code": "vscode",
    "copilot": "vscode",
}


def _all_choices() -> list[str]:
    return sorted(set(list(SUPPORTED_AGENTS.keys()) + list(AGENT_ALIASES.keys())))


def _resolve(name: str) -> str:
    return AGENT_ALIASES.get(name, name)


@click.command()
@click.argument("agent", type=click.Choice(_all_choices()))
def add(agent: str):
    """Add Context8 to a coding agent's MCP configuration."""
    canonical = _resolve(agent)
    console.print(
        f"\n[bold blue]Context8[/] Adding to {SUPPORTED_AGENTS[canonical]['name']}...\n"
    )

    from ...agents import add_to_agent

    ok, message = add_to_agent(canonical)

    if ok:
        console.print(f"[green]✓[/] {message}")
        agent_name = SUPPORTED_AGENTS[canonical]["name"]
        console.print(f"\n  [dim]Restart {agent_name} to pick up the new MCP server.[/]")
        console.print("  [dim]The agent will now have access to:[/]")
        console.print("    • [cyan]context8_search[/]            — Search past solutions")
        console.print("    • [cyan]context8_log[/]               — Log new solutions")
        console.print("    • [cyan]context8_rate[/]              — Report whether a fix worked")
        console.print("    • [cyan]context8_search_solutions[/]  — Find fixes by approach")
        console.print("    • [cyan]context8_stats[/]             — Knowledge base stats")
    else:
        console.print(f"[red]✗[/] {message}")
        raise SystemExit(1)

    console.print()


@click.command()
@click.argument("agent", type=click.Choice(_all_choices()))
def remove(agent: str):
    """Remove Context8 from a coding agent's MCP configuration."""
    canonical = _resolve(agent)
    console.print(
        f"\n[bold blue]Context8[/] Removing from {SUPPORTED_AGENTS[canonical]['name']}...\n"
    )

    from ...agents import remove_from_agent

    ok, message = remove_from_agent(canonical)

    if ok:
        console.print(f"[green]✓[/] {message}")
    else:
        console.print(f"[red]✗[/] {message}")
        raise SystemExit(1)

    console.print()

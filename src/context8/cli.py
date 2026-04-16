"""Context8 CLI — command-line interface for managing Context8.

Usage:
    context8 start                  Start the Actian VectorAI DB container
    context8 stop                   Stop the database container
    context8 init                   Initialize the collection
    context8 init --seed            Initialize and seed with starter data
    context8 add claude             Add Context8 to Claude Code
    context8 add cursor             Add Context8 to Cursor
    context8 add windsurf           Add Context8 to Windsurf
    context8 remove claude          Remove Context8 from Claude Code
    context8 stats                  Show knowledge base statistics
    context8 doctor                 Check everything is working
    context8 serve                  Start the MCP server (stdio)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import (
    COLLECTION_NAME,
    DB_URL,
    SUPPORTED_AGENTS,
    project_root,
)

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _docker_compose_cmd() -> list[str]:
    """Return the docker compose command (v2 first, v1 fallback)."""
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            check=True,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["docker-compose"]


def _run_docker(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a docker compose command."""
    cmd = _docker_compose_cmd() + args
    root = cwd or project_root()
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True)


def _check_actian_sdk() -> tuple[bool, str]:
    """Check if the actian-vectorai SDK is installed."""
    try:
        import actian_vectorai  # noqa: F401

        return True, "installed"
    except ImportError:
        return False, (
            "not installed — run:\n"
            '    pip install "actian-vectorai @ '
            "https://github.com/hackmamba-io/actian-vectorAI-db-beta/raw/main/"
            'actian_vectorai-0.1.0b2-py3-none-any.whl"'
        )


def _check_db_connection() -> tuple[bool, str]:
    """Check if the Actian VectorAI DB is reachable."""
    try:
        from actian_vectorai import VectorAIClient

        with VectorAIClient(DB_URL, timeout=5.0) as client:
            info = client.health_check()
            return True, f"{info.get('title', 'VectorAI DB')} v{info.get('version', '?')}"
    except ImportError:
        return False, "actian-vectorai SDK not installed"
    except Exception as e:
        return False, str(e)


# ── Main Group ────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(__version__, prog_name="context8")
def main():
    """Context8 — Collective problem-solving memory for coding agents."""
    pass


# ── start ─────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--detach/--no-detach", "-d", default=True, help="Run in background")
def start(detach: bool):
    """Start the Actian VectorAI DB container."""
    console.print("\n[bold blue]Context8[/] Starting database...\n")

    args = ["up"]
    if detach:
        args.append("-d")

    result = _run_docker(args)

    if result.returncode != 0:
        console.print(f"[red]Failed to start:[/]\n{result.stderr}")
        raise SystemExit(1)

    console.print("[green]✓[/] Container started")

    # Wait for DB to be ready
    console.print("  Waiting for database to be ready...", end="")
    import time

    for i in range(30):
        ok, info = _check_db_connection()
        if ok:
            console.print(" [green]ready![/]")
            console.print(f"  Connected to {info}")
            console.print(f"  gRPC endpoint: [cyan]{DB_URL}[/]\n")
            return
        time.sleep(1)
        console.print(".", end="")

    console.print("\n[yellow]⚠ Database not ready after 30s — it may still be starting[/]")
    console.print("  Try: [cyan]context8 doctor[/]\n")


# ── stop ──────────────────────────────────────────────────────────────────────


@main.command()
def stop():
    """Stop the Actian VectorAI DB container."""
    console.print("\n[bold blue]Context8[/] Stopping database...\n")
    result = _run_docker(["down"])

    if result.returncode != 0:
        console.print(f"[red]Failed to stop:[/]\n{result.stderr}")
        raise SystemExit(1)

    console.print("[green]✓[/] Container stopped\n")


# ── init ──────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--seed", is_flag=True, help="Seed with curated starter data")
@click.option("--force", is_flag=True, help="Drop and recreate collection")
def init(seed: bool, force: bool):
    """Initialize the Context8 collection in the database."""
    console.print("\n[bold blue]Context8[/] Initializing...\n")

    # Check DB connection
    ok, info = _check_db_connection()
    if not ok:
        console.print(f"[red]✗ Cannot connect to database:[/] {info}")
        console.print("  Run [cyan]context8 start[/] first\n")
        raise SystemExit(1)

    console.print(f"[green]✓[/] Connected to {info}")

    # Initialize collection
    from .storage import StorageService

    storage = StorageService()

    if force:
        console.print("  Dropping existing collection...")
        storage.drop_collection()

    created = storage.initialize()
    if created:
        console.print(f"[green]✓[/] Collection '{COLLECTION_NAME}' created")
    else:
        console.print(f"[green]✓[/] Collection '{COLLECTION_NAME}' already exists")

    # Seed
    if seed:
        console.print("\n  Seeding with starter data...")
        from .seed import seed_database

        count = seed_database(storage=storage)
        console.print(f"[green]✓[/] Seeded {count} problem-solution records")

    # Stats
    total = storage.count()
    console.print(f"\n  Total records: [bold]{total}[/]")
    storage.close()
    console.print("[green]✓[/] Ready\n")


# ── Agent name resolution ─────────────────────────────────────────────────────

AGENT_ALIASES = {
    "claude": "claude-code",
    "desktop": "claude-desktop",
    "code": "vscode",
    "vs-code": "vscode",
    "copilot": "vscode",
}

ALL_AGENT_CHOICES = sorted(set(list(SUPPORTED_AGENTS.keys()) + list(AGENT_ALIASES.keys())))


def _resolve_agent(name: str) -> str:
    """Resolve agent aliases to canonical names."""
    return AGENT_ALIASES.get(name, name)


# ── add ───────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("agent", type=click.Choice(ALL_AGENT_CHOICES))
def add(agent: str):
    """Add Context8 to a coding agent's MCP configuration.

    \b
    Agents:
      claude / claude-code     Claude Code      (~/.claude/settings.json)
      claude-desktop / desktop Claude Desktop    (claude_desktop_config.json)
      cursor                   Cursor            (~/.cursor/mcp.json)
      vscode / code / copilot  VS Code Copilot   (~/.vscode/mcp.json)
      windsurf                 Windsurf          (~/.windsurf/mcp.json)
      gemini                   Gemini CLI        (~/.gemini/.../mcp_config.json)
    """
    agent = _resolve_agent(agent)
    console.print(f"\n[bold blue]Context8[/] Adding to {SUPPORTED_AGENTS[agent]['name']}...\n")

    from .agents import add_to_agent

    ok, message = add_to_agent(agent)

    if ok:
        console.print(f"[green]✓[/] {message}")

        agent_name = SUPPORTED_AGENTS[agent]["name"]
        console.print(f"\n  [dim]Restart {agent_name} to pick up the new MCP server.[/]")
        console.print("  [dim]The agent will now have access to:[/]")
        console.print("    • [cyan]context8_search[/] — Search past solutions")
        console.print("    • [cyan]context8_log[/]    — Log new solutions")
        console.print("    • [cyan]context8_stats[/]  — Knowledge base stats")
    else:
        console.print(f"[red]✗[/] {message}")
        raise SystemExit(1)

    console.print()


# ── remove ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("agent", type=click.Choice(ALL_AGENT_CHOICES))
def remove(agent: str):
    """Remove Context8 from a coding agent's MCP configuration."""
    agent = _resolve_agent(agent)
    console.print(f"\n[bold blue]Context8[/] Removing from {SUPPORTED_AGENTS[agent]['name']}...\n")

    from .agents import remove_from_agent

    ok, message = remove_from_agent(agent)

    if ok:
        console.print(f"[green]✓[/] {message}")
    else:
        console.print(f"[red]✗[/] {message}")
        raise SystemExit(1)

    console.print()


# ── stats ─────────────────────────────────────────────────────────────────────


@main.command()
def stats():
    """Show Context8 knowledge base statistics."""
    console.print("\n[bold blue]Context8[/] Knowledge Base Stats\n")

    ok, info = _check_db_connection()
    if not ok:
        console.print(f"[red]✗ Cannot connect:[/] {info}")
        console.print("  Run [cyan]context8 start[/] first\n")
        raise SystemExit(1)

    from .storage import StorageService

    storage = StorageService()

    try:
        total = storage.count()
        collection_info = storage.get_collection_info()
    except Exception as e:
        console.print(f"[red]✗ Error:[/] {e}")
        console.print("  Run [cyan]context8 init[/] first\n")
        raise SystemExit(1)

    table = Table(box=box.ROUNDED, title="Context8 Knowledge Base")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Total records", str(total))
    table.add_row("Collection", COLLECTION_NAME)
    table.add_row("Database", info)
    table.add_row("Endpoint", DB_URL)
    table.add_row("Status", "[green]HEALTHY[/]")

    if collection_info:
        table.add_row("Vector spaces", ", ".join(collection_info.get("vectors", [])))
        table.add_row("Status", collection_info.get("status", "unknown"))

    console.print(table)
    console.print()

    storage.close()


# ── doctor ────────────────────────────────────────────────────────────────────


@main.command()
def doctor():
    """Check that everything is set up correctly."""
    console.print("\n[bold blue]Context8[/] Health Check\n")

    checks: list[tuple[str, bool, str]] = []

    # 1. Docker running?
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
        docker_ok = result.returncode == 0
        checks.append(("Docker", docker_ok, "running" if docker_ok else "not running"))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        checks.append(("Docker", False, "not found — install Docker Desktop"))

    # 2. Container running?
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=context8_db", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        container_status = result.stdout.strip()
        container_ok = bool(container_status) and "Up" in container_status
        checks.append(
            (
                "Container (context8_db)",
                container_ok,
                container_status if container_status else "not running — run: context8 start",
            )
        )
    except Exception:
        checks.append(("Container", False, "cannot check"))

    # 3. Actian VectorAI SDK?
    sdk_ok, sdk_info = _check_actian_sdk()
    checks.append(("actian-vectorai SDK", sdk_ok, sdk_info))

    # 4. DB connection?
    db_ok, db_info = _check_db_connection()
    checks.append(("Database connection", db_ok, db_info if db_ok else f"failed — {db_info}"))

    # 5. Collection exists?
    if db_ok:
        try:
            from .storage import StorageService

            storage = StorageService()
            col_exists = storage.collection_exists()
            total = storage.count() if col_exists else 0
            checks.append(
                (
                    "Collection",
                    col_exists,
                    f"'{COLLECTION_NAME}' ({total} records)"
                    if col_exists
                    else "not found — run: context8 init",
                )
            )
            storage.close()
        except Exception as e:
            checks.append(("Collection", False, str(e)))
    else:
        checks.append(("Collection", False, "skipped (no DB connection)"))

    # 6. Embedding models importable?
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401

        checks.append(("sentence-transformers", True, "installed"))
    except ImportError:
        checks.append(
            (
                "sentence-transformers",
                False,
                "not installed — pip install sentence-transformers",
            )
        )

    # 7. MCP SDK importable?
    try:
        import mcp  # noqa: F401

        checks.append(("MCP SDK", True, "installed"))
    except ImportError:
        checks.append(("MCP SDK", False, "not installed — pip install mcp"))

    # 7. Agent configs
    from .agents import list_agents_status

    agent_statuses = list_agents_status()
    configured_agents = [a for a in agent_statuses if a["configured"]]
    if configured_agents:
        names = ", ".join(a["name"] for a in configured_agents)
        checks.append(("Agent integrations", True, names))
    else:
        checks.append(("Agent integrations", False, "none — run: context8 add claude"))

    # Print results
    table = Table(box=box.ROUNDED)
    table.add_column("Check", style="bold")
    table.add_column("Status", width=6)
    table.add_column("Details")

    for name, ok, detail in checks:
        status = "[green]✓[/]" if ok else "[red]✗[/]"
        table.add_row(name, status, detail)

    console.print(table)

    all_ok = all(ok for _, ok, _ in checks)
    if all_ok:
        console.print("\n[green bold]All checks passed![/] Context8 is ready.\n")
    else:
        failed = [name for name, ok, _ in checks if not ok]
        console.print(f"\n[yellow]Some checks failed:[/] {', '.join(failed)}")
        console.print("Fix the issues above, then run [cyan]context8 doctor[/] again.\n")


# ── serve ─────────────────────────────────────────────────────────────────────


@main.command()
def serve():
    """Start the Context8 MCP server (stdio transport).

    This is what agents call. You typically don't run this directly —
    it's started automatically by the agent via the MCP config.
    """
    import asyncio

    from .server import run_server

    asyncio.run(run_server())


# ── search (dev/debug) ────────────────────────────────────────────────────────


@main.command(name="search")
@click.argument("query")
@click.option("--language", "-l", default=None, help="Filter by language")
@click.option("--framework", "-f", default=None, help="Filter by framework")
@click.option("--limit", "-n", default=5, help="Max results")
def search_cmd(query: str, language: str | None, framework: str | None, limit: int):
    """Search Context8 from the command line (for testing)."""
    console.print(f"\n[bold blue]Context8[/] Searching: [italic]{query}[/]\n")

    ok, info = _check_db_connection()
    if not ok:
        console.print(f"[red]✗ Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from .embeddings import EmbeddingService
    from .search import SearchEngine
    from .storage import StorageService

    storage = StorageService()
    embeddings = EmbeddingService()
    engine = SearchEngine(storage, embeddings)

    results = engine.search(
        query=query,
        language=language,
        framework=framework,
        limit=limit,
    )

    if not results:
        console.print("[yellow]No matching solutions found.[/]\n")
        storage.close()
        return

    for i, result in enumerate(results, 1):
        r = result.record
        panel_content = []
        panel_content.append(f"[bold]Problem:[/] {r.problem_text}")
        panel_content.append(f"[bold]Solution:[/] {r.solution_text}")
        if r.code_diff:
            panel_content.append(f"[bold]Diff:[/]\n{r.code_diff}")
        meta_parts = []
        if r.language:
            meta_parts.append(r.language)
        if r.framework:
            meta_parts.append(r.framework)
        if r.tags:
            meta_parts.append(f"tags: {', '.join(r.tags)}")
        if meta_parts:
            panel_content.append(f"[dim]{' · '.join(meta_parts)}[/]")

        console.print(
            Panel(
                "\n".join(panel_content),
                title=f"Result {i} — score: {result.score:.3f} — confidence: {r.confidence:.0%}",
                border_style="green" if result.score > 0.5 else "yellow",
                box=box.ROUNDED,
            )
        )

    storage.close()
    console.print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()

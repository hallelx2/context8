"""Lifecycle commands — start, stop, init.

Backend-aware: the SQLite path has nothing to start (just a file on
disk), so ``start`` / ``stop`` print a friendly note. The Actian path
keeps its Docker-container behaviour. ``init`` runs schema migrations
or creates the collection, downloads embedding models, and optionally
seeds.
"""

from __future__ import annotations

import click

from ...config import BACKEND, COLLECTION_NAME, DB_PATH, DB_URL
from ..ui import check_backend, console


@click.command()
@click.option("--detach/--no-detach", "-d", default=True, help="(Actian only) run in background")
def start(detach: bool):
    """Start the database backend (Actian: Docker container; SQLite: no-op)."""
    if BACKEND == "sqlite":
        console.print("\n[bold blue]Context8[/] [green]No daemon needed.[/]")
        console.print(f"  Using SQLite at [cyan]{DB_PATH}[/]")
        console.print(
            "  Run [cyan]context8 init[/] if you haven't already, then "
            "[cyan]context8 add claude-code[/] to wire up your agent.\n"
        )
        return

    console.print("\n[bold blue]Context8[/] Starting Actian database...\n")

    from ...docker import ensure_running, is_container_running

    if is_container_running():
        console.print("[green]OK[/] Container already running")
        ok, info = check_backend()
        if ok:
            console.print(f"  Connected to {info}")
            console.print(f"  gRPC endpoint: [cyan]{DB_URL}[/]\n")
        return

    console.print("  Starting container...", end="")
    ok, msg = ensure_running(timeout_secs=30)
    if ok:
        console.print(" [green]ready![/]")
        console.print(f"  {msg}")
        console.print(f"  gRPC endpoint: [cyan]{DB_URL}[/]\n")
    else:
        console.print(f"\n[red]X Failed:[/] {msg}")
        console.print("  Is your container runtime (Docker or Podman) running?\n")
        raise SystemExit(1)


@click.command()
def stop():
    """Stop the database backend (no-op for SQLite)."""
    if BACKEND == "sqlite":
        console.print(
            "\n[bold blue]Context8[/] [green]No daemon to stop.[/] "
            f"SQLite is just a file at [cyan]{DB_PATH}[/].\n"
        )
        return

    console.print("\n[bold blue]Context8[/] Stopping Actian database...\n")
    from ...docker import stop_container

    ok, msg = stop_container()
    if ok:
        console.print(f"[green]OK[/] Container {msg}\n")
    else:
        console.print(f"[red]X Failed:[/] {msg}\n")
        raise SystemExit(1)


@click.command()
@click.option("--seed", is_flag=True, help="Seed with curated starter data")
@click.option("--github", is_flag=True, help="Also import from popular GitHub repos")
@click.option("--force", is_flag=True, help="Drop and recreate the database / collection")
def init(seed: bool, github: bool, force: bool):
    """Initialize Context8.

    \b
    For SQLite (default): create ~/.context8/context8.db, run schema
    migrations, download embedding models, optionally seed.

    For Actian: ensure container is running, create the collection,
    download embedding models, optionally seed.
    """
    console.print("\n[bold blue]Context8[/] Initializing...\n")

    # ── Step 1: ensure backend is reachable ─────────────────────────────
    if BACKEND == "actian":
        console.print("  [dim]1/4[/] DB container...", end="")
        try:
            from ...docker import ensure_running

            ok, msg = ensure_running(timeout_secs=30)
            if ok:
                console.print(f" [green]OK[/] {msg}")
            else:
                console.print(f" [red]X[/] {msg}")
                console.print(
                    "  Is your container runtime (Docker or Podman) running?\n"
                )
                raise SystemExit(1)
        except ImportError:
            console.print(" [yellow]skipped[/] (check Docker manually)")
    else:
        console.print(f"  [dim]1/4[/] SQLite path... [green]OK[/] {DB_PATH}")

    # ── Step 2: ensure schema / collection ──────────────────────────────
    console.print("  [dim]2/4[/] Schema...", end="")
    from ...storage import StorageService

    storage = StorageService()
    if force:
        storage.drop_collection()
    created = storage.initialize()

    if BACKEND == "sqlite":
        if created:
            console.print(" [green]OK[/] tables created")
        else:
            console.print(" [green]OK[/] tables exist")
    else:
        if created:
            console.print(f" [green]OK[/] '{COLLECTION_NAME}' created")
        else:
            console.print(f" [green]OK[/] '{COLLECTION_NAME}' exists")

    # ── Step 3: download embedding model ────────────────────────────────
    console.print("  [dim]3/4[/] Embedding model...", end="")
    try:
        from ...embeddings import EmbeddingService

        EmbeddingService.ensure_models_downloaded()
        console.print(" [green]OK[/] ready")
    except Exception as exc:
        console.print(f" [yellow]![/] {exc}")

    # ── Step 4: seed ────────────────────────────────────────────────────
    if seed or github:
        console.print("  [dim]4/4[/] Seeding...", end="")
        from ...ingest import seed_database

        count = seed_database(storage=storage, include_github=github)
        console.print(f" [green]OK[/] {count} records")
        if github:
            console.print("        [dim](includes GitHub issues)[/]")
    else:
        console.print("  [dim]4/4[/] Seed: skipped (use --seed)")

    total = storage.count()
    console.print(f"\n  Total records: [bold]{total}[/]")
    storage.close()
    console.print("[green]OK[/] Context8 is ready\n")

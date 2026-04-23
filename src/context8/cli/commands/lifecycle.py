from __future__ import annotations

import click

from ...config import COLLECTION_NAME, DB_URL
from ..ui import check_db_connection, console


@click.command()
@click.option("--detach/--no-detach", "-d", default=True, help="Run in background")
def start(detach: bool):
    """Start the Actian VectorAI DB container."""
    console.print("\n[bold blue]Context8[/] Starting database...\n")

    from ...docker import ensure_running, is_container_running

    if is_container_running():
        console.print("[green]✓[/] Container already running")
        ok, info = check_db_connection()
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
        console.print(f"\n[red]✗ Failed:[/] {msg}")
        console.print("  Is Docker Desktop running?\n")
        raise SystemExit(1)


@click.command()
def stop():
    """Stop the Actian VectorAI DB container."""
    console.print("\n[bold blue]Context8[/] Stopping database...\n")

    from ...docker import stop_container

    ok, msg = stop_container()
    if ok:
        console.print(f"[green]✓[/] Container {msg}\n")
    else:
        console.print(f"[red]✗ Failed:[/] {msg}\n")
        raise SystemExit(1)


@click.command()
@click.option("--seed", is_flag=True, help="Seed with curated starter data")
@click.option("--github", is_flag=True, help="Also import from popular GitHub repos")
@click.option("--force", is_flag=True, help="Drop and recreate collection")
def init(seed: bool, github: bool, force: bool):
    """Initialize Context8 — start DB, create collection, download models, seed.

    This is the one-stop setup command. It:
    1. Starts Docker container if not running
    2. Creates the Actian VectorAI DB collection
    3. Downloads the embedding model (~80MB, cached after first run)
    4. Seeds with starter data (if --seed)
    5. Imports from GitHub repos (if --github)
    """
    console.print("\n[bold blue]Context8[/] Initializing...\n")

    # Step 1: Ensure Docker is running
    console.print("  [dim]1/4[/] Docker container...", end="")
    try:
        from ...docker import ensure_running

        ok, msg = ensure_running(timeout_secs=30)
        if ok:
            console.print(f" [green]✓[/] {msg}")
        else:
            console.print(f" [red]✗[/] {msg}")
            console.print("  Is Docker Desktop running?\n")
            raise SystemExit(1)
    except ImportError:
        console.print(" [yellow]skipped[/] (check Docker manually)")

    # Step 2: Create collection
    console.print("  [dim]2/4[/] Collection...", end="")
    from ...storage import StorageService

    storage = StorageService()

    if force:
        storage.drop_collection()

    created = storage.initialize()
    if created:
        console.print(f" [green]✓[/] '{COLLECTION_NAME}' created")
    else:
        console.print(f" [green]✓[/] '{COLLECTION_NAME}' exists")

    # Step 3: Download embedding model
    console.print("  [dim]3/4[/] Embedding model...", end="")
    try:
        from ...embeddings import EmbeddingService

        EmbeddingService.ensure_models_downloaded()
        console.print(" [green]✓[/] ready")
    except Exception as e:
        console.print(f" [yellow]⚠[/] {e}")

    # Step 4: Seed
    if seed or github:
        console.print("  [dim]4/4[/] Seeding...", end="")
        from ...ingest import seed_database

        count = seed_database(storage=storage, include_github=github)
        console.print(f" [green]✓[/] {count} records")
        if github:
            console.print("        [dim](includes GitHub issues)[/]")
    else:
        console.print("  [dim]4/4[/] Seed: skipped (use --seed)")

    total = storage.count()
    console.print(f"\n  Total records: [bold]{total}[/]")
    storage.close()
    console.print("[green]✓[/] Context8 is ready\n")

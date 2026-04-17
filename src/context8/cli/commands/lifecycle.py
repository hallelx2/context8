from __future__ import annotations

import time

import click

from ...config import COLLECTION_NAME, DB_URL
from ..ui import check_db_connection, console, run_docker


@click.command()
@click.option("--detach/--no-detach", "-d", default=True, help="Run in background")
def start(detach: bool):
    """Start the Actian VectorAI DB container."""
    console.print("\n[bold blue]Context8[/] Starting database...\n")

    args = ["up"]
    if detach:
        args.append("-d")

    result = run_docker(args)
    if result.returncode != 0:
        console.print(f"[red]Failed to start:[/]\n{result.stderr}")
        raise SystemExit(1)

    console.print("[green]✓[/] Container started")
    console.print("  Waiting for database to be ready...", end="")

    for _ in range(30):
        ok, info = check_db_connection()
        if ok:
            console.print(" [green]ready![/]")
            console.print(f"  Connected to {info}")
            console.print(f"  gRPC endpoint: [cyan]{DB_URL}[/]\n")
            return
        time.sleep(1)
        console.print(".", end="")

    console.print("\n[yellow]⚠ Database not ready after 30s — it may still be starting[/]")
    console.print("  Try: [cyan]context8 doctor[/]\n")


@click.command()
def stop():
    """Stop the Actian VectorAI DB container."""
    console.print("\n[bold blue]Context8[/] Stopping database...\n")
    result = run_docker(["down"])

    if result.returncode != 0:
        console.print(f"[red]Failed to stop:[/]\n{result.stderr}")
        raise SystemExit(1)

    console.print("[green]✓[/] Container stopped\n")


@click.command()
@click.option("--seed", is_flag=True, help="Seed with curated starter data")
@click.option("--force", is_flag=True, help="Drop and recreate collection")
def init(seed: bool, force: bool):
    """Initialize the Context8 collection in the database."""
    console.print("\n[bold blue]Context8[/] Initializing...\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]✗ Cannot connect to database:[/] {info}")
        console.print("  Run [cyan]context8 start[/] first\n")
        raise SystemExit(1)

    console.print(f"[green]✓[/] Connected to {info}")

    from ...storage import StorageService

    storage = StorageService()

    if force:
        console.print("  Dropping existing collection...")
        storage.drop_collection()

    created = storage.initialize()
    if created:
        console.print(f"[green]✓[/] Collection '{COLLECTION_NAME}' created")
    else:
        console.print(f"[green]✓[/] Collection '{COLLECTION_NAME}' already exists")

    if seed:
        console.print("\n  Seeding with starter data...")
        from ...ingest import seed_database

        count = seed_database(storage=storage)
        console.print(f"[green]✓[/] Seeded {count} problem-solution records")

    total = storage.count()
    console.print(f"\n  Total records: [bold]{total}[/]")
    storage.close()
    console.print("[green]✓[/] Ready\n")

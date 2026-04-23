from __future__ import annotations

import click
from rich import box
from rich.table import Table

from ..ui import check_db_connection, console


@click.command(name="import-github")
@click.argument("repo")
@click.option(
    "--label",
    "labels",
    multiple=True,
    help="Filter issues by label (repeat for multiple)",
)
@click.option(
    "--max-issues",
    default=30,
    show_default=True,
    help="Maximum number of issues to import",
)
@click.option(
    "--state",
    type=click.Choice(["closed", "open", "all"]),
    default="closed",
    show_default=True,
    help="Issue state to fetch",
)
@click.option(
    "--require-resolution/--allow-unresolved",
    default=True,
    show_default=True,
    help="Skip issues that don't have a resolution-style comment",
)
def import_github(
    repo: str,
    labels: tuple[str, ...],
    max_issues: int,
    state: str,
    require_resolution: bool,
):
    """Import closed GitHub issues from REPO (owner/name) into Context8.

    Example:

        context8 import-github vercel/next.js --label bug --max-issues 50
    """
    console.print(f"\n[bold blue]Context8[/] Importing from [cyan]{repo}[/]\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...embeddings import EmbeddingService
    from ...ingest import GitHubIssueImporter, IngestPipeline
    from ...storage import StorageService

    importer = GitHubIssueImporter()
    storage = StorageService()
    storage.initialize()
    embeddings = EmbeddingService()
    pipeline = IngestPipeline(storage, embeddings)

    with console.status(f"[cyan]Fetching issues from {repo}..."):
        try:
            fetched = importer.fetch(
                repo=repo,
                labels=list(labels) if labels else None,
                max_issues=max_issues,
                state=state,
            )
        except Exception as e:
            console.print(f"[red]X Fetch failed:[/] {e}\n")
            storage.close()
            raise SystemExit(1) from e

    console.print(f"[green]OK[/] Fetched [bold]{len(fetched.issues)}[/] issue(s)")

    records = importer.to_records(repo, fetched, require_resolution=require_resolution)
    console.print(
        f"[green]OK[/] Extracted [bold]{len(records)}[/] resolution record(s)"
        f" (skipped {len(fetched.issues) - len(records)} without a fix)"
    )

    if not records:
        console.print(
            "\n[yellow]No records to import.[/] "
            "Try --allow-unresolved or different --label filters.\n"
        )
        storage.close()
        return

    with console.status("[cyan]Embedding and storing..."):
        stats = pipeline.ingest(records, skip_existing=True)

    table = Table(box=box.ROUNDED, title=f"Ingest results for {repo}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold", justify="right")
    table.add_row("Attempted", str(stats.attempted))
    table.add_row("Stored (new)", f"[green]{stats.stored}[/]")
    table.add_row("Skipped (already present)", str(stats.duplicates))
    table.add_row("Failed", f"[red]{stats.failed}[/]" if stats.failed else "0")

    console.print(table)
    console.print(f"\n  Total records in DB now: [bold]{storage.count()}[/]\n")
    storage.close()


@click.command()
@click.argument("directory", type=click.Path(exists=True))
@click.option("--max-files", default=100, show_default=True, help="Max session files to scan")
def mine(directory: str, max_files: int):
    """Mine problem-solution pairs from agent session transcripts.

    Parses Claude Code (~/.claude/sessions/) or Cursor conversation
    files to find error→fix patterns and imports them into Context8.

    \b
    Examples:
        context8 mine ~/.claude/sessions/
        context8 mine ~/.cursor/conversations/
    """
    from pathlib import Path

    dir_path = Path(directory)
    console.print(f"\n[bold blue]Context8[/] Mining sessions from [cyan]{dir_path}[/]\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...embeddings import EmbeddingService
    from ...ingest import IngestPipeline
    from ...ingest.sessions import mine_directory
    from ...storage import StorageService

    with console.status("[cyan]Scanning session files..."):
        records = mine_directory(dir_path, max_files=max_files)

    if not records:
        console.print("[yellow]No problem-solution pairs found.[/]\n")
        return

    console.print(f"[green]OK[/] Found [bold]{len(records)}[/] problem-solution pairs")

    storage = StorageService()
    storage.initialize()
    embeddings = EmbeddingService()
    pipeline = IngestPipeline(storage, embeddings)

    with console.status("[cyan]Embedding and storing..."):
        stats = pipeline.ingest(records, skip_existing=True)

    table = Table(box=box.ROUNDED, title="Session mining results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold", justify="right")
    table.add_row("Files scanned", str(max_files))
    table.add_row("Pairs extracted", str(stats.attempted))
    table.add_row("Stored (new)", f"[green]{stats.stored}[/]")
    table.add_row("Duplicates", str(stats.duplicates))
    table.add_row("Failed", f"[red]{stats.failed}[/]" if stats.failed else "0")

    console.print(table)
    console.print(f"\n  Total records in DB now: [bold]{storage.count()}[/]\n")
    storage.close()

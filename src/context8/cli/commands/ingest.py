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
        console.print(f"[red]✗ Cannot connect:[/] {info}\n")
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
            console.print(f"[red]✗ Fetch failed:[/] {e}\n")
            storage.close()
            raise SystemExit(1) from e

    console.print(f"[green]✓[/] Fetched [bold]{len(fetched.issues)}[/] issue(s)")

    records = importer.to_records(repo, fetched, require_resolution=require_resolution)
    console.print(
        f"[green]✓[/] Extracted [bold]{len(records)}[/] resolution record(s)"
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

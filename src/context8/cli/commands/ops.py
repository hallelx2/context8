from __future__ import annotations

import subprocess

import click
from rich import box
from rich.panel import Panel
from rich.table import Table

from ...config import COLLECTION_NAME, DB_URL
from ..ui import check_actian_sdk, check_db_connection, console


@click.command()
def stats():
    """Show Context8 knowledge base statistics."""
    console.print("\n[bold blue]Context8[/] Knowledge Base Stats\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}")
        console.print("  Run [cyan]context8 start[/] first\n")
        raise SystemExit(1)

    from ...storage import StorageService

    storage = StorageService()

    try:
        total = storage.count()
        collection_info = storage.get_collection_info()
    except Exception as e:
        console.print(f"[red]X Error:[/] {e}")
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


@click.command()
def doctor():
    """Check that everything is set up correctly."""
    console.print("\n[bold blue]Context8[/] Health Check\n")

    checks: list[tuple[str, bool, str]] = []

    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
        docker_ok = result.returncode == 0
        checks.append(("Docker", docker_ok, "running" if docker_ok else "not running"))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        checks.append(("Docker", False, "not found — install Docker Desktop"))

    try:
        from ...docker import is_container_running

        container_ok = is_container_running()
        checks.append(
            (
                "Container (context8_db)",
                container_ok,
                "running" if container_ok else "not running — run: context8 start",
            )
        )
    except Exception:
        checks.append(("Container", False, "cannot check"))

    sdk_ok, sdk_info = check_actian_sdk()
    checks.append(("actian-vectorai SDK", sdk_ok, sdk_info))

    db_ok, db_info = check_db_connection()
    checks.append(("Database connection", db_ok, db_info if db_ok else f"failed — {db_info}"))

    if db_ok:
        try:
            from ...storage import StorageService

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

            if col_exists:
                col_info = storage.get_collection_info() or {}
                named_count = col_info.get("named_vector_count", 0)
                sparse_vecs = col_info.get("sparse_vectors", [])
                hybrid = col_info.get("hybrid_enabled", False)

                checks.append(
                    (
                        "Named vectors (≥3)",
                        named_count >= 3,
                        f"{named_count} found: {', '.join(col_info.get('vectors', []))}"
                        if named_count
                        else "not detected — collection fell back to single-vector mode",
                    )
                )
                checks.append(
                    (
                        "Sparse vectors",
                        bool(sparse_vecs),
                        f"enabled: {', '.join(sparse_vecs)}"
                        if sparse_vecs
                        else "disabled — hybrid fusion will degrade to dense-only",
                    )
                )
                checks.append(
                    (
                        "Hybrid fusion ready",
                        hybrid,
                        "dense + sparse + RRF fusion available"
                        if hybrid
                        else "missing components — see above",
                    )
                )

                try:
                    import actian_vectorai as _av

                    _filter = _av.FilterBuilder().must(_av.Field("language").eq("python")).build()
                    _zero = [0.0] * 384
                    storage.client.points.search(
                        COLLECTION_NAME,
                        vector=_zero,
                        using="problem",
                        filter=_filter,
                        limit=1,
                        with_payload=False,
                    )
                    checks.append(("Filtered search", True, "FilterBuilder query succeeded"))
                except Exception as e:
                    checks.append(("Filtered search", False, f"failed — {e}"))

            storage.close()
        except Exception as e:
            checks.append(("Collection", False, str(e)))
    else:
        checks.append(("Collection", False, "skipped (no DB connection)"))

    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401

        checks.append(("sentence-transformers", True, "installed"))
    except ImportError:
        checks.append(
            ("sentence-transformers", False, "not installed — pip install sentence-transformers")
        )

    try:
        import mcp  # noqa: F401

        checks.append(("MCP SDK", True, "installed"))
    except ImportError:
        checks.append(("MCP SDK", False, "not installed — pip install mcp"))

    from ...agents import list_agents_status

    agent_statuses = list_agents_status()
    configured_agents = [a for a in agent_statuses if a["configured"]]
    if configured_agents:
        names = ", ".join(a["name"] for a in configured_agents)
        checks.append(("Agent integrations", True, names))
    else:
        checks.append(("Agent integrations", False, "none — run: context8 add claude"))

    table = Table(box=box.ROUNDED)
    table.add_column("Check", style="bold")
    table.add_column("Status", width=6)
    table.add_column("Details")

    for name, ok, detail in checks:
        status = "[green]OK[/]" if ok else "[red]X[/]"
        table.add_row(name, status, detail)

    console.print(table)

    all_ok = all(ok for _, ok, _ in checks)
    if all_ok:
        console.print("\n[green bold]All checks passed![/] Context8 is ready.\n")
    else:
        failed = [name for name, ok, _ in checks if not ok]
        console.print(f"\n[yellow]Some checks failed:[/] {', '.join(failed)}")
        console.print("Fix the issues above, then run [cyan]context8 doctor[/] again.\n")


@click.command(name="search")
@click.argument("query")
@click.option("--language", "-l", default=None, help="Filter by language")
@click.option("--framework", "-f", default=None, help="Filter by framework")
@click.option("--limit", "-n", default=5, help="Max results")
@click.option("--explain/--no-explain", default=True, help="Show per-strategy attribution")
def search_cmd(query: str, language: str | None, framework: str | None, limit: int, explain: bool):
    """Search Context8 from the command line."""
    console.print(f"\n[bold blue]Context8[/] Searching: [italic]{query}[/]\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...embeddings import EmbeddingService
    from ...search import SearchEngine
    from ...storage import StorageService

    storage = StorageService()
    embeddings = EmbeddingService()
    engine = SearchEngine(storage, embeddings)

    results = engine.search(query=query, language=language, framework=framework, limit=limit)

    if not results:
        console.print("[yellow]No matching solutions found.[/]\n")
        storage.close()
        return

    for i, result in enumerate(results, 1):
        r = result.record
        panel_lines = [
            f"[bold]Problem:[/] {r.problem_text}",
            f"[bold]Solution:[/] {r.solution_text}",
        ]
        if r.code_diff:
            panel_lines.append(f"[bold]Diff:[/]\n{r.code_diff}")

        meta_parts = []
        if r.language:
            meta_parts.append(r.language)
        if r.framework:
            meta_parts.append(r.framework)
        if r.tags:
            meta_parts.append(f"tags: {', '.join(r.tags)}")
        if meta_parts:
            panel_lines.append(f"[dim]{' · '.join(meta_parts)}[/]")

        if explain:
            attr = result.attribution
            if attr.contributions:
                strat_bits = []
                for c in sorted(attr.contributions, key=lambda x: x.rank):
                    strat_bits.append(f"[cyan]{c.strategy}[/]@[bold]{c.rank}[/]({c.score:.2f})")
                panel_lines.append(f"[dim]via:[/] {' + '.join(strat_bits)}")

            if result.boost_factors:
                boost_bits = []
                for name, value in result.boost_factors.items():
                    color = "green" if value >= 0.95 else ("yellow" if value >= 0.85 else "red")
                    boost_bits.append(f"[{color}]{name} {value:.2f}[/]")
                panel_lines.append(f"[dim]boosts:[/] {'  '.join(boost_bits)}")

            fb = r.feedback
            if fb.applied_count > 0:
                panel_lines.append(
                    f"[dim]feedback:[/] {fb.worked_count}/{fb.applied_count} worked "
                    f"([bold]{fb.worked_ratio:.0%}[/])"
                )

        title = (
            f"Result {i} — score: {result.score:.3f} "
            f"(raw: {result.raw_score:.3f}) "
            f"— confidence: {r.confidence:.0%}"
        )
        border = "green" if result.score > 0.5 else "yellow"
        console.print(
            Panel(
                "\n".join(panel_lines),
                title=title,
                border_style=border,
                box=box.ROUNDED,
            )
        )

    storage.close()
    console.print()


@click.command()
@click.option("--tag", "-t", default=None, help="Filter by tag")
@click.option("--language", "-l", default=None, help="Filter by language")
@click.option("--framework", "-f", default=None, help="Filter by framework")
@click.option("--error-type", "-e", default=None, help="Filter by error type")
@click.option("--source", "-s", default=None, help="Filter by source (seed, github, session_mine)")
@click.option("--limit", "-n", default=20, help="Max results")
def browse(
    tag: str | None,
    language: str | None,
    framework: str | None,
    error_type: str | None,
    source: str | None,
    limit: int,
):
    """Browse records by metadata — no search query needed.

    \b
    Examples:
        context8 browse --tag docker
        context8 browse --language python --error-type ImportError
        context8 browse --source github
    """
    filters = []
    if tag:
        filters.append(f"tag={tag}")
    if language:
        filters.append(f"lang={language}")
    if framework:
        filters.append(f"fw={framework}")
    if error_type:
        filters.append(f"err={error_type}")
    if source:
        filters.append(f"source={source}")

    label = ", ".join(filters) if filters else "all records"
    console.print(f"\n[bold blue]Context8[/] Browsing: [italic]{label}[/]\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...browse import browse as do_browse
    from ...storage import StorageService

    storage = StorageService()
    records = do_browse(
        storage,
        tag=tag,
        language=language,
        framework=framework,
        error_type=error_type,
        source=source,
        limit=limit,
    )

    if not records:
        console.print("[yellow]No matching records found.[/]\n")
        storage.close()
        return

    table = Table(box=box.ROUNDED, title=f"Records ({len(records)})")
    table.add_column("#", width=3)
    table.add_column("Error Type", style="red", max_width=20)
    table.add_column("Problem", max_width=50)
    table.add_column("Lang", width=8)
    table.add_column("Tags", max_width=25)
    table.add_column("Source", width=10)

    for i, r in enumerate(records, 1):
        table.add_row(
            str(i),
            r.error_type or "-",
            r.problem_text[:50] + "..." if len(r.problem_text) > 50 else r.problem_text,
            r.language or "-",
            ", ".join(r.tags[:3]) if r.tags else "-",
            r.source or "-",
        )

    console.print(table)
    console.print()
    storage.close()


@click.command(name="export")
@click.option("--output", "-o", default="context8-export.json", help="Output file path")
def export_cmd(output: str):
    """Export the Context8 knowledge base to a JSON file."""
    from pathlib import Path

    console.print(f"\n[bold blue]Context8[/] Exporting to [cyan]{output}[/]\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...export import export_json
    from ...storage import StorageService

    storage = StorageService()
    count = export_json(storage, Path(output))
    storage.close()

    console.print(f"[green]OK[/] Exported [bold]{count}[/] records to {output}\n")


@click.command(name="import")
@click.argument("file", type=click.Path(exists=True))
def import_cmd(file: str):
    """Import records from a Context8 JSON export file."""
    from pathlib import Path

    console.print(f"\n[bold blue]Context8[/] Importing from [cyan]{file}[/]\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...embeddings import EmbeddingService
    from ...export import import_json
    from ...storage import StorageService

    storage = StorageService()
    storage.initialize()
    embeddings = EmbeddingService()

    count = import_json(storage, embeddings, Path(file))
    total = storage.count()
    storage.close()

    console.print(f"[green]OK[/] Imported [bold]{count}[/] new records")
    console.print(f"  Total records now: [bold]{total}[/]\n")

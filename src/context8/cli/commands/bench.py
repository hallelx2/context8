from __future__ import annotations

import click
from rich import box
from rich.panel import Panel
from rich.table import Table

from ..ui import check_db_connection, console


@click.command()
@click.option(
    "--show-misses",
    is_flag=True,
    help="Print queries that didn't return the expected record in the top 5",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Write results as markdown to a file (e.g. RESULTS.md)",
)
def bench(show_misses: bool, output: str | None):
    """Run the ground-truth retrieval benchmark and print the comparison table."""
    console.print("\n[bold blue]Context8[/] Retrieval Benchmark\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...benchmark import GROUND_TRUTH, run_benchmark
    from ...storage import StorageService

    storage = StorageService()
    total = storage.count()
    if total == 0:
        console.print("[red]X Empty collection.[/] Run [cyan]context8 init --seed[/] first.\n")
        raise SystemExit(1)

    console.print(f"  Records in DB:    [bold]{total}[/]")
    console.print(f"  Ground-truth queries: [bold]{len(GROUND_TRUTH)}[/]\n")

    with console.status("[cyan]Running benchmark across configurations..."):
        results = run_benchmark(storage=storage)

    baseline = results[0]
    table = Table(box=box.ROUNDED, title="Per-feature contribution to retrieval quality")
    table.add_column("Configuration", style="cyan", no_wrap=True)
    table.add_column("Recall@1", justify="right")
    table.add_column("Recall@3", justify="right")
    table.add_column("Recall@5", justify="right")
    table.add_column("MRR", justify="right")
    table.add_column("p50 latency", justify="right", style="dim")

    def _delta(value: float, base: float) -> str:
        if base == 0:
            return f"{value:.0%}"
        diff = value - base
        if abs(diff) < 1e-9:
            return f"{value:.0%}"
        sign = "+" if diff > 0 else ""
        color = "green" if diff > 0 else "red"
        return f"{value:.0%} [{color}]({sign}{diff:.0%})[/]"

    for r in results:
        if r is baseline:
            table.add_row(
                r.config.name,
                f"{r.recall_at_1:.0%}",
                f"{r.recall_at_3:.0%}",
                f"{r.recall_at_5:.0%}",
                f"{r.mrr:.2f}",
                f"{r.median_latency_ms:.0f} ms",
            )
        else:
            table.add_row(
                r.config.name,
                _delta(r.recall_at_1, baseline.recall_at_1),
                _delta(r.recall_at_3, baseline.recall_at_3),
                _delta(r.recall_at_5, baseline.recall_at_5),
                f"{r.mrr:.2f}",
                f"{r.median_latency_ms:.0f} ms",
            )

    console.print(table)

    final = results[-1]
    delta = final.recall_at_3 - baseline.recall_at_3
    console.print(
        f"\n  [bold]Hybrid + filter + ranker (full pipeline):[/] "
        f"Recall@3 lifted from [yellow]{baseline.recall_at_3:.0%}[/] "
        f"to [green]{final.recall_at_3:.0%}[/] "
        f"([bold green]+{delta:.0%}[/] absolute).\n"
    )

    if show_misses and final.misses:
        console.print(f"[yellow]Top configuration missed {len(final.misses)} query(ies):[/]")
        for m in final.misses:
            console.print(f"  [dim]→[/] [italic]{m.query}[/] (expected: {m.expected_slug})")
        console.print()

    if output:
        from pathlib import Path

        from ...benchmark.runner import results_to_markdown

        md = results_to_markdown(results)
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"  [green]OK[/] Results written to [cyan]{output}[/]\n")

    storage.close()


@click.command()
def demo():
    """Run three scripted demos that show the hybrid retrieval stack at work."""
    console.print("\n[bold blue]Context8[/] Live Demo\n")

    ok, info = check_db_connection()
    if not ok:
        console.print(f"[red]X Cannot connect:[/] {info}\n")
        raise SystemExit(1)

    from ...embeddings import EmbeddingService
    from ...search import SearchEngine
    from ...storage import StorageService

    storage = StorageService()
    if storage.count() == 0:
        console.print("[red]X Empty collection.[/] Run [cyan]context8 init --seed[/] first.\n")
        raise SystemExit(1)

    embeddings = EmbeddingService()
    engine = SearchEngine(storage, embeddings)
    embeddings.warmup()

    def _show_top(results, title: str, color: str = "green"):
        if not results:
            console.print(Panel("(no results)", title=title, border_style="red"))
            return
        lines = []
        for i, r in enumerate(results[:3], 1):
            lines.append(
                f"[bold]#{i}[/] [{color}]{r.score:.3f}[/] "
                f"[dim]({r.match_type})[/] {r.record.problem_text[:80]}"
            )
        console.print(Panel("\n".join(lines), title=title, border_style=color))

    console.print(
        "\n[bold]Scenario 1.[/] [italic]Named vectors —[/] "
        "the same record found via three different vector spaces.\n"
    )
    by_problem = engine.search(
        "asyncio.run cannot be called from a running event loop in Jupyter",
        use_problem_vector=True,
        use_code_vector=False,
        use_sparse=False,
        use_filter=False,
        apply_quality_boost=False,
        limit=3,
    )
    _show_top(by_problem, "[1a] via 'problem' vector — error text query", "cyan")

    by_code = engine.search(
        "loop = asyncio.get_event_loop(); loop.run_until_complete(main())",
        use_problem_vector=False,
        use_code_vector=True,
        use_sparse=False,
        use_filter=False,
        apply_quality_boost=False,
        limit=3,
    )
    _show_top(by_code, "[1b] via 'code_context' vector — code-pattern query", "magenta")

    by_solution = engine.search_by_solution(
        "use nest_asyncio to allow nested event loops",
        limit=3,
        apply_quality_boost=False,
    )
    _show_top(by_solution, "[1c] via 'solution' vector — approach query", "yellow")

    console.print("  [dim]→ Same record reachable from three independent semantic spaces.[/]\n")

    console.print(
        "\n[bold]Scenario 2.[/] [italic]Hybrid fusion —[/] "
        "sparse keyword vectors save dense search on exact error codes.\n"
    )
    console.print("  Query: [yellow]'ERESOLVE unable to resolve dependency tree'[/]\n")

    dense_only = engine.search(
        "ERESOLVE unable to resolve dependency tree",
        use_problem_vector=True,
        use_code_vector=False,
        use_sparse=False,
        use_filter=False,
        apply_quality_boost=False,
        limit=5,
    )
    _show_top(dense_only, "[2a] dense-only", "red")

    hybrid = engine.search(
        "ERESOLVE unable to resolve dependency tree",
        use_problem_vector=True,
        use_code_vector=True,
        use_sparse=True,
        use_filter=False,
        apply_quality_boost=False,
        limit=5,
    )
    _show_top(hybrid, "[2b] dense + sparse fusion (RRF)", "green")

    console.print(
        "  [dim]→ Sparse vectors catch exact tokens that dense embeddings normalize away.[/]\n"
    )

    console.print(
        "\n[bold]Scenario 3.[/] [italic]Filtered search —[/] "
        "metadata filters change the result set instantly, server-side.\n"
    )
    console.print("  Same query: [yellow]'out of memory error during build'[/]\n")

    py_only = engine.search(
        "out of memory error during build",
        language="python",
        use_filter=True,
        apply_quality_boost=False,
        limit=3,
    )
    _show_top(py_only, "[3a] filter: language=python", "blue")

    js_only = engine.search(
        "out of memory error during build",
        language="javascript",
        use_filter=True,
        apply_quality_boost=False,
        limit=3,
    )
    _show_top(js_only, "[3b] filter: language=javascript", "magenta")

    console.print(
        "  [dim]→ Metadata filters (SQL WHERE on SQLite, FilterBuilder on Actian) "
        "swap the result set without re-embedding.[/]\n"
    )

    console.print(
        "\n[bold]Scenario 4.[/] [italic]Quality ranker —[/] "
        "confidence + recency + worked-ratio re-rank for production use.\n"
    )
    raw = engine.search(
        "Cannot read properties of undefined map React",
        apply_quality_boost=False,
        limit=3,
    )
    boosted = engine.search(
        "Cannot read properties of undefined map React",
        apply_quality_boost=True,
        limit=3,
    )
    _show_top(raw, "[4a] raw retrieval score only", "yellow")
    _show_top(boosted, "[4b] + confidence/recency/feedback boost", "green")

    console.print("[bold green]Demo complete.[/]\n")
    storage.close()

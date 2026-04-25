from __future__ import annotations

import asyncio
import sys

import click


def _log(msg: str) -> None:
    """Bootstrap logging — stderr only, never stdout (stdio MCP uses stdout)."""
    print(f"[context8] {msg}", file=sys.stderr, flush=True)


def _bootstrap() -> None:
    """Idempotent bootstrap: container up, collection ready, models cached.

    Safe to run on every `serve` invocation — each step is a no-op when already
    satisfied. All output goes to stderr so the MCP stdio protocol stays clean.
    """
    from ...docker import ensure_running, is_container_running

    if not is_container_running():
        _log("starting DB container...")
        ok, msg = ensure_running(timeout_secs=30)
        if not ok:
            _log(f"FATAL: container failed to start: {msg}")
            raise SystemExit(1)
        _log(f"container ready ({msg})")

    from ...storage import StorageService

    storage = StorageService()
    created = storage.initialize()
    if created:
        _log("collection created")
    storage.close()

    try:
        from ...embeddings import EmbeddingService

        EmbeddingService.ensure_models_downloaded()
    except Exception as e:
        _log(f"warning: model pre-download failed ({e}) — will lazy-load")


@click.command()
@click.option(
    "--no-bootstrap",
    is_flag=True,
    help="Skip auto-start of container/collection (assume already initialized)",
)
def serve(no_bootstrap: bool):
    """Start the Context8 MCP server (stdio transport).

    By default, ensures the DB container is up and the collection exists before
    starting the server, so a single `context8 serve` works from a cold machine.
    """
    if not no_bootstrap:
        _bootstrap()

    from ...mcp import run_server

    asyncio.run(run_server())

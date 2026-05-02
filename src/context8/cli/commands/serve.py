"""``context8 serve`` — the MCP stdio server entry point.

Auto-bootstraps everything needed for a cold start:
- SQLite backend: create the DB file + apply schema, warm models.
- Actian backend: start the Docker container, create the collection,
  warm models.

After bootstrap, hands off to :func:`context8.mcp.run_server`. All log
output goes to stderr so the stdio MCP protocol on stdout stays clean.
"""

from __future__ import annotations

import asyncio
import sys

import click

from ...config import BACKEND


def _log(msg: str) -> None:
    """Bootstrap logging — stderr only, never stdout."""
    print(f"[context8] {msg}", file=sys.stderr, flush=True)


def _bootstrap() -> None:
    """Idempotent bootstrap: backend ready + models cached."""
    if BACKEND == "actian":
        from ...docker import ensure_running, is_container_running

        if not is_container_running():
            _log("starting Actian DB container...")
            ok, msg = ensure_running(timeout_secs=30)
            if not ok:
                _log(f"FATAL: container failed to start: {msg}")
                raise SystemExit(1)
            _log(f"container ready ({msg})")

    from ...storage import StorageService

    storage = StorageService()
    created = storage.initialize()
    if created:
        _log(f"{BACKEND} backend initialized")
    storage.close()

    try:
        from ...embeddings import EmbeddingService

        EmbeddingService.ensure_models_downloaded()
    except Exception as exc:
        _log(f"warning: model pre-download failed ({exc}) — will lazy-load")


@click.command()
@click.option(
    "--no-bootstrap",
    is_flag=True,
    help="Skip auto-start of backend (assume already initialized)",
)
def serve(no_bootstrap: bool):
    """Start the Context8 MCP server (stdio transport).

    By default, ensures the backend is ready before the stdio loop
    starts so a single ``context8 serve`` works on a cold machine.
    """
    if not no_bootstrap:
        _bootstrap()

    from ...mcp import run_server

    asyncio.run(run_server())

from __future__ import annotations

import asyncio

import click


@click.command()
def serve():
    """Start the Context8 MCP server (stdio transport)."""
    from ...mcp import run_server

    asyncio.run(run_server())

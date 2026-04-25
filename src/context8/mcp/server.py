from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import tools as tools_module
from .tools_browse import call_extra_tool, extra_tools

logger = logging.getLogger("context8.mcp")

app = Server("context8")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return tools_module.list_tools() + extra_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        # Try extra tools first (browse, ecosystem)
        result = await asyncio.to_thread(call_extra_tool, name, arguments)
        if result is not None:
            return result
        # Fall through to core tools
        return await asyncio.to_thread(tools_module.call_tool, name, arguments)
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Context8 error: {str(e)}")]


async def run_server():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Context8 MCP server starting...")

    embeddings, _, _, _ = tools_module.get_services()
    threading.Thread(target=embeddings.warmup, daemon=True).start()

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run_server())

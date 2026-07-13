"""Standalone stdio MCP server for SP-Mind.

Exposes the SP-Mind toolchain over the Model Context Protocol so it can be
installed into any MCP client (Claude Desktop, Claude Code, ...):

    claude mcp add spmind -- python -m spmind.mcp_stdio
    # or, via the console script:
    claude mcp add spmind -- spmind-mcp

Unlike the in-process server the agent uses (``spmind.tool.mcp_server``), this
runs as its own **local** subprocess that the MCP client spawns and talks to
over stdin/stdout. It is still entirely local: it calls the same local tool
functions, which run the containerized backends on this machine.
"""

from __future__ import annotations

import asyncio
import importlib

import mcp.types as mcptypes
from mcp.server import Server
from mcp.server.stdio import stdio_server

from spmind.tool.mcp_server import _input_schema
from spmind.utils import read_module2api

SERVER_NAME = "spmind"


def _registry() -> dict[str, tuple[str, str, dict]]:
    """Map tool name -> (module_path, description, input_schema)."""
    registry: dict[str, tuple[str, str, dict]] = {}
    for module_path, descriptions in read_module2api().items():
        for desc in descriptions:
            registry[desc["name"]] = (
                module_path,
                desc.get("description", desc["name"]),
                _input_schema(desc),
            )
    return registry


def list_spmind_tools() -> list[mcptypes.Tool]:
    """Return the MCP tool definitions (used by the ``list_tools`` handler)."""
    return [
        mcptypes.Tool(name=name, description=description, inputSchema=schema)
        for name, (_, description, schema) in _registry().items()
    ]


async def call_spmind_tool(name: str, arguments: dict | None) -> list[mcptypes.TextContent]:
    """Import and invoke the requested tool function, returning its output."""
    registry = _registry()
    if name not in registry:
        return [mcptypes.TextContent(type="text", text=f"Unknown tool: {name}")]
    module_path, _, _ = registry[name]
    try:
        module = importlib.import_module(module_path)
        fn = getattr(module, name)
        # Sync, potentially long-running (containers) -> keep off the event loop.
        result = await asyncio.to_thread(fn, **(arguments or {}))
        return [mcptypes.TextContent(type="text", text=str(result))]
    except Exception as e:  # surface to the client, don't crash the server
        return [mcptypes.TextContent(type="text", text=f"Error in {name}: {e}")]


def build_server() -> Server:
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def _list() -> list[mcptypes.Tool]:
        return list_spmind_tools()

    @server.call_tool()
    async def _call(name: str, arguments: dict) -> list[mcptypes.TextContent]:
        return await call_spmind_tool(name, arguments)

    return server


async def _run() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

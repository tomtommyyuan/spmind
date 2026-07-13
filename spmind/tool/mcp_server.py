"""In-process MCP server exposing the SP-Mind toolchain.

Turns the container-backed tool functions in ``spmind.tool.*`` into typed,
schema-validated Model Context Protocol (MCP) tools that the agent can call
directly, instead of hand-writing ``python -c`` snippets in the Bash tool.

The tool schemas are generated from the existing
``spmind.tool.tool_description.*`` metadata, so the MCP interface and the
underlying functions never drift out of sync.
"""

from __future__ import annotations

import asyncio
import importlib
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from spmind.utils import read_module2api

MCP_SERVER_NAME = "spmind"


def _json_type(type_str: str) -> str:
    """Map the loose type strings in tool_description to JSON-schema types."""
    t = (type_str or "").lower()
    if t.startswith("int"):
        return "integer"
    if t.startswith("float") or t.startswith("number"):
        return "number"
    if t.startswith("bool"):
        return "boolean"
    if t.startswith(("list", "tuple")):
        return "array"
    if t.startswith("dict"):
        return "object"
    # Union / Optional / anything else -> accept as string; the underlying
    # function does its own coercion/validation.
    return "string"


def _input_schema(tool_desc: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-schema ``input_schema`` from a tool_description entry."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in tool_desc.get("required_parameters", []):
        properties[param["name"]] = {
            "type": _json_type(param.get("type", "str")),
            "description": param.get("description", ""),
        }
        required.append(param["name"])
    for param in tool_desc.get("optional_parameters", []):
        properties[param["name"]] = {
            "type": _json_type(param.get("type", "str")),
            "description": param.get("description", ""),
        }
    return {"type": "object", "properties": properties, "required": required}


def _make_handler(module_path: str, func_name: str):
    """Create an async MCP handler that calls the real tool function."""

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        try:
            module = importlib.import_module(module_path)
            fn = getattr(module, func_name)
            # Tool functions are synchronous and can run for minutes (they
            # shell out to Docker/Singularity), so keep them off the event loop.
            result = await asyncio.to_thread(fn, **args)
            return {"content": [{"type": "text", "text": str(result)}]}
        except Exception as e:  # surface the failure to the agent, don't crash
            return {
                "content": [{"type": "text", "text": f"Error in {func_name}: {e}"}],
                "is_error": True,
            }

    return handler


def build_spmind_mcp_server():
    """Build the in-process SP-Mind MCP server from tool_description metadata.

    Returns:
        Tuple of ``(server_config, tool_names)``:
          - ``server_config`` to pass as
            ``mcp_servers={MCP_SERVER_NAME: server_config}``.
          - ``tool_names`` — fully-qualified names (``mcp__spmind__<tool>``)
            for optional allow-listing.
    """
    module2api = read_module2api()
    sdk_tools = []
    tool_names: list[str] = []

    for module_path, descriptions in module2api.items():
        for desc in descriptions:
            name = desc["name"]
            handler = _make_handler(module_path, name)
            sdk_tool = tool(name, desc.get("description", name), _input_schema(desc))(handler)
            sdk_tools.append(sdk_tool)
            tool_names.append(f"mcp__{MCP_SERVER_NAME}__{name}")

    server = create_sdk_mcp_server(MCP_SERVER_NAME, "1.0.0", sdk_tools)
    return server, tool_names

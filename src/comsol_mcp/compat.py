"""Compatibility layer supporting both MCP Python SDK v1 (FastMCP) and v2 (MCPServer)."""

from __future__ import annotations

from typing import Any

try:
    from mcp.server.mcpserver import MCPServer as _ServerClass

    MCP_SDK_MAJOR = 2
except ImportError:  # pragma: no cover - exercised when mcp<2 is installed
    from mcp.server.fastmcp import FastMCP as _ServerClass  # type: ignore

    MCP_SDK_MAJOR = 1


def create_mcp_server(name: str, instructions: str, version: str = "0.1.0") -> Any:
    """Instantiate an MCP server compatible with SDK v1 and v2."""
    if MCP_SDK_MAJOR >= 2:
        return _ServerClass(name=name, version=version, instructions=instructions)
    return _ServerClass(name=name, instructions=instructions)


def list_registered_tools(server: Any) -> list[str]:
    """Return sorted tool names registered on an MCPServer or FastMCP instance."""
    tool_mgr = getattr(server, "_tool_manager", None)
    if tool_mgr is not None:
        tools = getattr(tool_mgr, "_tools", None)
        if isinstance(tools, dict):
            return sorted(tools.keys())
        list_fn = getattr(tool_mgr, "list_tools", None)
        if callable(list_fn):
            return sorted(t.name for t in list_fn())
    return []


def list_registered_resources(server: Any) -> list[str]:
    """Return sorted resource URI templates registered on an MCPServer or FastMCP instance."""
    res_mgr = getattr(server, "_resource_manager", None)
    if res_mgr is None:
        return []
    uris: list[str] = []
    for attr in ("_resources", "_templates"):
        mapping = getattr(res_mgr, attr, None)
        if isinstance(mapping, dict):
            uris.extend(str(k) for k in mapping.keys())
    return sorted(set(uris))

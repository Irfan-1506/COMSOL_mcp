"""MCP resource endpoints (`comsol://session/info` and `comsol://model/{name}/*`)."""

from __future__ import annotations

import json
from typing import Any

from ..backends import BackendHub


def register_model_resources(mcp: Any, hub: BackendHub) -> None:
    @mcp.resource("comsol://session/info")
    def resource_session_info() -> str:
        """Current COMSOL MCP session status across all backends and active profiles."""
        return json.dumps(hub.overall_status(), indent=2)

    @mcp.resource("comsol://model/{name}/tree")
    def resource_model_tree(name: str) -> str:
        """Full inspected tree structure of a loaded interactive model."""
        return json.dumps(hub.interactive.model_inspect(model_name=name), indent=2)

    @mcp.resource("comsol://model/{name}/parameters")
    def resource_model_parameters(name: str) -> str:
        """Global parameters defined on a loaded interactive model."""
        return json.dumps(hub.interactive.param_list(model_name=name), indent=2)

    @mcp.resource("comsol://model/{name}/physics")
    def resource_model_physics(name: str) -> str:
        """Physics interfaces and features defined on a loaded interactive model."""
        info = hub.interactive.model_inspect(model_name=name)
        physics_by_comp = {
            ctag: comp.get("physics", {}) for ctag, comp in (info.get("components") or {}).items()
        }
        return json.dumps({"model": info.get("name"), "physics": physics_by_comp}, indent=2)

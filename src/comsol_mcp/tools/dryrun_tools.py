"""Dry-run simulator & offline Java codegen profile (`dryrun`)."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub
from ..codegen import write_model_java


def register_dryrun_tools(mcp: Any, hub: BackendHub) -> None:
    @mcp.tool()
    def dryrun_set_mode(enabled: bool) -> dict[str, Any]:
        """Switch interactive tools between the in-memory `dryrun` simulator (`enabled=True`) and live `mph` (`enabled=False`)."""
        return hub.set_dryrun(enabled)

    @mcp.tool()
    def dryrun_reset() -> dict[str, Any]:
        """Reset all in-memory models and operation history in the dry-run simulator."""
        return hub.dryrun.reset()

    @mcp.tool()
    def dryrun_ops_log(limit: int = 50) -> dict[str, Any]:
        """Return recent operations recorded by the dry-run simulator."""
        return {"count": len(hub.dryrun.ops_log), "ops": hub.dryrun.ops_log[-max(1, limit) :]}

    @mcp.tool()
    def generate_model_java(
        filepath: str,
        class_name: str = "GeneratedModel",
        spec: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Generate a standalone compilable COMSOL Java model file offline (no COMSOL install required)."""
        return write_model_java(filepath=filepath, class_name=class_name, spec=spec or {})

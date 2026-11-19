"""Guided workflows, rule-based model validation, and modeling assistant profile (`validate`)."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub
from ..validation import WorkflowManager, analyze_modeling_request, validate_model_snapshot


def register_validate_tools(mcp: Any, hub: BackendHub, workflows: WorkflowManager) -> None:
    @mcp.tool()
    def model_validate_all(model_name: Optional[str] = None) -> dict[str, Any]:
        """Run pre-solve rule-based checks across components, geometry, materials, physics, boundaries, mesh, and study."""
        snapshot = hub.interactive.model_inspect(model_name=model_name)
        return validate_model_snapshot(snapshot)

    @mcp.tool()
    def workflow_list_templates() -> dict[str, Any]:
        """List available guided multiphysics modeling workflow templates and step sequence."""
        return workflows.list_templates()

    @mcp.tool()
    def workflow_start(template: str = "general", goal: str = "") -> dict[str, Any]:
        """Start a guided step-by-step COMSOL modeling workflow (`general`, `heat_transfer`, `electrostatics`, `fluid_flow`, `solid_mechanics`, `electrochemistry`)."""
        return workflows.start(template=template, goal=goal)

    @mcp.tool()
    def workflow_next_step(advance: bool = True) -> dict[str, Any]:
        """Return the current workflow step, or mark it complete and advance (`advance=True`)."""
        return workflows.advance() if advance else workflows.current_step()

    @mcp.tool()
    def modeling_assist(question: str) -> dict[str, Any]:
        """Analyze a natural-language modeling request (English or Chinese) and recommend workflow template, physics, expressions, and tools."""
        return analyze_modeling_request(question)

"""Profile-gated MCP tool registration orchestrator."""

from __future__ import annotations

from typing import Any

from ..backends import BackendHub
from ..catalog import CatalogStore
from ..knowledge import RagKnowledgeBase
from ..validation import WorkflowManager
from .batch_tools import register_batch_tools
from .catalog_tools import register_catalog_tools
from .core_extended import register_core_extended_tools
from .core_mph import register_core_tools
from .dryrun_tools import register_dryrun_tools
from .gui_tools import register_gui_tools
from .physics_domain import register_physics_domain_tools
from .physics_extended import register_physics_extended_tools
from .rag_tools import register_rag_tools
from .validate_tools import register_validate_tools


def register_profile_tools(
    mcp: Any,
    hub: BackendHub,
    catalog: CatalogStore,
    workflows: WorkflowManager,
    rag: RagKnowledgeBase,
) -> list[str]:
    """Mount only the profiles requested in `hub.settings.profiles`."""
    mounted: list[str] = []
    profiles = set(hub.settings.profiles)

    if "core" in profiles:
        register_core_tools(mcp, hub)
        register_core_extended_tools(mcp, hub)
        mounted.append("core")
    if "physics" in profiles:
        register_physics_domain_tools(mcp, hub)
        register_physics_extended_tools(mcp, hub)
        mounted.append("physics")
    if "batch" in profiles:
        register_batch_tools(mcp, hub)
        mounted.append("batch")
    if "gui" in profiles:
        register_gui_tools(mcp, hub)
        mounted.append("gui")
    if "catalog" in profiles:
        register_catalog_tools(mcp, hub, catalog)
        mounted.append("catalog")
    if "validate" in profiles:
        register_validate_tools(mcp, hub, workflows)
        mounted.append("validate")
    if "rag" in profiles:
        register_rag_tools(mcp, rag)
        mounted.append("rag")
    if "dryrun" in profiles:
        register_dryrun_tools(mcp, hub)
        mounted.append("dryrun")

    return mounted

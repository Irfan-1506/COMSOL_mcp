"""Unified COMSOL MCP Server factory and runtime lifecycle management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from . import __version__
from .backends import BackendHub
from .catalog import CatalogStore
from .compat import create_mcp_server
from .config import Settings
from .knowledge import RagKnowledgeBase
from .resources import register_model_resources
from .tools import register_profile_tools
from .validation import WorkflowManager

SERVER_INSTRUCTIONS = """\
Unified COMSOL Multiphysics MCP server supporting warm `mph` sessions, isolated
native `comsolcompile`/`comsolbatch` jobs, optional Windows Desktop GUI tools,
offline COMSOL API catalog lookup, pre-solve model validation, PDF RAG, and
dry-run simulation.

Recommended patterns:
- Call `comsol_status` first to see active profiles and available backends.
- Use `catalog_search` / `catalog_get_properties` before setting unfamiliar COMSOL feature properties.
- Run `model_validate_all` before solving interactive models.
- For isolated native batch jobs (`batch_*`), always poll `batch_job_status` until a terminal state and never reuse existing output `.mph` filenames.
"""


@dataclass
class ServerBundle:
    mcp: Any
    settings: Settings
    hub: BackendHub
    catalog: CatalogStore
    workflows: WorkflowManager
    rag: RagKnowledgeBase
    mounted_profiles: list[str]

    def run_stdio(self, *, lock_batch_workspace: bool = True) -> None:
        locked = False
        if lock_batch_workspace and "batch" in self.mounted_profiles:
            self.hub.batch.acquire_workspace_lock()
            locked = True
        try:
            self.mcp.run(transport="stdio")
        finally:
            self.hub.shutdown()
            if locked:
                self.hub.batch.release_workspace_lock()


def build_server(
    settings: Optional[Settings] = None,
    *,
    profiles: Optional[str] = None,
    workspace: Optional[str] = None,
    dryrun: Optional[bool] = None,
) -> ServerBundle:
    """Construct a configured unified COMSOL MCP server instance."""
    cfg = settings or Settings.from_env(profiles=profiles, workspace=workspace, dryrun=dryrun)
    hub = BackendHub(cfg)
    catalog = CatalogStore(cfg.catalog_dir)
    workflows = WorkflowManager()
    rag = RagKnowledgeBase(cfg)

    mcp = create_mcp_server(
        name="COMSOL Multiphysics Unified MCP",
        version=__version__,
        instructions=SERVER_INSTRUCTIONS,
    )
    mounted = register_profile_tools(mcp, hub, catalog, workflows, rag)
    register_model_resources(mcp, hub)

    return ServerBundle(
        mcp=mcp,
        settings=cfg,
        hub=hub,
        catalog=catalog,
        workflows=workflows,
        rag=rag,
        mounted_profiles=mounted,
    )


def main() -> None:
    bundle = build_server()
    bundle.run_stdio()


if __name__ == "__main__":
    main()

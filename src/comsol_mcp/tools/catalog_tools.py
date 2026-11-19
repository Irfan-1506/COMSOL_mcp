"""Offline static COMSOL API catalog profile (`catalog`)."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub
from ..catalog import CatalogStore, build_catalog_from_install


def register_catalog_tools(mcp: Any, hub: BackendHub, catalog: CatalogStore) -> None:
    @mcp.tool()
    def catalog_info() -> dict[str, Any]:
        """Show built-in physics catalog summary and whether local COMSOL XML completion schemas are extracted."""
        return catalog.info()

    @mcp.tool()
    def catalog_build_local() -> dict[str, Any]:
        """Extract offline feature & property schemas directly from your locally installed `<COMSOL_HOME>/data/completion/*.xml`."""
        if not hub.settings.comsol_home:
            raise RuntimeError("COMSOL installation not found. Set COMSOL_HOME to your Multiphysics directory.")
        meta = build_catalog_from_install(hub.settings.comsol_home, hub.settings.catalog_dir)
        catalog._layer_cache.clear()
        return {"ok": True, "meta": meta}

    @mcp.tool()
    def catalog_search(query: str, layer: Optional[str] = None, limit: int = 25) -> dict[str, Any]:
        """Search COMSOL physics interfaces, features, multiphysics couplings, and local XML layers offline."""
        return catalog.search(query=query, layer=layer, limit=limit)

    @mcp.tool()
    def catalog_get_properties(feature_or_interface: str, layer: Optional[str] = None) -> dict[str, Any]:
        """Look up valid feature names for a physics interface/layer OR exact property names for a COMSOL feature."""
        try:
            return catalog.get_properties(feature_or_interface, layer=layer)
        except ValueError:
            return catalog.get_features(feature_or_interface)

    # --- Static catalog parity tools (7) ---
    @mcp.tool()
    def static_catalog_info() -> dict[str, Any]:
        """Inspect static COMSOL catalog metadata and loaded layers."""
        return catalog.info()

    @mcp.tool()
    def static_catalog_search(query: str, layer: Optional[str] = None, limit: int = 25) -> dict[str, Any]:
        """Search static COMSOL catalog interfaces, features, and local completion XML layers."""
        return catalog.search(query=query, layer=layer, limit=limit)

    @mcp.tool()
    def static_catalog_features(interface_or_layer: str) -> dict[str, Any]:
        """List valid feature names for a physics interface or local XML layer."""
        return catalog.get_features(interface_or_layer)

    @mcp.tool()
    def static_catalog_properties(feature_name: str, layer: Optional[str] = None) -> dict[str, Any]:
        """List valid property names, types, and defaults for a COMSOL feature."""
        return catalog.get_properties(feature_name, layer=layer)

    @mcp.tool()
    def static_catalog_variables(physics_interface: str) -> dict[str, Any]:
        """List common field and post-processing variables for a physics interface."""
        return catalog.get_variables(physics_interface)

    @mcp.tool()
    def static_catalog_discretization(physics_interface: str) -> dict[str, Any]:
        """Return standard shape-function discretization settings for a physics interface."""
        return catalog.get_discretization(physics_interface)

    @mcp.tool()
    def static_catalog_layer(layer: str, limit: int = 100) -> dict[str, Any]:
        """List extracted COMSOL feature types in a specific completion XML layer (`geom`, `mesh`, `physics`, `study`, `sol`, etc.)."""
        return catalog.list_layer(layer=layer, limit=limit)

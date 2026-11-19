"""Core interactive modeling profile (`core`): warm mph or dry-run simulator."""

from __future__ import annotations

import time
from typing import Any, Optional

from ..backends import BackendHub


def register_core_tools(mcp: Any, hub: BackendHub) -> None:
    def _wrap(name: str, fn):
        def inner(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                res = fn(*args, **kwargs)
                hub.record_call(name, True, (time.perf_counter() - t0) * 1000.0)
                return res
            except Exception as exc:
                hub.record_call(name, False, (time.perf_counter() - t0) * 1000.0, str(exc))
                raise

        return inner

    @mcp.tool()
    def comsol_status() -> dict[str, Any]:
        """Report status across all backends (mph, dryrun, batch, gui), profiles, and call telemetry."""
        data = hub.overall_status()
        data["telemetry"] = hub.call_stats()
        return data

    @mcp.tool()
    def comsol_start(cores: Optional[int] = None, version: Optional[str] = None) -> dict[str, Any]:
        """Start the active interactive COMSOL session (`mph` JVM or `dryrun` simulator)."""
        return _wrap("comsol_start", hub.interactive.start)(cores=cores or hub.settings.cores, version=version)

    @mcp.tool()
    def comsol_connect(host: str = "localhost", port: int = 2036) -> dict[str, Any]:
        """Connect to a running COMSOL Multiphysics Server on `host:port`."""
        return _wrap("comsol_connect", hub.interactive.connect)(host=host, port=port)

    @mcp.tool()
    def comsol_disconnect() -> dict[str, Any]:
        """Clear loaded models from the interactive session."""
        return _wrap("comsol_disconnect", hub.interactive.disconnect)()

    @mcp.tool()
    def model_create(name: str = "Model") -> dict[str, Any]:
        """Create a new empty COMSOL model in the active interactive session."""
        return _wrap("model_create", hub.interactive.model_create)(name=name)

    @mcp.tool()
    def model_load(path: str, name: Optional[str] = None) -> dict[str, Any]:
        """Load an existing `.mph` model file into the active interactive session."""
        return _wrap("model_load", hub.interactive.model_load)(path=path, name=name)

    @mcp.tool()
    def model_save(
        path: Optional[str] = None,
        model_name: Optional[str] = None,
        versioned: bool = False,
        tag: Optional[str] = None,
    ) -> dict[str, Any]:
        """Save the active model to `.mph`. Set `versioned=True` for timestamped + `_latest.mph` copies."""
        return _wrap("model_save", hub.interactive.model_save)(
            path=path, model_name=model_name, versioned=versioned, tag=tag
        )

    @mcp.tool()
    def model_list() -> dict[str, Any]:
        """List all models currently loaded in the interactive session."""
        return _wrap("model_list", hub.interactive.model_list)()

    @mcp.tool()
    def model_inspect(model_name: Optional[str] = None) -> dict[str, Any]:
        """Inspect a loaded model's parameters, components, geometry, materials, physics, meshes, and studies."""
        return _wrap("model_inspect", hub.interactive.model_inspect)(model_name=model_name)

    @mcp.tool()
    def model_diff(model_a: str, model_b: str) -> dict[str, Any]:
        """Compare two loaded models across parameters, components, physics, studies, and solutions."""
        return _wrap("model_diff", hub.interactive.model_diff)(model_a=model_a, model_b=model_b)

    @mcp.tool()
    def param_set(name: str, expression: str, description: str = "", model_name: Optional[str] = None) -> dict[str, Any]:
        """Set a global model parameter expression with explicit units (e.g. `L`, `20[mm]`)."""
        return _wrap("param_set", hub.interactive.param_set)(
            name=name, expression=expression, description=description, model_name=model_name
        )

    @mcp.tool()
    def param_list(model_name: Optional[str] = None) -> dict[str, Any]:
        """List all global parameters defined on the model."""
        return _wrap("param_list", hub.interactive.param_list)(model_name=model_name)

    @mcp.tool()
    def geometry_add(
        shape: str,
        params: dict[str, Any],
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        dim: int = 3,
        feature_tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a geometry primitive or boolean op (`Block`, `Cylinder`, `Sphere`, `Rectangle`, `Circle`, `Union`, `Difference`, `Import`)."""
        return _wrap("geometry_add", hub.interactive.geometry_add)(
            shape=shape,
            params=params,
            geom_tag=geom_tag,
            comp_tag=comp_tag,
            dim=dim,
            feature_tag=feature_tag,
            model_name=model_name,
        )

    @mcp.tool()
    def geometry_build(geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Build/finalize a geometry sequence so domains and boundaries are indexed."""
        return _wrap("geometry_build", hub.interactive.geometry_build)(
            geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def selection_create(
        tag: str,
        selection_type: str,
        config: dict[str, Any],
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a named geometric selection (`Explicit`, `Box`, `Cylinder`, `Ball`)."""
        return _wrap("selection_create", hub.interactive.selection_create)(
            tag=tag, selection_type=selection_type, config=config, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def material_add(
        tag: str,
        properties: dict[str, Any],
        label: Optional[str] = None,
        domains: Optional[list[int]] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a material with physical properties (e.g. `thermalconductivity`, `density`, `relpermittivity`)."""
        return _wrap("material_add", hub.interactive.material_add)(
            tag=tag, properties=properties, label=label, domains=domains, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def physics_add(
        tag: str,
        interface: str,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        properties: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a COMSOL physics interface (e.g. `HeatTransfer`, `Electrostatics`, `LaminarFlow`, `SolidMechanics`)."""
        return _wrap("physics_add", hub.interactive.physics_add)(
            tag=tag, interface=interface, geom_tag=geom_tag, comp_tag=comp_tag, properties=properties, model_name=model_name
        )

    @mcp.tool()
    def physics_feature_add(
        physics_tag: str,
        feature_tag: str,
        feature_type: str,
        dim: Optional[int] = None,
        selection: Optional[list[int] | str] = None,
        properties: Optional[dict[str, Any]] = None,
        parent_feature: Optional[str] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a domain/boundary condition or subfeature (e.g. `TemperatureBoundary`, `Ground`, `InletBoundary`) to a physics interface."""
        return _wrap("physics_feature_add", hub.interactive.physics_feature_add)(
            physics_tag=physics_tag,
            feature_tag=feature_tag,
            feature_type=feature_type,
            dim=dim,
            selection=selection,
            properties=properties,
            parent_feature=parent_feature,
            comp_tag=comp_tag,
            model_name=model_name,
        )

    @mcp.tool()
    def mesh_build(
        mesh_tag: str = "mesh1",
        size: int = 5,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate an automatic mesh (`size` 1=extremely fine .. 9=extremely coarse, 5=normal)."""
        return _wrap("mesh_build", hub.interactive.mesh_build)(
            mesh_tag=mesh_tag, size=size, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def study_create(
        study_tag: str = "std1",
        study_type: str = "Stationary",
        step_tag: Optional[str] = None,
        settings: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a study (`Stationary`, `Transient`, `Frequency`, `Eigenfrequency`)."""
        return _wrap("study_create", hub.interactive.study_create)(
            study_tag=study_tag, study_type=study_type, step_tag=step_tag, settings=settings, model_name=model_name
        )

    @mcp.tool()
    def study_solve(
        study_tag: str = "std1",
        async_mode: bool = False,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run a study synchronously or in a background thread (`async_mode=True`)."""
        return _wrap("study_solve", hub.interactive.study_solve)(
            study_tag=study_tag, async_mode=async_mode, model_name=model_name
        )

    @mcp.tool()
    def solver_status(cancel: bool = False) -> dict[str, Any]:
        """Check interactive solver progress or request cancellation (`cancel=True`)."""
        if cancel:
            return _wrap("solver_status", hub.interactive.solver_cancel)()
        return _wrap("solver_status", hub.interactive.solver_progress)()

    @mcp.tool()
    def results_evaluate(
        expression: str,
        dataset: Optional[str] = None,
        global_eval: bool = False,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Evaluate a COMSOL expression (`T`, `es.normE`, `spf.U`, `solid.mises`, etc.) on the solved dataset."""
        return _wrap("results_evaluate", hub.interactive.results_evaluate)(
            expression=expression, dataset=dataset, global_eval=global_eval, model_name=model_name
        )

    @mcp.tool()
    def results_export(
        kind: str,
        output_path: str,
        node_tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Export simulation results (`kind='data'` or `kind='image'`) to disk."""
        return _wrap("results_export", hub.interactive.results_export)(
            kind=kind, output_path=output_path, node_tag=node_tag, model_name=model_name
        )

    @mcp.tool()
    def node_mutate(
        category: str,
        action: str,
        tag: str,
        node_type: Optional[str] = None,
        properties: Optional[dict[str, Any]] = None,
        comp_tag: str = "comp1",
        parent_tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Low-level escape hatch to `create`, `set`, `toggle`, or `delete` nodes (`function`, `plot`, `material`, `physics`, `study`)."""
        return _wrap("node_mutate", hub.interactive.node_mutate)(
            category=category,
            action=action,
            tag=tag,
            node_type=node_type,
            properties=properties,
            comp_tag=comp_tag,
            parent_tag=parent_tag,
            model_name=model_name,
        )

"""Extended core parity tools: model lifecycle, audit, params, geometry primitives, mesh, study, results, low-level modify."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub


def register_core_extended_tools(mcp: Any, hub: BackendHub) -> None:
    # --- Model lifecycle & audit (9) ---
    @mcp.tool()
    def model_create_component(tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Create a model component (e.g. `comp1`)."""
        return hub.interactive.component_create(tag=tag, model_name=model_name)

    @mcp.tool()
    def model_list_components(model_name: Optional[str] = None) -> dict[str, Any]:
        """List all component tags in the model."""
        return hub.interactive.component_list(model_name=model_name)

    @mcp.tool()
    def model_save_version(tag: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Save a timestamped versioned `.mph` copy plus `_latest.mph`."""
        return hub.interactive.model_save(model_name=model_name, versioned=True, tag=tag)

    @mcp.tool()
    def model_set_current(name: str) -> dict[str, Any]:
        """Switch the active model by name."""
        return hub.interactive.model_set_current(name=name)

    @mcp.tool()
    def model_clone(source: str, new_name: str) -> dict[str, Any]:
        """Clone an existing loaded model to a new name."""
        return hub.interactive.model_clone(source=source, new_name=new_name)

    @mcp.tool()
    def model_remove(name: str) -> dict[str, Any]:
        """Remove a loaded model from memory."""
        return hub.interactive.model_remove(name=name)

    @mcp.tool()
    def model_audit(model_name: Optional[str] = None) -> dict[str, Any]:
        """Perform a deep recursive audit of the model tree, parameters, physics, meshes, and studies."""
        return hub.interactive.model_audit(model_name=model_name)

    @mcp.tool()
    def model_export_java(output_path: str, model_name: Optional[str] = None) -> dict[str, Any]:
        """Export the active model as a `.java` COMSOL API file."""
        return hub.interactive.model_export_java(output_path=output_path, model_name=model_name)

    @mcp.tool()
    def geometry_boundary_info(geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Inspect boundary indices and geometric dimension for a geometry sequence."""
        return hub.interactive.geometry_boundary_info(geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    # --- Parameters (3) ---
    @mcp.tool()
    def param_get(name: str, model_name: Optional[str] = None) -> dict[str, Any]:
        """Read a single global parameter value and description."""
        return hub.interactive.param_get(name=name, model_name=model_name)

    @mcp.tool()
    def param_description(name: str, description: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Get or update the description of a global parameter."""
        return hub.interactive.param_description(name=name, description=description, model_name=model_name)

    @mcp.tool()
    def param_sweep_setup(
        study_tag: str,
        parameter_name: str,
        values: list[str] | str,
        sweep_tag: str = "param",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Attach a Parametric Sweep study step to sweep a parameter across values."""
        return hub.interactive.param_sweep_setup(
            study_tag=study_tag,
            parameter_name=parameter_name,
            values=values,
            sweep_tag=sweep_tag,
            model_name=model_name,
        )

    # --- Geometry primitives, booleans & selections (14) ---
    @mcp.tool()
    def geometry_list(comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """List all geometry sequences in a component."""
        return hub.interactive.geometry_list(comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def geometry_create(geom_tag: str = "geom1", dim: int = 3, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Create a geometry sequence with spatial dimension `dim` (1, 2, or 3)."""
        return hub.interactive.geometry_create(geom_tag=geom_tag, dim=dim, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def geometry_add_feature(
        feature_type: str,
        params: dict[str, Any],
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        dim: int = 3,
        tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add any generic COMSOL geometry feature by type name."""
        return hub.interactive.geometry_add(
            shape=feature_type, params=params, geom_tag=geom_tag, comp_tag=comp_tag, dim=dim, feature_tag=tag, model_name=model_name
        )

    @mcp.tool()
    def geometry_add_block(
        size: list[str | float],
        pos: Optional[list[str | float]] = None,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a 3D rectangular Block primitive."""
        params: dict[str, Any] = {"size": [str(x) for x in size]}
        if pos is not None:
            params["pos"] = [str(x) for x in pos]
        return hub.interactive.geometry_add("Block", params, geom_tag=geom_tag, comp_tag=comp_tag, dim=3, feature_tag=tag, model_name=model_name)

    @mcp.tool()
    def geometry_add_cylinder(
        r: str | float,
        h: str | float,
        pos: Optional[list[str | float]] = None,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a 3D Cylinder primitive."""
        params: dict[str, Any] = {"r": str(r), "h": str(h)}
        if pos is not None:
            params["pos"] = [str(x) for x in pos]
        return hub.interactive.geometry_add("Cylinder", params, geom_tag=geom_tag, comp_tag=comp_tag, dim=3, feature_tag=tag, model_name=model_name)

    @mcp.tool()
    def geometry_add_sphere(
        r: str | float,
        pos: Optional[list[str | float]] = None,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a 3D Sphere primitive."""
        params: dict[str, Any] = {"r": str(r)}
        if pos is not None:
            params["pos"] = [str(x) for x in pos]
        return hub.interactive.geometry_add("Sphere", params, geom_tag=geom_tag, comp_tag=comp_tag, dim=3, feature_tag=tag, model_name=model_name)

    @mcp.tool()
    def geometry_add_rectangle(
        size: list[str | float],
        pos: Optional[list[str | float]] = None,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a 2D Rectangle primitive."""
        params: dict[str, Any] = {"size": [str(x) for x in size]}
        if pos is not None:
            params["pos"] = [str(x) for x in pos]
        return hub.interactive.geometry_add("Rectangle", params, geom_tag=geom_tag, comp_tag=comp_tag, dim=2, feature_tag=tag, model_name=model_name)

    @mcp.tool()
    def geometry_add_circle(
        r: str | float,
        pos: Optional[list[str | float]] = None,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a 2D Circle primitive."""
        params: dict[str, Any] = {"r": str(r)}
        if pos is not None:
            params["pos"] = [str(x) for x in pos]
        return hub.interactive.geometry_add("Circle", params, geom_tag=geom_tag, comp_tag=comp_tag, dim=2, feature_tag=tag, model_name=model_name)

    @mcp.tool()
    def geometry_boolean_union(
        inputs: list[str],
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Boolean union of geometry objects."""
        return hub.interactive.geometry_add("Union", {"input": inputs}, geom_tag=geom_tag, comp_tag=comp_tag, feature_tag=tag, model_name=model_name)

    @mcp.tool()
    def geometry_boolean_difference(
        add_objects: list[str],
        subtract_objects: list[str],
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Boolean difference (`add_objects` minus `subtract_objects`)."""
        return hub.interactive.geometry_add(
            "Difference",
            {"input": add_objects, "input2": subtract_objects},
            geom_tag=geom_tag,
            comp_tag=comp_tag,
            feature_tag=tag,
            model_name=model_name,
        )

    @mcp.tool()
    def geometry_import(
        filename: str,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        dim: int = 3,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Import a CAD/mesh geometry file (STEP, IGES, STL, DXF, MPHBIN)."""
        return hub.interactive.geometry_add("Import", {"filename": filename}, geom_tag=geom_tag, comp_tag=comp_tag, dim=dim, feature_tag=tag, model_name=model_name)

    @mcp.tool()
    def geometry_list_features(geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """List all features inside a geometry sequence."""
        return hub.interactive.geometry_list_features(geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def geometry_create_box_selection(
        tag: str,
        xmin: Optional[str | float] = None,
        xmax: Optional[str | float] = None,
        ymin: Optional[str | float] = None,
        ymax: Optional[str | float] = None,
        zmin: Optional[str | float] = None,
        zmax: Optional[str | float] = None,
        entitydim: int = 2,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a coordinate-bounded Box selection (domains/boundaries/edges/points)."""
        cfg: dict[str, Any] = {"entitydim": entitydim}
        for k, v in (("xmin", xmin), ("xmax", xmax), ("ymin", ymin), ("ymax", ymax), ("zmin", zmin), ("zmax", zmax)):
            if v is not None:
                cfg[k] = str(v)
        return hub.interactive.selection_create(tag=tag, selection_type="Box", config=cfg, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def geometry_create_side_selections(
        bounds: dict[str, float],
        tol: float = 1e-6,
        entitydim: int = 2,
        prefix: str = "side_",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create named box selections for bounding sides (`xmin`/`xmax`/`ymin`/`ymax`/`zmin`/`zmax`)."""
        created: list[dict[str, Any]] = []
        for axis in ("x", "y", "z"):
            lo, hi = bounds.get(f"{axis}min"), bounds.get(f"{axis}max")
            if lo is not None:
                created.append(
                    hub.interactive.selection_create(
                        f"{prefix}{axis}min",
                        "Box",
                        {"entitydim": entitydim, f"{axis}min": str(lo - tol), f"{axis}max": str(lo + tol)},
                        comp_tag=comp_tag,
                        model_name=model_name,
                    )
                )
            if hi is not None:
                created.append(
                    hub.interactive.selection_create(
                        f"{prefix}{axis}max",
                        "Box",
                        {"entitydim": entitydim, f"{axis}min": str(hi - tol), f"{axis}max": str(hi + tol)},
                        comp_tag=comp_tag,
                        model_name=model_name,
                    )
                )
        return {"ok": True, "created": created}

    # --- Mesh (4) ---
    @mcp.tool()
    def mesh_list(comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """List all mesh sequences in a component."""
        return hub.interactive.mesh_list(comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def mesh_create_sequence(mesh_tag: str = "mesh1", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Create an empty mesh sequence linked to a geometry."""
        return hub.interactive.mesh_create_sequence(mesh_tag=mesh_tag, geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def mesh_create(mesh_tag: str = "mesh1", size: int = 5, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Create and build an automatic mesh (`size`: 1 finest .. 9 coarsest)."""
        return hub.interactive.mesh_build(mesh_tag=mesh_tag, size=size, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def mesh_info(mesh_tag: str = "mesh1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Return mesh element count and feature statistics."""
        return hub.interactive.mesh_info(mesh_tag=mesh_tag, comp_tag=comp_tag, model_name=model_name)

    # --- Study & Solutions (7) ---
    @mcp.tool()
    def study_list(model_name: Optional[str] = None) -> dict[str, Any]:
        """List all studies and their steps in the model."""
        return hub.interactive.study_list(model_name=model_name)

    @mcp.tool()
    def study_solve_async(study_tag: str = "std1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Start solving a study in a background thread."""
        return hub.interactive.study_solve(study_tag=study_tag, async_mode=True, model_name=model_name)

    @mcp.tool()
    def study_get_progress() -> dict[str, Any]:
        """Get current status and progress of the interactive solver."""
        return hub.interactive.solver_progress()

    @mcp.tool()
    def study_cancel() -> dict[str, Any]:
        """Request cancellation of the active interactive solve."""
        return hub.interactive.solver_cancel()

    @mcp.tool()
    def study_wait(timeout_seconds: float = 60.0) -> dict[str, Any]:
        """Wait for an asynchronous interactive solve to complete."""
        return hub.interactive.study_wait(timeout_seconds=timeout_seconds)

    @mcp.tool()
    def solutions_list(model_name: Optional[str] = None) -> dict[str, Any]:
        """List solution sequences stored in the model."""
        return hub.interactive.solutions_list(model_name=model_name)

    @mcp.tool()
    def datasets_list(model_name: Optional[str] = None) -> dict[str, Any]:
        """List result datasets available for post-processing."""
        return hub.interactive.datasets_list(model_name=model_name)

    # --- Results (7) ---
    @mcp.tool()
    def results_global_evaluate(expression: str, dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Evaluate a scalar / global expression on the solved dataset."""
        return hub.interactive.results_evaluate(expression=expression, dataset=dataset, global_eval=True, model_name=model_name)

    @mcp.tool()
    def results_inner_values(dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """List inner solution values (e.g. time steps or frequencies) for a dataset."""
        return hub.interactive.results_inner_values(dataset=dataset, model_name=model_name)

    @mcp.tool()
    def results_outer_values(dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """List outer parametric sweep values for a dataset."""
        return hub.interactive.results_outer_values(dataset=dataset, model_name=model_name)

    @mcp.tool()
    def results_export_data(output_path: str, node_tag: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Export numerical data to text/CSV file."""
        return hub.interactive.results_export(kind="data", output_path=output_path, node_tag=node_tag, model_name=model_name)

    @mcp.tool()
    def results_export_image(output_path: str, node_tag: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Export a plot group visualization to PNG."""
        return hub.interactive.results_export(kind="image", output_path=output_path, node_tag=node_tag, model_name=model_name)

    @mcp.tool()
    def results_exports_list(model_name: Optional[str] = None) -> dict[str, Any]:
        """List export nodes configured under Results."""
        return hub.interactive.results_exports_list(model_name=model_name)

    @mcp.tool()
    def results_plots_list(model_name: Optional[str] = None) -> dict[str, Any]:
        """List plot group nodes configured under Results."""
        return hub.interactive.results_plots_list(model_name=model_name)

    # --- Low-level generic node modification (18) ---
    @mcp.tool()
    def physics_feature_info(physics_tag: str, feature_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Inspect type, active state, and properties of a physics feature."""
        return hub.interactive.physics_feature_info(physics_tag=physics_tag, feature_tag=feature_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_feature_create(
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
        """Create a feature or subfeature inside a physics interface."""
        return hub.interactive.physics_feature_add(
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
    def physics_feature_set(
        physics_tag: str,
        feature_tag: str,
        properties: dict[str, Any],
        selection: Optional[list[int] | str] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update properties and/or selection on an existing physics feature."""
        return hub.interactive.physics_feature_set(
            physics_tag=physics_tag, feature_tag=feature_tag, properties=properties, selection=selection, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def physics_feature_toggle(physics_tag: str, feature_tag: str, active: Optional[bool] = None, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Enable, disable, or toggle a physics feature."""
        return hub.interactive.physics_feature_toggle(physics_tag=physics_tag, feature_tag=feature_tag, active=active, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_feature_delete(physics_tag: str, feature_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Delete a feature from a physics interface."""
        return hub.interactive.physics_feature_delete(physics_tag=physics_tag, feature_tag=feature_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def solver_feature_list(sol_tag: str = "sol1", model_name: Optional[str] = None) -> dict[str, Any]:
        """List solver sequence features under a solution tag."""
        return hub.interactive.solver_feature_list(sol_tag=sol_tag, model_name=model_name)

    @mcp.tool()
    def solver_feature_set(sol_tag: str, feature_tag: str, properties: dict[str, Any], model_name: Optional[str] = None) -> dict[str, Any]:
        """Set properties on a solver sequence feature."""
        return hub.interactive.solver_feature_set(sol_tag=sol_tag, feature_tag=feature_tag, properties=properties, model_name=model_name)

    @mcp.tool()
    def solver_feature_toggle(sol_tag: str, feature_tag: str, active: bool = True, model_name: Optional[str] = None) -> dict[str, Any]:
        """Enable or disable a solver sequence feature."""
        return hub.interactive.solver_feature_toggle(sol_tag=sol_tag, feature_tag=feature_tag, active=active, model_name=model_name)

    @mcp.tool()
    def results_node_create(tag: str, node_type: str, properties: Optional[dict[str, Any]] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Create a Results plot/node (e.g. `PlotGroup3D`, `PlotGroup2D`)."""
        return hub.interactive.node_mutate("plot", "create", tag, node_type=node_type, properties=properties, model_name=model_name)

    @mcp.tool()
    def results_node_set(tag: str, properties: dict[str, Any], model_name: Optional[str] = None) -> dict[str, Any]:
        """Set properties on a Results node."""
        return hub.interactive.node_mutate("plot", "set", tag, properties=properties, model_name=model_name)

    @mcp.tool()
    def results_node_delete(tag: str, model_name: Optional[str] = None) -> dict[str, Any]:
        """Delete a Results node."""
        return hub.interactive.node_mutate("plot", "delete", tag, model_name=model_name)

    @mcp.tool()
    def results_numerical_evaluate(expression: str, dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Evaluate a derived numerical expression on the solved dataset."""
        return hub.interactive.results_evaluate(expression=expression, dataset=dataset, global_eval=True, model_name=model_name)

    @mcp.tool()
    def results_interpolate(expression: str, coordinates: list[list[float]], dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Interpolate a field expression at explicit `[x, y, (z)]` probe coordinates."""
        return hub.interactive.results_interpolate(expression=expression, coordinates=coordinates, dataset=dataset, model_name=model_name)

    @mcp.tool()
    def function_create(tag: str, func_type: str, properties: Optional[dict[str, Any]] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        """Create a global analytical/interpolation/step/ramp function."""
        return hub.interactive.node_mutate("function", "create", tag, node_type=func_type, properties=properties, model_name=model_name)

    @mcp.tool()
    def function_set(tag: str, properties: dict[str, Any], model_name: Optional[str] = None) -> dict[str, Any]:
        """Update properties on an existing global function."""
        return hub.interactive.node_mutate("function", "set", tag, properties=properties, model_name=model_name)

    @mcp.tool()
    def material_create(
        tag: str,
        properties: Optional[dict[str, Any]] = None,
        label: Optional[str] = None,
        domains: Optional[list[int]] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a material node and optionally assign domain properties."""
        return hub.interactive.material_add(
            tag=tag, properties=properties or {}, label=label, domains=domains, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def material_set(tag: str, properties: dict[str, Any], comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Update properties on an existing material node."""
        return hub.interactive.node_mutate("material", "set", tag, properties=properties, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def material_delete(tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Delete a material node from a component."""
        return hub.interactive.node_mutate("material", "delete", tag, comp_tag=comp_tag, model_name=model_name)

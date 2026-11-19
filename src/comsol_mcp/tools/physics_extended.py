"""Extended domain physics parity tools: electrochemistry, acoustics, PDE, physics helpers, Physics Builder status."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub
from ..catalog.store import BUILTIN_PHYSICS
from ..codegen.physicsbuilder import physics_builder_status


def register_physics_extended_tools(mcp: Any, hub: BackendHub) -> None:
    # --- Electrochemistry full 10-tool suite ---
    @mcp.tool()
    def electrochemistry_get_interfaces() -> dict[str, Any]:
        """List verified electrochemistry/battery/corrosion interface types."""
        ec = {k: v for k, v in BUILTIN_PHYSICS.items() if v.get("category") == "electrochemistry"}
        return {"count": len(ec), "interfaces": ec}

    @mcp.tool()
    def electrochemistry_get_feature_types(interface: str) -> dict[str, Any]:
        """List verified feature types and properties for an electrochemistry interface."""
        spec = BUILTIN_PHYSICS.get(interface)
        if not spec or spec.get("category") != "electrochemistry":
            raise ValueError(f"Unknown electrochemistry interface '{interface}'.")
        return {"interface": interface, "features": spec["features"]}

    @mcp.tool()
    def electrochemistry_add_interface(
        interface: str,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add an electrochemistry physics interface to the model."""
        spec = BUILTIN_PHYSICS.get(interface)
        default_tag = spec["tag_default"] if spec else interface[:4].lower()
        return hub.interactive.physics_add(tag=tag or default_tag, interface=interface, geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def electrochemistry_list_features(physics_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """List all features under an electrochemistry physics interface."""
        return hub.interactive.physics_list_features(physics_tag=physics_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def electrochemistry_add_feature(
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
        """Add a feature or subfeature (via `parent_feature`) to an electrochemistry interface."""
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
    def electrochemistry_set_feature_selection(
        physics_tag: str,
        feature_tag: str,
        selection: list[int] | str,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Assign domain/boundary entity indices or named selection to an electrochemistry feature."""
        return hub.interactive.physics_feature_set(
            physics_tag=physics_tag, feature_tag=feature_tag, properties={}, selection=selection, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def electrochemistry_list_interface_properties(physics_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Inspect interface-level properties of an electrochemistry physics node."""
        return hub.interactive.physics_interface_properties(physics_tag=physics_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def electrochemistry_set_interface_properties(
        physics_tag: str,
        properties: dict[str, Any],
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Set interface-level properties on an electrochemistry physics node."""
        return hub.interactive.physics_interface_properties(physics_tag=physics_tag, set_properties=properties, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def electrochemistry_set_feature_properties(
        physics_tag: str,
        feature_tag: str,
        properties: dict[str, Any],
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Set properties on an electrochemistry feature (reports any rejected property names)."""
        return hub.interactive.physics_feature_set(
            physics_tag=physics_tag, feature_tag=feature_tag, properties=properties, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def electrochemistry_list_feature_properties(physics_tag: str, feature_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Inspect valid property names and values on an electrochemistry feature."""
        return hub.interactive.physics_feature_info(physics_tag=physics_tag, feature_tag=feature_tag, comp_tag=comp_tag, model_name=model_name)

    # --- Physics convenience & boundary helpers (27) ---
    @mcp.tool()
    def physics_list(comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """List all physics interfaces in a component."""
        return hub.interactive.physics_list(comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_get_available() -> dict[str, Any]:
        """List built-in physics interface types and their default tags."""
        return {"count": len(BUILTIN_PHYSICS), "interfaces": {k: {"tag": v["tag_default"], "category": v["category"], "description": v["description"]} for k, v in BUILTIN_PHYSICS.items()}}

    @mcp.tool()
    def physics_get_acoustic_boundary_conditions() -> dict[str, Any]:
        """List common Pressure Acoustics boundary condition feature types and properties."""
        return {"interface": "PressureAcoustics", "boundary_conditions": BUILTIN_PHYSICS["PressureAcoustics"]["features"]}

    @mcp.tool()
    def physics_get_pde_boundary_conditions() -> dict[str, Any]:
        """List common PDE boundary condition feature types and properties."""
        return {
            "CoefficientFormPDE": BUILTIN_PHYSICS["CoefficientFormPDE"]["features"],
            "GeneralFormPDE": BUILTIN_PHYSICS["GeneralFormPDE"]["features"],
            "WeakFormPDE": BUILTIN_PHYSICS["WeakFormPDE"]["features"],
        }

    @mcp.tool()
    def physics_add_electrostatics(tag: str = "es", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add an Electrostatics (`es`) physics interface."""
        return hub.interactive.physics_add(tag=tag, interface="Electrostatics", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_solid_mechanics(tag: str = "solid", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add a Solid Mechanics (`solid`) physics interface."""
        return hub.interactive.physics_add(tag=tag, interface="SolidMechanics", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_heat_transfer(tag: str = "ht", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add a Heat Transfer (`ht`) physics interface."""
        return hub.interactive.physics_add(tag=tag, interface="HeatTransfer", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_laminar_flow(tag: str = "spf", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add a Laminar Flow (`spf`) physics interface."""
        return hub.interactive.physics_add(tag=tag, interface="LaminarFlow", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_pressure_acoustics(tag: str = "acpr", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add a Pressure Acoustics (`acpr`) physics interface."""
        return hub.interactive.physics_add(tag=tag, interface="PressureAcoustics", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_acoustics(interface: str = "PressureAcoustics", tag: str = "acpr", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add any geometry-based acoustic interface by COMSOL type name."""
        return hub.interactive.physics_add(tag=tag, interface=interface, geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_coefficient_form_pde(tag: str = "c", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add a Coefficient Form PDE (`c`) interface."""
        return hub.interactive.physics_add(tag=tag, interface="CoefficientFormPDE", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_general_form_pde(tag: str = "g", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add a General Form PDE (`g`) interface."""
        return hub.interactive.physics_add(tag=tag, interface="GeneralFormPDE", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_add_weak_form_pde(tag: str = "w", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Add a Weak Form PDE (`w`) interface."""
        return hub.interactive.physics_add(tag=tag, interface="WeakFormPDE", geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_configure_boundary(
        physics_tag: str,
        feature_tag: str,
        boundary_type: str,
        selection: list[int] | str,
        properties: Optional[dict[str, Any]] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add and configure a single boundary condition feature on a physics interface."""
        return hub.interactive.physics_feature_add(
            physics_tag=physics_tag,
            feature_tag=feature_tag,
            feature_type=boundary_type,
            selection=selection,
            properties=properties,
            comp_tag=comp_tag,
            model_name=model_name,
        )

    @mcp.tool()
    def physics_configure_acoustic_boundary(
        boundary_type: str,
        selection: list[int] | str,
        properties: Optional[dict[str, Any]] = None,
        physics_tag: str = "acpr",
        feature_tag: Optional[str] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Configure one acoustic boundary condition (`SoundHard`, `Pressure`, `Impedance`, `PlaneWaveRadiation`, etc.)."""
        return hub.interactive.physics_feature_add(
            physics_tag=physics_tag,
            feature_tag=feature_tag or boundary_type.lower()[:6] + "1",
            feature_type=boundary_type,
            selection=selection,
            properties=properties,
            comp_tag=comp_tag,
            model_name=model_name,
        )

    @mcp.tool()
    def physics_setup_acoustic_boundaries(
        boundaries: list[dict[str, Any]],
        physics_tag: str = "acpr",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Configure multiple acoustic boundary conditions in batch."""
        added = [
            hub.interactive.physics_feature_add(
                physics_tag=physics_tag,
                feature_tag=bc.get("tag", f"acbc{i}"),
                feature_type=bc["type"],
                selection=bc.get("selection", "all"),
                properties=bc.get("properties"),
                comp_tag=comp_tag,
                model_name=model_name,
            )
            for i, bc in enumerate(boundaries, start=1)
        ]
        return {"ok": True, "physics": physics_tag, "boundaries": added}

    @mcp.tool()
    def physics_configure_pde_boundary(
        physics_tag: str,
        boundary_type: str,
        selection: list[int] | str,
        properties: Optional[dict[str, Any]] = None,
        feature_tag: Optional[str] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Configure one PDE boundary condition (`DirichletBoundary`, `FluxBoundary`, `ZeroFluxBoundary`, `WeakContribution`)."""
        return hub.interactive.physics_feature_add(
            physics_tag=physics_tag,
            feature_tag=feature_tag or boundary_type.lower()[:6] + "1",
            feature_type=boundary_type,
            selection=selection,
            properties=properties,
            comp_tag=comp_tag,
            model_name=model_name,
        )

    @mcp.tool()
    def physics_setup_pde_boundaries(
        physics_tag: str,
        boundaries: list[dict[str, Any]],
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Configure multiple PDE boundary conditions in batch."""
        added = [
            hub.interactive.physics_feature_add(
                physics_tag=physics_tag,
                feature_tag=bc.get("tag", f"pdebc{i}"),
                feature_type=bc["type"],
                selection=bc.get("selection", "all"),
                properties=bc.get("properties"),
                comp_tag=comp_tag,
                model_name=model_name,
            )
            for i, bc in enumerate(boundaries, start=1)
        ]
        return {"ok": True, "physics": physics_tag, "boundaries": added}

    @mcp.tool()
    def physics_set_material(
        tag: str,
        properties: dict[str, Any],
        domains: Optional[list[int]] = None,
        label: Optional[str] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Assign a material and its physical properties to domains."""
        return hub.interactive.material_add(
            tag=tag, properties=properties, label=label, domains=domains, comp_tag=comp_tag, model_name=model_name
        )

    @mcp.tool()
    def physics_list_features(physics_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """List all features inside a physics interface."""
        return hub.interactive.physics_list_features(physics_tag=physics_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_remove(physics_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Remove a physics interface from a component."""
        return hub.interactive.physics_remove(physics_tag=physics_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def geometry_get_boundaries(geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Return boundary indices for a geometry sequence."""
        return hub.interactive.geometry_boundary_info(geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)

    @mcp.tool()
    def physics_interactive_setup_flow(geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Return boundary summary and prompts needed to configure Laminar Flow inlet/outlet boundaries."""
        binfo = hub.interactive.geometry_boundary_info(geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)
        return {
            "physics": "LaminarFlow",
            "boundaries": binfo,
            "next_call": "physics_setup_flow_boundaries(inlet_selection=[...], inlet_velocity='1[mm/s]', outlet_selection=[...], outlet_pressure='0[Pa]')",
        }

    @mcp.tool()
    def physics_setup_flow_boundaries(
        inlet_selection: list[int] | str,
        outlet_selection: list[int] | str,
        inlet_velocity: str = "1[mm/s]",
        outlet_pressure: str = "0[Pa]",
        physics_tag: str = "spf",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Configure InletBoundary and OutletBoundary for Laminar Flow in one call."""
        inl = hub.interactive.physics_feature_add(
            physics_tag, "inl1", "InletBoundary", selection=inlet_selection, properties={"U0in": inlet_velocity}, comp_tag=comp_tag, model_name=model_name
        )
        out = hub.interactive.physics_feature_add(
            physics_tag, "out1", "OutletBoundary", selection=outlet_selection, properties={"p0": outlet_pressure}, comp_tag=comp_tag, model_name=model_name
        )
        return {"ok": True, "inlet": inl, "outlet": out}

    @mcp.tool()
    def physics_interactive_setup_heat(geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        """Return boundary summary and prompts needed to configure Heat Transfer boundaries."""
        binfo = hub.interactive.geometry_boundary_info(geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)
        return {
            "physics": "HeatTransfer",
            "boundaries": binfo,
            "next_call": "physics_setup_heat_boundaries(temperature_boundaries=[...], flux_boundaries=[...])",
        }

    @mcp.tool()
    def physics_setup_heat_boundaries(
        temperature_boundaries: Optional[list[dict[str, Any]]] = None,
        flux_boundaries: Optional[list[dict[str, Any]]] = None,
        physics_tag: str = "ht",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Configure multiple TemperatureBoundary and HeatFluxBoundary features in one call."""
        added = []
        for idx, tb in enumerate(temperature_boundaries or [], start=1):
            added.append(
                hub.interactive.physics_feature_add(
                    physics_tag,
                    tb.get("tag", f"temp{idx}"),
                    "TemperatureBoundary",
                    selection=tb["selection"],
                    properties={"T0": str(tb.get("T0", "293.15[K]"))},
                    comp_tag=comp_tag,
                    model_name=model_name,
                )
            )
        for idx, fb in enumerate(flux_boundaries or [], start=1):
            added.append(
                hub.interactive.physics_feature_add(
                    physics_tag,
                    fb.get("tag", f"hf{idx}"),
                    "HeatFluxBoundary",
                    selection=fb["selection"],
                    properties={"q0": str(fb.get("q0", "1e4[W/m^2]"))},
                    comp_tag=comp_tag,
                    model_name=model_name,
                )
            )
        return {"ok": True, "physics": physics_tag, "configured": added}

    @mcp.tool()
    def physics_boundary_selection(
        physics_tag: str,
        feature_tag: str,
        selection: list[int] | str,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Assign boundary indices or named selection to an existing physics boundary feature."""
        return hub.interactive.physics_feature_set(
            physics_tag=physics_tag, feature_tag=feature_tag, properties={}, selection=selection, comp_tag=comp_tag, model_name=model_name
        )

    # --- PhysicsBuilder status (1) ---
    @mcp.tool()
    def physicsbuilder_status(prefs_dir: Optional[str] = None) -> dict[str, Any]:
        """Inspect registered `.mphphb` Physics Builder development files in COMSOL prefs."""
        return physics_builder_status(prefs_dir=prefs_dir)

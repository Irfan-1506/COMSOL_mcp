"""Specialized multiphysics domain profile (`physics`): electrochemistry, acoustics, PDEs, multiphysics, Physics Builder."""

from __future__ import annotations

from typing import Any, Optional

from ..backends import BackendHub
from ..catalog.store import BUILTIN_MULTIPHYSICS, BUILTIN_PHYSICS
from ..codegen.physicsbuilder import generate_physics_builder_xml, register_physics_builder


def register_physics_domain_tools(mcp: Any, hub: BackendHub) -> None:
    @mcp.tool()
    def electrochemistry_interfaces() -> dict[str, Any]:
        """List verified electrochemistry/battery physics interfaces and their feature schemas."""
        ec = {k: v for k, v in BUILTIN_PHYSICS.items() if v.get("category") == "electrochemistry"}
        return {"count": len(ec), "interfaces": ec}

    @mcp.tool()
    def electrochemistry_add(
        interface: str = "LithiumIonBatteryMPH",
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add an electrochemistry interface (`LithiumIonBatteryMPH`, `LumpedBattery`, `SecondaryCurrentDistribution`, `TertiaryCurrentDistributionNernstPlanck`)."""
        spec = BUILTIN_PHYSICS.get(interface)
        if not spec or spec.get("category") != "electrochemistry":
            valid = [k for k, v in BUILTIN_PHYSICS.items() if v.get("category") == "electrochemistry"]
            raise ValueError(f"Unknown electrochemistry interface '{interface}'. Valid: {valid}")
        return hub.interactive.physics_add(
            tag=tag or spec["tag_default"],
            interface=interface,
            geom_tag=geom_tag,
            comp_tag=comp_tag,
            model_name=model_name,
        )

    @mcp.tool()
    def acoustics_add(
        interface: str = "PressureAcoustics",
        tag: str = "acpr",
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        boundaries: Optional[list[dict[str, Any]]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add Pressure Acoustics and optionally configure acoustic boundary conditions in one call."""
        res = hub.interactive.physics_add(tag=tag, interface=interface, geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)
        added_bcs = []
        for idx, bc in enumerate(boundaries or [], start=1):
            btag = bc.get("tag", f"acbc{idx}")
            added_bcs.append(
                hub.interactive.physics_feature_add(
                    physics_tag=tag,
                    feature_tag=btag,
                    feature_type=bc["type"],
                    selection=bc.get("selection", "all"),
                    properties=bc.get("properties"),
                    comp_tag=comp_tag,
                    model_name=model_name,
                )
            )
        return {"physics": res, "boundaries": added_bcs}

    @mcp.tool()
    def pde_add(
        form: str = "coefficient",
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        boundaries: Optional[list[dict[str, Any]]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a mathematical PDE interface (`form`: `coefficient`, `general`, or `weak`) with optional BCs."""
        mapping = {
            "coefficient": ("CoefficientFormPDE", "c"),
            "general": ("GeneralFormPDE", "g"),
            "weak": ("WeakFormPDE", "w"),
        }
        key = form.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unknown PDE form '{form}'. Choose: {sorted(mapping)}")
        iface, default_tag = mapping[key]
        ptag = tag or default_tag
        res = hub.interactive.physics_add(tag=ptag, interface=iface, geom_tag=geom_tag, comp_tag=comp_tag, model_name=model_name)
        added_bcs = []
        for idx, bc in enumerate(boundaries or [], start=1):
            added_bcs.append(
                hub.interactive.physics_feature_add(
                    physics_tag=ptag,
                    feature_tag=bc.get("tag", f"pdebc{idx}"),
                    feature_type=bc["type"],
                    selection=bc.get("selection", "all"),
                    properties=bc.get("properties"),
                    comp_tag=comp_tag,
                    model_name=model_name,
                )
            )
        return {"physics": res, "boundaries": added_bcs}

    @mcp.tool()
    def multiphysics_add(
        coupling_type: str,
        tag: Optional[str] = None,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        properties: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a multiphysics coupling (e.g. `ElectromagneticHeating`, `NonIsothermalFlow`, `ThermalExpansion`)."""
        ctag = tag or coupling_type[:4].lower() + "1"
        res = hub.interactive.multiphysics_add(
            tag=ctag,
            coupling_type=coupling_type,
            geom_tag=geom_tag,
            comp_tag=comp_tag,
            properties=properties,
            model_name=model_name,
        )
        res["known_couplings"] = sorted(BUILTIN_MULTIPHYSICS.keys())
        return res

    @mcp.tool()
    def physicsbuilder_generate(
        output_path: str,
        interface_type: str,
        label: str,
        field_var: str = "u",
        weak_expression: str = "-d*test(ux)*ux - d*test(uy)*uy + f*test(u)",
        diffusivity_default: str = "1",
        source_default: str = "0",
    ) -> dict[str, Any]:
        """Generate a custom COMSOL Physics Builder `.mphphb` XML definition file."""
        return generate_physics_builder_xml(
            output_path=output_path,
            interface_type=interface_type,
            label=label,
            field_var=field_var,
            weak_expression=weak_expression,
            diffusivity_default=diffusivity_default,
            source_default=source_default,
        )

    @mcp.tool()
    def physicsbuilder_register(
        mphphb_path: str,
        prefs_dir: Optional[str] = None,
        unregister: bool = False,
    ) -> dict[str, Any]:
        """Register or unregister a `.mphphb` custom physics file in `comsol.prefs` and `comsolserver.prefs`."""
        return register_physics_builder(mphphb_path=mphphb_path, prefs_dir=prefs_dir, unregister=unregister)

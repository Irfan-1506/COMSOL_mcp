"""Rule-based validation of COMSOL model completeness, materials, boundaries, mesh, and studies."""

from __future__ import annotations

from typing import Any

from ..catalog.store import BUILTIN_PHYSICS

# Minimum boundary conditions expected per physics interface to avoid underconstrained solves
_REQUIRED_ANY_BC: dict[str, list[str]] = {
    "HeatTransfer": ["TemperatureBoundary", "HeatFluxBoundary", "ConvectiveHeatFlux"],
    "Electrostatics": ["Ground", "ElectricPotential", "Terminal"],
    "LaminarFlow": ["InletBoundary", "OutletBoundary"],
    "SolidMechanics": ["Fixed", "PrescribedDisplacement"],
    "PressureAcoustics": ["Pressure", "NormalVelocity", "NormalAcceleration", "Impedance", "PlaneWaveRadiation"],
    "LithiumIonBatteryMPH": ["ElectricGround", "ElectrodePotential", "ElectrodeCurrent"],
    "SecondaryCurrentDistribution": ["ElectrodeSurface"],
}

_WARN_MISSING_BC: dict[str, list[str]] = {
    "Electrostatics": ["Ground"],
    "LaminarFlow": ["OutletBoundary"],
    "SolidMechanics": ["Fixed"],
}


def validate_model_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate an inspected COMSOL model dict (from `mph` or `dryrun` backend)."""
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: dict[str, bool] = {}

    components = snapshot.get("components") or {}
    checks["has_component"] = len(components) > 0
    if not components:
        errors.append({"stage": "component", "message": "Model has no component (e.g. comp1)."})

    has_geom = False
    has_built_geom = False
    has_material = False
    has_physics = False
    has_mesh = False

    for ctag, comp in components.items():
        geoms = comp.get("geometries") or {}
        if geoms:
            has_geom = True
            for gtag, gdata in geoms.items():
                feats = gdata.get("features") or {}
                if not feats:
                    errors.append({"stage": "geometry", "message": f"Geometry '{ctag}/{gtag}' has no features."})
                if gdata.get("built", True):
                    has_built_geom = True
                else:
                    warnings.append({"stage": "geometry", "message": f"Geometry '{ctag}/{gtag}' has unbuilt edits; run `geometry_build`."})

        materials = comp.get("materials") or {}
        if materials:
            has_material = True
        material_props_present: set[str] = set()
        for mdata in materials.values():
            props = mdata.get("properties") or {}
            material_props_present.update(k.lower() for k in props.keys())

        physics_map = comp.get("physics") or {}
        if physics_map:
            has_physics = True
        for ptag, pdata in physics_map.items():
            ptype = pdata.get("type", "")
            feats = pdata.get("features") or {}
            feat_types = {f.get("type", "") for f in feats.values() if isinstance(f, dict)}

            # Material property coverage check (when properties are visible in snapshot)
            spec = BUILTIN_PHYSICS.get(ptype)
            if spec and spec.get("required_material_props"):
                if not materials:
                    errors.append(
                        {
                            "stage": "material",
                            "message": f"Physics '{ctag}/{ptag}' ({ptype}) requires material properties {spec['required_material_props']}, but no material is defined.",
                        }
                    )
                elif material_props_present:
                    missing_props = [p for p in spec["required_material_props"] if p.lower() not in material_props_present]
                    if missing_props:
                        warnings.append(
                            {
                                "stage": "material",
                                "message": f"Physics '{ctag}/{ptag}' ({ptype}) may be missing material properties: {missing_props}.",
                            }
                        )

            # Boundary condition checks
            req_any = _REQUIRED_ANY_BC.get(ptype)
            if req_any and not any(bc in feat_types for bc in req_any):
                errors.append(
                    {
                        "stage": "boundary",
                        "message": f"Physics '{ctag}/{ptag}' ({ptype}) needs at least one boundary condition from {req_any}.",
                    }
                )
            for warn_bc in _WARN_MISSING_BC.get(ptype, []):
                if warn_bc not in feat_types:
                    warnings.append(
                        {
                            "stage": "boundary",
                            "message": f"Physics '{ctag}/{ptag}' ({ptype}) has no '{warn_bc}' reference condition (risk of singular matrix).",
                        }
                    )

        meshes = comp.get("meshes") or {}
        if meshes:
            has_mesh = True

    checks["has_geometry"] = has_geom
    checks["geometry_built"] = has_built_geom
    checks["has_material"] = has_material
    checks["has_physics"] = has_physics
    checks["has_mesh"] = has_mesh

    if not has_geom:
        errors.append({"stage": "geometry", "message": "No geometry defined."})
    if not has_physics:
        errors.append({"stage": "physics", "message": "No physics interface defined."})
    if not has_mesh:
        warnings.append({"stage": "mesh", "message": "No mesh sequence built yet."})

    studies = snapshot.get("studies") or {}
    checks["has_study"] = len(studies) > 0
    if not studies:
        warnings.append({"stage": "study", "message": "No study defined yet."})

    solutions = snapshot.get("solutions") or []
    checks["has_solution"] = len(solutions) > 0

    return {
        "model": snapshot.get("name"),
        "valid_for_solve": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }

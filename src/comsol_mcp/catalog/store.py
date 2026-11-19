"""Offline COMSOL API catalog backed by built-in verified specs + local XML extraction.

Zero proprietary vendor XMLs or PDFs are committed to Git. Users with a local
COMSOL installation can run `build_catalog_from_install()` (or `comsol-mcp
catalog-build`) to extract feature/property schemas directly from their own
`<COMSOL_HOME>/data/completion/*.xml` files into `catalog_cache/`.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Built-in baseline schema for core physics, acoustics, PDE, electrochemistry & multiphysics
BUILTIN_PHYSICS: dict[str, dict[str, Any]] = {
    "HeatTransfer": {
        "tag_default": "ht",
        "category": "heat",
        "description": "Heat Transfer in Solids / Fluids",
        "required_material_props": ["thermalconductivity", "density", "heatcapacity"],
        "features": {
            "TemperatureBoundary": {"dim_offset": -1, "properties": ["T0"]},
            "HeatFluxBoundary": {"dim_offset": -1, "properties": ["q0", "HeatFluxType", "h", "Text"]},
            "ConvectiveHeatFlux": {"dim_offset": -1, "properties": ["h", "Text"]},
            "HeatSource": {"dim_offset": 0, "properties": ["Q0"]},
            "ThermalInsulation": {"dim_offset": -1, "properties": []},
        },
    },
    "Electrostatics": {
        "tag_default": "es",
        "category": "acdc",
        "description": "Electrostatics (Gauss's law / electric potential V)",
        "required_material_props": ["relpermittivity"],
        "features": {
            "ElectricPotential": {"dim_offset": -1, "properties": ["V0"]},
            "Ground": {"dim_offset": -1, "properties": []},
            "Terminal": {"dim_offset": -1, "properties": ["TerminalType", "V0", "Q0"]},
            "SurfaceChargeDensity": {"dim_offset": -1, "properties": ["rhoqs"]},
            "SpaceChargeDensity": {"dim_offset": 0, "properties": ["rhoq"]},
        },
    },
    "MagneticFields": {
        "tag_default": "mf",
        "category": "acdc",
        "description": "Magnetic Fields (Ampere's law / magnetic vector potential A)",
        "required_material_props": ["relpermeability", "electricconductivity"],
        "features": {
            "AmpereLaw": {"dim_offset": 0, "properties": ["ConstitutiveRelationBH"]},
            "Coil": {"dim_offset": 0, "properties": ["ICoil", "N", "ConductorModel"]},
            "MagneticInsulation": {"dim_offset": -1, "properties": []},
            "ExternalCurrentDensity": {"dim_offset": 0, "properties": ["Je"]},
        },
    },
    "LaminarFlow": {
        "tag_default": "spf",
        "category": "cfd",
        "description": "Single-Phase Laminar Flow (Navier-Stokes)",
        "required_material_props": ["density", "dynamicviscosity"],
        "features": {
            "InletBoundary": {"dim_offset": -1, "properties": ["U0in", "U0", "BoundaryCondition"]},
            "OutletBoundary": {"dim_offset": -1, "properties": ["p0", "BoundaryCondition"]},
            "Wall": {"dim_offset": -1, "properties": ["BoundaryCondition"]},
            "Symmetry": {"dim_offset": -1, "properties": []},
        },
    },
    "SolidMechanics": {
        "tag_default": "solid",
        "category": "structural",
        "description": "Structural Solid Mechanics",
        "required_material_props": ["youngsmodulus", "poissonsratio", "density"],
        "features": {
            "Fixed": {"dim_offset": -1, "properties": []},
            "BoundaryLoad": {"dim_offset": -1, "properties": ["FperArea", "LoadType"]},
            "BodyLoad": {"dim_offset": 0, "properties": ["FperVol"]},
            "PrescribedDisplacement": {"dim_offset": -1, "properties": ["u0"]},
        },
    },
    "PressureAcoustics": {
        "tag_default": "acpr",
        "category": "acoustics",
        "description": "Pressure Acoustics, Frequency Domain",
        "required_material_props": ["density", "soundspeed"],
        "features": {
            "SoundHard": {"dim_offset": -1, "properties": []},
            "SoundSoft": {"dim_offset": -1, "properties": []},
            "Pressure": {"dim_offset": -1, "properties": ["p0"]},
            "Impedance": {"dim_offset": -1, "properties": ["Zn"]},
            "NormalVelocity": {"dim_offset": -1, "properties": ["nvel"]},
            "NormalAcceleration": {"dim_offset": -1, "properties": ["nacc"]},
            "PlaneWaveRadiation": {"dim_offset": -1, "properties": []},
            "SphericalWaveRadiation": {"dim_offset": -1, "properties": []},
        },
    },
    "CoefficientFormPDE": {
        "tag_default": "c",
        "category": "pde",
        "description": "Coefficient Form PDE",
        "required_material_props": [],
        "features": {
            "CoefficientFormPDE": {"dim_offset": 0, "properties": ["c", "a", "f", "da", "ea", "alpha", "beta", "gamma"]},
            "DirichletBoundary": {"dim_offset": -1, "properties": ["r"]},
            "FluxBoundary": {"dim_offset": -1, "properties": ["g", "q"]},
            "ZeroFluxBoundary": {"dim_offset": -1, "properties": []},
            "WeakContribution": {"dim_offset": 0, "properties": ["weak"]},
        },
    },
    "GeneralFormPDE": {
        "tag_default": "g",
        "category": "pde",
        "description": "General Form PDE",
        "required_material_props": [],
        "features": {
            "GeneralFormPDE": {"dim_offset": 0, "properties": ["Gamma", "f", "da", "ea"]},
            "DirichletBoundary": {"dim_offset": -1, "properties": ["r"]},
            "FluxBoundary": {"dim_offset": -1, "properties": ["g", "q"]},
            "ZeroFluxBoundary": {"dim_offset": -1, "properties": []},
        },
    },
    "WeakFormPDE": {
        "tag_default": "w",
        "category": "pde",
        "description": "Weak Form PDE",
        "required_material_props": [],
        "features": {
            "WeakFormPDE": {"dim_offset": 0, "properties": ["weak"]},
            "DirichletBoundary": {"dim_offset": -1, "properties": ["r"]},
            "WeakContribution": {"dim_offset": -1, "properties": ["weak"]},
        },
    },
    "LithiumIonBatteryMPH": {
        "tag_default": "liion",
        "category": "electrochemistry",
        "description": "Lithium-Ion Battery (porous electrode + electrolyte transport)",
        "required_material_props": [],
        "features": {
            "PorousElectrode": {"dim_offset": 0, "properties": ["sigma_s", "epss", "epsl"]},
            "Electrolyte": {"dim_offset": 0, "properties": ["sigmal", "Dl", "tplus"]},
            "Separator": {"dim_offset": 0, "properties": ["epsl"]},
            "ElectricGround": {"dim_offset": -1, "properties": []},
            "ElectrodeCurrent": {"dim_offset": -1, "properties": ["I_app"]},
            "ElectrodePotential": {"dim_offset": -1, "properties": ["phi_s_ext"]},
            "PorousElectrodeReaction": {"dim_offset": 0, "properties": ["i0_ref", "alpha_a", "alpha_c"]},
        },
    },
    "LumpedBattery": {
        "tag_default": "lb",
        "category": "electrochemistry",
        "description": "Lumped Battery (0D/3D thermal-electrochemical equivalent circuit)",
        "required_material_props": [],
        "features": {
            "CellEquilibriumPotential": {"dim_offset": 0, "properties": ["E_ocv"]},
            "VoltageLosses": {"dim_offset": 0, "properties": ["eta_IR", "tau", "J0"]},
        },
    },
    "SecondaryCurrentDistribution": {
        "tag_default": "siec",
        "category": "electrochemistry",
        "description": "Secondary Current Distribution (Butler-Volmer electrode kinetics)",
        "required_material_props": [],
        "features": {
            "Electrolyte": {"dim_offset": 0, "properties": ["sigmal"]},
            "ElectrodeSurface": {"dim_offset": -1, "properties": ["phi_s_ext"]},
            "ElectrodeReaction": {"dim_offset": -1, "properties": ["i0", "Eeq", "alpha_a", "alpha_c"]},
            "Insulation": {"dim_offset": -1, "properties": []},
        },
    },
    "TertiaryCurrentDistributionNernstPlanck": {
        "tag_default": "tcd",
        "category": "electrochemistry",
        "description": "Tertiary Current Distribution, Nernst-Planck",
        "required_material_props": [],
        "features": {
            "Electrolyte": {"dim_offset": 0, "properties": ["D", "z"]},
            "ElectrodeSurface": {"dim_offset": -1, "properties": ["phi_s_ext"]},
            "Concentration": {"dim_offset": -1, "properties": ["c0"]},
        },
    },
    "DarcyLaw": {
        "tag_default": "dl",
        "category": "porous_media",
        "description": "Darcy's Law (Porous Media Flow)",
        "required_material_props": ["density", "dynamicviscosity"],
        "features": {
            "FluidAndMatrixProperties": {"dim_offset": 0, "properties": ["kappa", "epsilon"]},
            "Pressure": {"dim_offset": -1, "properties": ["p0"]},
            "Inlet": {"dim_offset": -1, "properties": ["U0"]},
            "NoFlow": {"dim_offset": -1, "properties": []},
        },
    },
}

BUILTIN_MULTIPHYSICS: dict[str, dict[str, Any]] = {
    "ElectromagneticHeating": {"description": "Joule / electromagnetic resistive heating coupling (ec/mf -> ht)"},
    "NonIsothermalFlow": {"description": "Conjugate heat transfer + fluid flow coupling (ht <-> spf)"},
    "ThermalExpansion": {"description": "Thermal stress / strain coupling (ht -> solid)"},
    "AcousticStructureBoundary": {"description": "Acoustic-structure interaction boundary coupling (acpr <-> solid)"},
    "ElectrochemicalHeating": {"description": "Electrochemical heat generation coupling (liion/siec -> ht)"},
}


def _parse_completion_xml(xml_path: Path) -> dict[str, Any]:
    """Parse one COMSOL `data/completion/*.xml` file and resolve its `<Properties>` tokens."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    prop_dict: dict[str, dict[str, Any]] = {}
    for props_node in root.iter("Properties"):
        for child in props_node:
            prop_dict[child.tag] = {
                "name": child.attrib.get("name", child.tag),
                "type": child.attrib.get("type", ""),
                "default": child.attrib.get("default", ""),
                "descr": child.attrib.get("descr", "").replace("_", " "),
                "values": child.attrib.get("values", ""),
            }

    features: dict[str, dict[str, Any]] = {}
    for elem in root.iter():
        if elem.tag in {"COMSOLCompletionData", "Properties", "description", "ModelEntityImage"}:
            continue
        raw_props = elem.attrib.get("props")
        if not raw_props:
            continue
        tokens = raw_props.split()
        resolved = [prop_dict[t] for t in tokens if t in prop_dict]
        if not resolved:
            continue
        desc_el = elem.find("description")
        desc = (desc_el.text.strip() if desc_el is not None and desc_el.text else "") or elem.attrib.get("descr", "").replace("_", " ")
        key = elem.tag
        if key not in features or len(resolved) > len(features[key]["properties"]):
            features[key] = {
                "id": elem.attrib.get("id", ""),
                "topic": elem.attrib.get("topic", ""),
                "description": desc,
                "properties": resolved,
            }

    return {"source": xml_path.name, "feature_count": len(features), "property_tokens": len(prop_dict), "features": features}


def build_catalog_from_install(comsol_home: Path, output_dir: Path) -> dict[str, Any]:
    """Extract offline feature & property schemas from `<COMSOL_HOME>/data/completion/*.xml`."""
    completion_dir = comsol_home / "data" / "completion"
    if not completion_dir.is_dir():
        raise FileNotFoundError(f"COMSOL completion XML directory not found at '{completion_dir}'.")

    output_dir.mkdir(parents=True, exist_ok=True)
    layers: dict[str, dict[str, Any]] = {}
    total_features = 0
    total_properties = 0

    for xml_file in sorted(completion_dir.glob("*.xml")):
        layer_name = xml_file.stem
        try:
            parsed = _parse_completion_xml(xml_file)
        except Exception:
            continue
        if parsed["feature_count"] == 0:
            continue
        (output_dir / f"{layer_name}.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        layers[layer_name] = {
            "source": xml_file.name,
            "feature_count": parsed["feature_count"],
            "property_tokens": parsed["property_tokens"],
        }
        total_features += parsed["feature_count"]
        total_properties += parsed["property_tokens"]

    meta = {
        "generated_at": datetime.now().isoformat(),
        "comsol_home": str(comsol_home),
        "layer_count": len(layers),
        "total_features": total_features,
        "total_property_tokens": total_properties,
        "layers": layers,
    }
    (output_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


class CatalogStore:
    """Query interface over built-in physics specs + locally extracted COMSOL completion XMLs."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self._layer_cache: dict[str, dict[str, Any]] = {}

    def _load_meta(self) -> Optional[dict[str, Any]]:
        meta_file = self.cache_dir / "meta.json"
        if not meta_file.is_file():
            return None
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_layer(self, layer: str) -> Optional[dict[str, Any]]:
        if layer in self._layer_cache:
            return self._layer_cache[layer]
        path = self.cache_dir / f"{layer}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        self._layer_cache[layer] = data
        return data

    def info(self) -> dict[str, Any]:
        meta = self._load_meta()
        return {
            "builtin_physics_count": len(BUILTIN_PHYSICS),
            "builtin_multiphysics_count": len(BUILTIN_MULTIPHYSICS),
            "builtin_physics": sorted(BUILTIN_PHYSICS.keys()),
            "builtin_multiphysics": sorted(BUILTIN_MULTIPHYSICS.keys()),
            "local_xml_catalog_loaded": meta is not None,
            "cache_dir": str(self.cache_dir),
            "local_xml_meta": meta,
        }

    def search(self, query: str, *, layer: Optional[str] = None, limit: int = 25) -> dict[str, Any]:
        q = query.strip().lower()
        hits: list[dict[str, Any]] = []

        if not layer or layer in {"physics", "builtin"}:
            for pname, pinfo in BUILTIN_PHYSICS.items():
                if q in pname.lower() or q in pinfo["description"].lower() or q in pinfo["category"].lower():
                    hits.append(
                        {
                            "source": "builtin_physics",
                            "name": pname,
                            "category": pinfo["category"],
                            "description": pinfo["description"],
                            "feature_count": len(pinfo["features"]),
                        }
                    )
                for fname, finfo in pinfo["features"].items():
                    if q in fname.lower():
                        hits.append(
                            {
                                "source": "builtin_feature",
                                "physics": pname,
                                "name": fname,
                                "properties": finfo["properties"],
                            }
                        )
            for mp_name, mp_info in BUILTIN_MULTIPHYSICS.items():
                if q in mp_name.lower() or q in mp_info["description"].lower():
                    hits.append({"source": "builtin_multiphysics", "name": mp_name, "description": mp_info["description"]})

        meta = self._load_meta()
        if meta:
            target_layers = [layer] if layer and layer in meta.get("layers", {}) else sorted(meta.get("layers", {}).keys())
            for lname in target_layers:
                ldata = self._load_layer(lname)
                if not ldata:
                    continue
                for fname, finfo in ldata.get("features", {}).items():
                    if q in fname.lower() or q in finfo.get("description", "").lower():
                        hits.append(
                            {
                                "source": f"xml:{lname}",
                                "name": fname,
                                "id": finfo.get("id", ""),
                                "description": finfo.get("description", ""),
                                "property_count": len(finfo.get("properties", [])),
                            }
                        )
                        if len(hits) >= limit:
                            break
                if len(hits) >= limit:
                    break

        return {"query": query, "count": len(hits[:limit]), "results": hits[:limit]}

    def get_features(self, interface_or_layer: str) -> dict[str, Any]:
        if interface_or_layer in BUILTIN_PHYSICS:
            p = BUILTIN_PHYSICS[interface_or_layer]
            return {"source": "builtin_physics", "name": interface_or_layer, **p}
        ldata = self._load_layer(interface_or_layer)
        if ldata:
            return {
                "source": f"xml:{interface_or_layer}",
                "name": interface_or_layer,
                "feature_count": ldata["feature_count"],
                "features": sorted(ldata["features"].keys()),
            }
        raise ValueError(
            f"Unknown interface or XML layer '{interface_or_layer}'. Built-in physics: {sorted(BUILTIN_PHYSICS.keys())}"
        )

    def get_properties(self, feature_name: str, *, layer: Optional[str] = None) -> dict[str, Any]:
        # Check built-in physics features first
        for pname, pinfo in BUILTIN_PHYSICS.items():
            if feature_name in pinfo["features"]:
                return {
                    "source": "builtin_physics",
                    "physics": pname,
                    "feature": feature_name,
                    **pinfo["features"][feature_name],
                }
        # Check extracted XML layers
        meta = self._load_meta()
        if meta:
            target_layers = [layer] if layer else sorted(meta.get("layers", {}).keys())
            for lname in target_layers:
                ldata = self._load_layer(lname)
                if ldata and feature_name in ldata.get("features", {}):
                    finfo = ldata["features"][feature_name]
                    return {"source": f"xml:{lname}", "feature": feature_name, **finfo}
        raise ValueError(f"Feature '{feature_name}' not found in built-in or local XML catalog.")

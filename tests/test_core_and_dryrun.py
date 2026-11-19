"""Tests for interactive core workflow, versioning, model diff, dry-run backend, and validation."""

from __future__ import annotations

from pathlib import Path

from comsol_mcp.server import ServerBundle
from comsol_mcp.validation import validate_model_snapshot


def test_full_dryrun_modeling_lifecycle(dryrun_bundle: ServerBundle, tmp_path: Path) -> None:
    backend = dryrun_bundle.hub.interactive
    assert dryrun_bundle.hub.interactive_name == "dryrun"

    assert backend.start(cores=2)["connected"] is True
    assert backend.model_create("thermal_chip")["model"] == "thermal_chip"
    backend.param_set("L", "20[mm]", "Chip length")
    backend.geometry_add("Block", {"size": ["L", "L", "2[mm]"]}, dim=3)

    # Validate before geometry_build & boundaries -> expect error + warning
    early_check = validate_model_snapshot(backend.model_inspect())
    assert early_check["valid_for_solve"] is False

    backend.geometry_build()
    backend.selection_create("top_face", "Box", {"zmin": "1.9[mm]"})
    backend.material_add(
        "si",
        {"thermalconductivity": "130[W/(m*K)]", "density": "2329[kg/m^3]", "heatcapacity": "700[J/(kg*K)]"},
        label="Silicon",
    )
    backend.physics_add("ht", "HeatTransfer")
    backend.physics_feature_add("ht", "temp1", "TemperatureBoundary", selection=[1], properties={"T0": "293.15[K]"})
    backend.physics_feature_add("ht", "flux1", "HeatFluxBoundary", selection="top_face", properties={"q0": "1e5[W/m^2]"})
    backend.mesh_build(size=4)
    backend.study_create("std1", "Stationary")

    # Now validation should pass cleanly
    pre_solve = validate_model_snapshot(backend.model_inspect())
    assert pre_solve["valid_for_solve"] is True
    assert pre_solve["error_count"] == 0

    solved = backend.study_solve("std1")
    assert solved["status"] == "completed"
    ev = backend.results_evaluate("T")
    assert ev["max"] > ev["min"]

    export_file = tmp_path / "exports" / "temp.csv"
    exp = backend.results_export("data", str(export_file))
    assert Path(exp["output"]).is_file()

    # Save versioned copies
    saved = backend.model_save(versioned=True, tag="v1")
    assert Path(saved["path"]).is_file()
    assert Path(saved["latest"]).is_file()

    # Clone & diff
    backend.model_clone("thermal_chip", "thermal_chip_v2")
    backend.param_set("L", "30[mm]", model_name="thermal_chip_v2")
    diff = backend.model_diff("thermal_chip", "thermal_chip_v2")
    assert diff["identical"] is False
    assert "parameters" in diff["differences"]

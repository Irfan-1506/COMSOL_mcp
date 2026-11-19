"""Verify 100% tool-name parity across all 135 classic COMSOL-MCP tools plus end-to-end execution."""

from __future__ import annotations

from pathlib import Path

from comsol_mcp.compat import list_registered_tools
from comsol_mcp.server import ServerBundle

ALL_135_CLASSIC_TOOLS: set[str] = {
    # Knowledge (8)
    "docs_get", "docs_list", "physics_get_guide", "troubleshoot", "modeling_best_practices",
    "pdf_search", "pdf_search_status", "pdf_list_modules",
    # Audit (4)
    "model_audit", "model_diff", "model_export_java", "geometry_boundary_info",
    # Electrochemistry (10)
    "electrochemistry_get_interfaces", "electrochemistry_get_feature_types", "electrochemistry_add_interface",
    "electrochemistry_list_features", "electrochemistry_add_feature", "electrochemistry_set_feature_selection",
    "electrochemistry_list_interface_properties", "electrochemistry_set_interface_properties",
    "electrochemistry_set_feature_properties", "electrochemistry_list_feature_properties",
    # Geometry (15)
    "geometry_list", "geometry_create", "geometry_add_feature", "geometry_add_block",
    "geometry_add_cylinder", "geometry_add_sphere", "geometry_add_rectangle", "geometry_add_circle",
    "geometry_boolean_union", "geometry_boolean_difference", "geometry_import", "geometry_build",
    "geometry_list_features", "geometry_create_box_selection", "geometry_create_side_selections",
    # Mesh (4)
    "mesh_list", "mesh_create_sequence", "mesh_create", "mesh_info",
    # Model (11)
    "model_load", "model_create", "model_create_component", "model_list_components", "model_save",
    "model_save_version", "model_list", "model_set_current", "model_clone", "model_remove", "model_inspect",
    # Modify (18)
    "physics_feature_info", "physics_feature_create", "physics_feature_set", "physics_feature_toggle",
    "physics_feature_delete", "solver_feature_list", "solver_feature_set", "solver_feature_toggle",
    "results_node_create", "results_node_set", "results_node_delete", "results_numerical_evaluate",
    "results_interpolate", "function_create", "function_set", "material_create", "material_set", "material_delete",
    # Parameters (5)
    "param_get", "param_set", "param_list", "param_sweep_setup", "param_description",
    # Physics (29)
    "physics_list", "physics_get_available", "physics_get_acoustic_boundary_conditions",
    "physics_get_pde_boundary_conditions", "physics_add", "physics_add_electrostatics",
    "physics_add_solid_mechanics", "physics_add_heat_transfer", "physics_add_laminar_flow",
    "physics_add_pressure_acoustics", "physics_add_acoustics", "physics_add_coefficient_form_pde",
    "physics_add_general_form_pde", "physics_add_weak_form_pde", "physics_configure_boundary",
    "physics_configure_acoustic_boundary", "physics_setup_acoustic_boundaries",
    "physics_configure_pde_boundary", "physics_setup_pde_boundaries", "physics_set_material",
    "multiphysics_add", "physics_list_features", "physics_remove", "geometry_get_boundaries",
    "physics_interactive_setup_flow", "physics_setup_flow_boundaries",
    "physics_interactive_setup_heat", "physics_setup_heat_boundaries", "physics_boundary_selection",
    # PhysicsBuilder (3)
    "physicsbuilder_generate", "physicsbuilder_register", "physicsbuilder_status",
    # Results (8)
    "results_evaluate", "results_global_evaluate", "results_inner_values", "results_outer_values",
    "results_export_data", "results_export_image", "results_exports_list", "results_plots_list",
    # Session (4)
    "comsol_start", "comsol_connect", "comsol_disconnect", "comsol_status",
    # Static catalog (7)
    "static_catalog_info", "static_catalog_search", "static_catalog_features", "static_catalog_properties",
    "static_catalog_variables", "static_catalog_discretization", "static_catalog_layer",
    # Study (9)
    "study_list", "study_create", "study_solve", "study_solve_async", "study_get_progress",
    "study_cancel", "study_wait", "solutions_list", "datasets_list",
}


def test_all_135_classic_tools_registered(dryrun_bundle: ServerBundle) -> None:
    assert len(ALL_135_CLASSIC_TOOLS) == 135
    registered = set(list_registered_tools(dryrun_bundle.mcp))
    missing = ALL_135_CLASSIC_TOOLS - registered
    assert missing == set(), f"Missing classic tools: {sorted(missing)}"


def test_extended_parity_tools_execution(dryrun_bundle: ServerBundle, tmp_path: Path) -> None:
    tools = dryrun_bundle.mcp._tool_manager._tools

    def call(tool_name: str, /, **kwargs):
        return tools[tool_name].fn(**kwargs)

    call("comsol_start")
    call("model_create", name="parity_demo")
    call("model_create_component", tag="comp1")
    assert "comp1" in call("model_list_components")["components"]

    call("param_set", name="L", expression="10[mm]", description="len")
    assert call("param_get", name="L")["expression"] == "10[mm]"
    assert call("param_description", name="L", description="updated")["description"] == "updated"

    call("geometry_create", geom_tag="geom1", dim=3)
    call("geometry_add_block", size=["L", "L", "2[mm]"], tag="blk1")
    call("geometry_add_cylinder", r="1[mm]", h="2[mm]", tag="cyl1")
    call("geometry_boolean_difference", add_objects=["blk1"], subtract_objects=["cyl1"], tag="dif1")
    call("geometry_build")
    call("geometry_create_side_selections", bounds={"xmin": 0.0, "xmax": 0.01})
    assert call("geometry_boundary_info")["boundary_count"] == 6

    call("physics_add_heat_transfer")
    call("physics_setup_heat_boundaries", temperature_boundaries=[{"selection": [1], "T0": "300[K]"}])
    call("electrochemistry_add_interface", interface="LithiumIonBatteryMPH")
    call("electrochemistry_add_feature", physics_tag="liion", feature_tag="pe1", feature_type="PorousElectrode")
    call("electrochemistry_set_feature_properties", physics_tag="liion", feature_tag="pe1", properties={"sigma_s": "100"})
    assert call("electrochemistry_list_feature_properties", physics_tag="liion", feature_tag="pe1")["properties"]["sigma_s"] == "100"

    call("mesh_create", size=4)
    assert call("mesh_info")["num_elements"] > 0

    call("study_create", study_tag="std1", study_type="Stationary")
    call("param_sweep_setup", study_tag="std1", parameter_name="L", values=["10[mm]", "20[mm]"])
    call("study_solve_async", study_tag="std1")
    assert call("study_wait")["solver"]["status"] == "completed"
    assert len(call("solutions_list")["solutions"]) == 1
    assert len(call("datasets_list")["datasets"]) == 1

    assert call("results_global_evaluate", expression="T")["value"] > 0
    assert len(call("results_interpolate", expression="T", coordinates=[[0.0, 0.0, 0.0], [0.005, 0.005, 0.001]])["values"]) == 2

    java_out = tmp_path / "exported.java"
    assert Path(call("model_export_java", output_path=str(java_out))["java_path"]).is_file()
    assert call("model_audit")["summary"]["component_count"] == 1

    assert len(call("static_catalog_variables", physics_interface="HeatTransfer")["variables"]) >= 2
    assert "shape" in call("static_catalog_discretization", physics_interface="HeatTransfer")["discretization"]
    assert "workflow" in call("docs_list")["topics"]
    assert "files" in call("physicsbuilder_status", prefs_dir=str(tmp_path / "prefs"))

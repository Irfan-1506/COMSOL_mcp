"""Tests for offline static catalog, local XML extraction, Java codegen, and Physics Builder."""

from __future__ import annotations

from pathlib import Path

from comsol_mcp.catalog import CatalogStore, build_catalog_from_install
from comsol_mcp.codegen import generate_physics_builder_xml, register_physics_builder, write_model_java
from comsol_mcp.config import discover_comsol_home


def test_builtin_catalog_lookup(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "cat")
    info = store.info()
    assert info["builtin_physics_count"] >= 10

    search = store.search("Lithium")
    assert any(r["name"] == "LithiumIonBatteryMPH" for r in search["results"])

    props = store.get_properties("HeatFluxBoundary")
    assert "q0" in props["properties"]


def test_xml_catalog_extraction_from_synthetic_and_optional_local_comsol(tmp_path: Path) -> None:
    # Synthetic COMSOL completion XML test (always runs offline)
    fake_home = tmp_path / "FakeComsol"
    comp_dir = fake_home / "data" / "completion"
    comp_dir.mkdir(parents=True)
    (comp_dir / "geom.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<COMSOLCompletionData>
  <model.geom>
    <Block id="blk" descr="Block" props="aaa bbb">
      <description>Create a 3D rectangular block.</description>
    </Block>
    <Properties>
      <aaa name="size" type="DoubleArray" default="1 1 1" descr="Size" />
      <bbb name="pos" type="DoubleArray" default="0 0 0" descr="Position" />
    </Properties>
  </model.geom>
</COMSOLCompletionData>
""",
        encoding="utf-8",
    )
    out = tmp_path / "catalog_cache"
    meta = build_catalog_from_install(fake_home, out)
    assert meta["layer_count"] == 1
    assert meta["total_features"] == 1

    store = CatalogStore(out)
    block = store.get_properties("Block")
    assert block["source"] == "xml:geom"
    assert [p["name"] for p in block["properties"]] == ["size", "pos"]

    # Bonus: if real COMSOL is installed locally, verify real XML extraction works too
    real_home = discover_comsol_home()
    if real_home and (real_home / "data" / "completion").is_dir():
        real_out = tmp_path / "real_catalog_cache"
        real_meta = build_catalog_from_install(real_home, real_out)
        assert real_meta["layer_count"] >= 5
        assert real_meta["total_features"] >= 50


def test_offline_java_codegen_and_physicsbuilder(tmp_path: Path) -> None:
    java_file = tmp_path / "ChipThermal.java"
    res = write_model_java(
        str(java_file),
        class_name="ChipThermal",
        spec={
            "dim": 3,
            "parameters": {"L": "10[mm]"},
            "geometries": [{"type": "Block", "tag": "blk1", "params": {"size": ["L", "L", "2[mm]"]}}],
            "materials": [{"tag": "mat1", "properties": {"thermalconductivity": "130[W/(m*K)]"}}],
            "physics": [{"tag": "ht", "interface": "HeatTransfer"}],
            "studies": [{"tag": "std1", "type": "Stationary"}],
            "save_path": "chip.mph",
        },
    )
    assert res["ok"] is True
    src = java_file.read_text(encoding="utf-8")
    assert "public class ChipThermal" in src
    assert 'model.param().set("L", "10[mm]");' in src
    assert 'HeatTransfer' in src

    # Physics Builder XML + prefs registration
    phb = generate_physics_builder_xml(
        str(tmp_path / "custom_diff"),
        interface_type="CustomDiffusion",
        label="Custom Diffusion",
        field_var="c",
    )
    assert Path(phb["path"]).is_file()
    prefs = tmp_path / "prefs"
    reg = register_physics_builder(phb["path"], prefs_dir=str(prefs))
    assert reg["ok"] is True
    assert "physicsbuilder.settings.usebuilder=on" in (prefs / "comsol.prefs").read_text(encoding="utf-8")
    assert "physicsbuilder.settings.usebuilder=on" in (prefs / "comsolserver.prefs").read_text(encoding="utf-8")

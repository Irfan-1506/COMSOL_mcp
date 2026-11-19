"""Custom COMSOL Physics Builder (.mphphb) XML generator and preferences registrar."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape


def _valid_ident(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid {label} '{value}'; must match [A-Za-z][A-Za-z0-9_]*. ")
    return value


def generate_physics_builder_xml(
    output_path: str,
    *,
    interface_type: str,
    label: str,
    field_var: str = "u",
    weak_expression: str = "-d*test(ux)*ux - d*test(uy)*uy + f*test(u)",
    diffusivity_default: str = "1",
    source_default: str = "0",
) -> dict[str, Any]:
    """Generate a minimal COMSOL Physics Builder `.mphphb` XML definition file."""
    itype = _valid_ident(interface_type, "interface_type")
    fvar = _valid_ident(field_var, "field_var")
    target = Path(output_path).resolve()
    if target.suffix.lower() != ".mphphb":
        target = target.with_suffix(".mphphb")
    target.parent.mkdir(parents=True, exist_ok=True)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<PhysicsBuilder version="1.0">
  <PhysicsInterface id="{escape(itype)}" type="{escape(itype)}" label="{escape(label)}" defaultTag="{escape(fvar)}phys">
    <DependentVariables>
      <Field name="{escape(fvar)}" shape="Lagrange" order="2" />
    </DependentVariables>
    <DomainFeature id="dom1" type="DomainEquation" label="{escape(label)} Equation" default="true">
      <UserInput name="d" label="Diffusivity" default="{escape(diffusivity_default)}" />
      <UserInput name="f" label="Source term" default="{escape(source_default)}" />
      <WeakEquation expression="{escape(weak_expression)}" />
    </DomainFeature>
    <BoundaryFeature id="dir1" type="DirichletBC" label="Dirichlet Boundary">
      <UserInput name="u0" label="Prescribed value" default="0" />
      <Constraint expression="{escape(fvar)}-u0" />
    </BoundaryFeature>
  </PhysicsInterface>
</PhysicsBuilder>
"""
    target.write_text(xml, encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "interface_type": itype,
        "label": label,
        "field_var": fvar,
        "note": "Register with `physicsbuilder_register`, then restart your COMSOL session to create instances of this interface.",
    }


def _default_prefs_dir() -> Path:
    home = Path.home()
    comsol_dir = home / ".comsol"
    if comsol_dir.is_dir():
        versions = sorted([p for p in comsol_dir.iterdir() if p.is_dir() and p.name.startswith("v")], reverse=True)
        if versions:
            return versions[0]
    return comsol_dir / "v62"


def _update_pref_file(pref_file: Path, mphphb_path: str, *, remove: bool = False) -> dict[str, Any]:
    pref_file.parent.mkdir(parents=True, exist_ok=True)
    lines = pref_file.read_text(encoding="utf-8", errors="replace").splitlines() if pref_file.is_file() else []
    kv: dict[str, str] = {}
    order: list[str] = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k = k.strip()
            kv[k] = v.strip()
            if k not in order:
                order.append(k)

    key = "physicsbuilder.settings.developmentfiles"
    existing = [p.strip() for p in kv.get(key, "").split(",") if p.strip()]
    norm = os.path.normpath(mphphb_path)
    if remove:
        existing = [p for p in existing if os.path.normpath(p) != norm]
    elif norm not in [os.path.normpath(p) for p in existing]:
        existing.append(norm)

    kv[key] = ",".join(existing)
    kv["physicsbuilder.settings.usebuilder"] = "on" if existing else "off"
    for k in (key, "physicsbuilder.settings.usebuilder"):
        if k not in order:
            order.append(k)

    out_lines = [f"{k}={kv[k]}" for k in order]
    pref_file.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return {"file": str(pref_file), "registered_files": existing, "usebuilder": kv["physicsbuilder.settings.usebuilder"]}


def register_physics_builder(
    mphphb_path: str,
    *,
    prefs_dir: Optional[str] = None,
    unregister: bool = False,
) -> dict[str, Any]:
    """Register (or unregister) a `.mphphb` file in both `comsol.prefs` and `comsolserver.prefs`."""
    p = Path(mphphb_path).resolve()
    if not unregister and not p.is_file():
        raise FileNotFoundError(f"Physics Builder file not found: {p}")
    target_dir = Path(prefs_dir).resolve() if prefs_dir else _default_prefs_dir()
    updated = [
        _update_pref_file(target_dir / "comsol.prefs", str(p), remove=unregister),
        _update_pref_file(target_dir / "comsolserver.prefs", str(p), remove=unregister),
    ]
    return {"ok": True, "action": "unregistered" if unregister else "registered", "path": str(p), "updated": updated}


def physics_builder_status(prefs_dir: Optional[str] = None) -> dict[str, Any]:
    """Read current Physics Builder development file registration from COMSOL prefs files."""
    target_dir = Path(prefs_dir).resolve() if prefs_dir else _default_prefs_dir()
    files: dict[str, Any] = {}
    for fname in ("comsol.prefs", "comsolserver.prefs"):
        p = target_dir / fname
        if not p.is_file():
            files[fname] = {"exists": False, "usebuilder": "off", "developmentfiles": []}
            continue
        kv: dict[str, str] = {}
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
        dev = [x.strip() for x in kv.get("physicsbuilder.settings.developmentfiles", "").split(",") if x.strip()]
        files[fname] = {
            "exists": True,
            "usebuilder": kv.get("physicsbuilder.settings.usebuilder", "off"),
            "developmentfiles": dev,
        }
    return {"prefs_dir": str(target_dir), "files": files}


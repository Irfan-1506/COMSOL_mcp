"""Standalone COMSOL Java model source generator (works without COMSOL installed)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..backends.base import java_string


def _sanitize_java_class(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", (name or "GeneratedModel").strip())
    if not cleaned:
        cleaned = "GeneratedModel"
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def generate_model_java_source(
    class_name: str = "GeneratedModel",
    spec: dict[str, Any] | None = None,
) -> str:
    """Render a standalone compilable COMSOL Java class from a declarative model spec."""
    cls = _sanitize_java_class(class_name)
    s = spec or {}
    comp = str(s.get("component", "comp1"))
    geom = str(s.get("geom", "geom1"))
    dim = int(s.get("dim", 3))

    lines: list[str] = [
        "import com.comsol.model.*;",
        "import com.comsol.model.util.*;",
        "",
        f"public class {cls} {{",
        "  public static Model run() throws Exception {",
        '    Model model = ModelUtil.create("Model");',
        f"    model.label({java_string(cls + '.mph')});",
    ]

    for k, v in (s.get("parameters") or {}).items():
        lines.append(f"    model.param().set({java_string(str(k))}, {java_string(str(v))});")

    lines.append(f"    model.component().create({java_string(comp)}, true);")
    lines.append(f"    model.component({java_string(comp)}).geom().create({java_string(geom)}, {dim});")

    for idx, gfeat in enumerate(s.get("geometries") or [], start=1):
        ftype = str(gfeat.get("type", "Block"))
        ftag = str(gfeat.get("tag", f"{ftype.lower()[:3]}{idx}"))
        lines.append(
            f"    model.component({java_string(comp)}).geom({java_string(geom)}).create({java_string(ftag)}, {java_string(ftype)});"
        )
        for pk, pv in (gfeat.get("params") or {}).items():
            if isinstance(pv, list):
                arr = ", ".join(java_string(str(x)) for x in pv)
                lines.append(
                    f"    model.component({java_string(comp)}).geom({java_string(geom)}).feature({java_string(ftag)}).set({java_string(str(pk))}, new String[]{{{arr}}});"
                )
            else:
                lines.append(
                    f"    model.component({java_string(comp)}).geom({java_string(geom)}).feature({java_string(ftag)}).set({java_string(str(pk))}, {java_string(str(pv))});"
                )

    lines.append(f"    model.component({java_string(comp)}).geom({java_string(geom)}).run();")

    for idx, mat in enumerate(s.get("materials") or [], start=1):
        mtag = str(mat.get("tag", f"mat{idx}"))
        lines.append(f'    model.component({java_string(comp)}).material().create({java_string(mtag)}, "Common");')
        for pk, pv in (mat.get("properties") or {}).items():
            lines.append(
                f'    model.component({java_string(comp)}).material({java_string(mtag)}).propertyGroup("def").set({java_string(str(pk))}, new String[]{{{java_string(str(pv))}}});'
            )

    for idx, phys in enumerate(s.get("physics") or [], start=1):
        ptag = str(phys.get("tag", f"phys{idx}"))
        ptype = str(phys.get("interface", "HeatTransfer"))
        lines.append(
            f"    model.component({java_string(comp)}).physics().create({java_string(ptag)}, {java_string(ptype)}, {java_string(geom)});"
        )

    mesh_size = int(s.get("mesh_size", 5))
    lines.append(f'    model.component({java_string(comp)}).mesh().create("mesh1");')
    lines.append(f'    model.component({java_string(comp)}).mesh("mesh1").autoMeshSize({mesh_size});')
    lines.append(f'    model.component({java_string(comp)}).mesh("mesh1").run();')

    for idx, st in enumerate(s.get("studies") or [], start=1):
        stag = str(st.get("tag", f"std{idx}"))
        stype = str(st.get("type", "Stationary"))
        step_tag = str(st.get("step_tag", stype.lower()[:4]))
        lines.append(f"    model.study().create({java_string(stag)});")
        lines.append(f"    model.study({java_string(stag)}).create({java_string(step_tag)}, {java_string(stype)});")
        if st.get("run", True):
            lines.append(f"    model.study({java_string(stag)}).run();")

    save_path = s.get("save_path")
    if save_path:
        lines.append(f"    model.save({java_string(str(save_path))});")

    lines.extend(
        [
            "    return model;",
            "  }",
            "  public static void main(String[] args) throws Exception { run(); }",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def write_model_java(filepath: str, class_name: str = "GeneratedModel", spec: dict[str, Any] | None = None) -> dict[str, Any]:
    target = Path(filepath).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    source = generate_model_java_source(class_name=class_name, spec=spec)
    target.write_text(source, encoding="utf-8")
    return {
        "ok": True,
        "filepath": str(target),
        "class_name": _sanitize_java_class(class_name),
        "lines": len(source.splitlines()),
        "compile_hint": f"comsolcompile {target.name} && comsolbatch -inputfile {_sanitize_java_class(class_name)}.class",
    }

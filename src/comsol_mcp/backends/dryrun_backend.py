"""In-memory dry-run COMSOL simulator backend.

Allows exercising the entire interactive modeling, validation, workflow, audit,
and MCP resource pipeline without a local COMSOL installation or license.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .base import sanitize_name, versioned_model_paths


@dataclass
class DryRunModel:
    name: str
    path: Optional[str] = None
    parameters: dict[str, dict[str, str]] = field(default_factory=dict)
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    studies: dict[str, dict[str, Any]] = field(default_factory=dict)
    solutions: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    plots: dict[str, dict[str, Any]] = field(default_factory=dict)
    functions: dict[str, dict[str, Any]] = field(default_factory=dict)
    multiphysics: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ensure_component(self, comp: str = "comp1") -> dict[str, Any]:
        if comp not in self.components:
            self.components[comp] = {
                "geometries": {},
                "selections": {},
                "materials": {},
                "physics": {},
                "meshes": {},
            }
        return self.components[comp]


class DryRunBackend:
    """Stateful in-memory backend mirroring the interactive MPh backend contract."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.connected: bool = False
        self.cores: int = 2
        self.models: dict[str, DryRunModel] = {}
        self.current_model: Optional[str] = None
        self.ops_log: list[dict[str, Any]] = []
        self._solver_state: dict[str, Any] = {"status": "idle", "progress": 0.0}

    def _record(self, op: str, **details: Any) -> dict[str, Any]:
        entry = {"ts": round(time.time(), 3), "op": op, **details}
        self.ops_log.append(entry)
        return entry

    def reset(self) -> dict[str, Any]:
        self.models.clear()
        self.current_model = None
        self.ops_log.clear()
        self._solver_state = {"status": "idle", "progress": 0.0}
        return {"ok": True, "mode": "dryrun", "message": "Dry-run simulator state reset."}

    def _get_model(self, model_name: Optional[str] = None) -> DryRunModel:
        target = model_name or self.current_model
        if not target or target not in self.models:
            raise ValueError(f"Model '{target}' not found. Loaded models: {sorted(self.models.keys())}")
        return self.models[target]

    # --- Session ---
    def start(self, cores: Optional[int] = None, version: Optional[str] = None) -> dict[str, Any]:
        self.connected = True
        if cores:
            self.cores = cores
        self._record("session_start", cores=self.cores, version=version or "dryrun-6.2")
        return {"ok": True, "backend": "dryrun", "connected": True, "cores": self.cores, "version": version or "dryrun-6.2"}

    def connect(self, host: str = "localhost", port: int = 2036) -> dict[str, Any]:
        self.connected = True
        self._record("session_connect", host=host, port=port)
        return {"ok": True, "backend": "dryrun", "connected": True, "host": host, "port": port}

    def disconnect(self) -> dict[str, Any]:
        self.connected = False
        self.models.clear()
        self.current_model = None
        self._record("session_disconnect")
        return {"ok": True, "backend": "dryrun", "connected": False}

    def status(self) -> dict[str, Any]:
        return {
            "backend": "dryrun",
            "connected": self.connected,
            "cores": self.cores,
            "current_model": self.current_model,
            "loaded_models": sorted(self.models.keys()),
            "ops_count": len(self.ops_log),
            "solver": dict(self._solver_state),
        }

    # --- Model lifecycle ---
    def model_create(self, name: str = "Model") -> dict[str, Any]:
        self.connected = True
        safe = sanitize_name(name)
        m = DryRunModel(name=safe)
        self.models[safe] = m
        self.current_model = safe
        self._record("model_create", name=safe)
        return {"ok": True, "model": safe, "backend": "dryrun"}

    def model_load(self, path: str, name: Optional[str] = None) -> dict[str, Any]:
        self.connected = True
        p = Path(path)
        mname = sanitize_name(name or p.stem)
        m = DryRunModel(name=mname, path=str(p))
        self.models[mname] = m
        self.current_model = mname
        self._record("model_load", name=mname, path=str(p))
        return {"ok": True, "model": mname, "path": str(p), "backend": "dryrun"}

    def model_save(self, path: Optional[str] = None, model_name: Optional[str] = None, versioned: bool = False, tag: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        if versioned:
            vpath, latest = versioned_model_paths(self.workspace, m.name, tag=tag)
            vpath.write_text(f"# dryrun-mph {m.name}\n", encoding="utf-8")
            latest.write_text(f"# dryrun-mph {m.name}\n", encoding="utf-8")
            m.path = str(vpath)
            self._record("model_save_version", model=m.name, path=str(vpath), latest=str(latest))
            return {"ok": True, "model": m.name, "path": str(vpath), "latest": str(latest), "backend": "dryrun"}
        target = Path(path) if path else (Path(m.path) if m.path else self.workspace / f"{m.name}.mph")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# dryrun-mph {m.name}\n", encoding="utf-8")
        m.path = str(target)
        self._record("model_save", model=m.name, path=str(target))
        return {"ok": True, "model": m.name, "path": str(target), "backend": "dryrun"}

    def model_list(self) -> dict[str, Any]:
        return {
            "backend": "dryrun",
            "current_model": self.current_model,
            "models": [
                {"name": name, "path": m.path, "components": list(m.components.keys()), "studies": list(m.studies.keys())}
                for name, m in self.models.items()
            ],
        }

    def model_set_current(self, name: str) -> dict[str, Any]:
        self._get_model(name)
        self.current_model = name
        return {"ok": True, "current_model": name}

    def model_clone(self, source: str, new_name: str) -> dict[str, Any]:
        src = self._get_model(source)
        cloned = copy.deepcopy(src)
        cloned.name = sanitize_name(new_name)
        cloned.path = None
        self.models[cloned.name] = cloned
        self.current_model = cloned.name
        self._record("model_clone", source=source, target=cloned.name)
        return {"ok": True, "source": source, "model": cloned.name}

    def model_remove(self, name: str) -> dict[str, Any]:
        self._get_model(name)
        del self.models[name]
        if self.current_model == name:
            self.current_model = next(iter(self.models), None)
        return {"ok": True, "removed": name, "current_model": self.current_model}

    def model_inspect(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {
            "backend": "dryrun",
            "name": m.name,
            "path": m.path,
            "parameters": copy.deepcopy(m.parameters),
            "components": copy.deepcopy(m.components),
            "multiphysics": copy.deepcopy(m.multiphysics),
            "studies": copy.deepcopy(m.studies),
            "solutions": list(m.solutions),
            "datasets": list(m.datasets),
            "plots": copy.deepcopy(m.plots),
            "functions": copy.deepcopy(m.functions),
        }

    def model_diff(self, model_a: str, model_b: str) -> dict[str, Any]:
        a = self.model_inspect(model_a)
        b = self.model_inspect(model_b)
        diffs: dict[str, Any] = {}
        for key in ("parameters", "components", "multiphysics", "studies", "solutions"):
            if a.get(key) != b.get(key):
                diffs[key] = {"model_a": a.get(key), "model_b": b.get(key)}
        return {"model_a": model_a, "model_b": model_b, "identical": len(diffs) == 0, "differences": diffs}

    # --- Parameters ---
    def param_set(self, name: str, expression: str, description: str = "", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        m.parameters[name] = {"expression": expression, "description": description}
        self._record("param_set", model=m.name, name=name, expression=expression)
        return {"ok": True, "name": name, "expression": expression, "description": description}

    def param_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "parameters": copy.deepcopy(m.parameters)}

    # --- Components & Geometry ---
    def component_create(self, tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        m.ensure_component(tag)
        self._record("component_create", model=m.name, tag=tag)
        return {"ok": True, "component": tag}

    def geometry_add(
        self,
        shape: str,
        params: dict[str, Any],
        *,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        dim: int = 3,
        feature_tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        geom = comp["geometries"].setdefault(geom_tag, {"dim": dim, "features": {}, "built": False})
        ftag = feature_tag or f"{shape.lower()[:3]}{len(geom['features']) + 1}"
        geom["features"][ftag] = {"type": shape, "params": dict(params)}
        geom["built"] = False
        self._record("geometry_add", model=m.name, geom=geom_tag, tag=ftag, shape=shape)
        return {"ok": True, "component": comp_tag, "geom": geom_tag, "tag": ftag, "type": shape}

    def geometry_build(self, geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        geom = comp["geometries"].get(geom_tag)
        if not geom:
            raise ValueError(f"Geometry '{geom_tag}' not found in component '{comp_tag}'.")
        geom["built"] = True
        n_feat = max(1, len(geom["features"]))
        geom["entity_counts"] = {"domains": n_feat, "boundaries": n_feat * 6 if geom["dim"] == 3 else n_feat * 4}
        self._record("geometry_build", model=m.name, geom=geom_tag)
        return {"ok": True, "geom": geom_tag, "built": True, "entity_counts": geom["entity_counts"]}

    def selection_create(
        self,
        tag: str,
        selection_type: str,
        config: dict[str, Any],
        *,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        comp["selections"][tag] = {"type": selection_type, "config": dict(config)}
        self._record("selection_create", model=m.name, tag=tag, type=selection_type)
        return {"ok": True, "component": comp_tag, "tag": tag, "type": selection_type}

    # --- Materials ---
    def material_add(
        self,
        tag: str,
        properties: dict[str, Any],
        *,
        label: Optional[str] = None,
        domains: Optional[list[int]] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        comp["materials"][tag] = {
            "label": label or tag,
            "properties": dict(properties),
            "domains": list(domains) if domains else ["all"],
        }
        self._record("material_add", model=m.name, tag=tag)
        return {"ok": True, "component": comp_tag, "tag": tag, "properties": dict(properties)}

    # --- Physics & Boundaries ---
    def physics_add(
        self,
        tag: str,
        interface: str,
        *,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        properties: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        comp["physics"][tag] = {
            "type": interface,
            "geom": geom_tag,
            "properties": dict(properties or {}),
            "features": {},
        }
        self._record("physics_add", model=m.name, tag=tag, interface=interface)
        return {"ok": True, "component": comp_tag, "tag": tag, "interface": interface, "geom": geom_tag}

    def physics_feature_add(
        self,
        physics_tag: str,
        feature_tag: str,
        feature_type: str,
        *,
        dim: Optional[int] = None,
        selection: Optional[list[int] | str] = None,
        properties: Optional[dict[str, Any]] = None,
        parent_feature: Optional[str] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        if physics_tag not in comp["physics"]:
            raise ValueError(f"Physics '{physics_tag}' not found in component '{comp_tag}'.")
        comp["physics"][physics_tag]["features"][feature_tag] = {
            "type": feature_type,
            "dim": dim,
            "selection": selection if selection is not None else "all",
            "properties": dict(properties or {}),
            "parent": parent_feature,
            "active": True,
        }
        self._record("physics_feature_add", model=m.name, physics=physics_tag, tag=feature_tag, type=feature_type)
        return {"ok": True, "physics": physics_tag, "feature": feature_tag, "type": feature_type}

    def multiphysics_add(
        self,
        tag: str,
        coupling_type: str,
        *,
        geom_tag: str = "geom1",
        comp_tag: str = "comp1",
        properties: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        m.multiphysics[tag] = {
            "type": coupling_type,
            "component": comp_tag,
            "geom": geom_tag,
            "properties": dict(properties or {}),
        }
        self._record("multiphysics_add", model=m.name, tag=tag, type=coupling_type)
        return {"ok": True, "tag": tag, "type": coupling_type}

    # --- Mesh ---
    def mesh_build(
        self,
        mesh_tag: str = "mesh1",
        *,
        size: int = 5,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        elements = max(100, (10 - min(max(size, 1), 9)) * 450)
        comp["meshes"][mesh_tag] = {"size": size, "built": True, "num_elements": elements}
        self._record("mesh_build", model=m.name, mesh=mesh_tag, size=size)
        return {"ok": True, "mesh": mesh_tag, "size": size, "num_elements": elements}

    # --- Study & Solving ---
    def study_create(
        self,
        study_tag: str = "std1",
        study_type: str = "Stationary",
        *,
        step_tag: Optional[str] = None,
        settings: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        stag = step_tag or study_type.lower()[:4]
        m.studies[study_tag] = {
            "steps": {stag: {"type": study_type, "settings": dict(settings or {})}},
            "solved": False,
        }
        self._record("study_create", model=m.name, study=study_tag, type=study_type)
        return {"ok": True, "study": study_tag, "step": stag, "type": study_type}

    def study_solve(
        self,
        study_tag: str = "std1",
        *,
        async_mode: bool = False,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        if study_tag not in m.studies:
            raise ValueError(f"Study '{study_tag}' not found.")
        m.studies[study_tag]["solved"] = True
        sol = f"sol_{study_tag}"
        dset = f"dset_{study_tag}"
        if sol not in m.solutions:
            m.solutions.append(sol)
        if dset not in m.datasets:
            m.datasets.append(dset)
        self._solver_state = {
            "status": "completed",
            "progress": 100.0,
            "study": study_tag,
            "model": m.name,
            "async": async_mode,
        }
        self._record("study_solve", model=m.name, study=study_tag, async_mode=async_mode)
        return {"ok": True, "model": m.name, "study": study_tag, "status": "completed", "solution": sol, "dataset": dset}

    def solver_progress(self) -> dict[str, Any]:
        return dict(self._solver_state)

    def solver_cancel(self) -> dict[str, Any]:
        self._solver_state["status"] = "cancelled"
        return {"ok": True, "status": "cancelled"}

    # --- Results & Generic Mutation ---
    def results_evaluate(
        self,
        expression: str,
        *,
        dataset: Optional[str] = None,
        global_eval: bool = False,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        if not m.solutions:
            raise ValueError("Model has no computed solutions yet. Run study_solve first.")
        self._record("results_evaluate", model=m.name, expression=expression, global_eval=global_eval)
        if global_eval:
            return {"ok": True, "expression": expression, "value": 305.42, "dataset": dataset or m.datasets[-1], "backend": "dryrun"}
        return {
            "ok": True,
            "expression": expression,
            "dataset": dataset or m.datasets[-1],
            "min": 293.15,
            "max": 318.62,
            "mean": 304.88,
            "sample_count": 64,
            "backend": "dryrun",
        }

    def results_export(
        self,
        kind: str,
        output_path: str,
        *,
        node_tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# dryrun export ({kind}) for {m.name}\n", encoding="utf-8")
        self._record("results_export", model=m.name, kind=kind, output=str(target))
        return {"ok": True, "kind": kind, "output": str(target), "node_tag": node_tag, "backend": "dryrun"}

    def node_mutate(
        self,
        category: str,
        action: str,
        tag: str,
        *,
        node_type: Optional[str] = None,
        properties: Optional[dict[str, Any]] = None,
        comp_tag: str = "comp1",
        parent_tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        buckets = {
            "function": m.functions,
            "plot": m.plots,
            "material": comp["materials"],
            "physics": comp["physics"],
            "study": m.studies,
        }
        bucket = buckets.get(category)
        if bucket is None:
            raise ValueError(f"Unsupported category '{category}'. Use one of: {sorted(buckets)}")
        if action == "delete":
            bucket.pop(tag, None)
        elif action == "toggle":
            if tag in bucket and isinstance(bucket[tag], dict):
                bucket[tag]["active"] = not bucket[tag].get("active", True)
        elif action in {"create", "set"}:
            entry = bucket.setdefault(tag, {"type": node_type or category, "properties": {}})
            if isinstance(entry, dict):
                if node_type:
                    entry["type"] = node_type
                if properties:
                    entry.setdefault("properties", {}).update(properties)
        else:
            raise ValueError(f"Unsupported action '{action}'. Use create, set, toggle, or delete.")
        self._record("node_mutate", model=m.name, category=category, action=action, tag=tag, parent=parent_tag)
        return {"ok": True, "category": category, "action": action, "tag": tag, "backend": "dryrun"}

    # --- Extended parity methods ---
    def model_export_java(self, output_path: str, model_name: Optional[str] = None) -> dict[str, Any]:
        from ..codegen.java_gen import write_model_java

        info = self.model_inspect(model_name)
        spec = {
            "parameters": {k: v["expression"] for k, v in info["parameters"].items()},
            "studies": [{"tag": k, "type": "Stationary"} for k in info["studies"].keys()],
        }
        res = write_model_java(output_path, class_name=info["name"], spec=spec)
        return {"ok": True, "model": info["name"], "java_path": res["filepath"], "backend": "dryrun"}

    def model_audit(self, model_name: Optional[str] = None) -> dict[str, Any]:
        info = self.model_inspect(model_name)
        summary = {
            "component_count": len(info["components"]),
            "parameter_count": len(info["parameters"]),
            "study_count": len(info["studies"]),
            "solution_count": len(info["solutions"]),
            "plot_count": len(info["plots"]),
        }
        return {"ok": True, "summary": summary, "tree": info, "backend": "dryrun"}

    def component_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "components": sorted(m.components.keys())}

    def param_get(self, name: str, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        if name not in m.parameters:
            raise KeyError(f"Parameter '{name}' not found.")
        return {"model": m.name, "name": name, **m.parameters[name]}

    def param_description(self, name: str, description: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        if name not in m.parameters:
            raise KeyError(f"Parameter '{name}' not found.")
        if description is not None:
            m.parameters[name]["description"] = description
        return {"model": m.name, "name": name, "description": m.parameters[name]["description"]}

    def param_sweep_setup(
        self,
        study_tag: str,
        parameter_name: str,
        values: list[str] | str,
        *,
        sweep_tag: str = "param",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        study = m.studies.setdefault(study_tag, {"steps": {}, "solved": False})
        vals = values if isinstance(values, list) else [values]
        study["steps"][sweep_tag] = {"type": "Parametric", "settings": {"pname": parameter_name, "plistarr": vals}}
        self._record("param_sweep_setup", model=m.name, study=study_tag, param=parameter_name, values=vals)
        return {"ok": True, "study": study_tag, "sweep_tag": sweep_tag, "parameter": parameter_name, "values": vals}

    def geometry_list(self, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        return {"component": comp_tag, "geometries": {k: {"dim": v["dim"], "built": v["built"], "features": list(v["features"].keys())} for k, v in comp["geometries"].items()}}

    def geometry_create(self, geom_tag: str = "geom1", dim: int = 3, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        comp = m.ensure_component(comp_tag)
        comp["geometries"].setdefault(geom_tag, {"dim": dim, "features": {}, "built": False})
        self._record("geometry_create", model=m.name, geom=geom_tag, dim=dim)
        return {"ok": True, "component": comp_tag, "geom": geom_tag, "dim": dim}

    def geometry_list_features(self, geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        geom = m.ensure_component(comp_tag)["geometries"].get(geom_tag)
        if not geom:
            raise ValueError(f"Geometry '{geom_tag}' not found.")
        return {"geom": geom_tag, "features": copy.deepcopy(geom["features"])}

    def geometry_boundary_info(self, geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        geom = m.ensure_component(comp_tag)["geometries"].get(geom_tag)
        if not geom:
            raise ValueError(f"Geometry '{geom_tag}' not found.")
        dim = geom["dim"]
        count = 6 if dim == 3 else (4 if dim == 2 else 2)
        labels = ["xmin", "xmax", "ymin", "ymax", "zmin", "zmax"][:count]
        boundaries = [{"index": i + 1, "side": labels[i]} for i in range(count)]
        return {"geom": geom_tag, "dim": dim, "boundary_count": count, "boundaries": boundaries, "backend": "dryrun"}

    def mesh_list(self, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"component": comp_tag, "meshes": sorted(m.ensure_component(comp_tag)["meshes"].keys())}

    def mesh_create_sequence(self, mesh_tag: str = "mesh1", geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        m.ensure_component(comp_tag)["meshes"].setdefault(mesh_tag, {"geom": geom_tag, "size": 5, "built": False, "num_elements": 0})
        return {"ok": True, "component": comp_tag, "mesh": mesh_tag, "geom": geom_tag}

    def mesh_info(self, mesh_tag: str = "mesh1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        mesh = m.ensure_component(comp_tag)["meshes"].get(mesh_tag)
        if not mesh:
            raise ValueError(f"Mesh '{mesh_tag}' not found.")
        return {"mesh": mesh_tag, **mesh, "backend": "dryrun"}

    def physics_list(self, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        phys = m.ensure_component(comp_tag)["physics"]
        return {"component": comp_tag, "physics": {k: {"type": v["type"], "geom": v.get("geom")} for k, v in phys.items()}}

    def physics_list_features(self, physics_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        ph = m.ensure_component(comp_tag)["physics"].get(physics_tag)
        if not ph:
            raise ValueError(f"Physics '{physics_tag}' not found.")
        return {"physics": physics_tag, "type": ph["type"], "features": copy.deepcopy(ph["features"])}

    def physics_remove(self, physics_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        phys = m.ensure_component(comp_tag)["physics"]
        if physics_tag not in phys:
            raise ValueError(f"Physics '{physics_tag}' not found.")
        del phys[physics_tag]
        return {"ok": True, "removed": physics_tag}

    def physics_feature_info(self, physics_tag: str, feature_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        ph = m.ensure_component(comp_tag)["physics"].get(physics_tag)
        if not ph or feature_tag not in ph["features"]:
            raise ValueError(f"Feature '{physics_tag}/{feature_tag}' not found.")
        return {"physics": physics_tag, "feature": feature_tag, **copy.deepcopy(ph["features"][feature_tag])}

    def physics_feature_set(
        self,
        physics_tag: str,
        feature_tag: str,
        properties: dict[str, Any],
        *,
        selection: Optional[list[int] | str] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        ph = m.ensure_component(comp_tag)["physics"].get(physics_tag)
        if not ph or feature_tag not in ph["features"]:
            raise ValueError(f"Feature '{physics_tag}/{feature_tag}' not found.")
        feat = ph["features"][feature_tag]
        feat["properties"].update(properties)
        if selection is not None:
            feat["selection"] = selection
        return {"ok": True, "physics": physics_tag, "feature": feature_tag, "properties": dict(feat["properties"]), "rejected_properties": []}

    def physics_feature_toggle(self, physics_tag: str, feature_tag: str, active: Optional[bool] = None, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        ph = m.ensure_component(comp_tag)["physics"].get(physics_tag)
        if not ph or feature_tag not in ph["features"]:
            raise ValueError(f"Feature '{physics_tag}/{feature_tag}' not found.")
        feat = ph["features"][feature_tag]
        feat["active"] = (not feat.get("active", True)) if active is None else bool(active)
        return {"ok": True, "physics": physics_tag, "feature": feature_tag, "active": feat["active"]}

    def physics_feature_delete(self, physics_tag: str, feature_tag: str, comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        ph = m.ensure_component(comp_tag)["physics"].get(physics_tag)
        if not ph or feature_tag not in ph["features"]:
            raise ValueError(f"Feature '{physics_tag}/{feature_tag}' not found.")
        del ph["features"][feature_tag]
        return {"ok": True, "physics": physics_tag, "deleted": feature_tag}

    def physics_interface_properties(
        self,
        physics_tag: str,
        *,
        set_properties: Optional[dict[str, Any]] = None,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        m = self._get_model(model_name)
        ph = m.ensure_component(comp_tag)["physics"].get(physics_tag)
        if not ph:
            raise ValueError(f"Physics '{physics_tag}' not found.")
        if set_properties:
            ph.setdefault("properties", {}).update(set_properties)
        return {"ok": True, "physics": physics_tag, "properties": copy.deepcopy(ph.get("properties", {}))}

    def study_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "studies": copy.deepcopy(m.studies)}

    def study_wait(self, timeout_seconds: float = 60.0) -> dict[str, Any]:
        return {"ok": True, "waited_seconds": 0.0, "timeout_seconds": timeout_seconds, "solver": dict(self._solver_state)}

    def solutions_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "solutions": list(m.solutions)}

    def datasets_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "datasets": list(m.datasets)}

    def solver_feature_list(self, sol_tag: str = "sol1", model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "solution": sol_tag, "features": ["st1", "v1", "s1"], "backend": "dryrun"}

    def solver_feature_set(self, sol_tag: str, feature_tag: str, properties: dict[str, Any], model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        self._record("solver_feature_set", model=m.name, sol=sol_tag, feature=feature_tag, properties=properties)
        return {"ok": True, "solution": sol_tag, "feature": feature_tag, "properties": properties, "backend": "dryrun"}

    def solver_feature_toggle(self, sol_tag: str, feature_tag: str, active: bool = True, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        self._record("solver_feature_toggle", model=m.name, sol=sol_tag, feature=feature_tag, active=active)
        return {"ok": True, "solution": sol_tag, "feature": feature_tag, "active": active, "backend": "dryrun"}

    def results_inner_values(self, dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "dataset": dataset or (m.datasets[-1] if m.datasets else "dset1"), "inner_values": [0.0, 0.5, 1.0], "backend": "dryrun"}

    def results_outer_values(self, dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "dataset": dataset or (m.datasets[-1] if m.datasets else "dset1"), "outer_values": [1.0], "backend": "dryrun"}

    def results_exports_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "exports": ["data1", "img1"], "backend": "dryrun"}

    def results_plots_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        return {"model": m.name, "plots": sorted(m.plots.keys()), "backend": "dryrun"}

    def results_interpolate(self, expression: str, coordinates: list[list[float]], dataset: Optional[str] = None, model_name: Optional[str] = None) -> dict[str, Any]:
        m = self._get_model(model_name)
        if not m.solutions:
            raise ValueError("Model has no computed solutions yet.")
        vals = [round(293.15 + idx * 2.5, 3) for idx in range(len(coordinates))]
        return {"ok": True, "expression": expression, "dataset": dataset or m.datasets[-1], "coordinates": coordinates, "values": vals, "backend": "dryrun"}


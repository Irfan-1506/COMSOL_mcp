"""Warm Python `mph`/JPype COMSOL backend with async solver and live Desktop Model1 support."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .base import sanitize_name, versioned_model_paths

# Prevent JPype/MPh INFO logging deadlock during JVM startup on Windows + COMSOL 6.x
logging.getLogger("mph").setLevel(logging.WARNING)

try:
    import mph  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    mph = None  # type: ignore


@dataclass
class SolverJobState:
    status: str = "idle"
    progress: float = 0.0
    message: str = ""
    study: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "study": self.study,
            "model": self.model,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def _to_list(java_iterable: Any) -> list[str]:
    if java_iterable is None:
        return []
    try:
        return [str(x) for x in list(java_iterable)]
    except Exception:
        return []


class MPhBackend:
    """Interactive warm-JVM COMSOL backend powered by Python `mph`."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._client: Any = None
        self._models: dict[str, Any] = {}
        self._current_model: Optional[str] = None
        self._lock = threading.RLock()
        self._solver_state = SolverJobState()
        self._solver_thread: Optional[threading.Thread] = None
        self._cancel_requested = threading.Event()
        self._live_desktop_mode = False

    @property
    def is_available(self) -> bool:
        return mph is not None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def _require_mph(self) -> None:
        if mph is None:
            raise RuntimeError("Python package 'mph' is not installed. Install with `pip install comsol-mcp-unified[mph]`.")

    def _require_client(self) -> Any:
        self._require_mph()
        if self._client is None:
            raise RuntimeError("No active COMSOL session. Call `comsol_start` or `comsol_connect` first.")
        return self._client

    def _get_model(self, model_name: Optional[str] = None) -> tuple[str, Any]:
        with self._lock:
            target = model_name or self._current_model
            if not target or target not in self._models:
                raise ValueError(f"Model '{target}' not loaded. Loaded models: {sorted(self._models.keys())}")
            return target, self._models[target]

    def _java_model(self, model: Any) -> Any:
        # Handle both mph.Model wrapper (`model.java`) and raw Java Model (`Model1` live attach)
        return model.java if hasattr(model, "java") else model

    # --- Session ---
    def start(self, cores: Optional[int] = None, version: Optional[str] = None) -> dict[str, Any]:
        self._require_mph()
        with self._lock:
            if self._client is None:
                kwargs: dict[str, Any] = {}
                if cores:
                    kwargs["cores"] = cores
                if version:
                    kwargs["version"] = version
                self._client = mph.start(**kwargs)
            self._live_desktop_mode = False
            return {
                "ok": True,
                "backend": "mph",
                "connected": True,
                "version": str(getattr(self._client, "version", version or "unknown")),
                "cores": getattr(self._client, "cores", cores),
            }

    def connect(
        self,
        host: str = "localhost",
        port: int = 2036,
        *,
        attach_desktop_model: Optional[str] = None,
        show_progress: bool = True,
        show_plots: bool = True,
    ) -> dict[str, Any]:
        """Connect to a COMSOL Server, optionally attaching directly to Desktop's live `Model1`."""
        self._require_mph()
        with self._lock:
            self._client = mph.Client(host=host, port=port)
            if attach_desktop_model:
                java = self._client.java
                try:
                    java.showProgress(bool(show_progress))
                    java.showPlots(bool(show_plots))
                except Exception:
                    pass
                jm = java.model(attach_desktop_model)
                self._models[attach_desktop_model] = jm
                self._current_model = attach_desktop_model
                self._live_desktop_mode = True
            return {
                "ok": True,
                "backend": "mph",
                "connected": True,
                "host": host,
                "port": port,
                "live_desktop_model": attach_desktop_model,
            }

    def disconnect(self) -> dict[str, Any]:
        with self._lock:
            if self._client is not None:
                try:
                    self._client.clear()
                except Exception:
                    pass
            self._models.clear()
            self._current_model = None
            self._live_desktop_mode = False
            return {"ok": True, "backend": "mph", "connected": self._client is not None, "note": "Cleared loaded models (mph JVM singleton kept warm)."}

    def status(self) -> dict[str, Any]:
        return {
            "backend": "mph",
            "mph_installed": self.is_available,
            "connected": self.connected,
            "live_desktop_mode": self._live_desktop_mode,
            "current_model": self._current_model,
            "loaded_models": sorted(self._models.keys()),
            "solver": self._solver_state.to_dict(),
        }

    # --- Model CRUD ---
    def model_create(self, name: str = "Model") -> dict[str, Any]:
        client = self._require_client()
        safe = sanitize_name(name)
        with self._lock:
            model = client.create(safe)
            self._models[safe] = model
            self._current_model = safe
        return {"ok": True, "model": safe, "backend": "mph"}

    def model_load(self, path: str, name: Optional[str] = None) -> dict[str, Any]:
        client = self._require_client()
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Model file not found: {p}")
        mname = sanitize_name(name or p.stem)
        with self._lock:
            model = client.load(str(p))
            self._models[mname] = model
            self._current_model = mname
        return {"ok": True, "model": mname, "path": str(p.resolve()), "backend": "mph"}

    def model_save(
        self,
        path: Optional[str] = None,
        model_name: Optional[str] = None,
        versioned: bool = False,
        tag: Optional[str] = None,
    ) -> dict[str, Any]:
        mname, model = self._get_model(model_name)
        jm = self._java_model(model)
        if versioned:
            vpath, latest = versioned_model_paths(self.workspace, mname, tag=tag)
            jm.save(str(vpath))
            jm.save(str(latest))
            return {"ok": True, "model": mname, "path": str(vpath), "latest": str(latest), "backend": "mph"}
        target = Path(path) if path else self.workspace / f"{mname}.mph"
        target.parent.mkdir(parents=True, exist_ok=True)
        jm.save(str(target))
        return {"ok": True, "model": mname, "path": str(target.resolve()), "backend": "mph"}

    def model_list(self) -> dict[str, Any]:
        return {"backend": "mph", "current_model": self._current_model, "models": sorted(self._models.keys())}

    def model_set_current(self, name: str) -> dict[str, Any]:
        self._get_model(name)
        self._current_model = name
        return {"ok": True, "current_model": name}

    def model_clone(self, source: str, new_name: str) -> dict[str, Any]:
        client = self._require_client()
        _, model = self._get_model(source)
        safe = sanitize_name(new_name)
        tmp = self.workspace / f".clone_{safe}_{int(time.time())}.mph"
        self._java_model(model).save(str(tmp))
        try:
            cloned = client.load(str(tmp))
            with self._lock:
                self._models[safe] = cloned
                self._current_model = safe
        finally:
            tmp.unlink(missing_ok=True)
        return {"ok": True, "source": source, "model": safe}

    def model_remove(self, name: str) -> dict[str, Any]:
        client = self._require_client()
        _, model = self._get_model(name)
        with self._lock:
            try:
                client.remove(model)
            except Exception:
                pass
            del self._models[name]
            if self._current_model == name:
                self._current_model = next(iter(self._models), None)
        return {"ok": True, "removed": name, "current_model": self._current_model}

    def model_inspect(self, model_name: Optional[str] = None) -> dict[str, Any]:
        mname, model = self._get_model(model_name)
        jm = self._java_model(model)
        params: dict[str, dict[str, str]] = {}
        try:
            for p in _to_list(jm.param().varnames()):
                desc = ""
                try:
                    desc = str(jm.param().descr(p))
                except Exception:
                    pass
                params[p] = {"expression": str(jm.param().get(p)), "description": desc}
        except Exception:
            pass

        components: dict[str, Any] = {}
        for ctag in _to_list(jm.component().tags()):
            comp = jm.component(ctag)
            geoms = {}
            for gtag in _to_list(comp.geom().tags()):
                g = comp.geom(gtag)
                geoms[gtag] = {"features": _to_list(g.feature().tags())}
            mats = {}
            for mtag in _to_list(comp.material().tags()):
                mat = comp.material(mtag)
                mats[mtag] = {"label": str(mat.label())}
            phys = {}
            for ptag in _to_list(comp.physics().tags()):
                ph = comp.physics(ptag)
                feats = {}
                for ftag in _to_list(ph.feature().tags()):
                    feat = ph.feature(ftag)
                    feats[ftag] = {"type": str(feat.getType())}
                phys[ptag] = {"type": str(ph.getType()), "features": feats}
            meshes = {mtag: {"features": _to_list(comp.mesh(mtag).feature().tags())} for mtag in _to_list(comp.mesh().tags())}
            sels = _to_list(comp.selection().tags())
            components[ctag] = {
                "geometries": geoms,
                "selections": sels,
                "materials": mats,
                "physics": phys,
                "meshes": meshes,
            }

        studies = {
            stag: {"steps": _to_list(jm.study(stag).feature().tags())}
            for stag in _to_list(jm.study().tags())
        }
        return {
            "backend": "mph",
            "name": mname,
            "parameters": params,
            "components": components,
            "studies": studies,
            "solutions": _to_list(jm.sol().tags()),
            "datasets": _to_list(jm.result().dataset().tags()),
            "plots": _to_list(jm.result().tags()),
        }

    def model_diff(self, model_a: str, model_b: str) -> dict[str, Any]:
        a = self.model_inspect(model_a)
        b = self.model_inspect(model_b)
        diffs = {k: {"model_a": a.get(k), "model_b": b.get(k)} for k in ("parameters", "components", "studies", "solutions") if a.get(k) != b.get(k)}
        return {"model_a": model_a, "model_b": model_b, "identical": len(diffs) == 0, "differences": diffs}

    def model_export_java(self, output_path: str, model_name: Optional[str] = None) -> dict[str, Any]:
        mname, model = self._get_model(model_name)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._java_model(model).save(str(target), "java")
        return {"ok": True, "model": mname, "java_path": str(target.resolve())}

    # --- Parameters ---
    def param_set(self, name: str, expression: str, description: str = "", model_name: Optional[str] = None) -> dict[str, Any]:
        _, model = self._get_model(model_name)
        jm = self._java_model(model)
        if description:
            jm.param().set(name, expression, description)
        else:
            jm.param().set(name, expression)
        return {"ok": True, "name": name, "expression": expression, "description": description}

    def param_list(self, model_name: Optional[str] = None) -> dict[str, Any]:
        info = self.model_inspect(model_name)
        return {"model": info["name"], "parameters": info["parameters"]}

    # --- Components, Geometry, Selections ---
    def component_create(self, tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        _, model = self._get_model(model_name)
        self._java_model(model).component().create(tag, True)
        return {"ok": True, "component": tag}

    def _ensure_geom(self, jm: Any, comp_tag: str, geom_tag: str, dim: int) -> Any:
        if comp_tag not in _to_list(jm.component().tags()):
            jm.component().create(comp_tag, True)
        comp = jm.component(comp_tag)
        if geom_tag not in _to_list(comp.geom().tags()):
            comp.geom().create(geom_tag, int(dim))
        return comp.geom(geom_tag)

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
        _, model = self._get_model(model_name)
        jm = self._java_model(model)
        geom = self._ensure_geom(jm, comp_tag, geom_tag, dim)
        existing = _to_list(geom.feature().tags())
        ftag = feature_tag or f"{shape.lower()[:3]}{len(existing) + 1}"
        feat = geom.create(ftag, shape)
        for k, v in params.items():
            if k in {"input", "input2"} and isinstance(v, list):
                feat.selection(k).set(v)
            else:
                feat.set(k, v)
        return {"ok": True, "component": comp_tag, "geom": geom_tag, "tag": ftag, "type": shape}

    def geometry_build(self, geom_tag: str = "geom1", comp_tag: str = "comp1", model_name: Optional[str] = None) -> dict[str, Any]:
        _, model = self._get_model(model_name)
        geom = self._java_model(model).component(comp_tag).geom(geom_tag)
        geom.run()
        return {"ok": True, "geom": geom_tag, "built": True}

    def selection_create(
        self,
        tag: str,
        selection_type: str,
        config: dict[str, Any],
        *,
        comp_tag: str = "comp1",
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        _, model = self._get_model(model_name)
        comp = self._java_model(model).component(comp_tag)
        sel = comp.selection().create(tag, selection_type)
        for k, v in config.items():
            if k == "entities" and isinstance(v, list):
                sel.set(v)
            else:
                sel.set(k, v)
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
        _, model = self._get_model(model_name)
        comp = self._java_model(model).component(comp_tag)
        mat = comp.material().create(tag, "Common")
        if label:
            mat.label(label)
        if domains:
            mat.selection().set(domains)
        else:
            mat.selection().all()
        pg = mat.propertyGroup("def")
        for k, v in properties.items():
            pg.set(k, str(v))
        return {"ok": True, "component": comp_tag, "tag": tag, "properties": properties}

    # --- Physics & Multiphysics ---
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
        _, model = self._get_model(model_name)
        comp = self._java_model(model).component(comp_tag)
        phys = comp.physics().create(tag, interface, geom_tag)
        for k, v in (properties or {}).items():
            phys.prop(k).set(k, v) if hasattr(phys, "prop") else None
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
        _, model = self._get_model(model_name)
        phys = self._java_model(model).component(comp_tag).physics(physics_tag)
        container = phys.feature(parent_feature) if parent_feature else phys
        feat = container.create(feature_tag, feature_type, dim) if dim is not None else container.create(feature_tag, feature_type)
        if selection == "all":
            feat.selection().all()
        elif isinstance(selection, list):
            feat.selection().set(selection)
        elif isinstance(selection, str) and selection:
            feat.selection().named(selection)
        rejected: list[str] = []
        for k, v in (properties or {}).items():
            try:
                feat.set(k, v)
            except Exception:
                rejected.append(k)
        return {"ok": True, "physics": physics_tag, "feature": feature_tag, "type": feature_type, "rejected_properties": rejected}

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
        _, model = self._get_model(model_name)
        mp = self._java_model(model).component(comp_tag).multiphysics().create(tag, coupling_type, geom_tag)
        for k, v in (properties or {}).items():
            mp.set(k, v)
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
        _, model = self._get_model(model_name)
        comp = self._java_model(model).component(comp_tag)
        if mesh_tag not in _to_list(comp.mesh().tags()):
            comp.mesh().create(mesh_tag)
        mesh = comp.mesh(mesh_tag)
        mesh.autoMeshSize(int(size))
        mesh.run()
        return {"ok": True, "mesh": mesh_tag, "size": size}

    # --- Study & Async Solving ---
    def study_create(
        self,
        study_tag: str = "std1",
        study_type: str = "Stationary",
        *,
        step_tag: Optional[str] = None,
        settings: Optional[dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        _, model = self._get_model(model_name)
        jm = self._java_model(model)
        if study_tag not in _to_list(jm.study().tags()):
            jm.study().create(study_tag)
        stag = step_tag or study_type.lower()[:4]
        step = jm.study(study_tag).create(stag, study_type)
        for k, v in (settings or {}).items():
            step.set(k, v)
        return {"ok": True, "study": study_tag, "step": stag, "type": study_type}

    def study_solve(
        self,
        study_tag: str = "std1",
        *,
        async_mode: bool = False,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        mname, model = self._get_model(model_name)
        jm = self._java_model(model)

        def _run() -> None:
            self._solver_state = SolverJobState(
                status="running",
                progress=10.0,
                message=f"Solving study '{study_tag}'...",
                study=study_tag,
                model=mname,
                started_at=datetime.now().isoformat(),
            )
            try:
                jm.study(study_tag).run()
                if self._cancel_requested.is_set():
                    self._solver_state.status = "cancelled"
                    self._solver_state.message = "Cancellation requested during solve."
                else:
                    self._solver_state.status = "completed"
                    self._solver_state.progress = 100.0
                    self._solver_state.message = f"Study '{study_tag}' solved."
            except Exception as exc:
                self._solver_state.status = "failed"
                self._solver_state.error = f"{exc}\n{traceback.format_exc(limit=4)}"
            finally:
                self._solver_state.finished_at = datetime.now().isoformat()

        self._cancel_requested.clear()
        if async_mode:
            if self._solver_thread and self._solver_thread.is_alive():
                raise RuntimeError("A study solve is already running in this session.")
            self._solver_thread = threading.Thread(target=_run, name="comsol-mph-solve", daemon=True)
            self._solver_thread.start()
            return {"ok": True, "model": mname, "study": study_tag, "status": "running", "async": True}

        _run()
        if self._solver_state.status == "failed":
            raise RuntimeError(self._solver_state.error or "Solve failed.")
        return {"ok": True, "model": mname, "study": study_tag, "status": self._solver_state.status}

    def solver_progress(self) -> dict[str, Any]:
        return self._solver_state.to_dict()

    def solver_cancel(self) -> dict[str, Any]:
        self._cancel_requested.set()
        return {"ok": True, "status": "cancel_requested", "note": "MPh in-process solves cannot hard-kill JVM threads; use the `batch` profile for hard process-tree cancellation."}

    # --- Results & Generic Mutation ---
    def results_evaluate(
        self,
        expression: str,
        *,
        dataset: Optional[str] = None,
        global_eval: bool = False,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        _, model = self._get_model(model_name)
        if hasattr(model, "evaluate"):
            vals = model.evaluate(expression, dataset=dataset) if dataset else model.evaluate(expression)
            try:
                import numpy as np  # type: ignore

                arr = np.asarray(vals, dtype=float)
                if global_eval or arr.size == 1:
                    return {"ok": True, "expression": expression, "value": float(arr.reshape(-1)[0])}
                return {
                    "ok": True,
                    "expression": expression,
                    "min": float(np.nanmin(arr)),
                    "max": float(np.nanmax(arr)),
                    "mean": float(np.nanmean(arr)),
                    "sample_count": int(arr.size),
                }
            except Exception:
                return {"ok": True, "expression": expression, "raw": str(vals)}
        raise RuntimeError("Direct evaluation requires an mph.Model wrapper; use batch export for raw Java models.")

    def results_export(
        self,
        kind: str,
        output_path: str,
        *,
        node_tag: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> dict[str, Any]:
        _, model = self._get_model(model_name)
        target = Path(output_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        jm = self._java_model(model)
        if kind == "image":
            exp_tag = node_tag or "img_mcp"
            if exp_tag not in _to_list(jm.result().export().tags()):
                jm.result().export().create(exp_tag, "Image")
            exp = jm.result().export(exp_tag)
            exp.set("pngfilename", str(target))
            exp.run()
        else:
            exp_tag = node_tag or "data_mcp"
            if exp_tag not in _to_list(jm.result().export().tags()):
                jm.result().export().create(exp_tag, "Data")
            exp = jm.result().export(exp_tag)
            exp.set("filename", str(target))
            exp.run()
        return {"ok": True, "kind": kind, "output": str(target), "node_tag": exp_tag}

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
        _, model = self._get_model(model_name)
        jm = self._java_model(model)
        comp = jm.component(comp_tag)
        container_map = {
            "function": jm.func(),
            "plot": jm.result(),
            "material": comp.material(),
            "physics": comp.physics(),
            "study": jm.study(),
        }
        container = container_map.get(category)
        if container is None:
            raise ValueError(f"Unsupported category '{category}'. Use: {sorted(container_map)}")
        if action == "create":
            node = container.create(tag, node_type) if node_type else container.create(tag)
            for k, v in (properties or {}).items():
                node.set(k, v)
        elif action == "set":
            node = container.get(tag) if hasattr(container, "get") else container(tag)
            for k, v in (properties or {}).items():
                node.set(k, v)
        elif action == "toggle":
            node = container.get(tag) if hasattr(container, "get") else container(tag)
            node.active(not bool(node.isActive()))
        elif action == "delete":
            container.remove(tag)
        else:
            raise ValueError(f"Unsupported action '{action}'.")
        return {"ok": True, "category": category, "action": action, "tag": tag}

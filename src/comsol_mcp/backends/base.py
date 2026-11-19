"""Shared utilities for safe workspace paths, Java escaping, and model versioning."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def java_string(value: str) -> str:
    """Safely encode a Python string as a Java double-quoted string literal."""
    return json.dumps(value, ensure_ascii=True)


def sanitize_name(name: str, fallback: str = "model") -> str:
    """Sanitize a model name for safe filesystem paths."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", (name or "").strip()).strip("._")
    return cleaned or fallback


def confined_path(
    root: Path,
    relative_or_abs: str,
    *,
    forbidden_subdir: Optional[Path] = None,
    suffix: Optional[str] = None,
    must_exist: bool = False,
) -> Path:
    """Resolve a path strictly inside `root` and outside `forbidden_subdir`."""
    root_resolved = root.resolve()
    target = (root_resolved / relative_or_abs).resolve()
    if not target.is_relative_to(root_resolved) or target == root_resolved:
        raise ValueError(f"Path '{relative_or_abs}' must stay inside workspace '{root_resolved}'.")
    if forbidden_subdir is not None and target.is_relative_to(forbidden_subdir.resolve()):
        raise ValueError(f"Path '{relative_or_abs}' cannot target internal directory '{forbidden_subdir.name}'.")
    if suffix and target.suffix.lower() != suffix.lower():
        raise ValueError(f"Expected a '{suffix}' file, got '{target.name}'.")
    if must_exist and not target.is_file():
        raise FileNotFoundError(f"File not found: {target}")
    return target


def versioned_model_paths(workspace: Path, model_name: str, tag: Optional[str] = None) -> tuple[Path, Path]:
    """Return (timestamped_path, latest_path) under `<workspace>/<model_name>/`."""
    safe = sanitize_name(model_name)
    folder = workspace / safe
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{sanitize_name(tag)}" if tag else ""
    versioned = folder / f"{safe}_{stamp}{suffix}.mph"
    latest = folder / f"{safe}_latest.mph"
    return versioned, latest
